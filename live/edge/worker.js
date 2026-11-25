// mikrofon.zailiprotiv.rs: "Ko sada govori" runs on the maintainer's computer behind a Cloudflare tunnel (live/).
// Every request goes to it first; when it can't answer (the tunnel is down: Cloudflare's 530, or any 5xx), the
// visitor gets its last answer if under two minutes old (a restart), and otherwise the site's own page for that, zailiprotiv.rs/mikrofon (pages_mikrofon.py), under a <base> so its links
// and styles come from the site; the live service's JSON says it is off, and anything else leads to the site.

const SITE = "https://zailiprotiv.rs";
const LIVE_JSON = /^\/(stanje\.json|dani\.json|dan\/)/;
const PART = /^\/(cir\/)?deo$/;  // what an open page asks for every few seconds; a failure keeps what it shows

// What every open page asks for every few seconds, the same for everyone: kept here three seconds per Cloudflare
// location, so the computer answers each about once in three seconds there, however many ask (18 Nov 2026: some
// 4,500 visits an hour, each page asking every five seconds, and other sites reading the state, left it unanswering).
const SHARED = /^\/((cir\/)?(deo|govor\/\d{10})?|stanje\.json)$/;
const KEEP = 3;
// The same answers kept longer, apart, for when the service doesn't answer (20 Nov 2026): a new image put live
// restarts it for a few seconds, and in that time an open page goes on showing the last answer (its "checked N s
// ago" grows) instead of the site's page for a service that is off. Older than this, the service is taken as off.
const LAST = 120;
const last = (url) => new Request(url.origin + "/~poslednje" + url.pathname);

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const shared = request.method === "GET" && SHARED.test(url.pathname);
    const key = shared ? new Request(url.origin + url.pathname) : null;  // a query string doesn't make it new
    if (shared) {
      const hit = await caches.default.match(key);
      if (hit) return fresh(hit);
    }
    let answer = null;
    try {
      answer = await fetch(request);
    } catch (e) {
      answer = null;
    }
    if (answer && answer.status < 500) {
      if (shared && answer.status === 200) {
        const kept = new Response(answer.clone().body, answer);
        kept.headers.set("cache-control", `public, max-age=${KEEP}`);
        ctx.waitUntil(caches.default.put(key, kept));
        const spare = new Response(answer.clone().body, answer);
        spare.headers.set("cache-control", `public, max-age=${LAST}`);
        ctx.waitUntil(caches.default.put(last(url), spare));
      }
      return answer;
    }
    if (shared) {  // the service restarting: the last answer, if it is recent
      const spare = await caches.default.match(last(url));
      if (spare) {
        const out = fresh(spare);
        out.headers.set("x-mikrofon", "poslednje");
        return out;
      }
    }
    return fallback(url);
  },
};

// A kept answer as the browser gets it: not to be kept again by the browser (the page asks for the newest).
function fresh(hit) {
  const out = new Response(hit.body, hit);
  out.headers.set("cache-control", "no-store");
  return out;
}

async function fallback(url) {
  const busy = { "cache-control": "no-store", "retry-after": "300" };
  if (LIVE_JSON.test(url.pathname)) {
    return new Response(JSON.stringify({ radi: false }), {
      status: 503, headers: { ...busy, "content-type": "application/json; charset=utf-8" } });
  }
  const mail = /^\/(cir\/)?iz-mejla\/(govor\/\d{10})$/.exec(url.pathname);  // a speech's link in a mail: the speech's own
  if (mail) return Response.redirect(`${url.origin}/${mail[1] || ""}${mail[2]}#iz-mejla`, 302);
  if (PART.test(url.pathname)) return new Response("", { status: 503, headers: busy });
  // a shared speech (/govor/<second>) too: the site's page lists the last day, and its script finds the speech there
  const page = /^\/(govor\/\d{10})?$/.test(url.pathname) ? "mikrofon"
    : /^\/cir(\/(govor\/\d{10})?)?$/.test(url.pathname) ? "cir/mikrofon" : null;
  if (!page) return Response.redirect(SITE + "/", 302);  // nothing else is here while the service is off
  const shown = await fetch(`${SITE}/${page}`, { cf: { cacheTtl: 300 } });
  if (!shown.ok) return new Response("Ko sada govori trenutno ne radi.", { status: 503, headers: busy });
  const at = `${SITE}/${page.startsWith("cir/") ? "cir/" : ""}`;
  const out = new HTMLRewriter()
    .on("head", { element(head) {  // the page's relative links and styles lead to the site, not to this host
      head.prepend(`<base href="${at}">`, { html: true });
    } })
    .on('a[href$="mikrofon"]', { element(a) {  // the other script's page: this host's, not the site's copy
      a.setAttribute("href", `${url.origin}/${page.startsWith("cir/") ? "" : "cir/"}`);
    } })
    .transform(shown);
  return new Response(out.body, {
    status: 503, headers: { ...busy, "content-type": "text/html; charset=utf-8" } });
}
