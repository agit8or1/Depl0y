"""ISO Images API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict
from datetime import datetime
import os
import hashlib
import shutil
import requests
import tempfile
import logging

from app.core.database import get_db
from app.core.config import settings
from app.models import ISOImage, OSType, User
from app.api.auth import get_current_user, require_operator

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory progress tracking
upload_progress: Dict[str, Dict] = {}


# Pydantic models
class ISOImageResponse(BaseModel):
    id: int
    name: str
    filename: str
    os_type: OSType
    version: Optional[str]
    architecture: str
    file_size: Optional[int]
    checksum: Optional[str]
    storage_path: str
    created_at: datetime
    is_available: bool

    class Config:
        from_attributes = True


class ISODownloadRequest(BaseModel):
    url: str
    name: str
    os_type: OSType
    version: Optional[str] = None
    architecture: str = "amd64"


def process_iso_file(
    temp_path: str,
    storage_path: str,
    upload_id: str,
    iso_id: int,
    db_session
):
    """Process ISO file in background: copy with progress and calculate checksum"""
    try:
        upload_progress[upload_id] = {
            "status": "copying",
            "progress": 0,
            "message": "Copying file to storage..."
        }

        # Get file size
        file_size = os.path.getsize(temp_path)

        # Copy with progress tracking
        bytes_copied = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        with open(temp_path, 'rb') as src:
            with open(storage_path, 'wb') as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
                    bytes_copied += len(chunk)
                    progress = int((bytes_copied / file_size) * 50)  # First 50% for copying
                    upload_progress[upload_id]["progress"] = progress

        # Remove temp file
        os.remove(temp_path)

        # Calculate checksum with progress
        upload_progress[upload_id].update({
            "status": "calculating_checksum",
            "progress": 50,
            "message": "Calculating checksum..."
        })

        sha256_hash = hashlib.sha256()
        bytes_hashed = 0

        with open(storage_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256_hash.update(chunk)
                bytes_hashed += len(chunk)
                progress = 50 + int((bytes_hashed / file_size) * 50)  # Last 50% for checksum
                upload_progress[upload_id]["progress"] = progress

        checksum = sha256_hash.hexdigest()

        # Update database
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            iso = db.query(ISOImage).filter(ISOImage.id == iso_id).first()
            if iso:
                iso.checksum = checksum
                db.commit()
        finally:
            db.close()

        upload_progress[upload_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Upload completed successfully",
            "checksum": checksum
        }

    except Exception as e:
        logger.error(f"Error processing ISO: {e}")
        upload_progress[upload_id] = {
            "status": "error",
            "progress": 0,
            "message": f"Error: {str(e)}"
        }
        # Clean up on error
        if os.path.exists(storage_path):
            os.remove(storage_path)


@router.get("/", response_model=List[ISOImageResponse])
async def list_isos(
    skip: int = 0,
    limit: int = 100,
    os_type: Optional[OSType] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all ISO images"""
    query = db.query(ISOImage)

    if os_type:
        query = query.filter(ISOImage.os_type == os_type)

    isos = query.filter(ISOImage.is_available == True).offset(skip).limit(limit).all()
    return isos


@router.post("/", response_model=ISOImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_iso(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = None,
    os_type: OSType = OSType.UBUNTU,
    version: str = None,
    architecture: str = "amd64",
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Upload an ISO image with progress tracking"""
    # Validate file extension
    if not file.filename.endswith('.iso'):
        raise HTTPException(status_code=400, detail="Only ISO files are allowed")

    # Create storage directory if it doesn't exist
    os.makedirs(settings.ISO_STORAGE_PATH, exist_ok=True)

    # Generate unique filename
    filename = file.filename
    storage_path = os.path.join(settings.ISO_STORAGE_PATH, filename)

    # Check if file already exists
    if os.path.exists(storage_path):
        raise HTTPException(status_code=400, detail="ISO file already exists")

    try:
        # Save to temporary file first (fast - already in memory from upload)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.iso') as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            temp_path = tmp_file.name

        # Calculate file size
        file_size = os.path.getsize(temp_path)

        if file_size > settings.MAX_ISO_SIZE:
            os.remove(temp_path)
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {settings.MAX_ISO_SIZE / (1024**3)}GB"
            )

        # Create database record with "processing" status
        iso_name = name or filename.replace('.iso', '')
        new_iso = ISOImage(
            name=iso_name,
            filename=filename,
            os_type=os_type,
            version=version,
            architecture=architecture,
            file_size=file_size,
            checksum="processing...",
            storage_path=storage_path,
            uploaded_by=current_user.id,
            is_available=True,
        )

        db.add(new_iso)
        db.commit()
        db.refresh(new_iso)

        # Generate upload ID for progress tracking
        upload_id = f"upload_{new_iso.id}"
        upload_progress[upload_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Upload queued for processing..."
        }

        # Process file in background
        background_tasks.add_task(
            process_iso_file,
            temp_path,
            storage_path,
            upload_id,
            new_iso.id,
            db
        )

        return new_iso

    except Exception as e:
        # Clean up temp file if database operation fails
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Failed to upload ISO: {str(e)}")


@router.post("/download", response_model=ISOImageResponse, status_code=status.HTTP_201_CREATED)
async def download_iso_from_url(
    download_request: ISODownloadRequest,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Download an ISO image from a URL"""
    # Create storage directory if it doesn't exist
    os.makedirs(settings.ISO_STORAGE_PATH, exist_ok=True)

    # Extract filename from URL or use provided name
    url_filename = download_request.url.split('/')[-1]
    if not url_filename.endswith('.iso'):
        url_filename = download_request.name.replace(' ', '_') + '.iso'

    filename = url_filename
    storage_path = os.path.join(settings.ISO_STORAGE_PATH, filename)

    # Check if file already exists
    if os.path.exists(storage_path):
        raise HTTPException(status_code=400, detail="ISO file already exists")

    try:
        # Download file from URL
        response = requests.get(download_request.url, stream=True, timeout=30)
        response.raise_for_status()

        # Get total file size if available
        total_size = int(response.headers.get('content-length', 0))

        if total_size > settings.MAX_ISO_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {settings.MAX_ISO_SIZE / (1024**3)}GB"
            )

        # Download to temporary file first
        with tempfile.NamedTemporaryFile(delete=False, suffix='.iso') as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
            tmp_path = tmp_file.name

        # Move to final location
        shutil.move(tmp_path, storage_path)

        # Calculate file size
        file_size = os.path.getsize(storage_path)

        # Set checksum to calculating for now
        checksum = "calculating..."

        # Create database record
        new_iso = ISOImage(
            name=download_request.name,
            filename=filename,
            os_type=download_request.os_type,
            version=download_request.version,
            architecture=download_request.architecture,
            file_size=file_size,
            checksum=checksum,
            storage_path=storage_path,
            uploaded_by=current_user.id,
            is_available=True,
        )

        db.add(new_iso)
        db.commit()
        db.refresh(new_iso)

        return new_iso

    except requests.exceptions.RequestException as e:
        # Clean up file if download fails
        if os.path.exists(storage_path):
            os.remove(storage_path)
        raise HTTPException(status_code=400, detail=f"Failed to download ISO: {str(e)}")
    except Exception as e:
        # Clean up file if database operation fails
        if os.path.exists(storage_path):
            os.remove(storage_path)
        raise HTTPException(status_code=500, detail=f"Failed to download ISO: {str(e)}")


@router.get("/{iso_id}", response_model=ISOImageResponse)
async def get_iso(
    iso_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get ISO image by ID"""
    iso = db.query(ISOImage).filter(ISOImage.id == iso_id).first()
    if not iso:
        raise HTTPException(status_code=404, detail="ISO not found")
    return iso


@router.delete("/{iso_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_iso(
    iso_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Delete ISO image"""
    iso = db.query(ISOImage).filter(ISOImage.id == iso_id).first()
    if not iso:
        raise HTTPException(status_code=404, detail="ISO not found")

    # Delete file from storage
    if os.path.exists(iso.storage_path):
        try:
            os.remove(iso.storage_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

    # Delete from database
    db.delete(iso)
    db.commit()

    return None


@router.get("/{iso_id}/progress")
async def get_upload_progress(
    iso_id: int,
    current_user: User = Depends(get_current_user),
):
    """Get upload progress for an ISO"""
    upload_id = f"upload_{iso_id}"

    if upload_id not in upload_progress:
        return {
            "status": "not_found",
            "progress": 100,
            "message": "Upload completed or not tracked"
        }

    return upload_progress[upload_id]


@router.post("/{iso_id}/verify")
async def verify_iso(
    iso_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify ISO checksum"""
    iso = db.query(ISOImage).filter(ISOImage.id == iso_id).first()
    if not iso:
        raise HTTPException(status_code=404, detail="ISO not found")

    if not os.path.exists(iso.storage_path):
        iso.is_available = False
        db.commit()
        raise HTTPException(status_code=404, detail="ISO file not found on disk")

    # Calculate current checksum
    sha256_hash = hashlib.sha256()
    with open(iso.storage_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    current_checksum = sha256_hash.hexdigest()

    # Compare with stored checksum
    if current_checksum == iso.checksum:
        return {
            "status": "valid",
            "message": "ISO checksum matches",
            "checksum": current_checksum,
        }
    else:
        return {
            "status": "invalid",
            "message": "ISO checksum does not match",
            "expected": iso.checksum,
            "actual": current_checksum,
        }
