"""Asset inventory parser (PR-03).

Render/reference image storage in ``asset_blob`` is deliberately deferred.  The
parser validates a discovered image and records its metadata in the ledger, but
returns ``skipped_by_policy`` and writes no bytes.  This keeps PR-03 honest: an
asset file is not reported as migrated when only its path/hash was seen.
"""
from __future__ import annotations

import mimetypes
import sqlite3

from .base import SourceFile, blocked, skipped


def _signature_ok(mime_type: str, data: bytes) -> bool:
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if mime_type == "image/bmp":
        return data.startswith(b"BM")
    return True


class AssetParser:
    classification = "asset"
    parser_version = "asset/1"

    def parse(self, source: SourceFile, connection: sqlite3.Connection):
        mime_type, _ = mimetypes.guess_type(source.relative_path)
        mime_type = mime_type or "application/octet-stream"
        data = source.read_bytes()
        if mime_type.startswith("image/") and not _signature_ok(mime_type, data):
            return blocked(
                "asset_signature_invalid",
                details={"mime_type": mime_type, "sha256": source.sha256},
            )
        return skipped(
            "asset_blob_deferred",
            details={
                "mime_type": mime_type,
                "sha256": source.sha256,
                "bytes": source.size_bytes,
                "reason": "asset_blob media persistence is deferred; metadata only",
            },
        )
