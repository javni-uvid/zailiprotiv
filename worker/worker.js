// Counts the votes visitors choose to send: from the quiz ("Glasaj i ti") and from each law's page.
//
// What is kept: for a vote from a law's page (or a quiz that sends a device mark), one row saying that a device
// voted this way on this law, so that a second vote from the same device replaces the first and does not add to it.
// The device is a random string the visitor's browser made up, kept here only as a hash with a secret (SALT). Beside
// it: the day, and a hash of the network the vote came from that changes every day (to see when one network sends
// most of a law's votes). No IP address, no cookie, no name. Older votes are three numbers per law and nothing else.
//
//   GET  /            → {"<law>": {"z": 12, "p": 30, "u": 2}, …}                 every law with votes
//   POST /            ← {"v": {"<law>": "z" | "p" | "u", …}, "d"?: "<device>"}   the quiz
//   GET  /z/<law>     → {"z": 12, "p": 30, "u": 2, "c": {"<quote>": 5, …}}       one law, and its marked quotes
//   POST /z           ← {"d": "<device>", "item": "<law>", "v": "z" | "p" | "u"} one vote, replacing the device's last
//   POST /c           ← {"d": "<device>", "item": "<law>", "q": "<quote>", "on": true | false}   mark a quote
//   POST /e           ← {"e": "kviz.kraj" | "listic.podeljeno" | …}               one use of the quiz or the ballot, counted
//   GET  /pregled     → what today's votes look like, law by law, for the watch against inflated counts, and the
//                       uses of the last two weeks by day
//   POST /p           ← {"endpoint": "<push address>", "cir": bool}   from the live page: notify this device when a
//                                                                     sitting's broadcast begins
//   POST /p/odjava    ← {"endpoint": "<push address>"}                no more notifications for it
//   POST /p/salji     ← {"od": <row>, "vrsta": "sednica"|"sazetak"}, with "authorization: Bearer <PUSH_TOKEN>"
//                       from the live service: send the day's notification of a sitting begun, or of the day's
//                       summary out (each once a day), a batch at a time; answers with where the next batch starts
//   POST /m/salji     ← {"poruke": [{"to", "subject", "html", "text", "odjava"}, …]}, with the token: from the live
//                       service, the day's summary by mail, up to 20 messages a call (sendMail)
//   POST /p/admin     ← {"endpoint"}, with the token: from the live service's /upozorenja (the maintainer's key):
//                       this device is told when "Ko sada govori" is down while a sitting is on; /p/admin/odjava
//   POST /p/vrsta     ← {"endpoint"}   from the page's service worker on a push: which notification it is
//   /m, /m/potvrdi, /m/odjava, /m/spisak: the day's summary by mail, who asked for it (mejl.js)
//
// Only laws (and quotes) the site itself lists are counted (glasanje.json, read from the site and kept for an hour),
// and one address can send only so often (Cloudflare's rate limiter; the address is not stored by us).
import * as mejl from "./mejl.js";

const SITE = "https://zailiprotiv.rs";
const LIVE = "https://mikrofon.zailiprotiv.rs";
// Mail goes out from the live page's own address (Cloudflare Email Service, the domain mikrofon.zailiprotiv.rs:
// the site's own domain keeps its mail at Loopia); answers go to the project's address.
const MAIL_FROM = { email: "sazetak@mikrofon.zailiprotiv.rs", name: "Za ili Protiv" };
const MAIL_REPLY = "kontakt@zailiprotiv.rs";
const MAIL_BATCH = 20;  // messages a call: each is a call of Cloudflare's, as each push is
const MAIL_TO = mejl.ADDRESS;

// One message to each address, made by the live service (`live/uzivo/mejl.py`): the subject, HTML and text as they
// are, and the address that unsubscribes this reader in one click (also as List-Unsubscribe, where mail readers put
// their own button). Answers what went and what did not, by its place in the batch, with Cloudflare's code.
async function sendMail(env, messages) {
  let sent = 0;
  const failed = [];
  for (const [i, m] of messages.entries()) {
    if (!m || typeof m.to !== "string" || !MAIL_TO.test(m.to) || typeof m.subject !== "string" || typeof m.html !== "string") {
      failed.push({ i, code: "poruka" });
      continue;
    }
    const msg = { from: MAIL_FROM, to: m.to, replyTo: MAIL_REPLY, subject: m.subject.slice(0, 300), html: m.html };
    if (typeof m.text === "string") msg.text = m.text;
    const out = typeof m.odjava === "string" && m.odjava.startsWith("https://") ? m.odjava : "";
    try {
      await env.MEJL.send(out ? { ...msg, headers: { "List-Unsubscribe": `<${out}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" } } : msg);
      sent++;
    } catch (e) {
      let err = e;
      if (out && String(e && e.code).startsWith("E_HEADER")) {  // the header not allowed: the link in the mail stays
        try { await env.MEJL.send(msg); sent++; continue; } catch (e2) { err = e2; }
      }
      failed.push({ i, code: String((err && err.code) || (err && err.name) || "greska") });
    }
  }
  return { poslato: sent, greske: failed };
}
let laws = { at: 0, map: new Map() };  // law → the quotes of its page that may be marked

async function allowed() {
  if (Date.now() - laws.at > 3600e3 || !laws.map.size) {
    let map = null;
    const r = await fetch(SITE + "/glasanje.json", { cf: { cacheTtl: 600 } });
    if (r.ok) map = new Map(Object.entries((await r.json()).laws));
    else {  // the site before it listed every law: the quiz's laws
      const old = await fetch(SITE + "/glasaj.json", { cf: { cacheTtl: 600 } });
      if (old.ok) map = new Map((await old.json()).laws.map((l) => [l, []]));
    }
    if (map) laws = { at: Date.now(), map };
  }
  return laws.map;
}

// What the quiz and the ballot count when it happens (a sum per day, nothing with it): the quiz's result shown, and
// for each picture to share, opened, the share sheet opened, shared, the text copied, the picture saved.
const EVENTS = new Set(["kviz.kraj", "kviz.podeli", "kviz.podeljeno", "kviz.kopiraj", "kviz.sacuvaj",
  "listic.otvori", "listic.podeli", "listic.podeljeno", "listic.kopiraj", "listic.sacuvaj",
  // the live page (mikrofon.zailiprotiv.rs): its ▶ on the broadcast pressed
  "mikrofon.pusti",
  // and, each at most once per page opened: the page opened; in view after 1, 5, 15, 30 minutes (time out of sight
  // not counted); a recording of the archive played; the agenda, the speaker's lines, a share of the moment or of
  // the day, the day in cards opened; a way to the site taken
  "mikrofon.otvori", "mikrofon.1min", "mikrofon.5min", "mikrofon.15min", "mikrofon.30min", "mikrofon.snimak",
  "mikrofon.tacke", "mikrofon.redovi", "mikrofon.podeli", "mikrofon.dan", "mikrofon.kartice", "mikrofon.sajt",
  // the page put on the phone's home screen (20 Nov 2026): opened from there, "add" pressed, added; the next
  // sitting's agenda opened in the countdown
  "mikrofon.ekran", "mikrofon.dodaj", "mikrofon.dodato", "mikrofon.sledeca",
  // notifications turned on and off (the addresses themselves are in the table `push`)
  "mikrofon.obavesti", "mikrofon.odjavi",
  // a sign-up for the day's summary by mail sent from the page (23 Nov 2026; the addresses are in the table `mejl`)
  "mikrofon.mejl",
  // the site's search (20 Nov 2026, to learn whether a search by meaning is worth building): a search run, a search
  // that found nothing, a result opened. Never the words searched for.
  "pretraga.trazi", "pretraga.prazno", "pretraga.klik",
  // the field on the home page and "Poslanici" (names and titles): typed in, nothing found, a name or title taken,
  // the whole text's search taken (20 Nov 2026)
  "pretraga.polje", "pretraga.polje-nema", "pretraga.polje-izbor", "pretraga.polje-ceo",
  // a recording played on the site's day page; a way taken from the site to the live page (20 Nov 2026)
  "sajt.snimak", "sajt.mikrofon",
  // the notification's offer on the live page: shown, pressed, refused at the browser's question, failed (20 Nov 2026)
  "mikrofon.obavesti-moze", "mikrofon.obavesti-klik", "mikrofon.obavesti-odbijeno", "mikrofon.obavesti-greska",
  // the way to the live page by where it was taken: the menu, the home page's strip, the announcement before a
  // sitting, the bar of a sitting, an MP at the rostrum (22 Nov 2026)
  "sajt.mikrofon-meni", "sajt.mikrofon-pocetna", "sajt.mikrofon-najava", "sajt.mikrofon-traka",
  "sajt.mikrofon-poslanik"]);

const DEVICE = /^[A-Za-z0-9_-]{16,64}$/;
async function hash(text) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
const today = () => new Date().toISOString().slice(0, 10);
// The network a request came from, coarsely (an IPv4 /24, an IPv6 /64), hashed with the secret and the day: the
// same network gives the same mark within a day and another one the next.
async function network(request, env, day) {
  const ip = request.headers.get("cf-connecting-ip") || "";
  const net = ip.includes(":") ? ip.split(":").slice(0, 4).join(":") : ip.split(".").slice(0, 3).join(".");
  return (await hash(env.SALT + "|" + day + "|" + net)).slice(0, 16);
}

// One law: the older counts and the devices' votes together, and how many devices marked each quote.
async function one(env, item) {
  const out = { z: 0, p: 0, u: 0, c: {} };
  const [old, now, marks] = await env.DB.batch([
    env.DB.prepare("SELECT vote, n FROM votes WHERE law = ?").bind(item),
    env.DB.prepare("SELECT vote, n FROM tally WHERE item = ?").bind(item),
    env.DB.prepare("SELECT quote, COUNT(*) AS n FROM marks WHERE item = ? GROUP BY quote").bind(item)]);
  for (const r of old.results.concat(now.results)) if (r.vote in out) out[r.vote] += r.n;
  for (const r of marks.results) out.c[r.quote] = r.n;
  return out;
}

// For the watch: every law voted on today, with how many of today's votes came from the busiest network, and how
// many devices sent many votes today. Numbers only.
async function overview(env) {
  const day = today();
  const [items, nets, busy, used] = await env.DB.batch([
    env.DB.prepare("SELECT item, COUNT(*) AS total, SUM(day = ?1) AS today FROM ballots GROUP BY item HAVING today > 0").bind(day),
    env.DB.prepare("SELECT item, net, COUNT(*) AS n FROM ballots WHERE day = ?1 GROUP BY item, net").bind(day),
    env.DB.prepare("SELECT COUNT(*) AS n FROM (SELECT device FROM ballots WHERE day = ?1 GROUP BY device HAVING COUNT(*) > 60)").bind(day),
    env.DB.prepare("SELECT day, what, n FROM events WHERE day >= ?1 ORDER BY day DESC, what").bind(new Date(Date.now() - 13 * 864e5).toISOString().slice(0, 10))]);
  const top = {};
  for (const r of nets.results) top[r.item] = Math.max(top[r.item] || 0, r.n);
  const uses = {};
  for (const r of used.results) (uses[r.day] = uses[r.day] || {})[r.what] = r.n;
  const push = await env.DB.batch([env.DB.prepare("SELECT COUNT(*) AS n FROM push"),
    env.DB.prepare("SELECT day, sent, gone FROM push_days ORDER BY day DESC LIMIT 14")]);
  return { day, devices_with_many_votes: busy.results[0].n, uses,
           push: { devices: push[0].results[0].n, sent: push[1].results }, mejl: await mejl.count(env),
           laws: items.results.map((r) => ({ item: r.item, total: r.total, today: r.today, busiest_network: top[r.item] || 0 }))
             .sort((a, b) => b.today - a.today).slice(0, 200) };
}

// Every law's totals: the older sums and the devices' votes (`tally`, kept by triggers on `ballots`). Every page of
// the quiz asks for them, and each law answered sends a vote that answers with them, so they are kept here a minute
// (in this copy of the worker) and only the laws just voted on are read again.
let kept = { at: 0, data: null };
function add(out, rows) {
  for (const r of rows) {
    const t = out[r.law] = out[r.law] || { z: 0, p: 0, u: 0 };
    if (r.vote in t) t[r.vote] += r.n;
  }
  return out;
}
async function totals(env, laws) {
  if (!kept.data || Date.now() - kept.at > 60e3) {
    const [old, now] = await env.DB.batch([env.DB.prepare("SELECT law, vote, n FROM votes"),
      env.DB.prepare("SELECT item AS law, vote, n FROM tally")]);
    kept = { at: Date.now(), data: add({}, old.results.concat(now.results)) };
    return kept.data;
  }
  if (!laws || !laws.length) return kept.data;
  const marks = laws.map(() => "?").join(", ");
  const [old, now] = await env.DB.batch([
    env.DB.prepare(`SELECT law, vote, n FROM votes WHERE law IN (${marks})`).bind(...laws),
    env.DB.prepare(`SELECT item AS law, vote, n FROM tally WHERE item IN (${marks})`).bind(...laws)]);
  const fresh = add({}, old.results.concat(now.results));
  for (const law of laws) kept.data[law] = fresh[law] || { z: 0, p: 0, u: 0 };
  return kept.data;
}

function reply(body, status, origin, keep) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: {
    "content-type": "application/json; charset=utf-8", "cache-control": keep ? "public, max-age=" + keep : "no-store",
    "access-control-allow-origin": origin, "access-control-allow-methods": "GET, POST, OPTIONS",
    "access-control-allow-headers": "content-type", "vary": "origin" } });
}

// The clock: start a workflow of the repository through GitHub's API. Needs the secret DISPATCH_TOKEN (a GitHub
// token allowed to run this repository's Actions, nothing else).
const REPO = "javni-uvid/zailiprotiv";
async function dispatch(env, workflow, inputs) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
    method: "POST",
    headers: { "authorization": `Bearer ${env.DISPATCH_TOKEN}`, "accept": "application/vnd.github+json",
               "user-agent": "zailiprotiv-glasovi", "content-type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs }),
  });
  if (!r.ok) throw new Error(`${workflow}: GitHub answered ${r.status} ${await r.text()}`);
}

// Notifications from the live page (20 Nov 2026, the maintainer's decision; an exception to principle 5, as the
// browser's own push service carries them). A push with no content: the page's service worker writes the
// notification itself, so nothing is encrypted and nothing about the sitting passes through the push service. Signed
// with the project's VAPID key (the secret VAPID_JWK; its public half is `push_key` in data/settings.json).
const PUSH_HOSTS = /^https:\/\/([a-z0-9-]+\.)*(fcm\.googleapis\.com|push\.services\.mozilla\.com|push\.apple\.com|notify\.windows\.com)\/\S{8,900}$/;
const PUSH_BATCH = 30;  // the free plan's 50 requests out per call, less the database's
const b64u = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
// The key and each push service's header are kept as promises: the 30 sends of a batch run at once, and each used
// to import the key and sign anew before the first had finished (the free plan's 10 ms of CPU a call).
let vapid = null;
async function authorization(env, endpoint) {
  if (!vapid) {
    vapid = (async () => {
      const jwk = JSON.parse(env.VAPID_JWK);
      const key = await crypto.subtle.importKey("jwk", { kty: "EC", crv: "P-256", x: jwk.x, y: jwk.y, d: jwk.d },
        { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
      const pub = new Uint8Array(65);
      pub[0] = 4; pub.set(unb64u(jwk.x), 1); pub.set(unb64u(jwk.y), 33);
      return { key, pub: b64u(pub), kept: new Map() };
    })();
    vapid.catch(() => { vapid = null; });
  }
  const v = await vapid;
  const aud = new URL(endpoint).origin, now = Math.floor(Date.now() / 1000), kept = v.kept.get(aud);
  if (kept && kept.exp - now > 3600) return kept.h;
  const exp = now + 12 * 3600, text = (o) => b64u(new TextEncoder().encode(JSON.stringify(o)));
  const head = text({ typ: "JWT", alg: "ES256" }) + "." + text({ aud, exp, sub: "mailto:kontakt@zailiprotiv.rs" });
  const h = crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, v.key, new TextEncoder().encode(head))
    .then((sig) => `vapid t=${head}.${b64u(sig)}, k=${v.pub}`);
  v.kept.set(aud, { exp, h });
  h.catch(() => v.kept.delete(aud));
  return h;
}
async function sendPush(env, from, what = "sednica") {
  // the sitting's beginning and the day's summary (20 Nov 2026), each once a day; the summary's day kept as "s:<day>"
  const day = (what === "sazetak" ? "s:" : "") + today();
  if (!from) {  // the first batch: once a day, whatever the live service asks
    const r = await env.DB.prepare("INSERT OR IGNORE INTO push_days (day) VALUES (?)").bind(day).run();
    if (!r.meta.changes) return { day, already: true, next: null };
    await watchSet(env, "poslato", { t: Date.now(), vrsta: what });  // what a service worker asking now was sent (kind)
  }
  const rows = (await env.DB.prepare("SELECT rowid AS id, endpoint FROM push WHERE rowid > ? ORDER BY rowid LIMIT ?")
    .bind(from || 0, PUSH_BATCH).all()).results;
  let sent = 0;
  const gone = [];
  await Promise.all(rows.map(async (r) => {
    try {
      const res = await fetch(r.endpoint, { method: "POST", headers: {
        authorization: await authorization(env, r.endpoint), ttl: "3600", urgency: "high", "content-length": "0" } });
      if (res.status === 404 || res.status === 410) gone.push(r.endpoint);  // the device unsubscribed: forgotten
      else if (res.ok) sent++;
    } catch (e) { /* tried again never: one notification a day */ }
  }));
  const writes = gone.map((e) => env.DB.prepare("DELETE FROM push WHERE endpoint = ?").bind(e));
  writes.push(env.DB.prepare("UPDATE push_days SET sent = sent + ?, gone = gone + ? WHERE day = ?").bind(sent, gone.length, day));
  await env.DB.batch(writes);
  return { day, sent, gone: gone.length, next: rows.length === PUSH_BATCH ? rows[rows.length - 1].id : null };
}
// The watch over "Ko sada govori" (20 Nov 2026, the maintainer's request): every five minutes of a weekday's working
// hours the service is asked for its state; when it doesn't answer, the Assembly's listings are read (at most once
// in half an hour) for a sitting marked "(у току)"; down through two checks while one is on, the maintainer's
// devices get one notification, and another when it answers again. The Assembly marks a sitting of several days
// "in progress" on its days off too, so a computer turned off on such a day is told about as well.
const LISTINGS = ["https://www.parlament.gov.rs/активности/народна-скупштина/заседања/редовна.34.html",
  "https://www.parlament.gov.rs/активности/народна-скупштина/заседања/ванредна.35.html"];
const DOWN_AFTER = 4 * 60e3;  // the second check in a row that finds it down (five minutes apart)
async function watchGet(env, k) {
  const r = await env.DB.prepare("SELECT v FROM watch WHERE k = ?").bind(k).first();
  return r ? JSON.parse(r.v) : null;
}
async function watchSet(env, k, v) {
  if (v === null) await env.DB.prepare("DELETE FROM watch WHERE k = ?").bind(k).run();
  else await env.DB.prepare("INSERT INTO watch (k, v) VALUES (?, ?) ON CONFLICT (k) DO UPDATE SET v = excluded.v").bind(k, JSON.stringify(v)).run();
}
async function answers() {  // the service itself, not the edge's copy of its last answer
  try {
    const r = await fetch(LIVE + "/stanje.json", { cf: { cacheTtl: 0 } });
    return r.status === 200 && !r.headers.get("x-mikrofon") && "stanje" in (await r.json());
  } catch (e) { return false; }
}
async function sitting(env) {
  const last = await watchGet(env, "sednica");
  if (last && Date.now() - last.t < 30 * 60e3) return last.on;
  let on = false;
  for (const url of LISTINGS) {
    try {
      const r = await fetch(encodeURI(url), { headers: { "user-agent": "zailiprotiv/0.1 (+https://github.com/javni-uvid/zailiprotiv)" } });
      if (r.ok && />[^<]*седниц[^<]*\(у току\)/i.test(await r.text())) on = true;
    } catch (e) { /* unreadable: not taken as a sitting */ }
    if (on) break;
  }
  await watchSet(env, "sednica", { t: Date.now(), on });
  return on;
}
async function tellAdmins(env, what, minutes) {
  await watchSet(env, "admin", { vrsta: what, min: minutes, t: Date.now() });
  const rows = (await env.DB.prepare("SELECT endpoint FROM push_admin LIMIT 20").all()).results;
  await Promise.all(rows.map(async (r) => {
    try {
      const res = await fetch(r.endpoint, { method: "POST", headers: {
        authorization: await authorization(env, r.endpoint), ttl: "1800", urgency: "high", "content-length": "0" } });
      if (res.status === 404 || res.status === 410) await env.DB.prepare("DELETE FROM push_admin WHERE endpoint = ?").bind(r.endpoint).run();
    } catch (e) {}
  }));
}
async function watch(env) {
  if (!env.VAPID_JWK) return;
  const down = await watchGet(env, "kvar"), now = Date.now();
  if (await answers()) {
    if (down) {
      if (down.told) await tellAdmins(env, "oporavak", Math.round((now - down.od) / 60e3));
      await watchSet(env, "kvar", null);
    }
    return;
  }
  if (!(await sitting(env))) { if (down) await watchSet(env, "kvar", null); return; }
  if (!down) { await watchSet(env, "kvar", { od: now, told: false }); return; }
  if (!down.told && now - down.od >= DOWN_AFTER) {
    await tellAdmins(env, "kvar", Math.round((now - down.od) / 60e3));
    await watchSet(env, "kvar", { ...down, told: true });
  }
}
// Which notification a push was, asked by the service worker that got it (a push carries nothing): for the
// maintainer's devices, the watch's last one if newer than the day's notification of a sitting and under ten
// minutes old; for everyone else always the sitting's.
async function kind(env, endpoint) {
  const admin = await env.DB.prepare("SELECT 1 AS x FROM push_admin WHERE endpoint = ?").bind(endpoint || "").first();
  const day = await watchGet(env, "poslato"), sent = { vrsta: (day && day.vrsta) || "sednica" };
  if (!admin) return sent;
  const last = await watchGet(env, "admin");
  if (last && Date.now() - last.t < 10 * 60e3 && (!day || last.t > day.t)) return { vrsta: last.vrsta, min: last.min };
  return sent;
}

async function same(a, b) {  // the token compared by its hash, so the time taken says nothing of it
  return (await hash(a)) === (await hash(b));
}

export default {
  async scheduled(event, env) {
    if (event.cron === "*/5 6-19 * * 1-5") return watch(env);
    if (event.cron === "47 5-21 * * *") await mejl.cleanup(env);  // sign-ups not confirmed in 48 hours
    if (!env.DISPATCH_TOKEN) return;
    if (event.cron === "53 */6 * * *") await dispatch(env, "summaries.yml", {});
    else await dispatch(env, "votes.yml", { convocation: "14", scheduled: "true" });
  },

  async fetch(request, env, ctx) {
    const from = request.headers.get("origin") || "";
    const origin = SITE;  // CORS names the site only; a POST from any other page is refused below
    const path = new URL(request.url).pathname;
    if (request.method === "OPTIONS") return reply({}, 204, origin);
    if (path === "/m" || (path.startsWith("/m/") && path !== "/m/salji")) {
      const res = await mejl.handle(request, env, path, from, same);
      if (res) return res;
    }
    if (request.method === "GET") {
      if (path === "/pregled") return reply(await overview(env), 200, origin, 300);
      if (path.startsWith("/z/")) {
        const item = decodeURIComponent(path.slice(3));
        return (await allowed()).has(item) ? reply(await one(env, item), 200, origin, 30) : reply({ error: "item" }, 404, origin);
      }
      // the same for everyone: Cloudflare's cache at the edge answers for a minute
      const cache = caches.default, key = new Request(new URL("/", request.url).toString());
      const hit = await cache.match(key);
      if (hit) return hit;
      const res = reply(await totals(env), 200, origin, 60);
      ctx.waitUntil(cache.put(key, res.clone()));
      return res;
    }
    if (request.method !== "POST") return reply({ error: "method" }, 405, origin);
    if (path === "/p/salji") {  // the live service, with its token
      const auth = request.headers.get("authorization") || "";
      if (!env.PUSH_TOKEN || !env.VAPID_JWK || !(await same(auth, "Bearer " + env.PUSH_TOKEN))) return reply({ error: "token" }, 403, origin);
      let od = 0, what = "sednica";
      try {
        const b = JSON.parse(await request.text());
        od = Math.max(0, parseInt(b.od, 10) || 0);
        if (b.vrsta === "sazetak") what = "sazetak";
      } catch (e) { od = 0; }
      return reply(await sendPush(env, od, what), 200, origin);
    }
    if (path === "/m/salji") {  // the live service, with its token: mail it made, sent as it is
      const auth = request.headers.get("authorization") || "";
      if (!env.PUSH_TOKEN || !env.MEJL || !(await same(auth, "Bearer " + env.PUSH_TOKEN))) return reply({ error: "token" }, 403, origin);
      let b;
      try { b = JSON.parse((await request.text()).slice(0, 4e6)) || {}; } catch (e) { return reply({ error: "json" }, 400, origin); }
      return reply(await sendMail(env, Array.isArray(b.poruke) ? b.poruke.slice(0, MAIL_BATCH) : []), 200, origin);
    }
    if (path === "/p/admin" || path === "/p/admin/odjava") {  // the live service, for the maintainer's key
      const auth = request.headers.get("authorization") || "";
      if (!env.PUSH_TOKEN || !(await same(auth, "Bearer " + env.PUSH_TOKEN))) return reply({ error: "token" }, 403, origin);
      let b;
      try { b = JSON.parse((await request.text()).slice(0, 2000)) || {}; } catch (e) { return reply({ error: "json" }, 400, origin); }
      if (typeof b.endpoint !== "string" || !PUSH_HOSTS.test(b.endpoint)) return reply({ error: "endpoint" }, 400, origin);
      if (path === "/p/admin/odjava") await env.DB.prepare("DELETE FROM push_admin WHERE endpoint = ?").bind(b.endpoint).run();
      else await env.DB.prepare("INSERT OR IGNORE INTO push_admin (endpoint, day) VALUES (?, ?)").bind(b.endpoint, today()).run();
      return reply({ ok: true }, 200, origin);
    }
    if (path === "/p/vrsta") {  // the page's service worker, on a push
      if (from !== LIVE) return reply({ error: "origin" }, 403, LIVE);
      let b = {};
      try { b = JSON.parse((await request.text()).slice(0, 2000)) || {}; } catch (e) { b = {}; }
      return reply(await kind(env, typeof b.endpoint === "string" ? b.endpoint : ""), 200, LIVE);
    }
    if (path === "/p" || path === "/p/odjava") {  // the live page only; its script reads the answer
      if (from !== LIVE) return reply({ error: "origin" }, 403, LIVE);
      if (env.LIMIT) {
        const { success } = await env.LIMIT.limit({ key: request.headers.get("cf-connecting-ip") || "x" });
        if (!success) return reply({ error: "limit" }, 429, LIVE);
      }
      let b;
      try { b = JSON.parse((await request.text()).slice(0, 2000)) || {}; } catch (e) { return reply({ error: "json" }, 400, LIVE); }
      if (typeof b.endpoint !== "string" || !PUSH_HOSTS.test(b.endpoint)) return reply({ error: "endpoint" }, 400, LIVE);
      if (path === "/p/odjava") await env.DB.prepare("DELETE FROM push WHERE endpoint = ?").bind(b.endpoint).run();
      else await env.DB.prepare("INSERT INTO push (endpoint, cir, day) VALUES (?, ?, ?) ON CONFLICT (endpoint) DO UPDATE SET cir = excluded.cir")
        .bind(b.endpoint, b.cir ? 1 : 0, today()).run();
      return reply({ ok: true }, 200, LIVE);
    }
    const uses = path === "/e" && from === LIVE;  // the live page may only add to the sums of uses
    if (from !== origin && !uses) return reply({ error: "origin" }, 403, origin);
    const single = path === "/z" || path === "/c" || path === "/e";
    const limiter = single ? env.VLIMIT : env.LIMIT;
    if (limiter) {
      const { success } = await limiter.limit({ key: request.headers.get("cf-connecting-ip") || "x" });
      if (!success) return reply({ error: "limit" }, 429, origin);
    }
    let body;
    try { body = JSON.parse((await request.text()).slice(0, 8000)); } catch (e) { return reply({ error: "json" }, 400, origin); }
    body = body || {};
    if (path === "/e") {
      if (!EVENTS.has(body.e) || (uses && !body.e.startsWith("mikrofon."))) return reply({ error: "event" }, 400, origin);
      await env.DB.prepare("INSERT INTO events (day, what, n) VALUES (?, ?, 1) ON CONFLICT (day, what) DO UPDATE SET n = n + 1")
        .bind(today(), body.e).run();
      return reply({}, 204, origin);
    }
    const known = await allowed(), day = today();
    const device = typeof body.d === "string" && DEVICE.test(body.d) && env.SALT ? (await hash(env.SALT + "|" + body.d)).slice(0, 32) : null;
    if (single) {
      if (!env.SALT) return reply({ error: "not ready" }, 503, origin);
      if (!device || !known.has(body.item)) return reply({ error: "bad" }, 400, origin);
      if (path === "/z") {
        if (!["z", "p", "u"].includes(body.v)) return reply({ error: "vote" }, 400, origin);
        await env.DB.prepare("INSERT INTO ballots (item, device, vote, day, net) VALUES (?, ?, ?, ?, ?) " +
          "ON CONFLICT (item, device) DO UPDATE SET vote = excluded.vote, day = excluded.day, net = excluded.net")
          .bind(body.item, device, body.v, day, await network(request, env, day)).run();
      } else {
        if (!known.get(body.item).includes(body.q)) return reply({ error: "quote" }, 400, origin);
        if (body.on === false) await env.DB.prepare("DELETE FROM marks WHERE item = ? AND quote = ? AND device = ?").bind(body.item, body.q, device).run();
        else await env.DB.prepare("INSERT OR IGNORE INTO marks (item, quote, device, day) VALUES (?, ?, ?, ?)").bind(body.item, body.q, device, day).run();
      }
      return reply(await one(env, body.item), 200, origin);
    }
    // The quiz: several laws at once. With a device mark each is that device's vote on the law (replacing its
    // last); without one (pages opened before the marks) it adds to the older counts.
    const votes = Object.entries(body.v || {}).filter(([law, v]) => known.has(law) && ["z", "p", "u"].includes(v)).slice(0, 30);
    if (!votes.length) return reply({ error: "empty" }, 400, origin);
    if (device) {
      const net = await network(request, env, day);
      await env.DB.batch(votes.map(([law, v]) => env.DB.prepare(
        "INSERT INTO ballots (item, device, vote, day, net) VALUES (?, ?, ?, ?, ?) " +
        "ON CONFLICT (item, device) DO UPDATE SET vote = excluded.vote, day = excluded.day, net = excluded.net").bind(law, device, v, day, net)));
    } else {
      await env.DB.batch(votes.map(([law, v]) => env.DB.prepare(
        "INSERT INTO votes (law, vote, n) VALUES (?, ?, 1) ON CONFLICT (law, vote) DO UPDATE SET n = n + 1").bind(law, v)));
    }
    return reply(await totals(env, votes.map(([law]) => law)), 200, origin);
  },
};
