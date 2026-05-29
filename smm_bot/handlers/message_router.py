"""
🔀 handlers/message_router.py — موجّه الرسائل المركزي
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import Database

logger = logging.getLogger(__name__)


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    db: Database = context.bot_data["db"]

    if db.is_banned(user.id):
        return

    msg          = update.message
    has_text     = bool(msg.text)
    has_photo    = bool(msg.photo)
    has_video    = bool(msg.video)
    has_document = bool(msg.document)

    # ── 1. Crypto TXID ───────────────────────────────────────
    if has_text:
        for key in ("cph", "ttp", "vah"):
            handler = context.bot_data.get(key)
            if handler and handler.in_session(user.id):
                if await handler.handle_txid_message(msg):
                    return

    # ── 1b. دفع نجوم لفاتورة ويب (successful_payment) ────────
    if msg.successful_payment:
        from handlers.invoice_charge import successful_payment_web_invoice
        if await successful_payment_web_invoice(update, context):
            return

    # ── 1c. مبلغ الفاتورة (إنشاء فاتورة ويب) ─────────────────
    from handlers.invoice_charge import invoice_amount_message_handler
    if await invoice_amount_message_handler(update, context):
        return

    # ── 2. ملف .db (استعادة نسخة احتياطية) ──────────────────
    if has_document:
        from handlers.admin.panel import admin_message_handler
        await admin_message_handler(update, context)
        return

    # ── 3. فودافون كاش (نص + صورة) ──────────────────────────
    from handlers.charge import vodafone_message_handler
    if await vodafone_message_handler(update, context):
        return

    # ── 4. ⭐ نجوم تيليغرام ───────────────────────────────────
    from handlers.stars_binance_pay import stars_amount_message_handler
    if await stars_amount_message_handler(update, context):
        return

    # ── 5. 💛 Binance Pay ─────────────────────────────────────
    from handlers.stars_binance_pay import binance_message_handler
    if await binance_message_handler(update, context):
        return

    # ── 6. رسائل الأدمن (نصوص + صور + فيديو للبرودكاست) ─────
    from handlers.admin.panel import admin_message_handler
    if await admin_message_handler(update, context):
        return

    # ── من هنا نص فقط ─────────────────────────────────────────
    if not has_text:
        return

    # ── 7. شحن الألعاب ───────────────────────────────────────
    from handlers.game_charge import game_message_handler
    if await game_message_handler(update, context):
        return

    # ── 8. تدفق الطلبات ──────────────────────────────────────
    from handlers.order import (
        order_message_handler, track_order_text_handler,
        refill_message_handler, manual_order_message_handler,
    )
    if await refill_message_handler(update, context):
        return
    if await manual_order_message_handler(update, context):
        return
    if await order_message_handler(update, context):
        return
    if await track_order_text_handler(update, context):
        return

    # ── 9. كود الهدية ────────────────────────────────────────
    from handlers.charge import gift_code_message_handler
    if await gift_code_message_handler(update, context):
        return

    # ── 10. الخدمات المجانية ─────────────────────────────────
    from handlers.free_services import free_text_handler, adm_free_text_handler
    if await free_text_handler(update, context):
        return
    if await adm_free_text_handler(update, context):
        return

    # ── 11. الميزات (تذاكر، VIP، حظر خدمات، إعدادات) ────────
    from handlers.features import (
        ticket_message_handler, adm_ticket_reply_handler,
        adm_vip_text_handler, adm_block_svc_text_handler,
        adm_feat_text_handler,
    )
    if await ticket_message_handler(update, context):
        return
    if await adm_ticket_reply_handler(update, context):
        return
    if await adm_vip_text_handler(update, context):
        return
    if await adm_block_svc_text_handler(update, context):
        return
    if await adm_feat_text_handler(update, context):
        return

    logger.debug(f"[ROUTER] رسالة غير معالجة من {user.id}")
