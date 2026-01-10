from django.urls import path
from .views import RegistrationV2View, PreRegistrationView, SupportUsView

app_name = "vmlc-v2"

urlpatterns = [
    path("register/", RegistrationV2View.as_view(), name="register"),
    path("pre-register/", PreRegistrationView.as_view(), name="pre-register"),
    path("support-us/", SupportUsView.as_view(), name="support-us"),
]
