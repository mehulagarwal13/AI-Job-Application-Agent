import uuid
from pathlib import Path
import hashlib

STORAGE_DIR = Path("storage/resumes")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}

# Magic bytes: don't trust the filename — verify the actual content.
# .docx is a ZIP container, hence the PK signature.
MAGIC_BYTES = {
    ".pdf": (b"%PDF-",),
    ".docx": (b"PK\x03\x04",),
}


def validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Only PDF and DOCX are allowed.")
    return ext


def validate_content(ext: str, content: bytes) -> None:
    """Rejects files whose bytes don't match their claimed type (e.g. renamed .exe)."""
    signatures = MAGIC_BYTES.get(ext, ())
    if not any(content.startswith(sig) for sig in signatures):
        raise ValueError(
            f"File content does not match a valid {ext} file. "
            "The file may be corrupt or renamed from another format."
        )


def save_resume_file(filename: str, content: bytes) -> tuple[str, str]:
    """
    Validates extension AND content signature, then saves to disk under a unique ID.
    Returns (resume_id, stored_path).
    """
    ext = validate_extension(filename)
    validate_content(ext, content)

    resume_id = str(uuid.uuid4())
    stored_filename = f"{resume_id}{ext}"
    stored_path = STORAGE_DIR / stored_filename

    with open(stored_path, "wb") as f:
        f.write(content)

    return resume_id, str(stored_path)


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
