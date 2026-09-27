from django.db import transaction
from django.utils import timezone

from account.models import CoachRequest, CoachRequestAttachment


class CoachRequestService:
    def create_request(self, *, user, form) -> CoachRequest:
        instance = form.save(commit=False)
        instance.user = user
        instance.admin_read_at = None
        instance.save()
        return instance

    @transaction.atomic
    def save_request(self, *, user, form, files=None) -> CoachRequest:
        """Create or update the athlete's pending request (form may be bound to an instance) + attachments."""
        instance = form.save(commit=False)
        instance.user = user
        instance.save()
        for uploaded in files or []:
            CoachRequestAttachment.objects.create(request=instance, file=uploaded)
        return instance

    def get_pending_for_user(self, user):
        return user.coach_requests.filter(status=CoachRequest.Status.PENDING)

    def get_pending_count(self) -> int:
        return CoachRequest.objects.filter(status=CoachRequest.Status.PENDING).count()

    def get_unread_pending_count(self, *, user=None) -> int:
        queryset = CoachRequest.objects.filter(
            status=CoachRequest.Status.PENDING,
            admin_read_at__isnull=True,
        )
        if user is not None:
            queryset = queryset.filter(user=user)
        return queryset.count()

    def get_pending_queryset(self):
        return CoachRequest.objects.filter(status=CoachRequest.Status.PENDING).select_related("user")

    def mark_handled(self, coach_request: CoachRequest) -> None:
        coach_request.status = CoachRequest.Status.HANDLED
        coach_request.handled_at = timezone.now()
        coach_request.admin_read_at = coach_request.admin_read_at or timezone.now()
        coach_request.save(update_fields=["status", "handled_at", "admin_read_at"])

    def mark_pending_as_read(self, *, user=None) -> int:
        queryset = CoachRequest.objects.filter(
            status=CoachRequest.Status.PENDING,
            admin_read_at__isnull=True,
        )
        if user is not None:
            queryset = queryset.filter(user=user)
        return queryset.update(admin_read_at=timezone.now())
