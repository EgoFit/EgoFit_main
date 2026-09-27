from api.v1.common import *

@api_endpoint
@api_methods("GET")
def series_list(request):
    limit = min(max(parse_int(request.GET.get("limit", 20), field="limit"), 1), 50)
    queryset = CourseSelector.get_series_filtered_queryset(free=request.GET.get("free"), category=request.GET.get("category"))
    return ok({"items": [_serialize_series(request, item, include_description=False) for item in queryset[:limit]], "limit": limit})

@api_endpoint
@api_methods("GET")
def series_detail(request, pk):
    series = get_object_or_404(CourseSelector.get_course_detail_queryset(), pk=pk)
    payload = _serialize_series(request, series)
    payload["access"] = CourseSelector.get_user_has_access(user=request.user, series=series)
    payload["seasons"] = [
        {"id": season.pk, "number": season.number, "title": season.title, "episodes": [
            {"id": episode.pk, "episode_number": episode.episode_number, "title": episode.title, "duration": episode.duration}
            for episode in season.episodes.all()
        ]}
        for season in series.seasons.all()
    ]
    payload["comments"] = [_serialize_comment(comment) for comment in CommentSelector.get_active_comments_for_series(series)]
    return ok(payload)

@api_endpoint
@api_methods("GET")
def article_list(request):
    limit = min(max(parse_int(request.GET.get("limit", 20), field="limit"), 1), 50)
    queryset = ArticleSelector.get_blog_queryset(category=request.GET.get("category"))
    return ok({"items": [_serialize_article(request, item) for item in queryset[:limit]], "limit": limit})

@api_endpoint
@api_methods("GET")
def article_detail(request, slug):
    article = get_object_or_404(ArticleBlogModel.objects.select_related("author", "language_kinds"), slug=slug)
    return ok(_serialize_article(request, article, detail=True))

@api_endpoint
@api_methods("GET")
def search(request):
    query = request.GET.get("q", "")
    if request.GET.get("type", "courses") == "blogs":
        items = SearchService.search_blogs(query)
        return ok({"items": [_serialize_article(request, item) for item in items]})
    items = SearchService.search_courses(query)
    return ok({"items": [_serialize_series(request, item, include_description=False) for item in items]})

@api_endpoint
@api_methods("POST")
@api_auth_required
@rate_limit(name="comment", limit=10, window=3600)
def create_comment(request, pk):
    series = get_object_or_404(SeriesModel, pk=pk)
    form = CommentSectionForm(data=request_data(request))
    if not form.is_valid():
        raise ValidationError(form.errors)
    comment = comment_service.submit_series_comment(series=series, user=request.user, cleaned_data=form.cleaned_data)
    return ok({"comment": {"id": comment.pk, "status": "pending"}}, status=201)

@api_endpoint
@api_methods("POST")
@api_auth_required
@rate_limit(name="reply", limit=10, window=3600)
def create_reply(request, pk, comment_id):
    series = get_object_or_404(SeriesModel, pk=pk)
    form = ReplyForm(data=request_data(request))
    if not form.is_valid():
        raise ValidationError(form.errors)
    reply = comment_service.submit_series_comment(series=series, user=request.user, cleaned_data=form.cleaned_data, parent_comment_id=comment_id)
    return ok({"reply": {"id": reply.pk, "status": "pending"}}, status=201)

@api_endpoint
@api_methods("POST")
@api_auth_required
def enroll_free(request, pk):
    series = get_object_or_404(SeriesModel, pk=pk, free=True)
    profile_service.add_free_course_to_profile(user=request.user, series_id=pk, series=series)
    return ok({"enrolled": True, "course_id": series.pk})

@api_endpoint
@api_methods("GET")
@api_auth_required
def episode_video(request, pk):
    episode = get_object_or_404(Episode.objects.select_related("season__series"), pk=pk)
    return VideoService.get_video_response(episode=episode, user=request.user, range_header=request.headers.get("Range"))

