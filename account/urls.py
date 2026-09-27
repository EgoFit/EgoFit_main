from django.urls import include, path

app_name = "register"

urlpatterns = [
    path("", include("account.auth.urls")),
    path("", include("account.profile.urls")),
    path("", include("account.workouts.urls")),
    path("", include("account.documents.urls")),
    path("", include("account.admin_portal.urls")),
]
