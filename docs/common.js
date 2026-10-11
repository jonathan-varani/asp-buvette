// Config publique (URL + clé « publishable » : lecture seule, protégée par RLS)
const SB_URL = "https://hlflcoayqomeqoodruyz.supabase.co";
const SB_KEY = "sb_publishable_Mle_5VNv7_8l4_g2OJoXvw_Hr4Kg1qJ";
const CLUB_KEY = "STE MARIE AUX CHENES";

const H = { apikey: SB_KEY, Authorization: "Bearer " + SB_KEY, "Content-Type": "application/json" };

async function sbGet(path) {
  const r = await fetch(SB_URL + "/rest/v1/" + path, { headers: H });
  if (!r.ok) throw new Error("Lecture impossible (" + r.status + ")");
  return r.json();
}
async function sbRpc(fn, body) {
  const r = await fetch(SB_URL + "/rest/v1/rpc/" + fn, { method: "POST", headers: H, body: JSON.stringify(body) });
  if (!r.ok) {
    let msg = "Erreur " + r.status;
    try { msg = (await r.json()).message || msg; } catch (e) {}
    throw new Error(msg);
  }
  const t = await r.text();
  return t ? JSON.parse(t) : null;
}

// ── Dates (semaine lundi → dimanche, en local) ──
const iso = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
const parseIso = s => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
function mondayOf(d) { const x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; }
function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
const fmt = (d, o) => d.toLocaleDateString("fr-FR", o);
function weekTitle(mon) {
  const sat = addDays(mon, 5), sun = addDays(mon, 6);
  const same = sat.getMonth() === sun.getMonth();
  const t = same
    ? sat.getDate() + "–" + sun.getDate() + " " + fmt(sun, { month: "long", year: "numeric" })
    : sat.getDate() + " " + fmt(sat, { month: "short" }) + " – " + sun.getDate() + " " + fmt(sun, { month: "short", year: "numeric" });
  return { main: "Weekend du " + t, sub: "" };
}

// ── Affichage ──
const SMALL = new Set(["de", "du", "des", "la", "le", "les", "et", "en", "aux", "au", "sur", "sous", "d", "l"]);
function pretty(name) {
  return name.toLowerCase().replace(/([a-zàâäéèêëïîôöùûüç']+)/g, (w, _, i) =>
    (i > 0 && SMALL.has(w)) ? w : w.charAt(0).toUpperCase() + w.slice(1))
    .replace(/\bAsp\b/, "ASP").replace(/\bChenes\b/, "Chênes").replace(/\b(Bc|Bb|Cs|Us|Sluc|Dbrk|Cse|Ie|Ctc)\b/g, m => m.toUpperCase());
}
const isClub = n => n.toUpperCase().includes(CLUB_KEY);
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function teamsLine(m) {
  const p = el("div", "teams");
  const a = el("span", isClub(m.equipe1) ? "club" : "", pretty(m.equipe1));
  const b = el("span", isClub(m.equipe2) ? "club" : "", pretty(m.equipe2));
  p.append(a, el("span", "vs", "contre"), b);
  if (m.joue && m.score1 != null) p.append(el("span", "score", m.score1 + " – " + m.score2));
  return p;
}
function matchCard(m, extra) {
  const c = el("article", "match" + (m.domicile ? " home" : "") + (m.statut === "annule" ? " cancel" : ""));
  const r = el("div", "row1");
  r.append(el("span", "time", m.heure ? m.heure.slice(0, 5) : "Heure à confirmer"));
  r.append(el("span", "badge", m.categorie || ""));
  r.append(el("span", "badge " + (m.domicile ? "home" : "away"), m.domicile ? "Domicile" : "Extérieur"));
  if (m.amical) r.append(el("span", "badge amical", "Amical"));
  if (m.statut === "annule") r.append(el("span", "badge cancel", "Annulé / retiré"));
  c.append(r, teamsLine(m));
  if (m.salle) c.append(el("div", "salle", "📍 " + pretty(m.salle)));
  if (extra) c.append(extra);
  return c;
}
function groupByDay(matches) {
  const g = new Map();
  for (const m of matches) { if (!g.has(m.date)) g.set(m.date, []); g.get(m.date).push(m); }
  return g;
}
function dayHeading(isoDate) {
  return el("h2", "day", fmt(parseIso(isoDate), { weekday: "long", day: "numeric", month: "long" }));
}
async function loadWeek(mon, withBuvette) {
  const from = iso(mon), to = iso(addDays(mon, 6));
  const sel = withBuvette ? "*,buvette(prenom,nom)" : "*";
  return sbGet("matches?select=" + encodeURIComponent(sel) + "&date=gte." + from + "&date=lte." + to + "&order=date.asc,heure.asc.nullsfirst");
}
function buvetteOf(m) { const b = m.buvette; return Array.isArray(b) ? b[0] : b; }
function queryWeek() {
  const p = new URLSearchParams(location.search).get("s");
  return p && /^\d{4}-\d{2}-\d{2}$/.test(p) ? mondayOf(parseIso(p)) : mondayOf(new Date());
}
function setQueryWeek(mon) {
  const u = new URL(location.href);
  if (iso(mon) === iso(mondayOf(new Date()))) u.searchParams.delete("s"); else u.searchParams.set("s", iso(mon));
  history.replaceState(null, "", u);
}
