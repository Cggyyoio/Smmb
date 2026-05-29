"""
🧾 إنشاء فاتورة ويب وإرسال الرابط — handlers/invoice_charge.py
"""

import logging
import random
import string
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from database import Database
from utils.safe_send import safe_answer, safe_edit
from utils.keyboards import cancel_kb, back_to_main_kb

logger = logging.getLogger(__name__)

WEB_BASE = "https://a1smm.store"


# ══════════════════════════════════════════════════════════════
#  توليد رقم الفاتورة
# ══════════════════════════════════════════════════════════════

def _gen_inv_id() -> str:
    """ينشئ معرّف فاتورة على شكل INV-XXXXXXXXXX (أحرف كبيرة + أرقام)."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=10))
    return f"INV-{suffix}"


# ══════════════════════════════════════════════════════════════
#  الخطوة 1: المستخدم يضغط "شحن رصيد"
#            → يطلب منه المبلغ بالدولار
# ══════════════════════════════════════════════════════════════

async def create_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يُستدعى عند الضغط على زر 'إنشاء فاتورة' / 'شحن رصيد'."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    user = update.effective_user

    balance = db.get_balance(user.id)

    context.user_data["inv_state"] = "waiting_amount"

    await safe_edit(
        query,
        f"💳 <b>إنشاء فاتورة دفع</b>\n\n"
        f"رصيدك الحالي: <b>${balance:.2f}</b>\n\n"
        f"📝 أرسل المبلغ الذي تريد شحنه <b>بالدولار</b>\n"
        f"مثال: <code>1.5</code>",
        reply_markup=cancel_kb("my_balance"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  الخطوة 2: استلام المبلغ، إنشاء الفاتورة، إرسال الرابط
# ══════════════════════════════════════════════════════════════

async def invoice_amount_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """يعالج المبلغ المُدخَل وينشئ الفاتورة."""
    if context.user_data.get("inv_state") != "waiting_amount":
        return False

    db: Database = context.bot_data["db"]
    user = update.effective_user

    raw = (update.message.text or "").strip().replace(",", ".")
    try:
        amount = float(raw)
        assert amount > 0
    except Exception:
        await update.message.reply_text(
            "❌ أدخل رقماً صحيحاً — مثال: <code>1.5</code>",
            reply_markup=cancel_kb("my_balance"),
            parse_mode="HTML",
        )
        return True

    # حدود
    min_usd = float(db.get_setting("inv_min_usd", "0.5"))
    max_usd = float(db.get_setting("inv_max_usd", "10000"))
    if amount < min_usd:
        await update.message.reply_text(
            f"❌ أقل مبلغ للشحن هو <b>${min_usd}</b>",
            reply_markup=cancel_kb("my_balance"),
            parse_mode="HTML",
        )
        return True
    if amount > max_usd:
        await update.message.reply_text(
            f"❌ أعلى مبلغ للشحن هو <b>${max_usd:,.0f}</b>",
            reply_markup=cancel_kb("my_balance"),
            parse_mode="HTML",
        )
        return True

    context.user_data.pop("inv_state", None)

    # إنشاء الفاتورة
    inv_id = _gen_inv_id()
    # تأكد من التفرد
    for _ in range(5):
        if not db.get_invoice(inv_id):
            break
        inv_id = _gen_inv_id()

    db.create_invoice(inv_id, user.id, amount)

    pay_url = f"{WEB_BASE}/pay/{inv_id}"

    # حساب المبالغ المرئية
    vod_rate    = _get_vod_rate(db)
    vod_egp     = round(amount * vod_rate)
    stars_rate  = _get_stars_rate(db)
    stars_count = int(amount * stars_rate)

    vod_on     = bool(db.get_setting("vodafone_number", "")) or \
                 db.get_setting("pay_vodafone_auto", "0") == "1"
    stars_on   = db.get_setting("pay_stars",   "0") == "1"
    binance_on = db.get_setting("pay_binance", "0") == "1"

    # بناء النص التوضيحي
    lines = [
        f"🧾 <b>تم إنشاء فاتورتك!</b>\n",
        f"📋 رقم الفاتورة: <code>{inv_id}</code>",
        f"💵 المبلغ: <b>${amount:.2f}</b>",
        f"⏰ تنتهي خلال: <b>ساعة واحدة</b>\n",
        f"<b>طرق الدفع المتاحة:</b>",
    ]
    if vod_on:
        lines.append(f"📱 فودافون كاش — <b>{vod_egp} ج.م</b>  (بسعر {int(vod_rate)} ج.م/$)")
    if stars_on:
        lines.append(f"⭐ Telegram Stars — <b>{stars_count} نجمة</b>")
    if binance_on:
        lines.append(f"💛 Binance Pay")
    lines.append(f"\n🔗 افتح صفحة الدفع:")

    text = "\n".join(lines)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 فتح صفحة الدفع", url=pay_url),
    ], [
        InlineKeyboardButton("🔙 رجوع", callback_data="my_balance"),
    ]])

    await update.message.reply_text(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )

    logger.info(f"[INV] created {inv_id} for uid={user.id} amount=${amount}")
    return True


# ══════════════════════════════════════════════════════════════
#  Telegram Stars: معالجة stars_pay_INV-xxx
#  يُستدعى من start_handler عند /start stars_pay_INV-xxx
# ══════════════════════════════════════════════════════════════

async def handle_stars_pay_invoice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    inv_id: str,
):
    """المستخدم ضغط على رابط النجوم — نرسل له فاتورة Stars."""
    from telegram import LabeledPrice
    from telegram.error import TelegramError

    db: Database = context.bot_data["db"]
    inv = db.get_invoice(inv_id)

    if not inv:
        await update.message.reply_text("❌ الفاتورة غير موجودة.", reply_markup=back_to_main_kb())
        return

    if inv["status"] == "paid":
        await update.message.reply_text("✅ هذه الفاتورة مدفوعة بالفعل.", reply_markup=back_to_main_kb())
        return

    # انتهت الصلاحية؟
    from invoice_web import _is_expired
    if _is_expired(inv):
        await update.message.reply_text("❌ انتهت صلاحية هذه الفاتورة.", reply_markup=back_to_main_kb())
        return

    amount_usd  = float(inv["amount_usd"])
    stars_rate  = _get_stars_rate(db)
    stars_count = int(amount_usd * stars_rate)

    try:
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=f"شحن ${amount_usd:.2f} رصيد SMM",
            description=(
                f"دفع {stars_count} نجمة مقابل إضافة ${amount_usd:.2f} "
                f"لرصيدك (الفاتورة {inv_id})"
            ),
            payload=f"webinv_{inv_id}_{update.effective_user.id}",
            currency="XTR",
            prices=[LabeledPrice(
                label=f"⭐ {stars_count} نجمة ← ${amount_usd:.2f}",
                amount=stars_count,
            )],
        )
    except TelegramError as e:
        logger.error(f"[STARS-INV] {e}")
        await update.message.reply_text("❌ حدث خطأ، حاول مرة أخرى.", reply_markup=back_to_main_kb())


async def successful_payment_web_invoice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    معالجة الدفع الناجح لفاتورة ويب بالنجوم.
    payload = webinv_<inv_id>_<uid>
    يُستدعى من message_router.
    """
    payment = update.message.successful_payment
    payload = payment.invoice_payload

    if not payload.startswith("webinv_"):
        return False

    db: Database = context.bot_data["db"]

    parts = payload.split("_", 2)
    try:
        inv_id     = parts[1]
        uid        = int(parts[2])
    except (IndexError, ValueError):
        logger.error(f"[STARS-INV] payload خاطئ: {payload}")
        return False

    stars_paid = payment.total_amount
    stars_rate = _get_stars_rate(db)
    usd_amount = round(stars_paid / stars_rate, 4)

    # تحديث الفاتورة وإضافة الرصيد
    ok = db.mark_invoice_paid(inv_id, "Telegram Stars")
    if ok:
        db.add_balance(uid, usd_amount)
        from handlers.charge import _apply_referral_bonus
        _apply_referral_bonus(db, uid, usd_amount)

    balance = db.get_balance(uid)

    await update.message.reply_text(
        f"✅ <b>تم شحن رصيدك!</b>\n\n"
        f"🧾 الفاتورة: <code>{inv_id}</code>\n"
        f"⭐ النجوم: <b>{stars_paid}</b>\n"
        f"💰 أضيف: <b>${usd_amount:.4f}</b>\n"
        f"💳 رصيدك الآن: <b>${balance:.4f}</b>",
        parse_mode="HTML",
        reply_markup=back_to_main_kb(),
    )

    # إشعار الأدمن
    try:
        from config import ADMIN_ID
        user = update.effective_user
        username = f"@{user.username}" if user.username else f"#{uid}"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"⭐ <b>شحن نجوم (فاتورة ويب) ✅</b>\n\n"
                f"👤 {username} (<code>{uid}</code>)\n"
                f"🧾 {inv_id}\n"
                f"⭐ {stars_paid} نجمة → <b>${usd_amount:.4f}</b>\n"
                f"💳 الرصيد: <b>${balance:.4f}</b>"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    logger.info(f"[STARS-INV] {inv_id} paid {stars_paid}★ = ${usd_amount}")
    return True


# ══════════════════════════════════════════════════════════════
#  مساعدات
# ══════════════════════════════════════════════════════════════

def _get_vod_rate(db: Database) -> float:
    try:
        return float(db.get_setting("vod_egp_rate", "50"))
    except Exception:
        return 50.0


def _get_stars_rate(db: Database) -> float:
    try:
        return float(db.get_setting("stars_per_dollar", "85"))
    except Exception:
        return 85.0
