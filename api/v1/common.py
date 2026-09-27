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



__all__ = [name for name in globals() if not name.startswith("__")]

