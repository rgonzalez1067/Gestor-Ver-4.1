"""PDF Storage helper — dual write to local FS + Emergent Object Storage.

Used to persist PDFs across deploys. Each environment uses its own namespace
(preview/, production/) controlled by the APP_ENV env var, so a deploy from
Preview to Production no longer overwrites Production's PDFs.
"""
import os
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

from services.object_storage import put_object, get_object

logger = logging.getLogger(__name__)

# Namespace per environment. Defaults to "preview" if not set.
APP_ENV = (os.environ.get("APP_ENV") or "preview").lower().strip().replace("/", "_") or "preview"
PDF_PREFIX = f"pdfs/{APP_ENV}"


def _storage_key(filename: str) -> str:
    """Build the canonical storage key for a given filename."""
    safe = (filename or "").lstrip("/").replace("\\", "/")
    # Conservar subdirectorios pero garantizar prefijo de ambiente
    return f"{PDF_PREFIX}/{safe}"


def save_pdf_to_storage(pdf_bytes: bytes, filename: str, content_type: str = "application/pdf") -> bool:
    """Upload a PDF (or any binary) to Object Storage.

    Returns True on success, False otherwise (logs warning).
    """
    if not pdf_bytes:
        return False
    try:
        put_object(_storage_key(filename), pdf_bytes, content_type)
        return True
    except Exception as e:
        logger.warning(f"[pdf_storage] put_object failed for {filename}: {e}")
        return False


def upload_existing_file(local_path: Path, filename: Optional[str] = None) -> bool:
    """Read a file from disk and push it to Object Storage. No-op if missing."""
    try:
        if not local_path or not Path(local_path).exists():
            return False
        path = Path(local_path)
        name = filename or path.name
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return save_pdf_to_storage(path.read_bytes(), name, content_type=ctype)
    except Exception as e:
        logger.warning(f"[pdf_storage] upload_existing_file failed: {e}")
        return False


def get_pdf_from_storage(filename: str) -> Optional[Tuple[bytes, str]]:
    """Fetch a file from Object Storage. Returns (bytes, content_type) or None."""
    try:
        return get_object(_storage_key(filename))
    except Exception as e:
        # 404s are expected for legacy files that only live on disk; debug-level log
        logger.debug(f"[pdf_storage] get_object miss for {filename}: {e}")
        return None


def save_pdf_dual(pdf_path: Path, pdf_bytes: bytes, filename: Optional[str] = None) -> Path:
    """Escribe el PDF en disco (compat / cache) Y lo sube a Object Storage.

    El upload a storage falla silenciosamente para no romper el flujo principal.
    Retorna el Path local (igual que antes) para que el código que lo necesite
    siga funcionando.
    """
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)
    name = filename or pdf_path.name
    save_pdf_to_storage(pdf_bytes, name)
    return pdf_path
