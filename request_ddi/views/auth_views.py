# -- DJANGO
from django.contrib.auth.views import LoginView

# -- LOCAL
from request_ddi.core.forms import CustomAuthenticationForm


class CustomLoginView(LoginView):
    template_name = "login.html"
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True
