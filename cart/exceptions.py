from __future__ import annotations


class CartException(Exception):
    """Base exception for cart domain errors."""


class CartValidationException(CartException):
    """Raised when cart or order validation fails."""


class EmptyCartException(CartValidationException):
    """Raised when the cart has no usable items."""


class DiscountCodeException(CartValidationException):
    """Raised when a discount code is invalid or unusable."""


class OrderOwnershipException(CartValidationException):
    """Raised when an order does not belong to the current user."""


class PaymentProviderException(CartException):
    """Raised when the payment provider cannot process a request."""


class PaymentVerificationException(PaymentProviderException):
    """Raised when payment verification fails."""
