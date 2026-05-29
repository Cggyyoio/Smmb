"""
📱 فودافون كاش تلقائي — vodafone_cash_pay.py
يستخدم مكتبة autocash للدفع التلقائي
"""

import logging
import asyncio
from typing import Optional
from autocash import AutoCash

from database import Database

logger = logging.getLogger(__name__)


class VodafoneCashHandler:
    """
    يتحكم في عمليات دفع فودافون كاش التلقائي عبر مكتبة autocash.
    البيانات تُخزَّن في جدول الإعدادات (settings) في قاعدة البيانات:
        autocash_user_id   → user_id  الخاص بك في لوحة AutoCash
        autocash_panel_id  → panel_id الخاص بك في لوحة AutoCash
        vod_egp_rate       → سعر صرف الجنيه مقابل الدولار  (مثال: 50 = 50 ج/$)
        vod_min_egp        → الحد الأدنى للشحن بالجنيه     (مثال: 20)
    """

    def __init__(self, db: Database, bot):
        self.db  = db
        self.bot = bot

    # ──────────────────────────────────────────────
    #  مساعدات داخلية
    # ──────────────────────────────────────────────

    def _get_client(self) -> Optional[AutoCash]:
        """يُنشئ كائن AutoCash من الإعدادات المخزَّنة، أو None إن لم تكتمل."""
        user_id  = self.db.get_setting("autocash_user_id",  "")
        panel_id = self.db.get_setting("autocash_panel_id", "")
        if not user_id or not panel_id:
            return None
        return AutoCash(user_id, panel_id)

    def is_enabled(self) -> bool:
        """هل فودافون كاش التلقائي مُفعَّل ومُهيَّأ؟"""
        client = self._get_client()
        if not client:
            return False
        return self.db.get_setting("pay_vod_auto", "0") == "1"

    def get_rate(self) -> float:
        """سعر الصرف: كم جنيه = 1 دولار."""
        try:
            return float(self.db.get_setting("vod_egp_rate", "50"))
        except ValueError:
            return 50.0

    def get_min_egp(self) -> float:
        """الحد الأدنى للشحن بالجنيه."""
        try:
            return float(self.db.get_setting("vod_min_egp", "20"))
        except ValueError:
            return 20.0

    def egp_to_usd(self, egp: float) -> float:
        """تحويل من جنيه إلى دولار باستخدام سعر الصرف المحدد."""
        rate = self.get_rate()
        if rate <= 0:
            return 0.0
        return round(egp / rate, 4)

    # ──────────────────────────────────────────────
    #  إنشاء رابط الدفع
    # ──────────────────────────────────────────────

    def create_payment_link(self, user_tg_id: int) -> Optional[str]:
        """
        يُنشئ رابط دفع فودافون كاش لمستخدم معيَّن.
        extra = معرَّف تيليغرام الخاص بالمستخدم (لربط العملية به).
        """
        client = self._get_client()
        if not client:
            return None
        try:
            link = client.create_payment_link(extra=str(user_tg_id))
            return link
        except Exception as e:
            logger.error(f"[VOD-AUTO] خطأ في إنشاء رابط الدفع: {e}")
            return None

    # ──────────────────────────────────────────────
    #  التحقق من الدفع
    # ──────────────────────────────────────────────

    def check_payment(self, phone: str, amount_egp: float) -> dict:
        """
        يتحقق من اكتمال عملية الدفع.
        يعيد dict بالمفاتيح: status (bool), message (str), key (str|None)
        """
        client = self._get_client()
        if not client:
            return {"status": False, "message": "AutoCash غير مُهيَّأ.", "key": None}
        try:
            result = client.check_payment(phone=phone, amount=int(amount_egp))
            return result
        except Exception as e:
            logger.error(f"[VOD-AUTO] خطأ في التحقق من الدفع: {e}")
            return {"status": False, "message": str(e), "key": None}

    # ──────────────────────────────────────────────
    #  صفحة الدفع — رسالة المستخدم
    # ──────────────────────────────────────────────

    async def show_pay_page(self, chat_id: int, user_tg_id: int):
        """يعرض للمستخدم رابط الدفع التلقائي مع التعليمات."""
        from utils.keyboards import vod_auto_sent_kb

        rate    = self.get_rate()
        min_egp = self.get_min_egp()

        link = self.create_payment_link(user_tg_id)
        if not link:
            await self.bot.send_message(
                chat_id=chat_id,
                text="⚠️ فودافون كاش التلقائي غير متاح حالياً، تواصل مع الدعم.",
            )
            return

        text = (
            "📱 <b>شحن فودافون كاش — تلقائي</b>\n\n"
            f"💱 سعر الصرف الحالي: <b>1$ = {rate:.2f} ج.م</b>\n"
            f"💵 الحد الأدنى: <b>{min_egp:.0f} ج.م</b>\n\n"
            "📌 <b>خطوات الدفع:</b>\n"
            "1️⃣ اضغط على الرابط أدناه\n"
            "2️⃣ حوّل المبلغ الذي تريده\n"
            "3️⃣ ارجع واضغط <b>«تحققت من الدفع»</b> وأرسل رقمك\n\n"
            f"🔗 <b>رابط الدفع:</b>\n{link}"
        )
        await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=vod_auto_sent_kb(),
            parse_mode="HTML",
        )

    # ──────────────────────────────────────────────
    #  معالجة التحقق بعد الضغط على «تحققت»
    # ──────────────────────────────────────────────

    async def prompt_phone(self, chat_id: int, user_tg_id: int, context_user_data: dict):
        """يطلب من المستخدم إدخال رقم هاتفه للتحقق."""
        from utils.keyboards import cancel_kb
        context_user_data["vod_auto_state"] = "waiting_phone"
        context_user_data["vod_auto_uid"]   = user_tg_id
        await self.bot.send_message(
            chat_id=chat_id,
            text=(
                "📞 أرسل <b>رقم هاتف فودافون</b> الذي دفعت منه:\n"
                "<i>(مثال: 01xxxxxxxxx)</i>"
            ),
            reply_markup=cancel_kb("my_balance"),
            parse_mode="HTML",
        )

    async def handle_phone_input(
        self,
        phone: str,
        amount_egp: float,
        user_tg_id: int,
        chat_id: int,
    ) -> bool:
        """
        يتحقق من العملية بالرقم والمبلغ.
        يعيد True إذا نجح الشحن، False إذا فشل.
        """
        from utils.keyboards import back_to_main_kb
        from handlers.charge import _apply_referral_bonus

        result = self.check_payment(phone=phone, amount_egp=amount_egp)

        if not result.get("status"):
            msg = result.get("message", "فشل التحقق.")
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"❌ {msg}\n\nتأكد من الرقم والمبلغ وأعد المحاولة.",
                reply_markup=back_to_main_kb(),
            )
            return False

        # تحويل المبلغ من جنيه إلى دولار وإضافته
        usd_amount = self.egp_to_usd(amount_egp)
        charge_id  = self.db.create_vodafone_charge(
            user_tg_id, usd_amount, "", phone
        )
        # تحديث حالة الشحن كـ completed مباشرة
        with self.db._conn() as conn:
            conn.execute(
                "UPDATE vodafone_charges SET status='completed' WHERE id=?",
                (charge_id,)
            )
        self.db.add_balance(user_tg_id, usd_amount)
        _apply_referral_bonus(self.db, user_tg_id, usd_amount)

        new_balance = self.db.get_balance(user_tg_id)
        rate        = self.get_rate()

        await self.bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ <b>تم شحن رصيدك تلقائياً!</b>\n\n"
                f"💵 المبلغ المدفوع: <b>{amount_egp:.0f} ج.م</b>\n"
                f"💱 بسعر صرف: <b>1$ = {rate:.2f} ج.م</b>\n"
                f"💰 تم إضافة: <b>${usd_amount:.2f}</b>\n"
                f"💳 رصيدك الآن: <b>${new_balance:.2f}</b>"
            ),
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )

        # إشعار الأدمن
        try:
            from config import ADMIN_ID
            await self.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📱 <b>شحن فودافون كاش تلقائي ✅</b>\n\n"
                    f"👤 المستخدم: <code>{user_tg_id}</code>\n"
                    f"📞 من رقم: <code>{phone}</code>\n"
                    f"💵 المبلغ: {amount_egp:.0f} ج.م → <b>${usd_amount:.2f}</b>\n"
                    f"🆔 رقم الشحن: <code>{charge_id}</code>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

        return True
