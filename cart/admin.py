from __future__ import annotations

from django.contrib import admin

from cart.models import DiscountCode, Order, OrderItem, UserDiscountCode


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "is_paid", "total_price", "created_at")
    inlines = (OrderItemInline,)
    list_filter = ("status", "is_paid", "created_at")
    search_fields = ("order_number", "user__fullname", "user__phone", "authority")
    readonly_fields = ("order_number", "created_at", "payment_attempted_at", "paid_at")


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity", "percentage", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(UserDiscountCode)
class UserDiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "discount_code")
    list_filter = ("user", "discount_code")
    search_fields = ("user__fullname", "discount_code__name")
