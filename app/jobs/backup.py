"""
Database backup job.
"""

import os
import subprocess
import structlog
from datetime import datetime
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pytz

from app.config import settings

logger = structlog.get_logger(__name__)

TZ = pytz.timezone(settings.calendar_timezone)

# Backup directory
BACKUP_DIR = Path("/app/backups")

# Google Drive scopes
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """Get Google Drive service."""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_credentials_path,
            scopes=DRIVE_SCOPES,
        )
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        logger.error("Failed to initialize Google Drive service", error=str(e))
        return None


async def backup_database() -> None:
    """
    Create a backup of the PostgreSQL database and upload to Google Drive.

    This job:
    1. Creates a pg_dump of the database
    2. Uploads the backup file to Google Drive
    3. Cleans up old local backups (keeps last 7 days)
    """
    logger.info("Starting database backup job")

    try:
        # Ensure backup directory exists
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"beauty_salon_backup_{timestamp}.sql"
        backup_path = BACKUP_DIR / backup_filename

        # Parse database URL for pg_dump
        # Expected format: postgresql+asyncpg://user:pass@host:port/dbname
        db_url = settings.database_url
        # Remove the async driver prefix
        db_url = db_url.replace("+asyncpg", "")

        # Extract connection details
        # Format: postgresql://user:pass@host:port/dbname
        from urllib.parse import urlparse

        parsed = urlparse(db_url)

        pg_host = parsed.hostname or "localhost"
        pg_port = parsed.port or 5432
        pg_user = parsed.username
        pg_password = parsed.password
        pg_database = parsed.path.lstrip("/")

        # Set environment variable for password
        env = os.environ.copy()
        env["PGPASSWORD"] = pg_password

        # Run pg_dump
        cmd = [
            "pg_dump",
            "-h", pg_host,
            "-p", str(pg_port),
            "-U", pg_user,
            "-d", pg_database,
            "-f", str(backup_path),
            "--no-owner",
            "--no-acl",
        ]

        logger.info("Running pg_dump", host=pg_host, database=pg_database)

        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error(
                "pg_dump failed",
                stderr=result.stderr,
                returncode=result.returncode,
            )
            return

        # Check backup file size
        backup_size = backup_path.stat().st_size
        logger.info(
            "Backup created",
            filename=backup_filename,
            size_bytes=backup_size,
        )

        # Upload to Google Drive
        if settings.google_drive_folder_id:
            await upload_to_drive(backup_path, backup_filename)

        # Clean up old backups (keep last 7 days)
        await cleanup_old_backups(days_to_keep=7)

        logger.info("Database backup job completed successfully")

    except subprocess.TimeoutExpired:
        logger.error("pg_dump timed out")
    except Exception as e:
        logger.error("Error in database backup job", error=str(e))


async def upload_to_drive(file_path: Path, filename: str) -> bool:
    """
    Upload a file to Google Drive.

    Args:
        file_path: Path to the local file
        filename: Name for the file in Drive

    Returns:
        True if successful, False otherwise
    """
    try:
        service = get_drive_service()
        if not service:
            return False

        file_metadata = {
            "name": filename,
            "parents": [settings.google_drive_folder_id],
        }

        media = MediaFileUpload(
            str(file_path),
            mimetype="application/sql",
            resumable=True,
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        ).execute()

        logger.info(
            "Backup uploaded to Google Drive",
            filename=filename,
            file_id=file.get("id"),
        )

        return True

    except Exception as e:
        logger.error("Failed to upload backup to Google Drive", error=str(e))
        return False


async def cleanup_old_backups(days_to_keep: int = 7) -> None:
    """
    Remove local backup files older than specified days.

    Args:
        days_to_keep: Number of days to keep backups
    """
    try:
        now = datetime.now()
        cutoff = now.timestamp() - (days_to_keep * 24 * 60 * 60)

        for backup_file in BACKUP_DIR.glob("beauty_salon_backup_*.sql"):
            if backup_file.stat().st_mtime < cutoff:
                backup_file.unlink()
                logger.info("Removed old backup", filename=backup_file.name)

    except Exception as e:
        logger.error("Error cleaning up old backups", error=str(e))
