#!/usr/bin/env python3
"""Freshness guard v2.1 — restore the newest valid dated copy of each data file.

Usage: python3 scripts/ci_data_freshness.py [paths...]
       (default: data/stocks.json data/industry.json)

For each path, candidates are the working copy, HEAD@{1} (optional) and origin/main.
- Dates are compared as calendar dates only.
- Ties keep the working copy (candidate order: working, HEAD@{1}, origin/main).
- An invalid or undated working copy is replaced by the newest valid candidate.
- If no candidate has a valid date, the run fails.

Recovery is two-phase: every replacement is validated in memory first, and only
then are files written and staged. Exit 0 = OK (corrections staged, QA required),
exit 1 = failure, nothing written.
"""
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

DATE_FIELDS = ("as_of", "asof", "date", "last_updated", "updated", "updated_at")
DEFAULT_PATHS = ("data/stocks.json", "data/industry.json")

COMPACT_DATE = re.compile(r"[0-9]{8}")
ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})")
ISO_DATETIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:\.(?:[0-9]{3}|[0-9]{6}))?)?"
    r"(?:Z|[+-][0-9]{2}:[0-9]{2})?"
)


def normalize_date(value):
    """Return an ISO calendar date (YYYY-MM-DD) for a valid date string, else None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        if COMPACT_DATE.fullmatch(text):
            return date(int(text[:4]), int(text[4:6]), int(text[6:])).isoformat()
        match = ISO_DATE.fullmatch(text)
        if match:
            return date(*map(int, match.groups())).isoformat()
        if ISO_DATETIME.fullmatch(text):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None
    return None


def extract_date(raw):
    """Return the authoritative ISO date of a JSON document (bytes), or None.

    meta.<field> is preferred over top-level <field>. If the first matching field
    is invalid, the result is None: a later field must not hide a bad date.
    """
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(doc, dict):
        return None
    for container in (doc.get("meta"), doc):
        if not isinstance(container, dict):
            continue
        for key in DATE_FIELDS:
            if key in container:
                return normalize_date(container[key])
    return None


def git(*args):
    return subprocess.run(["git", *args], capture_output=True)


def stderr_text(result):
    return result.stderr.decode("utf-8", errors="replace").strip()


def resolve_commit(ref, optional=False):
    result = git("rev-parse", "--verify", "--quiet", ref + "^{commit}")
    if result.returncode == 0:
        return result.stdout.decode("utf-8").strip()
    if optional:
        print(f"[freshness] WARNING: unavailable optional ref {ref}", file=sys.stderr)
        return None
    raise RuntimeError(f"Cannot resolve {ref}: {stderr_text(result)}")


def read_blob(ref, path):
    """Return the exact bytes of path at ref, or None if ref is None or path is absent."""
    if ref is None:
        return None
    listing = git("ls-tree", "-z", ref, "--", path)
    if listing.returncode != 0:
        raise RuntimeError(f"ls-tree {ref}:{path} failed: {stderr_text(listing)}")
    if not listing.stdout:
        return None
    blob = git("show", f"{ref}:{path}")
    if blob.returncode != 0:
        raise RuntimeError(f"show {ref}:{path} failed: {stderr_text(blob)}")
    return blob.stdout


def check_path(path):
    parts = Path(path).parts
    if not path or Path(path).is_absolute() or ".." in parts or path.startswith("-"):
        raise RuntimeError(f"Invalid repository path: {path}")


def plan_recovery(paths):
    """Phase 1: decide every path and validate every replacement. Writes nothing."""
    remote = resolve_commit("origin/main")
    previous = resolve_commit("HEAD@{1}", optional=True)
    refs = {"HEAD@{1}": previous, "origin/main": remote}

    restores = []  # (path, exact bytes to write, validated date)
    for path in dict.fromkeys(paths):
        check_path(path)
        try:
            working = Path(path).read_bytes()
        except OSError as exc:
            raise RuntimeError(f"Cannot read {path}: {exc}") from exc

        candidates = {"working": working}
        for label, ref in refs.items():
            blob = read_blob(ref, path)
            if blob is not None:
                candidates[label] = blob

        dates = {label: extract_date(raw) for label, raw in candidates.items()}
        for label, value in dates.items():
            if value is None:
                print(f"[freshness] WARNING: {path}: invalid date/JSON in {label}", file=sys.stderr)

        valid = {label: value for label, value in dates.items() if value is not None}
        if not valid:
            raise RuntimeError(f"{path}: no valid dated candidate")

        # max() returns the first maximal key, so the working copy wins ties.
        best = max(valid, key=valid.get)
        print(f"[freshness] {path}: {dates}; selected {best}")
        if best != "working":
            restores.append((path, candidates[best], valid[best]))
    return restores


def apply_recovery(restores):
    """Phase 2: write and stage the already-validated replacements."""
    for path, raw, expected in restores:
        if extract_date(raw) != expected:  # defensive; cheap and catches logic drift
            raise RuntimeError(f"Recovery verification failed: {path}")
    for path, raw, _ in restores:
        Path(path).write_bytes(raw)
        staged = git("add", "--", path)
        if staged.returncode != 0:
            raise RuntimeError(f"git add {path} failed: {stderr_text(staged)}")


def main(paths):
    try:
        restores = plan_recovery(paths)
        apply_recovery(restores)
    except (OSError, UnicodeError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"[freshness] ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"[freshness] OK: {len(restores)} correction(s) staged; caller must run QA")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(DEFAULT_PATHS)))
