from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class AuthenticationAPITests(APITestCase):
    def setUp(self):
        self.signup_url = reverse("accounts_api:signup")
        self.check_username_url = reverse("accounts_api:check-username")
        self.login_url = reverse("accounts_api:login")
        self.refresh_url = reverse("accounts_api:token-refresh")
        self.logout_url = reverse("accounts_api:logout")
        self.me_url = reverse("accounts_api:me")
        self.password = "StrongPass!2468"
        self.signup_data = {
            "username": "choezy_user",
            "email": "User@Example.com",
            "name": "최지",
            "birth_date": "2000-01-01",
            "gender": User.Gender.OTHER,
            "spending_type": [
                User.SpendingType.VALUE,
                User.SpendingType.CAUTIOUS,
            ],
            "value_criteria": [
                User.ValueCriterion.PRICE,
                User.ValueCriterion.QUALITY,
            ],
            "monthly_budget": User.MonthlyBudget.FROM_300K_TO_500K,
            "password": self.password,
            "password_confirm": self.password,
        }

    def create_user(self):
        response = self.client.post(
            self.signup_url,
            self.signup_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return User.objects.get(username=self.signup_data["username"])

    def login(self):
        return self.client.post(
            self.login_url,
            {
                "email": self.signup_data["email"],
                "password": self.password,
            },
            format="json",
        )

    def authenticate(self, access_token):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

    def test_signup_creates_user_with_profile(self):
        user = self.create_user()

        self.assertEqual(user.email, "user@example.com")
        self.assertEqual(user.name, self.signup_data["name"])
        self.assertEqual(
            user.value_criteria,
            self.signup_data["value_criteria"],
        )
        self.assertTrue(user.check_password(self.password))

    def test_signup_requires_erd_profile_fields(self):
        required_fields = [
            "birth_date",
            "gender",
            "spending_type",
            "value_criteria",
            "monthly_budget",
        ]

        for field in required_fields:
            with self.subTest(field=field):
                data = self.signup_data.copy()
                data.pop(field)
                response = self.client.post(
                    self.signup_url,
                    data,
                    format="json",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertIn(field, response.data)

    def test_signup_rejects_password_mismatch(self):
        data = {
            **self.signup_data,
            "password_confirm": "DifferentPass!2468",
        }

        response = self.client.post(
            self.signup_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_signup_rejects_password_similar_to_user_information(self):
        data = {
            **self.signup_data,
            "password": "choezy_user123!",
            "password_confirm": "choezy_user123!",
        }

        response = self.client.post(
            self.signup_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_signup_rejects_duplicate_value_criteria(self):
        data = {
            **self.signup_data,
            "value_criteria": [
                User.ValueCriterion.PRICE,
                User.ValueCriterion.PRICE,
            ],
        }

        response = self.client.post(
            self.signup_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("value_criteria", response.data)

    def test_signup_rejects_more_than_two_spending_types(self):
        data = {
            **self.signup_data,
            "spending_type": [
                User.SpendingType.VALUE,
                User.SpendingType.QUALITY,
                User.SpendingType.CAUTIOUS,
            ],
        }

        response = self.client.post(
            self.signup_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("spending_type", response.data)

    def test_signup_rejects_more_than_three_value_criteria(self):
        data = {
            **self.signup_data,
            "value_criteria": [
                User.ValueCriterion.PRICE,
                User.ValueCriterion.QUALITY,
                User.ValueCriterion.UTILIZATION,
                User.ValueCriterion.EFFICIENCY,
            ],
        }

        response = self.client.post(
            self.signup_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("value_criteria", response.data)

    def test_signup_rejects_case_insensitive_duplicate_email(self):
        self.create_user()
        data = {
            **self.signup_data,
            "username": "another_user",
            "email": "USER@example.com",
        }

        response = self.client.post(
            self.signup_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_returns_access_and_refresh_tokens(self):
        self.create_user()

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_accepts_email_case_insensitively(self):
        self.create_user()

        response = self.client.post(
            self.login_url,
            {
                "email": "USER@EXAMPLE.COM",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_rejects_invalid_password(self):
        self.create_user()

        response = self.client.post(
            self.login_url,
            {
                "email": self.signup_data["email"],
                "password": "WrongPass!2468",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_username_availability(self):
        available_response = self.client.get(
            self.check_username_url,
            {"username": self.signup_data["username"]},
        )
        self.assertEqual(available_response.status_code, status.HTTP_200_OK)
        self.assertTrue(available_response.data["available"])

        self.create_user()
        unavailable_response = self.client.get(
            self.check_username_url,
            {"username": self.signup_data["username"]},
        )
        self.assertEqual(
            unavailable_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(unavailable_response.data["available"])

    def test_authenticated_user_can_retrieve_my_info(self):
        self.create_user()
        login_response = self.login()
        self.authenticate(login_response.data["access"])

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "choezy_user")
        self.assertNotIn("password", response.data)

    def test_refresh_rotates_token_and_blacklists_old_token(self):
        self.create_user()
        login_response = self.login()
        old_refresh = login_response.data["refresh"]

        response = self.client.post(
            self.refresh_url,
            {"refresh": old_refresh},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        reused_response = self.client.post(
            self.refresh_url,
            {"refresh": old_refresh},
            format="json",
        )
        self.assertEqual(
            reused_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_logout_blacklists_refresh_token(self):
        self.create_user()
        login_response = self.login()
        refresh_token = login_response.data["refresh"]
        self.authenticate(login_response.data["access"])

        response = self.client.post(
            self.logout_url,
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_logout_rejects_another_users_refresh_token(self):
        self.create_user()
        login_response = self.login()
        self.authenticate(login_response.data["access"])
        another_user = User.objects.create_user(
            username="another_user",
            email="another@example.com",
            name="다른 사용자",
            password="AnotherPass!2468",
        )
        another_refresh = str(RefreshToken.for_user(another_user))

        response = self.client.post(
            self.logout_url,
            {"refresh": another_refresh},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": another_refresh},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
