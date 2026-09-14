from __future__ import annotations

from decimal import Decimal

from home.models import SeriesModel

CARD_SESSION_ID = "cart"


class Cart:
    def __init__(self, request):
        self.session = request.session
        stored_cart = self.session.get(CARD_SESSION_ID)
        if isinstance(stored_cart, dict):
            self.cart = stored_cart
        else:
            self.cart = {}

    def __iter__(self):
        cart = self.cart.copy()
        product_ids = [int(item["id"]) for item in cart.values() if item.get("id")]
        products = {
            product.id: product
            for product in SeriesModel.objects.filter(id__in=product_ids).select_related("author", "language_kinds")
        }

        for item in cart.values():
            product = products.get(int(item["id"]))
            if product is None:
                continue
            item["product"] = product
            item["unique_id"] = self.unique_id_generator(product.id)
            yield item

    def __len__(self):
        return len(self.cart)

    def unique_id_generator(self, id):
        return f"{id}"

    def add(self, quantity, product):
        unique = self.unique_id_generator(product.id)
        if unique not in self.cart:
            raw_price = product.discount_price or product.main_price or "0"
            self.cart[unique] = {"quantity": quantity or 1, "price": str(raw_price), "id": str(product.id)}
        self.save()

    def remove(self):
        self.session.pop(CARD_SESSION_ID, None)
        self.cart = {}
        self.session.modified = True

    @property
    def total_price(self):
        total_price = Decimal(0)
        for item in self.cart.values():
            if "price" in item and item["quantity"] is not None:
                price_str = str(item["price"]).replace(",", "")
                quantity_str = item["quantity"]
                if price_str not in (None, "", "None"):
                    try:
                        total_price += Decimal(quantity_str) * Decimal(price_str)
                    except Exception:
                        continue
        return total_price

    def delete(self, id):
        if id in self.cart:
            del self.cart[id]
            self.save()

    def save(self):
        if not self.cart:
            if CARD_SESSION_ID in self.session:
                self.session.pop(CARD_SESSION_ID, None)
            return
        self.session[CARD_SESSION_ID] = self.cart
        self.session.modified = True
