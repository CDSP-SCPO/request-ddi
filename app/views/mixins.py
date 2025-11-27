from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class StaffRequiredMixin(AccessMixin):
    """Mixin pour n'autoriser que les utilisateurs staff."""
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_staff:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


def staff_required_json(view_func):
    """Décorateur pour les vues API : renvoie du JSON."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_staff:
            return JsonResponse({"error": "Accès interdit"}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_required_html(view_func):
    """Décorateur pour les vues web : redirige vers login ou page interdite."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect(f"{reverse('app:login')}?next={request.path}")
        if not user.is_staff:
            return redirect("forbidden")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
