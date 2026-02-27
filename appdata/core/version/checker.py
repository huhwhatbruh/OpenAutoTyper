# File: appdata/core/version/checker.py
import re
import threading
from typing import Optional, Tuple

import requests

from appdata.core.version.model import VERSION

_VERSION_URLS = (
    "https://raw.githubusercontent.com/huhwhatbruh/OpenAutoTyper/main/appdata/core/version/model.py",
)

_VERSION_LINE_RE = re.compile(r'^\s*VERSION\s*=\s*["\']([^"\']+)["\']')


def check_version() -> None:
    """
    Check GitHub for a newer version of OpenAutoTyper in a background thread
    so the main window is never blocked by network I/O.
    """
    t = threading.Thread(target=_check_version_worker, daemon=True)
    t.start()


def _check_version_worker() -> None:
    """Runs on a daemon thread; must schedule any GUI work back on the main thread."""
    remote_version: Optional[str] = None

    for url in _VERSION_URLS:
        try:
            resp = requests.get(
                url,
                timeout=5,
                headers={
                    "User-Agent": "OpenAutoTyper/" + VERSION,
                    "Cache-Control": "no-cache",
                },
            )
        except Exception:
            continue

        if resp.status_code != 200:
            continue

        remote_version = _extract_version(resp.text)
        if remote_version is not None:
            break

    if remote_version is None:
        from PySide6.QtCore import QTimer  # type: ignore[import]
        QTimer.singleShot(0, _show_update_check_failed)
        return

    rv: str = remote_version  # local binding narrows the type for Pyre2
    if _compare_versions(VERSION, rv):
        from PySide6.QtCore import QTimer  # type: ignore[import]
        from functools import partial
        QTimer.singleShot(0, partial(_show_new_version_prompt, rv))


def _show_update_check_failed() -> None:
    from appdata.ui.message_boxes.update_check_failed import show_update_check_failed  # type: ignore[import]
    show_update_check_failed()


def _show_new_version_prompt(remote_version: str) -> None:
    from appdata.ui.message_boxes.new_version_prompt import show_new_version_prompt  # type: ignore[import]
    show_new_version_prompt(remote_version)


def _strip_v_prefix(s: str) -> str:
    """Remove a leading 'v' or 'V' from a version string."""
    if len(s) > 0 and s[0] in ("v", "V"):
        return s[1:].strip()
    return s


def _extract_version(text: str) -> Optional[str]:
    """
    Extract VERSION from a python source file.
    Expected format: VERSION = "0.12" (whitespace tolerant).
    """
    for line in text.splitlines():
        m = _VERSION_LINE_RE.match(line)
        if m is None:
            continue
        v = m.group(1).strip()
        v = _strip_v_prefix(v)
        return v if v else None
    return None


def _parse_version(ver: str) -> Tuple[int, ...]:
    """
    Parse a version string like '0.12' or '0.12.1' into a tuple of ints.
    Non-numeric suffixes (e.g. '0.12-beta') are ignored.
    Returns an empty tuple on failure.
    """
    s = ver.strip()
    if not s:
        return ()

    s = _strip_v_prefix(s)

    m = re.match(r"(\d+(?:\.\d+)*)", s)
    if m is None:
        return ()

    parts = m.group(1).split(".")
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            return ()
    return tuple(out)


def _compare_versions(local_ver: str, remote_ver: str) -> bool:
    """
    Return True if remote_ver is newer than local_ver.
    """
    local_t = _parse_version(local_ver)
    remote_t = _parse_version(remote_ver)
    if not local_t or not remote_t:
        return False

    n = max(len(local_t), len(remote_t))
    padded_local = local_t + (0,) * (n - len(local_t))
    padded_remote = remote_t + (0,) * (n - len(remote_t))

    return padded_remote > padded_local
