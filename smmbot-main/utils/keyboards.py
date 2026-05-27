"""
⌨️ كل لوحات المفاتيح — utils/keyboards.py
"""

from telegram import InlineKeyboardMarkup, InlineKeyboardButton


# ══════════════════════════════════════════════════════════════
#  مساعد: بناء صفوف من قائمة أزرار
# ══════════════════════════════════════════════════════════════

def _build_grid(buttons: list, cols: int = 2) -> list:
    """توزيع قائمة أزرار على شبكة بعدد أعمدة محدد."""
    return [buttons[i:i + cols] for i in range(0, len(buttons), cols)]


# ══════════════════════════════════════════════════════════════
#  القائمة الرئيسية
# ══════════════════════════════════════════════════════════════

def main_menu_kb(official_url: str = "", orders_url: str = "", website_url: str = "") -> InlineKeyboardMarkup:
    """القائمة الرئيسية — أزرار القنوات روابط مباشرة."""
    if official_url:
        ch_btn = InlineKeyboardButton("📢 : القناة الرسمية", url=official_url)
    else:
        ch_btn = InlineKeyboardButton("📢 : القناة الرسمية", callback_data="official_channel")

    if orders_url:
        ord_btn = InlineKeyboardButton("🎬 : قناة الطلبات", url=orders_url)
    else:
        ord_btn = InlineKeyboardButton("🎬 : قناة الطلبات", callback_data="orders_channel_btn")

    rows = [
        [InlineKeyboardButton("🚀 : بدء طلبية رشق جديدة", callback_data="smm_platforms")],
        [InlineKeyboardButton("🎮 : شحن الألعاب",          callback_data="game_charge")],
        [
            InlineKeyboardButton("💰 : إشحن رصيدك", callback_data="my_balance"),
            InlineKeyboardButton("💸 : ربح رصيد",   callback_data="redeem_gift"),
        ],
        [
            InlineKeyboardButton("📊 : الاحصائيات",  callback_data="my_stats"),
            InlineKeyboardButton("🔍 : كشف طلب",     callback_data="track_order_menu"),
        ],
        [
            InlineKeyboardButton("📋 : طلباتي",    callback_data="my_orders"),
            InlineKeyboardButton("📕 : التعليمات", callback_data="bot_instructions"),
        ],
        [
            InlineKeyboardButton("🎫 : تذاكر الدعم", callback_data="my_tickets"),
            InlineKeyboardButton("🎯 : نقاطي",       callback_data="my_points"),
        ],
        [
            InlineKeyboardButton("🔑 : مفتاح API",   callback_data="my_api_key"),
            InlineKeyboardButton("🤖 : الدعم الفني", callback_data="support_link"),
        ],
        [ch_btn],
        [ord_btn],
    ]

    # زر الموقع لو محدد
    if website_url:
        rows.append([InlineKeyboardButton("🌐 : الموقع الإلكتروني", url=website_url)])

    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  الفئات
# ══════════════════════════════════════════════════════════════

def platforms_list_kb(platforms: list) -> InlineKeyboardMarkup:
    """قائمة المنصات عند ضغط 'بدء طلبية رشق جديدة'."""
    buttons = [
        InlineKeyboardButton(
            f"{p['emoji']} {p['name']}",
            callback_data=f"platform_{p['id']}"
        )
        for p in platforms
    ]
    rows = _build_grid(buttons, cols=2)
    rows.append([InlineKeyboardButton("🎁 الخدمات المجانية", callback_data="free_services")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  شحن الألعاب
# ══════════════════════════════════════════════════════════════

def game_apps_kb(apps: list) -> InlineKeyboardMarkup:
    """قائمة تطبيقات الألعاب."""
    rows = [
        [InlineKeyboardButton(
            f"{a['emoji']} {a['name']}",
            callback_data=f"game_app_{a['id']}"
        )]
        for a in apps
    ]
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def game_packages_kb(packages: list, app_id: int) -> InlineKeyboardMarkup:
    """قائمة الباقات لتطبيق معيّن."""
    rows = [
        [InlineKeyboardButton(
            f"🔹 {p['name']} — ${p['price']:.2f}",
            callback_data=f"game_pkg_{p['id']}"
        )]
        for p in packages
    ]
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="game_charge")])
    return InlineKeyboardMarkup(rows)


def game_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    """تأكيد/إلغاء طلب شحن اللعبة."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد الطلب", callback_data=f"game_confirm_{order_id}"),
            InlineKeyboardButton("❌ إلغاء",       callback_data="game_cancel"),
        ],
    ])


def admin_approve_game_kb(order_id: int) -> InlineKeyboardMarkup:
    """أزرار الأدمن لقبول/رفض طلب شحن اللعبة."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ قبول الطلب",  callback_data=f"game_approve_{order_id}"),
            InlineKeyboardButton("❌ رفض الطلب",   callback_data=f"game_reject_{order_id}"),
        ],
    ])


def admin_approve_vodafone_kb(charge_id: int) -> InlineKeyboardMarkup:
    """أزرار الأدمن لقبول/رفض شحن فودافون."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ قبول وشحن الرصيد", callback_data=f"vod_approve_{charge_id}"),
            InlineKeyboardButton("❌ رفض",              callback_data=f"vod_reject_{charge_id}"),
        ],
    ])


def admin_approve_binance_kb(order_id: str, uid: int) -> InlineKeyboardMarkup:
    """أزرار الأدمن لقبول/رفض شحن Binance Pay."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ قبول وإدخال المبلغ", callback_data=f"binance_approve_{order_id}_{uid}"),
            InlineKeyboardButton("❌ رفض",                callback_data=f"binance_reject_{order_id}_{uid}"),
        ],
    ])


# ══════════════════════════════════════════════════════════════
#  الخدمات
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  الفئات
# ══════════════════════════════════════════════════════════════

def categories_kb(platform_id: int, categories: list) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            f"{c['emoji']} {c['name']}",
            callback_data=f"category_{c['id']}"
        )
        for c in categories
    ]
    rows = _build_grid(buttons, cols=2)
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="smm_platforms")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  الخدمات
# ══════════════════════════════════════════════════════════════

def services_kb(category_id: int, services: list,
                page: int = 0) -> InlineKeyboardMarkup:
    """قائمة خدمات مع صفحات (10 خدمات/صفحة)."""
    per_page = 10
    start = page * per_page
    chunk = services[start:start + per_page]
    rows = [
        [InlineKeyboardButton(
            f"🔹 {s['name']}",
            callback_data=f"service_{s['id']}"
        )]
        for s in chunk
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"svc_page_{category_id}_{page-1}"))
    if start + per_page < len(services):
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"svc_page_{category_id}_{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"platform_back_{category_id}")])
    return InlineKeyboardMarkup(rows)


def service_detail_kb(service_id: int) -> InlineKeyboardMarkup:
    """زر طلب الخدمة فقط."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 طلب الخدمة الآن", callback_data=f"order_svc_{service_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"service_back_{service_id}")],
    ])


def refill_confirm_kb(service_id: int) -> InlineKeyboardMarkup:
    """تأكيد طلب الرشق."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد الرشق", callback_data=f"refill_confirm_{service_id}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"service_{service_id}")],
    ])


def manual_order_kb(service_id: int) -> InlineKeyboardMarkup:
    """لوحة الطلب اليدوي."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء الطلب", callback_data=f"service_{service_id}")],
    ])


# ══════════════════════════════════════════════════════════════
#  الرصيد والشحن
# ══════════════════════════════════════════════════════════════

def balance_kb(bep20: bool, trc20: bool, vodafone: bool = True,
               stars: bool = False, binance: bool = False,
               ton: bool = False, trx: bool = False) -> InlineKeyboardMarkup:
    """أزرار طرق الدفع — تُعرض في شبكة 2 أعمدة حيثما أمكن."""
    rows = []

    # ── صف 1: نجوم + Binance ──
    row1 = []
    if stars:
        row1.append(InlineKeyboardButton("⭐ نجوم تيليغرام", callback_data="charge_stars"))
    if binance:
        row1.append(InlineKeyboardButton("💛 Binance Pay",   callback_data="charge_binance"))
    if row1:
        rows.append(row1)

    # ── صف 2: TON + TRX ──
    row2 = []
    if ton:
        row2.append(InlineKeyboardButton("💎 TON",           callback_data="charge_ton"))
    if trx:
        row2.append(InlineKeyboardButton("🔴 TRX",           callback_data="charge_trx"))
    if row2:
        rows.append(row2)

    # ── صف 3: BEP20 + TRC20 ──
    row3 = []
    if bep20:
        row3.append(InlineKeyboardButton("💎 USDT BEP20",    callback_data="charge_bep20"))
    if trc20:
        row3.append(InlineKeyboardButton("🟣 USDT TRC20",    callback_data="charge_trc20"))
    if row3:
        rows.append(row3)

    # ── صف 4: فودافون كاش ──
    if vodafone:
        rows.append([InlineKeyboardButton("📱 فودافون كاش",  callback_data="charge_vodafone")])

    # ── صف 5: كود هدية + رجوع ──
    rows.append([InlineKeyboardButton("🎁 كود هدية",         callback_data="charge_gift")])
    rows.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")])

    return InlineKeyboardMarkup(rows)


def crypto_pay_kb(network: str) -> InlineKeyboardMarkup:
    cb_sent = f"crypto_sent_{network}"
    cb_copy = f"crypto_copy_{network}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ أرسلت المبلغ", callback_data=cb_sent)],
        [InlineKeyboardButton("📋 نسخ العنوان",  callback_data=cb_copy)],
        [InlineKeyboardButton("🔙 رجوع",          callback_data="charge_back")],
    ])


def cancel_charge_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data="charge_cancel")],
    ])


# ══════════════════════════════════════════════════════════════
#  الطلب
# ══════════════════════════════════════════════════════════════

def order_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="order_cancel")],
    ])


def order_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد الطلب", callback_data="order_confirm"),
            InlineKeyboardButton("❌ إلغاء",        callback_data="order_cancel"),
        ],
    ])


# ══════════════════════════════════════════════════════════════
#  الاشتراك الإجباري
# ══════════════════════════════════════════════════════════════

def subscription_kb(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        title = ch.get("channel_title") or ch["channel_id"]
        cid = ch["channel_id"]
        link = f"https://t.me/{cid.lstrip('@')}"
        rows.append([InlineKeyboardButton(f"📢 {title}", url=link)])
    rows.append([InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  لوحة الأدمن — الرئيسية
# ══════════════════════════════════════════════════════════════

def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 المستخدمون",    callback_data="adm_users"),
            InlineKeyboardButton("📊 الإحصائيات",    callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton("📱 المنصات",       callback_data="adm_platforms"),
            InlineKeyboardButton("🛠 الخدمات",       callback_data="adm_services_home"),
        ],
        [
            InlineKeyboardButton("🎮 إدارة الألعاب", callback_data="adm_games"),
            InlineKeyboardButton("📋 الطلبات المعلقة", callback_data="adm_pending"),
        ],
        [
            InlineKeyboardButton("📈 نسبة الربح",     callback_data="adm_global_margin"),
            InlineKeyboardButton("🤝 نظام الإحالة",   callback_data="adm_referral"),
        ],
        [
            InlineKeyboardButton("🎁 أكواد الهدايا", callback_data="adm_gifts"),
            InlineKeyboardButton("💳 إعدادات الدفع",  callback_data="adm_payment"),
        ],
        [
            InlineKeyboardButton("📢 القنوات والإعدادات", callback_data="adm_channels"),
            InlineKeyboardButton("🔒 اشتراك إجباري",      callback_data="adm_forced"),
        ],
        [
            InlineKeyboardButton("👑 إدارة الأدمنز",  callback_data="adm_admins"),
            InlineKeyboardButton("📣 رسالة جماعية",   callback_data="adm_broadcast"),
        ],
        [
            InlineKeyboardButton("💾 نسخة احتياطية",      callback_data="adm_backup"),
            InlineKeyboardButton("📤 رفع نسخة احتياطية",  callback_data="adm_restore_prompt"),
        ],
        [
            InlineKeyboardButton("🎁 الخدمات المجانية", callback_data="adm_free"),
        ],
        [
            InlineKeyboardButton("🎫 تذاكر الدعم",    callback_data="adm_tickets"),
            InlineKeyboardButton("📦 طلبات معلقة +24h", callback_data="adm_pending_smm"),
        ],
        [
            InlineKeyboardButton("📅 التقرير اليومي",   callback_data="adm_daily_report"),
            InlineKeyboardButton("⚙️ إعدادات المميزات", callback_data="adm_features"),
        ],
    ])


def admin_admins_kb(admins: list) -> InlineKeyboardMarkup:
    """لوحة إدارة الأدمنز المتعددين."""
    rows = []
    for adm in admins:
        name = f"@{adm['username']}" if adm.get("username") else str(adm["tg_id"])
        rows.append([InlineKeyboardButton(
            f"🗑 {name} ({adm['tg_id']})",
            callback_data=f"adm_del_admin_{adm['tg_id']}"
        )])
    rows.append([InlineKeyboardButton("➕ إضافة أدمن جديد", callback_data="adm_add_admin")])
    rows.append([InlineKeyboardButton("🔙 رجوع",            callback_data="adm_main")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  أدمن — المستخدمون
# ══════════════════════════════════════════════════════════════

def admin_user_actions_kb(tg_id: int, is_banned: bool, is_vip: bool = False) -> InlineKeyboardMarkup:
    ban_text = "🔓 فك الحظر" if is_banned else "🚫 حظر"
    ban_cb   = f"adm_unban_{tg_id}" if is_banned else f"adm_ban_{tg_id}"
    vip_text = "👑 إلغاء VIP" if is_vip else "👑 تعيين VIP"
    vip_cb   = f"adm_vip_remove_{tg_id}" if is_vip else f"adm_vip_set_{tg_id}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ إضافة رصيد", callback_data=f"adm_add_bal_{tg_id}"),
            InlineKeyboardButton("➖ خصم رصيد",  callback_data=f"adm_dec_bal_{tg_id}"),
        ],
        [
            InlineKeyboardButton(vip_text, callback_data=vip_cb),
            InlineKeyboardButton(ban_text, callback_data=ban_cb),
        ],
        [InlineKeyboardButton("🚫 حظر خدمات", callback_data=f"adm_block_svc_{tg_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm_users")],
    ])


# ══════════════════════════════════════════════════════════════
#  أدمن — المنصات
# ══════════════════════════════════════════════════════════════

def admin_platforms_kb(platforms: list) -> InlineKeyboardMarkup:
    rows = []
    for p in platforms:
        status = "✅" if p["is_active"] else "❌"
        rows.append([
            InlineKeyboardButton(
                f"{status} {p['emoji']} {p['name']}",
                callback_data=f"adm_platform_{p['id']}"
            )
        ])
    rows.append([InlineKeyboardButton("➕ إضافة منصة", callback_data="adm_add_platform")])
    rows.append([InlineKeyboardButton("🔙 رجوع",       callback_data="adm_main")])
    return InlineKeyboardMarkup(rows)


def admin_platform_actions_kb(pid: int, is_active: bool) -> InlineKeyboardMarkup:
    tog = "❌ إخفاء" if is_active else "✅ إظهار"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 الفئات", callback_data=f"adm_cats_{pid}")],
        [
            InlineKeyboardButton(tog,           callback_data=f"adm_tog_platform_{pid}"),
            InlineKeyboardButton("🗑 حذف",      callback_data=f"adm_del_platform_{pid}"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm_platforms")],
    ])


# ══════════════════════════════════════════════════════════════
#  أدمن — الفئات
# ══════════════════════════════════════════════════════════════

def admin_categories_kb(platform_id: int, categories: list) -> InlineKeyboardMarkup:
    rows = []
    for c in categories:
        status = "✅" if c["is_active"] else "❌"
        rows.append([
            InlineKeyboardButton(
                f"{status} {c['emoji']} {c['name']}",
                callback_data=f"adm_cat_{c['id']}"
            )
        ])
    rows.append([InlineKeyboardButton("➕ إضافة فئة", callback_data=f"adm_add_cat_{platform_id}")])
    rows.append([InlineKeyboardButton("🔙 رجوع",      callback_data=f"adm_platform_{platform_id}")])
    return InlineKeyboardMarkup(rows)


def admin_cat_actions_kb(cid: int, is_active: bool, pid: int) -> InlineKeyboardMarkup:
    tog = "❌ إخفاء" if is_active else "✅ إظهار"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 الخدمات", callback_data=f"adm_svcs_{cid}")],
        [
            InlineKeyboardButton(tog,          callback_data=f"adm_tog_cat_{cid}"),
            InlineKeyboardButton("🗑 حذف",     callback_data=f"adm_del_cat_{cid}_{pid}"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_cats_{pid}")],
    ])


# ══════════════════════════════════════════════════════════════
#  أدمن — الخدمات
# ══════════════════════════════════════════════════════════════

def admin_services_kb(category_id: int, services: list) -> InlineKeyboardMarkup:
    rows = []
    for s in services:
        status = "✅" if s["is_active"] else "❌"
        rows.append([
            InlineKeyboardButton(
                f"{status} {s['name'][:30]}",
                callback_data=f"adm_svc_{s['id']}"
            )
        ])
    rows.append([
        InlineKeyboardButton("➕ إضافة خدمة", callback_data=f"adm_show_add_svc_{category_id}")
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_cat_{category_id}")])
    return InlineKeyboardMarkup(rows)


def admin_svc_actions_kb(sid: int, is_active: bool, cid: int) -> InlineKeyboardMarkup:
    tog = "❌ إخفاء" if is_active else "✅ إظهار"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(tog,         callback_data=f"adm_tog_svc_{sid}"),
            InlineKeyboardButton("🗑 حذف",    callback_data=f"adm_del_svc_{sid}_{cid}"),
        ],
        [
            InlineKeyboardButton("✏️ تعديل الاسم",  callback_data=f"adm_edit_svc_name_{sid}_{cid}"),
            InlineKeyboardButton("💲 تعديل السعر",  callback_data=f"adm_edit_svc_price_{sid}_{cid}"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_svcs_{cid}")],
    ])


def admin_quick_add_svc_kb(cid: int) -> InlineKeyboardMarkup:
    """لوحة إضافة خدمة سريعة بالـ ID أو تصفح."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 إضافة بـ ID مباشرة", callback_data=f"adm_quick_add_{cid}")],
        [InlineKeyboardButton("📋 تصفح قائمة API",     callback_data=f"adm_add_svc_{cid}")],
        [InlineKeyboardButton("🔙 رجوع",               callback_data=f"adm_svcs_{cid}")],
    ])


def admin_global_margin_kb() -> InlineKeyboardMarkup:
    """لوحة تغيير نسبة الربح الشاملة."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 تغيير نسبة الربح لكل الخدمات", callback_data="adm_global_margin")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")],
    ])


def admin_api_services_kb(services: list, category_id: int,
                          page: int = 0) -> InlineKeyboardMarkup:
    """قائمة خدمات API للاختيار منها."""
    per_page = 8
    start = page * per_page
    chunk = services[start:start + per_page]
    rows = [
        [InlineKeyboardButton(
            f"{s.get('name', '')[:40]}",
            callback_data=f"adm_pick_svc_{category_id}_{s['service']}"
        )]
        for s in chunk
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"adm_api_pg_{category_id}_{page-1}"))
    if start + per_page < len(services):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"adm_api_pg_{category_id}_{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"adm_svcs_{category_id}")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  أدمن — أكواد الهدايا
# ══════════════════════════════════════════════════════════════

def admin_gifts_kb(codes: list) -> InlineKeyboardMarkup:
    rows = []
    for c in codes:
        rows.append([
            InlineKeyboardButton(
                f"🎁 {c['code']} | ${c['amount']} | {c['current_uses']}/{c['max_uses']}",
                callback_data=f"adm_revoke_{c['code']}"
            )
        ])
    rows.append([InlineKeyboardButton("➕ إنشاء كود جديد", callback_data="adm_new_gift")])
    rows.append([InlineKeyboardButton("🔙 رجوع",           callback_data="adm_main")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  أدمن — الدفع
# ══════════════════════════════════════════════════════════════

def admin_payment_kb(bep20_on: bool, trc20_on: bool,
                     stars_on: bool = False, binance_on: bool = False,
                     ton_on: bool = False, trx_on: bool = False,
                     vod_auto_on: bool = False) -> InlineKeyboardMarkup:
    def _tog(label, on): return f"🔴 إيقاف {label}" if on else f"🟢 تفعيل {label}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_tog("نجوم ⭐", stars_on),   callback_data="adm_tog_stars"),
            InlineKeyboardButton(_tog("Binance 💛", binance_on), callback_data="adm_tog_binance"),
        ],
        [
            InlineKeyboardButton("⭐ إعدادات نجوم تيليغرام", callback_data="adm_cfg_stars"),
            InlineKeyboardButton("💛 إعدادات Binance Pay",   callback_data="adm_cfg_binance"),
        ],
        [
            InlineKeyboardButton(_tog("TON 💎", ton_on), callback_data="adm_tog_ton"),
            InlineKeyboardButton(_tog("TRX 🔴", trx_on), callback_data="adm_tog_trx"),
        ],
        [
            InlineKeyboardButton("💎 إعدادات TON", callback_data="adm_cfg_ton"),
            InlineKeyboardButton("🔴 إعدادات TRX", callback_data="adm_cfg_trx"),
        ],
        [
            InlineKeyboardButton(_tog("BEP20 💎", bep20_on), callback_data="adm_tog_bep20"),
            InlineKeyboardButton(_tog("TRC20 🟣", trc20_on), callback_data="adm_tog_trc20"),
        ],
        [
            InlineKeyboardButton("💎 إعدادات BEP20", callback_data="adm_cfg_bep20"),
            InlineKeyboardButton("🟣 إعدادات TRC20", callback_data="adm_cfg_trc20"),
        ],
        [
            InlineKeyboardButton(_tog("فودافون كاش تلقائي 📱", vod_auto_on),
                                 callback_data="adm_tog_vod_auto"),
        ],
        [
            InlineKeyboardButton("📱 إعدادات فودافون كاش", callback_data="adm_cfg_vod_auto"),
            InlineKeyboardButton("📞 رقم فودافون",          callback_data="adm_set_vodafone"),
        ],
        [InlineKeyboardButton("🔙 رجوع",             callback_data="adm_main")],
    ])


def admin_ton_cfg_kb(address: str, min_a: str) -> InlineKeyboardMarkup:
    short = address[:20] + "..." if len(address) > 20 else address or "غير محدد"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📍 العنوان: {short}", callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل عنوان TON",          callback_data="adm_set_ton_addr")],
        [InlineKeyboardButton(f"📉 الحد الأدنى: {min_a} TON", callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل الحد الأدنى",         callback_data="adm_set_ton_min")],
        [InlineKeyboardButton("🔙 رجوع",                      callback_data="adm_payment")],
    ])


def admin_trx_cfg_kb(address: str, min_a: str) -> InlineKeyboardMarkup:
    short = address[:20] + "..." if len(address) > 20 else address or "غير محدد"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📍 العنوان: {short}", callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل عنوان TRX",           callback_data="adm_set_trx_addr")],
        [InlineKeyboardButton(f"📉 الحد الأدنى: {min_a} TRX",  callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل الحد الأدنى",          callback_data="adm_set_trx_min")],
        [InlineKeyboardButton("🔙 رجوع",                       callback_data="adm_payment")],
    ])


def admin_vod_auto_cfg_kb(user_id: str, panel_id: str, min_egp: str) -> InlineKeyboardMarkup:
    """لوحة إعدادات فودافون كاش التلقائي عبر autocash."""
    uid_short = (user_id[:15] + "...") if len(user_id) > 15 else (user_id or "غير محدد")
    pid_short = (panel_id[:15] + "...") if len(panel_id) > 15 else (panel_id or "غير محدد")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🆔 User ID: {uid_short}",  callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل autocash User ID",  callback_data="adm_set_autocash_uid")],
        [InlineKeyboardButton(f"🆔 Panel ID: {pid_short}", callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل autocash Panel ID", callback_data="adm_set_autocash_pid")],
        [InlineKeyboardButton(f"📉 الحد الأدنى: {min_egp} جنيه", callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل الحد الأدنى (جنيه)", callback_data="adm_set_vod_min_egp")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm_payment")],
    ])


def admin_bep20_cfg_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 تعديل العنوان",     callback_data="adm_set_bep20_addr")],
        [InlineKeyboardButton("💵 تعديل الحد الأدنى", callback_data="adm_set_bep20_min")],
        [InlineKeyboardButton("💱 تعديل سعر الصرف",  callback_data="adm_set_bep20_rate")],
        [InlineKeyboardButton("🔙 رجوع",              callback_data="adm_payment")],
    ])


def admin_trc20_cfg_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 تعديل API Key",     callback_data="adm_set_trc20_key")],
        [InlineKeyboardButton("📍 تعديل العنوان",     callback_data="adm_set_trc20_addr")],
        [InlineKeyboardButton("💵 تعديل الحد الأدنى", callback_data="adm_set_trc20_min")],
        [InlineKeyboardButton("💱 تعديل سعر الصرف",  callback_data="adm_set_trc20_rate")],
        [InlineKeyboardButton("🔙 رجوع",              callback_data="adm_payment")],
    ])


def admin_stars_cfg_kb(rate: str, min_usd: str = "1") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💱 سعر الصرف: {rate} نجمة = $1", callback_data="noop")],
        [InlineKeyboardButton(f"📉 الحد الأدنى: ${min_usd}",      callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل عدد النجوم لكل $1",       callback_data="adm_set_stars_rate")],
        [InlineKeyboardButton("✏️ تعديل الحد الأدنى (بالدولار)",  callback_data="adm_set_stars_min")],
        [InlineKeyboardButton("🔙 رجوع",                           callback_data="adm_payment")],
    ])


def admin_binance_cfg_kb(pay_id: str, has_api: bool) -> InlineKeyboardMarkup:
    api_status = "✅ API مضبوط" if has_api else "⚠️ API غير مضبوط (يدوي)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🆔 Pay ID: {pay_id or 'غير محدد'}", callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل Pay ID",         callback_data="adm_set_binance_id")],
        [InlineKeyboardButton(f"🔑 {api_status}",         callback_data="noop")],
        [InlineKeyboardButton("✏️ تعديل API Key",         callback_data="adm_set_binance_key")],
        [InlineKeyboardButton("✏️ تعديل API Secret",      callback_data="adm_set_binance_secret")],
        [InlineKeyboardButton("🔙 رجوع",                  callback_data="adm_payment")],
    ])


# ══════════════════════════════════════════════════════════════
#  أدمن — القنوات والاشتراك الإجباري
# ══════════════════════════════════════════════════════════════

def admin_channels_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 قناة المستخدمين الجدد",    callback_data="adm_set_notif_ch")],
        [InlineKeyboardButton("📦 قناة الطلبات (ID للإرسال)", callback_data="adm_set_orders_ch")],
        [InlineKeyboardButton("📊 قناة تقارير الاسترداد",    callback_data="adm_set_checker_ch")],
        [InlineKeyboardButton("🆕 قناة تحديثات الخدمات",     callback_data="adm_set_updates_ch")],
        [InlineKeyboardButton("🔗 رابط القناة الرسمية",       callback_data="adm_set_official_ch")],
        [InlineKeyboardButton("🎬 رابط قناة الطلبات",         callback_data="adm_set_orders_ch_link")],
        [InlineKeyboardButton("🤖 يوزر الدعم الفني",          callback_data="adm_set_support")],
        [InlineKeyboardButton("📕 نص التعليمات",              callback_data="adm_set_instructions")],
        [InlineKeyboardButton("🌐 رابط الموقع الإلكتروني",    callback_data="adm_set_website_url")],
        [InlineKeyboardButton("🔙 رجوع",                      callback_data="adm_main")],
    ])


def admin_forced_kb(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        title    = ch.get("channel_title") or ch["channel_id"]
        row_id   = ch["id"]
        max_m    = ch.get("max_members", 0)
        cur_m    = ch.get("current_count", 0)
        limit_str = f" [{cur_m}/{max_m}]" if max_m > 0 else ""
        rows.append([
            InlineKeyboardButton(
                f"🗑 {title}{limit_str}",
                callback_data=f"adm_del_forced_{row_id}"
            )
        ])
    rows.append([InlineKeyboardButton("➕ إضافة قناة", callback_data="adm_add_forced")])
    rows.append([InlineKeyboardButton("🔙 رجوع",       callback_data="adm_main")])
    return InlineKeyboardMarkup(rows)


def skip_kb(skip_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ تخطي (دائمة)", callback_data=skip_callback),
    ]])


# ══════════════════════════════════════════════════════════════
#  أدمن — إدارة الألعاب
# ══════════════════════════════════════════════════════════════

def admin_games_kb(apps: list) -> InlineKeyboardMarkup:
    rows = []
    for a in apps:
        tog = "🔴 إيقاف" if a["is_active"] else "🟢 تفعيل"
        rows.append([
            InlineKeyboardButton(
                f"{a['emoji']} {a['name']}",
                callback_data=f"adm_game_{a['id']}"
            ),
            InlineKeyboardButton(tog, callback_data=f"adm_tog_game_{a['id']}"),
        ])
    rows.append([InlineKeyboardButton("➕ إضافة تطبيق", callback_data="adm_add_game")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")])
    return InlineKeyboardMarkup(rows)


def admin_game_app_kb(app_id: int, packages: list) -> InlineKeyboardMarkup:
    rows = []
    for p in packages:
        rows.append([
            InlineKeyboardButton(
                f"🔹 {p['name']} — ${p['price']:.2f}",
                callback_data=f"adm_game_pkg_{p['id']}"
            ),
            InlineKeyboardButton("🗑 حذف", callback_data=f"adm_del_game_pkg_{p['id']}_{app_id}"),
        ])
    rows.append([InlineKeyboardButton("➕ إضافة باقة", callback_data=f"adm_add_game_pkg_{app_id}")])
    rows.append([
        InlineKeyboardButton("🗑 حذف التطبيق", callback_data=f"adm_del_game_{app_id}"),
        InlineKeyboardButton("🔙 رجوع", callback_data="adm_games"),
    ])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  عام
# ══════════════════════════════════════════════════════════════

def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="menu_main")]
    ])


def cancel_kb(cb: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data=cb)]
    ])


def my_tickets_kb(tickets: list) -> InlineKeyboardMarkup:
    rows = []
    for t in tickets:
        st = "✅" if t["status"] == "closed" else "🔴"
        rows.append([InlineKeyboardButton(
            f"{st} #{t['id']} — {t['message'][:30]}...",
            callback_data=f"ticket_view_{t['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ تذكرة جديدة", callback_data="ticket_new")])
    rows.append([InlineKeyboardButton("🔙 رجوع",        callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def adm_tickets_kb(tickets: list) -> InlineKeyboardMarkup:
    rows = []
    for t in tickets:
        rows.append([InlineKeyboardButton(
            f"🔴 #{t['id']} — {t['message'][:35]}",
            callback_data=f"adm_ticket_{t['id']}"
        )])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")])
    return InlineKeyboardMarkup(rows)


def adm_features_kb(settings: dict) -> InlineKeyboardMarkup:
    """لوحة إعدادات الميزات."""
    pts_on    = settings.get("points_enabled", "0") == "1"
    lb_on     = settings.get("low_balance_alert", "0") == "1"
    cur2_on   = settings.get("second_currency_enabled", "0") == "1"
    rep_on    = settings.get("daily_report_enabled", "0") == "1"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"🎯 نظام النقاط: {'✅ مفعل' if pts_on else '❌ معطل'}",
            callback_data="adm_feat_toggle_points"
        )],
        [InlineKeyboardButton(
            f"🔔 تنبيه الرصيد المنخفض: {'✅' if lb_on else '❌'}",
            callback_data="adm_feat_toggle_low_balance"
        )],
        [
            InlineKeyboardButton("💲 حد الرصيد المنخفض", callback_data="adm_feat_set_low_bal"),
            InlineKeyboardButton("🎯 نقاط لكل $1",        callback_data="adm_feat_set_pts_rate"),
        ],
        [
            InlineKeyboardButton("🏆 نقاط للاسترداد",    callback_data="adm_feat_set_pts_redeem"),
            InlineKeyboardButton("💰 قيمة الاسترداد $",  callback_data="adm_feat_set_pts_value"),
        ],
        [InlineKeyboardButton(
            f"🌐 العملة الثانية: {'✅' if cur2_on else '❌'}",
            callback_data="adm_feat_toggle_currency2"
        )],
        [
            InlineKeyboardButton("🌐 اسم العملة",      callback_data="adm_feat_set_cur2_name"),
            InlineKeyboardButton("💱 سعر الصرف",       callback_data="adm_feat_set_cur2_rate"),
        ],
        [InlineKeyboardButton(
            f"📅 التقرير اليومي: {'✅' if rep_on else '❌'}",
            callback_data="adm_feat_toggle_daily_report"
        )],
        [InlineKeyboardButton("⏰ وقت التقرير اليومي", callback_data="adm_feat_set_report_time")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")],
    ])
