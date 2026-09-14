from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from functools import wraps


def get_post_login_redirect_url(user) -> str:
    if getattr(user, "is_admin", False):
        return reverse("register:admin_search")
    return reverse("home:home")


class AdminRequiredMixin(LoginRequiredMixin):
    login_url = "/accounts/register/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_admin:
            return redirect("register:profile")
        return super().dispatch(request, *args, **kwargs)


class UserPortalRequiredMixin(LoginRequiredMixin):
    login_url = "/accounts/register/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_admin:
            return redirect("register:admin_search")
        return super().dispatch(request, *args, **kwargs)


def user_portal_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('register:register')}?next={request.path}")
        if request.user.is_admin:
            return redirect("register:admin_search")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
