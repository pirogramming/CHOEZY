from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    UserSerializer,
    UsernameAvailabilitySerializer,
)
from .forms import SignupBasicForm, SignupProfileForm

User = get_user_model()
PENDING_SIGNUP_SESSION_KEY = "pending_signup"


# ==========================
# Template Views (Frontend)
# ==========================

@require_http_methods(["GET", "POST"])
def login_view(request):
    """이메일과 비밀번호로 로그인하고 Django 세션을 생성합니다."""
    if request.user.is_authenticated:
        return redirect("core:home")

    next_url = request.POST.get("next") or request.GET.get("next") or ""
    context = {
        "next": next_url,
        "email": "",
    }

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        context["email"] = email

        user = User.objects.filter(email__iexact=email).first()
        authenticated_user = None

        if user is not None:
            authenticated_user = authenticate(
                request,
                username=user.username,
                password=password,
            )

        if authenticated_user is not None and authenticated_user.is_active:
            auth_login(request, authenticated_user)

            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            return redirect("core:home")

        context["error"] = "이메일 또는 비밀번호가 올바르지 않습니다."

    return render(request, "accounts/login.html", context)


@require_POST
@login_required
def logout_view(request):
    """현재 Django 세션을 종료합니다."""
    auth_logout(request)
    messages.success(request, "로그아웃되었습니다.")
    return redirect("core:home")


@require_http_methods(["GET", "POST"])
def signup_view(request):
    """회원가입 1단계 기본 정보를 검증하여 세션에 임시 저장합니다."""
    if request.user.is_authenticated:
        return redirect("core:home")

    form = SignupBasicForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        request.session[PENDING_SIGNUP_SESSION_KEY] = {
            "name": data["name"],
            "username": data["username"],
            "email": data["email"],
            "gender": data["gender"],
            "birth_date": data["birth_date"].isoformat(),
            "password_hash": make_password(data["password"]),
        }
        return redirect("accounts:signup_profile")

    return render(
        request,
        "accounts/signup.html",
        {"form": form},
    )


@require_http_methods(["GET", "POST"])
def signup_profile_view(request):
    """회원가입 2단계 프로필을 검증한 뒤 사용자와 로그인 세션을 생성합니다."""
    if request.user.is_authenticated:
        return redirect("core:home")

    pending = request.session.get(PENDING_SIGNUP_SESSION_KEY)
    if not pending:
        messages.error(request, "기본 정보를 먼저 입력해주세요.")
        return redirect("accounts:signup")

    form = SignupProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if User.objects.filter(username__iexact=pending["username"]).exists():
            form.add_error(None, "이미 사용 중인 아이디입니다. 다시 확인해주세요.")
        elif User.objects.filter(email__iexact=pending["email"]).exists():
            form.add_error(None, "이미 사용 중인 이메일입니다. 다시 확인해주세요.")
        else:
            try:
                with transaction.atomic():
                    user = User.objects.create(
                        name=pending["name"],
                        username=pending["username"],
                        email=pending["email"],
                        gender=pending["gender"],
                        birth_date=pending["birth_date"],
                        password=pending["password_hash"],
                        spending_type=form.cleaned_data["spending_type"],
                        value_criteria=form.cleaned_data["value_criteria"],
                        monthly_budget=form.cleaned_data["monthly_budget"],
                    )
            except IntegrityError:
                form.add_error(
                    None,
                    "회원 정보가 이미 사용 중입니다. 기본 정보를 다시 확인해주세요.",
                )
            else:
                request.session.pop(PENDING_SIGNUP_SESSION_KEY, None)
                auth_login(request, user)
                messages.success(request, "회원가입이 완료되었습니다.")
                return redirect("products:consideration_create")

    return render(
        request,
        "accounts/signup_profile.html",
        {"form": form},
    )


# ==========================
# API Views
# ==========================

class UsernameAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = UsernameAvailabilitySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]

        return Response(
            {
                "username": username,
                "available": not User.objects.filter(
                    username=username
                ).exists(),
            },
            status=status.HTTP_200_OK,
        )


class MyInfoView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
