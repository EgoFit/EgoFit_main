from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.HomeView.as_view(), name="home"),
    path('contact_us/', views.comment_view, name="contact_us"),
    path('about_us/', views.AboutView.as_view(), name="about_us"),
    path('series/', views.SeriesView.as_view(), name="series"),
    path('article/detail/<slug:slug>/', views.ArticleDetailView.as_view(), name="article_detail"),
    path('search/', views.SearchProductView.as_view(), name="search"),
    path('course/detail/<int:pk>/', views.CourseDetailView.as_view(), name="course_detail"),
    path('course/comment/', views.comment_view, name="course_comment"),
    path('course/handle/', views.handle_form_submission, name="handle_comment"),
    path('blog/', views.BlogView.as_view(), name="blog"),  # این خط اصلاح شد
    path('blog/search/', views.BlogProductView.as_view(), name="blog_search"),
    path('series/epidos/<int:pk>/', views.SeriesEpisodeDetailView.as_view(), name="series_episod"),
    path('episodes/<int:pk>/video/', views.EpisodeVideoStreamView.as_view(), name="episode_video"),
    path('workout-library/', views.WorkoutLibraryView.as_view(), name='workout_library'),
    path('workout-library/bodybuilding/', views.WorkoutBodybuildingView.as_view(), name='workout_bodybuilding'),
    path('workout-library/corrective/', views.WorkoutCorrectiveLibraryView.as_view(), name='workout_corrective_library'),
    path('workout-library/musculology/', views.WorkoutMusculologyView.as_view(), name='workout_musculology'),
    path('workout-library/body-part/<int:pk>/', views.WorkoutBodyPartView.as_view(), name='workout_body_part'),
    path('workout-library/abnormality/<int:pk>/', views.WorkoutAbnormalityView.as_view(), name='workout_abnormality'),
    path('workout-library/muscle/<int:pk>/', views.WorkoutMuscleView.as_view(), name='workout_muscle'),
]
