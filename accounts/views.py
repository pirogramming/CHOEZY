from django.shortcuts import render
from django.contrib.auth import get_user_model

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    LoginSerializer,
    SignupSerializer,
    UserSerializer,
    UsernameAvailabilitySerializer,
)

User = get_user_model()


# ==========================
# Template Views (Frontend)
# ==========================

def login_view(request):
    return render(request, "accounts/login.html")


def signup_view(request):
    return render(request, "accounts/signup.html")


def signup_profile_view(request):
    return render(request, "accounts/signup_profile.html")


# ==========================
# API Views
# ==========================

class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


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


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {
                    "detail": "refresh token이 필요합니다.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)

            if str(token["user_id"]) != str(request.user.pk):
                return Response(
                    {
                        "detail": "현재 사용자의 refresh token이 아닙니다.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token.blacklist()

        except TokenError:
            return Response(
                {
                    "detail": "유효하지 않은 refresh token입니다.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": "로그아웃되었습니다.",
            },
            status=status.HTTP_200_OK,
        )


class MyInfoView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user