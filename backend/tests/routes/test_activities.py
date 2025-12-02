
from unittest.mock import patch, ANY
from app.middleware.auth import get_current_user
from app.main import app

def test_get_strava_activities_no_after_param(client, test_user_with_strava):
    """
    Test that get_strava_activities calls the service without the 'after' parameter,
    ensuring we fetch the most recent activities.
    """
    # Override get_current_user
    app.dependency_overrides[get_current_user] = lambda: test_user_with_strava
    
    with patch("app.services.strava_service.StravaService.list_recent_activities") as mock_list:
        mock_list.return_value = []
        
        response = client.get("/api/v1/activities/strava?limit=10")
        
        assert response.status_code == 200
        
        # Verify call args
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        
        # The 'after' parameter should NOT be present in the kwargs of the call
        # because we want to use the default behavior (fetch recent)
        # OR if it is present (e.g. default), it should be None.
        # Since we removed it from the call, it shouldn't be in kwargs.
        assert "after" not in kwargs
        assert kwargs.get("limit") == 10

def test_get_strava_activities_success(client, test_user_with_strava):
    """Test successful retrieval of Strava activities."""
    app.dependency_overrides[get_current_user] = lambda: test_user_with_strava
    
    # Mock activity object
    class MockActivity:
        def __init__(self):
            self.id = 12345
            self.name = "Test Run"
            self.type = "Run"
            self.start_date = "2023-01-01T10:00:00Z"
            self.distance = 5000.0
            self.moving_time = 1800
            self.elapsed_time = 1800
            self.total_elevation_gain = 100.0
            
    mock_activity = MockActivity()
    
    with patch("app.services.strava_service.StravaService.list_recent_activities") as mock_list:
        mock_list.return_value = [mock_activity]
        
        response = client.get("/api/v1/activities/strava")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "12345"
        assert data[0]["name"] == "Test Run"
