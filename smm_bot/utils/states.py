"""
🔐 utils/states.py — إدارة مركزية لحالات المستخدمين
"""

# كل مفاتيح الـ state في البوت
ALL_USER_KEYS = (
    # طلبات
    "order_state", "order_svc_id", "order_link", "order_qty",
    "order_price", "order_svc", "manual_link",
    # شحن
    "state", "vod_state", "vod_phone", "vod_screenshot",
    "stars_state", "binance_state", "bnb_admin_state",
    # خدمات مجانية
    "free_state", "free_fs_id", "free_svc", "free_qty",
    "free_min", "free_max",
    # تذاكر
    "ticket_state",
    # تتبع
    "tracking_order",
)

ALL_ADM_KEYS = (
    "adm_state", "adm_target",
    "adm_reply_ticket",
    "broadcast_media", "broadcast_media_type", "broadcast_caption",
    "bnb_admin_state",
)


def clear_user_state(context) -> None:
    """امسح كل states المستخدم."""
    for k in ALL_USER_KEYS:
        context.user_data.pop(k, None)


def clear_adm_state(context) -> None:
    """امسح كل states الأدمن."""
    for k in ALL_ADM_KEYS:
        context.user_data.pop(k, None)


def clear_all_states(context) -> None:
    """امسح كل شيء."""
    clear_user_state(context)
    clear_adm_state(context)
