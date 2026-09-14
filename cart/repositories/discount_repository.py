from __future__ import annotations

from cart.models import DiscountCode, UserDiscountCode


class DiscountRepository:
    def get_active_code_for_update(self, *, code: str):
        return DiscountCode.objects.select_for_update().get(name=code, is_active=True)

    def user_has_used_code(self, *, user, discount_code: DiscountCode) -> bool:
        return UserDiscountCode.objects.filter(user=user, discount_code=discount_code).exists()

    def create_user_discount_code(self, *, user, discount_code: DiscountCode) -> UserDiscountCode:
        return UserDiscountCode.objects.create(user=user, discount_code=discount_code)
