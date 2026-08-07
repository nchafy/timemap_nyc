"""Google Maps URL parsing.

Measured against the owner's real export: **no url carries coordinates** (0 of
768). They look like

    /maps/place/<Name>/data=!4m2!3m1!1s0x89c25b9c843094b5:0x97e7ef230b9352d

where the `!1s` hex pair is a *feature id* identifying the exact venue, not a
position. So this module recovers the name and the identifier, and deliberately
offers no coordinate extraction: inventing a position from a viewport parameter
would put pins hundreds of metres from the saved place.

This module must never make a network request, so it must not import
urllib.request. Resolving a feature id or a maps.app.goo.gl shortlink needs HTTP
and therefore belongs to a geocoding step, not here.
"""

from __future__ import annotations

import re
import urllib.parse as up

_PLACE_PATH = re.compile(r"^/maps/place/([^/]+)")
_FEATURE_ID = re.compile(r"!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)")
_GOOGLE_HOSTS = ("google.com", "google.co.uk", "goo.gl")


def is_google_maps_place_url(url: str) -> bool:
    """True if this url points at a Google Maps place rather than, say, an article."""
    if not url:
        return False
    parsed = up.urlparse(url)
    host = parsed.netloc.lower()
    if not any(host == h or host.endswith("." + h) for h in _GOOGLE_HOSTS):
        return False
    if _PLACE_PATH.match(parsed.path):
        return True
    query = up.parse_qs(parsed.query)
    return bool({"cid", "ftid", "place_id"} & set(query))


def extract_place_name(url: str) -> str | None:
    """The place name embedded in a `/maps/place/<Name>/` path, if present."""
    if not url:
        return None
    match = _PLACE_PATH.match(up.urlparse(url).path)
    if not match:
        return None
    name = up.unquote_plus(match.group(1)).strip()
    return name or None


def extract_feature_id(url: str) -> str | None:
    """A stable identifier for the exact venue saved.

    Three forms appear in real exports, in descending order of specificity:
    `!1s0x…:0x…` in the path, `ftid=0x…:0x…` in the query, and `cid=<digits>`.
    The cid form is prefixed so it cannot collide with an ftid.
    """
    if not url:
        return None
    match = _FEATURE_ID.search(url)
    if match:
        return match.group(1).lower()

    query = up.parse_qs(up.urlparse(url).query)
    ftid = (query.get("ftid") or [""])[0].strip()
    if ftid:
        return ftid.lower()
    cid = (query.get("cid") or [""])[0].strip()
    if cid:
        return f"cid:{cid}"
    return None
