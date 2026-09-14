from __future__ import annotations

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from home.exceptions import CommentSubmissionException
from home.repositories.comment_repository import CommentRepository
from home.models import CommentSectionModel


class CommentService:
    def __init__(self, repository: CommentRepository | None = None):
        self.repository = repository or CommentRepository()

    @transaction.atomic
    def submit_contact_comment(self, *, cleaned_data: dict, user=None):
        return self.repository.create_contact_comment(
            comment=cleaned_data["comment"],
            name=cleaned_data["name"],
            email=cleaned_data["email"],
            phone=cleaned_data.get("phone") or "",
            user=user,
        )

    @transaction.atomic
    def submit_series_comment(self, *, series, user, cleaned_data: dict, parent_comment_id: int | None = None):
        text = cleaned_data["text"]
        if parent_comment_id is not None:
            try:
                parent_comment = self.repository.get_active_parent_comment(series=series, comment_id=parent_comment_id)
            except CommentSectionModel.DoesNotExist as exc:
                raise CommentSubmissionException(_("دیدگاه والد معتبر نیست.")) from exc
            return self.repository.create_reply(parent_comment=parent_comment, user=user, text=text)
        return self.repository.create_series_comment(series=series, user=user, text=text)
