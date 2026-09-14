from __future__ import annotations

from types import SimpleNamespace
from secrets import randbelow
from unittest.mock import patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from cart.card_models import CARD_SESSION_ID, Cart
from cart.constants import PAYMENT_SESSION_KEY
from cart.models import Order
from cart.providers.base import PaymentInitiationResult, PaymentVerificationResult
from cart.services import OrderService, PaymentService
from cart.templatetags.cart_tags import extract_discount_amount
from cart.utils import normalize_price
from cart.views import ApplyDiscountView, OrderDetailView, VerifyView, request_payment
from account.models import User
from home.models import Category, SeriesModel


class FakeSession(dict):
    modified = False

    def save(self):
        self.modified = True


class CartViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.authenticated_user = SimpleNamespace(
            is_authenticated=True,
            id=1,
            pk=1,
            username="cart_owner",
        )
        self.other_user = SimpleNamespace(
            is_authenticated=True,
            id=2,
            pk=2,
            username="cart_other",
        )

    def _request(self, method: str, path: str, user, data=None):
        request = getattr(self.factory, method.lower())(path, data=data or {})
        request.session = FakeSession()
        request.user = user
        return request

    def test_order_detail_is_scoped_to_authenticated_user(self):
        request = self._request("get", "/cart/order/detail/10", self.other_user)
        expected_order = SimpleNamespace(id=10)

        def fake_get_object_or_404(queryset, *args, **kwargs):
            self.assertEqual(kwargs["id"], 10)
            self.assertEqual(kwargs["user"], self.other_user)
            return expected_order

        with patch("cart.views.get_object_or_404", side_effect=fake_get_object_or_404) as lookup_mock:
            with patch("cart.views.render", return_value=HttpResponse("ok")) as render_mock:
                response = OrderDetailView.as_view()(request, pk=10)

        self.assertEqual(response.status_code, 200)
        lookup_mock.assert_called_once()
        render_mock.assert_called_once_with(
            request,
            "cart/order_detail.html",
            {"order": expected_order},
        )

    def test_discount_code_cannot_be_applied_to_another_users_order(self):
        request = self._request("post", "/cart/order/10", self.other_user, {"discount_code": "SAVE10"})

        def fake_get_object_or_404(queryset, *args, **kwargs):
            self.assertEqual(kwargs["id"], 10)
            self.assertEqual(kwargs["user"], self.other_user)
            self.assertFalse(kwargs["is_paid"])
            raise Http404

        with patch("cart.views.get_object_or_404", side_effect=fake_get_object_or_404) as lookup_mock:
            with patch("cart.views.apply_discount") as apply_mock:
                with self.assertRaises(Http404):
                    ApplyDiscountView.as_view()(request, pk=10)

        lookup_mock.assert_called_once()
        apply_mock.assert_not_called()

    def test_verify_without_session_order_id_returns_safe_failure_page(self):
        request = self._request("get", "/cart/verify", self.authenticated_user)

        with patch("cart.views.messages.error") as messages_error:
            with patch("cart.views.payment_service.verify_callback") as verify_mock:
                with patch("cart.views.render", return_value=HttpResponse("fail")) as render_mock:
                    response = VerifyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        messages_error.assert_called_once()
        verify_mock.assert_not_called()
        render_mock.assert_called_once_with(request, "cart/fail_result.html")


class CartUtilityTests(SimpleTestCase):
    def test_normalize_price_strips_separators_and_casts_to_int(self):
        self.assertEqual(normalize_price("120,500"), 120500)

    def test_extract_discount_amount_handles_short_messages(self):
        self.assertEqual(extract_discount_amount(""), "")
        self.assertEqual(extract_discount_amount("کد تخفیف"), "تخفیف")
        self.assertEqual(extract_discount_amount("مبلغ 12000 تومان"), "12000")


class CartSessionTests(SimpleTestCase):
    def test_cart_len_reflects_session_items(self):
        factory = RequestFactory()
        request = factory.get("/")
        request.session = FakeSession({CARD_SESSION_ID: {}})

        cart = Cart(request)
        self.assertEqual(len(cart), 0)


class CartPaymentFlowTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            fullname=f"Cart User {randbelow(10**7):07d}",
            phone=f"0912{randbelow(10**7):07d}",
            password="test-pass-123",
        )
        unique_suffix = randbelow(10**7)
        self.category = Category.objects.create(title=f"Programming {unique_suffix:07d}", slug=f"programming-{unique_suffix:07d}")
        with patch("home.services.series_service.SeriesService.create_series_notifications_on_commit"):
            self.series = SeriesModel.objects.create(
                title="Django Production",
                image="series_courses/series.jpg",
                is_compeleted=True,
                language_kinds=self.category,
                author=self.user,
                main_price="150000",
                discount_price="120000",
                free=False,
                author_image="images/author.jpg",
            )

    def _request(self, method: str = "get", path: str = "/", data=None):
        request = getattr(self.factory, method.lower())(path, data=data or {})
        request.session = FakeSession()
        request.user = self.user
        return request

    def test_order_creation_payment_initiation_and_verification_flow_is_idempotent(self):
        request = self._request("get", "/")
        cart = Cart(request)
        cart.add(product=self.series, quantity=1)

        order = OrderService().build_order_from_cart(user=self.user, cart=cart)
        self.assertEqual(order.status, Order.PaymentStatus.PENDING)
        self.assertEqual(order.total_price, 120000)
        self.assertEqual(order.items.count(), 1)

        provider = type(
            "Provider",
            (),
            {
                "request_payment": lambda self, **kwargs: PaymentInitiationResult(
                    redirect_url="https://pay.example/start/ABC123",
                    authority="ABC123",
                    raw_response={"Status": 100, "Authority": "ABC123"},
                ),
                "verify_payment": lambda self, **kwargs: PaymentVerificationResult(
                    success=True,
                    ref_id="REF-123",
                    message=None,
                    raw_response={"Status": 100, "RefID": "REF-123"},
                ),
            },
        )()
        service = PaymentService(provider=provider)

        redirect_url = service.initiate_payment(order=order, callback_url="https://example.test/cart/verify/")
        order.refresh_from_db()
        self.assertEqual(redirect_url, "https://pay.example/start/ABC123")
        self.assertEqual(order.status, Order.PaymentStatus.PAYMENT_INITIATED)
        self.assertEqual(order.authority, "ABC123")

        second_redirect_url = service.initiate_payment(order=order, callback_url="https://example.test/cart/verify/")
        order.refresh_from_db()
        self.assertEqual(second_redirect_url, "https://www.zarinpal.com/pg/StartPay/ABC123")
        self.assertEqual(order.authority, "ABC123")
        self.assertEqual(order.status, Order.PaymentStatus.PAYMENT_INITIATED)

        result = service.verify_callback(authority="ABC123", status="OK")
        order.refresh_from_db()
        self.assertTrue(result.is_success)
        self.assertEqual(result.ref_id, "REF-123")
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, Order.PaymentStatus.PAID)
        self.assertEqual(order.ref_id, "REF-123")

        repeat_result = service.verify_callback(authority="ABC123", status="OK")
        self.assertTrue(repeat_result.is_already_paid)
        self.assertEqual(repeat_result.ref_id, "REF-123")

    def test_request_payment_view_persists_order_session_and_redirects(self):
        request = self._request("post", "/cart/request/1")
        cart = Cart(request)
        cart.add(product=self.series, quantity=1)
        order = OrderService().build_order_from_cart(user=self.user, cart=cart)

        with patch("cart.views.payment_service.initiate_payment", return_value="https://pay.example/start/ABC123") as initiate_mock:
            response = request_payment(request, order.id)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://pay.example/start/ABC123")
        self.assertEqual(request.session[PAYMENT_SESSION_KEY], str(order.id))
        initiate_mock.assert_called_once()


class ZarinPalProviderTests(SimpleTestCase):
    @patch("cart.providers.zarinpal_provider.requests.post")
    @override_settings(MERCHANT="c1bd626d-83bf-45b6-8b35-629a16250cdf", SANDBOX=False)
    def test_request_payment_uses_v4_api_with_toman_currency(self, mocked_post):
        from cart.providers.zarinpal_provider import ZarinPalPaymentProvider

        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            "data": {
                "code": 100,
                "message": "Success",
                "authority": "A0000000000000000000000000000wYiRy",
                "fee_type": "Merchant",
                "fee": 0,
            },
            "errors": [],
        }

        provider = ZarinPalPaymentProvider()
        result = provider.request_payment(
            amount=120000,
            callback_url="https://egofit.ir/cart/verify/",
            description="خرید دوره",
            mobile="09306612130",
        )

        self.assertEqual(result.authority, "A0000000000000000000000000000wYiRy")
        self.assertEqual(
            result.redirect_url,
            "https://www.zarinpal.com/pg/StartPay/A0000000000000000000000000000wYiRy",
        )
        mocked_post.assert_called_once()
        self.assertEqual(
            mocked_post.call_args.args[0],
            "https://payment.zarinpal.com/pg/v4/payment/request.json",
        )
        payload = mocked_post.call_args.kwargs["json"]
        self.assertEqual(payload["merchant_id"], "c1bd626d-83bf-45b6-8b35-629a16250cdf")
        self.assertEqual(payload["amount"], 120000)
        self.assertEqual(payload["currency"], "IRT")
        self.assertEqual(payload["metadata"]["mobile"], "09306612130")

    @patch("cart.providers.zarinpal_provider.requests.post")
    @override_settings(MERCHANT="c1bd626d-83bf-45b6-8b35-629a16250cdf", SANDBOX=True)
    def test_sandbox_uses_sandbox_endpoints(self, mocked_post):
        from cart.providers.zarinpal_provider import ZarinPalPaymentProvider

        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            "data": {"code": 100, "authority": "SANDBOX-AUTH"},
            "errors": [],
        }

        provider = ZarinPalPaymentProvider()
        result = provider.request_payment(
            amount=50000,
            callback_url="https://example.test/cart/verify/",
            description="test",
        )

        self.assertEqual(result.redirect_url, "https://sandbox.zarinpal.com/pg/StartPay/SANDBOX-AUTH")
        self.assertEqual(
            mocked_post.call_args.args[0],
            "https://sandbox.zarinpal.com/pg/v4/payment/request.json",
        )

    @patch("cart.providers.zarinpal_provider.requests.post")
    @override_settings(MERCHANT="c1bd626d-83bf-45b6-8b35-629a16250cdf", SANDBOX=False)
    def test_verify_payment_accepts_code_100_and_101(self, mocked_post):
        from cart.providers.zarinpal_provider import ZarinPalPaymentProvider

        provider = ZarinPalPaymentProvider()

        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            "data": {"code": 100, "ref_id": 201, "card_pan": "502229******5995"},
            "errors": [],
        }
        success = provider.verify_payment(amount=120000, authority="AUTH-1")
        self.assertTrue(success.success)
        self.assertEqual(success.ref_id, "201")

        mocked_post.return_value.json.return_value = {
            "data": {"code": 101, "ref_id": 202},
            "errors": [],
        }
        already_verified = provider.verify_payment(amount=120000, authority="AUTH-1")
        self.assertTrue(already_verified.success)
        self.assertEqual(already_verified.ref_id, "202")

    @patch("cart.providers.zarinpal_provider.requests.post")
    @override_settings(MERCHANT="", SANDBOX=False)
    def test_missing_merchant_id_raises_clear_error(self, mocked_post):
        from cart.exceptions import PaymentProviderException
        from cart.providers.zarinpal_provider import ZarinPalPaymentProvider

        with self.assertRaises(PaymentProviderException) as exc:
            ZarinPalPaymentProvider().request_payment(
                amount=10000,
                callback_url="https://example.test/cart/verify/",
                description="test",
            )

        self.assertIn("Merchant", str(exc.exception))
        mocked_post.assert_not_called()


class PaymentCallbackUrlTests(SimpleTestCase):
    @override_settings(
        SANDBOX=False,
        LIARA_PUBLIC_BASE_URL="https://egofit.ir",
    )
    def test_profile_document_callback_uses_registered_public_domain(self):
        from django.test import RequestFactory

        from cart.zarinpal import build_payment_callback_url

        request = RequestFactory().get("/accounts/profile_plans/", HTTP_HOST="localhost:8000")

        self.assertEqual(
            build_payment_callback_url(
                request,
                url_name="register:profile_document_verify",
            ),
            "https://egofit.ir/accounts/profile_plans/payment/verify/",
        )
