from utils.safe_send import safe_answer, safe_edit, safe_send
"""
⭐ نجوم تيليغرام + 💛 Binance Pay — handlers/stars_binance_pay.py

طريقتان للدفع التلقائي:
  1. Telegram Stars  → المستخدم يدخل المبلغ بالدولار، البوت يحسب النجوم تلقائياً
  2. Binance Pay     → المستخدم يحوّل على Binance ID ويبعت Order ID للبوت
"""

import logging
import aiohttp
import json
import hmac
import hashlib
import time

from telegram import Update, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from database import Database
from utils.keyboards import back_to_main_kb, cancel_kb
from config import ADMIN_ID
from handlers.admin.panel import is_super_admin

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  مساعدات إعدادات
# ══════════════════════════════════════════════════════════════

def _stars_rate(db: Database) -> float:
    """عدد النجوم مقابل $1 — الافتراضي 85"""
    try:
        return float(db.get_setting("stars_per_dollar", "85"))
    except Exception:
        return 85.0

def _stars_min_usd(db: Database) -> float:
    """الحد الأدنى للشحن بالنجوم بالدولار — الافتراضي 1"""
    try:
        return float(db.get_setting("stars_min_usd", "1"))
    except Exception:
        return 1.0

def _stars_enabled(db: Database) -> bool:
    return db.get_setting("pay_stars", "0") == "1"

def _binance_enabled(db: Database) -> bool:
    return db.get_setting("pay_binance", "0") == "1"

def _binance_pay_id(db: Database) -> str:
    return db.get_setting("binance_pay_id", "")

def _binance_api_key(db: Database) -> str:
    return db.get_setting("binance_api_key", "")

def _binance_api_secret(db: Database) -> str:
    return db.get_setting("binance_api_secret", "")


# ══════════════════════════════════════════════════════════════
#  ⭐ Telegram Stars — الخطوة 1: اختيار المبلغ
# ══════════════════════════════════════════════════════════════

async def charge_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المستخدم يضغط زر 'شحن بنجوم تيليغرام'."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]

    if not _stars_enabled(db):
        await safe_answer(query, "⭐ نجوم تيليغرام غير مفعّلة حالياً.", show_alert=True)
        return

    rate    = _stars_rate(db)
    min_usd = _stars_min_usd(db)
    min_stars = int(min_usd * rate)

    context.user_data["stars_state"] = "waiting_amount"

    await safe_edit(query, 
        f"⭐ <b>شحن بـ Telegram Stars</b>\n\n"
        f"💱 السعر: <b>{int(rate)} نجمة = $1</b>\n"
        f"💰 أقل مبلغ: <b>${min_usd:.2f}</b>\n\n"
        f"📝 أرسل المبلغ بالدولار\n"
        f"مثال: <code>5</code>",
        reply_markup=cancel_kb("charge_cancel"),
        parse_mode="HTML",
    )


async def stars_amount_message_handler(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE) -> bool:
    """المستخدم أدخل المبلغ — نحسب النجوم ونرسل الفاتورة."""
    if context.user_data.get("stars_state") != "waiting_amount":
        return False

    db: Database = context.bot_data["db"]

    try:
        usd = float((update.message.text or "").strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            "❌ أرسل رقماً صحيحاً، مثال: <code>5</code>",
            reply_markup=cancel_kb("charge_cancel"),
            parse_mode="HTML",
        )
        return True

    min_usd = _stars_min_usd(db)
    if usd < min_usd:
        await update.message.reply_text(
            f"❌ أقل مبلغ هو <b>${min_usd:.2f}</b>",
            reply_markup=cancel_kb("charge_cancel"),
            parse_mode="HTML",
        )
        return True

    if usd > 10000:
        await update.message.reply_text(
            "❌ الحد الأقصى $10,000",
            reply_markup=cancel_kb("charge_cancel"),
        )
        return True

    rate       = _stars_rate(db)
    stars_need = int(usd * rate)
    uid        = update.effective_user.id

    context.user_data.pop("stars_state", None)

    # ─── إرسال فاتورة Stars ───
    try:
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=f"شحن ${usd:.2f} رصيد SMM Bot",
            description=f"دفع {stars_need} نجمة مقابل إضافة ${usd:.2f} لرصيدك داخل البوت.",
            payload=f"stars_{uid}_{usd}",
            currency="XTR",           # Telegram Stars
            prices=[LabeledPrice(
                label=f"⭐ {stars_need} نجمة  ←  ${usd:.2f}",
                amount=stars_need,
            )],
        )
    except TelegramError as e:
        logger.error(f"[STARS] فشل إنشاء الفاتورة: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ، حاول مرة أخرى.",
            reply_markup=back_to_main_kb(),
        )
    return True


# ══════════════════════════════════════════════════════════════
#  ⭐ Telegram Stars — معالجة الدفع
# ══════════════════════════════════════════════════════════════

async def pre_checkout_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يجب الرد خلال 10 ثوانٍ وإلا يُلغى الدفع."""
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("stars_"):
        await safe_answer(query, ok=True)
    else:
        await safe_answer(query, ok=False, error_message="دفع غير معروف.")


async def successful_payment_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تم الدفع بنجاح — يُضاف الرصيد فوراً."""
    payment = update.message.successful_payment
    payload = payment.invoice_payload

    if not payload.startswith("stars_"):
        return

    db: Database = context.bot_data["db"]

    # payload = stars_<uid>_<usd>
    parts = payload.split("_", 2)
    try:
        uid       = int(parts[1])
        usd_asked = float(parts[2])
    except (IndexError, ValueError):
        logger.error(f"[STARS] payload خاطئ: {payload}")
        return

    stars_paid = payment.total_amount      # النجوم الفعلية المدفوعة
    rate       = _stars_rate(db)
    credit     = round(stars_paid / rate, 4)

    db.add_balance(uid, credit)
    balance = db.get_balance(uid)

    await update.message.reply_text(
        f"✅ <b>تم شحن رصيدك!</b>\n\n"
        f"⭐ النجوم: <b>{stars_paid}</b>\n"
        f"💰 أضيف: <b>${credit:.4f}</b>\n"
        f"💳 رصيدك: <b>${balance:.4f}</b>",
        parse_mode="HTML",
        reply_markup=back_to_main_kb(),
    )

    # إشعار الأدمن + قناة التقارير
    try:
        user = update.effective_user
        username = f"@{user.username}" if user.username else f"#{uid}"
        notif_text = (
            f"⭐ <b>شحن نجوم ناجح</b>\n\n"
            f"👤 {username} (<code>{uid}</code>)\n"
            f"⭐ نجوم: <b>{stars_paid}</b>\n"
            f"💰 أضيف: <b>${credit:.4f}</b>\n"
            f"💳 الرصيد: <b>${balance:.4f}</b>"
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=notif_text,
            parse_mode="HTML",
        )
        checker_ch = db.get_setting("checker_channel", "").strip()
        if checker_ch and checker_ch != str(ADMIN_ID):
            await context.bot.send_message(
                chat_id=checker_ch,
                text=notif_text,
                parse_mode="HTML",
            )
    except TelegramError:
        pass

    logger.info(f"[STARS] uid={uid} stars={stars_paid} credit=${credit}")


# ══════════════════════════════════════════════════════════════
#  💛 Binance Pay — الخطوة 1: عرض Binance ID وطلب Order ID
# ══════════════════════════════════════════════════════════════

async def charge_binance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]

    if not _binance_enabled(db):
        await safe_answer(query, "💛 Binance Pay غير مفعّل حالياً.", show_alert=True)
        return

    pay_id = _binance_pay_id(db)
    if not pay_id:
        await safe_answer(query, "⚠️ لم يُحدَّد Binance ID بعد. تواصل مع الأدمن.", show_alert=True)
        return

    context.user_data["binance_state"] = "waiting_order_id"

    await safe_edit(query, 
        f"💛 <b>شحن عبر Binance Pay</b>\n\n"
        f"🔹 حول على هذا <b>Binance ID</b>:\n"
        f"<code>{pay_id}</code>\n\n"
        f"🔹 بعد التحويل، أرسل <b>رقم الطلب (Order ID)</b>\n"
        f"مثال: <code>429587669106335744</code>",
        reply_markup=cancel_kb("charge_cancel"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  💛 Binance Pay — الخطوة 2: استلام Order ID والتحقق
# ══════════════════════════════════════════════════════════════

async def binance_message_handler(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("binance_state") != "waiting_order_id":
        return False

    db: Database = context.bot_data["db"]
    order_id = (update.message.text or "").strip()

    # Order No. في Binance يكون رقمي عادةً 15-20 خانة
    if not order_id or not order_id.isdigit() or len(order_id) < 10:
        await update.message.reply_text(
            "❌ Order ID غير صحيح.\n"
            "أرسل الرقم كما يظهر في تطبيق Binance.",
            reply_markup=cancel_kb("charge_cancel"),
            parse_mode="HTML",
        )
        return True

    context.user_data.pop("binance_state", None)

    # فحص التكرار — فقط لو العملية نجحت سابقاً
    used = db.get_setting(f"bnb_used_{order_id}", "")
    if used == "1":
        await update.message.reply_text(
            "❌ هذا Order ID تم استخدامه من قبل وتمت العملية بنجاح.",
            reply_markup=back_to_main_kb(),
        )
        return True

    api_key    = _binance_api_key(db)
    api_secret = _binance_api_secret(db)

    if api_key and api_secret:
        # ── التحقق التلقائي ──
        await update.message.reply_text("⏳ جاري التحقق...")
        amount = await _verify_binance_order(api_key, api_secret, order_id)

        if amount is None:
            # فشل التحقق — لا نحفظ الـ order_id ولا نبلغ الأدمن
            await update.message.reply_text(
                "❌ <b>لم يتم العثور على التحويل</b>\n\n"
                "تأكد من:\n"
                "• أن Order ID صحيح\n"
                "• أن التحويل اكتمل بنجاح في تطبيق Binance\n\n"
                "يمكنك المحاولة مرة أخرى بـ Order ID صحيح.",
                reply_markup=back_to_main_kb(),
                parse_mode="HTML",
            )
            return True

        if amount <= 0:
            await update.message.reply_text("❌ المبلغ غير صالح.", reply_markup=back_to_main_kb())
            return True

        uid = update.effective_user.id
        db.set_setting(f"bnb_used_{order_id}", "1")
        db.add_balance(uid, amount)
        balance = db.get_balance(uid)

        user     = update.effective_user
        username = f"@{user.username}" if user.username else f"#{uid}"

        await update.message.reply_text(
            f"✅ <b>تم الشحن!</b>\n\n"
            f"🆔 Order ID: <code>{order_id}</code>\n"
            f"💰 أضيف: <b>${amount:.4f}</b>\n"
            f"💳 رصيدك: <b>${balance:.4f}</b>",
            parse_mode="HTML",
            reply_markup=back_to_main_kb(),
        )

        notif_text = (
            f"💛 <b>شحن Binance ID تلقائي ✅</b>\n\n"
            f"👤 {username} (<code>{uid}</code>)\n"
            f"🆔 Order ID: <code>{order_id}</code>\n"
            f"💰 أضيف: <b>${amount:.4f}</b>\n"
            f"💳 الرصيد: <b>${balance:.4f}</b>"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID, text=notif_text, parse_mode="HTML",
            )
            checker_ch = db.get_setting("checker_channel", "").strip()
            if checker_ch and checker_ch != str(ADMIN_ID):
                await context.bot.send_message(
                    chat_id=checker_ch, text=notif_text, parse_mode="HTML",
                )
        except TelegramError:
            pass

    else:
        # ── وضع يدوي (بدون API) ──
        uid      = update.effective_user.id
        user     = update.effective_user
        username = f"@{user.username}" if user.username else f"#{uid}"

        db.set_setting(f"bnb_used_{order_id}", "pending")

        from utils.keyboards import admin_approve_binance_kb
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"💛 <b>طلب شحن Binance Pay (يدوي)</b>\n\n"
                    f"👤 {username} (<code>{uid}</code>)\n"
                    f"🆔 Order ID: <code>{order_id}</code>"
                ),
                parse_mode="HTML",
                reply_markup=admin_approve_binance_kb(order_id, uid),
            )
        except TelegramError as e:
            logger.warning(f"[BINANCE] فشل إشعار الأدمن: {e}")

        await update.message.reply_text(
            f"✅ <b>تم إرسال طلبك للمراجعة.</b>\n\n"
            f"🆔 Order ID: <code>{order_id}</code>\n"
            f"⏳ سيتم إضافة رصيدك بعد المراجعة.",
            parse_mode="HTML",
            reply_markup=back_to_main_kb(),
        )

    logger.info(f"[BINANCE] uid={update.effective_user.id} order_id={order_id}")
    return True


# ══════════════════════════════════════════════════════════════
#  Binance API — التحقق التلقائي
# ══════════════════════════════════════════════════════════════

async def _verify_binance_order(api_key: str, api_secret: str, order_id: str):
    """
    يتحقق من Order ID عبر Binance API.
    """
    try:
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - (30 * 24 * 60 * 60 * 1000)   # آخر 7 أيام

        query = (
            f"timestamp={now_ms}"
            f"&startTime={start_ms}"
            f"&endTime={now_ms}"
            f"&limit=100"
        )

        signature = hmac.new(
            api_secret.encode(),
            query.encode(),
            hashlib.sha256
        ).hexdigest()

        url = (
            "https://api.binance.com/sapi/v1/pay/transactions"
            f"?{query}&signature={signature}"
        )

        headers = {
            "X-MBX-APIKEY": api_key
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                data = await response.json(content_type=None)

        logger.warning(f"[BINANCE API RESPONSE] {data}")

        if not data.get("success"):
            logger.error(f"[BINANCE] API FAILED: {data}")
            return None

        txs = data.get("data", [])

        clean_order = ''.join(filter(str.isdigit, order_id))

        for tx in txs:
            api_order_id = str(tx.get("orderId", "")).strip()
            digits = ''.join(filter(str.isdigit, api_order_id))

            matched = (
                api_order_id == order_id
                or digits == clean_order
                or clean_order in digits
            )

            if not matched:
                continue

            logger.warning(f"[BINANCE MATCH FOUND] {tx}")

            amount = float(tx.get("amount", 0))

            # تجاهل التحويلات الخارجة
            if amount <= 0:
                logger.warning("[BINANCE] OUTGOING PAYMENT IGNORED")
                continue

            logger.warning(f"[BINANCE SUCCESS] order={api_order_id} amount={amount}")
            return amount

        logger.warning(f"[BINANCE] ORDER NOT FOUND: {order_id}")
        return None

    except Exception as e:
        logger.error(f"[BINANCE ERROR] {e}")
        return None


# ══════════════════════════════════════════════════════════════
#  أدمن: قبول / رفض Binance Pay يدوي
# ══════════════════════════════════════════════════════════════

async def binance_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الأدمن يضغط قبول — يطلب المبلغ."""
    query = update.callback_query
    await safe_answer(query)
    if not is_super_admin(update.effective_user.id):
        return

    # callback_data = binance_approve_<order_id>_<uid>
    parts    = query.data.split("_", 4)
    order_id = parts[2]
    uid      = parts[3]

    context.user_data["bnb_approve_order"] = order_id
    context.user_data["bnb_approve_uid"]   = int(uid)
    context.user_data["bnb_admin_state"]   = "waiting_amount"

    await safe_edit(query, 
        f"💛 قبول طلب Binance Pay\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"📝 أرسل المبلغ بالدولار (مثال: <code>5.00</code>):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="adm_main"),
        ]]),
    )


async def binance_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الأدمن يرفض الطلب."""
    query = update.callback_query
    await safe_answer(query)
    if not is_super_admin(update.effective_user.id):
        return

    parts    = query.data.split("_", 4)
    order_id = parts[2]
    uid      = int(parts[3])

    db: Database = context.bot_data["db"]
    db.set_setting(f"bnb_used_{order_id}", "rejected")

    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"❌ <b>تم رفض طلب Binance Pay</b>\n"
                f"🆔 Order ID: <code>{order_id}</code>"
            ),
            parse_mode="HTML",
        )
    except TelegramError:
        pass

    await safe_edit(query, f"❌ تم رفض الطلب: <code>{order_id}</code>", parse_mode="HTML")


async def binance_admin_amount_handler(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE) -> bool:
    """الأدمن يُدخل المبلغ بعد قبول الطلب."""
    if context.user_data.get("bnb_admin_state") != "waiting_amount":
        return False
    if update.effective_user.id != ADMIN_ID:
        return False

    try:
        amount = float((update.message.text or "").strip().replace(",", "."))
        assert amount > 0
    except Exception:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: <code>5.00</code>", parse_mode="HTML")
        return True

    order_id = context.user_data.pop("bnb_approve_order", "")
    uid      = context.user_data.pop("bnb_approve_uid", 0)
    context.user_data.pop("bnb_admin_state", None)

    db: Database = context.bot_data["db"]

    if db.get_setting(f"bnb_used_{order_id}", "") == "1":
        await update.message.reply_text("⚠️ هذا Order ID أُضيف بالفعل.")
        return True

    db.set_setting(f"bnb_used_{order_id}", "1")
    db.add_balance(uid, amount)
    balance = db.get_balance(uid)

    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"✅ <b>تم إضافة رصيدك!</b>\n\n"
                f"🆔 Order ID: <code>{order_id}</code>\n"
                f"💰 أضيف: <b>${amount:.4f}</b>\n"
                f"💳 رصيدك: <b>${balance:.4f}</b>"
            ),
            parse_mode="HTML",
            reply_markup=back_to_main_kb(),
        )
    except TelegramError:
        pass

    await update.message.reply_text(
        f"✅ تم إضافة <b>${amount:.4f}</b> للمستخدم <code>{uid}</code>",
        parse_mode="HTML",
    )
    logger.info(f"[BINANCE MANUAL] admin added ${amount} to uid={uid} order={order_id}")
    return True
