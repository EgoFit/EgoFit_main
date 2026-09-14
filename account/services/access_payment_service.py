from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from account.models import ClientDocument, ClientDocumentPayment, WorkoutProgram, WorkoutProgramPayment
from cart.exceptions import PaymentProviderException, PaymentVerificationException
from cart.providers.zarinpal_provider import ZarinPalPaymentProvider


@dataclass(frozen=True)
class AccessPaymentInitiation:
    payment_id: int | None
    redirect_url: str | None
    already_paid: bool = False


@dataclass(frozen=True)
class AccessPaymentVerification:
    payment: ClientDocumentPayment | WorkoutProgramPayment | None
    state: str
    ref_id: str | None = None
    message: str | None = None


class AccessPaymentService:
    """Own concurrency and idempotency for paid documents and workout programs."""

    def __init__(self, provider: ZarinPalPaymentProvider | None = None):
        self.provider = provider or ZarinPalPaymentProvider()

    @transaction.atomic
    def initiate_document(self, *, document_id: int, user, callback_url: str) -> AccessPaymentInitiation:
        document = ClientDocument.objects.select_for_update().get(pk=document_id, user=user)
        return self._initiate(
            target=document,
            user=user,
            payment_model=ClientDocumentPayment,
            target_field="document",
            callback_url=callback_url,
            description=f"دریافت فایل {document.title}",
            target_amount=document.price,
        )

    @transaction.atomic
    def initiate_program(self, *, program_id: int, user, callback_url: str) -> AccessPaymentInitiation:
        program = WorkoutProgram.objects.select_for_update().get(
            pk=program_id,
            user=user,
            is_published=True,
        )
        return self._initiate(
            target=program,
            user=user,
            payment_model=WorkoutProgramPayment,
            target_field="program",
            callback_url=callback_url,
            description=f"دسترسی به برنامه {program.title}",
            target_amount=program.price,
        )

    def _initiate(
        self,
        *,
        target,
        user,
        payment_model,
        target_field: str,
        callback_url: str,
        description: str,
        target_amount: int,
    ) -> AccessPaymentInitiation:
        filters = {
            target_field: target,
            "user": user,
            "status": payment_model.Status.PAID,
        }
        if payment_model.objects.filter(**filters).exists():
            return AccessPaymentInitiation(payment_id=None, redirect_url=None, already_paid=True)

        payment = payment_model.objects.select_for_update().filter(
            **{
                target_field: target,
                "user": user,
                "status": payment_model.Status.INITIATED,
            }
        ).first()
        if payment is None:
            payment = payment_model.objects.create(
                **{
                    target_field: target,
                    "user": user,
                    "amount": target_amount,
                }
            )

        if payment.authority:
            return AccessPaymentInitiation(
                payment_id=payment.pk,
                redirect_url=self.provider.build_startpay_url(payment.authority),
            )

        result = self.provider.request_payment(
            amount=payment.amount,
            callback_url=callback_url,
            description=description,
            mobile=getattr(user, "phone", None),
            email=getattr(user, "email", None) or None,
        )
        payment.authority = result.authority
        payment.status = payment_model.Status.INITIATED
        payment.save(update_fields=["authority", "status"])
        return AccessPaymentInitiation(payment_id=payment.pk, redirect_url=result.redirect_url)

    @transaction.atomic
    def verify_document(self, *, authority: str, status: str) -> AccessPaymentVerification:
        return self._verify(
            authority=authority,
            status=status,
            payment_model=ClientDocumentPayment,
        )

    @transaction.atomic
    def verify_program(self, *, authority: str, status: str) -> AccessPaymentVerification:
        return self._verify(
            authority=authority,
            status=status,
            payment_model=WorkoutProgramPayment,
        )

    def _verify(self, *, authority: str, status: str, payment_model) -> AccessPaymentVerification:
        payment = payment_model.objects.select_for_update().filter(authority=authority).first()
        if payment is None:
            return AccessPaymentVerification(payment=None, state="missing")
        if payment.status == payment_model.Status.PAID:
            return AccessPaymentVerification(payment=payment, state="already_paid", ref_id=payment.ref_id)
        if payment.status != payment_model.Status.INITIATED:
            return AccessPaymentVerification(payment=payment, state="failed", message="Payment is not active.")
        if status != "OK":
            payment.status = payment_model.Status.FAILED
            payment.save(update_fields=["status"])
            return AccessPaymentVerification(payment=payment, state="failed")

        try:
            result = self.provider.verify_payment(amount=payment.amount, authority=authority)
        except PaymentVerificationException as exc:
            payment.status = payment_model.Status.FAILED
            payment.save(update_fields=["status"])
            return AccessPaymentVerification(payment=payment, state="failed", message=str(exc))

        if not result.success:
            payment.status = payment_model.Status.FAILED
            payment.save(update_fields=["status"])
            return AccessPaymentVerification(payment=payment, state="failed", message=result.message)

        payment.status = payment_model.Status.PAID
        payment.ref_id = result.ref_id or ""
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "ref_id", "paid_at"])
        return AccessPaymentVerification(payment=payment, state="paid", ref_id=payment.ref_id)
