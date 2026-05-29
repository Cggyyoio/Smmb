from utils.safe_send import safe_answer, safe_edit, safe_send
"""
🛒 تدفق الطلب الكامل — handlers/order.py
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from database import Database
from utils.api_client import SMMApiClient
from utils.keyboards import (
    order_cancel_kb, order_confirm_kb, back_to_main_kb, service_detail_kb
)
from utils.notifications import notify_new_order

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
#  بدء الطلب — زر «طلب الخدمة الآن»
# ══════════════════════════════════════════════════════════

async def order_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    user = update.effective_user

    if db.is_banned(user.id):
        await safe_answer(query, "🚫 أنت محظور!", show_alert=True)
        return

    service_id = int(query.data.split("_")[2])
    svc = db.get_service(service_id)
    if not svc or not svc["is_active"]:
        await safe_answer(query, "❌ الخدمة غير متوفرة.", show_alert=True)
        return

    # ── مزامنة السعر من API قبل عرض الخدمة ──────────────────
    api: SMMApiClient = context.bot_data["api"]
    try:
        api_services = await api.get_services()
        api_svc = next(
            (s for s in api_services
             if int(s.get("service", -1)) == svc["api_service_id"]),
            None,
        )
        if api_svc:
            new_rate = float(api_svc.get("rate", 0))
            new_min  = int(api_svc.get("min", svc["min_qty"]))
            new_max  = int(api_svc.get("max", svc["max_qty"]))
            # تحديث min/max
            if new_min != svc["min_qty"] or new_max != svc["max_qty"]:
                with db._conn() as conn:
                    conn.execute(
                        "UPDATE services SET min_qty=?, max_qty=? WHERE id=?",
                        (new_min, new_max, service_id),
                    )
            if new_rate > 0:
                sync = db.sync_service_price(service_id, new_rate)
                if sync.get("changed"):
                    logger.info(
                        f"[PRICE SYNC] svc={service_id} "
                        f"${sync['old_price']:.4f}→${sync['new_price']:.4f} "
                        f"margin={sync['margin']:.1f}%"
                    )
                    svc = db.get_service(service_id)
            elif new_min != svc["min_qty"] or new_max != svc["max_qty"]:
                svc = db.get_service(service_id)
    except Exception as e:
        logger.warning(f"[PRICE SYNC] فشل: {e}")
    # ─────────────────────────────────────────────────────────

    balance = db.get_balance(user.id)
    price_per_1 = svc["price_per_1000"] / 1000
    min_cost    = price_per_1 * svc["min_qty"]

    if balance < min_cost:
        await safe_edit(query, 
            f"⚠️ <b>رصيد غير كافٍ!</b>\n\n"
            f"💳 رصيدك الحالي: <code>${balance:.2f}</code>\n"
            f"💵 الحد الأدنى للطلب: <code>${min_cost:.4f}</code>\n\n"
            f"اشحن رصيدك أولاً من القائمة.",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        return

    # حفظ بيانات الطلب الجارية
    context.user_data["order_svc_id"] = service_id
    context.user_data["order_state"]  = "waiting_link"

    await safe_edit(query, 
        f"🛒 <b>طلب خدمة: {svc['name']}</b>\n\n"
        f"📎 أرسل الرابط المطلوب تطبيق الخدمة عليه:",
        reply_markup=order_cancel_kb(),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  معالجة الرسائل في تدفق الطلب
# ══════════════════════════════════════════════════════════

async def order_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    يُستدعى من message_router.
    Returns True إذا تم معالجة الرسالة.
    """
    state = context.user_data.get("order_state")
    if not state:
        return False

    db: Database = context.bot_data["db"]
    user = update.effective_user
    text = (update.message.text or "").strip()

    # ── انتظار الرابط ──────────────────────────────────
    if state == "waiting_link":
        if not text.startswith(("http://", "https://")):
            await update.message.reply_text(
                "❌ الرابط غير صحيح.\nأرسل رابطاً يبدأ بـ http:// أو https://",
                reply_markup=order_cancel_kb(),
            )
            return True

        svc = db.get_service(context.user_data["order_svc_id"])
        context.user_data["order_link"]  = text
        context.user_data["order_state"] = "waiting_qty"

        await update.message.reply_text(
            f"✅ تم استلام الرابط.\n\n"
            f"🔢 أرسل الكمية المطلوبة:\n"
            f"• الحد الأدنى: <b>{svc['min_qty']}</b>\n"
            f"• الحد الأقصى: <b>{svc['max_qty']}</b>",
            reply_markup=order_cancel_kb(),
            parse_mode="HTML",
        )
        return True

    # ── انتظار الكمية ──────────────────────────────────
    if state == "waiting_qty":
        if not text.isdigit():
            await update.message.reply_text(
                "❌ الكمية يجب أن تكون رقماً صحيحاً.",
                reply_markup=order_cancel_kb(),
            )
            return True

        qty = int(text)
        svc = db.get_service(context.user_data["order_svc_id"])
        if qty < svc["min_qty"] or qty > svc["max_qty"]:
            await update.message.reply_text(
                f"❌ الكمية خارج النطاق المسموح!\n"
                f"• الحد الأدنى: <b>{svc['min_qty']}</b>\n"
                f"• الحد الأقصى: <b>{svc['max_qty']}</b>",
                reply_markup=order_cancel_kb(),
                parse_mode="HTML",
            )
            return True

        # ── فحص الخدمة المحظورة ──
        if db.is_service_blocked(user.id, svc["id"]):
            await update.message.reply_text(
                "⛔ هذه الخدمة غير متاحة لحسابك.\n"
                "تواصل مع الدعم للمزيد.",
            )
            context.user_data.pop("order_state", None)
            return True

        # ── حساب السعر مع خصم VIP ──
        vip_discount = db.get_vip_discount(user.id)
        base_price   = svc["price_per_1000"] / 1000
        if vip_discount > 0:
            base_price = base_price * (1 - vip_discount / 100)
        price   = round(base_price * qty, 4)
        balance = db.get_balance(user.id)

        # ── العملة الثانية ──
        cur2_name, cur2_rate = db.get_second_currency()
        price2_str = f" | {cur2_name} {price * cur2_rate:.1f}" if db.second_currency_enabled() and cur2_rate > 0 else ""
        vip_line   = f"⭐ خصم VIP: <b>{vip_discount:.0f}%</b>\n" if vip_discount > 0 else ""

        context.user_data["order_qty"]   = qty
        context.user_data["order_price"] = price
        context.user_data["order_state"] = "waiting_confirm"

        await update.message.reply_text(
            f"📋 <b>ملخّص الطلب</b>\n\n"
            f"🛠 الخدمة:  <b>{svc['name']}</b>\n"
            f"🔗 الرابط:  <code>{context.user_data['order_link']}</code>\n"
            f"🔢 الكمية:  <b>{qty}</b>\n"
            f"{vip_line}"
            f"💰 التكلفة: <b>${price:.4f}</b>{price2_str}\n"
            f"💳 رصيدك:  <b>${balance:.2f}</b>\n\n"
            f"هل تؤكد الطلب؟",
            reply_markup=order_confirm_kb(),
            parse_mode="HTML",
        )
        return True

    return False


# ══════════════════════════════════════════════════════════
#  تأكيد الطلب
# ══════════════════════════════════════════════════════════

async def order_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    user = update.effective_user

    svc_id  = context.user_data.get("order_svc_id")
    link    = context.user_data.get("order_link")
    qty     = context.user_data.get("order_qty")
    price   = context.user_data.get("order_price")

    if not all([svc_id, link, qty, price]):
        await safe_edit(query, 
            "❌ انتهت جلسة الطلب. ابدأ من جديد.",
            reply_markup=back_to_main_kb()
        )
        _clear_order(context)
        return

    svc = db.get_service(svc_id)
    if not svc:
        await safe_edit(query, "❌ الخدمة غير موجودة.", reply_markup=back_to_main_kb())
        _clear_order(context)
        return

    # خصم الرصيد
    deducted = db.deduct_balance(user.id, price)
    if not deducted:
        balance = db.get_balance(user.id)
        await safe_edit(query, 
            f"⚠️ <b>رصيد غير كافٍ!</b>\n\n"
            f"💳 رصيدك: <code>${balance:.2f}</code>\n"
            f"💵 التكلفة: <code>${price:.4f}</code>",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        _clear_order(context)
        return

    # إرسال الطلب للـ API
    await safe_edit(query, 
        "⚙️ <b>جارٍ إرسال الطلب...</b>",
        parse_mode="HTML",
    )

    api: SMMApiClient = context.bot_data["api"]
    api_result = await api.add_order(
        service=svc["api_service_id"],
        link=link,
        quantity=qty,
    )

    api_order_id = api_result.get("order")
    error_msg    = api_result.get("error")

    if not api_order_id:
        # استعادة الرصيد عند الفشل
        db.add_balance(user.id, price)
        await safe_edit(query, 
            f"❌ <b>فشل إرسال الطلب!</b>\n\n"
            f"السبب: {error_msg or 'خطأ غير معروف'}\n\n"
            f"تم استعادة رصيدك.",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        _clear_order(context)
        return

    # حفظ الطلب في قاعدة البيانات
    local_id = db.create_order(
        user_tg_id=user.id,
        service_id=svc_id,
        link=link,
        quantity=qty,
        price=price,
        api_order_id=str(api_order_id),
    )

    # ── نقاط ──
    if db.points_enabled():
        pts_rate   = db.get_points_rate()
        pts_earned = max(1, int(price * pts_rate))
        db.add_points(user.id, pts_earned)
    else:
        pts_earned = 0

    # ── تنبيه رصيد منخفض ──
    from handlers.features import check_low_balance
    await check_low_balance(context.bot, db, user.id)

    balance_after = db.get_balance(user.id)

    # ── العملة الثانية ──
    cur2_name, cur2_rate = db.get_second_currency()
    bal2_str   = f" | {cur2_name} {balance_after * cur2_rate:.1f}" if db.second_currency_enabled() and cur2_rate > 0 else ""
    pts_line   = f"\n🎯 كسبت: <b>{pts_earned} نقطة</b>" if pts_earned > 0 else ""

    await safe_edit(query, 
        f"✅ <b>تم إرسال الطلب بنجاح!</b>\n\n"
        f"🆔 رقم الطلب: <code>{api_order_id}</code>\n"
        f"🛠 الخدمة: <b>{svc['name']}</b>\n"
        f"🔢 الكمية: <b>{qty}</b>\n"
        f"💰 التكلفة: <b>${price:.4f}</b>\n"
        f"💳 رصيدك المتبقي: <code>${balance_after:.4f}</code>{bal2_str}"
        f"{pts_line}\n\n"
        f"تتبع طلبك بالأمر: /track {api_order_id}",
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )

    # إشعار قناة الطلبات
    from config import BOT_USERNAME
    order_data = {
        "user_tg_id":   user.id,
        "service_id":   svc_id,
        "service_name": svc["name"],
        "link":         link,
        "quantity":     qty,
        "price":        price,
        "api_order_id": str(api_order_id),
    }
    await notify_new_order(context.bot, db, order_data, BOT_USERNAME)
    _clear_order(context)


# ══════════════════════════════════════════════════════════
#  إلغاء الطلب
# ══════════════════════════════════════════════════════════

async def order_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    from utils.states import clear_all_states
    clear_all_states(context)
    # ارجع للقائمة الرئيسية مباشرة
    from handlers.user_menu import menu_main_callback
    await menu_main_callback(update, context)


# ══════════════════════════════════════════════════════════
#  /track — تتبع حالة طلب
# ══════════════════════════════════════════════════════════

async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db: Database = context.bot_data["db"]
    if db.is_banned(update.effective_user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "📡 الاستخدام: /track <رقم_الطلب>\nمثال: /track 123456",
            reply_markup=back_to_main_kb(),
        )
        return

    order_id = args[0]
    api: SMMApiClient = context.bot_data["api"]
    await update.message.reply_text(
        "🔍 <b>جارٍ جلب حالة الطلب...</b>",
        parse_mode="HTML",
    )
    result = await api.get_order_status(order_id)

    if not result:
        await update.message.reply_text(
            "❌ تعذّر جلب بيانات الطلب. تحقق من الرقم.",
            reply_markup=back_to_main_kb(),
        )
        return

    status = result.get("status", "—")
    charge = result.get("charge", "—")
    start_count = result.get("start_count", "—")
    remains     = result.get("remains", "—")
    currency    = result.get("currency", "")

    status_map = {
        "Pending":    "⏳ في الانتظار",
        "In progress": "⚙️ جارٍ التنفيذ",
        "Completed":  "✅ مكتمل",
        "Canceled":   "❌ ملغي",
        "Partial":    "⚠️ جزئي",
    }
    status_ar = status_map.get(status, status)

    await update.message.reply_text(
        f"📦 <b>حالة الطلب #{order_id}</b>\n\n"
        f"📊 الحالة:    <b>{status_ar}</b>\n"
        f"🔢 المبدأ:   <b>{start_count}</b>\n"
        f"⬇️ المتبقي:  <b>{remains}</b>\n"
        f"💰 التكلفة: <b>{charge} {currency}</b>",
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )


async def track_order_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """معالجة رقم الطلب المُدخَل بعد الضغط على زر تتبع."""
    if context.user_data.get("state") != "tracking_order":
        return False

    context.user_data.pop("state", None)
    text = (update.message.text or "").strip()
    if not text:
        return False

    api: SMMApiClient = context.bot_data["api"]
    msg = await update.message.reply_text("🔍 جارٍ جلب حالة الطلب...")
    result = await api.get_order_status(text)

    if not result:
        await msg.edit_text(
            "❌ تعذّر جلب بيانات الطلب. تحقق من الرقم.",
            reply_markup=back_to_main_kb(),
        )
        return True

    status   = result.get("status", "—")
    remains  = result.get("remains", "—")
    charge   = result.get("charge", "—")
    currency = result.get("currency", "")
    status_map = {
        "Pending": "⏳ في الانتظار", "In progress": "⚙️ جارٍ التنفيذ",
        "Completed": "✅ مكتمل", "Canceled": "❌ ملغي", "Partial": "⚠️ جزئي",
    }
    await msg.edit_text(
        f"📦 <b>حالة الطلب #{text}</b>\n\n"
        f"📊 الحالة: <b>{status_map.get(status, status)}</b>\n"
        f"⬇️ المتبقي: <b>{remains}</b>\n"
        f"💰 التكلفة: <b>{charge} {currency}</b>",
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )
    return True


# ══════════════════════════════════════════════════════════
#  مساعد
# ══════════════════════════════════════════════════════════

def _clear_order(context: ContextTypes.DEFAULT_TYPE):
    from utils.states import clear_user_state
    clear_user_state(context)


# ══════════════════════════════════════════════════════════
#  طلب الرشق — refill
# ══════════════════════════════════════════════════════════

async def refill_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض نافذة طلب الرشق — يطلب رقم الطلب القديم."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    user = update.effective_user

    if db.is_banned(user.id):
        await safe_answer(query, "🚫 أنت محظور!", show_alert=True)
        return

    service_id = int(query.data.split("_")[2])
    svc = db.get_service(service_id)
    if not svc or not svc["is_active"]:
        await safe_answer(query, "❌ الخدمة غير متوفرة.", show_alert=True)
        return

    context.user_data["refill_svc_id"] = service_id
    context.user_data["order_state"]   = "waiting_refill_order_id"

    from utils.keyboards import manual_order_kb
    await safe_edit(query, 
        f"♻️ <b>طلب رشق</b>\\n\\n"
        f"الخدمة: <b>{svc['name']}</b>\\n\\n"
        f"📎 أرسل <b>رقم الطلب القديم</b> الذي تريد رشقه:",
        reply_markup=manual_order_kb(service_id),
        parse_mode="HTML",
    )


async def refill_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """معالجة رقم الطلب لطلب الرشق."""
    state = context.user_data.get("order_state")
    if state != "waiting_refill_order_id":
        return False

    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("❌ أرسل رقم الطلب (أرقام فقط).")
        return True

    order_id = int(text)
    api: SMMApiClient = context.bot_data["api"]
    svc_id = context.user_data.pop("refill_svc_id", None)
    context.user_data.pop("order_state", None)

    result = await api.create_refill(order_id)
    refill_id = result.get("refill") if result else None

    if refill_id:
        await update.message.reply_text(
            f"✅ <b>تم إرسال طلب الرشق!</b>\\n\\n"
            f"🆔 رقم الطلب: <code>{order_id}</code>\\n"
            f"♻️ رقم الرشق: <code>{refill_id}</code>",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
    else:
        err = result.get("error", "خطأ غير معروف") if result else "تعذّر الاتصال"
        await update.message.reply_text(
            f"❌ <b>فشل طلب الرشق!</b>\\nالسبب: {err}",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
    return True


# ══════════════════════════════════════════════════════════
#  الطلب اليدوي — manual order
# ══════════════════════════════════════════════════════════

async def manual_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تدفق الطلب اليدوي."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    user = update.effective_user

    if db.is_banned(user.id):
        await safe_answer(query, "🚫 أنت محظور!", show_alert=True)
        return

    service_id = int(query.data.split("_")[2])
    svc = db.get_service(service_id)
    if not svc or not svc["is_active"]:
        await safe_answer(query, "❌ الخدمة غير متوفرة.", show_alert=True)
        return

    context.user_data["manual_svc_id"] = service_id
    context.user_data["order_state"]   = "manual_waiting_link"

    from utils.keyboards import manual_order_kb
    await safe_edit(query, 
        f"✍️ <b>طلب يدوي</b> — {svc['name']}\\n\\n"
        f"💰 السعر: <b>${svc['price_per_1000']:.4f}</b>/1000\\n"
        f"📊 الكمية: {svc['min_qty']} – {svc['max_qty']}\\n\\n"
        f"📎 أرسل الرابط المطلوب:",
        reply_markup=manual_order_kb(service_id),
        parse_mode="HTML",
    )


async def manual_order_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """معالجة مراحل الطلب اليدوي."""
    state = context.user_data.get("order_state")
    if not state or not state.startswith("manual_"):
        return False

    db: Database = context.bot_data["db"]
    user = update.effective_user
    text = (update.message.text or "").strip()

    if state == "manual_waiting_link":
        if not text.startswith(("http://", "https://")):
            await update.message.reply_text(
                "❌ الرابط غير صحيح. أرسل رابطاً يبدأ بـ http:// أو https://",
            )
            return True
        svc = db.get_service(context.user_data["manual_svc_id"])
        context.user_data["manual_link"]  = text
        context.user_data["order_state"]  = "manual_waiting_qty"
        await update.message.reply_text(
            f"✅ تم استلام الرابط.\\n\\n"
            f"🔢 أرسل الكمية:\\n"
            f"• الحد الأدنى: <b>{svc['min_qty']}</b>\\n"
            f"• الحد الأقصى: <b>{svc['max_qty']}</b>",
            parse_mode="HTML",
        )
        return True

    if state == "manual_waiting_qty":
        if not text.isdigit():
            await update.message.reply_text("❌ الكمية يجب أن تكون رقماً صحيحاً.")
            return True
        qty = int(text)
        svc = db.get_service(context.user_data["manual_svc_id"])
        if qty < svc["min_qty"] or qty > svc["max_qty"]:
            await update.message.reply_text(
                f"❌ الكمية خارج النطاق!\\n"
                f"• الأدنى: <b>{svc['min_qty']}</b> — الأقصى: <b>{svc['max_qty']}</b>",
                parse_mode="HTML",
            )
            return True

        price   = round((svc["price_per_1000"] / 1000) * qty, 4)
        balance = db.get_balance(user.id)

        context.user_data["manual_qty"]   = qty
        context.user_data["manual_price"] = price
        context.user_data["order_state"]  = "manual_waiting_confirm"

        await update.message.reply_text(
            f"📋 <b>ملخّص الطلب اليدوي</b>\\n\\n"
            f"🛠 الخدمة:  <b>{svc['name']}</b>\\n"
            f"🔗 الرابط:  <code>{context.user_data['manual_link']}</code>\\n"
            f"🔢 الكمية:  <b>{qty}</b>\\n"
            f"💰 التكلفة: <b>${price:.4f}</b>\\n"
            f"💳 رصيدك:  <b>${balance:.2f}</b>\\n\\n"
            f"أرسل ✅ لتأكيد الطلب أو ❌ للإلغاء:",
            reply_markup=order_confirm_kb(),
            parse_mode="HTML",
        )
        return True

    if state == "manual_waiting_confirm":
        # يتعامل معها order_confirm_callback عبر الزر
        return False

    return False


async def manual_order_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد الطلب اليدوي عبر زر التأكيد."""
    query = update.callback_query

    # إذا كان الطلب يدوياً
    if context.user_data.get("order_state") == "manual_waiting_confirm":
        await safe_answer(query)
        db: Database = context.bot_data["db"]
        user = update.effective_user
        svc_id = context.user_data.pop("manual_svc_id", None)
        link   = context.user_data.pop("manual_link", None)
        qty    = context.user_data.pop("manual_qty", None)
        price  = context.user_data.pop("manual_price", None)
        context.user_data.pop("order_state", None)

        svc = db.get_service(svc_id) if svc_id else None
        if not svc or not all([link, qty, price]):
            await safe_edit(query, "❌ انتهت الجلسة. ابدأ من جديد.", reply_markup=back_to_main_kb())
            return

        deducted = db.deduct_balance(user.id, price)
        if not deducted:
            balance = db.get_balance(user.id)
            await safe_edit(query, 
                f"⚠️ <b>رصيد غير كافٍ!</b>\\n💳 رصيدك: ${balance:.2f}\\n💵 التكلفة: ${price:.4f}",
                reply_markup=back_to_main_kb(), parse_mode="HTML",
            )
            return

        await safe_edit(query, "⚙️ <b>جارٍ إرسال الطلب...</b>", parse_mode="HTML")
        api: SMMApiClient = context.bot_data["api"]
        api_result = await api.add_order(service=svc["api_service_id"], link=link, quantity=qty)
        api_order_id = api_result.get("order")

        if not api_order_id:
            db.add_balance(user.id, price)
            await safe_edit(query, 
                f"❌ <b>فشل الطلب!</b>\\n{api_result.get('error','خطأ')}\\nتم استعادة رصيدك.",
                reply_markup=back_to_main_kb(), parse_mode="HTML",
            )
            return

        db.create_order(user_tg_id=user.id, service_id=svc_id, link=link,
                        quantity=qty, price=price, api_order_id=str(api_order_id))
        balance_after = db.get_balance(user.id)
        await safe_edit(query, 
            f"✅ <b>تم إرسال الطلب اليدوي!</b>\\n\\n"
            f"🆔 رقم الطلب: <code>{api_order_id}</code>\\n"
            f"💳 رصيدك المتبقي: <code>${balance_after:.2f}</code>",
            reply_markup=back_to_main_kb(), parse_mode="HTML",
        )
