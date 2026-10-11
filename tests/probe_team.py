import asyncio, re, sys, aiohttp, html
sys.path.insert(0, r"C:\Users\utilisateur\Documents\Claude\Projects\FFBB_Agenda")
from scraper_http import SSL_CTX, HEADERS, _decode_next_f_script
CLUB = "https://competitions.ffbb.com/ligues/ges/comites/0057/clubs/ges0057030"
async def main():
    async with aiohttp.ClientSession() as s:
        for e in ['200000005337317','200000005350114']:
            async with s.get(f"{CLUB}/equipes/{e}", headers=HEADERS, ssl=SSL_CTX) as r:
                t = await r.text()
            open(f"tests/team_{e}.html","w",encoding="utf-8").write(t)
            print(e, "title:", re.findall(r"<title>(.*?)</title>", t)[:1])
            print(" h1:", [re.sub('<[^>]+>','',x) for x in re.findall(r"<h1.*?</h1>", t, re.S)][:2])
            hrefs = sorted(set(re.findall(r'href="([^"]*(?:competitions|poule|phase)[^"]*)"', t)))
            hrefs = [h for h in hrefs if 'ges0057030' in h or 'poule=' in h or 'phase=' in h]
            print(" liens:", hrefs[:10])
            ids = re.findall(r'"(?:poule_id|pouleId|poule)":"?(\d+)', t)[:5]
            print(" poule ids:", ids)
            print(" mots:", {k: len(re.findall(k, t)) for k in ['rencontres','Calendrier','Prochain','Classement','engagement','salle']})
asyncio.run(main())
