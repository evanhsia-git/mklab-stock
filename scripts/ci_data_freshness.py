#!/usr/bin/env python3
"""Freshness guard v2.0 — compare calendar dates, stage recovery before push.
Default scope is unchanged. Date-only comparison preserves same-day tie policy.
Invalid working data may be restored from a valid Git candidate; otherwise fail.
The caller must run full QA and commit staged corrections before pushing.
"""
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

DATE_FIELDS = ("as_of", "asof", "date", "last_updated", "updated", "updated_at")


def _normalize(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        if re.fullmatch(r"[0-9]{8}", value):
            return date(int(value[:4]), int(value[4:6]), int(value[6:])).isoformat()
        match = re.fullmatch(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})", value)
        if match:
            return date(*map(int, match.groups())).isoformat()
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?", value):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    return None


def _date(text):
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(doc, dict):
        return None
    # Prefer metadata and existing field order; do not hide an invalid
    # authoritative date behind a later ingestion timestamp.
    for obj in (doc.get("meta"), doc):
        if not isinstance(obj, dict):
            continue
        for key in DATE_FIELDS:
            if key in obj:
                return _normalize(obj[key])
    return None


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")


def _resolve(ref, optional=False):
    result = _git("rev-parse", "--verify", "--quiet", ref + "^{commit}")
    if result.returncode == 0:
        return result.stdout.strip()
    if optional and result.returncode in (1, 128):
        print(f"[freshness] WARNING: unavailable optional ref {ref}", file=sys.stderr)
        return None
    raise RuntimeError(f"Cannot resolve {ref}: {result.stderr.strip()}")


def _show(ref, path):
    if ref is None:
        return None
    listing = _git("ls-tree", "-z", ref, "--", path)
    if listing.returncode:
        raise RuntimeError(listing.stderr.strip())
    if not listing.stdout:
        return None
    result = _git("show", f"{ref}:{path}")
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def main(paths):
    try:
        remote = _resolve("origin/main")
        previous = _resolve("HEAD@{1}", optional=True)
        plan = []
        for p in dict.fromkeys(paths):
            if Path(p).is_absolute() or ".." in Path(p).parts or p.startswith("-"):
                raise RuntimeError(f"Invalid repository path: {p}")
            try:
                working = Path(p).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise RuntimeError(f"Cannot read {p}: {exc}") from exc
            refs = {"HEAD@{1}": previous, "origin/main": remote}
            candidates = {"working": working}
            for label, sha in refs.items():
                text = _show(sha, p)
                if text is not None:
                    candidates[label] = text
            dates = {label: _date(text) for label, text in candidates.items()}
            for label, value in dates.items():
                if value is None:
                    print(f"[freshness] WARNING: {p}: invalid date/JSON in {label}", file=sys.stderr)
            valid = {label: value for label, value in dates.items() if value is not None}
            if not valid:
                raise RuntimeError(f"{p}: no valid dated candidate")
            # Dict order preserves original tie policy: working, previous, remote.
            best = max(valid, key=valid.get)
            print(f"[freshness] {p}: {dates}; selected {best}")
            if best != "working":
                plan.append((p, refs[best], valid[best]))
        # Validate all paths before staging any recovery.
        for p, sha, expected in plan:
            subprocess.run(["git", "checkout", sha, "--", p], check=True)
            if _date(Path(p).read_text(encoding="utf-8")) != expected:
                raise RuntimeError(f"Recovery verification failed: {p}")
        print(f"[freshness] OK: {len(plan)} correction(s) staged; caller must run QA")
        return 0
    except (OSError, UnicodeError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[freshness] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["data/stocks.json", "data/industry.json"]))
