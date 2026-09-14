from __future__ import annotations

from django.db import transaction

from cart.models import Order, OrderItem


class OrderRepository:
    def create_order(self, *, user, subtotal_price: int, course=None) -> Order:
        return Order.objects.create(
            user=user,
            subtotal_price=subtotal_price,
            total_price=subtotal_price,
            course=course,
        )

    def bulk_create_items(self, *, order: Order, items: list[dict]) -> None:
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=item["product"],
                    price=item["price"],
                )
                for item in items
            ]
        )

    def get_order_for_user(self, *, order_id: int, user, is_paid: bool | None = None, lock: bool = False):
        queryset = Order.objects.select_related("user", "course", "applied_discount_code")
        if lock:
            queryset = queryset.select_for_update()
        queryset = queryset.prefetch_related("items__product").filter(id=order_id, user=user)
        if is_paid is not None:
            queryset = queryset.filter(is_paid=is_paid)
        return queryset.first()

    def get_order_by_authority(self, *, authority: str, lock: bool = False):
        queryset = Order.objects.select_related("user", "course", "applied_discount_code")
        if lock:
            queryset = queryset.select_for_update()
        return queryset.prefetch_related("items__product").filter(authority=authority).first()

    def mark_payment_initiated(self, *, order: Order, authority: str) -> None:
        order.mark_payment_initiated(authority)

    def mark_paid(self, *, order: Order, ref_id: str | None = None) -> None:
        order.mark_paid(ref_id=ref_id)

    def mark_failed(self, *, order: Order) -> None:
        order.mark_failed()
