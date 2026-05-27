"""
🔒 فحص الاشتراك الإجباري — utils/subscription.py

ميزات:
- يقبل Channel ID رقمي (@username أو -100xxx)
- يعد الانضمامات تلقائياً
- يحذف القناة تلقائياً لما تصل للحد الأقصى
"""

import logging
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


def _normalize_ch_id(ch_id: str):
    """
    يحوّل channel_id لصيغة يفهمها python-telegram-bot:
    - "@username"    → str
    - "-100xxxxxxx"  → int
    - "100xxxxxxx"   → int (يضيف -)
    """
    ch = ch_id.strip()
    if ch.startswith("@"):
        return ch
    try:
        n = int(ch)
        # لو الرقم موجب بدون علامة سالب يضيف -100 (standard supergroup ID)
        if n > 0:
            return int(f"-100{n}")
        return n
    except ValueError:
        return ch


async def check_subscription(bot: Bot, user_id: int, db) -> tuple[bool, list]:
    """
    Returns (is_fully_subscribed, list_of_missing_channels)
    يتعامل مع @username و numeric chat_id بشكل صحيح.
    """
    channels = db.get_forced_channels()
    if not channels:
        return True, []

    missing = []
    for ch in channels:
        ch_id = _normalize_ch_id(ch["channel_id"])
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except TelegramError as e:
            logger.warning(f"[SUB] تعذّر فحص {ch_id}: {e}")
            # لا نحجب المستخدم إذا تعذّر الفحص

    return len(missing) == 0, missing


async def on_user_joined_channel(bot: Bot, db, channel_id: str):
    """
    يُستدعى لما مستخدم ينضم لقناة.
    يزيد العداد ويحذف القناة من الإجباري لو وصلت للحد.
    """
    reached_max = db.increment_forced_channel_count(channel_id)
    if reached_max:
        ch = None
        for c in db.get_forced_channels():
            if c["channel_id"] == channel_id:
                ch = c
                break

        db.remove_forced_channel(channel_id)
        logger.info(f"[SUB] تم حذف القناة {channel_id} تلقائياً (وصلت للحد الأقصى)")

        # إشعار الأدمن
        from config import ADMIN_ID
        title = ch["channel_title"] if ch else channel_id
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🔔 <b>تم إزالة قناة من الاشتراك الإجباري تلقائياً</b>\n\n"
                    f"📢 القناة: <b>{title}</b>\n"
                    f"🆔 ID: <code>{channel_id}</code>\n"
                    f"✅ وصلت للحد الأقصى من الانضمامات."
                ),
                parse_mode="HTML",
            )
        except TelegramError:
            pass


def subscription_kb_normalized(missing: list) -> InlineKeyboardMarkup:
    """
    يبني لوحة مفاتيح الاشتراك بروابط صحيحة سواء كانت @username أو ID.
    """
    rows = []
    for ch in missing:
        ch_id = ch["channel_id"]
        title = ch.get("channel_title") or ch_id

        # رابط القناة
        if ch_id.startswith("@"):
            link = f"https://t.me/{ch_id.lstrip('@')}"
        else:
            # رقمي → محاولة استخدام invite link لو موجود
            link = ch.get("invite_link", f"https://t.me/c/{ch_id.lstrip('-100')}")

        rows.append([InlineKeyboardButton(f"📢 {title}", url=link)])

    rows.append([InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data="check_sub")])
    return InlineKeyboardMarkup(rows)
