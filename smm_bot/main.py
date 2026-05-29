"""
╔══════════════════════════════════════════════════════════════╗
║           SMM Bot — نقطة الدخول الرئيسية (main.py)         ║
╚══════════════════════════════════════════════════════════════╝
"""

import logging
import shutil
import os
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, filters,
)

import config
from database import Database
from crypto_pay import CryptoPayHandler
from utils.api_client import SMMApiClient

from handlers.start import start_handler, check_sub_callback
from handlers.free_services import register_free_services
from handlers.features import (
    register_features, register_daily_report,
    adm_feat_text_handler, adm_ticket_reply_handler,
    adm_vip_text_handler, adm_block_svc_text_handler,
    ticket_message_handler,
)
from handlers.user_menu import (
    menu_main_callback, smm_platforms_callback,
    platform_callback, category_callback,
    svc_page_callback, service_callback, service_back_callback,
    platform_back_callback, menu_back_callback, my_orders_callback,
    track_order_menu_callback, my_stats_callback,
    bot_instructions_callback, support_link_callback,
    official_channel_callback, orders_channel_btn_callback,
)
from handlers.order import (
    order_svc_callback, order_confirm_callback, order_cancel_callback,
    track_command, refill_svc_callback,
    manual_order_callback, manual_order_confirm_callback,
)
from handlers.charge import (
    my_balance_callback, charge_bep20_callback, charge_trc20_callback,
    charge_vodafone_callback, charge_back_callback, charge_cancel_callback,
    charge_gift_callback, redeem_gift_callback,
    crypto_sent_callback, crypto_copy_callback,
    charge_ton_callback, charge_trx_callback,
    tontrx_sent_callback, tontrx_copy_callback,
)
from handlers.stars_binance_pay import (
    charge_stars_callback,
    pre_checkout_stars, successful_payment_stars,
    charge_binance_callback,
    binance_approve_callback, binance_reject_callback,
)
from handlers.invoice_charge import create_invoice_callback
from handlers.game_charge import (
    game_charge_callback, game_app_callback, game_pkg_callback,
    game_confirm_callback, game_cancel_callback,
    game_approve_callback, game_reject_callback,
)
from handlers.message_router import message_router
from handlers.admin.panel import (
    admin_command, adm_main_callback, adm_stats_callback,
    adm_users_callback, adm_ban_callback, adm_unban_callback,
    adm_add_bal_callback, adm_dec_bal_callback,
    adm_platforms_callback, adm_platform_callback, adm_add_platform_callback,
    adm_tog_platform_callback, adm_del_platform_callback,
    adm_cats_callback, adm_cat_callback, adm_add_cat_callback,
    adm_tog_cat_callback, adm_del_cat_callback,
    adm_svcs_callback, adm_svc_callback, adm_add_svc_callback,
    adm_api_pg_callback, adm_pick_svc_callback,
    adm_tog_svc_callback, adm_del_svc_callback,
    adm_show_add_svc_callback, adm_quick_add_callback,
    adm_global_margin_callback,
    adm_edit_svc_name_callback, adm_edit_svc_price_callback,
    adm_gifts_callback, adm_new_gift_callback, adm_revoke_callback,
    adm_payment_callback, adm_tog_bep20_callback, adm_tog_trc20_callback,
    adm_cfg_bep20_callback, adm_cfg_trc20_callback,
    adm_set_bep20_addr_callback, adm_set_bep20_min_callback, adm_set_bep20_rate_callback,
    adm_set_trc20_key_callback, adm_set_trc20_addr_callback,
    adm_set_trc20_min_callback, adm_set_trc20_rate_callback,
    adm_tog_stars_callback, adm_cfg_stars_callback,
    adm_set_stars_rate_callback, adm_set_stars_min_callback,
    adm_tog_binance_callback, adm_cfg_binance_callback,
    adm_set_binance_id_callback, adm_set_binance_key_callback, adm_set_binance_secret_callback,
    adm_tog_ton_callback, adm_cfg_ton_callback,
    adm_set_ton_addr_callback, adm_set_ton_min_callback,
    adm_tog_trx_callback, adm_cfg_trx_callback,
    adm_set_trx_addr_callback, adm_set_trx_min_callback,
    adm_channels_callback,
    adm_admins_callback, adm_add_admin_callback, adm_del_admin_callback,
    adm_set_checker_ch_callback, adm_set_updates_ch_callback,
    adm_set_notif_ch_callback, adm_set_orders_ch_callback,
    adm_set_official_ch_callback, adm_set_orders_ch_link_callback,
    adm_set_support_callback, adm_set_instructions_callback,
    adm_set_vodafone_callback,
    adm_tog_vod_auto_callback, adm_cfg_vod_auto_callback,
    adm_set_autocash_uid_callback, adm_set_autocash_pid_callback,
    adm_set_vod_min_egp_callback,
    adm_forced_callback, adm_add_forced_callback, adm_del_forced_callback,
    adm_forced_skip_max_callback,
    adm_backup_callback, adm_broadcast_callback, adm_broadcast_send_callback, adm_restore_prompt_callback,
    adm_games_callback, adm_add_game_callback, adm_game_callback,
    adm_tog_game_callback, adm_del_game_callback,
    adm_add_game_pkg_callback, adm_del_game_pkg_callback,
    adm_pending_callback,
    adm_referral_callback, adm_set_ref_pct_callback,
    vod_approve_callback, vod_reject_callback,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def auto_backup_job(context):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"/tmp/auto_backup_{ts}.db"
    try:
        shutil.copy2(config.DATABASE_PATH, dest)
        with open(dest, "rb") as f:
            await context.bot.send_document(
                chat_id=config.ADMIN_ID,
                document=f,
                filename=f"auto_backup_{ts}.db",
                caption=f"🔄 نسخة احتياطية تلقائية — {ts}",
            )
    except Exception as e:
        logger.error(f"[BACKUP] فشل: {e}")
    finally:
        if os.path.exists(dest):
            os.remove(dest)


def register_handlers(app: Application):
    # أوامر
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("track", track_command))

    # القائمة الرئيسية
    app.add_handler(CallbackQueryHandler(menu_main_callback,        pattern="^menu_main$"))
    app.add_handler(CallbackQueryHandler(menu_back_callback,        pattern="^menu_back$"))
    app.add_handler(CallbackQueryHandler(check_sub_callback,        pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(smm_platforms_callback,    pattern="^smm_platforms$"))
    app.add_handler(CallbackQueryHandler(platform_callback,         pattern=r"^platform_\d+$"))
    app.add_handler(CallbackQueryHandler(category_callback,         pattern=r"^category_\d+$"))
    app.add_handler(CallbackQueryHandler(svc_page_callback,         pattern=r"^svc_page_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(service_callback,          pattern=r"^service_\d+$"))
    app.add_handler(CallbackQueryHandler(service_back_callback,     pattern=r"^service_back_\d+$"))
    app.add_handler(CallbackQueryHandler(platform_back_callback,    pattern=r"^platform_back_\d+$"))
    app.add_handler(CallbackQueryHandler(my_orders_callback,        pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(track_order_menu_callback, pattern="^track_order_menu$"))
    app.add_handler(CallbackQueryHandler(my_stats_callback,         pattern="^my_stats$"))
    app.add_handler(CallbackQueryHandler(bot_instructions_callback, pattern="^bot_instructions$"))
    app.add_handler(CallbackQueryHandler(support_link_callback,     pattern="^support_link$"))
    app.add_handler(CallbackQueryHandler(official_channel_callback, pattern="^official_channel$"))
    app.add_handler(CallbackQueryHandler(orders_channel_btn_callback, pattern="^orders_channel_btn$"))

    # شحن الألعاب
    app.add_handler(CallbackQueryHandler(game_charge_callback,  pattern="^game_charge$"))
    app.add_handler(CallbackQueryHandler(game_app_callback,     pattern=r"^game_app_\d+$"))
    app.add_handler(CallbackQueryHandler(game_pkg_callback,     pattern=r"^game_pkg_\d+$"))
    app.add_handler(CallbackQueryHandler(game_confirm_callback, pattern=r"^game_confirm_\d+$"))
    app.add_handler(CallbackQueryHandler(game_cancel_callback,  pattern="^game_cancel$"))
    app.add_handler(CallbackQueryHandler(game_approve_callback, pattern=r"^game_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(game_reject_callback,  pattern=r"^game_reject_\d+$"))

    # الطلبات
    app.add_handler(CallbackQueryHandler(order_svc_callback,    pattern=r"^order_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(order_confirm_callback,pattern="^order_confirm$"))
    app.add_handler(CallbackQueryHandler(order_cancel_callback, pattern="^order_cancel$"))
    app.add_handler(CallbackQueryHandler(refill_svc_callback,   pattern=r"^refill_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(manual_order_callback, pattern=r"^manual_order_\d+$"))
    app.add_handler(CallbackQueryHandler(manual_order_confirm_callback, pattern="^manual_confirm$"))

    # الرصيد والشحن
    app.add_handler(CallbackQueryHandler(my_balance_callback,    pattern="^my_balance$"))
    app.add_handler(CallbackQueryHandler(create_invoice_callback,pattern="^create_invoice$"))
    app.add_handler(CallbackQueryHandler(charge_bep20_callback,  pattern="^charge_bep20$"))
    app.add_handler(CallbackQueryHandler(charge_trc20_callback,  pattern="^charge_trc20$"))
    app.add_handler(CallbackQueryHandler(charge_vodafone_callback,pattern="^charge_vodafone$"))
    app.add_handler(CallbackQueryHandler(charge_back_callback,   pattern="^charge_back$"))
    app.add_handler(CallbackQueryHandler(charge_cancel_callback, pattern="^charge_cancel$"))
    app.add_handler(CallbackQueryHandler(charge_gift_callback,   pattern="^charge_gift$"))
    app.add_handler(CallbackQueryHandler(redeem_gift_callback,   pattern="^redeem_gift$"))
    app.add_handler(CallbackQueryHandler(crypto_sent_callback,   pattern=r"^crypto_sent_(bep20|trc20)$"))
    app.add_handler(CallbackQueryHandler(crypto_copy_callback,   pattern=r"^crypto_copy_(bep20|trc20)$"))

    # فودافون قبول/رفض
    app.add_handler(CallbackQueryHandler(vod_approve_callback, pattern=r"^vod_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(vod_reject_callback,  pattern=r"^vod_reject_\d+$"))

    # الأدمن
    app.add_handler(CallbackQueryHandler(adm_main_callback,   pattern="^adm_main$"))
    app.add_handler(CallbackQueryHandler(adm_stats_callback,  pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(adm_pending_callback,pattern="^adm_pending$"))

    app.add_handler(CallbackQueryHandler(adm_users_callback,   pattern="^adm_users$"))
    app.add_handler(CallbackQueryHandler(adm_ban_callback,     pattern=r"^adm_ban_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_unban_callback,   pattern=r"^adm_unban_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_add_bal_callback, pattern=r"^adm_add_bal_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_dec_bal_callback, pattern=r"^adm_dec_bal_\d+$"))

    app.add_handler(CallbackQueryHandler(adm_platforms_callback,    pattern="^adm_platforms$"))
    app.add_handler(CallbackQueryHandler(adm_platform_callback,     pattern=r"^adm_platform_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_add_platform_callback, pattern="^adm_add_platform$"))
    app.add_handler(CallbackQueryHandler(adm_tog_platform_callback, pattern=r"^adm_tog_platform_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_del_platform_callback, pattern=r"^adm_del_platform_\d+$"))

    app.add_handler(CallbackQueryHandler(adm_cats_callback,    pattern=r"^adm_cats_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_cat_callback,     pattern=r"^adm_cat_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_add_cat_callback, pattern=r"^adm_add_cat_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_tog_cat_callback, pattern=r"^adm_tog_cat_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_del_cat_callback, pattern=r"^adm_del_cat_\d+_\d+$"))

    app.add_handler(CallbackQueryHandler(adm_svcs_callback,           pattern=r"^adm_svcs_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_svc_callback,            pattern=r"^adm_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_add_svc_callback,        pattern=r"^adm_add_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_api_pg_callback,         pattern=r"^adm_api_pg_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_pick_svc_callback,       pattern=r"^adm_pick_svc_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_tog_svc_callback,        pattern=r"^adm_tog_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_del_svc_callback,        pattern=r"^adm_del_svc_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_show_add_svc_callback,   pattern=r"^adm_show_add_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_quick_add_callback,      pattern=r"^adm_quick_add_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_global_margin_callback,  pattern="^adm_global_margin$"))
    app.add_handler(CallbackQueryHandler(adm_edit_svc_name_callback,  pattern=r"^adm_edit_svc_name_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_edit_svc_price_callback, pattern=r"^adm_edit_svc_price_\d+_\d+$"))

    app.add_handler(CallbackQueryHandler(adm_games_callback,        pattern="^adm_games$"))
    app.add_handler(CallbackQueryHandler(adm_add_game_callback,     pattern="^adm_add_game$"))
    app.add_handler(CallbackQueryHandler(adm_game_callback,         pattern=r"^adm_game_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_tog_game_callback,     pattern=r"^adm_tog_game_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_del_game_callback,     pattern=r"^adm_del_game_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_add_game_pkg_callback, pattern=r"^adm_add_game_pkg_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_del_game_pkg_callback, pattern=r"^adm_del_game_pkg_\d+_\d+$"))

    app.add_handler(CallbackQueryHandler(adm_referral_callback,    pattern="^adm_referral$"))
    app.add_handler(CallbackQueryHandler(adm_set_ref_pct_callback, pattern="^adm_set_ref_pct$"))

    app.add_handler(CallbackQueryHandler(adm_gifts_callback,    pattern="^adm_gifts$"))
    app.add_handler(CallbackQueryHandler(adm_new_gift_callback, pattern="^adm_new_gift$"))
    app.add_handler(CallbackQueryHandler(adm_revoke_callback,   pattern=r"^adm_revoke_\S+$"))

    app.add_handler(CallbackQueryHandler(adm_payment_callback,        pattern="^adm_payment$"))
    app.add_handler(CallbackQueryHandler(adm_tog_bep20_callback,      pattern="^adm_tog_bep20$"))
    app.add_handler(CallbackQueryHandler(adm_tog_trc20_callback,      pattern="^adm_tog_trc20$"))
    app.add_handler(CallbackQueryHandler(adm_cfg_bep20_callback,      pattern="^adm_cfg_bep20$"))
    app.add_handler(CallbackQueryHandler(adm_cfg_trc20_callback,      pattern="^adm_cfg_trc20$"))
    app.add_handler(CallbackQueryHandler(adm_set_bep20_addr_callback, pattern="^adm_set_bep20_addr$"))
    app.add_handler(CallbackQueryHandler(adm_set_bep20_min_callback,  pattern="^adm_set_bep20_min$"))
    app.add_handler(CallbackQueryHandler(adm_set_bep20_rate_callback, pattern="^adm_set_bep20_rate$"))
    app.add_handler(CallbackQueryHandler(adm_set_trc20_key_callback,  pattern="^adm_set_trc20_key$"))
    app.add_handler(CallbackQueryHandler(adm_set_trc20_addr_callback, pattern="^adm_set_trc20_addr$"))
    app.add_handler(CallbackQueryHandler(adm_set_trc20_min_callback,  pattern="^adm_set_trc20_min$"))
    app.add_handler(CallbackQueryHandler(adm_set_trc20_rate_callback, pattern="^adm_set_trc20_rate$"))
    # ⭐ Stars
    app.add_handler(CallbackQueryHandler(adm_tog_stars_callback,         pattern="^adm_tog_stars$"))
    app.add_handler(CallbackQueryHandler(adm_cfg_stars_callback,         pattern="^adm_cfg_stars$"))
    app.add_handler(CallbackQueryHandler(adm_set_stars_rate_callback,    pattern="^adm_set_stars_rate$"))
    app.add_handler(CallbackQueryHandler(adm_set_stars_min_callback,     pattern="^adm_set_stars_min$"))
    # 💛 Binance
    app.add_handler(CallbackQueryHandler(adm_tog_binance_callback,       pattern="^adm_tog_binance$"))
    app.add_handler(CallbackQueryHandler(adm_cfg_binance_callback,       pattern="^adm_cfg_binance$"))
    app.add_handler(CallbackQueryHandler(adm_set_binance_id_callback,    pattern="^adm_set_binance_id$"))
    app.add_handler(CallbackQueryHandler(adm_set_binance_key_callback,   pattern="^adm_set_binance_key$"))
    app.add_handler(CallbackQueryHandler(adm_set_binance_secret_callback,pattern="^adm_set_binance_secret$"))
    # Stars user
    app.add_handler(CallbackQueryHandler(charge_stars_callback,  pattern="^charge_stars$"))
    app.add_handler(CallbackQueryHandler(charge_binance_callback,pattern="^charge_binance$"))
    app.add_handler(CallbackQueryHandler(binance_approve_callback,pattern=r"^binance_approve_\S+$"))
    app.add_handler(CallbackQueryHandler(binance_reject_callback, pattern=r"^binance_reject_\S+$"))
    # TON / TRX
    app.add_handler(CallbackQueryHandler(charge_ton_callback,   pattern="^charge_ton$"))
    app.add_handler(CallbackQueryHandler(charge_trx_callback,   pattern="^charge_trx$"))
    app.add_handler(CallbackQueryHandler(tontrx_sent_callback,  pattern=r"^tontrx_sent_(ton|trx)$"))
    app.add_handler(CallbackQueryHandler(tontrx_copy_callback,  pattern=r"^tontrx_copy_(ton|trx)$"))
    # Admin TON/TRX
    app.add_handler(CallbackQueryHandler(adm_tog_ton_callback,      pattern="^adm_tog_ton$"))
    app.add_handler(CallbackQueryHandler(adm_cfg_ton_callback,      pattern="^adm_cfg_ton$"))
    app.add_handler(CallbackQueryHandler(adm_set_ton_addr_callback, pattern="^adm_set_ton_addr$"))
    app.add_handler(CallbackQueryHandler(adm_set_ton_min_callback,  pattern="^adm_set_ton_min$"))
    app.add_handler(CallbackQueryHandler(adm_tog_trx_callback,      pattern="^adm_tog_trx$"))
    app.add_handler(CallbackQueryHandler(adm_cfg_trx_callback,      pattern="^adm_cfg_trx$"))
    app.add_handler(CallbackQueryHandler(adm_set_trx_addr_callback, pattern="^adm_set_trx_addr$"))
    app.add_handler(CallbackQueryHandler(adm_set_trx_min_callback,  pattern="^adm_set_trx_min$"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_stars))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_stars))
    app.add_handler(CallbackQueryHandler(adm_set_vodafone_callback,    pattern="^adm_set_vodafone$"))
    # فودافون كاش التلقائي (autocash)
    app.add_handler(CallbackQueryHandler(adm_tog_vod_auto_callback,       pattern="^adm_tog_vod_auto$"))
    app.add_handler(CallbackQueryHandler(adm_cfg_vod_auto_callback,       pattern="^adm_cfg_vod_auto$"))
    app.add_handler(CallbackQueryHandler(adm_set_autocash_uid_callback,   pattern="^adm_set_autocash_uid$"))
    app.add_handler(CallbackQueryHandler(adm_set_autocash_pid_callback,   pattern="^adm_set_autocash_pid$"))
    app.add_handler(CallbackQueryHandler(adm_set_vod_min_egp_callback,    pattern="^adm_set_vod_min_egp$"))

    app.add_handler(CallbackQueryHandler(adm_channels_callback,           pattern="^adm_channels$"))
    app.add_handler(CallbackQueryHandler(adm_set_checker_ch_callback,    pattern="^adm_set_checker_ch$"))
    app.add_handler(CallbackQueryHandler(adm_set_updates_ch_callback,    pattern="^adm_set_updates_ch$"))
    app.add_handler(CallbackQueryHandler(adm_admins_callback,            pattern="^adm_admins$"))
    app.add_handler(CallbackQueryHandler(adm_add_admin_callback,         pattern="^adm_add_admin$"))
    app.add_handler(CallbackQueryHandler(adm_del_admin_callback,         pattern=r"^adm_del_admin_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_set_notif_ch_callback,       pattern="^adm_set_notif_ch$"))
    app.add_handler(CallbackQueryHandler(adm_set_orders_ch_callback,      pattern="^adm_set_orders_ch$"))
    app.add_handler(CallbackQueryHandler(adm_set_official_ch_callback,    pattern="^adm_set_official_ch$"))
    app.add_handler(CallbackQueryHandler(adm_set_orders_ch_link_callback, pattern="^adm_set_orders_ch_link$"))
    app.add_handler(CallbackQueryHandler(adm_set_support_callback,        pattern="^adm_set_support$"))
    app.add_handler(CallbackQueryHandler(adm_set_instructions_callback,   pattern="^adm_set_instructions$"))

    app.add_handler(CallbackQueryHandler(adm_forced_callback,          pattern="^adm_forced$"))
    app.add_handler(CallbackQueryHandler(adm_add_forced_callback,      pattern="^adm_add_forced$"))
    app.add_handler(CallbackQueryHandler(adm_del_forced_callback,      pattern=r"^adm_del_forced_\S+$"))
    app.add_handler(CallbackQueryHandler(adm_forced_skip_max_callback, pattern="^adm_forced_skip_max$"))

    app.add_handler(CallbackQueryHandler(adm_backup_callback,       pattern="^adm_backup$"))
    app.add_handler(CallbackQueryHandler(adm_broadcast_callback,      pattern="^adm_broadcast$"))
    app.add_handler(CallbackQueryHandler(adm_broadcast_send_callback,  pattern="^adm_broadcast_send$"))
    app.add_handler(CallbackQueryHandler(adm_restore_prompt_callback,pattern="^adm_restore_prompt$"))

    app.add_handler(CallbackQueryHandler(adm_platforms_callback, pattern="^adm_services_home$"))

    # الخدمات المجانية
    register_free_services(app, lambda uid: uid == config.ADMIN_ID)
    register_features(app)

    # موجّه الرسائل (الأخير) — نصوص + صور
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
        message_router,
    ))
    # ملفات (لاستعادة قاعدة البيانات)
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, message_router))


def main():
    os.makedirs("data", exist_ok=True)

    db  = Database(config.DATABASE_PATH)
    api = SMMApiClient(config.SMM_API_URL, config.SMM_API_KEY)
    app = Application.builder().token(config.BOT_TOKEN).build()
    cph = CryptoPayHandler(db=db, bot=app.bot)

    from ton_trx_pay import TonTrxPayHandler
    ttp = TonTrxPayHandler(db=db, bot=app.bot)

    from vodafone_auto import VodafoneAutoHandler
    vah = VodafoneAutoHandler(db=db, bot=app.bot)

    app.bot_data["db"]  = db
    app.bot_data["api"] = api
    app.bot_data["cph"] = cph
    app.bot_data["ttp"] = ttp
    app.bot_data["vah"] = vah

    register_handlers(app)

    if app.job_queue:
        app.job_queue.run_repeating(
            auto_backup_job,
            interval=config.BACKUP_INTERVAL,
            first=config.BACKUP_INTERVAL,
        )
        # ── تتبع الطلبات والاسترداد التلقائي ──
        from order_checker import register_order_checker
        register_order_checker(app, db, api, interval_minutes=10)
        # ── مزامنة أسعار الخدمات ──
        from service_sync import register_service_sync
        register_service_sync(app, interval_minutes=30)
        # ── التقرير اليومي ──
        hour = db.get_daily_report_hour()
        register_daily_report(app, db, hour=hour)

    logger.info("🚀 البوت يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()

