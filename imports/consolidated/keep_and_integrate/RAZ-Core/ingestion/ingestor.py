"""
RAZ Core - File Ingestion Pipeline
Handles ingestion of documents, notes, and files into RAZ's memory.
Supports: .txt, .pdf, .docx, .py, .md, .json, .csv, .xlsx, image OCR
Safe handling: no auto-deletes, no destructive actions.
"""

import os
import hashlib
import json
from datetime import datetime

# Optional imports (graceful degradation if not installed)
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from docx import Document as DocxDocument
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False

try:
    from openpyxl import load_workbook
    XLSX_SUPPORT = True
except ImportError:
    XLSX_SUPPORT = False

try:
    from PIL import Image
    PIL_SUPPORT = True
except ImportError:
    PIL_SUPPORT = False

try:
    import pytesseract
    OCR_SUPPORT = True
except ImportError:
    OCR_SUPPORT = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INGESTION_LOG = os.path.join(BASE_DIR, "logs", "ingestion_log.json")

SUPPORTED_EXTENSIONS = {
    ".txt", ".py", ".md", ".json", ".csv", ".pdf", ".docx", ".xlsx",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"
}


def compute_hash(filepath: str) -> str:
    """Compute SHA256 hash of file for duplicate detection."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_text(filepath: str) -> str:
    """Extract readable text content from a file."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext in {".txt", ".md", ".py", ".csv"}:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"[READ ERROR: {e}]"

    elif ext == ".json":
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            return json.dumps(data, indent=2)[:10000]
        except Exception as e:
            return f"[JSON READ ERROR: {e}]"

    elif ext == ".pdf":
        if not PDF_SUPPORT:
            return "[PDF SUPPORT NOT INSTALLED - run: pip install PyPDF2]"
        try:
            text_parts = []
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts)
        except Exception as e:
            return f"[PDF READ ERROR: {e}]"

    elif ext == ".docx":
        if not DOCX_SUPPORT:
            return "[DOCX SUPPORT NOT INSTALLED - run: pip install python-docx]"
        try:
            doc = DocxDocument(filepath)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception as e:
            return f"[DOCX READ ERROR: {e}]"

    elif ext == ".xlsx":
        if not XLSX_SUPPORT:
            return "[XLSX SUPPORT NOT INSTALLED - run: pip install openpyxl]"
        try:
            wb = load_workbook(filepath, data_only=True)
            lines = []
            for ws in wb.worksheets:
                lines.append(f"[SHEET] {ws.title}")
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if cells:
                        lines.append(" | ".join(cells))
            return "\n".join(lines)
        except Exception as e:
            return f"[XLSX READ ERROR: {e}]"

    elif ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        if not PIL_SUPPORT:
            return "[IMAGE SUPPORT NOT INSTALLED - run: pip install Pillow]"
        if not OCR_SUPPORT:
            return "[OCR SUPPORT NOT INSTALLED - run: pip install pytesseract]"
        try:
            image = Image.open(filepath)
            text = pytesseract.image_to_string(image)
            if text and text.strip():
                return text
            return "[OCR READ OK - no text detected in image]"
        except Exception as e:
            return f"[OCR READ ERROR: {e}]"

    return f"[UNSUPPORTED FILE TYPE: {ext}]"


def auto_tag(filename: str, content: str) -> list:
    """Auto-generate tags from filename and content keywords."""
    tags = []
    name_lower = filename.lower()
    content_lower = content.lower()

    tag_map = {
        "hyperbaric": ["hyperbaric", "wellness", "recovery"],
        "hero": ["veterans", "nonprofit", "heroes"],
        "floater": ["lonely floater", "artist", "music"],
        "aveek": ["aveek", "artist", "music"],
        "marketing": ["marketing", "strategy"],
        "cybersecurity": ["cybersecurity", "security"],
        "project": ["project", "planning"],
        "meeting": ["meeting", "notes"],
        "research": ["research"],
        "code": [".py", "def ", "class ", "import "],
        "finance": ["revenue", "budget", "cost", "income", "profit"],
    }

    for tag_key, keywords in tag_map.items():
        for kw in keywords:
            if kw in name_lower or kw in content_lower[:2000]:
                tags.append(tag_key)
                break

    return list(set(tags))


def ingest_file(filepath: str, memory_engine=None) -> dict:
    """
    Ingest a single file into RAZ memory.
    Returns a result dict with status, metadata, and preview.
    Does NOT delete or modify the original file.
    """
    result = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "status": None,
        "reason": None,
        "tags": [],
        "preview": "",
        "hash": None,
        "size_bytes": 0,
        "timestamp": datetime.now().isoformat()
    }

    if not os.path.isfile(filepath):
        result["status"] = "error"
        result["reason"] = "File not found"
        return result

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        result["status"] = "skipped"
        result["reason"] = f"Unsupported extension: {ext}"
        return result

    try:
        file_hash = compute_hash(filepath)
        result["hash"] = file_hash
        result["size_bytes"] = os.path.getsize(filepath)

        if memory_engine:
            if memory_engine.check_file_duplicate(file_hash):
                result["status"] = "duplicate"
                result["reason"] = "File already ingested (hash match)"
                _append_log(result)
                return result

        content = extract_text(filepath)
        tags = auto_tag(result["filename"], content)
        preview = content[:500]

        result["tags"] = tags
        result["preview"] = preview

        if memory_engine:
            success, reason = memory_engine.record_ingested_file(
                filename=result["filename"],
                filepath=filepath,
                file_hash=file_hash,
                size_bytes=result["size_bytes"],
                content_preview=preview,
                tags=tags
            )
            result["status"] = "ingested" if success else reason
        else:
            result["status"] = "extracted"

        result["reason"] = f"Tags: {', '.join(tags) if tags else 'none'}"

    except Exception as e:
        result["status"] = "error"
        result["reason"] = str(e)

    _append_log(result)
    return result


def ingest_directory(dirpath: str, memory_engine=None, recursive: bool = True) -> list:
    """
    Ingest all supported files from a directory.
    Safe: read-only, no modifications to original files.
    """
    results = []

    if not os.path.isdir(dirpath):
        return [{"status": "error", "reason": f"Not a directory: {dirpath}"}]

    for root, dirs, files in os.walk(dirpath):
        # Skip hidden and system dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"__pycache__", "node_modules", ".git"}]

        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                filepath = os.path.join(root, filename)
                result = ingest_file(filepath, memory_engine=memory_engine)
                results.append(result)
                status_icon = {"ingested": "OK", "duplicate": "DUP", "error": "ERR", "skipped": "SKIP", "extracted": "EXT"}.get(result["status"], "?")
                print(f"  [{status_icon}] {filename} | {result['reason']}")

        if not recursive:
            break

    ingested = sum(1 for r in results if r["status"] == "ingested")
    duplicates = sum(1 for r in results if r["status"] == "duplicate")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"\n[INGESTION] Complete: {ingested} ingested, {duplicates} duplicates, {errors} errors, {len(results)} total")
    return results


def scan_for_duplicates(directory: str) -> list:
    """
    Scan a directory and identify duplicate files by hash.
    Purely analytical - no files are modified or deleted.
    Returns list of duplicate groups.
    """
    hash_map = {}
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"__pycache__", ".git"}]
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                h = compute_hash(filepath)
                if h not in hash_map:
                    hash_map[h] = []
                hash_map[h].append(filepath)
            except Exception:
                pass

    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    print(f"[SCAN] Found {len(duplicates)} duplicate groups across {directory}")
    for h, paths in duplicates.items():
        print(f"  HASH {h[:12]}...")
        for p in paths:
            print(f"    - {p}")
    return duplicates


def _append_log(result: dict):
    """Append ingestion result to the log file."""
    os.makedirs(os.path.dirname(INGESTION_LOG), exist_ok=True)
    try:
        if os.path.exists(INGESTION_LOG):
            with open(INGESTION_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = []
        log.append(result)
        with open(INGESTION_LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    import sys
    sys.path.insert(0, BASE_DIR)
    import core.memory_engine as mem
    mem.init_memory()

    test_dir = os.path.join(BASE_DIR, "..", "Raziel")
    if os.path.isdir(test_dir):
        print(f"[INGESTION] Scanning: {test_dir}")
        results = ingest_directory(test_dir, memory_engine=mem, recursive=False)
    else:
        print("[INGESTION] Test directory not found. Provide a path to ingest.")
        print("Usage: python ingestion/ingestor.py")
