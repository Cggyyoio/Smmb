"""
╔══════════════════════════════════════════════════════╗
║   🔄 سيستم تتبع الطلبات والاسترداد التلقائي          ║
║              order_checker.py                        ║
║                                                      ║
║  يفحص الطلبات النشطة كل X دقيقة ويسترد الفلوس:      ║
║   • طلب ملغى   → استرداد كامل + إشعار المستخدم      ║
║   • طلب جزئي   → استرداد الفرق + إشعار المستخدم     ║
╚══════════════════════════════════════════════════════╝
"""

import logging
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

from database import Database
from utils.api_client import SMMApiClient
from config import ADMIN_ID

logger = logging.getLogger(__name__)

BATCH_SIZE   = 100     # عدد الطلبات لكل API call
MIN_REFUND   = 0.0001  # أقل مبلغ يُسترد

FINAL_STATUSES = {"completed", "cancelled", "canceled", "partial", "refunded"}


# ══════════════════════════════════════════════════════════════
#  Migration — إضافة الأعمدة الجديدة للـ DB
# ══════════════════════════════════════════════════════════════

def run_migrations(db: Database):
    for col, typ, default in [
        ("remains",          "INTEGER", "NULL"),
        ("refunded_amount",  "REAL",    "0"),
        ("checker_status",   "TEXT",    "NULL"),
    ]:
        try:
            with db._conn() as conn:
                conn.execute(
                    f"ALTER TABLE orders ADD COLUMN {col} {typ} DEFAULT {default}"
                )
        except Exception:
            pass
    db.migrate_forced_channels()
    db.migrate_admins()
    logger.info("[MIGRATION] ✅ اكتملت ترقية قاعدة البيانات")


# ══════════════════════════════════════════════════════════════
#  جلب الطلبات النشطة
# ══════════════════════════════════════════════════════════════

def _get_active_orders(db: Database) -> list:
    with db._conn() as conn:
        rows = conn.execute(
            """SELECT o.id, o.user_tg_id, o.api_order_id,
                      o.quantity, o.price, o.status,
                      o.refunded_amount,
                      s.price_per_1000,
                      s.name as service_name
               FROM orders o
               LEFT JOIN services s ON o.service_id = s.id
               WHERE o.status IN ('pending', 'in progress', 'processing', 'inprogress')
                 AND o.api_order_id IS NOT NULL
                 AND o.api_order_id != ''
               ORDER BY o.id ASC
               LIMIT 500"""
        ).fetchall()
        return [dict(r) for r in rows]


def _mark_order(db: Database, order_id: int, status: str, remains: int = None,
                refunded: float = 0):
    """
    يحدّث حالة الطلب في DB.
    الحالات النهائية (completed/cancelled/partial) لن تظهر في الفحص القادم
    لأن _get_active_orders تجلب pending/processing فقط.
    """
    # نوحّد الأسماء
    status_clean = status.lower().strip()
    if status_clean == "canceled":
        status_clean = "cancelled"

    with db._conn() as conn:
        conn.execute(
            """UPDATE orders
               SET status          = ?,
                   remains         = COALESCE(?, remains),
                   refunded_amount = COALESCE(refunded_amount, 0) + ?,
                   checker_status  = ?
               WHERE id = ?""",
            (
                status_clean,
                remains,
                refunded,
                f"checked:{datetime.now().strftime('%Y-%m-%d %H:%M')}",
                order_id,
            ),
        )


# ══════════════════════════════════════════════════════════════
#  حساب مبلغ الاسترداد
# ══════════════════════════════════════════════════════════════

def _calc_refund(order: dict, api_data: dict) -> tuple[float, str, int]:
    """
    يُعيد (refund_amount, reason, remains_count)

    منطق الاسترداد:
    - ملغي  → نرجع كامل order["price"]  (الـ charge = 0)
    - جزئي  → نرجع (order["price"] - charge) أي اللي ما اتصرفش فعلاً
    """
    raw     = api_data.get("status", "").lower().strip()
    charge  = round(float(api_data.get("charge") or 0), 6)
    remains = int(api_data.get("remains") or 0)
    price   = round(float(order["price"]), 6)

    # ── ملغي: charge = 0 → كل الفلوس ترجع ──
    if raw in ("cancelled", "canceled"):
        return price, "cancelled", 0

    # ── جزئي: نرجع الفرق (ما دفعه - ما اتصرف فعلاً) ──
    if raw == "partial":
        if remains <= 0:
            return 0.0, "partial_done", 0
        refund = round(price - charge, 6)
        if refund <= MIN_REFUND:
            return 0.0, "no_refund", remains
        return refund, "partial", remains

    return 0.0, "no_refund", 0


# ══════════════════════════════════════════════════════════════
#  إشعار المستخدم
# ══════════════════════════════════════════════════════════════

async def _notify_user(bot: Bot, order: dict, refund: float,
                       reason: str, remains: int):
    uid      = order["user_tg_id"]
    svc_name = order.get("service_name") or "—"

    if reason in ("cancelled", "canceled"):
        text = (
            f"🔔 <b>تحديث على طلبك</b>\n\n"
            f"❌ <b>تم إلغاء الطلب</b>\n"
            f"🆔 <code>{order['api_order_id']}</code>\n"
            f"📦 {svc_name}\n\n"
            f"💰 تم إرجاع <b>${refund:.4f}</b> لرصيدك تلقائياً ✅"
        )
    elif reason == "partial":
        executed = int(order["quantity"]) - remains
        text = (
            f"🔔 <b>تحديث على طلبك</b>\n\n"
            f"⚠️ <b>تم تنفيذه جزئياً</b>\n"
            f"🆔 <code>{order['api_order_id']}</code>\n"
            f"📦 {svc_name}\n\n"
            f"✅ المنفَّذ:      <b>{executed:,}</b>\n"
            f"❌ غير المنفَّذ: <b>{remains:,}</b>\n\n"
            f"💰 تم إرجاع <b>${refund:.4f}</b> لرصيدك تلقائياً ✅"
        )
    elif reason == "completed":
        text = (
            f"🔔 <b>تحديث على طلبك</b>\n\n"
            f"✅ <b>تم تنفيذ الطلب بنجاح!</b>\n"
            f"🆔 <code>{order['api_order_id']}</code>\n"
            f"📦 {svc_name}\n"
            f"🔢 الكمية: <b>{order['quantity']:,}</b>\n"
            f"💰 المبلغ: <b>${order['price']:.4f}</b>"
        )
    else:
        return

    try:
        await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.warning(f"[NOTIFY] فشل إشعار {uid}: {e}")


# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════

async def _send_report(bot: Bot, db: Database,
                       processed: int, refunded: int, total: float):
    """
    يرسل تقرير الاسترداد إلى:
    - قناة التقارير (checker_channel) لو موجودة
    - وإلا للأدمن الرئيسي مباشرة
    """
    text = (
        f"📊 <b>تقرير فحص الطلبات</b>\n\n"
        f"🔍 فُحص: <b>{processed}</b> طلب\n"
        f"💸 استُرد في: <b>{refunded}</b> طلب\n"
        f"💰 إجمالي مُسترد: <b>${total:.4f}</b>\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    # أولوية: قناة التقارير → الأدمن الرئيسي
    channel = db.get_setting("checker_channel", "")
    target  = channel if channel else ADMIN_ID
    try:
        await bot.send_message(chat_id=target, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.warning(f"[REPORT] فشل إرسال التقرير إلى {target}: {e}")
        # fallback للأدمن لو القناة فشلت
        if channel:
            try:
                await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="HTML")
            except TelegramError:
                pass


async def check_and_refund_orders(bot: Bot, db: Database, api: SMMApiClient):
    orders = _get_active_orders(db)
    if not orders:
        return

    logger.info(f"[CHECKER] 🔍 فحص {len(orders)} طلب نشط...")
    total_refunded  = 0.0
    count_refunded  = 0
    count_processed = 0

    for i in range(0, len(orders), BATCH_SIZE):
        batch = orders[i:i + BATCH_SIZE]

        # ── جلب الحالات بـ parallel calls فردية (أكثر موثوقية من batch) ──
        async def _fetch(order):
            try:
                res = await api.get_order_status(order["api_order_id"])
                logger.debug(
                    f"[CHECKER] api={order['api_order_id']} → {res}"
                )
                return str(order["api_order_id"]), res if isinstance(res, dict) else {}
            except Exception as e:
                logger.warning(f"[CHECKER] فشل جلب {order['api_order_id']}: {e}")
                return str(order["api_order_id"]), {}

        results  = await asyncio.gather(*[_fetch(o) for o in batch])
        statuses = {k: v for k, v in results}

        for order in batch:
            count_processed += 1
            api_id   = str(order["api_order_id"])
            api_data = statuses.get(api_id, {})

            if not api_data:
                logger.warning(f"[CHECKER] لا يوجد رد لـ api_id={api_id}")
                continue

            raw_status = api_data.get("status", "").strip()
            logger.info(
                f"[CHECKER] order={order['id']} api={api_id} status={raw_status!r}"
            )

            if not raw_status:
                continue

            refund, reason, remains = _calc_refund(order, api_data)

            logger.info(
                f"[CHECKER] order={order['id']} refund={refund:.4f} reason={reason}"
            )

            # ── إشعار الاكتمال ──
            if raw_status.lower() in ("completed",) and order.get("status", "").lower() not in ("completed",):
                await _notify_user(bot, order, 0, "completed", 0)

            # ── أولاً: أضف الرصيد قبل تغيير الحالة ──
            if refund > MIN_REFUND:
                db.add_balance(order["user_tg_id"], refund)

                count_refunded += 1
                total_refunded  = round(total_refunded + refund, 6)

                logger.info(
                    f"[REFUND] ✅ order={order['id']} api={api_id} "
                    f"uid={order['user_tg_id']} "
                    f"reason={reason} amount=${refund:.4f}"
                )

                await _notify_user(bot, order, refund, reason, remains)

            # ── ثانياً: حدّث الحالة في DB ──
            _mark_order(
                db, order["id"], raw_status,
                remains if reason != "no_refund" else None,
                refund if refund > MIN_REFUND else 0,
            )

        await asyncio.sleep(0.3)

    logger.info(
        f"[CHECKER] ✅ فحص {count_processed} | "
        f"استرداد {count_refunded} | إجمالي ${total_refunded:.4f}"
    )

    if count_refunded > 0:
        await _send_report(bot, db, count_processed, count_refunded, total_refunded)


# ══════════════════════════════════════════════════════════════
#  التسجيل في job_queue
# ══════════════════════════════════════════════════════════════

def register_order_checker(app, db: Database, api: SMMApiClient,
                           interval_minutes: int = 10):
    run_migrations(db)

    async def job(context):
        await check_and_refund_orders(context.bot, db, api)

    app.job_queue.run_repeating(
        job,
        interval=interval_minutes * 60,
        first=10,
        name="order_checker",
    )
    logger.info(f"[CHECKER] ✅ فحص الطلبات كل {interval_minutes} دقيقة")

