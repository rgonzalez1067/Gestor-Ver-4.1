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
    """Persiste el archivo. Prioridad: Object Storage (primary) + FS local (cache).

    Comportamiento tolerante a entornos con filesystem ephemeral o read-only
    (como algunos pods de Kubernetes en producción):
      - Intenta Object Storage primero. Si tiene éxito → considerado OK.
      - Intenta FS local como cache best-effort. Si falla por OSError
        (PermissionError, ReadOnlyFileSystemError, etc.) se loggea y se ignora.
      - Si AMBOS fallan, lanza la excepción para que el caller lo sepa.

    Retorna el Path local (puede o no existir físicamente, según el FS).
    """
    pdf_path = Path(pdf_path)
    name = filename or pdf_path.name
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"

    # 1) Object Storage primero (primary). Importante: este es el storage
    # persistente cross-deploy y es el que la app usa para servir descargas.
    storage_ok = save_pdf_to_storage(pdf_bytes, name, content_type=ctype)

    # 2) Filesystem local — best-effort. En producción con FS read-only
    # este bloque puede fallar; lo toleramos siempre que storage_ok=True.
    fs_ok = False
    fs_err: Optional[Exception] = None
    try:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(pdf_bytes)
        fs_ok = True
    except (OSError, PermissionError) as e:
        fs_err = e
        logger.warning(f"[pdf_storage] FS write skipped (likely read-only): {pdf_path} → {e}")

    if not storage_ok and not fs_ok:
        # Ningún backend pudo persistir → propagamos el error.
        raise RuntimeError(
            f"No se pudo persistir el archivo. ObjectStorage falló y FS también: {fs_err}"
        )
    return pdf_path
