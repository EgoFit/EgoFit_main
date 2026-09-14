from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect

from cart.constants import PAYMENT_SESSION_KEY
from cart.models import Order
from cart.providers.zarinpal_provider import ZarinPalPaymentProvider
from cart.services.payment_service import PaymentService


def build_payment_callback_url(request, url_name: str = "cart:verify") -> str:
    from django.urls import reverse

    path = reverse(url_name)
    if settings.SANDBOX:
        return request.build_absolute_uri(path)

    public_base = getattr(settings, "LIARA_PUBLIC_BASE_URL", "").rstrip("/")
    if public_base:
        return f"{public_base}{path}"
    return request.build_absolute_uri(path)


def build_callback_url(*, order_id: int) -> str:
    base_url = getattr(settings, "LIARA_PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        base_url = "http://127.0.0.1:8000"
    return f"{base_url}/cart/verify/?order_id={order_id}"


class ZarinPal:
    def __init__(self, merchant, call_back_url):
        self.MERCHANT = merchant
        self.callbackURL = call_back_url
        self.provider = ZarinPalPaymentProvider(merchant_id=merchant)
        self.payment_service = PaymentService(provider=self.provider)

    def send_request(self, pk, request, description, email=None, mobile=None):
        order = get_object_or_404(Order, id=pk, user=request.user, is_paid=False)
        callback_url = self.callbackURL.format(order_id=order.id) if "{order_id}" in self.callbackURL else self.callbackURL

        redirect_url = self.payment_service.initiate_payment(
            order=order,
            callback_url=callback_url,
        )
        request.session[PAYMENT_SESSION_KEY] = str(order.id)
        request.session.save()
        return redirect(redirect_url)

    def verify(self, request, **kwargs):
        authority = (request.GET.get("Authority") or "").strip()
        status = (request.GET.get("Status") or "").strip().upper()
        result = self.payment_service.verify_callback(authority=authority, status=status)
        if result.is_success:
            return {"transaction": True, "pay": True, "RefID": result.ref_id, "message": None}
        if result.is_already_paid:
            return {"transaction": True, "pay": True, "RefID": result.ref_id, "message": None}
        if result.is_missing_order:
            return {"status": "missing", "message": result.message, "error_code": None}
        return {"transaction": False, "pay": False, "RefID": None, "message": result.message}
