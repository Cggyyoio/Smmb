from utils.safe_send import safe_answer, safe_edit, safe_send
"""
💳 شحن الرصيد — handlers/charge.py
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from database import Database
from crypto_pay import CryptoPayHandler, _session_clear
from ton_trx_pay import TonTrxPayHandler
from utils.keyboards import balance_kb, back_to_main_kb, cancel_kb, main_menu_kb
from config import ADMIN_ID

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
#  عرض الرصيد
# ══════════════════════════════════════════════════════════

async def my_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    user = update.effective_user

    balance = db.get_balance(user.id)
    cph: CryptoPayHandler = context.bot_data["cph"]
    bep20_on   = cph.is_bep20_enabled()
    trc20_on   = cph.is_trc20_enabled()
    vod_on     = bool(db.get_setting("vodafone_number", ""))
    stars_on   = db.get_setting("pay_stars",   "0") == "1"
    binance_on = db.get_setting("pay_binance", "0") == "1"
    ton_on     = context.bot_data["ttp"].is_ton_enabled()
    trx_on     = context.bot_data["ttp"].is_trx_enabled()

    referral_count = db.get_referral_count(user.id)
    u_data = db.get_user(user.id)
    earnings = u_data.get("referral_earnings", 0.0) if u_data else 0.0

    from config import BOT_USERNAME
    bot_name = BOT_USERNAME.lstrip("@")
    ref_link = f"https://t.me/{bot_name}?start=ref_{user.id}"

    text = (
        f"💳 <b>رصيدك الحالي</b>: <b>${balance:.2f}</b>\n\n"
        f"🤝 رابط الإحالة الخاص بك:\n<code>{ref_link}</code>\n"
        f"👥 عدد الإحالات: <b>{referral_count}</b>\n"
        f"💸 أرباح الإحالة: <b>${earnings:.2f}</b>\n\n"
        f"اختر طريقة الشحن:"
    )
    await safe_edit(query, 
        text,
        reply_markup=balance_kb(bep20_on, trc20_on, vod_on, stars_on, binance_on, ton_on, trx_on),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  شحن BEP20 / TRC20
# ══════════════════════════════════════════════════════════

async def charge_bep20_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    cph: CryptoPayHandler = context.bot_data["cph"]
    if not cph.is_bep20_enabled():
        await safe_answer(query, "⛔ BEP20 غير مفعّل حالياً.", show_alert=True)
        return
    await query.delete_message()
    await cph.show_pay_page(update.effective_chat.id, "bep20")


async def charge_trc20_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    cph: CryptoPayHandler = context.bot_data["cph"]
    if not cph.is_trc20_enabled():
        await safe_answer(query, "⛔ TRC20 غير مفعّل حالياً.", show_alert=True)
        return
    await query.delete_message()
    await cph.show_pay_page(update.effective_chat.id, "trc20")


async def charge_ton_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    ttp: TonTrxPayHandler = context.bot_data["ttp"]
    if not ttp.is_ton_enabled():
        await safe_answer(query, "⛔ TON غير مفعّل حالياً.", show_alert=True)
        return
    await query.delete_message()
    await ttp.show_pay_page(update.effective_chat.id, "ton")


async def charge_trx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    ttp: TonTrxPayHandler = context.bot_data["ttp"]
    if not ttp.is_trx_enabled():
        await safe_answer(query, "⛔ TRX غير مفعّل حالياً.", show_alert=True)
        return
    await query.delete_message()
    await ttp.show_pay_page(update.effective_chat.id, "trx")


async def tontrx_sent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    network = query.data.split("_")[2]   # tontrx_sent_ton أو tontrx_sent_trx
    ttp: TonTrxPayHandler = context.bot_data["ttp"]
    await query.delete_message()
    await ttp.prompt_txid(update.effective_chat.id, update.effective_user.id, network)


async def tontrx_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    network = query.data.split("_")[2]
    ttp: TonTrxPayHandler = context.bot_data["ttp"]
    await ttp.copy_address(update.effective_chat.id, network)


async def charge_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    # امسح أي state مفتوح (binance, stars, vod, ...)
    from utils.states import clear_all_states
    _session_clear(update.effective_user.id)
    clear_all_states(context)
    db: Database = context.bot_data["db"]
    cph: CryptoPayHandler = context.bot_data["cph"]
    user = update.effective_user
    balance = db.get_balance(user.id)
    vod_on     = bool(db.get_setting("vodafone_number", ""))
    stars_on   = db.get_setting("pay_stars",   "0") == "1"
    binance_on = db.get_setting("pay_binance", "0") == "1"
    ttp: TonTrxPayHandler = context.bot_data["ttp"]
    await safe_edit(query,
        f"💳 <b>رصيدك الحالي</b>: <b>${balance:.2f}</b>\n\nاختر طريقة الشحن:",
        reply_markup=balance_kb(cph.is_bep20_enabled(), cph.is_trc20_enabled(),
                                vod_on, stars_on, binance_on,
                                ttp.is_ton_enabled(), ttp.is_trx_enabled()),
        parse_mode="HTML",
    )


async def charge_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    _session_clear(update.effective_user.id)
    from utils.states import clear_all_states
    clear_all_states(context)
    # ارجع لصفحة الشحن مباشرة
    await charge_back_callback(update, context)


# ══════════════════════════════════════════════════════════
#  Crypto callbacks
# ══════════════════════════════════════════════════════════

async def crypto_sent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    network = query.data.split("_")[2]
    uid = update.effective_user.id
    cph: CryptoPayHandler = context.bot_data["cph"]
    await query.delete_message()
    await cph.prompt_txid(update.effective_chat.id, uid, network)


async def crypto_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    network = query.data.split("_")[2]
    cph: CryptoPayHandler = context.bot_data["cph"]
    await cph.handle_copy(update.effective_chat.id, network)


# ══════════════════════════════════════════════════════════
#  فودافون كاش
# ══════════════════════════════════════════════════════════

async def charge_vodafone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توجيه فودافون كاش: تلقائي أو يدوي حسب الإعداد."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]

    vod_number = db.get_setting("vodafone_number", "")
    if not vod_number:
        await safe_answer(query, "⚠️ فودافون كاش غير متاح حالياً.", show_alert=True)
        return

    # إذا كان التلقائي مفعلاً → نحوّل للـ VodafoneAutoHandler
    if db.get_setting("pay_vodafone_auto", "0") == "1":
        vah = context.bot_data.get("vah")
        if vah and vah.is_enabled():
            await query.delete_message()
            await vah.show_pay_page(update.effective_chat.id, update.effective_user.id)
            return

    # وضع يدوي (الطريقة القديمة)
    context.user_data["vod_state"] = "waiting_phone"
    await safe_edit(query, 
        f"📱 <b>شحن فودافون كاش</b>\n\n"
        f"📞 رقم التحويل: <code>{vod_number}</code>\n\n"
        f"حوّل المبلغ الذي تريده على الرقم أعلاه،\n"
        f"ثم أرسل <b>رقم هاتفك</b> المحوّل منه:",
        reply_markup=cancel_kb("my_balance"),
        parse_mode="HTML",
    )


async def vodafone_message_handler(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE) -> bool:
    """معالجة خطوات شحن فودافون: رقم الهاتف ثم لقطة الشاشة."""
    state = context.user_data.get("vod_state")
    if not state:
        return False

    db: Database = context.bot_data["db"]
    user = update.effective_user

    # ── الخطوة 1: انتظار رقم الهاتف (نص) ──
    if state == "waiting_phone":
        if not update.message.text:
            return False
        phone = update.message.text.strip()
        if len(phone) < 7 or not phone.replace("+", "").replace("-", "").isdigit():
            await update.message.reply_text(
                "❌ أرسل رقم هاتف صحيح.",
                reply_markup=cancel_kb("my_balance"),
            )
            return True
        context.user_data["vod_phone"] = phone
        context.user_data["vod_state"] = "waiting_screenshot"
        await update.message.reply_text(
            "✅ تم استلام الرقم.\n\n"
            "📸 الآن أرسل <b>لقطة شاشة</b> إيصال التحويل:",
            reply_markup=cancel_kb("my_balance"),
            parse_mode="HTML",
        )
        return True

    # ── الخطوة 2: انتظار الصورة ──
    if state == "waiting_screenshot":
        if not update.message.photo:
            if update.message.text:
                await update.message.reply_text(
                    "❌ أرسل صورة (لقطة شاشة) وليس نصاً.",
                    reply_markup=cancel_kb("my_balance"),
                )
            return True
        file_id = update.message.photo[-1].file_id
        phone   = context.user_data.pop("vod_phone", "")
        context.user_data.pop("vod_state", None)

        # حفظ الطلب بمبلغ 0 (الأدمن يحدده عند القبول)
        charge_id = db.create_vodafone_charge(user.id, 0.0, file_id, phone)

        # إرسال للأدمن
        from utils.keyboards import admin_approve_vodafone_kb
        username = f"@{user.username}" if user.username else f"#{user.id}"
        caption = (
            f"📱 <b>طلب شحن فودافون كاش!</b>\n\n"
            f"👤 المستخدم: <code>{user.id}</code> ({username})\n"
            f"📞 من رقم: <code>{phone}</code>\n"
            f"🆔 رقم الطلب: <code>{charge_id}</code>\n\n"
            f"💡 عند القبول ستُحدد المبلغ بناءً على سعر الصرف."
        )
        try:
            adm_msg = await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=file_id,
                caption=caption,
                reply_markup=admin_approve_vodafone_kb(charge_id),
                parse_mode="HTML",
            )
            db.set_vodafone_admin_msg(charge_id, adm_msg.message_id)
        except TelegramError as e:
            logger.warning(f"[VOD] فشل إرسال إشعار الأدمن: {e}")

        await update.message.reply_text(
            f"✅ <b>تم إرسال طلبك!</b>\n\n"
            f"📞 رقمك: <code>{phone}</code>\n"
            f"🆔 رقم الطلب: <code>{charge_id}</code>\n\n"
            f"⏳ في انتظار موافقة الأدمن...",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        return True

    return False


# ══════════════════════════════════════════════════════════
#  أكواد الهدايا
# ══════════════════════════════════════════════════════════

async def redeem_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    context.user_data["state"] = "waiting_gift_code"
    await safe_edit(query, 
        "🎁 <b>استبدال كود هدية</b>\n\nأرسل الكود:",
        reply_markup=cancel_kb("menu_main"),
        parse_mode="HTML",
    )


async def charge_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await redeem_gift_callback(update, context)


async def gift_code_message_handler(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("state") != "waiting_gift_code":
        return False
    context.user_data.pop("state", None)
    db: Database = context.bot_data["db"]
    code = (update.message.text or "").strip()
    result = db.redeem_gift_code(update.effective_user.id, code)
    if not result["success"]:
        await update.message.reply_text(result["error"], reply_markup=back_to_main_kb())
        return True

    # إحالة: أضف نسبة للمحيل
    _apply_referral_bonus(db, update.effective_user.id, result["amount"])

    balance = db.get_balance(update.effective_user.id)
    await update.message.reply_text(
        f"🎉 <b>تم استبدال الكود بنجاح!</b>\n\n"
        f"💰 تم إضافة: <code>${result['amount']:.2f}</code>\n"
        f"💳 رصيدك الآن: <code>${balance:.2f}</code>",
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )
    return True


# ══════════════════════════════════════════════════════════
#  مساعد الإحالة
# ══════════════════════════════════════════════════════════

def _apply_referral_bonus(db: Database, user_tg_id: int, amount: float):
    """يضيف نسبة إحالة للمحيل عند شحن رصيد المستخدم."""
    referrer = db.get_referrer(user_tg_id)
    if not referrer:
        return
    try:
        pct = float(db.get_setting("referral_pct", "0"))
        if pct <= 0:
            return
        bonus = round(amount * pct / 100, 4)
        if bonus > 0:
            db.add_referral_earning(referrer, bonus)
            logger.info(f"[REF] أضيف ${bonus} للمستخدم {referrer}")
    except Exception as e:
        logger.warning(f"[REF] خطأ في حساب الإحالة: {e}")
