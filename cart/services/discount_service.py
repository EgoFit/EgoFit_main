from __future__ import annotations

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from cart.exceptions import DiscountCodeException
from cart.models import DiscountCode
from cart.repositories.discount_repository import DiscountRepository
from cart.repositories.order_repository import OrderRepository


class DiscountService:
    def __init__(self, order_repository: OrderRepository | None = None, discount_repository: DiscountRepository | None = None):
        self.order_repository = order_repository or OrderRepository()
        self.discount_repository = discount_repository or DiscountRepository()

    @transaction.atomic
    def apply_discount(self, *, order_id: int, user, raw_code: str):
        code = (raw_code or "").strip().upper()
        if not code:
            raise DiscountCodeException(_("کد تخفیف را وارد کنید."))

        order = self.order_repository.get_order_for_user(order_id=order_id, user=user, is_paid=False, lock=True)
        if order is None:
            raise DiscountCodeException(_("سفارش مورد نظر پیدا نشد."))

        if order.applied_discount_code_id:
            raise DiscountCodeException(_("برای این سفارش قبلاً کد تخفیف اعمال شده است."))

        try:
            discount_code = self.discount_repository.get_active_code_for_update(code=code)
        except DiscountCode.DoesNotExist as exc:
            raise DiscountCodeException(_("کد تخفیف نامعتبر است.")) from exc

        if discount_code.quantity <= 0:
            raise DiscountCodeException(_("این کد تخفیف قابل استفاده نیست."))

        if self.discount_repository.user_has_used_code(user=user, discount_code=discount_code):
            raise DiscountCodeException(_("شما قبلاً از این کد تخفیف استفاده کرده‌اید."))

        discount_amount = int(discount_code.percentage * order.subtotal_price / 100)
        discount_amount = min(discount_amount, order.subtotal_price)
        order.discount_amount = discount_amount
        order.total_price = max(order.subtotal_price - discount_amount, 0)
        order.applied_discount_code = discount_code
        order.save(update_fields=["discount_amount", "total_price", "applied_discount_code"])

        discount_code.quantity -= 1
        discount_code.save(update_fields=["quantity"])
        self.discount_repository.create_user_discount_code(user=user, discount_code=discount_code)

        return order, discount_amount
