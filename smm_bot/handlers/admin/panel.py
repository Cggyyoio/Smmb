from utils.safe_send import safe_answer, safe_edit, safe_send
"""
👑 لوحة الأدمن الكاملة — handlers/admin/panel.py
"""

import logging
import os
import shutil
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import Database
from utils.api_client import SMMApiClient
from utils.keyboards import (
    admin_main_kb, admin_user_actions_kb, admin_platforms_kb,
    admin_platform_actions_kb, admin_categories_kb, admin_cat_actions_kb,
    admin_services_kb, admin_svc_actions_kb, admin_api_services_kb,
    admin_quick_add_svc_kb,
    admin_gifts_kb, admin_payment_kb, admin_bep20_cfg_kb, admin_trc20_cfg_kb,
    admin_vod_auto_cfg_kb,
    admin_stars_cfg_kb, admin_binance_cfg_kb, admin_approve_binance_kb,
    admin_ton_cfg_kb, admin_trx_cfg_kb,
    admin_channels_kb, admin_forced_kb, admin_admins_kb,
    skip_kb, back_to_main_kb, cancel_kb
)

logger = logging.getLogger(__name__)


def is_admin(user_id: int, db: Database = None) -> bool:
    """الأدمن الرئيسي أو أي أدمن فرعي مضاف في DB."""
    if user_id == ADMIN_ID:
        return True
    if db is not None:
        return db.is_sub_admin(user_id)
    return False


def is_super_admin(user_id: int) -> bool:
    """الأدمن الرئيسي فقط — للعمليات الحساسة (إضافة/حذف أدمنز)."""
    return user_id == ADMIN_ID


def _guard(func):
    """ديكوراتور التحقق من صلاحية الأدمن (رئيسي أو فرعي)."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        db: Database = context.bot_data.get("db")
        if not is_admin(uid, db):
            if update.callback_query:
                await update.callback_query.answer("🚫 غير مصرح!", show_alert=True)
            return
        return await func(update, context)
    return wrapper


# ══════════════════════════════════════════════════════════
#  /admin — الدخول للوحة
# ══════════════════════════════════════════════════════════

@_guard
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db: Database = context.bot_data["db"]
    stats = db.get_stats()
    text = (
        "👑 <b>لوحة التحكم</b>\n\n"
        f"👥 المستخدمون: <b>{stats['users']}</b>\n"
        f"📦 الطلبات:    <b>{stats['orders']}</b>\n"
        f"💰 الإيرادات:  <b>${stats['revenue']:.2f}</b>\n"
        f"🛠 الخدمات:   <b>{stats['services']}</b>\n"
        f"📱 المنصات:   <b>{stats['platforms']}</b>"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=admin_main_kb(), parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=admin_main_kb(), parse_mode="HTML")


@_guard
async def adm_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.states import clear_all_states
    clear_all_states(context)
    await admin_command(update, context)


# ══════════════════════════════════════════════════════════
#  إحصائيات
# ══════════════════════════════════════════════════════════

@_guard
async def adm_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    stats = db.get_stats()
    await safe_edit(query, 
        f"📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 إجمالي المستخدمين: <b>{stats['users']}</b>\n"
        f"📦 إجمالي الطلبات:    <b>{stats['orders']}</b>\n"
        f"💰 إجمالي الإيرادات: <b>${stats['revenue']:.2f}</b>\n"
        f"💳 مجموع أرصدة المستخدمين: <b>${stats['total_balance']:.4f}</b>\n"
        f"🛠 الخدمات النشطة:   <b>{stats['services']}</b>\n"
        f"📱 المنصات النشطة:   <b>{stats['platforms']}</b>",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  إدارة المستخدمين
# ══════════════════════════════════════════════════════════

@_guard
async def adm_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    context.user_data["adm_state"] = "waiting_user_id"
    await safe_edit(query, 
        "👥 <b>إدارة المستخدمين</b>\n\nأرسل ID المستخدم:",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


@_guard
async def adm_ban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = int(query.data.split("_")[2])
    db.ban_user(uid, True)
    await safe_edit(query, 
        f"🚫 تم حظر المستخدم <code>{uid}</code>.",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


@_guard
async def adm_unban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    uid = int(query.data.split("_")[2])
    db.ban_user(uid, False)
    await safe_edit(query, 
        f"✅ تم فك حظر المستخدم <code>{uid}</code>.",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


@_guard
async def adm_add_bal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    uid = int(query.data.split("_")[3])
    context.user_data["adm_state"]   = "waiting_add_bal"
    context.user_data["adm_target"]  = uid
    await safe_edit(query, 
        f"➕ إضافة رصيد للمستخدم <code>{uid}</code>\n\nأرسل المبلغ ($):",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


@_guard
async def adm_dec_bal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    uid = int(query.data.split("_")[3])
    context.user_data["adm_state"]  = "waiting_dec_bal"
    context.user_data["adm_target"] = uid
    await safe_edit(query, 
        f"➖ خصم رصيد من المستخدم <code>{uid}</code>\n\nأرسل المبلغ ($):",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  إدارة المنصات
# ══════════════════════════════════════════════════════════

@_guard
async def adm_platforms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    platforms = db.get_platforms(active_only=False)
    await safe_edit(query, 
        "📱 <b>إدارة المنصات</b>",
        reply_markup=admin_platforms_kb(platforms),
        parse_mode="HTML",
    )


@_guard
async def adm_platform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    pid = int(query.data.split("_")[2])
    p = db.get_platform(pid)
    if not p:
        await safe_answer(query, "غير موجود!", show_alert=True)
        return
    await safe_edit(query, 
        f"📱 منصة: <b>{p['emoji']} {p['name']}</b>\n"
        f"الحالة: {'✅ نشطة' if p['is_active'] else '❌ مخفية'}",
        reply_markup=admin_platform_actions_kb(pid, p["is_active"]),
        parse_mode="HTML",
    )


@_guard
async def adm_add_platform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    context.user_data["adm_state"] = "waiting_platform_emoji"
    await safe_edit(query, 
        "📱 <b>إضافة منصة جديدة</b>\n\nأرسل الإيموجي أولاً (مثل: 📸):",
        reply_markup=cancel_kb("adm_platforms"),
        parse_mode="HTML",
    )


@_guard
async def adm_tog_platform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    pid = int(query.data.split("_")[3])
    p = db.get_platform(pid)
    db.toggle_platform(pid, not p["is_active"])
    await adm_platforms_callback(update, context)


@_guard
async def adm_del_platform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    pid = int(query.data.split("_")[3])
    db.delete_platform(pid)
    await adm_platforms_callback(update, context)


# ══════════════════════════════════════════════════════════
#  إدارة الفئات
# ══════════════════════════════════════════════════════════

@_guard
async def adm_cats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    pid = int(query.data.split("_")[2])
    cats = db.get_categories(pid, active_only=False)
    p    = db.get_platform(pid)
    await safe_edit(query, 
        f"📂 فئات منصة <b>{p['emoji']} {p['name']}</b>:",
        reply_markup=admin_categories_kb(pid, cats),
        parse_mode="HTML",
    )


@_guard
async def adm_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    cid = int(query.data.split("_")[2])
    cat = db.get_category(cid)
    if not cat:
        await safe_answer(query, "غير موجود!", show_alert=True)
        return
    await safe_edit(query, 
        f"📂 فئة: <b>{cat['emoji']} {cat['name']}</b>\n"
        f"الحالة: {'✅ نشطة' if cat['is_active'] else '❌ مخفية'}",
        reply_markup=admin_cat_actions_kb(cid, cat["is_active"], cat["platform_id"]),
        parse_mode="HTML",
    )


@_guard
async def adm_add_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    pid = int(query.data.split("_")[3])
    context.user_data["adm_state"]   = "waiting_cat_emoji"
    context.user_data["adm_platform"] = pid
    await safe_edit(query, 
        "📂 <b>إضافة فئة جديدة</b>\n\nأرسل الإيموجي (مثل: 👁):",
        reply_markup=cancel_kb(f"adm_cats_{pid}"),
        parse_mode="HTML",
    )


@_guard
async def adm_tog_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    cid = int(query.data.split("_")[4])
    cat = db.get_category(cid)
    db.toggle_category(cid, not cat["is_active"])
    await adm_cat_callback(update, context)


@_guard
async def adm_del_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    parts = query.data.split("_")
    cid, pid = int(parts[3]), int(parts[4])
    db.delete_category(cid)
    cats = db.get_categories(pid, active_only=False)
    p    = db.get_platform(pid)
    await safe_edit(query, 
        f"📂 فئات منصة <b>{p['emoji']} {p['name']}</b>:",
        reply_markup=admin_categories_kb(pid, cats),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  إدارة الخدمات
# ══════════════════════════════════════════════════════════

@_guard
async def adm_svcs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    cid      = int(query.data.split("_")[2])
    services = db.get_services(cid, active_only=False)
    cat      = db.get_category(cid)
    await safe_edit(query, 
        f"🛠 خدمات فئة <b>{cat['emoji']} {cat['name']}</b>:",
        reply_markup=admin_services_kb(cid, services),
        parse_mode="HTML",
    )


@_guard
async def adm_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    sid = int(query.data.split("_")[2])
    svc = db.get_service(sid)
    if not svc:
        await safe_answer(query, "غير موجود!", show_alert=True)
        return
    await safe_edit(query, 
        f"🛠 <b>{svc['name']}</b>\n"
        f"السعر/1000: ${svc['price_per_1000']:.4f}\n"
        f"الحالة: {'✅' if svc['is_active'] else '❌'}",
        reply_markup=admin_svc_actions_kb(sid, svc["is_active"], svc["category_id"]),
        parse_mode="HTML",
    )


@_guard
async def adm_add_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تدفق إضافة خدمة جديدة — يجلب قائمة API."""
    query = update.callback_query
    await safe_answer(query, "⏳ جارٍ جلب خدمات API...")
    cid = int(query.data.split("_")[4])
    api: SMMApiClient = context.bot_data["api"]
    services = await api.get_services()

    if not services:
        await safe_edit(query, 
            "❌ تعذّر جلب خدمات API. تحقق من الإعدادات.",
            reply_markup=cancel_kb(f"adm_svcs_{cid}"),
        )
        return

    context.user_data["adm_state"]    = "picking_api_svc"
    context.user_data["adm_cat_id"]   = cid
    context.user_data["adm_api_svcs"] = services

    await safe_edit(query, 
        f"🛠 <b>اختر الخدمة من API</b> (الفئة #{cid}):\n"
        f"({len(services)} خدمة متاحة)",
        reply_markup=admin_api_services_kb(services, cid, page=0),
        parse_mode="HTML",
    )

@_guard
async def adm_show_add_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض خيار إضافة خدمة: بـ ID مباشرة أو تصفح."""
    query = update.callback_query
    await safe_answer(query)
    cid = int(query.data.split("_")[4])
    context.user_data["adm_cat_id"] = cid
    await safe_edit(query, 
        "🛠 <b>إضافة خدمة جديدة</b>\n\nكيف تريد الإضافة؟",
        reply_markup=admin_quick_add_svc_kb(cid),
        parse_mode="HTML",
    )


@_guard
async def adm_quick_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة خدمة بـ API ID مباشرة."""
    query = update.callback_query
    await safe_answer(query)
    cid = int(query.data.split("_")[3])
    context.user_data["adm_state"]  = "waiting_quick_svc_id"
    context.user_data["adm_cat_id"] = cid
    await safe_edit(query, 
        "🔢 <b>إضافة خدمة بـ ID</b>\n\n"
        "أرسل <b>رقم ID الخدمة</b> من API مباشرة:\n"
        "(مثال: 1234)",
        reply_markup=cancel_kb(f"adm_svcs_{cid}"),
        parse_mode="HTML",
    )


@_guard
async def adm_global_margin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغيير نسبة الربح لجميع الخدمات."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    total = db.get_services_count()
    context.user_data["adm_state"] = "waiting_global_margin"
    await safe_edit(query, 
        f"📈 <b>تغيير نسبة الربح الشاملة</b>\n\n"
        f"عدد الخدمات الحالية: <b>{total}</b>\n\n"
        f"⚠️ سيتم إعادة حساب سعر كل الخدمات بناءً على السعر الأصلي من API.\n\n"
        f"أرسل <b>نسبة الربح الجديدة %</b> (مثال: 30 = 30%):",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


@_guard
async def adm_edit_svc_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل اسم خدمة."""
    query = update.callback_query
    await safe_answer(query)
    parts = query.data.split("_")
    sid, cid = int(parts[4]), int(parts[5])
    db: Database = context.bot_data["db"]
    svc = db.get_service(sid)
    context.user_data["adm_state"]      = "waiting_edit_svc_name"
    context.user_data["adm_edit_svc_id"] = sid
    context.user_data["adm_cat_id"]     = cid
    await safe_edit(query, 
        f"✏️ <b>تعديل اسم الخدمة</b>\n\n"
        f"الاسم الحالي: <b>{svc['name']}</b>\n\n"
        f"أرسل الاسم الجديد:",
        reply_markup=cancel_kb(f"adm_svcs_{cid}"),
        parse_mode="HTML",
    )


@_guard
async def adm_edit_svc_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل سعر خدمة."""
    query = update.callback_query
    await safe_answer(query)
    parts = query.data.split("_")
    sid, cid = int(parts[4]), int(parts[5])
    db: Database = context.bot_data["db"]
    svc = db.get_service(sid)
    context.user_data["adm_state"]       = "waiting_edit_svc_price"
    context.user_data["adm_edit_svc_id"] = sid
    context.user_data["adm_cat_id"]      = cid
    await safe_edit(query, 
        f"💲 <b>تعديل سعر الخدمة</b>\n\n"
        f"الخدمة: <b>{svc['name']}</b>\n"
        f"السعر الحالي: <b>${svc['price_per_1000']:.4f}</b>/1000\n\n"
        f"أرسل السعر الجديد لكل 1000 (بالدولار):",
        reply_markup=cancel_kb(f"adm_svcs_{cid}"),
        parse_mode="HTML",
    )


@_guard
async def adm_api_pg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تصفح صفحات قائمة API."""
    query = update.callback_query
    await safe_answer(query)
    parts = query.data.split("_")
    cid, page = int(parts[3]), int(parts[4])
    services = context.user_data.get("adm_api_svcs", [])
    await safe_edit(query, 
        f"🛠 <b>اختر الخدمة من API</b>\n({len(services)} خدمة):",
        reply_markup=admin_api_services_kb(services, cid, page=page),
        parse_mode="HTML",
    )


@_guard
async def adm_pick_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار خدمة API محددة → طلب نسبة الربح."""
    query = update.callback_query
    await safe_answer(query)
    parts      = query.data.split("_")
    cid        = int(parts[3])
    api_svc_id = int(parts[4])
    services   = context.user_data.get("adm_api_svcs", [])

    picked = next((s for s in services if int(s["service"]) == api_svc_id), None)
    if not picked:
        await safe_answer(query, "لم يُعثر على الخدمة!", show_alert=True)
        return

    context.user_data["adm_state"]      = "waiting_svc_margin"
    context.user_data["adm_cat_id"]     = cid
    context.user_data["adm_picked_svc"] = picked

    await safe_edit(query, 
        f"📌 الخدمة المختارة:\n<b>{picked['name']}</b>\n"
        f"السعر الأصلي: ${float(picked.get('rate', 0)):.4f} / 1000\n\n"
        f"أرسل <b>نسبة الربح %</b> (مثلاً 30 = 30%):",
        reply_markup=cancel_kb(f"adm_svcs_{cid}"),
        parse_mode="HTML",
    )


@_guard
async def adm_tog_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    sid = int(query.data.split("_")[3])
    svc = db.get_service(sid)
    db.toggle_service(sid, not svc["is_active"])
    await adm_svc_callback(update, context)


@_guard
async def adm_del_svc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    parts = query.data.split("_")
    sid, cid = int(parts[3]), int(parts[4])

    # نجيب بيانات الخدمة قبل الحذف للإشعار
    svc = db.get_service(sid)
    db.delete_service(sid)

    # ── إشعار قناة تحديثات الخدمات ──────────────────────
    if svc:
        updates_ch = db.get_setting("updates_channel", "").strip()
        if updates_ch:
            try:
                cat  = db.get_category(svc["category_id"]) or {}
                plat = db.get_platform(cat.get("platform_id", 0)) or {}
                cat_label  = f"{cat.get('emoji','')} {cat.get('name','')}".strip()
                plat_label = f"{plat.get('emoji','')} {plat.get('name','')}".strip()
                await context.bot.send_message(
                    chat_id=updates_ch,
                    text=(
                        f"🗑️ <b>خدمة تم إزالتها</b>\n\n"
                        f"🏷️ الاسم: {svc['name']}\n"
                        f"📱 المنصة: {plat_label or '—'}\n"
                        f"📂 القسم: {cat_label or '—'}"
                    ),
                    parse_mode="HTML",
                )
            except Exception as _e:
                logger.warning(f"[UPDATES CH] فشل إشعار الحذف: {_e}")
    # ─────────────────────────────────────────────────────

    services = db.get_services(cid, active_only=False)
    cat = db.get_category(cid)
    await safe_edit(query, 
        f"🛠 خدمات فئة <b>{cat['emoji']} {cat['name']}</b>:",
        reply_markup=admin_services_kb(cid, services),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  أكواد الهدايا
# ══════════════════════════════════════════════════════════

@_guard
async def adm_gifts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    codes = db.get_active_gift_codes()
    await safe_edit(query, 
        f"🎁 <b>أكواد الهدايا النشطة</b> ({len(codes)}):",
        reply_markup=admin_gifts_kb(codes),
        parse_mode="HTML",
    )


@_guard
async def adm_new_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    context.user_data["adm_state"] = "waiting_gift_amount"
    await safe_edit(query, 
        "🎁 <b>إنشاء كود هدية</b>\n\nأرسل المبلغ بالدولار (مثل: 5.00):",
        reply_markup=cancel_kb("adm_gifts"),
        parse_mode="HTML",
    )


@_guard
async def adm_revoke_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    code = query.data.split("_")[2]
    db.deactivate_gift_code(code)
    await safe_answer(query, f"✅ تم إلغاء الكود {code}", show_alert=True)
    await adm_gifts_callback(update, context)


# ══════════════════════════════════════════════════════════
#  إعدادات الدفع
# ══════════════════════════════════════════════════════════

@_guard
async def adm_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    from ton_trx_pay import TonTrxPayHandler
    ttp: TonTrxPayHandler = context.bot_data["ttp"]
    bep20_on   = db.get_setting("pay_bep20",   "0") == "1"
    trc20_on   = db.get_setting("pay_trc20",   "0") == "1"
    stars_on   = db.get_setting("pay_stars",   "0") == "1"
    binance_on = db.get_setting("pay_binance", "0") == "1"
    ton_on     = ttp.is_ton_enabled()
    trx_on     = ttp.is_trx_enabled()
@_guard
async def adm_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    from ton_trx_pay import TonTrxPayHandler
    ttp: TonTrxPayHandler = context.bot_data["ttp"]
    bep20_on    = db.get_setting("pay_bep20",         "0") == "1"
    trc20_on    = db.get_setting("pay_trc20",         "0") == "1"
    stars_on    = db.get_setting("pay_stars",         "0") == "1"
    binance_on  = db.get_setting("pay_binance",       "0") == "1"
    ton_on      = ttp.is_ton_enabled()
    trx_on      = ttp.is_trx_enabled()
    vod_auto_on = db.get_setting("pay_vodafone_auto", "0") == "1"
    await safe_edit(query, 
        "💳 <b>إعدادات طرق الدفع</b>",
        reply_markup=admin_payment_kb(
            bep20_on, trc20_on, stars_on, binance_on,
            ton_on, trx_on, vod_auto_on,
        ),
        parse_mode="HTML",
    )


@_guard
async def adm_tog_bep20_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    cur = db.get_setting("pay_bep20", "0")
    db.set_setting("pay_bep20", "0" if cur == "1" else "1")
    await adm_payment_callback(update, context)


@_guard
async def adm_tog_trc20_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    cur = db.get_setting("pay_trc20", "0")
    db.set_setting("pay_trc20", "0" if cur == "1" else "1")
    await adm_payment_callback(update, context)


@_guard
async def adm_cfg_bep20_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    addr = db.get_setting("bep20_address", "—")
    mn   = db.get_setting("bep20_min_usdt", "1")
    rt   = db.get_setting("bep20_usdt_rate", "1")
    await safe_edit(query, 
        f"💎 <b>إعدادات BEP20</b>\n\n"
        f"📍 العنوان: <code>{addr}</code>\n"
        f"💵 الحد الأدنى: {mn} USDT\n"
        f"💱 سعر الصرف: {rt}",
        reply_markup=admin_bep20_cfg_kb(),
        parse_mode="HTML",
    )


@_guard
async def adm_cfg_trc20_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    addr = db.get_setting("trc20_address", "—")
    mn   = db.get_setting("trc20_min_usdt", "1")
    rt   = db.get_setting("trc20_usdt_rate", "1")
    await safe_edit(query, 
        f"🟣 <b>إعدادات TRC20</b>\n\n"
        f"📍 العنوان: <code>{addr}</code>\n"
        f"💵 الحد الأدنى: {mn} USDT\n"
        f"💱 سعر الصرف: {rt}",
        reply_markup=admin_trc20_cfg_kb(),
        parse_mode="HTML",
    )


def _set_adm_state(context, state, **extra):
    context.user_data["adm_state"] = state
    for k, v in extra.items():
        context.user_data[k] = v


@_guard
async def adm_set_bep20_addr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_bep20_addr")
    await q.edit_message_text("📍 أرسل عنوان محفظة BEP20:", reply_markup=cancel_kb("adm_cfg_bep20"))


@_guard
async def adm_set_bep20_min_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_bep20_min")
    await q.edit_message_text("💵 أرسل الحد الأدنى (USDT):", reply_markup=cancel_kb("adm_cfg_bep20"))


@_guard
async def adm_set_bep20_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_bep20_rate")
    await q.edit_message_text("💱 أرسل سعر الصرف (1 USDT = ?):", reply_markup=cancel_kb("adm_cfg_bep20"))


@_guard
async def adm_set_trc20_key_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_trc20_key")
    await q.edit_message_text("🔑 أرسل TronGrid API Key:", reply_markup=cancel_kb("adm_cfg_trc20"))


@_guard
async def adm_set_trc20_addr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_trc20_addr")
    await q.edit_message_text("📍 أرسل عنوان محفظة TRC20:", reply_markup=cancel_kb("adm_cfg_trc20"))


@_guard
async def adm_set_trc20_min_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_trc20_min")
    await q.edit_message_text("💵 أرسل الحد الأدنى (USDT):", reply_markup=cancel_kb("adm_cfg_trc20"))


@_guard
async def adm_set_trc20_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_trc20_rate")
    await q.edit_message_text("💱 أرسل سعر الصرف (1 USDT = ?):", reply_markup=cancel_kb("adm_cfg_trc20"))


# ── نجوم تيليغرام ──────────────────────────────────────────

@_guard
async def adm_tog_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    cur = db.get_setting("pay_stars", "0")
    db.set_setting("pay_stars", "0" if cur == "1" else "1")
    await adm_payment_callback(update, context)


@_guard
async def adm_cfg_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    rate    = db.get_setting("stars_per_dollar", "85")
    min_usd = db.get_setting("stars_min_usd",    "1")
    from utils.keyboards import admin_stars_cfg_kb
    await q.edit_message_text(
        f"⭐ <b>إعدادات نجوم تيليغرام</b>\n\n"
        f"💱 سعر الصرف الحالي: <b>{rate} نجمة = $1</b>\n"
        f"📉 الحد الأدنى للشحن: <b>${min_usd}</b>",
        reply_markup=admin_stars_cfg_kb(rate, min_usd),
        parse_mode="HTML",
    )


@_guard
async def adm_set_stars_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_stars_rate")
    await q.edit_message_text(
        "⭐ أرسل عدد النجوم مقابل $1\nمثال: <code>85</code>",
        reply_markup=cancel_kb("adm_cfg_stars"),
        parse_mode="HTML",
    )


@_guard
async def adm_set_stars_min_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_stars_min")
    await q.edit_message_text(
        "📉 أرسل الحد الأدنى للشحن بالدولار\nمثال: <code>1</code> أو <code>0.5</code>",
        reply_markup=cancel_kb("adm_cfg_stars"),
        parse_mode="HTML",
    )


# ── Binance Pay ─────────────────────────────────────────────

@_guard
async def adm_tog_binance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    cur = db.get_setting("pay_binance", "0")
    db.set_setting("pay_binance", "0" if cur == "1" else "1")
    await adm_payment_callback(update, context)


@_guard
async def adm_cfg_binance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    pay_id  = db.get_setting("binance_pay_id",     "غير محدد")
    api_key = db.get_setting("binance_api_key",    "")
    api_sec = db.get_setting("binance_api_secret", "")
    has_api = bool(api_key and api_sec)
    from utils.keyboards import admin_binance_cfg_kb
    await q.edit_message_text(
        f"💛 <b>إعدادات Binance Pay</b>\n\n"
        f"🆔 Pay ID: <code>{pay_id}</code>\n"
        f"🔑 API: {'✅ مضبوط (تحقق تلقائي)' if has_api else '⚠️ غير مضبوط (مراجعة يدوية)'}",
        reply_markup=admin_binance_cfg_kb(pay_id, has_api),
        parse_mode="HTML",
    )


@_guard
async def adm_set_binance_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_binance_id")
    await q.edit_message_text(
        "🆔 أرسل Binance Pay ID الخاص بك:",
        reply_markup=cancel_kb("adm_cfg_binance"),
    )


@_guard
async def adm_set_binance_key_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_binance_key")
    await q.edit_message_text(
        "🔑 أرسل Binance API Key:",
        reply_markup=cancel_kb("adm_cfg_binance"),
    )


@_guard
async def adm_set_binance_secret_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_binance_secret")
    await q.edit_message_text(
        "🔐 أرسل Binance API Secret:",
        reply_markup=cancel_kb("adm_cfg_binance"),
    )


# ── TON ─────────────────────────────────────────────────────

@_guard
async def adm_tog_ton_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    cur = db.get_setting("pay_ton", "0")
    db.set_setting("pay_ton", "0" if cur == "1" else "1")
    await adm_payment_callback(update, context)


@_guard
async def adm_cfg_ton_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    addr  = db.get_setting("ton_address",    "")
    min_a = db.get_setting("ton_min_amount", "1")
    await q.edit_message_text(
        f"💎 <b>إعدادات TON</b>\n\n"
        f"📍 العنوان: <code>{addr or 'غير محدد'}</code>\n"
        f"📉 الحد الأدنى: <b>{min_a} TON</b>\n\n"
        f"💡 سعر الصرف يُجلب تلقائياً من CoinGecko",
        reply_markup=admin_ton_cfg_kb(addr, min_a),
        parse_mode="HTML",
    )


@_guard
async def adm_set_ton_addr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_ton_addr")
    await q.edit_message_text(
        "📍 أرسل عنوان محفظة TON:\nمثال: <code>EQD...xyz</code>",
        reply_markup=cancel_kb("adm_cfg_ton"),
        parse_mode="HTML",
    )


@_guard
async def adm_set_ton_min_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_ton_min")
    await q.edit_message_text(
        "📉 أرسل الحد الأدنى للشحن بـ TON:\nمثال: <code>1</code> أو <code>0.5</code>",
        reply_markup=cancel_kb("adm_cfg_ton"),
        parse_mode="HTML",
    )


# ── TRX ─────────────────────────────────────────────────────

@_guard
async def adm_tog_trx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    cur = db.get_setting("pay_trx", "0")
    db.set_setting("pay_trx", "0" if cur == "1" else "1")
    await adm_payment_callback(update, context)


@_guard
async def adm_cfg_trx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db: Database = context.bot_data["db"]
    addr  = db.get_setting("trx_address",    "")
    min_a = db.get_setting("trx_min_amount", "10")
    await q.edit_message_text(
        f"🔴 <b>إعدادات TRX</b>\n\n"
        f"📍 العنوان: <code>{addr or 'غير محدد'}</code>\n"
        f"📉 الحد الأدنى: <b>{min_a} TRX</b>\n\n"
        f"💡 سعر الصرف يُجلب تلقائياً من CoinGecko",
        reply_markup=admin_trx_cfg_kb(addr, min_a),
        parse_mode="HTML",
    )


@_guard
async def adm_set_trx_addr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_trx_addr")
    await q.edit_message_text(
        "📍 أرسل عنوان محفظة TRX:\nمثال: <code>TXyz...abc</code>",
        reply_markup=cancel_kb("adm_cfg_trx"),
        parse_mode="HTML",
    )


@_guard
async def adm_set_trx_min_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_trx_min")
    await q.edit_message_text(
        "📉 أرسل الحد الأدنى للشحن بـ TRX:\nمثال: <code>10</code>",
        reply_markup=cancel_kb("adm_cfg_trx"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  الطلبات المعلقة
# ══════════════════════════════════════════════════════════

@_guard
async def adm_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]

    vod_pending  = db.get_pending_vodafone_charges()
    game_pending = db.get_pending_game_orders()

    lines = ["📋 <b>الطلبات المعلقة</b>\n"]

    if vod_pending:
        lines.append("📱 <b>فودافون كاش:</b>")
        for c in vod_pending[:10]:
            lines.append(f"  🔹 #{c['id']} | ${c['amount']:.2f} | <code>{c['user_tg_id']}</code> | {c['created_at'][:16]}")
    else:
        lines.append("📱 فودافون: لا توجد طلبات معلقة")

    lines.append("")

    if game_pending:
        lines.append("🎮 <b>شحن ألعاب:</b>")
        for o in game_pending[:10]:
            lines.append(f"  🔹 #{o['id']} | {o.get('app_emoji','')} {o.get('app_name','')} | {o.get('pkg_name','')} | <code>{o['user_tg_id']}</code>")
    else:
        lines.append("🎮 ألعاب: لا توجد طلبات معلقة")

    from utils.keyboards import cancel_kb as ckb
    await safe_edit(query, 
        "\n".join(lines),
        reply_markup=ckb("adm_main"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  نظام الإحالة
# ══════════════════════════════════════════════════════════

@_guard
async def adm_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    pct = db.get_setting("referral_pct", "0")
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تغيير نسبة الإحالة", callback_data="adm_set_ref_pct")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")],
    ])
    await safe_edit(query, 
        f"🤝 <b>نظام الإحالة</b>\n\n"
        f"النسبة الحالية: <b>{pct}%</b>\n\n"
        f"عند شحن رصيد مستخدم محال، يحصل المحيل على هذه النسبة من المبلغ المشحون.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@_guard
async def adm_set_ref_pct_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    _set_adm_state(context, "waiting_ref_pct")
    await safe_edit(query, 
        "✏️ أرسل نسبة الإحالة (مثال: 5 = 5%، 0 لإيقافها):",
        reply_markup=cancel_kb("adm_referral"),
    )


# ══════════════════════════════════════════════════════════
#  قبول/رفض فودافون كاش
# ══════════════════════════════════════════════════════════

@_guard
async def vod_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    charge_id = int(query.data.split("_")[2])
    charge    = db.get_vodafone_charge(charge_id)

    if not charge:
        await query.edit_message_caption("❌ الطلب غير موجود.")
        return
    if charge["status"] != "pending":
        await query.edit_message_caption(f"⚠️ الطلب #{charge_id} تم معالجته مسبقاً ({charge['status']}).")
        return

    # اطلب من الأدمن المبلغ قبل القبول
    context.user_data["adm_state"]          = "waiting_vod_amount"
    context.user_data["adm_vod_charge_id"]  = charge_id
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"💵 أرسل المبلغ الذي ستضيفه للمستخدم\n"
            f"(رقم الطلب: <code>{charge_id}</code> | رقم: <code>{charge['from_phone']}</code>):"
        ),
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


@_guard
async def vod_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    charge_id = int(query.data.split("_")[2])
    charge    = db.get_vodafone_charge(charge_id)

    if not charge:
        await query.edit_message_caption("❌ الطلب غير موجود.")
        return
    if charge["status"] != "pending":
        await query.edit_message_caption(f"⚠️ الطلب #{charge_id} تم معالجته مسبقاً.")
        return

    db.update_vodafone_status(charge_id, "rejected")

    try:
        await context.bot.send_message(
            chat_id=charge["user_tg_id"],
            text=(
                f"❌ <b>تم رفض طلب الشحن!</b>\n\n"
                f"💵 المبلغ: <b>${charge['amount']:.2f}</b>\n"
                f"🆔 رقم الطلب: <code>{charge_id}</code>\n\n"
                f"تواصل مع الدعم إذا كان هناك خطأ."
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await query.edit_message_caption(
        f"❌ تم رفض الطلب #{charge_id}.",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  رفع نسخة احتياطية (استعادة)
# ══════════════════════════════════════════════════════════

@_guard
async def adm_restore_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    _set_adm_state(context, "waiting_restore_file")
    await safe_edit(query, 
        "📤 <b>رفع نسخة احتياطية</b>\n\n"
        "أرسل ملف <code>.db</code> لاستعادته.\n"
        "⚠️ سيتم استبدال قاعدة البيانات الحالية!",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  إدارة الألعاب
# ══════════════════════════════════════════════════════════

@_guard
async def adm_games_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    from utils.keyboards import admin_games_kb
    apps = db.get_game_apps(active_only=False)
    await safe_edit(query, 
        "🎮 <b>إدارة الألعاب</b>\n\nقائمة التطبيقات:",
        reply_markup=admin_games_kb(apps),
        parse_mode="HTML",
    )


@_guard
async def adm_add_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    context.user_data["adm_state"] = "waiting_game_emoji"
    await safe_edit(query, 
        "🎮 أرسل **إيموجي** التطبيق (مثل: 🎮🔫🏆):",
        reply_markup=cancel_kb("adm_games"),
    )


@_guard
async def adm_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل تطبيق (باقاته)."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    from utils.keyboards import admin_game_app_kb
    app_id   = int(query.data.split("_")[2])
    app      = db.get_game_app(app_id)
    packages = db.get_game_packages(app_id)
    await safe_edit(query, 
        f"{app['emoji']} <b>{app['name']}</b>\n\nالباقات المتاحة:",
        reply_markup=admin_game_app_kb(app_id, packages),
        parse_mode="HTML",
    )


@_guard
async def adm_tog_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    from utils.keyboards import admin_games_kb
    app_id = int(query.data.split("_")[3])
    app    = db.get_game_app(app_id)
    db.toggle_game_app(app_id, not app["is_active"])
    apps   = db.get_game_apps(active_only=False)
    await safe_edit(query, 
        "🎮 <b>إدارة الألعاب</b>\n\nقائمة التطبيقات:",
        reply_markup=admin_games_kb(apps),
        parse_mode="HTML",
    )


@_guard
async def adm_del_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    from utils.keyboards import admin_games_kb
    app_id = int(query.data.split("_")[3])
    db.delete_game_app(app_id)
    apps   = db.get_game_apps(active_only=False)
    await safe_edit(query, 
        "✅ تم حذف التطبيق.\n\n🎮 <b>إدارة الألعاب</b>:",
        reply_markup=admin_games_kb(apps),
        parse_mode="HTML",
    )


@_guard
async def adm_add_game_pkg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    app_id = int(query.data.split("_")[4])
    context.user_data["adm_game_app_id"] = app_id
    context.user_data["adm_state"]       = "waiting_game_pkg_name"
    await safe_edit(query, 
        "🎁 أرسل **اسم الباقة** (مثل: 60 شدة / 100 جوهرة):",
        reply_markup=cancel_kb("adm_games"),
    )


@_guard
async def adm_del_game_pkg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    from utils.keyboards import admin_game_app_kb
    parts  = query.data.split("_")
    pkg_id = int(parts[4])
    app_id = int(parts[5])
    db.delete_game_package(pkg_id)
    packages = db.get_game_packages(app_id)
    app      = db.get_game_app(app_id)
    await safe_edit(query, 
        f"✅ تم حذف الباقة.\n\n{app['emoji']} <b>{app['name']}</b>:",
        reply_markup=admin_game_app_kb(app_id, packages),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  القنوات
# ══════════════════════════════════════════════════════════
#  👑 إدارة الأدمنز المتعددين (الأدمن الرئيسي فقط)
# ══════════════════════════════════════════════════════════

@_guard
async def adm_admins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الأدمنز."""
    q = update.callback_query; await q.answer()
    if not is_super_admin(q.from_user.id):
        await q.answer("🚫 هذا القسم للأدمن الرئيسي فقط.", show_alert=True)
        return
    db: Database = context.bot_data["db"]
    admins = db.get_all_admins()
    await q.edit_message_text(
        f"👑 <b>إدارة الأدمنز</b>\n"
        f"({len(admins)} أدمن فرعي + الأدمن الرئيسي)\n\n"
        f"⚠️ الأدمن الفرعي يملك نفس صلاحيات لوحة التحكم\n"
        f"ما عدا: إضافة/حذف أدمنز",
        reply_markup=admin_admins_kb(admins),
        parse_mode="HTML",
    )


@_guard
async def adm_add_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_super_admin(q.from_user.id):
        await q.answer("🚫 للأدمن الرئيسي فقط.", show_alert=True)
        return
    _set_adm_state(context, "waiting_new_admin_id")
    await q.edit_message_text(
        "👑 <b>إضافة أدمن جديد</b>\n\n"
        "أرسل الـ Telegram ID للمستخدم\n"
        "مثال: <code>123456789</code>\n\n"
        "💡 يمكن للمستخدم معرفة ID عبر @userinfobot",
        reply_markup=cancel_kb("adm_admins"),
        parse_mode="HTML",
    )


@_guard
async def adm_del_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_super_admin(q.from_user.id):
        await q.answer("🚫 للأدمن الرئيسي فقط.", show_alert=True)
        return
    db: Database = context.bot_data["db"]
    try:
        tg_id = int(q.data.split("_")[3])
    except (IndexError, ValueError):
        return
    db.remove_admin(tg_id)
    try:
        await context.bot.send_message(
            chat_id=tg_id,
            text="🔔 تم إزالة صلاحياتك كأدمن من البوت."
        )
    except Exception:
        pass
    await adm_admins_callback(update, context)


# ══════════════════════════════════════════════════════════

@_guard
async def adm_channels_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    notif   = db.get_setting("notif_channel",    "—")
    orders  = db.get_setting("orders_channel",   "—")
    checker = db.get_setting("checker_channel",  "—")
    updates = db.get_setting("updates_channel",  "—")
    await safe_edit(query, 
        f"📢 <b>إعدادات القنوات</b>\n\n"
        f"🔔 قناة المستخدمين الجدد:  <code>{notif}</code>\n"
        f"📦 قناة الطلبات المنفذة:   <code>{orders}</code>\n"
        f"📊 قناة تقارير الاسترداد:  <code>{checker}</code>\n"
        f"🆕 قناة تحديثات الخدمات:  <code>{updates}</code>",
        reply_markup=admin_channels_kb(),
        parse_mode="HTML",
    )


@_guard
async def adm_set_checker_ch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_checker_ch")
    await q.edit_message_text(
        "📊 أرسل معرّف قناة تقارير الاسترداد:\n"
        "(مثل: @mychannel أو -100xxx)\n\n"
        "💡 سيتم إرسال تقرير الملغى والجزئي هنا بدلاً من إزعاج الأدمن",
        reply_markup=cancel_kb("adm_channels"),
    )


@_guard
async def adm_set_updates_ch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_updates_ch")
    await q.edit_message_text(
        "🆕 أرسل معرّف <b>قناة تحديثات الخدمات</b>:\n"
        "(مثل: @mychannel أو -100xxx)\n\n"
        "💡 سيُرسل إليها إشعار عند:\n"
        "• إضافة خدمة جديدة ✅\n"
        "• حذف خدمة 🗑️\n"
        "• تغيّر سعر خدمة 📈📉",
        reply_markup=cancel_kb("adm_channels"),
        parse_mode="HTML",
    )


@_guard
async def adm_set_notif_ch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_notif_ch")
    await q.edit_message_text("🔔 أرسل معرّف قناة المستخدمين الجدد (مثل: @mychannel أو -100xxx):",
                              reply_markup=cancel_kb("adm_channels"))


@_guard
async def adm_set_orders_ch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_orders_ch")
    await q.edit_message_text("📦 أرسل معرّف قناة الطلبات (مثل: @mychannel أو -100xxx):",
                              reply_markup=cancel_kb("adm_channels"))


@_guard
async def adm_set_official_ch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_official_ch")
    await q.edit_message_text("🔗 أرسل رابط القناة الرسمية:", reply_markup=cancel_kb("adm_channels"))


@_guard
async def adm_set_orders_ch_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_orders_ch_link")
    await q.edit_message_text("🎬 أرسل رابط قناة الطلبات:", reply_markup=cancel_kb("adm_channels"))


@_guard
async def adm_set_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_support")
    await q.edit_message_text("🤖 أرسل يوزر الدعم الفني (مثال: @support):", reply_markup=cancel_kb("adm_channels"))


@_guard
async def adm_set_instructions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_instructions")
    await q.edit_message_text("📕 أرسل نص التعليمات (يدعم HTML):", reply_markup=cancel_kb("adm_channels"))


@_guard
async def adm_tog_vod_auto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل/إيقاف فودافون كاش التلقائي."""
    q = update.callback_query
    await q.answer()
    db: Database = context.bot_data["db"]
    cur = db.get_setting("pay_vodafone_auto", "0")
    db.set_setting("pay_vodafone_auto", "0" if cur == "1" else "1")
    await adm_payment_callback(update, context)


@_guard
async def adm_cfg_vod_auto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """صفحة إعدادات autocash."""
    q = update.callback_query
    await q.answer()
    db: Database = context.bot_data["db"]
    uid = db.get_setting("autocash_user_id",  "")
    pid = db.get_setting("autocash_panel_id", "")
    mn  = db.get_setting("vod_auto_min_egp",  "50")
    await q.edit_message_text(
        "📱 <b>إعدادات فودافون كاش التلقائي (autocash)</b>\n\n"
        "تحتاج إلى User ID و Panel ID من لوحة autocash\n"
        "لإنشاء حساب: https://autocash.store",
        reply_markup=admin_vod_auto_cfg_kb(uid, pid, mn),
        parse_mode="HTML",
    )


@_guard
async def adm_set_autocash_uid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_autocash_uid")
    await q.edit_message_text(
        "🆔 أرسل <b>User ID</b> من لوحة autocash:",
        reply_markup=cancel_kb("adm_cfg_vod_auto"),
        parse_mode="HTML",
    )


@_guard
async def adm_set_autocash_pid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_autocash_pid")
    await q.edit_message_text(
        "🆔 أرسل <b>Panel ID</b> من لوحة autocash:",
        reply_markup=cancel_kb("adm_cfg_vod_auto"),
        parse_mode="HTML",
    )


@_guard
async def adm_set_vod_min_egp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_vod_min_egp")
    await q.edit_message_text(
        "📉 أرسل <b>الحد الأدنى للشحن بالجنيه</b> (مثال: 50):",
        reply_markup=cancel_kb("adm_cfg_vod_auto"),
        parse_mode="HTML",
    )


@_guard
async def adm_set_vodafone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_vodafone_number")
    await q.edit_message_text("📱 أرسل رقم فودافون كاش:", reply_markup=cancel_kb("adm_payment"))


# ══════════════════════════════════════════════════════════
#  الاشتراك الإجباري
# ══════════════════════════════════════════════════════════

@_guard
@_guard
async def adm_forced_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    channels = db.get_forced_channels()
    await safe_edit(query, 
        f"🔒 <b>الاشتراك الإجباري</b>\n({len(channels)} قناة مضافة)",
        reply_markup=admin_forced_kb(channels),
        parse_mode="HTML",
    )


@_guard
async def adm_add_forced_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _set_adm_state(context, "waiting_forced_ch")
    await q.edit_message_text(
        "🔒 <b>إضافة قناة اشتراك إجباري</b>\n\n"
        "أرسل معرّف القناة:\n"
        "• يوزر: <code>@channelname</code>\n"
        "• ID رقمي: <code>-1001234567890</code>\n\n"
        "⚠️ تأكد أن البوت أدمن في القناة.",
        reply_markup=cancel_kb("adm_forced"),
        parse_mode="HTML",
    )


@_guard
async def adm_del_forced_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف قناة بالـ row ID الرقمي (آمن مع @ والـ numeric IDs)."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    # callback_data = adm_del_forced_<row_id>
    try:
        row_id = int(query.data.split("_")[3])
        db.remove_forced_channel_by_id(row_id)
    except (IndexError, ValueError):
        # fallback: حذف بالـ channel_id
        ch_id = query.data.replace("adm_del_forced_", "")
        db.remove_forced_channel(ch_id)
    await adm_forced_callback(update, context)


@_guard
async def adm_forced_skip_max_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الأدمن اختار 'دائمة' بدون حد أقصى."""
    q = update.callback_query; await q.answer()
    context.user_data.pop("adm_state", None)
    ch_id = context.user_data.pop("pending_forced_ch_id",    "")
    title = context.user_data.pop("pending_forced_ch_title", ch_id)
    db: Database = context.bot_data["db"]
    db.add_forced_channel(ch_id, title, max_members=0)
    await q.edit_message_text(
        f"✅ تمت إضافة القناة: <b>{title}</b>\n🔢 الحد: دائمة",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  النسخة الاحتياطية
# ══════════════════════════════════════════════════════════

@_guard
async def adm_backup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query, "📦 جارٍ إنشاء النسخة الاحتياطية...")
    from config import DATABASE_PATH
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"/tmp/backup_{ts}.db"
    shutil.copy2(DATABASE_PATH, dest)
    with open(dest, "rb") as f:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=f,
            filename=f"backup_{ts}.db",
            caption=f"💾 نسخة احتياطية — {ts}",
        )
    os.remove(dest)


# ══════════════════════════════════════════════════════════
#  الرسالة الجماعية
# ══════════════════════════════════════════════════════════

@_guard
async def adm_broadcast_send_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد الإرسال الجماعي."""
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]

    media_id   = context.user_data.pop("broadcast_media", None)
    media_type = context.user_data.pop("broadcast_media_type", "text")
    caption    = context.user_data.pop("broadcast_caption", "")
    context.user_data.pop("adm_state", None)

    all_ids = db.get_all_user_ids()
    sent = failed = 0
    msg = await safe_edit(query, f"📣 جارٍ الإرسال لـ {len(all_ids)} مستخدم...")

    for uid in all_ids:
        try:
            if media_type == "photo":
                await context.bot.send_photo(chat_id=uid, photo=media_id,
                                              caption=caption, parse_mode="HTML")
            elif media_type == "video":
                await context.bot.send_video(chat_id=uid, video=media_id,
                                              caption=caption, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=uid, text=caption, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await msg.edit_text(
        f"📣 <b>اكتملت الرسالة الجماعية</b>\n\n✅ نجح: {sent}\n❌ فشل: {failed}",
        parse_mode="HTML",
    )



@_guard
async def adm_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    _set_adm_state(context, "waiting_broadcast")
    await safe_edit(query, 
        "📣 <b>رسالة جماعية</b>\n\n"
        "أرسل الرسالة الآن:\n"
        "• نص فقط (يدعم HTML)\n"
        "• صورة مع نص (Caption)\n"
        "• فيديو مع نص (Caption)",
        reply_markup=cancel_kb("adm_main"),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  معالج رسائل الأدمن النصية (state machine)
# ══════════════════════════════════════════════════════════

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    db: Database = context.bot_data.get("db")
    if not is_admin(update.effective_user.id, db):
        return False

    # تحقق من معالج Binance يدوي (له state منفصل)
    from handlers.stars_binance_pay import binance_admin_amount_handler
    if await binance_admin_amount_handler(update, context):
        return True

    state = context.user_data.get("adm_state")
    if not state:
        return False

    db: Database = context.bot_data["db"]
    text = (update.message.text or update.message.caption or "").strip()

    # ── المستخدمون ──
    if state == "waiting_user_id":
        if not text.lstrip("-").isdigit():
            await update.message.reply_text("❌ أرسل ID رقمياً.")
            return True
        uid = int(text)
        user = db.get_user(uid)
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            context.user_data.pop("adm_state", None)
            return True
        balance  = db.get_balance(uid)
        uname    = f"@{user['username']}" if user.get("username") else "—"
        vip      = db.get_vip(uid)
        pts      = db.get_points(uid) if db.points_enabled() else None
        spent    = db.get_user_total_spent(uid)
        context.user_data.pop("adm_state", None)

        vip_line = f"\n👑 VIP — خصم {vip['discount_pct']:.0f}%" if vip else ""
        pts_line = f"\n🎯 النقاط: {pts:,}" if pts is not None else ""

        await update.message.reply_text(
            f"👤 <b>معلومات المستخدم</b>\n\n"
            f"ID: <code>{uid}</code>\n"
            f"الاسم: {user.get('first_name','—')}\n"
            f"المعرف: {uname}\n"
            f"الرصيد: <b>${balance:.4f}</b>\n"
            f"الإنفاق الكلي: <b>${spent:.4f}</b>\n"
            f"محظور: {'🚫 نعم' if user['is_banned'] else '✅ لا'}"
            f"{vip_line}{pts_line}",
            reply_markup=admin_user_actions_kb(uid, bool(user["is_banned"]), bool(vip)),
            parse_mode="HTML",
        )
        return True

    if state == "waiting_add_bal":
        try:
            amount = float(text)
            assert amount > 0
        except Exception:
            await update.message.reply_text("❌ أدخل مبلغاً صحيحاً أكبر من صفر.")
            return True
        uid = context.user_data.pop("adm_target", None)
        context.user_data.pop("adm_state", None)
        db.add_balance(uid, amount)
        bal = db.get_balance(uid)
        await update.message.reply_text(
            f"✅ تمت إضافة <b>${amount:.2f}</b> للمستخدم <code>{uid}</code>.\nرصيده الآن: <b>${bal:.2f}</b>",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"🎉 تم إضافة <b>${amount:.2f}</b> لرصيدك!\n💳 رصيدك الآن: <b>${bal:.2f}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return True

    if state == "waiting_dec_bal":
        try:
            amount = float(text)
            assert amount > 0
        except Exception:
            await update.message.reply_text("❌ أدخل مبلغاً صحيحاً أكبر من صفر.")
            return True
        uid = context.user_data.pop("adm_target", None)
        context.user_data.pop("adm_state", None)
        bal = db.get_balance(uid)
        new_bal = max(0.0, bal - amount)
        db.set_balance(uid, new_bal)
        await update.message.reply_text(
            f"✅ تم خصم <b>${amount:.2f}</b> من المستخدم <code>{uid}</code>.\nرصيده الآن: <b>${new_bal:.2f}</b>",
            parse_mode="HTML",
        )
        return True

    # ── المنصات ──
    if state == "waiting_platform_emoji":
        context.user_data["adm_platform_emoji"] = text
        context.user_data["adm_state"]           = "waiting_platform_name"
        await update.message.reply_text("📱 الآن أرسل اسم المنصة (مثل: انستجرام):",
                                        reply_markup=cancel_kb("adm_platforms"))
        return True

    if state == "waiting_platform_name":
        emoji = context.user_data.pop("adm_platform_emoji", "📱")
        context.user_data.pop("adm_state", None)
        db.add_platform(text, emoji)
        await update.message.reply_text(f"✅ تمت إضافة منصة: {emoji} {text}")
        return True

    # ── الفئات ──
    if state == "waiting_cat_emoji":
        context.user_data["adm_cat_emoji"] = text
        context.user_data["adm_state"]     = "waiting_cat_name"
        await update.message.reply_text("📂 الآن أرسل اسم الفئة (مثل: متابعين):",
                                        reply_markup=cancel_kb("adm_main"))
        return True

    if state == "waiting_cat_name":
        emoji = context.user_data.pop("adm_cat_emoji", "📂")
        pid   = context.user_data.pop("adm_platform", None)
        context.user_data.pop("adm_state", None)
        db.add_category(pid, text, emoji)
        await update.message.reply_text(f"✅ تمت إضافة الفئة: {emoji} {text}")
        return True

    # ── الخدمات (نسبة الربح) ──
    if state == "waiting_svc_margin":
        try:
            margin = float(text)
            assert 0 <= margin <= 1000
        except Exception:
            await update.message.reply_text("❌ أدخل نسبة صحيحة (مثل: 30 = 30%)")
            return True
        picked = context.user_data.get("adm_picked_svc", {})
        context.user_data["adm_margin"] = margin
        context.user_data["adm_state"]  = "waiting_svc_name"
        orig = float(picked.get("rate", 0))
        final = round(orig * (1 + margin / 100), 4)
        await update.message.reply_text(
            f"💡 السعر الأصلي: ${orig:.4f}\n"
            f"💰 السعر بعد الربح ({margin}%): <b>${final:.4f}</b>/1000\n\n"
            f"أرسل <b>الاسم المخصص</b> للخدمة (أو أرسل - للإبقاء على الاسم الأصلي):",
            reply_markup=cancel_kb("adm_main"),
            parse_mode="HTML",
        )
        return True

    if state == "waiting_svc_name":
        picked  = context.user_data.get("adm_picked_svc", {})
        margin  = context.user_data.get("adm_margin", 0)
        cat_id  = context.user_data.get("adm_cat_id", None)
        name    = text if text != "-" else picked.get("name", "خدمة")
        context.user_data["adm_svc_name"] = name
        context.user_data["adm_state"]    = "waiting_svc_desc"
        await update.message.reply_text(
            "📝 أرسل وصفاً للخدمة (أو أرسل - لتركه فارغاً):",
            reply_markup=cancel_kb("adm_main"),
        )
        return True

    if state == "waiting_svc_desc":
        picked    = context.user_data.get("adm_picked_svc", {})
        cat_id    = context.user_data.get("adm_cat_id", None)
        name      = context.user_data.get("adm_svc_name", picked.get("name","خدمة"))
        desc      = "" if text == "-" else text
        orig_rate = float(picked.get("rate", 0))
        margin    = float(context.user_data.get("adm_margin", 0))
        final_price = round(orig_rate * (1 + margin / 100), 4)
        context.user_data.pop("adm_state", None)

        new_sid = db.add_service(
            category_id    = cat_id,
            api_service_id = int(picked["service"]),
            name           = name,
            description    = desc,
            price_per_1000 = final_price,
            api_base_price = orig_rate,
            min_qty        = int(picked.get("min", 10)),
            max_qty        = int(picked.get("max", 10000)),
            speed          = picked.get("speed", ""),
            quality        = "",
            warranty       = "",
        )
        await update.message.reply_text(
            f"✅ تمت إضافة الخدمة:\n<b>{name}</b>\n${final_price:.4f}/1000",
            parse_mode="HTML",
        )

        # ── إشعار قناة تحديثات الخدمات ──────────────────
        updates_ch = db.get_setting("updates_channel", "").strip()
        if updates_ch:
            try:
                cat  = db.get_category(cat_id) or {}
                plat = db.get_platform(cat.get("platform_id", 0)) or {}
                cat_label  = f"{cat.get('emoji','')} {cat.get('name','')}".strip()
                plat_label = f"{plat.get('emoji','')} {plat.get('name','')}".strip()
                from config import BOT_USERNAME
                bot_name = BOT_USERNAME.lstrip("@")
                deep_link = f"https://t.me/{bot_name}?start=svc_{new_sid}"
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("📦 طلب من نفس الخدمة", url=deep_link)
                ]])
                await context.bot.send_message(
                    chat_id=updates_ch,
                    text=(
                        f"🆕 <b>خدمة جديدة تم إضافتها</b>\n\n"
                        f"🏷️ الاسم: {name}\n"
                        f"📱 المنصة: {plat_label or '—'}\n"
                        f"📂 القسم: {cat_label or '—'}\n\n"
                        f"🪙 السعر: <b>${final_price:.4f}</b> لكل 1000\n"
                        f"🔢 الحد الأدنى: {int(picked.get('min', 10)):,}\n"
                        f"🔢 الحد الأقصى: {int(picked.get('max', 10000)):,}"
                    ),
                    reply_markup=kb,
                    parse_mode="HTML",
                )
            except Exception as _e:
                logger.warning(f"[UPDATES CH] فشل إشعار الإضافة: {_e}")
        # ─────────────────────────────────────────────────
        context.user_data.pop("adm_margin", None)
        context.user_data.pop("adm_cat_id", None)
        context.user_data.pop("adm_picked_svc", None)
        context.user_data.pop("adm_svc_name", None)
        return True

    # ── إضافة سريعة بـ ID ──
    if state == "waiting_quick_svc_id":
        if not text.isdigit():
            await update.message.reply_text("❌ أرسل رقم ID صحيح (أرقام فقط).")
            return True
        api_svc_id = int(text)
        api: SMMApiClient = context.bot_data["api"]
        services = await api.get_services()
        picked = next((s for s in services if int(s.get("service", -1)) == api_svc_id), None)
        if not picked:
            await update.message.reply_text(
                f"❌ لم يُعثر على خدمة بـ ID: <b>{api_svc_id}</b>\n"
                "تأكد من الرقم وحاول مجدداً.",
                parse_mode="HTML"
            )
            return True
        context.user_data["adm_state"]      = "waiting_svc_margin"
        context.user_data["adm_picked_svc"] = picked
        orig = float(picked.get("rate", 0))
        await update.message.reply_text(
            f"✅ تم العثور على الخدمة:\n<b>{picked['name']}</b>\n"
            f"السعر الأصلي: ${orig:.4f}/1000\n\n"
            f"أرسل <b>نسبة الربح %</b> (مثلاً 30 = 30%):",
            parse_mode="HTML",
        )
        return True

    # ─ـ تغيير نسبة الربح الشاملة ─ـ
    if state == "waiting_global_margin":
        try:
            margin = float(text)
            assert 0 <= margin <= 1000
        except Exception:
            await update.message.reply_text("❌ أدخل نسبة صحيحة (مثل: 30 = 30%)")
            return True
        context.user_data.pop("adm_state", None)
        db.apply_global_margin(margin)
        total = db.get_services_count()
        await update.message.reply_text(
            f"✅ <b>تم تحديث نسبة الربح!</b>\n\n"
            f"النسبة الجديدة: <b>{margin}%</b>\n"
            f"الخدمات المحدّثة: <b>{total}</b>",
            parse_mode="HTML",
        )
        return True

    # ─ـ تعديل اسم خدمة ─ـ
    if state == "waiting_edit_svc_name":
        sid = context.user_data.pop("adm_edit_svc_id", None)
        cid = context.user_data.pop("adm_cat_id", None)
        context.user_data.pop("adm_state", None)
        if sid:
            db.update_service_field(sid, "name", text)
            await update.message.reply_text(
                f"✅ تم تغيير الاسم إلى: <b>{text}</b>",
                parse_mode="HTML"
            )
        return True

    # ─ـ تعديل سعر خدمة ─ـ
    if state == "waiting_edit_svc_price":
        sid = context.user_data.pop("adm_edit_svc_id", None)
        cid = context.user_data.pop("adm_cat_id", None)
        context.user_data.pop("adm_state", None)
        try:
            new_price = float(text)
            assert new_price > 0
        except Exception:
            await update.message.reply_text("❌ أدخل سعراً صحيحاً أكبر من صفر.")
            return True
        if sid:
            db.update_service_field(sid, "price_per_1000", new_price)
            await update.message.reply_text(
                f"✅ تم تغيير السعر إلى: <b>${new_price:.4f}</b>/1000",
                parse_mode="HTML"
            )
        return True

    # ─ـ الهدايا ─ـ
    if state == "waiting_gift_amount":
        try:
            amount = float(text)
            assert amount > 0
        except Exception:
            await update.message.reply_text("❌ أدخل مبلغاً صحيحاً.")
            return True
        context.user_data["adm_gift_amount"] = amount
        context.user_data["adm_state"]       = "waiting_gift_max_uses"
        await update.message.reply_text("🔢 أرسل الحد الأقصى للاستخدامات (مثل: 1):",
                                        reply_markup=cancel_kb("adm_gifts"))
        return True

    if state == "waiting_gift_max_uses":
        try:
            max_uses = int(text)
            assert max_uses > 0
        except Exception:
            await update.message.reply_text("❌ أدخل عدداً صحيحاً.")
            return True
        amount = context.user_data.pop("adm_gift_amount", 1.0)
        context.user_data.pop("adm_state", None)
        import random, string
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        db.create_gift_code(code, amount, max_uses)
        await update.message.reply_text(
            f"🎁 <b>تم إنشاء الكود بنجاح!</b>\n\n"
            f"الكود: <code>{code}</code>\n"
            f"المبلغ: <b>${amount:.2f}</b>\n"
            f"الاستخدامات: <b>{max_uses}</b>",
            parse_mode="HTML",
        )
        return True

    # ─ـ إعدادات الدفع ─ـ
    PAYMENT_STATES = {
        "waiting_bep20_addr":    ("bep20_address",    "adm_cfg_bep20"),
        "waiting_bep20_min":     ("bep20_min_usdt",   "adm_cfg_bep20"),
        "waiting_bep20_rate":    ("bep20_usdt_rate",  "adm_cfg_bep20"),
        "waiting_trc20_key":     ("trc20_api_key",    "adm_cfg_trc20"),
        "waiting_trc20_addr":    ("trc20_address",    "adm_cfg_trc20"),
        "waiting_trc20_min":     ("trc20_min_usdt",   "adm_cfg_trc20"),
        "waiting_trc20_rate":    ("trc20_usdt_rate",  "adm_cfg_trc20"),
        "waiting_stars_rate":    ("stars_per_dollar",  "adm_cfg_stars"),
        "waiting_stars_min":     ("stars_min_usd",     "adm_cfg_stars"),
        "waiting_ton_addr":      ("ton_address",      "adm_cfg_ton"),
        "waiting_ton_min":       ("ton_min_amount",   "adm_cfg_ton"),
        "waiting_trx_addr":      ("trx_address",      "adm_cfg_trx"),
        "waiting_trx_min":       ("trx_min_amount",   "adm_cfg_trx"),
        "waiting_binance_id":    ("binance_pay_id",    "adm_cfg_binance"),
        "waiting_binance_key":   ("binance_api_key",   "adm_cfg_binance"),
        "waiting_binance_secret":("binance_api_secret","adm_cfg_binance"),
        "waiting_notif_ch":      ("notif_channel",    "adm_channels"),
        "waiting_orders_ch":     ("orders_channel",   "adm_channels"),
        "waiting_checker_ch":    ("checker_channel",  "adm_channels"),
        "waiting_updates_ch":    ("updates_channel",  "adm_channels"),
    }
    if state in PAYMENT_STATES:
        setting_key, back_cb = PAYMENT_STATES[state]
        db.set_setting(setting_key, text)
        context.user_data.pop("adm_state", None)
        await update.message.reply_text(
            f"✅ تم حفظ الإعداد.",
            reply_markup=cancel_kb(back_cb),
        )
        return True

    # ─ـ قبول فودافون: إدخال المبلغ ─ـ
    if state == "waiting_vod_amount":
        context.user_data.pop("adm_state", None)
        charge_id = context.user_data.pop("adm_vod_charge_id", None)
        try:
            amount = float(text)
            assert amount > 0
        except Exception:
            await update.message.reply_text("❌ أرسل مبلغاً صحيحاً (مثال: 10 أو 5.5)")
            return True
        if not charge_id:
            await update.message.reply_text("❌ انتهت الجلسة.")
            return True
        charge = db.get_vodafone_charge(charge_id)
        if not charge or charge["status"] != "pending":
            await update.message.reply_text("❌ الطلب غير موجود أو تم معالجته.")
            return True
        # تحديث المبلغ والقبول
        with db._conn() as conn:
            conn.execute("UPDATE vodafone_charges SET amount=?, status='completed' WHERE id=?",
                         (amount, charge_id))
        db.add_balance(charge["user_tg_id"], amount)
        from handlers.charge import _apply_referral_bonus
        _apply_referral_bonus(db, charge["user_tg_id"], amount)
        try:
            await context.bot.send_message(
                chat_id=charge["user_tg_id"],
                text=(
                    f"✅ <b>تم قبول شحنك!</b>\n\n"
                    f"💵 المبلغ المضاف: <b>${amount:.2f}</b>\n"
                    f"💳 رصيدك الآن: <b>${db.get_balance(charge['user_tg_id']):.2f}</b>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await update.message.reply_text(
            f"✅ تم قبول الطلب #{charge_id} وإضافة <b>${amount:.2f}</b> للمستخدم <code>{charge['user_tg_id']}</code>.",
            parse_mode="HTML",
        )
        return True

    # ─ـ الاشتراك الإجباري — الخطوة 1: معرف القناة ─ـ
    if state == "waiting_forced_ch":
        raw = text.strip()
        ch_id = raw if raw.startswith("@") or raw.startswith("-") else f"@{raw}"
        context.user_data.pop("adm_state", None)
        try:
            chat = await context.bot.get_chat(ch_id)
            title = chat.title or ch_id
            # حفظ مؤقت وانتقل لسؤال الحد الأقصى
            context.user_data["pending_forced_ch_id"]    = ch_id
            context.user_data["pending_forced_ch_title"] = title
            _set_adm_state(context, "waiting_forced_max")
            from utils.keyboards import skip_kb
            await update.message.reply_text(
                f"✅ تم التحقق من القناة: <b>{title}</b>\n\n"
                f"📊 كم عدد الانضمامات قبل أن تُحذف تلقائياً من الاشتراك الإجباري؟\n\n"
                f"• أرسل رقماً مثل <code>500</code>\n"
                f"• أو اضغط <b>تخطي</b> لجعلها دائمة",
                reply_markup=skip_kb("adm_forced_skip_max"),
                parse_mode="HTML",
            )
        except Exception as e:
            await update.message.reply_text(f"❌ تعذّر الوصول للقناة: {e}")
        return True

    # ─ـ الاشتراك الإجباري — الخطوة 2: الحد الأقصى ─ـ
    if state == "waiting_forced_max":
        context.user_data.pop("adm_state", None)
        ch_id  = context.user_data.pop("pending_forced_ch_id",    "")
        title  = context.user_data.pop("pending_forced_ch_title", ch_id)
        try:
            max_m = int(text.strip())
            assert max_m > 0
        except Exception:
            max_m = 0
        db.add_forced_channel(ch_id, title, max_m)
        limit_txt = f"تُحذف بعد {max_m} انضمام" if max_m > 0 else "دائمة"
        await update.message.reply_text(
            f"✅ تمت إضافة القناة: <b>{title}</b>\n"
            f"🔢 الحد: {limit_txt}",
            parse_mode="HTML",
        )
        return True

    # ─ـ الرسالة الجماعية: استلام المحتوى ─ـ
    if state == "waiting_broadcast":
        msg   = update.message
        photo = msg.photo
        video = msg.video

        if photo:
            context.user_data["broadcast_media"]      = photo[-1].file_id
            context.user_data["broadcast_media_type"] = "photo"
            context.user_data["broadcast_caption"]    = msg.caption or ""
        elif video:
            context.user_data["broadcast_media"]      = video.file_id
            context.user_data["broadcast_media_type"] = "video"
            context.user_data["broadcast_caption"]    = msg.caption or ""
        else:
            context.user_data["broadcast_media"]      = None
            context.user_data["broadcast_media_type"] = "text"
            context.user_data["broadcast_caption"]    = text

        _set_adm_state(context, "waiting_broadcast_confirm")

        # عرض معاينة + زرا تأكيد/إلغاء
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        confirm_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ إرسال للجميع", callback_data="adm_broadcast_send"),
                InlineKeyboardButton("❌ إلغاء",        callback_data="adm_main"),
            ]
        ])
        preview = context.user_data["broadcast_caption"] or "(بدون نص)"
        await msg.reply_text(
            f"📣 <b>معاينة الرسالة الجماعية</b>\n\n"
            f"النوع: {'🖼 صورة' if context.user_data['broadcast_media_type']=='photo' else '🎥 فيديو' if context.user_data['broadcast_media_type']=='video' else '📝 نص'}\n"
            f"النص: {preview[:200]}\n\n"
            "هل تريد الإرسال للجميع؟",
            reply_markup=confirm_kb,
            parse_mode="HTML",
        )
        return True

    # ─ـ نسبة الإحالة ─ـ
    if state == "waiting_ref_pct":
        context.user_data.pop("adm_state", None)
        try:
            pct = float(text)
            assert 0 <= pct <= 100
        except Exception:
            await update.message.reply_text("❌ أرسل رقماً بين 0 و100")
            return True
        db.set_setting("referral_pct", str(pct))
        await update.message.reply_text(f"✅ نسبة الإحالة: <b>{pct}%</b>", parse_mode="HTML")
        return True

    # ─ـ إضافة أدمن جديد ─ـ
    if state == "waiting_new_admin_id":
        if not is_super_admin(update.effective_user.id):
            return False
        context.user_data.pop("adm_state", None)
        try:
            new_id = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ أرسل Telegram ID رقمي صحيح.")
            return True
        if new_id == ADMIN_ID:
            await update.message.reply_text("⚠️ هذا هو الأدمن الرئيسي بالفعل!")
            return True
        # محاولة جلب معلومات المستخدم
        username = ""
        try:
            chat = await context.bot.get_chat(new_id)
            username = chat.username or ""
            name = chat.full_name or str(new_id)
        except Exception:
            name = str(new_id)
        added = db.add_admin(new_id, username)
        if added:
            await update.message.reply_text(
                f"✅ تمت إضافة الأدمن: <b>{name}</b>\n"
                f"🆔 <code>{new_id}</code>",
                parse_mode="HTML",
            )
            try:
                await context.bot.send_message(
                    chat_id=new_id,
                    text="🎉 تمت إضافتك كأدمن في البوت!\nاكتب /admin للوصول للوحة التحكم."
                )
            except Exception:
                pass
        else:
            await update.message.reply_text("⚠️ هذا المستخدم أدمن بالفعل.")
        return True

    # ─ـ استعادة قاعدة البيانات ─ـ
    if state == "waiting_restore_file":
        context.user_data.pop("adm_state", None)
        if not update.message.document:
            await update.message.reply_text(
                "❌ أرسل ملف .db فقط.\n/admin للرجوع للوحة."
            )
            return True
        doc = update.message.document
        if not doc.file_name.endswith(".db"):
            await update.message.reply_text("❌ الملف يجب أن يكون بصيغة .db")
            return True
        # حجم الملف لا يتجاوز 50 MB
        if doc.file_size and doc.file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ حجم الملف كبير جداً (الحد 50 MB).")
            return True
        try:
            import sqlite3 as _sqlite3
            import tempfile, os
            from config import DATABASE_PATH
            # ── تنزيل الملف في مكان مؤقت أولاً ──
            tmp_path = DATABASE_PATH + ".tmp_restore"
            file = await context.bot.get_file(doc.file_id)
            await file.download_to_drive(tmp_path)
            # ── التحقق أنه قاعدة بيانات SQLite صحيحة ──
            try:
                conn_test = _sqlite3.connect(tmp_path)
                tables = {
                    r[0] for r in
                    conn_test.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                conn_test.close()
            except _sqlite3.DatabaseError:
                os.remove(tmp_path)
                await update.message.reply_text(
                    "❌ الملف ليس قاعدة بيانات SQLite صحيحة.\n"
                    "تأكد أنك رفعت النسخة الاحتياطية الصحيحة."
                )
                return True
            # ── التحقق من وجود الجداول الأساسية ──
            required = {"users", "orders", "settings"}
            missing  = required - tables
            if missing:
                os.remove(tmp_path)
                await update.message.reply_text(
                    f"❌ الملف لا يبدو نسخة من هذا البوت.\n"
                    f"جداول مفقودة: {', '.join(missing)}"
                )
                return True
            # ── نسخ احتياطي من الحالي ثم استبداله ──
            backup_path = DATABASE_PATH + ".bak"
            shutil.copy2(DATABASE_PATH, backup_path)
            shutil.move(tmp_path, DATABASE_PATH)
            await update.message.reply_text(
                f"✅ <b>تم استعادة قاعدة البيانات!</b>\n\n"
                f"📋 الجداول المُستعادة: {len(tables)}\n"
                f"💾 نسخة احتياطية من القديم: {backup_path}\n\n"
                f"⚠️ <b>أعد تشغيل البوت لتطبيق التغييرات.</b>",
                parse_mode="HTML",
            )
        except Exception as e:
            # تنظيف الملف المؤقت لو موجود
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            await update.message.reply_text(f"❌ فشل الاستعادة: {e}")
        return True

    # ─ـ إعدادات القنوات والروابط ─ـ
    LINK_STATES = {
        "waiting_notif_ch":        ("notif_channel",       "adm_channels"),
        "waiting_orders_ch":       ("orders_channel",      "adm_channels"),
        "waiting_support":         ("support_link",        "adm_channels"),
        "waiting_official_ch":     ("official_channel",    "adm_channels"),
        "waiting_orders_ch_link":  ("orders_channel_link", "adm_channels"),
        "waiting_instructions":    ("instructions",        "adm_channels"),
        "waiting_vodafone_number": ("vodafone_number",     "adm_payment"),
        "waiting_autocash_uid":    ("autocash_user_id",   "adm_cfg_vod_auto"),
        "waiting_autocash_pid":    ("autocash_panel_id",  "adm_cfg_vod_auto"),
        "waiting_vod_min_egp":     ("vod_auto_min_egp",   "adm_cfg_vod_auto"),
    }
    if state in LINK_STATES:
        setting_key, back_cb = LINK_STATES[state]
        db.set_setting(setting_key, text)
        context.user_data.pop("adm_state", None)
        await update.message.reply_text("✅ تم حفظ الإعداد.", reply_markup=cancel_kb(back_cb))
        return True

    # ─ـ الألعاب ─ـ
    if state == "waiting_game_emoji":
        context.user_data["adm_game_emoji"] = text
        context.user_data["adm_state"]      = "waiting_game_name"
        await update.message.reply_text("🎮 الآن أرسل اسم التطبيق:", reply_markup=cancel_kb("adm_games"))
        return True

    if state == "waiting_game_name":
        emoji = context.user_data.pop("adm_game_emoji", "🎮")
        context.user_data.pop("adm_state", None)
        db.add_game_app(text, emoji)
        await update.message.reply_text(f"✅ تمت إضافة التطبيق: {emoji} {text}")
        return True

    if state == "waiting_game_pkg_name":
        context.user_data["adm_game_pkg_name"] = text
        context.user_data["adm_state"]         = "waiting_game_pkg_price"
        await update.message.reply_text("💰 أرسل سعر الباقة (مثال: 5.50):", reply_markup=cancel_kb("adm_games"))
        return True

    if state == "waiting_game_pkg_price":
        try:
            price = float(text)
            assert price > 0
        except Exception:
            await update.message.reply_text("❌ أدخل سعراً صحيحاً (مثال: 5.50)")
            return True
        pkg_name = context.user_data.pop("adm_game_pkg_name", "")
        app_id   = context.user_data.pop("adm_game_app_id", None)
        context.user_data.pop("adm_state", None)
        db.add_game_package(app_id, pkg_name, price)
        await update.message.reply_text(
            f"✅ تمت إضافة الباقة: <b>{pkg_name}</b> — <b>${price:.2f}</b>",
            parse_mode="HTML",
        )
        return True

    return False