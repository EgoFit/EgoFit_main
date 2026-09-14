from __future__ import annotations

import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, TemplateView
from django.db.models import Q

from home.forms import CommentForm, CommentSectionForm, ReplyForm
from home.exceptions import SearchValidationException
from account.models import CorrectiveExercise, Exercise, ExerciseAbnormalityType, ExerciseBodyPart, Muscle
from home.models import ArticleBlogModel, Episode, SeriesModel
from home.selectors.article_selector import ArticleSelector
from home.selectors.course_selector import CourseSelector
from home.services import CommentService, ContentService, SearchService, SeriesService, VideoService
from home.exceptions import CommentSubmissionException


logger = logging.getLogger(__name__)

content_service = ContentService()
comment_service = CommentService()
search_service = SearchService()
series_service = SeriesService()
video_service = VideoService()


def handle_series_comment_submission(request, series):
    if not request.user.is_authenticated:
        return redirect("register:pass_login")

    comment_id = request.POST.get("comment_id")
    if comment_id:
        reply_form = ReplyForm(request.POST)
        if not reply_form.is_valid():
            messages.error(request, _("متن پاسخ معتبر نیست."))
            return False
        try:
            parent_comment_id = int(comment_id)
        except (TypeError, ValueError):
            messages.error(request, _("شناسه دیدگاه معتبر نیست."))
            return False
        try:
            comment_service.submit_series_comment(
                series=series,
                user=request.user,
                cleaned_data=reply_form.cleaned_data,
                parent_comment_id=parent_comment_id,
            )
        except CommentSubmissionException as exc:
            messages.error(request, str(exc))
            return False
        messages.success(request, _("پاسخ شما ثبت شد و بعد از بررسی نمایش داده می‌شود."))
        return True

    comment_form = CommentSectionForm(request.POST)
    if not comment_form.is_valid():
        messages.error(request, _("متن دیدگاه معتبر نیست."))
        return False

    comment_service.submit_series_comment(series=series, user=request.user, cleaned_data=comment_form.cleaned_data)
    messages.success(request, _("دیدگاه شما ثبت شد و بعد از بررسی نمایش داده می‌شود."))
    return True


class HomeView(TemplateView):
    template_name = "home/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(content_service.get_home_context())
        return context


class WorkoutLibraryView(TemplateView):
    template_name = "home/workout-library.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()
        context.update({
            "query": query,
            "body_parts": ExerciseBodyPart.objects.filter(
                Q(name__icontains=query) | Q(name_en__icontains=query) if query else Q()
            ).order_by("name"),
            "abnormalities": ExerciseAbnormalityType.objects.filter(
                Q(name__icontains=query) | Q(name_en__icontains=query) if query else Q()
            ).order_by("name"),
            "muscles": Muscle.objects.filter(
                Q(name__icontains=query) | Q(name_en__icontains=query) | Q(function_note__icontains=query)
                if query else Q()
            ).order_by("name"),
            "search_result_count": 0,
        })
        context["search_result_count"] = (
            context["body_parts"].count()
            + context["abnormalities"].count()
            + context["muscles"].count()
        )
        return context


class WorkoutBodybuildingView(TemplateView):
    template_name = "home/workout-library-categories.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()
        context["page_title"] = _("تمرینات بدنسازی")
        context["page_description"] = _("حرکت‌های بدنسازی را بر اساس عضله و بخش بدن پیدا کنید.")
        context["page_kind"] = "exercises"
        context["categories"] = ExerciseBodyPart.objects.filter(
            Q(name__icontains=query) | Q(name_en__icontains=query) if query else Q()
        ).order_by("name")
        context["category_url_name"] = "home:workout_body_part"
        context["query"] = query
        return context


class WorkoutCorrectiveLibraryView(TemplateView):
    template_name = "home/workout-library-categories.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()
        context["page_title"] = _("حرکات اصلاحی")
        context["page_description"] = _("حرکت‌های اصلاحی را بر اساس ناهنجاری انتخاب کنید.")
        context["page_kind"] = "correctives"
        context["categories"] = ExerciseAbnormalityType.objects.filter(
            Q(name__icontains=query) | Q(name_en__icontains=query) if query else Q()
        ).order_by("name")
        context["category_url_name"] = "home:workout_abnormality"
        context["query"] = query
        return context


class WorkoutMusculologyView(TemplateView):
    template_name = "home/workout-library-muscles.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()
        muscles = Muscle.objects.all()
        if query:
            muscles = muscles.filter(Q(name__icontains=query) | Q(name_en__icontains=query) | Q(function_note__icontains=query))
        context.update({
            "page_title": _("آناتومی عضلات"),
            "muscles": muscles.order_by("name"),
            "query": query,
        })
        return context


class WorkoutBodyPartView(TemplateView):
    template_name = "home/workout-library-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(ExerciseBodyPart, pk=kwargs["pk"])
        query = (self.request.GET.get("q") or "").strip()
        exercises = Exercise.objects.filter(body_part=category).select_related(
            "primary_muscle", "secondary_muscle", "movement_type", "joint_type",
            "difficulty_level", "equipment_type"
        )
        if query:
            exercises = exercises.filter(Q(name__icontains=query) | Q(name_en__icontains=query) | Q(description__icontains=query))
        context.update({
            "page_title": category.name,
            "page_description": _("حرکت‌های مناسب این بخش بدن را با جزئیات کامل ببینید."),
            "page_kind": "exercises",
            "query": query,
            "items": exercises,
            "category": category,
        })
        return context


class WorkoutAbnormalityView(TemplateView):
    template_name = "home/workout-library-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(ExerciseAbnormalityType, pk=kwargs["pk"])
        query = (self.request.GET.get("q") or "").strip()
        items = CorrectiveExercise.objects.filter(abnormality_type=category).select_related("equipment")
        if query:
            items = items.filter(Q(name__icontains=query) | Q(description__icontains=query))
        context.update({
            "page_title": category.name,
            "page_description": _("حرکت‌های اصلاحی این ناهنجاری را با توضیحات کامل ببینید."),
            "page_kind": "correctives",
            "query": query,
            "items": items,
            "category": category,
        })
        return context


class WorkoutMuscleView(TemplateView):
    template_name = "home/workout-library-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        muscle = get_object_or_404(Muscle, pk=kwargs["pk"])
        context.update({
            "page_title": muscle.name,
            "page_description": _("اطلاعات کامل آناتومیک و عملکردی این عضله."),
            "page_kind": "muscles",
            "items": [muscle],
            "query": "",
            "category": muscle,
        })
        return context


def handle_form_submission(request):
    return comment_view(request)


def comment_view(request):
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment_service.submit_contact_comment(
                cleaned_data=form.cleaned_data,
                user=request.user if request.user.is_authenticated else None,
            )
            messages.success(request, _("پیام شما با موفقیت ارسال شد!"))
            return redirect("home:contact_us")
        messages.error(request, _("خطا در ارسال پیام، لطفا دوباره تلاش کنید."))
    else:
        form = CommentForm()

    context = {"form": form}
    context.update(content_service.get_contact_page_context())
    return render(request, "home/contact-us.html", context)


class AboutView(TemplateView):
    template_name = "home/about-us.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(content_service.get_about_context())
        return context


class SeriesView(TemplateView):
    template_name = "home/series.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = content_service.get_series_list_context(
            free=self.request.GET.get("free"),
            category=self.request.GET.get("category"),
        )
        if filters.get("warning_message"):
            messages.warning(self.request, filters["warning_message"])
        context.update(filters)
        context["archive_mode"] = True
        return context


class ArticleDetailView(DetailView):
    model = ArticleBlogModel
    template_name = "home/article-detail.html"
    queryset = (
        ArticleBlogModel.objects.select_related("author", "language_kinds")
        .prefetch_related("gallery_images", "article_links")
        .all()
    )

    def get_object(self, queryset=None):
        queryset = queryset or self.get_queryset()
        return get_object_or_404(queryset, slug=self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_article"] = self.object
        context["related_articles"] = ArticleSelector.get_related_articles(self.object)
        return context


class SearchProductView(View):
    def render_response(self, request, search=None, product=None, error_message=None):
        result_count = len(product) if product is not None else 0
        return render(
            request,
            "home/search_course.html",
            {
                "search": search,
                "product": product,
                "error_message": error_message,
                "result_count": result_count,
            },
        )

    def get(self, request):
        return self.render_response(request)

    def post(self, request):
        search = request.POST.get("search", "")
        try:
            products = list(search_service.search_courses(search))
        except SearchValidationException as exc:
            return self.render_response(request, search=search, error_message=str(exc))
        if not products:
            return self.render_response(request, search=search, error_message="دوره ای یافت نشد.")

        return self.render_response(request, search=search, product=products)


class CourseDetailView(DetailView):
    template_name = "home/course-detail.html"
    model = SeriesModel
    queryset = CourseSelector.get_course_detail_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(series_service.get_course_detail_context(self.object, user=self.request.user))
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        result = handle_series_comment_submission(request, self.object)
        if hasattr(result, "status_code"):
            return result
        if not result:
            return self.render_to_response(self.get_context_data(), status=400)
        return redirect("home:course_detail", pk=self.object.pk)


class BlogView(TemplateView):
    template_name = "home/blog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = content_service.get_blog_list_context(category=self.request.GET.get("category"))
        if filters.get("warning_message"):
            messages.warning(self.request, filters["warning_message"])
        context.update(filters)
        return context


class BlogProductView(View):
    def render_response(self, request, search=None, blog=None, error_message=None):
        result_count = len(blog) if blog is not None else 0
        return render(
            request,
            "home/search_blog.html",
            {
                "search": search,
                "blog": blog,
                "error_message": error_message,
                "categories": list(search_service.list_blog_categories()),
                "result_count": result_count,
            },
        )

    def get(self, request):
        return self.render_response(request)

    def post(self, request):
        search = request.POST.get("search", "")
        try:
            blog = list(search_service.search_blogs(search))
        except SearchValidationException as exc:
            return self.render_response(request, search=search, error_message=str(exc))
        except Exception:
            logger.exception("Unexpected error while searching blogs.")
            return self.render_response(request, search=search, error_message="خطایی در جستجوی مقاله رخ داد.")
        if not blog:
            return self.render_response(request, search=search, error_message="مقاله ای یافت نشد.")
        return self.render_response(request, search=search, blog=blog, error_message=None)


class SeriesEpisodeDetailView(DetailView):
    model = SeriesModel
    template_name = "home/course-episodes.html"
    queryset = CourseSelector.get_episode_queryset()

    def get(self, request, *args, **kwargs):
        series = self.get_object()
        if not series_service.has_access(user=request.user, series=series):
            raise Http404("You do not have access to this page")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(series_service.get_series_episode_context(self.object, user=self.request.user))
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        result = handle_series_comment_submission(request, self.object)
        if hasattr(result, "status_code"):
            return result
        if not result:
            return self.render_to_response(self.get_context_data(), status=400)
        return redirect("home:series_episod", pk=self.object.pk)


class EpisodeVideoStreamView(LoginRequiredMixin, View):
    def get(self, request, pk):
        episode = get_object_or_404(Episode.objects.select_related("season__series"), pk=pk)
        return video_service.get_video_response(
            episode=episode,
            user=request.user,
            range_header=request.headers.get("Range"),
        )
