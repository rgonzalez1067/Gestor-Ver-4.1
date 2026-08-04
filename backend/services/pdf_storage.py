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


def storage_key_exists(filename: str) -> bool:
    """Verificación AUTORITATIVA de existencia de un archivo en Object Storage
    (solo metadata, sin descargar el contenido).

    A diferencia de `list_storage_keys` (que el storage trunca a 1000 claves y
    puede dar falsos negativos en cuentas grandes), esto consulta la clave exacta
    como prefijo y confirma coincidencia exacta. Devuelve True/False.
    """
    from services.object_storage import list_objects

    key = _storage_key(filename)
    try:
        objs, _ = list_objects(key)
        return any((o.get("path") or "") == key for o in objs)
    except Exception as e:
        logger.warning(f"[pdf_storage] storage_key_exists error {filename}: {e}")
        return False


def list_storage_keys() -> set:
    """Devuelve el conjunto de claves RELATIVAS (sin el prefijo de ambiente) que
    existen actualmente en Object Storage para este entorno.

    Ej: {'COT-2026-...pdf', 'client_documents/ab12_x.pdf'}

    Se usa para auditar existencia en lote con UNA sola llamada de red (en vez de
    descargar cada archivo), evitando timeouts del proxy en la auto-recuperación.
    ⚠️ El storage trunca a 1000 claves; para grandes volúmenes usar
    `storage_key_exists` como verificación autoritativa por archivo.
    """
    from services.object_storage import list_objects

    objs, truncated = list_objects(PDF_PREFIX)
    if truncated:
        logger.warning(
            "[pdf_storage] list_storage_keys: respuesta truncada por el storage; "
            "el inventario puede estar incompleto."
        )
    prefix = PDF_PREFIX.rstrip("/") + "/"
    keys = set()
    for o in objs:
        p = (o.get("path") or "")
        if p.startswith(prefix):
            keys.add(p[len(prefix):])
    return keys


def storage_name_from_upload_url(url: str) -> str:
    """Convierte la URL pública del adjunto en la clave usada por `save_pdf_dual`.

    Ej: `/uploads/client_documents/ab12_x.pdf` -> `client_documents/ab12_x.pdf`
    """
    return (url or "").replace("/uploads/", "", 1).lstrip("/")


def load_attachment_bytes(upload_url: str) -> Optional[bytes]:
    """Resuelve los bytes de un adjunto persistido por `save_pdf_dual`.

    Prioridad (homologado con el origen que sirve descargas/preview):
      1) Object Storage (persistente cross-deploy / producción).
      2) Filesystem local como fallback best-effort (cache del pod).
    Devuelve None si no se localiza en ningún backend.
    """
    name = storage_name_from_upload_url(upload_url)
    res = get_pdf_from_storage(name)
    if res and res[0]:
        return res[0]
    local = f"/app/backend{upload_url or ''}"
    try:
        if os.path.exists(local):
            with open(local, "rb") as fh:
                return fh.read()
    except OSError as e:
        logger.warning(f"[pdf_storage] lectura local falló para {local}: {e}")
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
