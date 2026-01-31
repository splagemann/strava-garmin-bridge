"""
FIT file utilities for GPS checks (e.g. before Strava upload).
"""

from pathlib import Path

from fitparse import FitFile

NO_GPS_MESSAGE = (
    "This activity has no GPS data. Strava requires GPS for uploads; "
    "indoor or manual activities cannot be synced to Strava."
)


def fit_file_has_gps(file_path: str) -> bool:
    """
    Check if a FIT file contains at least one record with GPS (position_lat/long).

    Returns False if no GPS data; on parse error returns True so Strava can validate.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return True  # Let caller/Strava handle missing file
    try:
        fit = FitFile(str(path))
        for record in fit.get_messages("record"):
            for field in record:
                if field.name in ("position_lat", "position_long") and field.value is not None:
                    return True
        return False
    except Exception:
        return True  # Parse error: allow upload, let Strava validate
