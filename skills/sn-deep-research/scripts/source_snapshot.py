#!/usr/bin/env python3
"""Store and verify immutable, report-scoped source text snapshots.

The cache layout is:

    source_cache/<url_sha256>/<content_sha256>.md
    source_cache/<url_sha256>/<content_sha256>.meta.json

Only UTF-8 text is accepted. Cache files are installed atomically and are never
overwritten with different bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SNAPSHOT_REF_RE = re.compile(
    r"^source_cache/(?P<url_hash>[0-9a-f]{64})/"
    r"(?P<content_hash>[0-9a-f]{64})\.md$"
)
META_SCHEMA_VERSION = "1.0"


class SnapshotError(ValueError):
    """Raised when a snapshot path or payload violates the cache contract."""


def normalize_url(url: str) -> str:
    """Return the stable URL form used to derive a cache key.

    Normalization is intentionally conservative: scheme and host are folded,
    default ports and fragments are removed, and query order is preserved.
    """
    if not isinstance(url, str) or not url.strip():
        raise SnapshotError("URL must be a non-empty string")
    raw = url.strip()
    if any(ord(ch) < 0x20 or ch.isspace() for ch in raw):
        raise SnapshotError("URL must not contain whitespace or control characters")

    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError as exc:
        raise SnapshotError(f"Invalid URL: {exc}") from exc

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise SnapshotError("URL scheme must be http or https")
    if parts.username is not None or parts.password is not None:
        raise SnapshotError("URL credentials are not allowed")
    if not parts.hostname:
        raise SnapshotError("URL must include a host")

    try:
        host = parts.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise SnapshotError("URL host is not valid IDNA") from exc
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def content_hash(text: str) -> str:
    return hashlib.sha256(_text_bytes(text)).hexdigest()


def make_snapshot_ref(url_digest: str, content_digest: str) -> str:
    _require_hash(url_digest, "url hash")
    _require_hash(content_digest, "content hash")
    return f"source_cache/{url_digest}/{content_digest}.md"


def parse_snapshot_ref(snapshot_ref: str) -> tuple[str, str]:
    if not isinstance(snapshot_ref, str):
        raise SnapshotError("snapshot_ref must be a string")
    match = SNAPSHOT_REF_RE.fullmatch(snapshot_ref)
    if not match:
        raise SnapshotError(
            "snapshot_ref must match source_cache/<url_hash>/<content_hash>.md"
        )
    return match.group("url_hash"), match.group("content_hash")


def store_snapshot(source_cache: Path | str, url: str, text: str) -> dict:
    """Store one immutable snapshot and return its reference and metadata."""
    normalized = normalize_url(url)
    body = _text_bytes(text)
    uhash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    chash = hashlib.sha256(body).hexdigest()
    snapshot_ref = make_snapshot_ref(uhash, chash)
    cache_dir = _ensure_cache_dir(Path(source_cache), uhash)

    metadata = {
        "schema_version": META_SCHEMA_VERSION,
        "normalized_url": normalized,
        "url_hash": uhash,
        "content_hash": chash,
        "encoding": "utf-8",
        "media_type": "text/markdown",
    }
    meta_bytes = (json.dumps(
        metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n").encode("utf-8")

    _atomic_install(cache_dir / f"{chash}.md", body)
    _atomic_install(cache_dir / f"{chash}.meta.json", meta_bytes)
    return {"snapshot_ref": snapshot_ref, **metadata}


def lookup_snapshots(
    source_cache: Path | str,
    url: str,
    expected_content_hash: str | None = None,
) -> list[dict]:
    """Return verified snapshots for a URL, ordered by content hash."""
    normalized = normalize_url(url)
    uhash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    root = _resolved_cache_root(Path(source_cache), create=False)
    url_dir = root / uhash
    if not url_dir.exists():
        return []
    _require_real_directory(url_dir)

    if expected_content_hash is not None:
        _require_hash(expected_content_hash, "content hash")
        refs = [make_snapshot_ref(uhash, expected_content_hash)]
        if not (url_dir / f"{expected_content_hash}.md").exists() and not (
            url_dir / f"{expected_content_hash}.meta.json"
        ).exists():
            return []
    else:
        refs = [
            make_snapshot_ref(uhash, path.name.removesuffix(".meta.json"))
            for path in sorted(url_dir.glob("*.meta.json"))
            if HASH_RE.fullmatch(path.name.removesuffix(".meta.json"))
        ]

    results = []
    for ref in refs:
        verified = verify_snapshot(source_cache, ref, expected_url=url)
        results.append({
            "snapshot_ref": ref,
            "normalized_url": verified["metadata"]["normalized_url"],
            "url_hash": verified["metadata"]["url_hash"],
            "content_hash": verified["metadata"]["content_hash"],
        })
    return results


def verify_snapshot(
    source_cache: Path | str,
    snapshot_ref: str,
    expected_url: str | None = None,
) -> dict:
    """Verify path, metadata, hashes, and UTF-8 text for one snapshot."""
    uhash, chash = parse_snapshot_ref(snapshot_ref)
    root = _resolved_cache_root(Path(source_cache), create=False)
    body_path = _safe_snapshot_path(root, uhash, f"{chash}.md")
    meta_path = _safe_snapshot_path(root, uhash, f"{chash}.meta.json")

    body = _read_regular_file(body_path)
    if hashlib.sha256(body).hexdigest() != chash:
        raise SnapshotError("Snapshot content hash does not match snapshot_ref")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotError("Snapshot body must be UTF-8 text") from exc
    _validate_text(text)

    try:
        metadata = json.loads(_read_regular_file(meta_path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("Snapshot metadata must be valid UTF-8 JSON") from exc
    if not isinstance(metadata, dict):
        raise SnapshotError("Snapshot metadata must be a JSON object")

    expected = {
        "schema_version": META_SCHEMA_VERSION,
        "url_hash": uhash,
        "content_hash": chash,
        "encoding": "utf-8",
        "media_type": "text/markdown",
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise SnapshotError(f"Snapshot metadata field {key!r} does not match cache path")

    normalized = metadata.get("normalized_url")
    try:
        canonical = normalize_url(normalized)
    except SnapshotError as exc:
        raise SnapshotError("Snapshot metadata normalized_url is invalid") from exc
    if canonical != normalized:
        raise SnapshotError("Snapshot metadata normalized_url is not canonical")
    if hashlib.sha256(normalized.encode("utf-8")).hexdigest() != uhash:
        raise SnapshotError("Snapshot URL hash does not match normalized_url")
    if expected_url is not None and normalize_url(expected_url) != normalized:
        raise SnapshotError("Snapshot URL does not match evidence source URL")

    return {"snapshot_ref": snapshot_ref, "metadata": metadata, "text": text}


def contains_direct_quote(snapshot_text: str, snippet: str) -> bool:
    """Check a direct quote with Unicode and whitespace normalization only."""
    if not isinstance(snippet, str) or not snippet.strip():
        return False
    haystack = _quote_normal_form(snapshot_text)
    needle = _quote_normal_form(snippet)
    return bool(needle) and needle in haystack


def _quote_normal_form(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _validate_text(text: str) -> None:
    if not isinstance(text, str):
        raise SnapshotError("Snapshot body must be text")
    if "\x00" in text:
        raise SnapshotError("Snapshot body must not contain NUL bytes")


def _text_bytes(text: str) -> bytes:
    _validate_text(text)
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SnapshotError("Snapshot body must be valid Unicode text") from exc


def _require_hash(value: str, label: str) -> None:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise SnapshotError(f"{label} must be 64 lowercase hexadecimal characters")


def _resolved_cache_root(path: Path, create: bool) -> Path:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        raise SnapshotError(f"Source cache does not exist: {path}")
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise SnapshotError(f"Source cache does not exist: {path}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise SnapshotError(f"Source cache must be a real directory: {path}")
    return path.resolve(strict=True)


def _ensure_cache_dir(source_cache: Path, uhash: str) -> Path:
    _require_hash(uhash, "URL hash")
    root = _resolved_cache_root(source_cache, create=True)
    cache_dir = root / uhash
    try:
        cache_dir.mkdir(mode=0o700)
    except FileExistsError:
        pass
    _require_real_directory(cache_dir)
    if cache_dir.resolve(strict=True).parent != root:
        raise SnapshotError("URL cache directory escapes source cache")
    return cache_dir


def _require_real_directory(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise SnapshotError(f"Cache directory does not exist: {path}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise SnapshotError(f"Cache path is not a real directory: {path}")


def _safe_snapshot_path(root: Path, uhash: str, filename: str) -> Path:
    _require_hash(uhash, "URL hash")
    url_dir = root / uhash
    _require_real_directory(url_dir)
    if url_dir.resolve(strict=True).parent != root:
        raise SnapshotError("Snapshot directory escapes source cache")
    path = url_dir / filename
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise SnapshotError("Snapshot path escapes source cache") from exc
    return path


def _read_regular_file(path: Path) -> bytes:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise SnapshotError(f"Snapshot file does not exist: {path}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise SnapshotError(f"Snapshot path is not a regular file: {path}")
    return path.read_bytes()


def _atomic_install(target: Path, payload: bytes) -> None:
    """Install bytes without exposing partial content or replacing a target."""
    if target.parent.is_symlink():
        raise SnapshotError(f"Snapshot parent must not be a symlink: {target.parent}")

    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, target)
        except FileExistsError:
            if _read_regular_file(target) != payload:
                raise SnapshotError(f"Immutable snapshot already exists with different bytes: {target}")
        else:
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temp_path.unlink(missing_ok=True)


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize = subparsers.add_parser("normalize", help="normalize a source URL")
    normalize.add_argument("url")

    store = subparsers.add_parser("store", help="store an immutable UTF-8 text snapshot")
    store.add_argument("--source-cache", required=True)
    store.add_argument("--url", required=True)
    store.add_argument("--input", default="-", help="UTF-8 text file, or - for stdin")

    lookup = subparsers.add_parser("lookup", help="list verified snapshots for a URL")
    lookup.add_argument("--source-cache", required=True)
    lookup.add_argument("--url", required=True)
    lookup.add_argument("--content-hash")

    verify = subparsers.add_parser("verify", help="verify one exact snapshot reference")
    verify.add_argument("--source-cache", required=True)
    verify.add_argument("--snapshot-ref", required=True)
    verify.add_argument("--url")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "normalize":
            result = {"normalized_url": normalize_url(args.url), "url_hash": url_hash(args.url)}
        elif args.command == "store":
            result = store_snapshot(args.source_cache, args.url, _read_input(args.input))
        elif args.command == "lookup":
            result = {"snapshots": lookup_snapshots(
                args.source_cache, args.url, args.content_hash
            )}
        else:
            verified = verify_snapshot(args.source_cache, args.snapshot_ref, args.url)
            result = {
                "snapshot_ref": verified["snapshot_ref"],
                **verified["metadata"],
            }
    except (OSError, SnapshotError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
