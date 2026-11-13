// Counts the votes visitors choose to send from "Glasaj i ti". It keeps three numbers per law and nothing else:
// no cookies, no IP addresses, no record of who voted or when.
//
//   GET  /        → {"<law>": {"z": 12, "p": 30, "u": 2}, …}
//   POST /        ← {"v": {"<law>": "z" | "p" | "u", …}}   → the totals, as GET
//
// Only laws the site's own page lists are counted (its list is read from the site and kept for an hour), and one
// address can send a few times an hour (Cloudflare's rate limiter; the address is not stored by us).
const SITE = "https://zailiprotiv.rs";
let laws = { at: 0, set: new Set() };

async function allowed() {
  if (Date.now() - laws.at > 3600e3 || !laws.set.size) {
    const r = await fetch(SITE + "/glasaj.json", { cf: { cacheTtl: 600 } });
    if (r.ok) laws = { at: Date.now(), set: new Set((await r.json()).laws) };
  }
  return laws.set;
}

async function totals(env) {
  const out = {};
  const rows = await env.DB.prepare("SELECT law, vote, n FROM votes").all();
  for (const r of rows.results) (out[r.law] = out[r.law] || { z: 0, p: 0, u: 0 })[r.vote] = r.n;
  return out;
}

function reply(body, status, origin) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: {
    "content-type": "application/json; charset=utf-8", "cache-control": "no-store",
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

  async fetch(request, env) {
    const from = request.headers.get("origin") || "";
    const origin = from === SITE || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(from) ? from : SITE;
    if (request.method === "OPTIONS") return reply({}, 204, origin);
    if (request.method === "GET") return reply(await totals(env), 200, origin);
    if (request.method !== "POST") return reply({ error: "method" }, 405, origin);
    if (from !== origin) return reply({ error: "origin" }, 403, origin);
    if (env.LIMIT) {
      const { success } = await env.LIMIT.limit({ key: request.headers.get("cf-connecting-ip") || "x" });
      if (!success) return reply({ error: "limit" }, 429, origin);
    }
    let body;
    try { body = JSON.parse((await request.text()).slice(0, 8000)); } catch (e) { return reply({ error: "json" }, 400, origin); }
    const known = await allowed(), votes = Object.entries((body && body.v) || {})
      .filter(([law, v]) => known.has(law) && ["z", "p", "u"].includes(v)).slice(0, 30);
    if (!votes.length) return reply({ error: "empty" }, 400, origin);
    await env.DB.batch(votes.map(([law, v]) => env.DB.prepare(
      "INSERT INTO votes (law, vote, n) VALUES (?, ?, 1) ON CONFLICT (law, vote) DO UPDATE SET n = n + 1").bind(law, v)));
    return reply(await totals(env), 200, origin);
  },
};
