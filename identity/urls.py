from django.urls import path

from .views import CowrywiseKidProfileView

app_name = "identity"

urlpatterns = [
    path("cowrywise-kids/", CowrywiseKidProfileView.as_view(), name="cowrywise-kids"),
]
