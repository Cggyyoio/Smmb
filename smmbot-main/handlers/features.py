from utils.safe_send import safe_answer, safe_edit, safe_send
"""
✨ الميزات الجديدة — handlers/features.py
تذاكر الدعم | نظام النقاط | إعادة الطلب | إحصائيات تفصيلية
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.error import TelegramError

from database import Database

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  🎫 تذاكر الدعم — المستخدم
# ══════════════════════════════════════════════════════════════

async def my_tickets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = update.effective_user.id
    tickets = db.get_user_tickets(uid)

    from utils.keyboards import my_tickets_kb
    if not tickets:
        await safe_edit(query, 
            "🎫 <b>تذاكر الدعم</b>\n\nليس لديك تذاكر بعد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ تذكرة جديدة", callback_data="ticket_new")],
                [InlineKeyboardButton("🔙 رجوع",        callback_data="menu_main")],
            ]),
            parse_mode="HTML",
        )
        return

    await safe_edit(query, 
        "🎫 <b>تذاكر الدعم</b>\n\nاختر تذكرة للتفاصيل:",
        reply_markup=my_tickets_kb(tickets),
        parse_mode="HTML",
    )


async def ticket_new_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    context.user_data["ticket_state"] = "waiting_message"
    await safe_edit(query, 
        "🎫 <b>تذكرة جديدة</b>\n\nاكتب مشكلتك بالتفصيل:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="my_tickets")
        ]]),
        parse_mode="HTML",
    )


async def ticket_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    tid = int(query.data.split("_")[2])
    t   = db.get_ticket(tid)
    if not t:
        await safe_answer(query, "❌ التذكرة غير موجودة!", show_alert=True)
        return

    st = "✅ مغلقة" if t["status"] == "closed" else "🔴 مفتوحة"
    text = (
        f"🎫 <b>تذكرة #{t['id']}</b> — {st}\n\n"
        f"📝 <b>الرسالة:</b>\n{t['message']}\n\n"
        f"📅 {t['created_at'][:16]}"
    )
    if t.get("admin_reply"):
        text += f"\n\n💬 <b>رد الأدمن:</b>\n{t['admin_reply']}"

    await safe_edit(query, 
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="my_tickets")
        ]]),
        parse_mode="HTML",
    )


async def ticket_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("ticket_state") != "waiting_message":
        return False
    context.user_data.pop("ticket_state", None)
    db: Database = context.bot_data["db"]
    uid = update.effective_user.id
    msg = (update.message.text or "").strip()
    if not msg:
        return True

    tid = db.create_ticket(uid, msg)

    # إشعار الأدمن
    from config import ADMIN_ID
    user = update.effective_user
    uname = f"@{user.username}" if user.username else f"#{uid}"
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🎫 <b>تذكرة دعم جديدة #{tid}</b>\n\n"
                f"👤 {uname} (<code>{uid}</code>)\n"
                f"📝 {msg[:300]}"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✉️ رد", callback_data=f"adm_ticket_{tid}"),
                InlineKeyboardButton("✅ إغلاق", callback_data=f"adm_ticket_close_{tid}"),
            ]]),
            parse_mode="HTML",
        )
    except TelegramError:
        pass

    await update.message.reply_text(
        f"✅ <b>تم إرسال تذكرتك #{tid}</b>\n\nسيرد عليك الأدمن قريباً.",
        parse_mode="HTML",
    )
    return True


# ══════════════════════════════════════════════════════════════
#  🎫 تذاكر الدعم — الأدمن
# ══════════════════════════════════════════════════════════════

async def adm_tickets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    tickets = db.get_open_tickets()
    from utils.keyboards import adm_tickets_kb
    if not tickets:
        await safe_edit(query, 
            "🎫 <b>تذاكر الدعم</b>\n\n✅ لا توجد تذاكر مفتوحة حالياً.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")
            ]]),
            parse_mode="HTML",
        )
        return
    await safe_edit(query, 
        f"🎫 <b>تذاكر الدعم المفتوحة ({len(tickets)})</b>",
        reply_markup=adm_tickets_kb(tickets),
        parse_mode="HTML",
    )


async def adm_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    tid = int(query.data.split("_")[2])
    t   = db.get_ticket(tid)
    if not t:
        await safe_answer(query, "❌ التذكرة غير موجودة!", show_alert=True)
        return

    text = (
        f"🎫 <b>تذكرة #{t['id']}</b>\n\n"
        f"👤 <code>{t['user_tg_id']}</code>\n"
        f"📝 {t['message']}\n"
        f"📅 {t['created_at'][:16]}"
    )
    if t.get("admin_reply"):
        text += f"\n\n💬 ردك: {t['admin_reply']}"

    context.user_data["adm_reply_ticket"] = tid
    await safe_edit(query, 
        text + "\n\n✉️ <b>اكتب ردك الآن أو اضغط إغلاق:</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ إغلاق التذكرة", callback_data=f"adm_ticket_close_{tid}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="adm_tickets")],
        ]),
        parse_mode="HTML",
    )


async def adm_ticket_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    tid = int(query.data.split("_")[3])
    db.close_ticket(tid)
    context.user_data.pop("adm_reply_ticket", None)
    await safe_edit(query, 
        f"✅ تم إغلاق التذكرة #{tid}.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="adm_tickets")
        ]]),
    )


async def adm_ticket_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    tid = context.user_data.get("adm_reply_ticket")
    if not tid:
        return False
    db: Database = context.bot_data["db"]
    reply = (update.message.text or "").strip()
    if not reply:
        return True

    t = db.get_ticket(tid)
    if not t:
        context.user_data.pop("adm_reply_ticket", None)
        return True

    db.reply_ticket(tid, reply)
    context.user_data.pop("adm_reply_ticket", None)

    # إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id=t["user_tg_id"],
            text=(
                f"💬 <b>رد على تذكرتك #{tid}</b>\n\n"
                f"{reply}"
            ),
            parse_mode="HTML",
        )
    except TelegramError:
        pass

    await update.message.reply_text(f"✅ تم إرسال الرد على التذكرة #{tid}.")
    return True


# ══════════════════════════════════════════════════════════════
#  🎯 نظام النقاط
# ══════════════════════════════════════════════════════════════

async def my_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = update.effective_user.id

    if not db.points_enabled():
        await safe_answer(query, "🎯 نظام النقاط غير مفعّل حالياً.", show_alert=True)
        return

    info       = db.get_points_info(uid)
    min_redeem = db.get_points_redeem_min()
    value      = db.get_points_redeem_value()
    pts        = info["points"]
    can_redeem = pts >= min_redeem

    bar_filled = int((pts / max(min_redeem, 1)) * 10)
    bar_filled = min(bar_filled, 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    text = (
        f"🎯 <b>نقاطك</b>\n\n"
        f"النقاط الحالية:  <b>{pts:,}</b>\n"
        f"المكتسبة كلياً:  <b>{info['total_earned']:,}</b>\n\n"
        f"{bar}  {pts}/{min_redeem}\n\n"
        f"💡 {min_redeem} نقطة = ${value:.2f}"
    )

    kb_rows = []
    if can_redeem:
        kb_rows.append([InlineKeyboardButton(
            f"🎁 استبدال {min_redeem} نقطة بـ ${value:.2f}",
            callback_data="points_redeem"
        )])
    kb_rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")])

    await safe_edit(query, text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML")


async def points_redeem_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = update.effective_user.id

    min_redeem = db.get_points_redeem_min()
    value      = db.get_points_redeem_value()

    success = db.redeem_points(uid, min_redeem)
    if not success:
        await safe_answer(query, "❌ نقاطك غير كافية للاسترداد!", show_alert=True)
        return

    db.add_balance(uid, value)
    db.reset_low_balance_notification(uid)
    balance = db.get_balance(uid)

    await safe_edit(query, 
        f"✅ <b>تم استبدال {min_redeem:,} نقطة بـ ${value:.2f}</b>\n\n"
        f"💳 رصيدك الآن: <b>${balance:.4f}</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="my_points")
        ]]),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  🔄 إعادة الطلب
# ══════════════════════════════════════════════════════════════

async def reorder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = update.effective_user.id

    order_id = int(query.data.split("_")[1])
    order    = db.get_order_for_reorder(order_id, uid)

    if not order:
        await safe_answer(query, "❌ الطلب غير موجود!", show_alert=True)
        return

    svc = db.get_service(order["service_id"])
    if not svc:
        await safe_answer(query, "❌ الخدمة لم تعد متاحة!", show_alert=True)
        return

    # تطبيق خصم VIP
    vip_discount = db.get_vip_discount(uid)
    base_price   = svc["price_per_1000"] / 1000
    if vip_discount > 0:
        base_price = base_price * (1 - vip_discount / 100)

    qty   = order["quantity"]
    price = round(base_price * qty, 4)
    bal   = db.get_balance(uid)

    # العملة الثانية
    cur2_name, cur2_rate = db.get_second_currency()
    price2_str = f" | {cur2_name} {price * cur2_rate:.1f}" if db.second_currency_enabled() and cur2_rate > 0 else ""

    context.user_data["order_svc_id"]  = order["service_id"]
    context.user_data["order_link"]    = order["link"]
    context.user_data["order_qty"]     = qty
    context.user_data["order_price"]   = price
    context.user_data["order_state"]   = "waiting_confirm"

    vip_line = f"⭐ خصم VIP: <b>{vip_discount:.0f}%</b>\n" if vip_discount > 0 else ""

    await safe_edit(query, 
        f"🔄 <b>إعادة الطلب</b>\n\n"
        f"🛠 الخدمة:  <b>{svc['name']}</b>\n"
        f"🔗 الرابط:  <code>{order['link']}</code>\n"
        f"🔢 الكمية:  <b>{qty:,}</b>\n"
        f"{vip_line}"
        f"💰 التكلفة: <b>${price:.4f}</b>{price2_str}\n"
        f"💳 رصيدك:  <b>${bal:.4f}</b>\n\n"
        "هل تريد تأكيد الطلب؟",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأكيد", callback_data="order_confirm"),
                InlineKeyboardButton("❌ إلغاء", callback_data="my_orders"),
            ]
        ]),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  📊 إحصائيات تفصيلية
# ══════════════════════════════════════════════════════════════

async def my_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = update.effective_user.id

    stats   = db.get_user_detailed_stats(uid)
    balance = db.get_balance(uid)
    vip     = db.get_vip(uid)
    pts     = db.get_points(uid) if db.points_enabled() else None

    vip_line = f"\n⭐ <b>مستخدم VIP</b> — خصم {vip['discount_pct']:.0f}%" if vip else ""
    pts_line = f"\n🎯 النقاط: <b>{pts:,}</b>" if pts is not None else ""

    # العملة الثانية
    cur2_name, cur2_rate = db.get_second_currency()
    bal2_str = f" | {cur2_name} {balance * cur2_rate:.1f}" if db.second_currency_enabled() and cur2_rate > 0 else ""

    text = (
        f"📊 <b>إحصائياتك التفصيلية</b>{vip_line}{pts_line}\n\n"
        f"💳 الرصيد:        <b>${balance:.4f}</b>{bal2_str}\n"
        f"💸 إجمالي الصرف:  <b>${stats['spent']:.4f}</b>\n"
        f"📦 إجمالي الطلبات: <b>{stats['total']}</b>\n"
        f"  ✅ مكتملة: <b>{stats['done']}</b>\n"
        f"  ❌ ملغية:  <b>{stats['cancel']}</b>\n"
        f"  ⚠️ جزئية:  <b>{stats['partial']}</b>\n"
    )
    if stats["top_svc"] != "—":
        text += f"\n🏆 أكثر خدمة طلبتها:\n   {stats['top_svc']} ({stats['top_cnt']} مرة)\n"

    text += f"\n📅 عضو منذ: <b>{stats['joined']}</b>"

    await safe_edit(query, 
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")
        ]]),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  ⚙️ إعدادات الميزات — الأدمن
# ══════════════════════════════════════════════════════════════

async def adm_features_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    settings = {
        "points_enabled":           db.get_setting("points_enabled", "0"),
        "low_balance_alert":        db.get_setting("low_balance_alert", "0"),
        "second_currency_enabled":  db.get_setting("second_currency_enabled", "0"),
        "daily_report_enabled":     db.get_setting("daily_report_enabled", "0"),
    }
    from utils.keyboards import adm_features_kb
    await safe_edit(query, 
        "⚙️ <b>إعدادات الميزات</b>",
        reply_markup=adm_features_kb(settings),
        parse_mode="HTML",
    )


async def adm_feat_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]

    feat_map = {
        "adm_feat_toggle_points":       "points_enabled",
        "adm_feat_toggle_low_balance":  "low_balance_alert",
        "adm_feat_toggle_currency2":    "second_currency_enabled",
        "adm_feat_toggle_daily_report": "daily_report_enabled",
    }
    key = feat_map.get(query.data)
    if key:
        current = db.get_setting(key, "0")
        db.set_setting(key, "0" if current == "1" else "1")

    await adm_features_callback(update, context)


async def adm_feat_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)

    prompts = {
        "adm_feat_set_low_bal":    ("waiting_feat_low_bal",    "💲 أرسل حد الرصيد المنخفض بالدولار (مثال: 1.5):"),
        "adm_feat_set_pts_rate":   ("waiting_feat_pts_rate",   "🎯 أرسل عدد النقاط لكل $1 ينفقه المستخدم (مثال: 10):"),
        "adm_feat_set_pts_redeem": ("waiting_feat_pts_redeem", "🏆 أرسل الحد الأدنى للاسترداد (عدد النقاط، مثال: 100):"),
        "adm_feat_set_pts_value":  ("waiting_feat_pts_value",  "💰 أرسل قيمة الاسترداد بالدولار (مثال: 0.5):"),
        "adm_feat_set_cur2_name":  ("waiting_feat_cur2_name",  "🌐 أرسل اسم العملة الثانية (مثال: EGP):"),
        "adm_feat_set_cur2_rate":  ("waiting_feat_cur2_rate",  "💱 أرسل سعر الصرف (كم وحدة من العملة الثانية لكل $1):"),
        "adm_feat_set_report_time":("waiting_feat_report_time","⏰ أرسل ساعة إرسال التقرير اليومي (0-23):"),
    }
    state_key, prompt = prompts.get(query.data, (None, None))
    if not state_key:
        return

    context.user_data["adm_state"] = state_key
    from utils.keyboards import cancel_kb
    await safe_edit(query, 
        prompt,
        reply_markup=cancel_kb("adm_features"),
    )


async def adm_feat_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    state = context.user_data.get("adm_state", "")
    if not state.startswith("waiting_feat_"):
        return False

    db: Database = context.bot_data["db"]
    text = (update.message.text or "").strip()
    context.user_data.pop("adm_state", None)

    settings_map = {
        "waiting_feat_low_bal":    ("low_balance_threshold",  float, "💲 تم تحديث حد الرصيد المنخفض: ${}"),
        "waiting_feat_pts_rate":   ("points_per_dollar",       int,   "🎯 تم تحديث معدل النقاط: {} نقطة/$1"),
        "waiting_feat_pts_redeem": ("points_redeem_min",       int,   "🏆 تم تحديث حد الاسترداد: {} نقطة"),
        "waiting_feat_pts_value":  ("points_redeem_value",     float, "💰 تم تحديث قيمة الاسترداد: ${}"),
        "waiting_feat_cur2_name":  ("second_currency_name",    str,   "🌐 تم تحديث اسم العملة: {}"),
        "waiting_feat_cur2_rate":  ("second_currency_rate",    float, "💱 تم تحديث سعر الصرف: {}"),
        "waiting_feat_report_time":("daily_report_hour",       int,   "⏰ تم تحديث وقت التقرير: الساعة {}"),
    }

    if state not in settings_map:
        return False

    setting_key, cast, msg_template = settings_map[state]
    try:
        val = cast(text)
        if setting_key == "daily_report_hour":
            assert 0 <= int(val) <= 23
    except Exception:
        await update.message.reply_text("❌ قيمة غير صحيحة، حاول مرة أخرى.")
        return True

    db.set_setting(setting_key, str(val))
    await update.message.reply_text(
        f"✅ {msg_template.format(val)}",
        parse_mode="HTML",
    )
    return True


# ══════════════════════════════════════════════════════════════
#  👑 VIP — الأدمن
# ══════════════════════════════════════════════════════════════

async def adm_vip_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    uid = int(query.data.split("_")[3])
    context.user_data["adm_state"]  = "waiting_vip_pct"
    context.user_data["adm_target"] = uid
    from utils.keyboards import cancel_kb
    await safe_edit(query, 
        f"👑 أرسل نسبة الخصم للمستخدم <code>{uid}</code> (مثال: 20 = 20%)",
        reply_markup=cancel_kb(f"adm_users"),
        parse_mode="HTML",
    )


async def adm_vip_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = int(query.data.split("_")[3])
    db.remove_vip(uid)
    await safe_answer(query, f"✅ تم إلغاء VIP للمستخدم {uid}", show_alert=True)
    try:
        await context.bot.send_message(
            chat_id=uid,
            text="ℹ️ تم إلغاء وضع VIP الخاص بك.",
        )
    except Exception:
        pass


async def adm_vip_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("adm_state") != "waiting_vip_pct":
        return False
    db: Database = context.bot_data["db"]
    uid = context.user_data.pop("adm_target", None)
    context.user_data.pop("adm_state", None)
    text = (update.message.text or "").strip()
    try:
        pct = float(text)
        assert 0 < pct <= 100
    except Exception:
        await update.message.reply_text("❌ أرسل رقماً بين 1 و100.")
        return True
    db.set_vip(uid, pct)
    await update.message.reply_text(
        f"✅ تم تعيين خصم VIP <b>{pct:.0f}%</b> للمستخدم <code>{uid}</code>.",
        parse_mode="HTML",
    )
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=f"🎉 تهانينا! أصبحت مستخدم <b>VIP</b> بخصم <b>{pct:.0f}%</b> على جميع الطلبات!",
            parse_mode="HTML",
        )
    except Exception:
        pass
    return True


# ══════════════════════════════════════════════════════════════
#  🚫 حظر خدمات لمستخدم — الأدمن
# ══════════════════════════════════════════════════════════════

async def adm_block_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = int(query.data.split("_")[3])
    blocked = db.get_blocked_services(uid)
    blocked_ids = {b["service_id"] for b in blocked}

    context.user_data["adm_state"]  = "waiting_block_svc"
    context.user_data["adm_target"] = uid
    from utils.keyboards import cancel_kb
    blocked_text = ""
    if blocked:
        names = ", ".join(b.get("service_name", str(b["service_id"])) for b in blocked[:5])
        blocked_text = f"\n\n🚫 المحظورة حالياً: {names}"
    await safe_edit(query, 
        f"🚫 أرسل <b>ID الخدمة</b> لحظرها أو رفع الحظر عنها للمستخدم <code>{uid}</code>\n"
        f"(اكتب رقم الخدمة من الـ API){blocked_text}",
        reply_markup=cancel_kb("adm_users"),
        parse_mode="HTML",
    )


async def adm_block_svc_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("adm_state") != "waiting_block_svc":
        return False
    db: Database = context.bot_data["db"]
    uid = context.user_data.pop("adm_target", None)
    context.user_data.pop("adm_state", None)
    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("❌ أرسل رقم الخدمة صحيح.")
        return True
    svc = db.get_service_by_api_id(int(text))
    if not svc:
        svc = db.get_service(int(text))
    if not svc:
        await update.message.reply_text("❌ الخدمة غير موجودة.")
        return True
    sid = svc["id"]
    if db.is_service_blocked(uid, sid):
        db.unblock_service(uid, sid)
        await update.message.reply_text(
            f"✅ تم رفع الحظر عن خدمة <b>{svc['name']}</b> للمستخدم <code>{uid}</code>.",
            parse_mode="HTML",
        )
    else:
        db.block_service(uid, sid)
        await update.message.reply_text(
            f"🚫 تم حظر خدمة <b>{svc['name']}</b> للمستخدم <code>{uid}</code>.",
            parse_mode="HTML",
        )
    return True


# ══════════════════════════════════════════════════════════════
#  📦 طلبات SMM معلقة +24h — الأدمن
# ══════════════════════════════════════════════════════════════

async def adm_pending_smm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    orders = db.get_pending_orders_over(hours=24)

    if not orders:
        await safe_edit(query, 
            "📦 <b>طلبات SMM معلقة +24 ساعة</b>\n\n✅ لا توجد طلبات معلقة.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")
            ]]),
            parse_mode="HTML",
        )
        return

    lines = [f"📦 <b>طلبات معلقة أكثر من 24 ساعة ({len(orders)})</b>\n"]
    for o in orders[:15]:
        uname = f"@{o['username']}" if o.get("username") else f"#{o['user_tg_id']}"
        svc   = o.get("service_name", "—")[:25]
        lines.append(
            f"<blockquote>🔹 <b>#{o['id']}</b> — {svc}\n"
            f"👤 {uname} | 💰 ${o['price']:.2f}\n"
            f"📅 {o['created_at'][:16]}</blockquote>"
        )

    await safe_edit(query, 
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")
        ]]),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  📅 التقرير اليومي — الأدمن
# ══════════════════════════════════════════════════════════════

async def adm_daily_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    await _send_daily_report(context.bot, db)


async def _send_daily_report(bot, db: Database):
    from config import ADMIN_ID
    stats   = db.get_daily_stats()
    all_st  = db.get_stats()
    margin  = stats["revenue"] - stats.get("refunds", 0)

    # العملة الثانية
    cur2_name, cur2_rate = db.get_second_currency()
    rev2_str = f" | {cur2_name} {stats['revenue'] * cur2_rate:.1f}" if db.second_currency_enabled() and cur2_rate > 0 else ""

    text = (
        f"📅 <b>التقرير اليومي</b>\n\n"
        f"💰 المبيعات:    <b>${stats['revenue']:.4f}</b>{rev2_str}\n"
        f"📦 الطلبات:     <b>{stats['orders']}</b>\n"
        f"👥 مستخدمون جدد: <b>{stats['new_users']}</b>\n"
        f"💸 استردادات:   <b>${stats['refunds']:.4f}</b>\n"
        f"📊 صافي الإيراد: <b>${margin:.4f}</b>\n\n"
        f"📈 إجمالي المستخدمين: <b>{all_st['users']:,}</b>\n"
        f"📦 إجمالي الطلبات:    <b>{all_st['orders']:,}</b>"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="HTML")
        checker_ch = db.get_setting("checker_channel", "").strip()
        if checker_ch and checker_ch != str(ADMIN_ID):
            await bot.send_message(chat_id=checker_ch, text=text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"[DAILY REPORT] فشل: {e}")


def register_daily_report(app, db, hour: int = 0):
    """يسجل job التقرير اليومي في الساعة المحددة."""
    import datetime
    from telegram.ext import JobQueue
    async def _job(ctx):
        if not db.daily_report_enabled():
            return
        await _send_daily_report(ctx.bot, db)

    app.job_queue.run_daily(
        _job,
        time=datetime.time(hour=hour, minute=0),
        name="daily_report",
    )


# ══════════════════════════════════════════════════════════════
#  🔔 تنبيه الرصيد المنخفض
# ══════════════════════════════════════════════════════════════

async def check_low_balance(bot, db: Database, uid: int):
    """يُستدعى بعد كل إنفاق."""
    try:
        if not db.low_balance_alert_enabled():
            return
        threshold = db.get_low_balance_threshold()
        balance   = db.get_balance(uid)
        if balance > threshold:
            return
        if not db.should_notify_low_balance(uid):
            return
        db.mark_low_balance_notified(uid)
        from handlers.start import _get_menu_kb
        await bot.send_message(
            chat_id=uid,
            text=(
                f"⚠️ <b>تنبيه: رصيدك منخفض!</b>\n\n"
                f"💳 رصيدك الحالي: <b>${balance:.4f}</b>\n"
                f"الحد المحدد: ${threshold:.2f}\n\n"
                f"اشحن رصيدك الآن للاستمرار في الطلبات."
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💰 اشحن الآن", callback_data="my_balance")
            ]]),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.debug(f"[LOW_BAL] {e}")


# ══════════════════════════════════════════════════════════════
#  تسجيل الهاندلرز
# ══════════════════════════════════════════════════════════════

def register_features(app):
    # تذاكر المستخدم
    app.add_handler(CallbackQueryHandler(my_tickets_callback,        pattern=r"^my_tickets$"))
    app.add_handler(CallbackQueryHandler(ticket_new_callback,        pattern=r"^ticket_new$"))
    app.add_handler(CallbackQueryHandler(ticket_view_callback,       pattern=r"^ticket_view_\d+$"))

    # نقاط
    app.add_handler(CallbackQueryHandler(my_points_callback,         pattern=r"^my_points$"))
    app.add_handler(CallbackQueryHandler(points_redeem_callback,     pattern=r"^points_redeem$"))

    # إعادة طلب
    app.add_handler(CallbackQueryHandler(reorder_callback,           pattern=r"^reorder_\d+$"))

    # إحصائيات
    app.add_handler(CallbackQueryHandler(my_stats_callback,          pattern=r"^my_stats$"))

    # أدمن — تذاكر
    app.add_handler(CallbackQueryHandler(adm_tickets_callback,       pattern=r"^adm_tickets$"))
    app.add_handler(CallbackQueryHandler(adm_ticket_callback,        pattern=r"^adm_ticket_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_ticket_close_callback,  pattern=r"^adm_ticket_close_\d+$"))

    # أدمن — VIP
    app.add_handler(CallbackQueryHandler(adm_vip_set_callback,       pattern=r"^adm_vip_set_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_vip_remove_callback,    pattern=r"^adm_vip_remove_\d+$"))

    # أدمن — حظر خدمات
    app.add_handler(CallbackQueryHandler(adm_block_svc_callback,     pattern=r"^adm_block_svc_\d+$"))

    # أدمن — طلبات معلقة
    app.add_handler(CallbackQueryHandler(adm_pending_smm_callback,   pattern=r"^adm_pending_smm$"))

    # أدمن — تقرير يومي
    app.add_handler(CallbackQueryHandler(adm_daily_report_callback,  pattern=r"^adm_daily_report$"))

    # أدمن — إعدادات ميزات
    app.add_handler(CallbackQueryHandler(adm_features_callback,      pattern=r"^adm_features$"))
    app.add_handler(CallbackQueryHandler(adm_feat_toggle_callback,   pattern=r"^adm_feat_toggle_\w+$"))
    app.add_handler(CallbackQueryHandler(adm_feat_set_callback,      pattern=r"^adm_feat_set_\w+$"))
