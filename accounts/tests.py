from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status


User = get_user_model()


def create_user(**overrides):
    data = {
        "username": "session_user",
        "email": "session@example.com",
        "name": "세션 사용자",
        "birth_date": "2000-01-01",
        "gender": User.Gender.OTHER,
        "spending_type": [User.SpendingType.VALUE],
        "value_criteria": [User.ValueCriterion.PRICE],
        "monthly_budget": User.MonthlyBudget.FROM_300K_TO_500K,
        "password": "StrongPass!2468",
    }
    data.update(overrides)
    return User.objects.create_user(**data)


class SessionAuthenticationPageTests(TestCase):
    def setUp(self):
        self.password = "StrongPass!2468"
        self.user = create_user(password=self.password)
        self.login_url = reverse("accounts:login")
        self.logout_url = reverse("accounts:logout")

    def test_login_creates_django_session(self):
        response = self.client.post(
            self.login_url,
            {
                "email": "SESSION@EXAMPLE.COM",
                "password": self.password,
            },
        )

        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            self.user.pk,
        )

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            self.login_url,
            {
                "email": self.user.email,
                "password": "WrongPass!2468",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["error"],
            "이메일 또는 비밀번호가 올바르지 않습니다.",
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_clears_django_session(self):
        self.client.force_login(self.user)

        response = self.client.post(self.logout_url)

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_does_not_allow_get(self):
        self.client.force_login(self.user)

        response = self.client.get(self.logout_url)

        self.assertEqual(response.status_code, 405)


class SignupPageTests(TestCase):
    def setUp(self):
        self.signup_url = reverse("accounts:signup")
        self.profile_url = reverse("accounts:signup_profile")
        self.password = "StrongPass!2468"
        self.basic_data = {
            "username": "choezy_user",
            "email": "User@Example.com",
            "name": "최지",
            "birth_date": "2000-01-01",
            "gender": User.Gender.MALE,
            "password": self.password,
            "password_confirm": self.password,
        }
        self.profile_data = {
            "spending_type": [
                User.SpendingType.VALUE,
                User.SpendingType.CAUTIOUS,
            ],
            "value_criteria": [
                User.ValueCriterion.PRICE,
                User.ValueCriterion.QUALITY,
            ],
            "monthly_budget": User.MonthlyBudget.FROM_300K_TO_500K,
        }

    def submit_basic_data(self):
        return self.client.post(self.signup_url, self.basic_data)

    def test_two_step_signup_creates_user_and_session(self):
        first_response = self.submit_basic_data()
        self.assertRedirects(first_response, self.profile_url)
        self.assertFalse(User.objects.filter(username="choezy_user").exists())

        response = self.client.post(self.profile_url, self.profile_data)

        user = User.objects.get(username="choezy_user")
        self.assertRedirects(
            response,
            reverse("products:consideration_create"),
        )
        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.spending_type, self.profile_data["spending_type"])
        self.assertEqual(
            user.value_criteria,
            self.profile_data["value_criteria"],
        )
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            user.pk,
        )

        self.assertNotIn("pending_signup", self.client.session)

    def test_basic_step_requires_all_fields(self):
        required_fields = ["name", "username", "email", "birth_date", "gender"]

        for field in required_fields:
            with self.subTest(field=field):
                data = self.basic_data.copy()
                data.pop(field)
                response = self.client.post(self.signup_url, data)

                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)

    def test_signup_rejects_password_mismatch(self):
        data = {
            **self.basic_data,
            "password_confirm": "DifferentPass!2468",
        }

        response = self.client.post(self.signup_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("password_confirm", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="choezy_user").exists())

    def test_signup_rejects_case_insensitive_duplicate_username_and_email(self):
        create_user(
            username="CHOEZY_USER",
            email="USER@example.com",
        )

        response = self.client.post(self.signup_url, self.basic_data)
        errors = response.context["form"].errors

        self.assertIn("username", errors)
        self.assertIn("email", errors)

    def test_signup_rejects_more_than_two_spending_types(self):
        self.submit_basic_data()
        data = {
            **self.profile_data,
            "spending_type": [
                User.SpendingType.VALUE,
                User.SpendingType.QUALITY,
                User.SpendingType.CAUTIOUS,
            ],
        }

        response = self.client.post(self.profile_url, data)

        self.assertIn("spending_type", response.context["form"].errors)

    def test_signup_rejects_more_than_three_value_criteria(self):
        self.submit_basic_data()
        data = {
            **self.profile_data,
            "value_criteria": [
                User.ValueCriterion.PRICE,
                User.ValueCriterion.QUALITY,
                User.ValueCriterion.UTILIZATION,
                User.ValueCriterion.EFFICIENCY,
            ],
        }

        response = self.client.post(self.profile_url, data)

        self.assertIn("value_criteria", response.context["form"].errors)

    def test_profile_step_requires_basic_step(self):
        response = self.client.get(self.profile_url)

        self.assertRedirects(response, self.signup_url)

    def test_profile_step_rechecks_duplicate_username(self):
        self.submit_basic_data()
        create_user(username="CHOEZY_USER", email="other@example.com")

        response = self.client.post(self.profile_url, self.profile_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertEqual(User.objects.filter(username__iexact="choezy_user").count(), 1)


class AccountAPITests(TestCase):
    def setUp(self):
        self.check_username_url = reverse("accounts_api:check-username")
        self.me_url = reverse("accounts_api:me")

    def test_username_availability(self):
        response = self.client.get(
            self.check_username_url,
            {"username": "available_user"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["available"])

        create_user(username="available_user")
        response = self.client.get(
            self.check_username_url,
            {"username": "available_user"},
        )
        self.assertFalse(response.json()["available"])

    def test_session_user_can_retrieve_my_info(self):
        user = create_user()
        self.client.force_login(user)

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["username"], user.username)
        self.assertNotIn("password", response.json())

    def test_anonymous_user_cannot_retrieve_my_info(self):
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
