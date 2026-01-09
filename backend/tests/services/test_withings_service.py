import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from app.services.withings_service import WithingsService
from app.models.user import User

def test_get_recent_weights_success(test_db, test_user_with_withings):
    """Test fetching recent weights successfully."""
    service = WithingsService(test_db)
    
    # Mock response data
    mock_response_data = {
        "status": 0,
        "body": {
            "measuregrps": [
                {
                    "date": 1672531200,  # 2023-01-01
                    "measures": [{"type": 1, "value": 70500, "unit": -3}]  # 70.5 kg
                },
                {
                    "date": 1672617600,  # 2023-01-02
                    "measures": [{"type": 1, "value": 71000, "unit": -3}]  # 71.0 kg
                }
            ]
        }
    }

    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response_data
        
        weights = service.get_recent_weights(test_user_with_withings)
        
        assert len(weights) == 2
        # Verify sorting (oldest first)
        assert weights[0]["weight"] == 70.5
        assert weights[0]["timestamp"] == 1672531200
        assert weights[1]["weight"] == 71.0
        assert weights[1]["timestamp"] == 1672617600

def test_get_recent_weights_no_auth(test_db, test_user):
    """Test fetching weights without authentication."""
    service = WithingsService(test_db)
    weights = service.get_recent_weights(test_user)
    assert weights == []

def test_get_recent_weights_api_error(test_db, test_user_with_withings):
    """Test API error handling."""
    service = WithingsService(test_db)
    
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": 1, "error": "Some error"}
        
        weights = service.get_recent_weights(test_user_with_withings)
        assert weights == []

def test_get_recent_weights_network_error(test_db, test_user_with_withings):
    """Test network error handling."""
    service = WithingsService(test_db)
    
    with patch("httpx.post", side_effect=Exception("Network error")):
        weights = service.get_recent_weights(test_user_with_withings)
        assert weights == []

def test_token_refresh(test_db, test_user_with_withings):
    """Test token refresh when expired."""
    service = WithingsService(test_db)
    
    # Expire the token
    test_user_with_withings.withings_auth.expires_at = datetime.utcnow() - timedelta(hours=1)
    test_db.commit()
    
    mock_refresh_response = {
        "status": 0,
        "body": {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 10800
        }
    }
    
    mock_measures_response = {
        "status": 0,
        "body": {"measuregrps": []}
    }

    with patch("httpx.post") as mock_post:
        # First call is refresh, second is get measurements
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: mock_refresh_response),
            MagicMock(status_code=200, json=lambda: mock_measures_response)
        ]
        
        service.get_recent_weights(test_user_with_withings)
        
        # Verify token updated
        auth = test_user_with_withings.withings_auth
        assert auth.access_token == "new_access_token"
        assert auth.refresh_token == "new_refresh_token"
        assert auth.expires_at > datetime.utcnow()
