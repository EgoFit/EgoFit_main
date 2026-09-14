from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from requests import RequestException

from cart.constants import (
    DEFAULT_PAYMENT_TIMEOUT_SECONDS,
    ZARINPAL_API_BASE_URL,
    ZARINPAL_CURRENCY,
    ZARINPAL_SANDBOX_API_BASE_URL,
)
from cart.exceptions import PaymentProviderException, PaymentVerificationException
from cart.providers.base import BasePaymentProvider, PaymentInitiationResult, PaymentVerificationResult

logger = logging.getLogger(__name__)


class ZarinPalPaymentProvider(BasePaymentProvider):
    def __init__(self, *, merchant_id: str | None = None, sandbox: bool | None = None):
        self.merchant_id = (merchant_id or settings.MERCHANT or "").strip()
        self.sandbox = settings.SANDBOX if sandbox is None else sandbox

    def build_startpay_url(self, authority: str) -> str:
        sandbox_prefix = "sandbox" if self.sandbox else "www"
        return f"https://{sandbox_prefix}.zarinpal.com/pg/StartPay/{authority}"

    def _api_base_url(self) -> str:
        if self.sandbox:
            return ZARINPAL_SANDBOX_API_BASE_URL
        return ZARINPAL_API_BASE_URL

    def _parse_response_data(self, response: requests.Response) -> dict[str, Any]:
        try:
            response_data = response.json()
        except ValueError as exc:
            logger.error("Zarinpal returned non-JSON response with status %s", response.status_code)
            raise PaymentProviderException(_("پاسخ نامعتبر از درگاه پرداخت دریافت شد.")) from exc

        if not isinstance(response_data, dict):
            raise PaymentProviderException(_("پاسخ نامعتبر از درگاه پرداخت دریافت شد."))
        return response_data

    def _post(self, *, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.merchant_id:
            raise PaymentProviderException(_("شناسه درگاه پرداخت (Merchant ID) تنظیم نشده است."))

        url = f"{self._api_base_url()}/{path}.json"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=DEFAULT_PAYMENT_TIMEOUT_SECONDS,
            )
        except RequestException as exc:
            logger.exception("Zarinpal request failed: %s", path)
            raise PaymentProviderException(_("اتصال به درگاه پرداخت برقرار نشد.")) from exc

        response_data = self._parse_response_data(response)
        if response.status_code >= 400:
            error_message = self._extract_error_message(response_data)
            logger.error("Zarinpal request rejected (%s): %s", response.status_code, response_data)
            raise PaymentProviderException(error_message)

        return response_data

    @staticmethod
    def _extract_error_message(response_data: dict[str, Any]) -> str:
        errors = response_data.get("errors")
        if isinstance(errors, dict):
            message = errors.get("message")
            if message:
                return str(message)
        if isinstance(errors, list) and errors:
            first_error = errors[0]
            if isinstance(first_error, dict) and first_error.get("message"):
                return str(first_error["message"])
            return str(first_error)

        data = response_data.get("data")
        if isinstance(data, dict) and data.get("message"):
            return str(data["message"])

        return _("درخواست پرداخت توسط درگاه رد شد.")

    @staticmethod
    def _extract_data(response_data: dict[str, Any]) -> dict[str, Any]:
        data = response_data.get("data")
        if isinstance(data, dict):
            return data
        return {}

    def request_payment(
        self,
        *,
        amount: int,
        callback_url: str,
        description: str,
        mobile: str | None = None,
        email: str | None = None,
    ) -> PaymentInitiationResult:
        payload: dict[str, Any] = {
            "merchant_id": self.merchant_id,
            "amount": int(amount),
            "currency": ZARINPAL_CURRENCY,
            "description": description,
            "callback_url": callback_url,
        }

        metadata: dict[str, str] = {}
        if mobile:
            metadata["mobile"] = mobile
        if email:
            metadata["email"] = email
        if metadata:
            payload["metadata"] = metadata

        response_data = self._post(path="request", payload=payload)
        data = self._extract_data(response_data)
        if data.get("code") != 100:
            error_message = self._extract_error_message(response_data)
            logger.error("Zarinpal payment request rejected: %s", response_data)
            raise PaymentProviderException(error_message)

        authority = str(data.get("authority") or "").strip()
        if not authority:
            raise PaymentProviderException(_("شناسه پرداخت نامعتبر است."))

        return PaymentInitiationResult(
            redirect_url=self.build_startpay_url(authority),
            authority=authority,
            raw_response=response_data,
        )

    def verify_payment(self, *, amount: int, authority: str) -> PaymentVerificationResult:
        payload = {
            "merchant_id": self.merchant_id,
            "amount": int(amount),
            "authority": authority,
        }

        try:
            response_data = self._post(path="verify", payload=payload)
        except PaymentProviderException as exc:
            raise PaymentVerificationException(str(exc)) from exc

        data = self._extract_data(response_data)
        verification_code = data.get("code")
        if verification_code in {100, 101}:
            return PaymentVerificationResult(
                success=True,
                ref_id=str(data.get("ref_id") or ""),
                message=None,
                raw_response=response_data,
            )

        return PaymentVerificationResult(
            success=False,
            ref_id=None,
            message=self._extract_error_message(response_data),
            raw_response=response_data,
        )
