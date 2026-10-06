"""Resolve the visitor's browser timezone for server-rendered timestamps.

Streamlit renders on the server and never sees the client's timezone, so a
zero-height inline component asks the browser once per session and caches the
answer in session state. Display helpers then convert through that zone, so
times read in the viewer's local time and carry the correct abbreviation
("EDT", "PDT", ...) instead of a hardcoded ET.

The React port reads the same zone straight from `Intl.DateTimeFormat`, so both
apps agree for the same browser.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import streamlit as st

FALLBACK_TZ = "America/New_York"
_PROBE_KEY = "browser_tz_probe"

_HTML = """<div id="tz-probe" style="display:none"></div>"""

_JS = """
export default function (component) {
  const { data, setStateValue } = component
  let zone = ""
  try {
    zone = Intl.DateTimeFormat().resolvedOptions().timeZone || ""
  } catch (err) {
    zone = ""
  }
  // Only report a change, otherwise every rerun would queue another one.
  if (zone && zone !== (data && data.value)) setStateValue("tz", zone)
}
"""

_probe = st.components.v2.component(
    "wnba_browser_timezone_probe",
    html=_HTML,
    js=_JS,
)


def _validated(name: object) -> str | None:
    """Return `name` if zoneinfo can resolve it, else None."""
    if not isinstance(name, str) or not name:
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return name


def browser_timezone(*, mount: bool = True) -> str:
    """Browser timezone as an IANA name, falling back to US Eastern.

    Mounts the probe only while the answer is unknown, so the extra round trip
    costs at most one rerun per browser session. Pass ``mount=False`` in hot
    loops to read the cached value without adding a component.
    """
    cached = _validated(st.session_state.get(_PROBE_KEY, {}).get("tz"))
    if cached:
        return cached
    if mount:
        _probe(key=_PROBE_KEY, data={"value": ""}, height="content")
        cached = _validated(st.session_state.get(_PROBE_KEY, {}).get("tz"))
        if cached:
            return cached
    return FALLBACK_TZ


def short_tz_name(tz_name: str, stamp: pd.Timestamp | datetime | None = None) -> str:
    """Short zone abbreviation for `tz_name` at `stamp` (default: now)."""
    if stamp is None:
        return datetime.now(tz=ZoneInfo(tz_name)).strftime("%Z") or tz_name
    moment = pd.Timestamp(stamp)
    if moment.tzinfo is None:
        moment = moment.tz_localize("UTC")
    return moment.tz_convert(tz_name).strftime("%Z") or tz_name
