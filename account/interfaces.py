from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable


@dataclass(frozen=True)
class PersonalizedSmsMessage:
    receptor: str
    message: str
    client_reference_id: str | None = None


@runtime_checkable
class BaseSMSProvider(Protocol):
    def send_verification_sms(self, phone: str, code: str | int, template: str = "randcode") -> bool:
        ...

    def send_bulk_sms(self, message: str, recipients: Iterable[str]) -> bool:
        ...

    def send_personalized_bulk_sms(self, recipients: Iterable[PersonalizedSmsMessage]) -> bool:
        ...


@runtime_checkable
class BaseWhatsAppProvider(Protocol):
    def is_configured(self) -> bool:
        ...

    def send_text_message(self, phone: str, message: str) -> bool:
        ...

