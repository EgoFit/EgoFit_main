from __future__ import annotations

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from cart.exceptions import EmptyCartException, CartValidationException
from cart.repositories.order_repository import OrderRepository
from cart.selectors.order_selector import OrderSelector
from cart.utils import normalize_price


class OrderService:
    def __init__(self, repository: OrderRepository | None = None):
        self.repository = repository or OrderRepository()

    @transaction.atomic
    def build_order_from_cart(self, *, user, cart):
        cart_items = list(cart)
        if not cart_items:
            raise EmptyCartException(_("سبد خرید خالی است."))

        product_ids = [item["product"].id for item in cart_items]
        already_owned_ids = OrderSelector.get_owned_product_ids(user=user, product_ids=product_ids)

        filtered_items = [item for item in cart_items if item["product"].id not in already_owned_ids]
        if not filtered_items:
            raise CartValidationException(_("تمام دوره‌های این سفارش قبلاً خریداری شده‌اند."))

        priced_items = []
        for item in filtered_items:
            # Never trust the price copied into a client-controlled session
            # cart. Re-read the current catalog price before creating an order.
            product = item["product"]
            price = normalize_price(product.discount_price or product.main_price or "0")
            priced_items.append({"product": item["product"], "price": price})

        subtotal = sum(item["price"] for item in priced_items)
        if subtotal <= 0:
            raise CartValidationException(_("مبلغ سفارش نامعتبر است."))

        order = self.repository.create_order(
            user=user,
            subtotal_price=subtotal,
            course=priced_items[0]["product"] if len(priced_items) == 1 else None,
        )
        self.repository.bulk_create_items(order=order, items=priced_items)
        return order
