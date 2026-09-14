from __future__ import annotations

from django.core.exceptions import ValidationError

from cart.exceptions import CartValidationException
from cart.services.discount_service import DiscountService
from cart.services.order_service import OrderService
from cart.services.payment_service import PaymentService

__all__ = [
    "OrderService",
    "DiscountService",
    "PaymentService",
    "build_order_from_cart",
    "apply_discount",
]


def build_order_from_cart(*, user, cart):
    try:
        return OrderService().build_order_from_cart(user=user, cart=cart)
    except CartValidationException as exc:
        raise ValidationError(str(exc)) from exc


def apply_discount(*, order_id: int, user, raw_code: str):
    try:
        return DiscountService().apply_discount(order_id=order_id, user=user, raw_code=raw_code)
    except CartValidationException as exc:
        raise ValidationError(str(exc)) from exc
