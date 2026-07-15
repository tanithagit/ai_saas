VALID_PASSWORD = "Test@1234"


def _register_and_verify_individual(client, email="profiletest@gmail.com", password=VALID_PASSWORD):
    from core.jwt_handler import decode_token

    response = client.post("/auth/register", json={
        "full_name": "Profile Test User",
        "email": email,
        "password": password,
        "confirm_password": password,
        "account_type": "individual",
        "organization_name": None,
    })
    otp_token = response.cookies.get("otp_token")
    otp = decode_token(otp_token)["otp"]
    client.cookies.set("otp_token", otp_token)
    client.post("/auth/verify-otp", json={"otp": otp})
    client.cookies.delete("otp_token")

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    return login_resp


class TestUserProfile:
    def test_get_profile_requires_auth(self, client):
        client.cookies.delete("access_token")
        response = client.get("/users/profile")
        assert response.status_code == 401

    def test_get_profile_success(self, client):
        self._register_and_verify_individual(client, "getprofile@gmail.com")
        response = client.get("/users/profile")
        assert response.status_code == 200
        assert response.json()["email"] == "getprofile@gmail.com"
        assert response.json()["account_type"] == "individual"

    _register_and_verify_individual = staticmethod(_register_and_verify_individual)

    def test_update_profile_success(self, client):
        self._register_and_verify_individual(client, "updateprofile@gmail.com")
        response = client.put("/users/profile", json={"full_name": "Updated Name"})
        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"

    def test_change_password_success_and_relogin(self, client):
        email = "changepass@gmail.com"
        self._register_and_verify_individual(client, email, VALID_PASSWORD)

        response = client.post("/users/change-password", json={
            "current_password": VALID_PASSWORD,
            "new_password": "NewSecure@123",
            "confirm_new_password": "NewSecure@123",
        })
        assert response.status_code == 200

        client.cookies.delete("access_token")
        client.cookies.delete("refresh_token")

        old_login = client.post("/auth/login", json={"email": email, "password": VALID_PASSWORD})
        assert old_login.status_code == 401

        new_login = client.post("/auth/login", json={"email": email, "password": "NewSecure@123"})
        assert new_login.status_code == 200

    def test_change_password_wrong_current_password_fails(self, client):
        self._register_and_verify_individual(client, "wrongcurrent@gmail.com")
        response = client.post("/users/change-password", json={
            "current_password": "WrongPass@123",
            "new_password": "NewSecure@123",
            "confirm_new_password": "NewSecure@123",
        })
        assert response.status_code == 400