from __future__ import annotations

from cart.card_models import Cart


class CartMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cart = Cart(request)
        request.cart = cart
        request.cart_item_count = len(cart)
        return self.get_response(request)
