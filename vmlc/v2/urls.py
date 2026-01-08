from django.urls import path
from vmlc.v2.views.registration import RegistrationV2View, PreRegistrationView

app_name = "vmlc-v2"

urlpatterns = [
    path("register/", RegistrationV2View.as_view(), name="register"),
    path("pre-register/", PreRegistrationView.as_view(), name="pre-register")
]
