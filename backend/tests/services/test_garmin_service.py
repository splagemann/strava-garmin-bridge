from types import SimpleNamespace

import requests

from app.services.garmin_service import GarminService


def test_restore_pending_mfa_state_without_private_get_session(test_db):
    """Restores MFA state with the session API exposed by current garminconnect."""
    service = GarminService(test_db)

    original_session = requests.Session()
    original_session.cookies.set("GARMIN-SSO", "cookie-value")
    source = SimpleNamespace(
        client=SimpleNamespace(
            _mfa_session=original_session,
            _mfa_flow="portal",
            _mfa_method="email",
            _mfa_login_params={"clientId": "client-id"},
            _mfa_post_headers={"Origin": "https://sso.garmin.com"},
            _mfa_service_url="https://connect.garmin.com/modern",
            _portal_service_url="https://connect.garmin.com/modern",
            _sso="https://sso.garmin.com",
        )
    )

    encoded_state = service._encode_pending_mfa_state(source)
    target = SimpleNamespace(client=SimpleNamespace())

    service._restore_pending_mfa_state(target, encoded_state)

    assert target.client._mfa_session.cookies.get("GARMIN-SSO") == "cookie-value"
    assert target.client._mfa_flow == "portal"
    assert target.client._mfa_method == "email"
    assert target.client._mfa_login_params == {"clientId": "client-id"}
