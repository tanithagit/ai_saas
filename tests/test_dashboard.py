from core.jwt_handler import decode_token

VALID_PASSWORD = "Test@1234"


def _register_and_verify_individual(client, email="dashindiv@gmail.com", password=VALID_PASSWORD):
    response = client.post("/auth/register", json={
        "full_name": "Dashboard Individual",
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
    return client.post("/auth/login", json={"email": email, "password": password})


def _register_and_verify_org(client, email="dashorg@company.com", org_name="Dashboard Org", password=VALID_PASSWORD):
    response = client.post("/auth/register", json={
        "full_name": "Dashboard Org Admin",
        "email": email,
        "password": password,
        "confirm_password": password,
        "account_type": "organization",
        "organization_name": org_name,
    })
    otp_token = response.cookies.get("otp_token")
    otp = decode_token(otp_token)["otp"]
    client.cookies.set("otp_token", otp_token)
    client.post("/auth/verify-otp", json={"otp": otp})
    client.cookies.delete("otp_token")
    return client.post("/auth/login", json={"email": email, "password": password})


class TestDashboards:
    def test_individual_dashboard_success(self, client):
        _register_and_verify_individual(client, "dashindivsuccess@gmail.com")
        response = client.get("/dashboard/individual")
        assert response.status_code == 200
        assert "Welcome" in response.json()["message"]

    def test_individual_dashboard_blocked_for_org_account(self, client):
        _register_and_verify_org(client, "dashindivblock@company.com", "Block Org")
        response = client.get("/dashboard/individual")
        assert response.status_code == 403

    def test_organization_dashboard_success(self, client):
        _register_and_verify_org(client, "dashorgsuccess@company.com", "Success Org")
        response = client.get("/dashboard/organization")
        assert response.status_code == 200
        assert response.json()["organization"]["organization_name"] == "Success Org"
        assert response.json()["stats"]["total_users"] == 1

    def test_organization_dashboard_stats_update_after_invite(self, client):
        _register_and_verify_org(client, "dashorgstats@company.com", "Stats Org")
        client.post("/organizations/users/invite", json={
            "full_name": "Stats Member",
            "email": "statsmember@company.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
        })
        response = client.get("/dashboard/organization")
        assert response.status_code == 200
        assert response.json()["stats"]["total_users"] == 2

    def test_organization_dashboard_blocked_for_individual_account(self, client):
        _register_and_verify_individual(client, "dashorgblock@gmail.com")
        response = client.get("/dashboard/organization")
        assert response.status_code == 403

    def test_dashboards_require_authentication(self, client):
        client.cookies.delete("access_token")
        response1 = client.get("/dashboard/individual")
        assert response1.status_code == 401

        response2 = client.get("/dashboard/organization")
        assert response2.status_code == 401