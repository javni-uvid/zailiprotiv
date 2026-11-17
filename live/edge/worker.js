// mikrofon.zailiprotiv.rs: "Ko sada govori" runs on the maintainer's computer behind a Cloudflare tunnel (live/).
// Every request goes to it first; when it can't answer (the tunnel is down: Cloudflare's 530, or any 5xx), the
// visitor gets the site's own page for that, zailiprotiv.rs/mikrofon (pages_mikrofon.py), under a <base> so its links
// and styles come from the site; the live service's JSON says it is off, and anything else leads to the site.

const SITE = "https://zailiprotiv.rs";
const LIVE_JSON = /^\/(stanje\.json|dani\.json|dan\/)/;
const PART = /^\/(cir\/)?deo$/;  // what an open page asks for every few seconds; a failure keeps what it shows

export default {
  async fetch(request) {
    let answer = null;
    try {
      answer = await fetch(request);
    } catch (e) {
      answer = null;
    }
    if (answer && answer.status < 500) return answer;
    return fallback(new URL(request.url));
  },
};

async function fallback(url) {
  const busy = { "cache-control": "no-store", "retry-after": "300" };
  if (LIVE_JSON.test(url.pathname)) {
    return new Response(JSON.stringify({ radi: false }), {
      status: 503, headers: { ...busy, "content-type": "application/json; charset=utf-8" } });
  }
  if (PART.test(url.pathname)) return new Response("", { status: 503, headers: busy });
  const page = url.pathname === "/" ? "mikrofon" : /^\/cir\/?$/.test(url.pathname) ? "cir/mikrofon" : null;
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
