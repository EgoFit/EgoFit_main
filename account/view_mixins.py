class AccountPageMixin:
    """Shared chrome metadata for athlete-facing account pages."""

    active_section = "dashboard"
    account_title = ""
    account_description = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("active_section", self.active_section)
        context.setdefault("account_title", self.account_title)
        context.setdefault("account_description", self.account_description)
        return context
