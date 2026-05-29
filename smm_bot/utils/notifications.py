"""
📡 الإشعارات التلقائية — utils/notifications.py
"""

import logging
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


def _pretty_mask(text: str, keep: int = 7) -> str:
    """
    يخفي النص بشكل سلس: 4 نجوم + أول keep حرف من النص.
    مثال:  https://instagram.com/user  →  ****instagr
    """
    if not text:
        return "****"
    # اقتطع البروتوكول للحصول على جزء أنظف
    clean = text.replace("https://", "").replace("http://", "").replace("www.", "")
    chunk = clean[:keep]
    return f"✦✦✦✦{chunk}"


def _mask_id(user_id) -> str:
    """يخفي نصف الـ ID بنجوم منسّقة."""
    s    = str(user_id)
    half = len(s) // 2
    return s[:half] + "✦" * (len(s) - half)


async def notify_new_user(bot: Bot, db, user: dict):
    channel_id = db.get_setting("notif_channel", "")
    if not channel_id:
        return
    total    = db.get_users_count()
    username = f"@{user['username']}" if user.get("username") else "—"
    text = (
        "👤 <b>مستخدم جديد!</b>\n\n"
        f"الاسم: <b>{user.get('first_name','—')}</b>\n"
        f"المعرف: <b>{username}</b>\n"
        f"ID: <code>{user['tg_id']}</code>\n"
        f"إجمالي المستخدمين: <b>{total}</b>"
    )
    try:
        await bot.send_message(chat_id=channel_id, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.warning(f"[NOTIF] فشل إشعار مستخدم جديد: {e}")


async def notify_new_order(bot: Bot, db, order_data: dict, bot_username: str):
    """
    إشعار قناة الطلبات عند تنفيذ طلب SMM.
    الرابط مُخفى: ✦✦✦✦ + أول 7 حروف.
    الـ ID مُخفى: نصف الأرقام ✦.
    """
    channel_id = db.get_setting("orders_channel", "")
    if not channel_id:
        return

    link    = order_data.get("link", "")
    user_id = order_data["user_tg_id"]

    masked_link = _pretty_mask(link, keep=7)
    masked_id   = _mask_id(user_id)

    text = (
        "📦 <b>طلب جديد!</b>\n\n"
        f"🛠 الخدمة:    <b>{order_data.get('service_name','—')}</b>\n"
        f"🔗 الرابط:    <code>{masked_link}</code>\n"
        f"🔢 الكمية:    <b>{order_data['quantity']:,}</b>\n"
        f"💰 السعر:     <b>${order_data['price']:.4f}</b>\n"
        f"🆔 رقم الطلب: <code>{order_data.get('api_order_id','—')}</code>\n"
        f"👤 المستخدم:  <code>{masked_id}</code>"
    )

    bot_name  = bot_username.lstrip("@")
    svc_id    = order_data.get("service_id", "")
    deep_link = f"https://t.me/{bot_name}?start=svc_{svc_id}" if svc_id else f"https://t.me/{bot_name}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 اطلب نفس الخدمة", url=deep_link)]
    ])
    try:
        await bot.send_message(
            chat_id=channel_id,
            text=text,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except TelegramError as e:
        logger.warning(f"[NOTIF] فشل إشعار طلب: {e}")

