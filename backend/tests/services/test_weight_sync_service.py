import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.services.weight_sync_service import WeightSyncService
from app.models.sync_log import SyncLog

def test_sync_weight_success(test_db, test_user_full, test_user_with_withings):
    """Test syncing multiple weights successfully."""
    # Setup user with both auths
    test_user_with_withings.garmin_auth = test_user_full.garmin_auth
    test_db.commit()
    
    service = WeightSyncService(test_db)
    
    # Mock services
    mock_measurements = [
        {
            "weight": 70.5,
            "timestamp": 1672531200,  # 2023-01-01
            "date": datetime(2023, 1, 1)
        },
        {
            "weight": 71.0,
            "timestamp": 1672617600,  # 2023-01-02
            "date": datetime(2023, 1, 2)
        }
    ]
    
    service.withings_service.get_recent_weights = MagicMock(return_value=mock_measurements)
    service.garmin_service.connect = MagicMock(return_value=True)
    service.garmin_service.upload_weight = MagicMock(return_value=True)
    
    # Run sync
    result = service.sync_weight(test_user_with_withings)
    
    assert result is True
    assert service.garmin_service.upload_weight.call_count == 2
    
    # Verify logs created
    logs = test_db.query(SyncLog).filter(
        SyncLog.user_id == test_user_with_withings.id,
        SyncLog.activity_type == "weight"
    ).all()
    assert len(logs) == 2
    assert logs[0].status == "success"
    assert logs[1].status == "success"

def test_sync_weight_skip_existing(test_db, test_user_full, test_user_with_withings):
    """Test skipping already synced weights."""
    test_user_with_withings.garmin_auth = test_user_full.garmin_auth
    test_db.commit()
    
    service = WeightSyncService(test_db)
    
    # Create existing log for first measurement
    ts1 = 1672531200
    log = SyncLog(
        user_id=test_user_with_withings.id,
        sync_direction="withings_to_garmin",
        status="success",
        source_activity_id=str(ts1),
        strava_activity_id=f"withings_{ts1}",
        activity_type="weight"
    )
    test_db.add(log)
    test_db.commit()
    
    mock_measurements = [
        {
            "weight": 70.5,
            "timestamp": ts1,
            "date": datetime.fromtimestamp(ts1)
        },
        {
            "weight": 71.0,
            "timestamp": 1672617600,
            "date": datetime.fromtimestamp(1672617600)
        }
    ]
    
    service.withings_service.get_recent_weights = MagicMock(return_value=mock_measurements)
    service.garmin_service.connect = MagicMock(return_value=True)
    service.garmin_service.upload_weight = MagicMock(return_value=True)
    
    result = service.sync_weight(test_user_with_withings)
    
    assert result is True
    # Should only upload the second one
    assert service.garmin_service.upload_weight.call_count == 1
    assert service.garmin_service.upload_weight.call_args[0][0] == 71.0

def test_sync_weight_partial_failure(test_db, test_user_full, test_user_with_withings):
    """Test handling partial failures."""
    test_user_with_withings.garmin_auth = test_user_full.garmin_auth
    test_db.commit()
    
    service = WeightSyncService(test_db)
    
    mock_measurements = [
        {
            "weight": 70.5,
            "timestamp": 1672531200,
            "date": datetime(2023, 1, 1)
        },
        {
            "weight": 71.0,
            "timestamp": 1672617600,
            "date": datetime(2023, 1, 2)
        }
    ]
    
    service.withings_service.get_recent_weights = MagicMock(return_value=mock_measurements)
    service.garmin_service.connect = MagicMock(return_value=True)
    # Fail first, succeed second
    service.garmin_service.upload_weight = MagicMock(side_effect=[False, True])
    
    result = service.sync_weight(test_user_with_withings)
    
    assert result is True  # Overall process considered success if it completed
    
    logs = test_db.query(SyncLog).filter(
        SyncLog.user_id == test_user_with_withings.id,
        SyncLog.activity_type == "weight"
    ).all()
    
    assert len(logs) == 2
    # Verify statuses (order depends on list order which is preserved)
    statuses = [l.status for l in logs]
    assert "failed" in statuses
    assert "success" in statuses

def test_sync_weight_no_auth(test_db, test_user):
    """Test skipping when not authenticated."""
    service = WeightSyncService(test_db)
    result = service.sync_weight(test_user)
    assert result is False
