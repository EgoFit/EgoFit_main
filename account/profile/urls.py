from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/mood/", views.ProfileMoodView.as_view(), name="profile_mood"),
    path("profile/analysis/", views.ProfileAnalysisView.as_view(), name="profile_analysis"),
    path("profile_courses/", views.ProfileCoursesView.as_view(), name="profile_course"),
    path("profile/coach/", views.ProfileCoachView.as_view(), name="profile_coach"),
    path("profile_financial/", views.ProfileFinancialView.as_view(), name="profile_financial"),
    path("profile_comments/", views.ProfileCommentsView.as_view(), name="profile_comments"),
    path("profile_notifications/", views.ProfileNotificationsView.as_view(), name="profile_notifications"),
    path("profile_useredit/", views.edit_user_profile, name="profile_useredit"),
    path("profile/metric/<slug:metric>/", views.ProfileMetricEditView.as_view(), name="profile_metric_edit"),
    path("profile/weight/", views.ProfileMetricEditView.as_view(), {"metric": "weight"}, name="profile_weight_edit"),
    path("profile/height/", views.ProfileMetricEditView.as_view(), {"metric": "height"}, name="profile_height_edit"),
    path("profile/birth-date/", views.ProfileMetricEditView.as_view(), {"metric": "birth_date"}, name="profile_birth_date_edit"),
    path("profile/blood-group/", views.ProfileMetricEditView.as_view(), {"metric": "blood_group"}, name="profile_blood_group_edit"),
    path("add_course/<int:series_id>/", views.AddCourseToProfileView.as_view(), name="add_course_to_profile"),
]
