from django.urls import include, path

from api.v1.auth import views as auth_views
from api.v1.commerce import views as commerce_views
from api.v1.content import views as content_views
from api.v1.profile import views as profile_views
from api.v1.library import urls as library_urls

urlpatterns = [
    path("library/", include(library_urls)),
    path("health/", auth_views.health, name="health"),
    path("auth/register/", auth_views.register, name="register"),
    path("auth/login/", auth_views.login, name="login"),
    path("auth/otp/request/", auth_views.otp_request, name="otp_request"),
    path("auth/otp/verify/", auth_views.otp_verify, name="otp_verify"),
    path("auth/password-reset/request/", profile_views.password_reset_request, name="password_reset_request"),
    path("auth/password-reset/confirm/", profile_views.password_reset_confirm, name="password_reset_confirm"),
    path("auth/refresh/", auth_views.refresh, name="refresh"),
    path("auth/logout/", auth_views.logout, name="logout"),
    path("me/", profile_views.me, name="me"),
    path("me/password/change/", profile_views.password_change, name="password_change"),
    path("me/phone/request/", profile_views.phone_change_request, name="phone_change_request"),
    path("me/phone/confirm/", profile_views.phone_change_confirm, name="phone_change_confirm"),
    path("me/metrics/<slug:metric_name>/", profile_views.metric, name="metric"),
    path("me/dashboard/", profile_views.dashboard, name="dashboard"),
    path("me/courses/", profile_views.courses, name="courses"),
    path("me/orders/", commerce_views.orders, name="orders"),
    path("me/notifications/", profile_views.notifications, name="notifications"),
    path("me/notifications/<int:pk>/read/", profile_views.mark_notification_read, name="notification_read"),
    path("me/coach-requests/", profile_views.coach_request, name="coach_request"),
    path("me/programs/", profile_views.programs, name="programs"),
    path("me/programs/<int:pk>/performance/", profile_views.program_performance, name="program_performance"),
    path("me/documents/<int:pk>/download/", profile_views.document_download, name="document_download"),
    path("me/documents/<int:pk>/payment/", profile_views.document_payment, name="document_payment"),
    path("courses/", content_views.series_list, name="series_list"),
    path("courses/<int:pk>/", content_views.series_detail, name="series_detail"),
    path("courses/<int:pk>/comments/", content_views.create_comment, name="create_comment"),
    path("courses/<int:pk>/comments/<int:comment_id>/replies/", content_views.create_reply, name="create_reply"),
    path("courses/<int:pk>/enroll/", content_views.enroll_free, name="enroll_free"),
    path("articles/", content_views.article_list, name="article_list"),
    path("articles/<slug:slug>/", content_views.article_detail, name="article_detail"),
    path("search/", content_views.search, name="search"),
    path("cart/", commerce_views.cart_detail, name="cart_detail"),
    path("cart/items/<int:pk>/", commerce_views.cart_add, name="cart_add"),
    path("cart/items/<int:pk>/delete/", commerce_views.cart_delete, name="cart_delete"),
    path("cart/empty/", commerce_views.cart_empty, name="cart_empty"),
    path("orders/", commerce_views.order_create, name="order_create"),
    path("orders/<int:pk>/discount/", commerce_views.order_discount, name="order_discount"),
    path("orders/<int:pk>/payment/", commerce_views.order_payment, name="order_payment"),
    path("payments/verify/", commerce_views.payment_verify, name="payment_verify"),
    path("payments/documents/verify/", commerce_views.document_payment_verify, name="document_payment_verify"),
    path("episodes/<int:pk>/video/", content_views.episode_video, name="episode_video"),
]
