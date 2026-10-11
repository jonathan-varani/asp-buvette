import asyncio, re, sys, aiohttp
sys.path.insert(0, r"C:\Users\utilisateur\Documents\Claude\Projects\FFBB_Agenda")
from scraper_http import SSL_CTX, HEADERS
CLUB = "https://competitions.ffbb.com/ligues/ges/comites/0057/clubs/ges0057030"
async def get(s, u):
    async with s.get(u, headers=HEADERS, ssl=SSL_CTX) as r:
        return r.status, await r.text()
async def main():
    async with aiohttp.ClientSession() as s:
        st, h = await get(s, CLUB)
        print("club", st, len(h))
        eq = sorted(set(re.findall(r'/clubs/ges0057030/equipes/(\d+)', h)))
        print("equipes:", len(eq), eq)
        for e in eq[:3]:
            st, t = await get(s, f"{CLUB}/equipes/{e}")
            print(e, st, len(t), "CHALLENGE" if "bunny-shield" in t else "ok")
            print("  poules:", sorted(set(re.findall(r'competitions/[a-z0-9-]+\?phase=\d+&(?:amp;)?poule=\d+', t)))[:5])
            await asyncio.sleep(2)
asyncio.run(main())
