"""
🌐 واجهة API موقع SMM — utils/api_client.py
"""

import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)


class SMMApiClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self._timeout = aiohttp.ClientTimeout(total=30)

    async def _post(self, **kwargs) -> dict:
        data = {"key": self.api_key, **kwargs}
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(self.api_url, data=data) as resp:
                    result = await resp.json(content_type=None)
                    return result
        except Exception as e:
            logger.error(f"[SMMApi] خطأ: {e}")
            return {}

    async def get_services(self) -> list:
        """جلب كل الخدمات من الـ API."""
        result = await self._post(action="services")
        if isinstance(result, list):
            return result
        return []

    async def add_order(self, service: int, link: str, quantity: int) -> dict:
        """إنشاء طلب جديد. Returns {'order': id} or {'error': msg}."""
        return await self._post(
            action="add",
            service=service,
            link=link,
            quantity=quantity
        )

    async def get_order_status(self, order_id) -> dict:
        """جلب حالة الطلب."""
        result = await self._post(action="status", order=order_id)
        return result if isinstance(result, dict) else {}

    async def get_multiple_status(self, order_ids: list) -> dict:
        """جلب حالات متعددة."""
        ids_str = ",".join(str(i) for i in order_ids)
        result = await self._post(action="status", orders=ids_str)
        return result if isinstance(result, dict) else {}

    async def get_balance(self) -> Optional[float]:
        """جلب رصيد الحساب في API."""
        result = await self._post(action="balance")
        try:
            return float(result.get("balance", 0))
        except Exception:
            return None

    async def create_refill(self, order_id: int) -> dict:
        """طلب رشق لطلب سابق. Returns {'refill': id} or {'error': msg}."""
        result = await self._post(action="refill", order=order_id)
        return result if isinstance(result, dict) else {}

    async def get_refill_status(self, refill_id: int) -> dict:
        """جلب حالة الرشق."""
        result = await self._post(action="refill_status", refill=refill_id)
        return result if isinstance(result, dict) else {}
