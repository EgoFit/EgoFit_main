from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.Register.as_view(), name="register"),
    path("check_otp/", views.CheckOtpView.as_view(), name="verification"),
    path("resend_otp/", views.ResendOtpView.as_view(), name="resend_otp"),
    path("logout/", views.user_logout, name="logout"),
    path("profile_number_edit/", views.NumberEdit.as_view(), name="profile_number_edit"),
    path("profile_number_verify/", views.NumberEditVerify.as_view(), name="profile_number_verify"),
    path("pass_register/", views.signup, name="pass_register"),
    path("pass_login/", views.login_view, name="pass_login"),
    path("forgot_password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
    path("forgot_password/confirm/", views.ForgotPasswordConfirmView.as_view(), name="forgot_password_confirm"),
    path("password_change/", views.PasswordsChangeView.as_view(), name="change_password"),
]
