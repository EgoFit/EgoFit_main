from __future__ import annotations

from django.db.models import Prefetch, Q

from account.models import User
from cart.models import Order
from home.models import CommentSectionModel
from account.selectors.course_selector import CourseSelector


class UserSelector:
    @staticmethod
    def search_clients(queryset, query: str):
        query = (query or "").strip()
        if not query:
            return queryset
        filters = Q(fullname__icontains=query) | Q(phone__icontains=query) | Q(display_name__icontains=query)
        if query.isdigit():
            filters |= Q(pk=int(query))
        return queryset.filter(filters)

    @staticmethod
    def get_learning_courses(user: User):
        return CourseSelector.get_learning_courses(user)

    @staticmethod
    def get_learning_courses_count(user: User) -> int:
        return CourseSelector.get_learning_courses(user).count()

    @staticmethod
    def get_paid_orders(user: User):
        return (
            Order.objects.filter(user=user, is_paid=True)
            .select_related("course", "applied_discount_code")
            .prefetch_related("items__product")
            .order_by("-created_at")
        )

    @staticmethod
    def get_paid_orders_count(user: User) -> int:
        return Order.objects.filter(user=user, is_paid=True).count()

    @staticmethod
    def get_user_comments(user: User):
        return (
            CommentSectionModel.objects.filter(user=user)
            .select_related("series")
            .prefetch_related(Prefetch("replies", queryset=CommentSectionModel.objects.none()))
            .order_by("-created_at")
        )

    @staticmethod
    def get_user_comments_count(user: User) -> int:
        return CommentSectionModel.objects.filter(user=user).count()

    @staticmethod
    def get_active_sms_recipients():
        return (
            User.objects.filter(is_active=True)
            .exclude(phone__isnull=True)
            .exclude(phone="")
            .only("id", "phone", "fullname")
            .order_by("id")
        )
