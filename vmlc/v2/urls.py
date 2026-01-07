from django.urls import path
from vmlc.v2.views.registration import RegistrationV2View

app_name = "vmlc-v2"

urlpatterns = [
    path("register/", RegistrationV2View.as_view(), name="register"),
]
