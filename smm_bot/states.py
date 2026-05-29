"""
حالات ConversationHandler — states.py
"""

# ── تدفق الطلب ─────────────────────────────────────────
ORDER_LINK    = 10
ORDER_QTY     = 11
ORDER_CONFIRM = 12

# ── تدفق الشحن ────────────────────────────────────────
CHARGE_TXID       = 20
CHARGE_GIFT_CODE  = 21

# ── تدفق الأدمن (state machine عبر user_data) ─────────
ADM_USER_ID           = "adm_user_id"
ADM_BAL_AMOUNT        = "adm_bal_amount"
ADM_PLATFORM_NAME     = "adm_platform_name"
ADM_PLATFORM_EMOJI    = "adm_platform_emoji"
ADM_CAT_NAME          = "adm_cat_name"
ADM_CAT_EMOJI         = "adm_cat_emoji"
ADM_SVC_MARGIN        = "adm_svc_margin"
ADM_SVC_NAME          = "adm_svc_name"
ADM_SVC_DESC          = "adm_svc_desc"
ADM_GIFT_AMOUNT       = "adm_gift_amount"
ADM_GIFT_MAX_USES     = "adm_gift_max_uses"
ADM_FORCED_CH_ADD     = "adm_forced_ch_add"
ADM_NOTIF_CHANNEL     = "adm_notif_channel"
ADM_ORDERS_CHANNEL    = "adm_orders_channel"
ADM_BEP20_ADDR        = "adm_bep20_addr"
ADM_BEP20_MIN         = "adm_bep20_min"
ADM_BEP20_RATE        = "adm_bep20_rate"
ADM_TRC20_ADDR        = "adm_trc20_addr"
ADM_TRC20_KEY         = "adm_trc20_key"
ADM_TRC20_MIN         = "adm_trc20_min"
ADM_TRC20_RATE        = "adm_trc20_rate"
ADM_BROADCAST         = "adm_broadcast"
