from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentInitiationResult:
    redirect_url: str
    authority: str
    raw_response: dict


@dataclass
class PaymentVerificationResult:
    success: bool
    ref_id: str | None
    message: str | None
    raw_response: dict


class BasePaymentProvider(ABC):
    @abstractmethod
    def request_payment(
        self,
        *,
        amount: int,
        callback_url: str,
        description: str,
        mobile: str | None = None,
        email: str | None = None,
    ) -> PaymentInitiationResult:
        raise NotImplementedError

    @abstractmethod
    def verify_payment(self, *, amount: int, authority: str) -> PaymentVerificationResult:
        raise NotImplementedError
