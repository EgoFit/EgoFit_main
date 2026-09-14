from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from cart.card_models import Cart
from cart.constants import PAYMENT_SESSION_KEY
from cart.exceptions import PaymentProviderException
from cart.selectors.order_selector import OrderSelector
from cart.services import PaymentService, apply_discount, build_order_from_cart
from cart.zarinpal import build_payment_callback_url
from home.models import SeriesModel


payment_service = PaymentService()


class CartDetailView(View):
    def get(self, request):
        cart = Cart(request)
        if not cart.cart:
            return redirect("cart:cart_empty")
        if not request.user.is_authenticated:
            return redirect("register:register")
        return render(request, "cart/cart.html", {"cart": cart, "cart_item_count": len(cart)})


class CartAddView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("register:register")

        product = get_object_or_404(SeriesModel, id=pk)
        if OrderSelector.user_has_paid_product(user=request.user, product=product):
            return redirect("home:series_episod", pk=pk)

        cart = Cart(request)
        cart.add(product=product, quantity=1)
        return redirect("cart:cart_detail")


class CartDeleteView(View):
    def get(self, request, id):
        return redirect("cart:cart_detail")

    def post(self, request, id):
        cart = Cart(request)
        cart.delete(id)
        return redirect("cart:cart_detail")


class CartEmptyView(TemplateView):
    template_name = "cart/cart-empty.html"


class OrderDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        order = get_object_or_404(OrderSelector.get_order_detail_queryset(), id=pk, user=request.user)
        return render(request, "cart/order_detail.html", {"order": order})


class OrderCreationView(LoginRequiredMixin, View):
    def get(self, request):
        return redirect("cart:cart_detail")

    def post(self, request):
        cart = Cart(request)
        try:
            order = build_order_from_cart(user=request.user, cart=cart)
        except ValidationError as exc:
            messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
            return redirect("cart:cart_detail")

        cart.remove()
        request.session.pop(PAYMENT_SESSION_KEY, None)
        return redirect("cart:order_detail", order.id)


class ApplyDiscountView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(
            OrderSelector.get_order_detail_queryset(),
            id=pk,
            user=request.user,
            is_paid=False,
        )
        try:
            order, discount_amount = apply_discount(
                order_id=order.id,
                user=request.user,
                raw_code=request.POST.get("discount_code"),
            )
        except ValidationError as exc:
            messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
            return redirect("cart:order_detail", pk)

        return render(
            request,
            "cart/order_detail.html",
            {
                "order": order,
                "discount_amount": discount_amount,
            },
        )


@login_required
def request_payment(request, pk):
    if request.method != "POST":
        return redirect("cart:order_detail", pk)

    order = get_object_or_404(
        OrderSelector.get_order_detail_queryset(),
        id=pk,
        user=request.user,
        is_paid=False,
    )
    if order.total_price <= 0:
        messages.error(request, _("مبلغ سفارش نامعتبر است."))
        return redirect("cart:order_detail", order.id)

    try:
        redirect_url = payment_service.initiate_payment(
            order=order,
            callback_url=build_payment_callback_url(request),
        )
    except PaymentProviderException as exc:
        messages.error(request, str(exc))
        return redirect("cart:order_detail", order.id)

    request.session[PAYMENT_SESSION_KEY] = str(order.id)
    request.session.save()
    return redirect(redirect_url)


class VerifyView(View):
    def get(self, request):
        authority = (request.GET.get("Authority") or "").strip()
        status = (request.GET.get("Status") or "").strip().upper()
        if not authority:
            messages.error(request, _("شناسه پرداخت از درگاه دریافت نشد."))
            return render(request, "cart/fail_result.html")

        result = payment_service.verify_callback(authority=authority, status=status)
        request.session.pop(PAYMENT_SESSION_KEY, None)

        if result.is_missing_order:
            messages.error(request, _("سفارش متناظر با این پرداخت پیدا نشد."))
            return render(request, "cart/fail_result.html")

        if result.is_success or result.is_already_paid:
            return render(request, "cart/succsses_pay.html", {"order": result.order})

        if result.message:
            messages.error(request, result.message)
        return render(request, "cart/fail_result.html", {"order": result.order})
