from core.jwt_handler import decode_token

VALID_PASSWORD = "Test@1234"


def _register_and_verify_org(client, email="orgtest@company.com", org_name="Test Org", password=VALID_PASSWORD):
    response = client.post("/auth/register", json={
        "full_name": "Org Admin",
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


def _register_and_verify_individual(client, email="indivtest@gmail.com", password=VALID_PASSWORD):
    response = client.post("/auth/register", json={
        "full_name": "Individual Test",
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


class TestOrganizationProfile:
    def test_get_organization_profile_success(self, client):
        _register_and_verify_org(client, "getorgprofile@company.com", "Get Org Profile Test")
        response = client.get("/organizations/profile")
        assert response.status_code == 200
        assert response.json()["organization_name"] == "Get Org Profile Test"

    def test_update_organization_profile_as_admin_success(self, client):
        _register_and_verify_org(client, "updateorgprofile@company.com", "Old Name")
        response = client.put("/organizations/profile", json={"organization_name": "New Name Pvt Ltd"})
        assert response.status_code == 200
        assert response.json()["organization_name"] == "New Name Pvt Ltd"

    def test_individual_account_cannot_access_org_profile(self, client):
        _register_and_verify_individual(client, "noaccess@gmail.com")
        response = client.get("/organizations/profile")
        assert response.status_code == 403

    def test_individual_account_cannot_update_org_profile(self, client):
        _register_and_verify_individual(client, "noaccessupdate@gmail.com")
        response = client.put("/organizations/profile", json={"organization_name": "Hacked Name"})
        assert response.status_code == 403