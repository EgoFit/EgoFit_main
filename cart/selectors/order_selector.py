from __future__ import annotations

from cart.models import Order, OrderItem


class OrderSelector:
    @staticmethod
    def get_order_detail_queryset():
        return Order.objects.select_related("user", "course", "applied_discount_code").prefetch_related("items__product")

    @staticmethod
    def get_order_by_authority_queryset():
        return Order.objects.select_related("user", "course", "applied_discount_code").prefetch_related("items__product")

    @staticmethod
    def user_has_paid_product(*, user, product) -> bool:
        return OrderItem.objects.filter(order__user=user, order__is_paid=True, product=product).exists()

    @staticmethod
    def get_owned_product_ids(*, user, product_ids: list[int]) -> set[int]:
        if not product_ids:
            return set()
        return set(
            OrderItem.objects.filter(
                order__user=user,
                order__is_paid=True,
                product_id__in=product_ids,
            ).values_list("product_id", flat=True)
        )

    @staticmethod
    def get_user_order_queryset(*, user):
        return Order.objects.select_related("user", "course", "applied_discount_code").prefetch_related("items__product").filter(user=user)
