from __future__ import annotations

from home.models import Comment, CommentSectionModel, Reply, SeriesModel


class CommentRepository:
    def create_contact_comment(self, *, comment: str, name: str, email: str, phone: str | None = None, user=None) -> Comment:
        return Comment.objects.create(comment=comment, name=name, email=email, phone=phone or "", user=user)

    def create_series_comment(self, *, series: SeriesModel, user, text: str) -> CommentSectionModel:
        return CommentSectionModel.objects.create(series=series, user=user, text=text)

    def create_reply(self, *, parent_comment: CommentSectionModel, user, text: str) -> Reply:
        return Reply.objects.create(comment=parent_comment, user=user, text=text)

    def get_active_parent_comment(self, *, series: SeriesModel, comment_id: int) -> CommentSectionModel:
        return CommentSectionModel.objects.get(pk=comment_id, series=series, is_active=True)
