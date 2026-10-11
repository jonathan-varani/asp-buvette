import asyncio, re, sys, json, html, aiohttp
sys.path.insert(0, r"C:\Users\utilisateur\Documents\Claude\Projects\FFBB_Agenda")
import scraper_http
from scraper_http import SSL_CTX, HEADERS, scrape_poule
scraper_http.MAX_CONCURRENT = 2
ROOT = "https://competitions.ffbb.com"
CLUB = ROOT + "/ligues/ges/comites/0057/clubs/ges0057030"
KEY = "STE MARIE AUX CHENES"
async def main():
    async with aiohttp.ClientSession() as s:
        async with s.get(CLUB, headers=HEADERS, ssl=SSL_CTX) as r: h = await r.text()
        eqs = sorted(set(re.findall(r'/clubs/ges0057030/equipes/(\d+)', h)))
        teams = []
        for e in eqs:
            async with s.get(f"{CLUB}/equipes/{e}", headers=HEADERS, ssl=SSL_CTX) as r: t = await r.text()
            name = re.findall(r"<h1.*?</h1>", t, re.S)
            name = re.sub('<[^>]+>','',name[0]) if name else "?"
            comp = re.findall(r'href="(/ligues/[^"]*competitions/[^"]*poule=\d+[^"]*)"', t)
            title = html.unescape(re.findall(r"<title>(.*?)</title>", t)[0])
            teams.append((e, name, title, html.unescape(comp[0]) if comp else None))
            await asyncio.sleep(1.5)
    out = []
    for e, name, title, url in teams:
        print(f"\n[{e}] {name} | {title}\n   {url}")
        if not url: print("   !! pas de poule"); continue
        try:
            ms, meta = await scrape_poule(ROOT + url)
        except Exception as ex:
            print("   !! erreur", ex); continue
        mine = [m for m in ms if KEY in (m['equipe1']+m['equipe2']).upper()]
        home = [m for m in mine if KEY in m['equipe1'].upper()]
        print(f"   poule={len(ms)} matchs, club={len(mine)}, domicile={len(home)}, meta={ {k: meta.get(k) for k in ('titre','poule')} }")
        for m in sorted(mine, key=lambda m: m['date'])[:3]:
            print("     ", m['date'], m['heure'], m['equipe1'], 'vs', m['equipe2'], '|', m['salle'], '|', m['match_url'][-60:])
        out.append({"equipe_id": e, "name": name, "url": url, "matches": mine})
    json.dump(out, open("tests/probe_result.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
asyncio.run(main())
