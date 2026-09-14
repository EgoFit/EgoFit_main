from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from account.froms import BirthDateForm, BloodGroupForm, CoachRequestForm, HeightForm, WeightForm, validate_coach_request_file
from account.models import (
    ClientDocument,
    ClientDocumentPayment,
    CoachRequest,
    User,
    WorkoutPerformanceRecord,
    WorkoutProgram,
    WorkoutProgramDay,
    WorkoutProgramExercise,
)
from account.services import AuthService, NotificationService, OTPService, PasswordService, ProfileService
from account.services.coach_request_service import CoachRequestService
from account.services.access_payment_service import AccessPaymentService
from account.validators import validate_fullname, validate_phone_number, validate_strong_password
from api.auth import _hash_token, issue_token_pair, revoke_user_tokens, rotate_token_pair
from api.decorators import api_auth_required, api_endpoint, api_methods
from api.limits import rate_limit
from api.models import ApiToken
from api.responses import error, ok
from api.utils import absolute_file_url, json_value, parse_int, request_data
from cart.card_models import Cart
from cart.exceptions import PaymentProviderException, PaymentVerificationException
from cart.providers.zarinpal_provider import ZarinPalPaymentProvider
from cart.models import Order
from cart.services import PaymentService, apply_discount, build_order_from_cart
from cart.selectors.order_selector import OrderSelector
from cart.zarinpal import build_payment_callback_url
from home.forms import CommentSectionForm, ReplyForm
from home.models import ArticleBlogModel, CommentSectionModel, Episode, Reply, SeriesModel
from home.selectors.article_selector import ArticleSelector
from home.selectors.comment_selector import CommentSelector
from home.selectors.course_selector import CourseSelector
from home.services import CommentService, SearchService, SeriesService, VideoService


auth_service = AuthService()
otp_service = OTPService()
profile_service = ProfileService()
password_service = PasswordService()
comment_service = CommentService()
coach_request_service = CoachRequestService()
notification_service = NotificationService()
payment_service = PaymentService()
access_payment_service = AccessPaymentService()
series_service = SeriesService()


def _user_data(request, user):
    return {
        "id": user.pk,
        "fullname": user.fullname,
        "display_name": user.display_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "biography": user.biography,
        "birth_date_jalali": user.birth_date_jalali,
        "weight_kg": json_value(user.weight_kg),
        "height_cm": json_value(user.height_cm),
        "blood_group": user.blood_group,
        "gender": user.gender,
        "activity_level": user.activity_level,
        "profile_picture": absolute_file_url(request, user.profile_picture),
    }


def _serialize_user(request, user):
    return _user_data(request, user)


def _serialize_series(request, series, *, include_description=True):
    payload = {
        "id": series.pk,
        "title": series.title,
        "free": series.free,
        "completed": series.is_compeleted,
        "seasons": series.seseaons,
        "hours": series.hours,
        "main_price": series.main_price,
        "discount_price": series.discount_price,
        "image": absolute_file_url(request, series.image),
        "author": {"id": series.author_id, "fullname": series.author.fullname} if series.author_id else None,
        "category": {"id": series.language_kinds_id, "title": series.language_kinds.title} if series.language_kinds_id else None,
    }
    if include_description:
        payload.update({"description": series.description, "introduction": series.introdution_course})
    return payload


def _serialize_article(request, article, *, detail=False):
    payload = {
        "id": article.pk,
        "slug": article.slug,
        "title": article.title,
        "reading_time": article.reading_time,
        "excerpt": article.article_excerpt,
        "image": absolute_file_url(request, article.image),
        "author": {"id": article.author_id, "fullname": article.author.fullname} if article.author_id else None,
    }
    if detail:
        payload.update({"description": article.article_description, "built_in": article.built_in})
    return payload


def _serialize_comment(comment):
    return {
        "id": comment.pk,
        "text": comment.text,
        "created_at": json_value(comment.created_at),
        "author": {"id": comment.user_id, "fullname": comment.user.fullname} if comment.user_id else None,
        "replies": [
            {
                "id": reply.pk,
                "text": reply.text,
                "created_at": json_value(reply.created_at),
                "author": {"id": reply.user_id, "fullname": reply.user.fullname} if reply.user_id else None,
            }
            for reply in getattr(comment, "active_replies", [])
        ],
    }


def _serialize_order(order):
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "subtotal_price": order.subtotal_price,
        "discount_amount": order.discount_amount,
        "total_price": order.total_price,
        "is_paid": order.is_paid,
        "status": order.status,
        "created_at": json_value(order.created_at),
        "paid_at": json_value(order.paid_at),
        "items": [
            {"product_id": item.product_id, "title": item.product.title, "price": item.price}
            for item in order.items.all()
        ],
    }


def _serialize_program(program):
    return {
        "id": program.pk,
        "title": program.title,
        "start_date": json_value(program.start_date),
        "end_date": json_value(program.end_date),
        "notes": program.notes,
        "supplements_note": program.supplements_note,
        "warmup_notes": program.warmup_notes,
        "cooldown_notes": program.cooldown_notes,
        "days": [
            {
                "id": day.pk,
                "name": day.name,
                "order": day.order,
                "notes": day.notes,
                "exercises": [
                    {
                        "id": item.pk,
                        "exercise": {"id": item.exercise_id, "name": item.exercise.name},
                        "superset_exercise": {"id": item.superset_exercise_id, "name": item.superset_exercise.name} if item.superset_exercise_id else None,
                        "third_exercise": {"id": item.third_exercise_id, "name": item.third_exercise.name} if item.third_exercise_id else None,
                        "sets": item.sets,
                        "reps": item.reps,
                        "rest": item.rest,
                        "note": item.note,
                        "order": item.order,
                    }
                    for item in day.items.all()
                ],
            }
            for day in program.days.all()
        ],
    }


def _reject_unknown(data, allowed):
    unknown = set(data.keys()) - set(allowed)
    if unknown:
        raise ValidationError({"fields": [f"Unsupported fields: {', '.join(sorted(unknown))}"]})


@api_endpoint
@api_methods("GET")
def health(request):
    return ok({"status": "ok", "api_version": "v1"})


@api_endpoint
@api_methods("POST")
@rate_limit(name="register", limit=5, window=900)
def register(request):
    data = request_data(request)
    _reject_unknown(data, {"fullname", "phone", "password", "device_name"})
    fullname = str(data.get("fullname") or "").strip()
    phone = validate_phone_number(data.get("phone"))
    password = str(data.get("password") or "")
    validate_fullname(fullname)
    validate_strong_password(password)
    user = auth_service.register_user(fullname=fullname, phone=phone, password=password)
    return ok({"user": _serialize_user(request, user), **issue_token_pair(user=user, name=data.get("device_name", ""))}, status=201)


@api_endpoint
@api_methods("POST")
@rate_limit(name="login", limit=10, window=900)
def login(request):
    data = request_data(request)
    _reject_unknown(data, {"fullname", "password", "device_name"})
    fullname = str(data.get("fullname") or "").strip()
    password = str(data.get("password") or "")
    user = authenticate(username=fullname, password=password)
    if user is None or not user.is_active:
        return error("invalid_credentials", "Invalid credentials.", status=401)
    return ok({"user": _serialize_user(request, user), **issue_token_pair(user=user, name=data.get("device_name", ""))})


@api_endpoint
@api_methods("POST")
@rate_limit(name="otp-request", limit=5, window=900)
def otp_request(request):
    data = request_data(request)
    _reject_unknown(data, {"phone"})
    phone = validate_phone_number(data.get("phone"))
    # Keep the token opaque and never return the OTP code in an API response.
    result = otp_service.create_otp(phone)
    return ok({"verification_token": result.token, "expires_in": 300})


@api_endpoint
@api_methods("POST")
@rate_limit(name="otp-verify", limit=10, window=900)
def otp_verify(request):
    data = request_data(request)
    _reject_unknown(data, {"verification_token", "code", "device_name"})
    verification_token = str(data.get("verification_token") or "").strip()
    try:
        code = int(str(data.get("code") or "").strip())
    except ValueError:
        return error("invalid_otp", "The verification code is invalid.", status=400)
    otp = otp_service.validate_otp(token=verification_token, code=code)
    user, _created = auth_service.get_or_create_otp_user(phone=otp.phone)
    otp_service.consume_otp(otp)
    return ok({"user": _serialize_user(request, user), **issue_token_pair(user=user, name=data.get("device_name", ""))})


@api_endpoint
@api_methods("POST")
@rate_limit(name="refresh", limit=20, window=900)
def refresh(request):
    data = request_data(request)
    _reject_unknown(data, {"refresh_token"})
    pair = rotate_token_pair(str(data.get("refresh_token") or "").strip())
    if pair is None:
        return error("invalid_refresh_token", "The refresh token is invalid or expired.", status=401)
    return ok(pair)


@api_endpoint
@api_methods("POST")
def logout(request):
    raw_refresh = str((request_data(request) or {}).get("refresh_token") or "").strip()
    token = getattr(request, "api_token", None)
    if token:
        ApiToken.objects.filter(family_id=token.family_id, revoked_at__isnull=True).update(revoked_at=timezone.now())
    if raw_refresh:
        refresh_token = ApiToken.objects.filter(token_hash=_hash_token(raw_refresh)).first()
        if refresh_token:
            ApiToken.objects.filter(family_id=refresh_token.family_id, revoked_at__isnull=True).update(revoked_at=timezone.now())
    return ok({"logged_out": True})


@api_endpoint
@api_methods("GET", "PATCH")
@api_auth_required
def me(request):
    if request.method == "GET":
        return ok({"user": _serialize_user(request, request.user), "metrics": profile_service.get_profile_metrics(request.user)})
    data = request_data(request)
    allowed = {"first_name", "last_name", "display_name", "email", "biography", "web_site", "github", "linkdin", "telegram"}
    unknown = set(data) - allowed
    if unknown:
        raise ValidationError({"fields": [f"Unsupported fields: {', '.join(sorted(unknown))}"]})
    for field in allowed:
        if field in data:
            value = data[field]
            if field == "email":
                from django.forms import EmailField

                value = EmailField(required=False).clean(value)
                if request.user.__class__.objects.filter(email=value).exclude(pk=request.user.pk).exists():
                    raise ValidationError({"email": "This email is already in use."})
            setattr(request.user, field, value)
    request.user.save(update_fields=[field for field in allowed if field in data])
    return ok({"user": _serialize_user(request, request.user)})


@api_endpoint
@api_methods("PATCH")
@api_auth_required
def metric(request, metric_name):
    data = request_data(request)
    form_map = {
        "weight": (WeightForm, "weight", "weight_kg"),
        "height": (HeightForm, "height", "height_cm"),
        "birth_date": (BirthDateForm, "birth_date", "birth_date_jalali"),
        "blood_group": (BloodGroupForm, "blood_group", "blood_group"),
    }
    if metric_name not in form_map:
        return error("not_found", "Metric not found.", status=404)
    form_class, input_name, model_field = form_map[metric_name]
    form = form_class(data={input_name: data.get(input_name)})
    if not form.is_valid():
        raise ValidationError(form.errors)
    profile_service.update_profile_metric(user=request.user, field_name=model_field, value=form.cleaned_data[input_name])
    return ok({"user": _serialize_user(request, request.user), "metric": metric_name})


@api_endpoint
@api_methods("POST")
@api_auth_required
def password_change(request):
    data = request_data(request)
    _reject_unknown(data, {"old_password", "new_password"})
    old_password = str(data.get("old_password") or "")
    new_password = str(data.get("new_password") or "")
    validate_strong_password(new_password)
    password_service.change_password(user=request.user, old_password=old_password, new_password=new_password)
    revoke_user_tokens(request.user)
    return ok({"changed": True})


@api_endpoint
@api_methods("POST")
@rate_limit(name="password-reset-request", limit=5, window=900)
def password_reset_request(request):
    data = request_data(request)
    _reject_unknown(data, {"phone"})
    phone = validate_phone_number(data.get("phone"))
    if not User.objects.filter(phone=phone, is_active=True).exists():
        # Avoid account enumeration while keeping the response useful to a
        # legitimate client.
        return ok({"accepted": True, "message": "If the account exists, a verification code was sent."}, status=202)
    result = otp_service.create_otp(phone)
    return ok({"accepted": True, "verification_token": result.token, "expires_in": 300})


@api_endpoint
@api_methods("POST")
@rate_limit(name="password-reset-confirm", limit=10, window=900)
def password_reset_confirm(request):
    data = request_data(request)
    _reject_unknown(data, {"verification_token", "code", "new_password"})
    validate_strong_password(str(data.get("new_password") or ""))
    try:
        code = int(str(data.get("code") or "").strip())
    except ValueError:
        return error("invalid_otp", "The verification code is invalid.", status=400)
    otp = otp_service.validate_otp(token=str(data.get("verification_token") or "").strip(), code=code)
    user = User.objects.filter(phone=otp.phone, is_active=True).first()
    if user is None:
        otp_service.consume_otp(otp)
        return error("invalid_reset", "The password reset request is invalid.", status=400)
    password_service.reset_password(user=user, new_password=str(data.get("new_password")))
    otp_service.consume_otp(otp)
    revoke_user_tokens(user)
    return ok({"reset": True})


@api_endpoint
@api_methods("POST")
@api_auth_required
@rate_limit(name="phone-change-request", limit=5, window=900)
def phone_change_request(request):
    data = request_data(request)
    _reject_unknown(data, {"phone"})
    phone = validate_phone_number(data.get("phone"))
    if User.objects.filter(phone=phone).exclude(pk=request.user.pk).exists():
        return error("phone_unavailable", "This phone number is already in use.", status=409)
    result = otp_service.create_otp(phone)
    return ok({"verification_token": result.token, "expires_in": 300})


@api_endpoint
@api_methods("POST")
@api_auth_required
@rate_limit(name="phone-change-confirm", limit=10, window=900)
def phone_change_confirm(request):
    data = request_data(request)
    _reject_unknown(data, {"verification_token", "code"})
    try:
        code = int(str(data.get("code") or "").strip())
    except ValueError:
        return error("invalid_otp", "The verification code is invalid.", status=400)
    with transaction.atomic():
        otp = otp_service.validate_otp(token=str(data.get("verification_token") or "").strip(), code=code)
        if User.objects.filter(phone=otp.phone).exclude(pk=request.user.pk).exists():
            otp_service.consume_otp(otp)
            return error("phone_unavailable", "This phone number is already in use.", status=409)
        request.user.phone = otp.phone
        request.user.save(update_fields=["phone"])
        otp_service.consume_otp(otp)
    return ok({"user": _serialize_user(request, request.user)})


@api_endpoint
@api_methods("GET")
@api_auth_required
def dashboard(request):
    context = profile_service.get_dashboard_context(request.user)
    return ok({
        "cards": context["dashboard_cards"],
        "profile_metrics": context["profile_metrics"],
        "feed": context["dashboard_feed"],
        "counts": {
            "courses": context["learning_courses_count"],
            "orders": context["paid_orders_count"],
            "comments": context["comments_count"],
            "notifications": context["notifications_count"],
        },
    })


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
@api_methods("GET")
@api_auth_required
def courses(request):
    return ok({"items": [_serialize_series(request, item, include_description=False) for item in profile_service.get_learning_courses(request.user)]})


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
def orders(request):
    return ok({"items": [_serialize_order(order) for order in profile_service.get_paid_orders(request.user)]})


@api_endpoint
@api_methods("GET")
@api_auth_required
def notifications(request):
    items = notification_service.get_profile_notifications(request.user, limit=50)
    return ok({"items": [
        {"id": getattr(item, "pk", None), "title": item.title, "message": item.message, "created_at": json_value(item.created_at), "read": getattr(item, "read", False), "global": getattr(item, "is_global", False)}
        for item in items
    ]})


@api_endpoint
@api_methods("POST")
@api_auth_required
def mark_notification_read(request, pk):
    from account.models import Notification

    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.read = True
    notification.save(update_fields=["read"])
    return ok({"read": True})


@api_endpoint
@api_methods("GET", "POST")
@api_auth_required
def coach_request(request):
    if request.method == "GET":
        items = request.user.coach_requests.all()[:20]
        return ok({"items": [{"id": item.pk, "status": item.status, "created_at": json_value(item.created_at), "updated_at": json_value(item.updated_at)} for item in items]})
    pending = coach_request_service.get_pending_for_user(request.user).first()
    allowed = set(CoachRequestForm.Meta.fields) | {"attachments"}
    unknown = set(request_data(request).keys()) - allowed
    if unknown:
        raise ValidationError({"fields": [f"Unsupported fields: {', '.join(sorted(unknown))}"]})
    uploads = request.FILES.getlist("attachments")
    if len(uploads) > 10:
        raise ValidationError({"attachments": "At most 10 attachments may be submitted."})
    for uploaded in uploads:
        validate_coach_request_file(uploaded)
    form = CoachRequestForm(data=request_data(request), files=request.FILES, instance=pending)
    if not form.is_valid():
        raise ValidationError(form.errors)
    item = coach_request_service.save_request(user=request.user, form=form, files=request.FILES.getlist("attachments"))
    return ok({"request": {"id": item.pk, "status": item.status}}, status=201 if pending is None else 200)


@api_endpoint
@api_methods("GET")
@api_auth_required
def programs(request):
    queryset = WorkoutProgram.objects.filter(user=request.user, is_published=True).prefetch_related(
        "days__items__exercise", "days__items__superset_exercise", "days__items__third_exercise"
    )
    return ok({"items": [_serialize_program(program) for program in queryset]})


@api_endpoint
@api_methods("POST")
@api_auth_required
def program_performance(request, pk):
    data = request_data(request)
    program = get_object_or_404(WorkoutProgram, pk=pk, user=request.user, is_published=True)
    records = data.get("records", [])
    if not isinstance(records, list) or len(records) > 100:
        raise ValidationError({"records": "records must be an array with at most 100 items."})
    day_id = data.get("day_id")
    day = None
    if day_id is not None:
        day = get_object_or_404(WorkoutProgramDay, pk=day_id, program=program)
    saved = 0
    with transaction.atomic():
        for entry in records:
            if not isinstance(entry, dict):
                raise ValidationError({"records": "Each record must be an object."})
            item = get_object_or_404(WorkoutProgramExercise.objects.select_related("exercise", "superset_exercise", "third_exercise", "day"), pk=entry.get("program_exercise_id"), day__program=program)
            if day is not None and item.day_id != day.pk:
                raise ValidationError({"program_exercise_id": "The exercise does not belong to day_id."})
            exercise_id = parse_int(entry.get("exercise_id"), field="exercise_id")
            if exercise_id not in {item.exercise_id, item.superset_exercise_id, item.third_exercise_id}:
                raise ValidationError({"exercise_id": "The exercise is not part of this program item."})
            mode = str(entry.get("mode") or "")
            if mode not in WorkoutPerformanceRecord.Mode.values:
                raise ValidationError({"mode": "Invalid performance mode."})
            repetitions = str(entry.get("repetitions") or "").strip()[:60]
            set_number = parse_int(entry.get("set_number"), field="set_number")
            if not repetitions or set_number < 1:
                raise ValidationError({"record": "repetitions and a positive set_number are required."})
            try:
                value = Decimal(str(entry.get("value")))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError({"value": "value must be a positive number."})
            if value <= 0 or value > Decimal("999999.99"):
                raise ValidationError({"value": "value must be between 0 and 999999.99."})
            record, created = WorkoutPerformanceRecord.objects.select_for_update().get_or_create(
                user=request.user, exercise_id=exercise_id, repetitions=repetitions, mode=mode, set_number=set_number,
                defaults={"program": program, "program_exercise": item, "value": value},
            )
            if not created and value > record.value:
                record.value = value
                record.program = program
                record.program_exercise = item
                record.save(update_fields=["value", "program", "program_exercise", "updated_at"])
            saved += 1
        if "difficulty" in data:
            difficulty = parse_int(data.get("difficulty"), field="difficulty")
            if not 0 <= difficulty <= 10:
                raise ValidationError({"difficulty": "difficulty must be between 0 and 10."})
            from account.models import WorkoutProgramFeedback

            WorkoutProgramFeedback.objects.update_or_create(program=program, day=day, defaults={"difficulty": difficulty})
    return ok({"saved_records": saved})


@api_endpoint
@api_methods("GET")
@api_auth_required
def cart_detail(request):
    cart = Cart(request)
    return ok({"items": [
        {"product": _serialize_series(request, item["product"], include_description=False), "quantity": item.get("quantity", 1), "price": item.get("price")}
        for item in cart
    ], "total_price": str(cart.total_price)})


@api_endpoint
@api_methods("POST")
@api_auth_required
def cart_add(request, pk):
    product = get_object_or_404(SeriesModel, pk=pk)
    if OrderSelector.user_has_paid_product(user=request.user, product=product):
        return error("already_owned", "You already own this course.", status=409)
    cart = Cart(request)
    cart.add(quantity=1, product=product)
    return cart_detail(request)


@api_endpoint
@api_methods("DELETE")
@api_auth_required
def cart_delete(request, pk):
    cart = Cart(request)
    cart.delete(str(pk))
    return cart_detail(request)


@api_endpoint
@api_methods("DELETE")
@api_auth_required
def cart_empty(request):
    Cart(request).remove()
    return ok({"empty": True})


@api_endpoint
@api_methods("POST")
@api_auth_required
def order_create(request):
    order = build_order_from_cart(user=request.user, cart=Cart(request))
    Cart(request).remove()
    return ok({"order": _serialize_order(order)}, status=201)


@api_endpoint
@api_methods("POST")
@api_auth_required
def order_discount(request, pk):
    data = request_data(request)
    order = get_object_or_404(Order, pk=pk, user=request.user, is_paid=False)
    order, discount_amount = apply_discount(order_id=order.pk, user=request.user, raw_code=data.get("discount_code"))
    return ok({"order": _serialize_order(order), "discount_amount": discount_amount})


@api_endpoint
@api_methods("POST")
@api_auth_required
def order_payment(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user, is_paid=False)
    callback_url = build_payment_callback_url(request, url_name="api:payment_verify")
    redirect_url = payment_service.initiate_payment(order=order, callback_url=callback_url)
    return ok({"order_id": order.pk, "redirect_url": redirect_url})


@api_endpoint
@api_methods("POST")
@api_auth_required
def document_payment(request, pk):
    document = get_object_or_404(ClientDocument, pk=pk, user=request.user)
    if not document.requires_payment or document.price <= 0:
        return error("payment_not_required", "This document does not require payment.", status=400)
    result = access_payment_service.initiate_document(
        document_id=document.pk,
        user=request.user,
        callback_url=build_payment_callback_url(request, url_name="api:document_payment_verify"),
    )
    if result.already_paid:
        return ok({"document_id": document.pk, "already_paid": True})
    return ok({"document_id": document.pk, "payment_id": result.payment_id, "redirect_url": result.redirect_url})

    if ClientDocumentPayment.objects.filter(document=document, user=request.user, status=ClientDocumentPayment.Status.PAID).exists():
        return ok({"document_id": document.pk, "already_paid": True})
    payment = ClientDocumentPayment.objects.filter(
        document=document, user=request.user, status=ClientDocumentPayment.Status.INITIATED
    ).first()
    if payment is None:
        payment = ClientDocumentPayment.objects.create(document=document, user=request.user, amount=document.price)
    result = ZarinPalPaymentProvider().request_payment(
        amount=payment.amount,
        callback_url=build_payment_callback_url(request, url_name="api:document_payment_verify"),
        description=f"دریافت فایل {document.title}",
        mobile=request.user.phone,
        email=request.user.email or None,
    )
    payment.authority = result.authority
    payment.status = ClientDocumentPayment.Status.INITIATED
    payment.save(update_fields=["authority", "status"])
    return ok({"document_id": document.pk, "payment_id": payment.pk, "redirect_url": result.redirect_url})


@api_endpoint
@api_methods("GET")
def payment_verify(request):
    authority = (request.GET.get("Authority") or "").strip()
    status = (request.GET.get("Status") or "").strip().upper()
    if not authority:
        return error("invalid_callback", "Payment authority is missing.")
    result = payment_service.verify_callback(authority=authority, status=status)
    if result.is_missing_order:
        return error("not_found", "Payment order was not found.", status=404)
    return ok({"state": result.state, "ref_id": result.ref_id, "order_id": result.order.pk if result.order else None})


@api_endpoint
@api_methods("GET")
def document_payment_verify(request):
    authority = (request.GET.get("Authority") or "").strip()
    status = (request.GET.get("Status") or "").strip().upper()
    result = access_payment_service.verify_document(authority=authority, status=status)
    if result.payment is None:
        return error("not_found", "Document payment was not found.", status=404)
    if result.state not in {"paid", "already_paid"}:
        return error("payment_failed", result.message or "Document payment could not be verified.")
    return ok({"state": result.state, "document_id": result.payment.document_id, "ref_id": result.ref_id})

    payment = ClientDocumentPayment.objects.filter(
        authority=authority, status=ClientDocumentPayment.Status.INITIATED
    ).select_related("document", "user").first()
    if payment is None:
        return error("not_found", "Document payment was not found.", status=404)
    if status != "OK":
        payment.status = ClientDocumentPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return ok({"state": "failed", "document_id": payment.document_id})
    try:
        result = ZarinPalPaymentProvider().verify_payment(amount=payment.amount, authority=authority)
    except PaymentVerificationException as exc:
        payment.status = ClientDocumentPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return error("payment_failed", str(exc))
    if not result.success:
        payment.status = ClientDocumentPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return error("payment_failed", result.message or "Document payment could not be verified.")
    payment.status = ClientDocumentPayment.Status.PAID
    payment.ref_id = result.ref_id or ""
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "ref_id", "paid_at"])
    return ok({"state": "paid", "document_id": payment.document_id, "ref_id": payment.ref_id})


@api_endpoint
@api_methods("GET")
@api_auth_required
def document_download(request, pk):
    document = get_object_or_404(ClientDocument, pk=pk, user=request.user)
    if document.requires_payment and not ClientDocumentPayment.objects.filter(document=document, user=request.user, status=ClientDocumentPayment.Status.PAID).exists():
        return error("payment_required", "This document requires payment.", status=403)
    document.file.open("rb")
    response = FileResponse(document.file, as_attachment=True, filename=os.path.basename(document.file.name))
    response["Cache-Control"] = "private, no-store"
    return response


@api_endpoint
@api_methods("GET")
@api_auth_required
def episode_video(request, pk):
    episode = get_object_or_404(Episode.objects.select_related("season__series"), pk=pk)
    return VideoService.get_video_response(episode=episode, user=request.user, range_header=request.headers.get("Range"))
