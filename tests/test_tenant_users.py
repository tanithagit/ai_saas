from core.jwt_handler import decode_token

VALID_PASSWORD = "Test@1234"


def _register_and_verify_org(client, email, org_name, password=VALID_PASSWORD):
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


def _invite_user(client, email="member1@company.com"):
    return client.post("/organizations/users/invite", json={
        "full_name": "Invited Member",
        "email": email,
        "password": VALID_PASSWORD,
        "confirm_password": VALID_PASSWORD,
    })


class TestTenantUserManagement:
    def test_invite_user_success(self, client):
        _register_and_verify_org(client, "inviteadmin1@company.com", "Invite Test Org")
        response = _invite_user(client, "invitedmember1@company.com")
        assert response.status_code == 200
        assert response.json()["role"] == "member"
        assert response.json()["is_active"] is True

    def test_invite_duplicate_email_fails(self, client):
        _register_and_verify_org(client, "inviteadmin2@company.com", "Invite Test Org 2")
        _invite_user(client, "dupmember@company.com")
        response = _invite_user(client, "dupmember@company.com")
        assert response.status_code == 400

    def test_list_organization_users(self, client):
        _register_and_verify_org(client, "listadmin@company.com", "List Test Org")
        _invite_user(client, "listmember@company.com")
        response = client.get("/organizations/users")
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()]
        assert "listadmin@company.com" in emails
        assert "listmember@company.com" in emails

    def test_get_specific_user(self, client):
        _register_and_verify_org(client, "getadmin@company.com", "Get Test Org")
        invite_resp = _invite_user(client, "getmember@company.com")
        user_id = invite_resp.json()["id"]

        response = client.get(f"/organizations/users/{user_id}")
        assert response.status_code == 200
        assert response.json()["email"] == "getmember@company.com"

    def test_get_nonexistent_user_returns_404(self, client):
        _register_and_verify_org(client, "get404admin@company.com", "Get 404 Org")
        response = client.get("/organizations/users/999999")
        assert response.status_code == 404

    def test_update_user_details(self, client):
        _register_and_verify_org(client, "updateadmin@company.com", "Update Test Org")
        invite_resp = _invite_user(client, "updatemember@company.com")
        user_id = invite_resp.json()["id"]

        response = client.put(f"/organizations/users/{user_id}", json={
            "full_name": "Updated Member Name",
            "email": "updatedmember@company.com",
        })
        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Member Name"

    def test_deactivate_and_reactivate_user(self, client):
        _register_and_verify_org(client, "statusadmin@company.com", "Status Test Org")
        invite_resp = _invite_user(client, "statusmember@company.com")
        user_id = invite_resp.json()["id"]

        deactivate_resp = client.patch(f"/organizations/users/{user_id}/status", json={"is_active": False})
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["is_active"] is False

        reactivate_resp = client.patch(f"/organizations/users/{user_id}/status", json={"is_active": True})
        assert reactivate_resp.status_code == 200
        assert reactivate_resp.json()["is_active"] is True

    def test_admin_cannot_deactivate_self(self, client):
        login_resp = _register_and_verify_org(client, "selfstatusadmin@company.com", "Self Status Org")
        admin_id_response = client.get("/users/profile")
        admin_id = admin_id_response.json()["id"]

        response = client.patch(f"/organizations/users/{admin_id}/status", json={"is_active": False})
        assert response.status_code == 400

    def test_delete_user_soft_delete(self, client):
        _register_and_verify_org(client, "deleteadmin@company.com", "Delete Test Org")
        invite_resp = _invite_user(client, "deletemember@company.com")
        user_id = invite_resp.json()["id"]

        delete_resp = client.delete(f"/organizations/users/{user_id}")
        assert delete_resp.status_code == 200

        list_resp = client.get("/organizations/users")
        emails = [u["email"] for u in list_resp.json()]
        assert "deletemember@company.com" not in emails

        get_resp = client.get(f"/organizations/users/{user_id}")
        assert get_resp.status_code == 404

    def test_admin_cannot_delete_self(self, client):
        _register_and_verify_org(client, "selfdeleteadmin@company.com", "Self Delete Org")
        admin_id_response = client.get("/users/profile")
        admin_id = admin_id_response.json()["id"]

        response = client.delete(f"/organizations/users/{admin_id}")
        assert response.status_code == 400

    def test_tenant_isolation_cannot_access_other_org_user(self, client):
        _register_and_verify_org(client, "tenantAadmin@companyA.com", "Tenant A")
        invite_resp = _invite_user(client, "tenantAmember@companyA.com")
        user_id_in_tenant_a = invite_resp.json()["id"]

        client.cookies.delete("access_token")
        client.cookies.delete("refresh_token")

        _register_and_verify_org(client, "tenantBadmin@companyB.com", "Tenant B")

        response = client.get(f"/organizations/users/{user_id_in_tenant_a}")
        assert response.status_code == 404