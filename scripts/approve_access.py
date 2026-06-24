#!/usr/bin/env python3
"""
Zatwierdź lub odmów wniosku o dostęp — przenosi usera z grupy pending-* do docelowej grupy.

Użycie:
  # Zatwierdź wniosek (przenieś z pending-nauczyciel → rola-nauczyciel)
  python scripts/approve_access.py \
    --authentik-url https://login.zsel.opole.pl \
    --api-token AK_TOKEN \
    --username jan.kowalski \
    --source-group pending-nauczyciel \
    --target-group rola-nauczyciel \
    --action approve

  # Odmów wniosku (usuń z pending-*, pozostaw bez roli)
  python scripts/approve_access.py ... --action deny

  # Lista oczekujących wniosków
  python scripts/approve_access.py ... --action list-pending

API token: Authentik → Admin → Tokens → utwórz token dla akadmin z zakresem write.
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
import urllib.error


def ak_request(base: str, token: str, method: str, path: str, body: dict | None = None):
    url = f"{base}/api/v3{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_user(base: str, token: str, username: str) -> dict | None:
    status, data = ak_request(base, token, "GET", f"/core/users/?username={username}")
    if status == 200 and data.get("results"):
        return data["results"][0]
    return None


def get_group(base: str, token: str, name: str) -> dict | None:
    status, data = ak_request(base, token, "GET", f"/core/groups/?name={name}")
    if status == 200 and data.get("results"):
        return data["results"][0]
    return None


def get_pending_users(base: str, token: str, pending_groups: list[str]) -> list[dict]:
    pending = []
    for gname in pending_groups:
        grp = get_group(base, token, gname)
        if not grp:
            continue
        status, data = ak_request(base, token, "GET", f"/core/groups/{grp['pk']}/")
        if status == 200:
            for uid in data.get("users", []):
                u_status, u = ak_request(base, token, "GET", f"/core/users/{uid}/")
                if u_status == 200:
                    pending.append({**u, "_pending_group": gname})
    return pending


def add_to_group(base: str, token: str, user_pk: int, group_pk: str) -> bool:
    status, _ = ak_request(base, token, "POST", f"/core/groups/{group_pk}/add_user/",
                            {"pk": user_pk})
    return status in (200, 204)


def remove_from_group(base: str, token: str, user_pk: int, group_pk: str) -> bool:
    status, _ = ak_request(base, token, "POST", f"/core/groups/{group_pk}/remove_user/",
                            {"pk": user_pk})
    return status in (200, 204)


def main() -> None:
    ap = argparse.ArgumentParser(description="Zatwierdź/odmów wniosku o dostęp w Authentik")
    ap.add_argument("--authentik-url", required=True, help="https://login.zsel.opole.pl")
    ap.add_argument("--api-token", required=True, help="Authentik API token akadmin")
    ap.add_argument("--username", help="Nazwa użytkownika (dla approve/deny)")
    ap.add_argument("--source-group", help="Grupa pending-* z której usunąć po zatwierdzeniu")
    ap.add_argument("--target-group", help="Docelowa grupa rola-* (dla approve)")
    ap.add_argument("--action", required=True,
                    choices=["approve", "deny", "list-pending"])
    args = ap.parse_args()

    base = args.authentik_url.rstrip("/")
    token = args.api_token

    PENDING_GROUPS = ["pending-nauczyciel", "pending-rodzic", "pending-pracownik"]

    if args.action == "list-pending":
        users = get_pending_users(base, token, PENDING_GROUPS)
        if not users:
            print("Brak oczekujących wniosków.")
            return
        print(f"\n{'#':<4} {'Użytkownik':<25} {'Imię Nazwisko':<30} {'Wniosek o rolę'}")
        print("-" * 80)
        for i, u in enumerate(users, 1):
            name = f"{u.get('name', '')}".strip()
            print(f"{i:<4} {u['username']:<25} {name:<30} {u['_pending_group']}")
        print(f"\n{len(users)} oczekujących wniosków.")
        return

    # approve / deny
    if not args.username:
        ap.error("--username wymagany dla approve/deny")
    if not args.source_group:
        ap.error("--source-group wymagany dla approve/deny")

    user = get_user(base, token, args.username)
    if not user:
        print(f"✗ Użytkownik '{args.username}' nie znaleziony", file=sys.stderr)
        sys.exit(1)

    source_grp = get_group(base, token, args.source_group)
    if not source_grp:
        print(f"✗ Grupa '{args.source_group}' nie znaleziona", file=sys.stderr)
        sys.exit(1)

    if args.action == "deny":
        ok = remove_from_group(base, token, user["pk"], source_grp["pk"])
        if ok:
            print(f"✓ Odmówiono — '{args.username}' usunięty z '{args.source_group}'")
        else:
            print(f"✗ Błąd przy usuwaniu z grupy")
        return

    # approve
    if not args.target_group:
        ap.error("--target-group wymagany dla approve")
    target_grp = get_group(base, token, args.target_group)
    if not target_grp:
        print(f"✗ Docelowa grupa '{args.target_group}' nie znaleziona", file=sys.stderr)
        sys.exit(1)

    ok1 = add_to_group(base, token, user["pk"], target_grp["pk"])
    ok2 = remove_from_group(base, token, user["pk"], source_grp["pk"])

    if ok1 and ok2:
        print(f"✓ Zatwierdzono — '{args.username}' → '{args.target_group}' "
              f"(usunięty z '{args.source_group}')")
        print(f"  Sprawdź login.zsel.opole.pl → Admin → Użytkownicy → {args.username}")
    else:
        print(f"⚠️  Częściowy sukces: add={ok1}, remove_pending={ok2}")
        sys.exit(1)


if __name__ == "__main__":
    main()
