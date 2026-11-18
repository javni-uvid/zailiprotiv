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
//
// Only laws (and quotes) the site itself lists are counted (glasanje.json, read from the site and kept for an hour),
// and one address can send only so often (Cloudflare's rate limiter; the address is not stored by us).
const SITE = "https://zailiprotiv.rs";
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
  "listic.otvori", "listic.podeli", "listic.podeljeno", "listic.kopiraj", "listic.sacuvaj"]);

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
  return { day, devices_with_many_votes: busy.results[0].n, uses,
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

export default {
  async scheduled(event, env) {
    if (!env.DISPATCH_TOKEN) return;
    if (event.cron === "53 */6 * * *") await dispatch(env, "summaries.yml", {});
    else await dispatch(env, "votes.yml", { convocation: "14", scheduled: "true" });
  },

  async fetch(request, env, ctx) {
    const from = request.headers.get("origin") || "";
    const origin = SITE;  // CORS names the site only; a POST from any other page is refused below
    const path = new URL(request.url).pathname;
    if (request.method === "OPTIONS") return reply({}, 204, origin);
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
    if (from !== origin) return reply({ error: "origin" }, 403, origin);
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
      if (!EVENTS.has(body.e)) return reply({ error: "event" }, 400, origin);
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
