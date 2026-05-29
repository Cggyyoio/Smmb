"""
╔══════════════════════════════════════════════════════════╗
║   🔄 مزامنة الخدمات التلقائية — service_sync.py          ║
║                                                          ║
║  تعمل كـ job دورية كل 30 دقيقة:                         ║
║  • تحذف الخدمات المحذوفة من API وترسل إشعار             ║
║  • تحدّث الأسعار التي تغيّرت وترسل إشعار (↑↓)           ║
║  • تحدّث min/max لكل خدمة                                ║
╚══════════════════════════════════════════════════════════╝
"""

import logging
from telegram import Bot
from telegram.error import TelegramError
from config import BOT_USERNAME

logger = logging.getLogger(__name__)


async def _get_updates_channel(db) -> str | None:
    ch = db.get_setting("updates_channel", "").strip()
    return ch if ch else None


def _order_deep_link(api_service_id: int) -> str:
    """رابط deep link يفتح البوت مباشرة على الخدمة."""
    bot = BOT_USERNAME.lstrip("@")
    return f"https://t.me/{bot}?start=svc_{api_service_id}"


async def _notify_deleted(bot: Bot, ch: str, svc: dict):
    """إشعار حذف خدمة من الـ API."""
    cat_name  = svc.get("_cat_name", "—")
    plat_name = svc.get("_plat", "—")
    try:
        await bot.send_message(
            chat_id=ch,
            text=(
                f"🗑️ <b>خدمة تم إزالتها</b>\n\n"
                f"🏷️ الاسم: {svc['name']}\n"
                f"📱 المنصة: {plat_name}\n"
                f"📂 القسم: {cat_name}"
            ),
            parse_mode="HTML",
        )
    except TelegramError as e:
        logger.warning(f"[SYNC] فشل إشعار الحذف: {e}")


async def _notify_price_change(bot: Bot, ch: str, svc: dict,
                                old_price: float, new_price: float,
                                margin: float):
    """إشعار تغيّر السعر (↑ أو ↓)."""
    direction = "📈 ارتفع" if new_price > old_price else "📉 انخفض"
    arrow     = "🔺" if new_price > old_price else "🔻"
    cat_name  = svc.get("_cat_name", "—")
    plat_name = svc.get("_plat", "—")

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    import config as _cfg
    bot_name  = getattr(_cfg, "BOT_USERNAME", "").lstrip("@")
    svc_id    = svc.get("id", "")
    deep_link = f"https://t.me/{bot_name}?start=svc_{svc_id}" if bot_name and svc_id else f"https://t.me/{bot_name}"

    try:
        await bot.send_message(
            chat_id=ch,
            text=(
                f"{arrow} <b>سعر خدمة {direction}</b>\n\n"
                f"🏷️ الاسم: {svc['name']}\n"
                f"📱 المنصة: {plat_name}\n"
                f"📂 القسم: {cat_name}\n\n"
                f"💰 السعر القديم: <b>${old_price:.4f}</b> / 1000\n"
                f"💰 السعر الجديد: <b>${new_price:.4f}</b> / 1000\n"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 اطلب هذه الخدمة", url=deep_link)]
            ]),
            parse_mode="HTML",
        )
    except TelegramError as e:
        logger.warning(f"[SYNC] فشل إشعار السعر: {e}")


async def services_sync_job(context):
    """
    Job دورية — تُشغَّل كل 30 دقيقة.
    تقارن خدمات الـ DB بخدمات API وترسل إشعارات بالتغييرات.
    """
    db  = context.bot_data.get("db")
    api = context.bot_data.get("api")
    bot: Bot = context.bot

    if not db or not api:
        return

    ch = await _get_updates_channel(db)

    try:
        api_services = await api.get_services()
    except Exception as e:
        logger.error(f"[SYNC JOB] فشل جلب الخدمات من API: {e}")
        return

    # نبني dict سريع من api_service_id → بيانات API
    api_map = {int(s.get("service", -1)): s for s in api_services}

    # نجيب كل خدمات DB
    db_services = db.get_all_services()

    # ── تحقق من أن الـ API شغال قبل أي حذف ──────────────
    _api_is_alive = False
    try:
        balance = await api.get_balance()
        _api_is_alive = balance is not None
        if not _api_is_alive:
            logger.warning("[SYNC] فشل التحقق من رصيد الـ API — لن يتم حذف أي خدمة")
        else:
            logger.info(f"[SYNC] الـ API شغال — الرصيد: {balance}")
    except Exception as e:
        logger.warning(f"[SYNC] تعذّر التحقق من رصيد الـ API: {e}")

    deleted_count    = 0
    price_up_count   = 0
    price_down_count = 0
    minmax_count     = 0

    for svc in db_services:
        api_svc_id = svc.get("api_service_id")
        if not api_svc_id:
            continue

        api_data = api_map.get(int(api_svc_id))

        # ── جلب اسم القسم والمنصة للإشعارات ──────────────
        cat  = db.get_category(svc["category_id"]) or {}
        plat = None
        if cat.get("platform_id"):
            plat = db.get_platform(cat["platform_id"]) or {}
        svc["_cat_name"] = f"{cat.get('emoji','')} {cat.get('name','')}".strip()
        svc["_plat"]     = f"{plat.get('emoji','')} {plat.get('name','')}".strip() if plat else "—"

        # ── 1. خدمة محذوفة من API ─────────────────────────
        if api_data is None:
            # تحقق من رصيد الـ API قبل الحذف — لو الـ API واقف مش نحذف
            if not _api_is_alive:
                logger.warning(f"[SYNC] تخطي حذف #{svc['id']} — الـ API لا يستجيب")
                continue
            logger.info(f"[SYNC] حذف خدمة #{svc['id']} (api_id={api_svc_id}) - غير موجودة في API")
            db.delete_service(svc["id"])
            deleted_count += 1
            if ch:
                await _notify_deleted(bot, ch, svc)
            continue

        # ── 2. تحديث min/max ──────────────────────────────
        new_min = int(api_data.get("min", svc["min_qty"]))
        new_max = int(api_data.get("max", svc["max_qty"]))
        if new_min != svc["min_qty"] or new_max != svc["max_qty"]:
            with db._conn() as conn:
                conn.execute(
                    "UPDATE services SET min_qty=?, max_qty=? WHERE id=?",
                    (new_min, new_max, svc["id"]),
                )
            minmax_count += 1

        # ── 3. تحديث السعر ────────────────────────────────
        new_rate = float(api_data.get("rate", 0))
        if new_rate <= 0:
            continue

        sync = db.sync_service_price(svc["id"], new_rate)
        if not sync.get("changed"):
            continue

        old_p = sync["old_price"]
        new_p = sync["new_price"]

        if new_p > old_p:
            price_up_count += 1
        else:
            price_down_count += 1

        logger.info(
            f"[SYNC] سعر #{svc['id']} {old_p:.4f}→{new_p:.4f} "
            f"(margin={sync['margin']:.1f}%)"
        )

        if ch:
            await _notify_price_change(bot, ch, svc, old_p, new_p, sync["margin"])

    logger.info(
        f"[SYNC JOB] ✅ انتهت المزامنة: "
        f"حُذف={deleted_count} | سعر↑={price_up_count} | "
        f"سعر↓={price_down_count} | min/max={minmax_count}"
    )


def register_service_sync(app, interval_minutes: int = 30):
    """تسجيل الـ job في bot job queue."""
    if not app.job_queue:
        logger.warning("[SYNC] job_queue غير متاح — لم يتم تسجيل مزامنة الخدمات")
        return
    interval = interval_minutes * 60
    app.job_queue.run_repeating(
        services_sync_job,
        interval=interval,
        first=60,  # أول تشغيل بعد دقيقة من بدء البوت
    )
    logger.info(f"[SYNC] مزامنة الخدمات مسجّلة كل {interval_minutes} دقيقة")


