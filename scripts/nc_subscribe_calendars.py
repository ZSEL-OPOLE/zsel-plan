#!/usr/bin/env python3
"""
Subskrybuj plan lekcji w Nextcloud Calendar.

Dla każdej klasy (i opcjonalnie nauczyciela) tworzy subskrypcję kalendarza
w Nextcloud wskazującą na plan.zsel.opole.pl/api/plan/ical/klasa/{klasa}.

Użycie:
  python scripts/nc_subscribe_calendars.py \
    --nc-url https://dysk.zsel.opole.pl \
    --nc-user akadmin --nc-pass SECRET \
    --plan-url https://plan.zsel.opole.pl \
    --rok-start 2026-09-01

Nextcloud CalDAV subscription tworzona przez MKCALENDAR + PROPPATCH (zewn. subskrypcja).
"""
from __future__ import annotations
import argparse
import sys
import urllib.request
import urllib.parse
import json
import base64

CALENDAR_COLOR = "#1E88E5"  # niebieski — plan lekcji


def nc_request(
    method: str,
    url: str,
    auth: str,
    body: str | None = None,
    content_type: str = "application/xml",
) -> tuple[int, str]:
    headers = {
        "Authorization": f"Basic {auth}",
        "OCS-APIRequest": "true",
    }
    if body:
        headers["Content-Type"] = content_type
    data = body.encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def subscribe_class_calendar(
    nc_base: str,
    nc_user: str,
    auth: str,
    klasa: str,
    plan_base: str,
    rok_start: str,
) -> bool:
    """Utwórz subskrypcję kalendarza dla klasy w Nextcloud."""
    cal_name = f"Plan {klasa}"
    cal_id = f"plan-{klasa.lower()}"
    ical_url = f"{plan_base}/api/plan/ical/klasa/{urllib.parse.quote(klasa)}?rok_start={rok_start}"

    # Create calendar via MKCALENDAR (CalDAV)
    caldav_base = f"{nc_base}/remote.php/dav/calendars/{nc_user}"
    cal_url = f"{caldav_base}/{cal_id}/"

    mk_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<c:mkcalendar xmlns:c="urn:ietf:params:xml:ns:caldav"
              xmlns:d="DAV:"
              xmlns:cs="http://calendarserver.org/ns/"
              xmlns:oc="http://owncloud.org/ns">
  <d:set>
    <d:prop>
      <d:displayname>{cal_name}</d:displayname>
      <oc:calendar-color>{CALENDAR_COLOR}</oc:calendar-color>
    </d:prop>
  </d:set>
</c:mkcalendar>"""

    status, _ = nc_request("MKCALENDAR", cal_url, auth, mk_body)
    if status not in (200, 201, 405):  # 405 = already exists
        print(f"  ✗ {klasa}: MKCALENDAR {status}")
        return False

    # Set external subscription source via PROPPATCH
    pp_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<d:propertyupdate xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/">
  <d:set>
    <d:prop>
      <cs:source>
        <d:href>{ical_url}</d:href>
      </cs:source>
    </d:prop>
  </d:set>
</d:propertyupdate>"""

    status2, _ = nc_request("PROPPATCH", cal_url, auth, pp_body)
    if status2 in (200, 207):
        print(f"  ✓ {klasa}: subskrypcja → {ical_url}")
        return True
    else:
        print(f"  ✗ {klasa}: PROPPATCH {status2}")
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Subskrybuj plany klas w Nextcloud Calendar")
    ap.add_argument("--nc-url", required=True, help="Nextcloud base URL, np. https://dysk.zsel.opole.pl")
    ap.add_argument("--nc-user", required=True, help="Użytkownik Nextcloud (admin)")
    ap.add_argument("--nc-pass", required=True, help="Hasło Nextcloud")
    ap.add_argument("--plan-url", required=True, help="Plan API base URL, np. https://plan.zsel.opole.pl")
    ap.add_argument("--rok-start", default="2026-09-01", help="Pierwszy poniedziałek roku szkolnego (YYYY-MM-DD)")
    ap.add_argument("--klasy", nargs="*", help="Lista klas (domyślnie: pobierz z /api/plan/klasy)")
    args = ap.parse_args()

    auth = base64.b64encode(f"{args.nc_user}:{args.nc_pass}".encode()).decode()

    # Pobierz listę klas z API jeśli nie podano
    klasy = args.klasy
    if not klasy:
        try:
            with urllib.request.urlopen(f"{args.plan_url}/api/plan/klasy", timeout=10) as r:
                klasy = json.loads(r.read())
            print(f"Pobrano {len(klasy)} klas z {args.plan_url}/api/plan/klasy")
        except Exception as e:
            print(f"Błąd pobierania listy klas: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"\nSubskrybuję {len(klasy)} kalendarzy w {args.nc_url} ...\n")
    ok = sum(
        subscribe_class_calendar(args.nc_url, args.nc_user, auth, kl, args.plan_url, args.rok_start)
        for kl in klasy
    )
    print(f"\n{'✅' if ok == len(klasy) else '⚠️'} {ok}/{len(klasy)} subskrypcji utworzono pomyślnie")
    print("\nW Nextcloud Calendar klasy widoczne jako niebieskie kalendarze 'Plan <klasa>'.")


if __name__ == "__main__":
    main()
