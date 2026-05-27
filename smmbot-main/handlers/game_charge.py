"""
🎮 شحن الألعاب اليدوي — handlers/game_charge.py

تدفق المستخدم:
  زر "شحن الألعاب" → قائمة التطبيقات → اختيار باقة
  → إرسال game ID → تأكيد → خصم رصيد → إرسال للأدمن

تدفق الأدمن:
  رسالة بزر قبول/رفض → الأدمن يقبل أو يرفض
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from database import Database
from utils.keyboards import (
    game_apps_kb, game_packages_kb, game_confirm_kb,
    admin_approve_game_kb, back_to_main_kb, main_menu_kb
)
from config import ADMIN_ID

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
#  عرض قائمة التطبيقات
# ══════════════════════════════════════════════════════════

async def game_charge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر «شحن الألعاب» في القائمة الرئيسية."""
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]
    user = update.effective_user

    if db.is_banned(user.id):
        await query.answer("🚫 أنت محظور!", show_alert=True)
        return

    apps = db.get_game_apps(active_only=True)
    if not apps:
        await query.edit_message_text(
            "⚠️ لا توجد ألعاب متاحة حالياً.\nتواصل مع الأدمن.",
            reply_markup=back_to_main_kb(),
        )
        return

    await query.edit_message_text(
        "🎮 <b>شحن الألعاب</b>\n\nاختر اللعبة التي تريد شحنها:",
        reply_markup=game_apps_kb(apps),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  اختيار تطبيق → عرض الباقات
# ══════════════════════════════════════════════════════════

async def game_app_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]

    app_id = int(query.data.split("_")[2])
    app    = db.get_game_app(app_id)
    if not app or not app["is_active"]:
        await query.answer("❌ اللعبة غير متاحة.", show_alert=True)
        return

    packages = db.get_game_packages(app_id)
    if not packages:
        await query.answer("⚠️ لا توجد باقات لهذه اللعبة بعد.", show_alert=True)
        return

    balance = db.get_balance(update.effective_user.id)
    await query.edit_message_text(
        f"{app['emoji']} <b>{app['name']}</b>\n\n"
        f"💳 رصيدك الحالي: <b>${balance:.2f}</b>\n\n"
        f"اختر الباقة المطلوبة:",
        reply_markup=game_packages_kb(packages, app_id),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  اختيار باقة → طلب game ID
# ══════════════════════════════════════════════════════════

async def game_pkg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]
    user = update.effective_user

    pkg_id = int(query.data.split("_")[2])
    pkg    = db.get_game_package(pkg_id)
    if not pkg:
        await query.answer("❌ الباقة غير موجودة.", show_alert=True)
        return

    app    = db.get_game_app(pkg["app_id"])
    balance = db.get_balance(user.id)

    if balance < pkg["price"]:
        await query.edit_message_text(
            f"⚠️ <b>رصيد غير كافٍ!</b>\n\n"
            f"💳 رصيدك: <b>${balance:.2f}</b>\n"
            f"💵 سعر الباقة: <b>${pkg['price']:.2f}</b>\n\n"
            f"اشحن رصيدك أولاً من القائمة الرئيسية.",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        return

    # حفظ بيانات الطلب
    context.user_data["game_pkg_id"]  = pkg_id
    context.user_data["game_app_id"]  = pkg["app_id"]
    context.user_data["game_price"]   = pkg["price"]
    context.user_data["game_state"]   = "waiting_game_id"

    from utils.keyboards import cancel_kb
    await query.edit_message_text(
        f"{app['emoji']} <b>{app['name']}</b> — {pkg['name']}\n\n"
        f"💰 السعر: <b>${pkg['price']:.2f}</b>\n\n"
        f"🆔 أرسل <b>ID اللاعب</b> في اللعبة:",
        reply_markup=cancel_kb("game_charge"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  معالج رسائل شحن الألعاب
# ══════════════════════════════════════════════════════════

async def game_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """يُستدعى من message_router. Returns True إذا تم معالجة الرسالة."""
    if context.user_data.get("game_state") != "waiting_game_id":
        return False

    db: Database = context.bot_data["db"]
    user = update.effective_user
    game_id = (update.message.text or "").strip()

    if not game_id:
        await update.message.reply_text("❌ أرسل ID اللاعب.")
        return True

    pkg_id  = context.user_data.get("game_pkg_id")
    app_id  = context.user_data.get("game_app_id")
    price   = context.user_data.get("game_price")

    pkg = db.get_game_package(pkg_id)
    app = db.get_game_app(app_id)

    if not pkg or not app:
        await update.message.reply_text("❌ انتهت الجلسة. ابدأ من جديد.")
        _clear_game(context)
        return True

    balance = db.get_balance(user.id)
    context.user_data["game_id"]    = game_id
    context.user_data["game_state"] = "waiting_game_confirm"

    # إنشاء طلب مؤقت في DB
    order_id = db.create_game_order(
        user_tg_id=user.id,
        app_id=app_id,
        package_id=pkg_id,
        game_id=game_id,
        price=price,
    )
    context.user_data["game_order_id"] = order_id

    await update.message.reply_text(
        f"📋 <b>ملخّص الطلب</b>\n\n"
        f"{app['emoji']} اللعبة:  <b>{app['name']}</b>\n"
        f"🎁 الباقة:  <b>{pkg['name']}</b>\n"
        f"🆔 ID اللاعب: <code>{game_id}</code>\n"
        f"💰 التكلفة: <b>${price:.2f}</b>\n"
        f"💳 رصيدك:  <b>${balance:.2f}</b>\n\n"
        f"هل تؤكد الطلب؟",
        reply_markup=game_confirm_kb(order_id),
        parse_mode="HTML",
    )
    return True


# ══════════════════════════════════════════════════════════
#  تأكيد الطلب
# ══════════════════════════════════════════════════════════

async def game_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]
    user = update.effective_user

    order_id = int(query.data.split("_")[2])
    order    = db.get_game_order(order_id)

    if not order or order["status"] != "pending" or order["user_tg_id"] != user.id:
        await query.edit_message_text("❌ الطلب غير موجود أو منتهي.", reply_markup=back_to_main_kb())
        _clear_game(context)
        return

    price = order["price"]

    # خصم الرصيد
    deducted = db.deduct_balance(user.id, price)
    if not deducted:
        balance = db.get_balance(user.id)
        await query.edit_message_text(
            f"⚠️ <b>رصيد غير كافٍ!</b>\n💳 رصيدك: ${balance:.2f}\n💵 التكلفة: ${price:.2f}",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        _clear_game(context)
        return

    _clear_game(context)

    # إرسال للأدمن
    username = f"@{user.username}" if user.username else f"#{user.id}"
    adm_text = (
        f"🎮 <b>طلب شحن لعبة جديد!</b>\n\n"
        f"👤 المستخدم: <code>{user.id}</code> ({username})\n"
        f"{order['app_emoji']} اللعبة:  <b>{order['app_name']}</b>\n"
        f"🎁 الباقة:  <b>{order['pkg_name']}</b>\n"
        f"🆔 ID اللاعب: <code>{order['game_id']}</code>\n"
        f"💰 السعر:  <b>${price:.2f}</b>\n"
        f"🆔 رقم الطلب: <code>{order_id}</code>"
    )
    try:
        adm_msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=adm_text,
            reply_markup=admin_approve_game_kb(order_id),
            parse_mode="HTML",
        )
        db.set_game_order_admin_msg(order_id, adm_msg.message_id)
    except TelegramError as e:
        logger.warning(f"[GAME] فشل إرسال إشعار الأدمن: {e}")

    # إشعار قناة الطلبات
    await _notify_game_order_channel(context.bot, db, order, user)

    await query.edit_message_text(
        f"✅ <b>تم إرسال طلبك!</b>\n\n"
        f"{order['app_emoji']} اللعبة: <b>{order['app_name']}</b>\n"
        f"🎁 الباقة: <b>{order['pkg_name']}</b>\n"
        f"🆔 رقم طلبك: <code>{order_id}</code>\n\n"
        f"⏳ في انتظار موافقة الأدمن... سيصلك إشعار فور المعالجة.",
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  إلغاء الطلب
# ══════════════════════════════════════════════════════════

async def game_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]

    # إلغاء الطلب المؤقت إن وُجد
    order_id = context.user_data.get("game_order_id")
    if order_id:
        db.update_game_order_status(order_id, "canceled")

    _clear_game(context)
    apps = db.get_game_apps()
    await query.edit_message_text(
        "❌ تم إلغاء الطلب.\n\n🎮 <b>شحن الألعاب</b>\n\nاختر اللعبة:",
        reply_markup=game_apps_kb(apps),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  الأدمن: قبول الطلب
# ══════════════════════════════════════════════════════════

async def game_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]

    order_id = int(query.data.split("_")[2])
    order    = db.get_game_order(order_id)

    if not order:
        await query.edit_message_text("❌ الطلب غير موجود.")
        return

    if order["status"] != "pending":
        await query.edit_message_text(
            f"⚠️ الطلب #{order_id} تم معالجته مسبقاً (الحالة: {order['status']})."
        )
        return

    db.update_game_order_status(order_id, "completed")

    # إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id=order["user_tg_id"],
            text=(
                f"✅ <b>تم إكمال طلبك!</b>\n\n"
                f"{order['app_emoji']} اللعبة: <b>{order['app_name']}</b>\n"
                f"🎁 الباقة: <b>{order['pkg_name']}</b>\n"
                f"🆔 ID اللاعب: <code>{order['game_id']}</code>\n"
                f"🆔 رقم الطلب: <code>{order_id}</code>\n\n"
                f"شكراً لثقتك بنا! 💙"
            ),
            parse_mode="HTML",
        )
    except TelegramError as e:
        logger.warning(f"[GAME] فشل إشعار المستخدم بالقبول: {e}")

    await query.edit_message_text(
        f"✅ <b>تم قبول الطلب #{order_id}</b>\n\n"
        f"{order['app_emoji']} {order['app_name']} — {order['pkg_name']}\n"
        f"🆔 ID: {order['game_id']}\n"
        f"👤 المستخدم: {order['user_tg_id']}",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  الأدمن: رفض الطلب
# ══════════════════════════════════════════════════════════

async def game_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]

    order_id = int(query.data.split("_")[2])
    order    = db.get_game_order(order_id)

    if not order:
        await query.edit_message_text("❌ الطلب غير موجود.")
        return

    if order["status"] != "pending":
        await query.edit_message_text(
            f"⚠️ الطلب #{order_id} تم معالجته مسبقاً (الحالة: {order['status']})."
        )
        return

    db.update_game_order_status(order_id, "canceled")
    # استعادة الرصيد
    db.add_balance(order["user_tg_id"], order["price"])

    # إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id=order["user_tg_id"],
            text=(
                f"❌ <b>تم رفض طلبك!</b>\n\n"
                f"{order['app_emoji']} اللعبة: <b>{order['app_name']}</b>\n"
                f"🎁 الباقة: <b>{order['pkg_name']}</b>\n"
                f"🆔 رقم الطلب: <code>{order_id}</code>\n\n"
                f"💰 تم استعادة مبلغ <b>${order['price']:.2f}</b> لرصيدك."
            ),
            parse_mode="HTML",
        )
    except TelegramError as e:
        logger.warning(f"[GAME] فشل إشعار المستخدم بالرفض: {e}")

    await query.edit_message_text(
        f"❌ <b>تم رفض الطلب #{order_id}</b>\n\n"
        f"تم استعادة المبلغ للمستخدم {order['user_tg_id']}.",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  إشعار قناة الطلبات
# ══════════════════════════════════════════════════════════

async def _notify_game_order_channel(bot, db, order: dict, user):
    channel_id = db.get_setting("orders_channel", "")
    if not channel_id:
        return
    try:
        await bot.send_message(
            chat_id=channel_id,
            text=(
                f"🎮 <b>طلب شحن لعبة!</b>\n\n"
                f"{order['app_emoji']} اللعبة: <b>{order['app_name']}</b>\n"
                f"🎁 الباقة: <b>{order['pkg_name']}</b>\n"
                f"💰 السعر: <b>${order['price']:.2f}</b>\n"
                f"👤 المستخدم: <code>{user.id}</code>"
            ),
            parse_mode="HTML",
        )
    except TelegramError as e:
        logger.warning(f"[GAME] فشل إرسال إشعار القناة: {e}")


# ══════════════════════════════════════════════════════════
#  مساعد
# ══════════════════════════════════════════════════════════

def _clear_game(context):
    for k in ("game_pkg_id", "game_app_id", "game_price",
              "game_state", "game_id", "game_order_id"):
        context.user_data.pop(k, None)
