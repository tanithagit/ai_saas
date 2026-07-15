import re

from datetime import timedelta
from core.jwt_handler import decode_token, create_otp_token



VALID_PASSWORD = "Test@1234"


def extract_cookie(response, name):
    return response.cookies.get(name)


class TestRegistration:
    def test_individual_registration_success(self, client):
        response = client.post("/auth/register", json={
            "full_name": "John Doe",
            "email": "john.individual@gmail.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        assert response.status_code == 200
        assert response.json()["email"] == "john.individual@gmail.com"
        assert extract_cookie(response, "otp_token") is not None

    def test_organization_registration_success(self, client):
        response = client.post("/auth/register", json={
            "full_name": "Jane Admin",
            "email": "jane@acmecorp.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "organization",
            "organization_name": "Acme Corp",
        })
        assert response.status_code == 200
        assert extract_cookie(response, "otp_token") is not None

    def test_organization_registration_missing_org_name_fails(self, client):
        response = client.post("/auth/register", json={
            "full_name": "Jane Admin",
            "email": "jane2@acmecorp.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "organization",
            "organization_name": None,
        })
        assert response.status_code == 422

    def test_organization_registration_free_email_rejected(self, client):
        response = client.post("/auth/register", json={
            "full_name": "Jane Admin",
            "email": "jane@gmail.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "organization",
            "organization_name": "Acme Corp",
        })
        assert response.status_code == 422

    def test_password_mismatch_fails(self, client):
        response = client.post("/auth/register", json={
            "full_name": "John Doe",
            "email": "mismatch@example.com",
            "password": VALID_PASSWORD,
            "confirm_password": "Different@123",
            "account_type": "individual",
            "organization_name": None,
        })
        assert response.status_code == 422

    def test_weak_password_fails(self, client):
        response = client.post("/auth/register", json={
            "full_name": "John Doe",
            "email": "weakpass@example.com",
            "password": "weak",
            "confirm_password": "weak",
            "account_type": "individual",
            "organization_name": None,
        })
        assert response.status_code == 422

    def test_duplicate_email_registration_fails(self, client, db_session):
        from core.security import hash_password
        from models.user import User, AccountType

        existing = User(
            full_name="Existing User",
            email="existing@gmail.com",
            password_hash=hash_password(VALID_PASSWORD),
            account_type=AccountType.individual,
            is_active=True,
        )
        db_session.add(existing)
        db_session.commit()

        response = client.post("/auth/register", json={
            "full_name": "Someone Else",
            "email": "existing@gmail.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        assert response.status_code == 400



class TestOtpVerification:
    def _register_and_get_otp(self, client, email="otp.test@example.com"):
        response = client.post("/auth/register", json={
            "full_name": "OTP Test",
            "email": email,
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        otp_token = extract_cookie(response, "otp_token")
        token_data = decode_token(otp_token)
        return response, otp_token, token_data["otp"]

    def test_valid_otp_activates_account(self, client):
        _, otp_token, otp = self._register_and_get_otp(client, "otpvalid@gmail.com")
        client.cookies.set("otp_token", otp_token)

        response = client.post("/auth/verify-otp", json={"otp": otp})
        assert response.status_code == 200
        assert response.json()["message"] == "Account verified and activated successfully."

    def test_invalid_otp_rejected(self, client):
        _, otp_token, otp = self._register_and_get_otp(client, "otpinvalid@gmail.com")
        client.cookies.set("otp_token", otp_token)

        response = client.post("/auth/verify-otp", json={"otp": "000000"})
        assert response.status_code == 400
        assert "Invalid OTP" in response.json()["detail"]

    def test_expired_otp_rejected(self, client):
        # Manually create an already-expired OTP token
        expired_token = create_otp_token(
            {"sub": "otpexpired@example.com", "full_name": "Expired", "password_hash": "x",
             "account_type": "individual", "organization_name": None, "otp": "123456"},
            purpose="registration",
        )
        # Force expiry by decoding and re-encoding with past exp (simulate via jose directly)
        from jose import jwt
        from core.config import settings
        payload = jwt.decode(expired_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        import time
        payload["exp"] = int(time.time()) - 10  # 10 seconds in the past
        bad_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        client.cookies.set("otp_token", bad_token)
        response = client.post("/auth/verify-otp", json={"otp": "123456"})
        assert response.status_code == 400

    def test_max_retry_exceeded(self, client):
        _, otp_token, otp = self._register_and_get_otp(client, "otpmaxretry@gmail.com")
        client.cookies.set("otp_token", otp_token)

        # Explicitly carry forward the updated otp_token cookie after each attempt
        for _ in range(3):
            resp = client.post("/auth/verify-otp", json={"otp": "000000"})
            updated_cookie = extract_cookie(resp, "otp_token")
            if updated_cookie:
                client.cookies.set("otp_token", updated_cookie)

        # 4th attempt should now be blocked
        response = client.post("/auth/verify-otp", json={"otp": "000000"})
        assert response.status_code == 429
        
    def test_resend_otp_generates_new_otp(self, client):
        _, otp_token, original_otp = self._register_and_get_otp(client, "otpresend@gmail.com")
        client.cookies.set("otp_token", otp_token)

        resend_response = client.post("/auth/resend-otp", json={"purpose": "registration"})
        assert resend_response.status_code == 200

        new_otp_token = extract_cookie(resend_response, "otp_token")
        new_otp = decode_token(new_otp_token)["otp"]
        assert new_otp != original_otp

        client.cookies.set("otp_token", new_otp_token)
        verify_response = client.post("/auth/verify-otp", json={"otp": new_otp})
        assert verify_response.status_code == 200


class TestLogin:
    def _register_and_activate(self, client, email="login.test@example.com"):
        response = client.post("/auth/register", json={
            "full_name": "Login Test",
            "email": email,
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        otp_token = extract_cookie(response, "otp_token")
        otp = decode_token(otp_token)["otp"]
        client.cookies.set("otp_token", otp_token)
        client.post("/auth/verify-otp", json={"otp": otp})
        client.cookies.delete("otp_token")

    def test_valid_login_success(self, client):
        self._register_and_activate(client, "loginvalid@gmail.com")
        response = client.post("/auth/login", json={"email": "loginvalid@gmail.com", "password": VALID_PASSWORD})
        assert response.status_code == 200
        assert extract_cookie(response, "access_token") is not None
        assert extract_cookie(response, "refresh_token") is not None

    def test_invalid_password_fails(self, client):
        self._register_and_activate(client, "loginwrongpass@gmail.com")
        response = client.post("/auth/login", json={"email": "loginwrongpass@gmail.com", "password": "WrongPass@1"})
        assert response.status_code == 401

    def test_nonexistent_email_fails(self, client):
        response = client.post("/auth/login", json={"email": "doesnotexist@example.com", "password": VALID_PASSWORD})
        assert response.status_code == 401

    def test_unverified_account_login_fails(self, client):
        client.post("/auth/register", json={
            "full_name": "Unverified User",
            "email": "unverified@example.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        # Note: never verifying OTP here
        response = client.post("/auth/login", json={"email": "unverified@example.com", "password": VALID_PASSWORD})
        assert response.status_code == 401


class TestLogout:
    def test_logout_requires_authentication(self, client):
        client.cookies.delete("access_token")
        response = client.post("/auth/logout")
        assert response.status_code == 401

    def test_logout_success_then_fails_second_time(self, client):
        # Register + activate + login
        client.post("/auth/register", json={
            "full_name": "Logout Test",
            "email": "logouttest@example.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        otp_token = extract_cookie(
            client.post("/auth/resend-otp", json={"purpose": "registration"}), "otp_token"
        )
        # simpler: just decode from register response directly instead
        register_resp = client.post("/auth/register", json={
            "full_name": "Logout Test2",
            "email": "logouttest2@gmail.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        otp_token = extract_cookie(register_resp, "otp_token")
        otp = decode_token(otp_token)["otp"]
        client.cookies.set("otp_token", otp_token)
        client.post("/auth/verify-otp", json={"otp": otp})
        client.cookies.delete("otp_token")

        login_resp = client.post("/auth/login", json={"email": "logouttest2@gmail.com", "password": VALID_PASSWORD})
        client.cookies.set("access_token", extract_cookie(login_resp, "access_token"))

        first_logout = client.post("/auth/logout")
        assert first_logout.status_code == 200

        client.cookies.delete("access_token")
        second_logout = client.post("/auth/logout")
        assert second_logout.status_code == 401


class TestForgotPassword:
    def _register_and_activate(self, client, email):
        response = client.post("/auth/register", json={
            "full_name": "Forgot Test",
            "email": email,
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
            "account_type": "individual",
            "organization_name": None,
        })
        otp_token = extract_cookie(response, "otp_token")
        otp = decode_token(otp_token)["otp"]
        client.cookies.set("otp_token", otp_token)
        client.post("/auth/verify-otp", json={"otp": otp})
        client.cookies.delete("otp_token")

    def test_full_forgot_password_flow(self, client):
        self._register_and_activate(client, "forgotflow@gmail.com")

        forgot_resp = client.post("/auth/forgot-password", json={"email": "forgotflow@gmail.com"})
        assert forgot_resp.status_code == 200
        forgot_otp_token = extract_cookie(forgot_resp, "forgot_otp_token")
        assert forgot_otp_token is not None
        otp = decode_token(forgot_otp_token)["otp"]

        client.cookies.set("forgot_otp_token", forgot_otp_token)
        verify_resp = client.post("/auth/verify-forgot-otp", json={"otp": otp})
        assert verify_resp.status_code == 200
        reset_token = extract_cookie(verify_resp, "reset_token")
        assert reset_token is not None

        client.cookies.set("reset_token", reset_token)
        reset_resp = client.post("/auth/reset-password", json={
            "new_password": "NewPass@123",
            "confirm_new_password": "NewPass@123",
        })
        assert reset_resp.status_code == 200

        client.cookies.delete("reset_token")

        # New password should work
        login_new = client.post("/auth/login", json={"email": "forgotflow@gmail.com", "password": "NewPass@123"})
        assert login_new.status_code == 200

        # Old password should fail
        login_old = client.post("/auth/login", json={"email": "forgotflow@gmail.com", "password": VALID_PASSWORD})
        assert login_old.status_code == 401

    def test_forgot_password_nonexistent_email_generic_response(self, client):
        response = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
        assert response.status_code == 200
        assert "registered" in response.json()["message"].lower()