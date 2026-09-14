from __future__ import annotations

import logging
import os
from typing import Any, Iterable
from uuid import uuid4

import ghasedak_sms
import requests
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from requests import RequestException

from account.constants import SMS_DEFAULT_TEMPLATE, SMS_REQUEST_TIMEOUT_SECONDS
from account.exceptions import SMSProviderException
from account.interfaces import BaseSMSProvider, PersonalizedSmsMessage

logger = logging.getLogger(__name__)

GHASEDAK_SEND_OTP_URL = "https://gateway.ghasedak.me/rest/api/v1/WebService/sendotpsms"


def _get_api_key() -> str | None:
    api_key = getattr(settings, "GHASEDAK_API_KEY", None) or os.getenv("GHASEDAK_API_KEY")
    return api_key.strip() if api_key else None


def _get_line_number() -> str | None:
    line_number = getattr(settings, "GHASEDAK_LINE_NUMBER", None) or os.getenv("GHASEDAK_LINE_NUMBER")
    return line_number.strip() if line_number else None


def _get_otp_template() -> str:
    return getattr(settings, "GHASEDAK_OTP_TEMPLATE", None) or SMS_DEFAULT_TEMPLATE


def _get_otp_param() -> str:
    return getattr(settings, "GHASEDAK_OTP_PARAM", None) or "param1"


def _build_default_client():
    api_key = _get_api_key()
    if not api_key:
        return _UnavailableGhasedakClient()
    return ghasedak_sms.Ghasedak(api_key)


_default_sms_client = None


def get_sms_client():
    global _default_sms_client
    if _default_sms_client is None:
        _default_sms_client = _build_default_client()
    return _default_sms_client


def _is_success_response(response) -> bool:
    if response is None:
        return False
    if hasattr(response, "is_success"):
        return _coerce_bool(getattr(response, "is_success"))
    if isinstance(response, dict):
        for key in ("isSuccess", "IsSuccess", "is_success", "Success", "success"):
            if key in response:
                return _coerce_bool(response[key])
        status_code = response.get("statusCode", response.get("status_code"))
        try:
            status_code = int(status_code)
        except (TypeError, ValueError):
            status_code = None
        if status_code is not None:
            return 200 <= status_code < 300
        return False
    return bool(response)


def _coerce_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "ok", "success"}
    return bool(value)


def _extract_error_message(response: Any) -> str:
    if response is None:
        return _("ارسال پیامک با خطا مواجه شد. لطفاً دوباره تلاش کنید.")

    if hasattr(response, "message") and getattr(response, "message"):
        return str(response.message).strip() or _("ارسال پیامک با خطا مواجه شد. لطفاً دوباره تلاش کنید.")

    if isinstance(response, dict):
        message = response.get("message") or response.get("Message")
        if message:
            return str(message)

    return _("ارسال پیامک با خطا مواجه شد. لطفاً دوباره تلاش کنید.")


def _post_ghasedak_json(*, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    api_key = _get_api_key()
    if not api_key:
        raise SMSProviderException(_("پیکربندی سرویس پیامک انجام نشده است."))

    headers = {
        "Content-Type": "application/json",
        "ApiKey": api_key,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=SMS_REQUEST_TIMEOUT_SECONDS)
    except RequestException as exc:
        logger.exception("Ghasedak request failed for %s", url)
        raise SMSProviderException(
            _("ارسال پیامک با خطا مواجه شد. لطفاً چند لحظه بعد دوباره تلاش کنید.")
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        logger.error("Ghasedak returned non-JSON response for %s: %s", url, response.text[:500])
        raise SMSProviderException(_("پاسخ نامعتبر از سرویس پیامک دریافت شد.")) from exc

    if not isinstance(body, dict):
        raise SMSProviderException(_("پاسخ نامعتبر از سرویس پیامک دریافت شد."))

    if response.status_code >= 400 or not _is_success_response(body):
        error_message = _extract_error_message(body)
        logger.error("Ghasedak %s failed (%s): %s", url, response.status_code, body)
        raise SMSProviderException(error_message)

    return body


class _UnavailableGhasedakClient:
    def _raise_unavailable(self):
        raise SMSProviderException(_("پیکربندی سرویس پیامک انجام نشده است."))

    def send_otp_sms(self, *args, **kwargs):
        self._raise_unavailable()

    def send_bulk_sms(self, *args, **kwargs):
        self._raise_unavailable()

    def send_single_sms(self, *args, **kwargs):
        self._raise_unavailable()

    def send_pair_to_pair_sms(self, *args, **kwargs):
        self._raise_unavailable()

    def get_account_information(self, *args, **kwargs):
        self._raise_unavailable()


class GhasedakSMSProvider(BaseSMSProvider):
    def __init__(self, client=None, *, line_number: str | None = None, otp_param: str | None = None):
        self.client = client or get_sms_client()
        self.line_number = line_number if line_number is not None else _get_line_number()
        self.otp_param = otp_param or _get_otp_param()

    def _require_line_number(self):
        if not self.line_number:
            raise SMSProviderException(
                _("شماره خط ارسال پیامک تنظیم نشده است. مقدار GHASEDAK_LINE_NUMBER را در تنظیمات وارد کنید.")
            )
        return self.line_number

    def _send_otp_via_rest(self, phone: str, code: str | int, template_name: str) -> bool:
        payload = {
            "sendDate": None,
            "receptors": [
                {
                    "mobile": phone,
                    "clientReferenceId": str(uuid4()),
                }
            ],
            "templateName": template_name,
            "inputs": [
                {
                    "param": self.otp_param,
                    "value": str(code),
                }
            ],
            "udh": False,
        }
        _post_ghasedak_json(url=GHASEDAK_SEND_OTP_URL, payload=payload)
        return True

    def _send_otp_via_sdk(self, phone: str, code: str | int, template_name: str) -> bool:
        command = ghasedak_sms.SendOtpInput(
            send_date=None,
            receptors=[ghasedak_sms.SendOtpReceptorDto(mobile=phone)],
            template_name=template_name,
            inputs=[
                ghasedak_sms.SendOtpInput.OtpInput(param=self.otp_param, value=str(code)),
            ],
            udh=False,
        )
        response = self.client.send_otp_sms(command)
        if not _is_success_response(response):
            logger.error("Ghasedak SDK OTP SMS failed for %s: %s", phone, response)
            raise SMSProviderException(_extract_error_message(response))
        return True

    def send_verification_sms(self, phone: str, code: str | int, template: str | None = None) -> bool:
        template_name = template or _get_otp_template()
        return self._send_otp_via_rest(phone, code, template_name)

    def send_bulk_sms(self, message: str, recipients: Iterable[str]) -> bool:
        recipient_list = [recipient for recipient in recipients if recipient]
        if not recipient_list:
            return False
        command = ghasedak_sms.SendBulkInput(
            send_date=None,
            line_number=self._require_line_number(),
            receptors=recipient_list,
            message=message,
            client_reference_id=None,
            is_voice=False,
            udh=False,
        )
        response = self.client.send_bulk_sms(command)
        if not _is_success_response(response):
            logger.error("Ghasedak bulk SMS failed: %s", response)
            raise SMSProviderException(_extract_error_message(response))
        return True

    def send_personalized_bulk_sms(self, recipients: Iterable[PersonalizedSmsMessage]) -> bool:
        recipient_list = [recipient for recipient in recipients if recipient and recipient.receptor and recipient.message]
        if not recipient_list:
            return False

        command = ghasedak_sms.SendPairToPairInput(
            items=[
                ghasedak_sms.SendPairToPairInput.SendPairToPairSmsWebServiceDto(
                    line_number=self._require_line_number(),
                    receptor=recipient.receptor,
                    message=recipient.message,
                    client_reference_id=recipient.client_reference_id,
                )
                for recipient in recipient_list
            ],
            udh=False,
        )
        response = self.client.send_pair_to_pair_sms(command)
        if not _is_success_response(response):
            logger.error("Ghasedak personalized SMS failed: %s", response)
            raise SMSProviderException(_extract_error_message(response))
        return True


class SmsService:
    def __init__(self, provider: BaseSMSProvider | None = None):
        self.provider = provider or GhasedakSMSProvider()

    def send_verification_sms(self, phone: str, code: str | int) -> bool:
        try:
            sent = self.provider.send_verification_sms(phone, code)
        except SMSProviderException:
            raise
        except Exception as exc:
            raise SMSProviderException(_("ارسال پیامک با خطا مواجه شد. لطفاً دوباره تلاش کنید.")) from exc
        if not sent:
            raise SMSProviderException(_("ارسال پیامک با خطا مواجه شد. لطفاً دوباره تلاش کنید."))
        return sent

    def send_bulk_sms(self, message: str, recipients: Iterable[str]) -> bool:
        try:
            sent = self.provider.send_bulk_sms(message, recipients)
        except Exception as exc:
            raise SMSProviderException(str(exc)) from exc
        if not sent:
            raise SMSProviderException(_("پنل پیامکی پاسخ موفق برای ارسال پیامک برنگرداند."))
        return True

    def send_personalized_bulk_sms(self, recipients: Iterable[PersonalizedSmsMessage]) -> bool:
        try:
            sent = self.provider.send_personalized_bulk_sms(recipients)
        except Exception as exc:
            raise SMSProviderException(str(exc)) from exc
        if not sent:
            raise SMSProviderException(_("پنل پیامکی پاسخ موفق برای ارسال گروهی برنگرداند."))
        return True
