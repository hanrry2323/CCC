import os
import threading
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException

from ..auth import check_auth
from .projects import PROJECTS

router = APIRouter()

EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", ".ccc",
    ".idea", ".vscode", "dist", "build",
}
EXCLUDE_FILE_NAMES = {".DS_Store"}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".egg-info")
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".pyc",
    ".so", ".dylib",
}
MAX_FILE_TREE_ENTRIES = 500
MAX_FILE_TREE_DEPTH = 4
MAX_FILE_READ_BYTES = 100 * 1024


def _walk_project_files(root: str) -> dict:
    result = {
        "project_id": "", "root": root,
        "entries": [], "truncated": False, "timed_out": False,
    }

    def _walk():
        root_path = Path(root).resolve()
        if not root_path.exists():
            result["error"] = "root not found"
            result["done"] = True
            return
        try:
            for current, dirs, files in os.walk(root_path, followlinks=False):
                rel = Path(current).relative_to(root_path)
                depth = 0 if str(rel) == "." else len(rel.parts)
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
                if depth > MAX_FILE_TREE_DEPTH:
                    dirs[:] = []
                    continue
                if str(rel) != ".":
                    if len(result["entries"]) >= MAX_FILE_TREE_ENTRIES:
                        result["truncated"] = True
                        dirs[:] = []
                        continue
                    result["entries"].append({
                        "name": Path(current).name, "type": "dir",
                        "path": str(rel).replace(os.sep, "/"), "depth": depth,
                    })
                for fname in files:
                    if len(result["entries"]) >= MAX_FILE_TREE_ENTRIES:
                        result["truncated"] = True
                        break
                    if fname in EXCLUDE_FILE_NAMES:
                        continue
                    if any(fname.endswith(s) for s in EXCLUDE_FILE_SUFFIXES):
                        continue
                    full = Path(current) / fname
                    try:
                        size = full.stat().st_size
                    except OSError:
                        size = 0
                    file_rel = (rel / fname) if str(rel) != "." else Path(fname)
                    result["entries"].append({
                        "name": fname, "type": "file",
                        "path": str(file_rel).replace(os.sep, "/"),
                        "depth": depth + 1 if str(rel) != "." else 1,
                        "size": size,
                    })
        except Exception as e:
            result["error"] = f"walk failed: {e}"
        finally:
            result["done"] = True

    worker = threading.Thread(target=_walk, daemon=True)
    worker.start()
    worker.join(timeout=5.0)
    if worker.is_alive():
        result["timed_out"] = True
        result["truncated"] = True
    elif not result.get("done") and not result.get("error"):
        result["error"] = "walk aborted without result"
    return result


@router.get("/api/projects/{project_id}/files")
async def list_project_files(request: Request, project_id: str):
    check_auth(request)
    proj = PROJECTS.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    root = Path(proj["path"]).resolve()
    data = _walk_project_files(str(root))
    data["project_id"] = project_id
    return data


@router.get("/api/projects/{project_id}/file")
async def read_project_file(request: Request, project_id: str, path: str):
    check_auth(request)
    proj = PROJECTS.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    if ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="path traversal not allowed")
    root = Path(proj["path"]).resolve()
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="path traversal not allowed")
    parts = Path(path).parts
    if any(p in EXCLUDE_DIRS for p in parts):
        raise HTTPException(status_code=400, detail=f"access to {path} is denied")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    ext = target.suffix.lower()
    if ext in BINARY_EXTS:
        raise HTTPException(status_code=415, detail="binary file not readable")
    try:
        size = target.stat().st_size
    except OSError:
        raise HTTPException(status_code=500, detail="stat failed")
    truncated = False
    if size > MAX_FILE_READ_BYTES:
        truncated = True
        content = target.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
    else:
        try:
            content = target.read_text(errors="replace")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="binary file not readable")
    return {
        "project_id": project_id, "path": path,
        "size": size, "truncated": truncated, "content": content,
    }
