"""
🚀 هاندلر /start — handlers/start.py
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from database import Database
from utils.subscription import check_subscription
from utils.keyboards import main_menu_kb, subscription_kb, back_to_main_kb

logger = logging.getLogger(__name__)


def _get_menu_kb(db: Database) -> object:
    """يجلب روابط القنوات من DB ويبني لوحة المفاتيح الرئيسية."""
    official_url = db.get_setting("official_channel", "")
    orders_url   = db.get_setting("orders_channel_link", "")
    website_url  = db.get_setting("website_url", "")
    return main_menu_kb(official_url=official_url, orders_url=orders_url, website_url=website_url)


def _welcome_text(user: dict, balance: float, spent: float) -> str:
    tg_id    = user["tg_id"]
    username = f"@{user['username']}" if user.get("username") else user.get("first_name", "زائر")
    return (
        f"مرحباً بك <b>{username}</b> 💙\n\n"
        f"🤖 : رقم حسابك: <code>BOT-{tg_id}F</code>\n"
        f"📚 : المستوى: <b>عادي 🌿</b>\n"
        f"🆔 : ايديك: <code>{tg_id}</code>\n"
        f"💰 : الرصيد المتوفر: <b>{balance:.2f}USD</b>\n"
        f"💸 : الصرفيات: <b>{spent:.2f}USD</b>\n"
        f"📚 : العملة: <b>دولار</b>\n\n"
        f"🧑 : يمكنك التحكم بالبوت عبر الأزرار في الاسفل. 👇"
    )


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    user    = update.effective_user
    u_data  = db.get_user(user.id)
    balance = db.get_balance(user.id)
    spent   = db.get_user_total_spent(user.id)
    text    = _welcome_text(u_data, balance, spent)
    kb      = _get_menu_kb(db)

    if update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db: Database = context.bot_data["db"]
    user = update.effective_user
    is_new = db.ensure_user(user.id, user.username, user.first_name)

    if db.is_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور من استخدام البوت.")
        return

    if is_new:
        from utils.notifications import notify_new_user
        u_data = db.get_user(user.id)
        await notify_new_user(context.bot, db, u_data)

    ok, missing = await check_subscription(context.bot, user.id, db)
    if not ok:
        await update.message.reply_text(
            "📢 <b>يجب عليك الاشتراك في القنوات التالية أولاً:</b>",
            reply_markup=subscription_kb(missing),
            parse_mode="HTML",
        )
        return

    args = context.args
    if args:
        arg = args[0]
        if arg.startswith("svc_"):
            try:
                await _show_service_deep(update, context, db, int(arg[4:]))
                return
            except (ValueError, IndexError):
                pass
        elif arg.startswith("ref_"):
            try:
                referrer_id = int(arg[4:])
                if referrer_id != user.id and is_new:
                    db.set_referral(user.id, referrer_id)
            except (ValueError, IndexError):
                pass

    await _show_main_menu(update, context, db)


async def _show_service_deep(update, context, db, service_id):
    from utils.keyboards import service_detail_kb
    svc = db.get_service(service_id)
    if not svc or not svc["is_active"]:
        await update.message.reply_text("❌ الخدمة غير متوفرة.", reply_markup=back_to_main_kb())
        return
    balance = db.get_balance(update.effective_user.id)
    lines = [
        f"🔹 <b>{svc['name']}</b>\n",
        f"💰 السعر لكل 1000: <b>${svc['price_per_1000']:.4f}</b>",
        f"📊 الحد الأدنى: <b>{svc['min_qty']}</b>",
        f"📊 الحد الأقصى: <b>{svc['max_qty']}</b>",
        f"💳 رصيدك الحالي: <b>${balance:.2f}</b>",
    ]
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=service_detail_kb(service_id),
        parse_mode="HTML",
    )


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db: Database = context.bot_data["db"]
    user = update.effective_user

    ok, missing = await check_subscription(context.bot, user.id, db)
    if not ok:
        await query.edit_message_text(
            "⚠️ <b>لم يكتمل الاشتراك بعد!</b>\nاشترك ثم أعد المحاولة.",
            reply_markup=subscription_kb(missing),
            parse_mode="HTML",
        )
        return
    await _show_main_menu(update, context, db)
