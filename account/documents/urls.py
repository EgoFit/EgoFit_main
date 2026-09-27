from django.urls import path

from . import views

urlpatterns = [
    path("profile_plans/", views.ProfileDocumentsView.as_view(), name="profile_plans"),
    path("profile_plans/<int:pk>/pay/", views.ClientDocumentPaymentView.as_view(), name="profile_document_pay"),
    path("profile_plans/payment/verify/", views.ClientDocumentPaymentVerifyView.as_view(), name="profile_document_verify"),
    path("profile_plans/<int:pk>/download/", views.ClientDocumentDownloadView.as_view(), name="profile_document_download"),
]
