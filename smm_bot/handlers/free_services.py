from utils.safe_send import safe_answer, safe_edit, safe_send
"""
╔══════════════════════════════════════════╗
║   الخدمات المجانية — free_services.py   ║
╚══════════════════════════════════════════╝
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from database import Database

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
#  Keyboards
# ══════════════════════════════════════════════════════════════

def free_services_list_kb(services: list) -> InlineKeyboardMarkup:
    rows = []
    for fs in services:
        rem     = fs.get("remaining_today", 0)
        locked  = fs.get("locked", False)
        name    = (fs.get("service_name") or "خدمة")[:30]
        if locked:
            lock_reason = fs.get("lock_reason", "")
            if lock_reason == "limit_reached":
                label = f"⏳ {name}  (انتهت المحاولات)"
            elif lock_reason.startswith("need_deposit"):
                _, req, cur = lock_reason.split(":")
                label = f"💳 {name}  (يتطلب ${float(req):.2f})"
            elif lock_reason == "not_selected":
                label = f"🔒 {name}  (مختارون فقط)"
            else:
                label = f"🔒 {name}"
        else:
            label = f"🎁 {name}  ({rem}/{fs['daily_limit']} متبقي)"
        rows.append([InlineKeyboardButton(label, callback_data=f"free_use_{fs['id']}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def adm_free_list_kb(services: list) -> InlineKeyboardMarkup:
    rows = []
    for fs in services:
        st   = "✅" if fs["is_active"] else "❌"
        name = (fs.get("service_name") or "خدمة")[:25]
        rows.append([InlineKeyboardButton(
            f"{st} {name}", callback_data=f"adm_free_{fs['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ إضافة خدمة مجانية", callback_data="adm_free_add")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_main")])
    return InlineKeyboardMarkup(rows)


def adm_free_detail_kb(fs: dict) -> InlineKeyboardMarkup:
    tog   = "❌ تعطيل" if fs["is_active"] else "✅ تفعيل"
    fs_id = fs["id"]
    mode  = fs["mode"]

    # الكميات الفعلية
    svc_min = fs.get("min_qty", 0)
    svc_max = fs.get("max_qty", 0)
    cur_min = fs.get("custom_min") or svc_min
    cur_max = fs.get("custom_max") or svc_max

    rows = [
        [InlineKeyboardButton(tog, callback_data=f"adm_free_tog_{fs_id}")],
        [
            InlineKeyboardButton(
                f"👥 {'✅ ' if mode=='all' else ''}الجميع",
                callback_data=f"adm_free_mode_{fs_id}_all"
            ),
            InlineKeyboardButton(
                f"💳 {'✅ ' if mode=='min_deposit' else ''}حد إيداع",
                callback_data=f"adm_free_mode_{fs_id}_min_deposit"
            ),
            InlineKeyboardButton(
                f"🔒 {'✅ ' if mode=='selected' else ''}مختارون",
                callback_data=f"adm_free_mode_{fs_id}_selected"
            ),
        ],
        [
            InlineKeyboardButton(f"📉 Min: {cur_min:,}", callback_data=f"adm_free_setmin_{fs_id}"),
            InlineKeyboardButton(f"📈 Max: {cur_max:,}", callback_data=f"adm_free_setmax_{fs_id}"),
        ],
        [InlineKeyboardButton("💲 تغيير الحد الأدنى للإيداع", callback_data=f"adm_free_setdep_{fs_id}")],
        [InlineKeyboardButton("🔢 تغيير المحاولات اليومية",   callback_data=f"adm_free_setlimit_{fs_id}")],
        [
            InlineKeyboardButton("➕ إضافة مستخدم", callback_data=f"adm_free_adduser_{fs_id}"),
            InlineKeyboardButton("➖ حذف مستخدم",   callback_data=f"adm_free_deluser_{fs_id}"),
        ],
        [InlineKeyboardButton("🗑 حذف هذه الخدمة", callback_data=f"adm_free_del_{fs_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm_free")],
    ]
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════
#  User Handlers
# ══════════════════════════════════════════════════════════════

async def free_services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    from utils.states import clear_user_state
    clear_user_state(context)

    db: Database = context.bot_data["db"]
    uid = update.effective_user.id

    services = db.get_free_services_for_user(uid)
    if not services:
        await safe_edit(query, 
            "🎁 <b>الخدمات المجانية</b>\n\n"
            "⚠️ لا توجد خدمات مجانية متاحة لك حالياً.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
            ]]),
            parse_mode="HTML",
        )
        return

    text = "🎁 <b>الخدمات المجانية</b>\n\nاختر الخدمة التي تريد استخدامها:"
    await safe_edit(query, 
        text,
        reply_markup=free_services_list_kb(services),
        parse_mode="HTML",
    )


async def free_use_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    db: Database = context.bot_data["db"]
    uid   = update.effective_user.id
    fs_id = int(query.data.split("_")[2])

    fs = db.get_free_service(fs_id)
    if not fs:
        await safe_answer(query, "❌ الخدمة غير موجودة!", show_alert=True)
        return

    # ── جلب الحالة مع lock_reason مباشرة ──
    result    = db.can_use_free_service(fs_id, uid)
    can       = result[0]
    remaining = result[1]
    reason    = result[2] if len(result) > 2 else ("ok" if can else "no_access")

    logger.info(f"[FREE] uid={uid} fs_id={fs_id} mode={fs.get('mode')} can={can} reason={reason} remaining={remaining}")

    if not can:
        if reason == "limit_reached":
            msg = (
                f"⏳ انتهت محاولاتك اليومية!\n\n"
                f"الحد اليومي: {fs['daily_limit']} محاولة\n"
                f"عد غداً للحصول على محاولات جديدة."
            )
        elif reason.startswith("need_deposit:"):
            _, required, current = reason.split(":")
            needed = float(required) - float(current)
            msg = (
                f"💳 هذه الخدمة تتطلب حداً أدنى من الإيداع!\n\n"
                f"✅ المطلوب:       ${float(required):.2f}\n"
                f"💰 إيداعك الحالي: ${float(current):.2f}\n\n"
                f"اشحن ${needed:.2f} إضافية للوصول لهذه الخدمة."
            )
        elif reason == "not_selected":
            msg = "🔒 هذه الخدمة متاحة لمستخدمين مختارين فقط.\nتواصل مع الأدمن للحصول على الوصول."
        else:
            msg = "❌ هذه الخدمة غير متاحة لك حالياً."

        await safe_answer(query, msg, show_alert=True)
        return

    await safe_answer(query)

    svc_min = fs.get("min_qty", 0)
    svc_max = fs.get("max_qty", 0)
    cur_min = fs.get("custom_min") or svc_min
    cur_max = fs.get("custom_max") or svc_max

    context.user_data["free_fs_id"]  = fs_id
    context.user_data["free_state"]  = "waiting_qty"
    context.user_data["free_svc"]    = fs
    context.user_data["free_min"]    = cur_min
    context.user_data["free_max"]    = cur_max

    await safe_edit(query, 
        f"🎁 <b>{fs['service_name']}</b>\n\n"
        f"📅 متبقي اليوم: <b>{remaining}</b> محاولة\n"
        f"📉 الكمية الدنيا:  <b>{cur_min:,}</b>\n"
        f"📈 الكمية القصوى: <b>{cur_max:,}</b>\n\n"
        "🔢 <b>أرسل الكمية المطلوبة:</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="free_services")
        ]]),
        parse_mode="HTML",
    )


async def free_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("free_state", "")
    if not state:
        return

    # لو المستخدم بعت رسالة مش في الوقت المناسب (مثلاً رجع من الخدمة وبعت حاجة تانية)
    # نتحقق إن الـ fs_id والـ svc لا تزال موجودة وصحيحة
    if state in ("waiting_qty", "waiting_link"):
        if not context.user_data.get("free_fs_id") or not context.user_data.get("free_svc"):
            context.user_data.pop("free_state", None)
            return

    db: Database = context.bot_data["db"]
    api          = context.bot_data.get("api")
    uid  = update.effective_user.id
    text = update.message.text.strip()

    # ── مرحلة ١: الكمية ──
    if state == "waiting_qty":
        fs_min = context.user_data.get("free_min", 0)
        fs_max = context.user_data.get("free_max", 0)

        if not text.isdigit():
            await update.message.reply_text(f"❌ أرسل رقماً صحيحاً بين {fs_min:,} و {fs_max:,}.")
            return

        qty = int(text)
        if qty < fs_min or qty > fs_max:
            await update.message.reply_text(
                f"❌ الكمية خارج النطاق المسموح!\n"
                f"الحد الأدنى: {fs_min:,} | الحد الأقصى: {fs_max:,}"
            )
            return

        context.user_data["free_qty"]   = qty
        context.user_data["free_state"] = "waiting_link"
        await update.message.reply_text(
            f"✅ الكمية: <b>{qty:,}</b>\n\n🔗 <b>أرسل الرابط الآن:</b>",
            parse_mode="HTML",
        )
        return

    # ── مرحلة ٢: الرابط ──
    if state == "waiting_link":
        fs_id = context.user_data.get("free_fs_id")
        fs    = context.user_data.get("free_svc")
        qty   = context.user_data.get("free_qty", 0)

        if not fs or not fs_id or not qty:
            context.user_data.pop("free_state", None)
            return

        can = db.can_use_free_service(fs_id, uid)[0]
        if not can:
            await update.message.reply_text("❌ لم تعد هذه الخدمة متاحة لك اليوم.")
            context.user_data.pop("free_state", None)
            return

        link = text
        svc_full   = db.get_service(fs["service_id"])
        api_svc_id = svc_full["api_service_id"] if svc_full else fs["service_id"]

        _FREE_KEYS = ("free_state","free_fs_id","free_svc","free_qty","free_min","free_max")
        _FREE_ERRORS = {
            "105": "هذه الخدمة غير متاحة حالياً، تواصل مع الأدمن.",
            "106": "الرصيد غير كافٍ لإتمام الطلب.",
            "110": "الرابط غير صحيح أو غير مدعوم.",
            "111": "الرابط غير صحيح، تأكد منه وأعد المحاولة.",
        }

        try:
            result       = await api.add_order(service=api_svc_id, link=link, quantity=qty)
            api_order_id = result.get("order")
            if not api_order_id:
                err_code = str(result.get("status", ""))
                err_msg  = _FREE_ERRORS.get(err_code, "حدث خطأ، تواصل مع الأدمن.")
                logger.error(f"[FREE] API error: {result}")
                for k in _FREE_KEYS: context.user_data.pop(k, None)
                await update.message.reply_text(f"⚠️ {err_msg}")
                return
        except Exception as e:
            logger.error(f"[FREE] exception: {e}")
            for k in _FREE_KEYS: context.user_data.pop(k, None)
            await update.message.reply_text("⚠️ تعذّر الاتصال بالخادم، حاول مرة أخرى.")
            return

        db.create_order(
            user_tg_id=uid,
            service_id=fs["service_id"],
            link=link,
            quantity=qty,
            price=0.0,
            api_order_id=str(api_order_id)
        )
        db.record_free_service_use(fs_id, uid)

        context.user_data.pop("free_state", None)
        context.user_data.pop("free_fs_id", None)
        context.user_data.pop("free_svc", None)
        context.user_data.pop("free_qty", None)
        context.user_data.pop("free_min", None)
        context.user_data.pop("free_max", None)

        await update.message.reply_text(
            f"✅ <b>تم إرسال طلبك المجاني!</b>\n\n"
            f"🆔 رقم الطلب: <code>{api_order_id}</code>\n"
            f"📦 {fs['service_name']}\n"
            f"🔢 الكمية: {qty:,}\n\n"
            f"سيتم إشعارك عند الاكتمال.",
            parse_mode="HTML",
        )


# ══════════════════════════════════════════════════════════════
#  Admin Handlers
# ══════════════════════════════════════════════════════════════

async def adm_free_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    services = db.get_free_services()
    await safe_edit(query, 
        "🎁 <b>إدارة الخدمات المجانية</b>",
        reply_markup=adm_free_list_kb(services),
        parse_mode="HTML",
    )


async def adm_free_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    # نجيب آخر رقم في الـ callback_data (يشتغل مع كل الـ patterns)
    parts = query.data.split("_")
    fs_id = next((int(p) for p in reversed(parts) if p.isdigit()), None)
    if not fs_id:
        await safe_answer(query, "❌ خطأ في البيانات!", show_alert=True)
        return
    fs = db.get_free_service(fs_id)
    if not fs:
        await safe_answer(query, "❌ غير موجودة!", show_alert=True)
        return

    mode_ar = {
        "all":         "الجميع",
        "min_deposit": f"حد إيداع ${fs['min_deposit']}",
        "selected":    "مستخدمون مختارون"
    }
    users   = db.get_free_service_allowed_users(fs_id) if fs["mode"] == "selected" else []
    svc_min = fs.get("min_qty", 0)
    svc_max = fs.get("max_qty", 0)
    cur_min = fs.get("custom_min") or svc_min
    cur_max = fs.get("custom_max") or svc_max

    text = (
        f"🎁 <b>{fs['service_name']}</b>\n\n"
        f"الحالة:             {'✅ مفعل' if fs['is_active'] else '❌ معطل'}\n"
        f"الوصول:            <b>{mode_ar.get(fs['mode'], fs['mode'])}</b>\n"
        f"المحاولات اليومية: <b>{fs['daily_limit']}</b>\n"
        f"الكمية Min:        <b>{cur_min:,}</b>  (أصلي: {svc_min:,})\n"
        f"الكمية Max:        <b>{cur_max:,}</b>  (أصلي: {svc_max:,})\n"
        + (f"المستخدمون:        <b>{len(users)}</b>\n" if users else "")
    )
    await safe_edit(query, text, reply_markup=adm_free_detail_kb(fs), parse_mode="HTML")


async def adm_free_tog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    fs_id = int(query.data.split("_")[3])
    fs    = db.get_free_service(fs_id)
    db.update_free_service(fs_id, is_active=0 if fs["is_active"] else 1)
    await adm_free_detail_callback(update, context)


async def adm_free_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    # adm_free_mode_{id}_{mode} — الـ mode ممكن يحتوي على _ مثل min_deposit
    parts = query.data.split("_")  # ["adm","free","mode","{id}","min","deposit"] أو ["adm","free","mode","{id}","all"]
    fs_id = int(parts[3])
    mode  = "_".join(parts[4:])    # يلم min_deposit صح
    db.update_free_service(fs_id, mode=mode)
    query.data = f"adm_free_{fs_id}"  # نصلح الـ data عشان detail يشتغل
    await adm_free_detail_callback(update, context)


async def adm_free_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    context.user_data["adm_free_state"] = "waiting_api_service_id"
    await safe_edit(query, 
        "🎁 <b>إضافة خدمة مجانية</b>\n\n"
        "أرسل <b>رقم الخدمة من موقع الـ API</b>\n"
        "(نفس الرقم الظاهر في قائمة الخدمات على الموقع):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="adm_free")
        ]]),
        parse_mode="HTML",
    )


async def adm_free_setmin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    fs_id = int(query.data.split("_")[3])
    fs    = context.bot_data["db"].get_free_service(fs_id)
    context.user_data["adm_free_state"] = f"waiting_min_{fs_id}"
    await safe_edit(query, 
        f"📉 أرسل الكمية الدنيا (Min) للخدمة المجانية:\n"
        f"الكمية الأصلية للخدمة: <b>{fs.get('min_qty',0):,}</b> — <b>{fs.get('max_qty',0):,}</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data=f"adm_free_{fs_id}")
        ]]),
        parse_mode="HTML",
    )


async def adm_free_setmax_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    fs_id = int(query.data.split("_")[3])
    fs    = context.bot_data["db"].get_free_service(fs_id)
    context.user_data["adm_free_state"] = f"waiting_max_{fs_id}"
    await safe_edit(query, 
        f"📈 أرسل الكمية القصوى (Max) للخدمة المجانية:\n"
        f"الكمية الأصلية للخدمة: <b>{fs.get('min_qty',0):,}</b> — <b>{fs.get('max_qty',0):,}</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data=f"adm_free_{fs_id}")
        ]]),
        parse_mode="HTML",
    )


async def adm_free_setdep_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    fs_id = int(query.data.split("_")[3])
    context.user_data["adm_free_state"] = f"waiting_dep_{fs_id}"
    await safe_edit(query, 
        "💲 أرسل الحد الأدنى للإيداع بالدولار (مثال: 0.5):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data=f"adm_free_{fs_id}")
        ]]),
    )


async def adm_free_setlimit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    fs_id = int(query.data.split("_")[3])
    context.user_data["adm_free_state"] = f"waiting_limit_{fs_id}"
    await safe_edit(query, 
        "🔢 أرسل عدد المحاولات اليومية (مثال: 5):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data=f"adm_free_{fs_id}")
        ]]),
    )


async def adm_free_adduser_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    fs_id = int(query.data.split("_")[3])
    context.user_data["adm_free_state"] = f"waiting_adduser_{fs_id}"
    await safe_edit(query, 
        "👤 أرسل الـ Telegram ID للمستخدم المراد إضافته:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data=f"adm_free_{fs_id}")
        ]]),
    )


async def adm_free_deluser_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    fs_id = int(query.data.split("_")[3])
    context.user_data["adm_free_state"] = f"waiting_deluser_{fs_id}"
    await safe_edit(query, 
        "👤 أرسل الـ Telegram ID للمستخدم المراد إزالته:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data=f"adm_free_{fs_id}")
        ]]),
    )


async def adm_free_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    db: Database = context.bot_data["db"]
    fs_id = int(query.data.split("_")[3])
    db.delete_free_service(fs_id)
    await adm_free_callback(update, context)


async def adm_free_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("adm_free_state", "")
    if not state:
        return

    db: Database = context.bot_data["db"]
    text = update.message.text.strip()

    if state == "waiting_api_service_id":
        if not text.isdigit():
            await update.message.reply_text("❌ أرسل رقماً صحيحاً.")
            return
        api_svc_id = int(text)

        # ── تحقق من الـ API أولاً ──
        api = context.bot_data.get("api")
        api_services = []
        try:
            api_services = await api.get_services() or []
        except Exception:
            pass

        api_svc_info = next((s for s in api_services if str(s.get("service")) == str(api_svc_id)), None)
        if not api_svc_info:
            await update.message.reply_text(
                f"❌ الخدمة رقم <b>{api_svc_id}</b> غير موجودة أو معطّلة على موقع الـ API.\n\n"
                "تأكد من الرقم الصحيح من قائمة الخدمات على الموقع.",
                parse_mode="HTML",
            )
            return

        # ── تحقق من الـ DB المحلي ──
        svc = db.get_service_by_api_id(api_svc_id)
        if not svc:
            await update.message.reply_text(
                f"⚠️ الخدمة <b>{api_svc_info.get('name', api_svc_id)}</b> موجودة على الـ API "
                f"لكن غير موجودة في البوت.\n\n"
                "اعمل Sync للخدمات أولاً من لوحة الأدمن.",
                parse_mode="HTML",
            )
            return

        existing = db.get_free_services()
        if any(fs["service_id"] == svc["id"] for fs in existing):
            await update.message.reply_text(
                f"⚠️ الخدمة <b>{svc['name']}</b> مضافة مسبقاً!",
                parse_mode="HTML",
            )
            context.user_data.pop("adm_free_state", None)
            return

        db.add_free_service(svc["id"])
        context.user_data.pop("adm_free_state", None)
        await update.message.reply_text(
            f"✅ تمت إضافة <b>{svc['name']}</b> للخدمات المجانية!\n\n"
            f"🆔 API ID: <code>{api_svc_id}</code>\n"
            f"📉 Min: {svc['min_qty']:,} | 📈 Max: {svc['max_qty']:,}\n\n"
            "يمكنك الآن تخصيص الإعدادات من قائمة الخدمات المجانية.",
            parse_mode="HTML",
        )
        return

    elif state.startswith("waiting_min_"):
        fs_id = int(state.split("_")[2])
        if not text.isdigit():
            await update.message.reply_text("❌ أرسل رقماً صحيحاً.")
            return
        db.update_free_service(fs_id, custom_max=int(text))
        context.user_data.pop("adm_free_state", None)
        await update.message.reply_text(f"✅ تم تحديث الكمية القصوى (Max) إلى {int(text):,}.")

    elif state.startswith("waiting_dep_"):
        fs_id = int(state.split("_")[2])
        try:
            val = float(text)
            db.update_free_service(fs_id, min_deposit=val)
            context.user_data.pop("adm_free_state", None)
            await update.message.reply_text(f"✅ تم تحديث الحد الأدنى للإيداع إلى ${val}.")
        except ValueError:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 0.5")

    elif state.startswith("waiting_limit_"):
        fs_id = int(state.split("_")[2])
        if not text.isdigit():
            await update.message.reply_text("❌ أرسل رقماً صحيحاً.")
            return
        db.update_free_service(fs_id, daily_limit=int(text))
        context.user_data.pop("adm_free_state", None)
        await update.message.reply_text(f"✅ تم تحديث المحاولات اليومية إلى {text}.")

    elif state.startswith("waiting_adduser_"):
        fs_id = int(state.split("_")[2])
        if not text.lstrip("-").isdigit():
            await update.message.reply_text("❌ أرسل Telegram ID صحيح.")
            return
        db.add_free_service_user(fs_id, int(text))
        context.user_data.pop("adm_free_state", None)
        await update.message.reply_text(f"✅ تمت إضافة المستخدم {text}.")

    elif state.startswith("waiting_deluser_"):
        fs_id = int(state.split("_")[2])
        if not text.lstrip("-").isdigit():
            await update.message.reply_text("❌ أرسل Telegram ID صحيح.")
            return
        db.remove_free_service_user(fs_id, int(text))
        context.user_data.pop("adm_free_state", None)
        await update.message.reply_text(f"✅ تمت إزالة المستخدم {text}.")


# ══════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════

def register_free_services(app, is_admin_func):
    # User
    app.add_handler(CallbackQueryHandler(free_services_callback, pattern=r"^free_services$"))
    app.add_handler(CallbackQueryHandler(free_use_callback,      pattern=r"^free_use_\d+$"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        free_text_handler
    ), group=5)

    # Admin
    app.add_handler(CallbackQueryHandler(adm_free_callback,        pattern=r"^adm_free$"))
    app.add_handler(CallbackQueryHandler(adm_free_detail_callback, pattern=r"^adm_free_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_tog_callback,    pattern=r"^adm_free_tog_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_mode_callback,   pattern=r"^adm_free_mode_\d+_\w+$"))
    app.add_handler(CallbackQueryHandler(adm_free_add_callback,    pattern=r"^adm_free_add$"))
    app.add_handler(CallbackQueryHandler(adm_free_setmin_callback,  pattern=r"^adm_free_setmin_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_setmax_callback,  pattern=r"^adm_free_setmax_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_setdep_callback,  pattern=r"^adm_free_setdep_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_setlimit_callback,pattern=r"^adm_free_setlimit_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_adduser_callback, pattern=r"^adm_free_adduser_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_deluser_callback, pattern=r"^adm_free_deluser_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_free_del_callback,     pattern=r"^adm_free_del_\d+$"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        adm_free_text_handler
    ), group=6)

