"""
ASP Buvette — synchronisation FFBB -> Supabase.

Découvre les équipes du club sur competitions.ffbb.com, lit le championnat/poule
de chacune, extrait les matchs du club et les envoie dans la table `matches`
(upsert). Ne touche jamais à la table `buvette` (responsables saisis en admin).

Usage :
    python sync.py              # scrape + envoi vers Supabase
    python sync.py --dry-run    # scrape seulement, écrit out/matches.json
Code retour : 0 si tout est OK, 1 si au moins une équipe n'a pas pu être lue.

Prérequis : .env avec SUPABASE_SERVICE_KEY ; le projet FFBB_Agenda (scraper_http.py)
à l'emplacement FFBB_AGENDA_PATH (par défaut ci-dessous).
"""
import argparse
import asyncio
import html
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import aiohttp
import requests

ROOT_DIR = Path(__file__).resolve().parent
FFBB_AGENDA_PATH = os.environ.get(
    "FFBB_AGENDA_PATH", r"C:\Users\utilisateur\Documents\Claude\Projects\FFBB_Agenda"
)
sys.path.insert(0, FFBB_AGENDA_PATH)

import scraper_http  # noqa: E402
from scraper_http import HEADERS, SSL_CTX, scrape_poule  # noqa: E402

scraper_http.MAX_CONCURRENT = 2  # c'est le débit qui fait couper la FFBB

SITE = "https://competitions.ffbb.com"
CLUB_ID = "ges0057030"
CLUB_URL = f"{SITE}/ligues/ges/comites/0057/clubs/{CLUB_ID}"
CLUB_KEY = "STE MARIE AUX CHENES"

PAUSE_ENTRE_EQUIPES = 3        # secondes
PAUSES_RETRY = (20, 60, 120)   # secondes avant chaque nouvel essai si défi anti-bot


def load_env() -> None:
    f = ROOT_DIR / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_supabase_config() -> tuple[str, str]:
    cfg = json.loads((ROOT_DIR / "supabase.config.json").read_text(encoding="utf-8"))
    return cfg["url"].rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")


# ── Découverte ────────────────────────────────────────────────────────────────

def is_challenge(page: str) -> bool:
    return "Establishing a secure connection" in page or "Hold tight" in page[:3000]


async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    """GET avec retries si la FFBB répond par son défi anti-bot."""
    for i in range(len(PAUSES_RETRY) + 1):
        async with session.get(url, headers=HEADERS, ssl=SSL_CTX,
                               timeout=aiohttp.ClientTimeout(total=40)) as r:
            page = await r.text()
        if r.status == 200 and not is_challenge(page):
            return page
        if i < len(PAUSES_RETRY):
            print(f"   … défi anti-bot / HTTP {r.status}, nouvel essai dans {PAUSES_RETRY[i]}s")
            await asyncio.sleep(PAUSES_RETRY[i])
    raise RuntimeError(f"page inaccessible : {url}")


async def discover_teams(session: aiohttp.ClientSession) -> list[str]:
    page = await fetch(session, CLUB_URL)
    return sorted(set(re.findall(rf"/clubs/{CLUB_ID}/equipes/(\d+)", page)))


async def team_competition_url(session: aiohttp.ClientSession, team_id: str) -> str | None:
    page = await fetch(session, f"{CLUB_URL}/equipes/{team_id}")
    links = [html.unescape(x) for x in
             re.findall(r'href="(/ligues/[^"]*competitions/[^"]*phase=\d+[^"]*)"', page)]
    # championnat classique : phase + poule ; amical : phase seule
    return next((x for x in links if "poule=" in x), links[0] if links else None)


# ── Transformation ────────────────────────────────────────────────────────────

def categorie_from(titre: str, code: str) -> str:
    """Libellé lisible (U13 M, Seniors F…) depuis le titre FFBB, sinon le code."""
    t = (titre or "").lower()
    c = code.lower()
    sexe = "F" if re.search(r"f[ée]minin", t) else "M" if re.search(r"masculin", t) else ""
    age = re.search(r"\bu\s?(\d{1,2})\b", t)
    if age:
        cat = f"U{age.group(1)}"
    elif "senior" in t:
        cat = "Seniors"
    else:
        m = re.search(r"u(\d{1,2})", c)
        cat = f"U{m.group(1)}" if m else "Seniors"
    if not sexe:
        for seg in c.split("-"):
            m = re.match(r"^(?:id|dv|d|r|pn|n|e)?([mf])(?:u\d+|\d+)?$", seg)
            if m:
                sexe = m.group(1).upper()
                break
    return f"{cat} {sexe}".strip()


def to_row(m: dict, code: str, meta: dict) -> dict | None:
    mid = re.search(r"/match/(\d+)", m.get("match_url", ""))
    if not mid or not m.get("date"):
        return None
    score1 = score2 = None
    if m.get("joue") and m.get("score") and "-" in m["score"]:
        a, b = m["score"].split("-", 1)
        if a.isdigit() and b.isdigit():
            score1, score2 = int(a), int(b)
    titre = meta.get("titre", "") or ""
    amical = bool(re.search(r"amical|(^|-)ami(-|$)", (titre + " " + code).lower()))
    heure = m.get("heure") or None
    return {
        "id": mid.group(1),
        "date": m["date"],
        "heure": None if heure in (None, "", "00:00") else heure,
        "equipe1": m["equipe1"],
        "equipe2": m["equipe2"],
        "competition": code,
        "categorie": categorie_from(titre, code),
        "poule": meta.get("poule") or None,
        "salle": m.get("salle") or None,
        "adresse": m.get("adresse") or None,
        "score1": score1,
        "score2": score2,
        "joue": bool(m.get("joue")),
        "amical": amical,
        "domicile": CLUB_KEY in m["equipe1"].upper(),
        "statut": "joue" if m.get("joue") else "prevu",
        "match_url": m.get("match_url") or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Supabase ──────────────────────────────────────────────────────────────────

class Supabase:
    def __init__(self, url: str, key: str):
        self.base = f"{url}/rest/v1"
        self.h = {"apikey": key, "Authorization": f"Bearer {key}",
                  "Content-Type": "application/json"}

    def upsert_matches(self, rows: list[dict]) -> None:
        for i in range(0, len(rows), 200):
            r = requests.post(
                f"{self.base}/matches?on_conflict=id",
                headers={**self.h, "Prefer": "resolution=merge-duplicates,return=minimal"},
                data=json.dumps(rows[i:i + 200]), timeout=60)
            r.raise_for_status()

    def future_ids(self, competition: str, poule: str | None) -> set[str]:
        params = {"select": "id", "competition": f"eq.{competition}",
                  "date": f"gte.{date.today().isoformat()}", "statut": "eq.prevu"}
        params["poule"] = f"eq.{poule}" if poule else "is.null"
        r = requests.get(f"{self.base}/matches", headers=self.h, params=params, timeout=30)
        r.raise_for_status()
        return {x["id"] for x in r.json()}

    def mark_cancelled(self, ids: list[str]) -> None:
        if not ids:
            return
        in_list = ",".join(ids)
        r = requests.patch(f"{self.base}/matches?id=in.({in_list})",
                           headers={**self.h, "Prefer": "return=minimal"},
                           data=json.dumps({"statut": "annule",
                                            "updated_at": datetime.now(timezone.utc).isoformat()}),
                           timeout=30)
        r.raise_for_status()

    def log(self, **kw) -> None:
        r = requests.post(f"{self.base}/sync_log", headers={**self.h, "Prefer": "return=minimal"},
                          data=json.dumps(kw), timeout=30)
        r.raise_for_status()


# ── Orchestration ─────────────────────────────────────────────────────────────

async def scrape_all() -> tuple[list[dict], list[tuple[str, str | None, set[str]]], list[str], int]:
    """Retourne (rows, [(code, poule, ids présents)], erreurs, nb_equipes)."""
    rows: dict[str, dict] = {}
    seen_comps: dict[tuple[str, str | None], set[str]] = {}
    errors: list[str] = []
    seen_urls: set[str] = set()

    async with aiohttp.ClientSession() as session:
        teams = await discover_teams(session)
        print(f"{len(teams)} équipes découvertes")
        for n, tid in enumerate(teams, 1):
            try:
                url = await team_competition_url(session, tid)
                if not url:
                    raise RuntimeError("aucune poule trouvée")
                code = re.search(r"/competitions/([^/?]+)", url).group(1)
                if url in seen_urls:
                    print(f"[{n}/{len(teams)}] {tid} {code} : poule déjà traitée")
                    continue
                seen_urls.add(url)
                matches, meta = await scrape_poule(SITE + url)
                mine = [m for m in matches if CLUB_KEY in (m["equipe1"] + m["equipe2"]).upper()]
                new = [r for r in (to_row(m, code, meta) for m in mine) if r]
                if not new:
                    raise RuntimeError(f"aucun match du club dans {code}")
                for r in new:
                    rows[r["id"]] = r
                seen_comps[(code, new[0]["poule"])] = {r["id"] for r in new}
                print(f"[{n}/{len(teams)}] {tid} {code} {new[0]['categorie']} : "
                      f"{len(new)} matchs ({sum(r['domicile'] for r in new)} à domicile)")
            except Exception as e:  # une équipe en échec ne bloque pas les autres
                errors.append(f"{tid}: {e}")
                print(f"[{n}/{len(teams)}] {tid} ÉCHEC : {e}")
            await asyncio.sleep(PAUSE_ENTRE_EQUIPES)
    comps = [(c, p, ids) for (c, p), ids in seen_comps.items()]
    return list(rows.values()), comps, errors, len(teams)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    load_env()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    rows, comps, errors, n_teams = asyncio.run(scrape_all())
    print(f"\n{len(rows)} matchs, {n_teams - len(errors)}/{n_teams} équipes OK, {len(errors)} échec(s)")

    if args.dry_run:
        out = ROOT_DIR / "out"
        out.mkdir(exist_ok=True)
        (out / "matches.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"dry-run : {out / 'matches.json'}")
        return 1 if errors else 0

    url, key = load_supabase_config()
    if not key:
        print("SUPABASE_SERVICE_KEY manquante dans .env")
        return 1
    if not rows:
        print("aucun match récupéré : rien n'est écrit")
        return 1

    db = Supabase(url, key)
    db.upsert_matches(rows)
    # Matchs futurs connus mais disparus de la FFBB -> annulés (jamais supprimés)
    cancelled = []
    for code, poule, ids in comps:
        cancelled += sorted(db.future_ids(code, poule) - ids)
    db.mark_cancelled(cancelled)
    if cancelled:
        print(f"{len(cancelled)} match(s) marqué(s) annulé(s)")
    db.log(ok=not errors, equipes_total=n_teams, equipes_ok=n_teams - len(errors),
           matchs=len(rows), message="; ".join(errors)[:500] or None)
    print("envoi Supabase OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
