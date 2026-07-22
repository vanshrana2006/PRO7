"""Downloads a PDF from a URL to local storage. Network layer -- verify live
per README; logic itself is a straightforward streamed write, low-risk."""
from __future__ import annotations

import os
import pathlib

import httpx

from app.core.config import get_settings


class PDFDownloadError(RuntimeError):
    pass


async def download_pdf(url: str, dest_filename: str) -> str:
    """Streams `url` to PDF_STORAGE_DIR/dest_filename. Returns the local path.
    Raises PDFDownloadError on any failure -- never returns a path to a
    partially-written or missing file."""
    settings = get_settings()
    os.makedirs(settings.PDF_STORAGE_DIR, exist_ok=True)
    dest_path = str(pathlib.Path(settings.PDF_STORAGE_DIR) / dest_filename)

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "pdf" not in content_type and not url.endswith(".pdf"):
                    # Some servers omit content-type; don't hard-fail on that
                    # alone, but do fail if it's clearly HTML (e.g. an error
                    # page returned with a 200 status).
                    if "html" in content_type:
                        raise PDFDownloadError(
                            f"Expected a PDF but got content-type '{content_type}' from {url}"
                        )
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
    except httpx.HTTPError as exc:
        raise PDFDownloadError(f"Failed to download PDF from {url}: {exc}") from exc

    if not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
        raise PDFDownloadError(f"Download from {url} produced an empty file")

    return dest_path
