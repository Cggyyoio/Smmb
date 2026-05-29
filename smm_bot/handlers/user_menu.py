from utils.safe_send import safe_answer, safe_edit, safe_send
"""
📱 تصفح المنصات والفئات والخدمات — handlers/user_menu.py
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from database import Database
from utils.keyboards import (
    platforms_list_kb, main_menu_kb, categories_kb, services_kb,
    service_detail_kb, back_to_main_kb, balance_kb
)
from utils.subscription import check_subscription
from utils.keyboards import subscription_kb

logger = logging.getLogger(__name__)


async def _check_and_proceed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    db: Database = context.bot_data["db"]
    user = update.effective_user
    if db.is_banned(user.id):
        await safe_answer(query, "🚫 أنت محظور!", show_alert=True)
        return False
    ok, missing = await check_subscription(context.bot, user.id, db)
    if not ok:
        await safe_answer(query)
        await safe_edit(query, 
            "📢 <b>يجب الاشتراك في القنوات أولاً:</b>",
            reply_markup=subscription_kb(missing),
            parse_mode="HTML",
        )
        return False
    return True


# ══════════════════════════════════════════════════════════
#  القائمة الرئيسية
# ══════════════════════════════════════════════════════════

async def _build_welcome(user_id: int, db: Database) -> tuple:
    """بناء نص الترحيب + لوحة المفاتيح."""
    from handlers.start import _welcome_text, _get_menu_kb
    u_data  = db.get_user(user_id)
    balance = db.get_balance(user_id)
    spent   = db.get_user_total_spent(user_id)
    text    = _welcome_text(u_data, balance, spent)

    # ── إضافات: VIP + عملة ثانية + نقاط ──
    extras = []
    vip = db.get_vip(user_id)
    if vip:
        extras.append(f"⭐ <b>VIP — خصم {vip['discount_pct']:.0f}%</b>")
    if db.points_enabled():
        pts = db.get_points(user_id)
        extras.append(f"🎯 نقاطك: <b>{pts:,}</b>")
    cur2_name, cur2_rate = db.get_second_currency()
    if db.second_currency_enabled() and cur2_rate > 0:
        extras.append(f"💱 <b>${balance:.2f} = {cur2_name} {balance * cur2_rate:.1f}</b>")
    if extras:
        text += "\n" + "  |  ".join(extras)

    return text, _get_menu_kb(db)


async def menu_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    if not await _check_and_proceed(update, context):
        return
    # امسح أي state مفتوح للخدمات المجانية
    from utils.states import clear_all_states
    clear_all_states(context)
    db: Database = context.bot_data["db"]
    text, kb = await _build_welcome(update.effective_user.id, db)
    await safe_edit(query, text, reply_markup=kb, parse_mode="HTML")


async def menu_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await menu_main_callback(update, context)


# ══════════════════════════════════════════════════════════
#  SMM Platforms (زر "بدء طلبية رشق جديدة")
# ══════════════════════════════════════════════════════════

async def smm_platforms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المنصات بعد ضغط زر الرشق."""
    query = update.callback_query
    await safe_answer(query)
    if not await _check_and_proceed(update, context):
        return

    db: Database = context.bot_data["db"]
    platforms = db.get_platforms()
    if not platforms:
        await safe_edit(query, 
            "⚠️ لا توجد منصات متاحة حالياً.\nتواصل مع الأدمن.",
            reply_markup=back_to_main_kb(),
        )
        return

    await safe_edit(query, 
        "🚀 <b>بدء طلبية رشق جديدة</b>\n\nاختر المنصة:",
        reply_markup=platforms_list_kb(platforms),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  المنصة → الفئات
# ══════════════════════════════════════════════════════════

async def platform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    if not await _check_and_proceed(update, context):
        return

    db: Database  = context.bot_data["db"]
    platform_id   = int(query.data.split("_")[1])
    platform      = db.get_platform(platform_id)
    if not platform:
        await safe_edit(query, "❌ المنصة غير موجودة.", reply_markup=back_to_main_kb())
        return

    categories = db.get_categories(platform_id)
    if not categories:
        await safe_edit(query, 
            "⚠️ لا توجد فئات في هذه المنصة حالياً.\nتواصل مع الأدمن.",
            reply_markup=back_to_main_kb(),
        )
        return

    await safe_edit(query, 
        f"{platform['emoji']} <b>{platform['name']}</b>\n\nاختر الفئة:",
        reply_markup=categories_kb(platform_id, categories),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  الفئة → الخدمات
# ══════════════════════════════════════════════════════════

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    if not await _check_and_proceed(update, context):
        return

    db: Database = context.bot_data["db"]
    category_id  = int(query.data.split("_")[1])
    cat          = db.get_category(category_id)
    if not cat:
        await safe_edit(query, "❌ الفئة غير موجودة.", reply_markup=back_to_main_kb())
        return

    services = db.get_services(category_id)
    if not services:
        await safe_edit(query, 
            f"{cat.get('emoji','')} <b>{cat['name']}</b>\n\n"
            "⚠️ لا توجد خدمات في هذه الفئة حالياً.\nتواصل مع الأدمن.",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        return

    context.user_data["svc_list"] = services
    context.user_data["svc_cat"]  = category_id

    await safe_edit(query, 
        f"{cat['emoji']} <b>{cat['name']}</b>\n\nاختر الخدمة:",
        reply_markup=services_kb(category_id, services, page=0),
        parse_mode="HTML",
    )


async def svc_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query       = update.callback_query
    await safe_answer(query)
    parts       = query.data.split("_")
    category_id = int(parts[2])
    page        = int(parts[3])
    db: Database = context.bot_data["db"]
    services    = db.get_services(category_id)
    cat         = db.get_category(category_id)
    await safe_edit(query, 
        f"{cat['emoji']} <b>{cat['name']}</b>\n\nاختر الخدمة:",
        reply_markup=services_kb(category_id, services, page=page),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  تفاصيل الخدمة
# ══════════════════════════════════════════════════════════

async def service_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    if not await _check_and_proceed(update, context):
        return

    db: Database = context.bot_data["db"]
    service_id   = int(query.data.split("_")[1])
    svc          = db.get_service(service_id)
    if not svc or not svc["is_active"]:
        await safe_answer(query, "❌ الخدمة غير متوفرة حالياً.", show_alert=True)
        return

    balance = db.get_balance(update.effective_user.id)
    text = _format_service(svc, balance)
    await safe_edit(query, 
        text,
        reply_markup=service_detail_kb(service_id),
        parse_mode="HTML",
    )


async def service_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    service_id   = int(query.data.split("_")[2])
    svc          = db.get_service(service_id)
    if not svc:
        text, kb = await _build_welcome(update.effective_user.id, db)
        await safe_edit(query, text, reply_markup=kb, parse_mode="HTML")
        return
    cat_id   = svc["category_id"]
    services = db.get_services(cat_id)
    cat      = db.get_category(cat_id)
    await safe_edit(query, 
        f"{cat['emoji']} <b>{cat['name']}</b>\n\nاختر الخدمة:",
        reply_markup=services_kb(cat_id, services, page=0),
        parse_mode="HTML",
    )


async def platform_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    cat_id   = int(query.data.split("_")[2])
    cat      = db.get_category(cat_id)
    if not cat:
        await menu_main_callback(update, context)
        return
    pid      = cat["platform_id"]
    platform = db.get_platform(pid)
    cats     = db.get_categories(pid)
    await safe_edit(query, 
        f"{platform['emoji']} <b>{platform['name']}</b>\n\nاختر الفئة:",
        reply_markup=categories_kb(pid, cats),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  طلباتي
# ══════════════════════════════════════════════════════════

async def my_orders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    if not await _check_and_proceed(update, context):
        return

    db: Database = context.bot_data["db"]
    api          = context.bot_data.get("api")
    orders       = db.get_user_orders(update.effective_user.id, limit=10)

    if not orders:
        await safe_edit(query, 
            "📦 <b>لا توجد طلبات بعد!</b>\nابدأ بطلب خدمة من القائمة.",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        return

    STATUS_MAP = {
        "pending":     ("⏳", "قيد الانتظار"),
        "in progress": ("⚙️", "جاري التنفيذ"),
        "inprogress":  ("⚙️", "جاري التنفيذ"),
        "processing":  ("⚙️", "جاري التنفيذ"),
        "completed":   ("✅", "مكتمل"),
        "canceled":    ("❌", "ملغي"),
        "cancelled":   ("❌", "ملغي"),
        "partial":     ("⚠️", "جزئي"),
        "refunded":    ("💸", "مسترد"),
    }

    # ── جلب كل الحالات في call واحد ──
    api_ids = [str(o["api_order_id"]) for o in orders if o.get("api_order_id")]
    live: dict = {}   # {"3152": {"status": "Canceled", ...}, ...}

    if api and api_ids:
        try:
            if len(api_ids) == 1:
                res = await api.get_order_status(api_ids[0])
                if isinstance(res, dict) and not res.get("error"):
                    live[api_ids[0]] = res
            else:
                res = await api.get_multiple_status(api_ids)
                if isinstance(res, dict):
                    live = {k: v for k, v in res.items()
                            if isinstance(v, dict) and not v.get("error")}
        except Exception:
            pass  # fallback للـ DB

    # ── تحديث DB للطلبات اللي اتغيرت (batch) ──
    with db._conn() as conn:
        for o in orders:
            api_id   = str(o.get("api_order_id") or "")
            api_data = live.get(api_id, {})
            if not api_data:
                continue
            new_st = api_data.get("status", "").lower().strip()
            if new_st and new_st != o.get("status", "").lower():
                conn.execute("UPDATE orders SET status=? WHERE id=?",
                             (new_st, o["id"]))

    # ── بناء الرسالة ──
    lines = ["📦 <b>آخر طلباتك:</b>\n"]
    for o in orders:
        api_id   = str(o.get("api_order_id") or "")
        api_data = live.get(api_id, {})

        if api_data:
            raw_status  = api_data.get("status", "").lower().strip()
            remains_val = str(api_data.get("remains") or "")
        else:
            raw_status  = o.get("status", "pending").lower().strip()
            remains_val = str(o.get("remains") or "")

        emoji, status_ar = STATUS_MAP.get(raw_status, ("❓", raw_status))
        svc_name = o.get("service_name") or "—"

        # شكل الرسالة — اقتباس لكل طلب
        block = (
            f"{emoji} <b>#{o['id']}</b> — {svc_name}  "
            f"📊 الحاله : {status_ar}\n"
            f"💰المبلغ : ${o['price']:.2f} \n"
            f"🔢 الكميه : {o['quantity']:,}"
        )
        if raw_status == "partial" and remains_val not in ("0", ""):
            block += f"\n⬇️ المتبقي : {remains_val}"
        if api_id:
            block += f"\n🆔 معرف الطلب : {api_id}"

        lines.append(block)

    # دمج كل طلب في blockquote مع زر إعادة الطلب
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    header = lines[0]

    msg_parts = [header]
    reorder_btns = []
    for i, o in enumerate(orders):
        msg_parts.append(f"<blockquote>{lines[i+1]}</blockquote>")
        raw_st = (o.get("status") or "pending").lower()
        if raw_st in ("completed", "partial", "cancelled", "canceled"):
            reorder_btns.append([InlineKeyboardButton(
                f"🔄 إعادة #{o['id']}",
                callback_data=f"reorder_{o['id']}"
            )])

    kb_rows = reorder_btns + [[InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")]]

    await safe_edit(query, 
        "\n\n".join(msg_parts),
        reply_markup=InlineKeyboardMarkup(kb_rows),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  الاحصائيات
# ══════════════════════════════════════════════════════════

async def my_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    user = update.effective_user

    balance = db.get_balance(user.id)
    spent   = db.get_user_total_spent(user.id)
    orders  = db.get_user_orders(user.id, limit=1000)
    total_orders = len(orders)

    await safe_edit(query, 
        f"📊 <b>إحصائياتك</b>\n\n"
        f"💳 الرصيد الحالي: <b>${balance:.2f}</b>\n"
        f"💸 إجمالي الصرفيات: <b>${spent:.2f}</b>\n"
        f"📦 إجمالي الطلبات: <b>{total_orders}</b>",
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  طلب تعويض (رشق من القائمة)
# ══════════════════════════════════════════════════════════

async def refill_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    from utils.keyboards import cancel_kb
    await safe_edit(query, 
        "♻️ <b>طلب تعويض (رشق)</b>\n\n"
        "أرسل رقم الطلب القديم الذي تريد رشقه:",
        reply_markup=cancel_kb("menu_main"),
        parse_mode="HTML",
    )
    context.user_data["order_state"] = "waiting_refill_order_id"
    context.user_data["refill_from_menu"] = True


# ══════════════════════════════════════════════════════════
#  تتبع طلب
# ══════════════════════════════════════════════════════════

async def track_order_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    from utils.keyboards import cancel_kb
    await safe_edit(query, 
        "📡 <b>تتبع الطلب</b>\n\nأرسل رقم الطلب (API Order ID):",
        reply_markup=cancel_kb("menu_main"),
        parse_mode="HTML",
    )
    context.user_data["state"] = "tracking_order"


# ══════════════════════════════════════════════════════════
#  التعليمات
# ══════════════════════════════════════════════════════════

async def bot_instructions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    instructions = db.get_setting("instructions", "لا توجد تعليمات متاحة حالياً.")
    await safe_edit(query, 
        f"📕 <b>التعليمات</b>\n\n{instructions}",
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════
#  روابط (الدعم / القناة)
# ══════════════════════════════════════════════════════════

async def support_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    support = db.get_setting("support_link", "")
    if support:
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        # يدعم يوزر مثل @admin أو رابط كامل
        url = support if support.startswith("http") else f"https://t.me/{support.lstrip('@')}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 تواصل مع الدعم", url=url)],
            [InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")],
        ])
        await safe_edit(query, 
            "🤖 <b>الدعم الفني</b>\n\nاضغط الزر أدناه للتواصل:",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await safe_answer(query, "لم يتم تعيين رابط الدعم بعد.", show_alert=True)


async def official_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    ch = db.get_setting("official_channel", "")
    if ch:
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 القناة الرسمية", url=ch)],
            [InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")],
        ])
        await safe_edit(query, 
            "📢 <b>القناة الرسمية</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await safe_answer(query, "لم يتم تعيين القناة بعد.", show_alert=True)


async def orders_channel_btn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    ch = db.get_setting("orders_channel_link", "")
    if ch:
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 قناة الطلبات", url=ch)],
            [InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")],
        ])
        await safe_edit(query, 
            "🎬 <b>قناة الطلبات</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await safe_answer(query, "لم يتم تعيين رابط القناة بعد.", show_alert=True)


# ══════════════════════════════════════════════════════════
#  مساعد تنسيق الخدمة
# ══════════════════════════════════════════════════════════

def _format_service(svc: dict, user_balance: float = 0.0) -> str:
    price = svc["price_per_1000"]
    lines = [
        f"🔹 <b>{svc['name']}</b>\n",
        f"💰 السعر لكل 1000: <b>${price:.4f}</b>",
        f"📊 الحد الأدنى: <b>{svc['min_qty']}</b>",
        f"📊 الحد الأقصى: <b>{svc['max_qty']}</b>",
        f"💳 رصيدك الحالي: <b>${user_balance:.2f}</b>",
    ]
    if svc.get("speed"):
        lines.append(f"⚡ السرعة: {svc['speed']}")
    if svc.get("quality"):
        lines.append(f"✨ الجودة: {svc['quality']}")
    if svc.get("warranty"):
        lines.append(f"🛡 الضمان: {svc['warranty']}")
    if svc.get("description"):
        lines.append(f"\n📝 {svc['description']}")
    return "\n".join(lines)
