"""Figma URL parsing and open-file matching helpers.

The bundled read-only Figma bridge reads files that are *open* in Figma Desktop
through its companion plugin (no REST API, no token). Spec2Ship parses the URL
locally and then asks Claude to confirm, through the MCP tools, that the open
file / node matches what the user referenced (by file key when the bridge
reports one, otherwise by file name).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .common import Spec2ShipError

_KINDS = {"design", "file", "proto", "board", "slides", "make", "site"}
_KEY_RE = re.compile(r"^[A-Za-z0-9]{10,64}$")
_NODE_RE = re.compile(r"^(I?\d+)[:-](\d+)((?:;\d+[:-]\d+)*)$")


def normalize_node_id(raw: str) -> str:
    """'12-345' / '12%3A345' / '12:345' -> '12:345' (format required by the Figma plugin API)."""
    value = unquote(raw).strip()
    m = _NODE_RE.match(value)
    if not m:
        raise Spec2ShipError(f"Invalid Figma node id '{raw}'. Expected e.g. 12-345 or 12:345")
    rest = m.group(3).replace("-", ":") if m.group(3) else ""
    return f"{m.group(1)}:{m.group(2)}{rest}"


def parse_figma_url(url: str) -> dict[str, Any]:
    if not url or not isinstance(url, str):
        raise Spec2ShipError("A Figma URL is required, e.g. https://www.figma.com/design/<FILE_KEY>/<name>?node-id=1-2")
    u = urlparse(url.strip())
    if u.scheme != "https":
        raise Spec2ShipError(f"Figma URL must use https: {url}")
    host = (u.hostname or "").lower()
    if host not in ("figma.com", "www.figma.com"):
        raise Spec2ShipError(f"Not a figma.com URL: {url}")
    parts = [p for p in u.path.split("/") if p]
    if len(parts) < 2 or parts[0] not in _KINDS:
        raise Spec2ShipError(
            f"Unrecognized Figma URL path '{u.path}'. Expected /design/<FILE_KEY>/<name> (or /file/, /proto/, /board/)."
        )
    kind, key = parts[0], parts[1]
    if not _KEY_RE.match(key):
        raise Spec2ShipError(f"Figma file key '{key}' looks invalid")
    branch_key = None
    name_slug = parts[2] if len(parts) > 2 else None
    if len(parts) > 3 and parts[2] == "branch":
        branch_key = parts[3]
        name_slug = parts[4] if len(parts) > 4 else None
    qs = parse_qs(u.query)
    node_id = None
    if "node-id" in qs and qs["node-id"][0]:
        node_id = normalize_node_id(qs["node-id"][0])
    return {
        "url": url.strip(),
        "kind": kind,
        "file_key": key,
        "branch_key": branch_key,
        "name_slug": unquote(name_slug) if name_slug else None,
        "node_id": node_id,
    }


def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def match_open_file(url_info: dict[str, Any], open_file_name: str | None,
                    open_file_key: str | None = None) -> dict[str, Any]:
    """Compare the referenced file with the file open in Figma Desktop.

    A file key reported by the bridge (`list_files`) is decisive. Otherwise the URL
    name slug is compared heuristically with the open file name, and anything but
    'high' must be confirmed by the user.
    """
    key = url_info.get("file_key")
    if open_file_key and key:
        if open_file_key == key:
            return {"match": "high", "reason": f"Open file key {open_file_key} equals the URL file key."}
        return {"match": "low", "reason": f"Open file key {open_file_key} differs from the URL file key {key}. "
                                          "Ask the user to open the referenced file in Figma Desktop."}
    slug = url_info.get("name_slug")
    if not open_file_name:
        return {"match": "unknown", "reason": "Open file name not available from the Figma MCP."}
    if not slug:
        return {"match": "unknown", "reason": "URL has no file-name segment to compare."}
    a, b = _norm_name(slug), _norm_name(open_file_name)
    if a and a == b:
        return {"match": "high", "reason": f"URL name '{slug}' matches open file '{open_file_name}'."}
    if a and b and (a in b or b in a):
        return {"match": "medium", "reason": f"URL name '{slug}' partially matches open file '{open_file_name}'."}
    return {
        "match": "low",
        "reason": f"URL name '{slug}' does not match open file '{open_file_name}'. Ask the user to open the referenced file in Figma Desktop.",
    }
