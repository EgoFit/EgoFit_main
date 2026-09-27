from django.urls import include, path

from api.v1.library import views

app_name = "library"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("filters/", views.filters, name="filters"),
    path("exercises/", views.exercise_list, name="exercise_list"),
    path("exercises/<int:pk>/", views.exercise_detail, name="exercise_detail"),
    path("corrective-exercises/", views.corrective_exercise_list, name="corrective_exercise_list"),
    path("corrective-exercises/<int:pk>/", views.corrective_exercise_detail, name="corrective_exercise_detail"),
    path("muscles/", views.muscle_list, name="muscle_list"),
    path("muscles/<int:pk>/", views.muscle_detail, name="muscle_detail"),
    path("<slug:lookup>/", views.lookup_list, name="lookup_list"),
    path("<slug:lookup>/<int:pk>/", views.lookup_detail, name="lookup_detail"),
]
