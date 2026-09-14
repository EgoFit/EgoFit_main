from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from requests import RequestException

from account.constants import (
    WHATSAPP_API_VERSION,
    WHATSAPP_REQUEST_TIMEOUT_SECONDS,
    WHATSAPP_UNAVAILABLE_ERROR_CODES,
)
from account.exceptions import WhatsAppProviderException, WhatsAppUnavailableException
from account.interfaces import BaseWhatsAppProvider
from account.utils import is_valid_mobile_phone, normalize_phone_number, to_international_phone

logger = logging.getLogger(__name__)

STATUS_SENT = "sent"
STATUS_SKIPPED_DISABLED = "skipped_disabled"
STATUS_SKIPPED_INVALID_PHONE = "skipped_invalid_phone"
STATUS_SKIPPED_NO_WHATSAPP = "skipped_no_whatsapp"
STATUS_FAILED = "failed"


def _setting(name: str, default: str = "") -> str:
    value = getattr(settings, name, None)
    if value is None:
        return default
    return str(value).strip()


class MetaCloudWhatsAppProvider:
    """Send athlete news messages through the official WhatsApp Cloud API."""

    def is_configured(self) -> bool:
        if not bool(getattr(settings, "WHATSAPP_ENABLED", False)):
            return False
        return bool(_setting("WHATSAPP_TOKEN") and _setting("WHATSAPP_PHONE_NUMBER_ID"))

    def send_text_message(self, phone: str, message: str) -> bool:
        if not self.is_configured():
            raise WhatsAppProviderException("پیکربندی سرویس واتساپ انجام نشده است.")

        international_phone = to_international_phone(phone)
        token = _setting("WHATSAPP_TOKEN")
        phone_number_id = _setting("WHATSAPP_PHONE_NUMBER_ID")
        api_version = _setting("WHATSAPP_API_VERSION", WHATSAPP_API_VERSION) or WHATSAPP_API_VERSION
        url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(international_phone, message)

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
        except RequestException as exc:
            logger.exception("WhatsApp request failed for %s", international_phone)
            raise WhatsAppProviderException("ارسال پیام واتساپ با خطا مواجه شد.") from exc

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:500]}

        if response.status_code >= 400 or not self._is_success(body):
            if self._is_unavailable(body):
                raise WhatsAppUnavailableException("شماره روی واتساپ در دسترس نیست.")
            logger.error("WhatsApp send failed (%s): %s", response.status_code, body)
            raise WhatsAppProviderException(self._error_message(body))
        return True

    def _build_payload(self, international_phone: str, message: str) -> dict[str, Any]:
        template_name = _setting("WHATSAPP_TEMPLATE_NAME")
        if template_name:
            language = _setting("WHATSAPP_TEMPLATE_LANGUAGE", "fa") or "fa"
            payload: dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": international_phone,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language},
                },
            }
            if bool(getattr(settings, "WHATSAPP_TEMPLATE_INCLUDE_BODY", True)):
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": message[:1024]}],
                    }
                ]
            return payload

        return {
            "messaging_product": "whatsapp",
            "to": international_phone,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }

    @staticmethod
    def _is_success(body: Any) -> bool:
        if not isinstance(body, dict):
            return False
        if body.get("error"):
            return False
        messages = body.get("messages")
        return isinstance(messages, list) and bool(messages)

    @staticmethod
    def _is_unavailable(body: Any) -> bool:
        if not isinstance(body, dict):
            return False
        error = body.get("error") or {}
        code = error.get("code")
        error_subcode = error.get("error_subcode")
        return code in WHATSAPP_UNAVAILABLE_ERROR_CODES or error_subcode in WHATSAPP_UNAVAILABLE_ERROR_CODES

    @staticmethod
    def _error_message(body: Any) -> str:
        if isinstance(body, dict):
            error = body.get("error") or {}
            message = error.get("message") or body.get("message")
            if message:
                return str(message)
        return "ارسال پیام واتساپ با خطا مواجه شد."


class WhatsAppService:
    def __init__(self, provider: BaseWhatsAppProvider | None = None):
        self.provider = provider or MetaCloudWhatsAppProvider()

    def is_configured(self) -> bool:
        return bool(self.provider.is_configured())

    def send_news_if_available(self, phone: str | None, message: str) -> str:
        if not self.is_configured():
            return STATUS_SKIPPED_DISABLED

        normalized = normalize_phone_number(phone)
        if not is_valid_mobile_phone(normalized) or not (message or "").strip():
            return STATUS_SKIPPED_INVALID_PHONE

        try:
            sent = self.provider.send_text_message(normalized, message.strip())
        except WhatsAppUnavailableException:
            logger.info("Skipping WhatsApp news for %s; number is not on WhatsApp.", normalized)
            return STATUS_SKIPPED_NO_WHATSAPP
        except WhatsAppProviderException:
            logger.exception("WhatsApp news failed for %s.", normalized)
            return STATUS_FAILED
        except Exception:
            logger.exception("Unexpected WhatsApp news failure for %s.", normalized)
            return STATUS_FAILED

        return STATUS_SENT if sent else STATUS_FAILED
