from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    PasswordChangeOTPConfirmView,
    PasswordChangeView,
    RefreshTokenView,
    RequestPasswordChangeView,
    ResendPasswordChangeOTPView,
    SendEmailOTPView,
    VerifyEmailOTPView,
    CowrywiseKidProfileView,
)
from .views.registration import RegistrationV2View, PreRegistrationView

app_name = "identity"

urlpatterns = [
    path("cowrywise-kids/", CowrywiseKidProfileView.as_view(), name="cowrywise-kids"),
    # Registration
    path("register/", RegistrationV2View.as_view(), name="register"),
    path("pre-register/", PreRegistrationView.as_view(), name="pre-register"),
    # Authentication
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path(
        "auth/password-change/request/",
        RequestPasswordChangeView.as_view(),
        name="request-password-change",
    ),
    path(
        "auth/password-change/confirm-otp/",
        PasswordChangeOTPConfirmView.as_view(),
        name="verify-password-change-otp",
    ),
    path(
        "auth/password-change/",
        PasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "auth/password-change/resend-otp/",
        ResendPasswordChangeOTPView.as_view(),
        name="resend-password-change-otp",
    ),
    path("verify-email-otp/", VerifyEmailOTPView.as_view(), name="verify-email-otp"),
    path("send-email-otp/", SendEmailOTPView.as_view(), name="send-email-otp"),
]
