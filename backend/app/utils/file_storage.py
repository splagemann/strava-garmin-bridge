"""
File storage utilities for saving uploaded activity files.
"""

import os
from pathlib import Path

from app.config import settings

# Default uploads directory (relative to backend root)
DEFAULT_UPLOADS_DIR = "data/uploads"


def get_uploads_directory() -> Path:
    """
    Get the uploads directory path, creating it if it doesn't exist.
    
    Returns:
        Path object pointing to the uploads directory
    """
    # Use environment variable if set, otherwise use default
    uploads_dir = os.getenv("UPLOADS_DIR", DEFAULT_UPLOADS_DIR)
    
    # If relative path, resolve relative to backend root (where this file is)
    if not os.path.isabs(uploads_dir):
        backend_root = Path(__file__).parent.parent.parent
        uploads_path = backend_root / uploads_dir
    else:
        uploads_path = Path(uploads_dir)
    
    # Create directory if it doesn't exist
    uploads_path.mkdir(parents=True, exist_ok=True)
    
    return uploads_path


def save_uploaded_file(file_bytes: bytes, sync_log_id: int, extension: str) -> str:
    """
    Save uploaded file to disk and return the relative path.
    
    Args:
        file_bytes: File content as bytes
        sync_log_id: Sync log ID (used in filename)
        extension: File extension (e.g., "fit", "gpx", "tcx")
    
    Returns:
        Relative path to the saved file (relative to backend root)
    """
    uploads_dir = get_uploads_directory()
    filename = f"sync_{sync_log_id}.{extension}"
    file_path = uploads_dir / filename
    
    # Write file
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    
    # Return relative path (for storage in DB)
    backend_root = Path(__file__).parent.parent.parent
    try:
        relative_path = file_path.relative_to(backend_root)
        return str(relative_path)
    except ValueError:
        # If not relative, return absolute path
        return str(file_path)


def get_file_path(stored_path: str) -> Path:
    """
    Get absolute Path object for a stored file path.
    
    Args:
        stored_path: Path stored in database (relative or absolute)
    
    Returns:
        Absolute Path object
    """
    path = Path(stored_path)
    if path.is_absolute():
        return path
    
    # If relative, resolve relative to backend root
    backend_root = Path(__file__).parent.parent.parent
    return backend_root / path


def delete_uploaded_file(stored_path: str) -> None:
    """
    Delete an uploaded file from disk.
    
    Args:
        stored_path: Path stored in database
    """
    try:
        file_path = get_file_path(stored_path)
        if file_path.exists():
            file_path.unlink()
    except Exception:
        # Ignore errors when deleting (file might already be gone)
        pass
