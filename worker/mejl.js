// The day's summary by mail: who asked for it, kept so that this worker can write an address and never read it.
//
// An address is encrypted at sign-up with the public half of the maintainer's key (MEJL_JAVNI, P-256; its private
// half is only in the live service's .env on the maintainer's computer): a fresh key pair of the worker's own for
// each address, ECDH with the public key, HKDF-SHA-256, AES-GCM. What is kept beside it: a hash of the address with
// the secret SALT (to find a second sign-up of the same address, and to stop asking it too often), the script, when
// it was asked and when confirmed. No name, no IP address, nothing about opening the mail.
//
//   POST /m              ← {"adresa", "pismo": "lat"|"cir"} (JSON from the page's script, or the form without it), from
//                          the live page: a mail asking to confirm, at most once a day to one address
//   GET  /m/potvrdi?k=   → a page with one button; POST /m/potvrdi (the button) confirms. A button, not the link
//                          itself: mail scanners open links, and a sign-up must be the reader's own
//   GET  /m/odjava?i=&k= → a page with one button (the link in every mail: scanners open it too, and until 23 Nov
//                          2026 opening it deleted the address); POST deletes the address at once (the button, and
//                          List-Unsubscribe-Post, the mail reader's own button)
//   GET  /m/spisak       ← with the push's token: the confirmed, encrypted, with each one's unsubscribe link
// Unconfirmed sign-ups are deleted after 48 hours (cleanup, from the scheduled run).

const LIVE = "https://mikrofon.zailiprotiv.rs";
const SELF = "https://glasovi.zailiprotiv.rs";
const FROM = { email: "sazetak@mikrofon.zailiprotiv.rs", name: "Za ili Protiv" };
const REPLY = "kontakt@zailiprotiv.rs";
const PRIVACY = "https://zailiprotiv.rs/privatnost";
export const ADDRESS = /^[^\s@<>()",;]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$/;
const KEEP_UNCONFIRMED = 48 * 3600e3;

const enc = new TextEncoder();
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const hex = (buf) => [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
async function sha(text) { return hex(await crypto.subtle.digest("SHA-256", enc.encode(text))); }
const random = (n) => hex(crypto.getRandomValues(new Uint8Array(n)));

// The address, sealed for the maintainer's key: base64url of the worker's one-time public key (65 bytes), the
// nonce (12) and the AES-GCM ciphertext. `live/uzivo/pretplata.py` opens it.
export async function seal(jwk, text) {
  const them = await crypto.subtle.importKey("jwk", jwk, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const mine = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const shared = await crypto.subtle.deriveBits({ name: "ECDH", public: them }, mine.privateKey, 256);
  const base = await crypto.subtle.importKey("raw", shared, "HKDF", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: enc.encode("zailiprotiv mejl") },
                                            base, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(text));
  const pub = new Uint8Array(await crypto.subtle.exportKey("raw", mine.publicKey));
  const out = new Uint8Array(pub.length + iv.length + ct.byteLength);
  out.set(pub, 0); out.set(iv, pub.length); out.set(new Uint8Array(ct), pub.length + iv.length);
  return b64u(out);
}

const WORDS = {
  lat: { subject: "Potvrdi prijavu: klikni na dugme u ovom mejlu", brand: "Za ili Protiv",
         head: "Potvrdi prijavu", lead: "Klikni na dugme, pa još jednom na stranici koja se otvori. Bez toga ti sažetak dana ne stiže.",
         reply: "Ne odgovaraj na ovaj mejl: odgovor ne potvrđuje prijavu. Ako dugme ne radi, otvori ovaj link:",
         ask: "Neko, verovatno ti, prijavio je ovu adresu za sažetak dana sednice Narodne skupštine sa mikrofon.zailiprotiv.rs: posle svakog dana sednice, šta je odlučeno, ko je dobio opomenu i ko je šta rekao.",
         button: "Da, prijavi me", not: "Ako nisi ti, ne radi ništa: bez potvrde adresu brišemo za 48 sati i više ti ne pišemo.",
         privacy: "Politika o privatnosti",
         confirmTitle: "Poslednji korak", confirmText: "Klikni na dugme da potvrdiš prijavu. Tek tada ti sažetak dana stiže posle svakog dana sednice.",
         done: "Prijava je potvrđena", doneText: "Sažetak stiže posle sledećeg dana sednice. Odjava je u svakom mejlu.",
         gone: "Link je istekao", goneText: "Prijava nije potvrđena u 48 sati ili je već potvrđena. Prijavi se ponovo na mikrofonu.",
         fail: "Mejl nije poslat", failText: "Nismo uspeli da pošaljemo mejl za potvrdu. Probaj ponovo malo kasnije.",
         outAsk: "Odjavi se", outAskText: "Jedan klik i tvoja adresa se briše: sažetak dana ti više ne stiže.",
         out: "Odjavljen si", outText: "Tvoja adresa je obrisana i više ti ne pišemo.",
         check: "Proveri sanduče", checkText: "Poslali smo ti mejl. Otvori ga i klikni na dugme „Da, prijavi me“: bez toga prijava ne važi. Odgovor na mejl je ne potvrđuje.",
         bad: "Adresa nije ispravna", back: "Nazad na mikrofon" },
  cir: { subject: "Потврди пријаву: кликни на дугме у овом мејлу", brand: "За или Против",
         head: "Потврди пријаву", lead: "Кликни на дугме, па још једном на страници која се отвори. Без тога ти сажетак дана не стиже.",
         reply: "Не одговарај на овај мејл: одговор не потврђује пријаву. Ако дугме не ради, отвори овај линк:",
         ask: "Неко, вероватно ти, пријавио је ову адресу за сажетак дана седнице Народне скупштине са mikrofon.zailiprotiv.rs: после сваког дана седнице, шта је одлучено, ко је добио опомену и ко је шта рекао.",
         button: "Да, пријави ме", not: "Ако ниси ти, не ради ништа: без потврде адресу бришемо за 48 сати и више ти не пишемо.",
         privacy: "Политика о приватности",
         confirmTitle: "Последњи корак", confirmText: "Кликни на дугме да потврдиш пријаву. Тек тада ти сажетак дана стиже после сваког дана седнице.",
         done: "Пријава је потврђена", doneText: "Сажетак стиже после следећег дана седнице. Одјава је у сваком мејлу.",
         gone: "Линк је истекао", goneText: "Пријава није потврђена у 48 сати или је већ потврђена. Пријави се поново на микрофону.",
         fail: "Мејл није послат", failText: "Нисмо успели да пошаљемо мејл за потврду. Пробај поново мало касније.",
         outAsk: "Одјави се", outAskText: "Један клик и твоја адреса се брише: сажетак дана ти више не стиже.",
         out: "Одјављен си", outText: "Твоја адреса је обрисана и више ти не пишемо.",
         check: "Провери сандуче", checkText: "Послали смо ти мејл. Отвори га и кликни на дугме „Да, пријави ме“: без тога пријава не важи. Одговор на мејл је не потврђује.",
         bad: "Адреса није исправна", back: "Назад на микрофон" },
};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// A page of the worker's own (a confirmation, an unsubscription): the site's look, nothing loaded from anywhere.
function page(w, title, text, form) {
  const live = w === WORDS.cir ? LIVE + "/cir/" : LIVE + "/";
  return new Response(`<!doctype html><html lang="${w === WORDS.cir ? "sr-Cyrl" : "sr-Latn"}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${esc(title)} · ${esc(w.brand)}</title>
<style>body{margin:0;background:#eef0f3;color:#111;font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:30rem;margin:12vh auto 0;background:#fff;border-top:4px solid #111;border-radius:14px;padding:1.6rem 1.5rem}
.b{font:700 1.2rem Georgia,serif}.b i{font-style:normal;color:#1f5fa8}.b em{font-style:normal;color:#c2410c}
h1{font:700 1.6rem/1.2 Georgia,serif;margin:1rem 0 .4rem}p{margin:.4rem 0 1rem;color:#333}
button,.a{display:inline-block;font:inherit;font-weight:700;background:#111;color:#fff;border:0;border-radius:999px;padding:.7rem 1.2rem;cursor:pointer;text-decoration:none}
a{color:#111}@media (prefers-color-scheme:dark){body{background:#0c0e12;color:#f1f1ee}main{background:#181b21;border-color:#f1f1ee}p{color:#c9ccd3}
button,.a{background:#f1f1ee;color:#111}a{color:#f1f1ee}.b i{color:#7cc0f5}.b em{color:#ff9a52}}</style></head><body><main>
<div class="b"><i>${w === WORDS.cir ? "За" : "Za"}</i> ${w === WORDS.cir ? "или" : "ili"} <em>${w === WORDS.cir ? "Против" : "Protiv"}</em></div>
<h1>${esc(title)}</h1><p>${esc(text)}</p>${form || `<a class="a" href="${live}">${esc(w.back)}</a>`}
<p style="font-size:.85rem;margin-top:1.4rem"><a href="${PRIVACY}">${esc(w.privacy)}</a></p></main></body></html>`,
    { status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "referrer-policy": "no-referrer",
                              "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'" } });
}

function confirmMail(w, link) {
  const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#eef0f3"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#fff;border-top:4px solid #111;border-radius:14px">
<tr><td style="padding:24px 24px 22px;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:16px;line-height:1.55;color:#111">
<div style="font-family:Georgia,serif;font-size:19px;font-weight:bold"><span style="color:#1f5fa8">${w === WORDS.cir ? "За" : "Za"}</span> ${w === WORDS.cir ? "или" : "ili"} <span style="color:#c2410c">${w === WORDS.cir ? "Против" : "Protiv"}</span></div>
<h1 style="margin:18px 0 6px;font-family:Georgia,serif;font-size:26px;line-height:1.2">${esc(w.head)}</h1>
<p style="margin:0 0 16px;font-size:17px">${esc(w.lead)}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" bgcolor="#1f5fa8" style="border-radius:10px">
<a href="${esc(link)}" style="display:block;background:#1f5fa8;color:#fff;text-decoration:none;font-size:20px;font-weight:bold;padding:17px 18px;border-radius:10px">${esc(w.button)}</a></td></tr></table>
<p style="margin:14px 0 0;font-size:14px;color:#333"><b>${esc(w.reply.split(".")[0])}.</b>${esc(w.reply.slice(w.reply.indexOf(".") + 1))} <a href="${esc(link)}" style="color:#1f5fa8;word-break:break-all">${esc(link)}</a></p>
<p style="margin:16px 0 0;font-size:13px;color:#5b616b">${esc(w.ask)} ${esc(w.not)} <a href="${PRIVACY}" style="color:#5b616b">${esc(w.privacy)}</a></p>
</td></tr></table></td></tr></table></body></html>`;
  const text = `${w.head}: ${w.lead}\n\n${w.button}: ${link}\n\n${w.reply.split(".")[0]}.\n\n${w.ask} ${w.not}\n${w.privacy}: ${PRIVACY}\n`;
  return { html, text };
}

async function form(request) {
  const type = request.headers.get("content-type") || "";
  const body = (await request.text()).slice(0, 2000);
  if (type.includes("application/json")) { try { return { json: true, ...(JSON.parse(body) || {}) }; } catch (e) { return { json: true }; } }
  // the page's script sends the form as it is (no preflight), with js=1 to have JSON back; the form alone, a page
  const fields = Object.fromEntries(new URLSearchParams(body));
  return { ...fields, json: fields.js === "1" };
}

const json = (body, status) => new Response(JSON.stringify(body), { status, headers: {
  "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "access-control-allow-origin": LIVE, "vary": "origin" } });

// The unsubscribe link of one confirmed address: its row and a hash of it with the secret, so a link can't be made
// up for another row.
async function outLink(env, id) { return `${SELF}/m/odjava?i=${id}&k=${(await sha(env.SALT + "|odjava|" + id)).slice(0, 32)}`; }

export async function handle(request, env, path, from, same) {
  const url = new URL(request.url);
  if (path === "/m" && request.method === "POST") {
    if (from !== LIVE) return json({ error: "origin" }, 403);
    if (!env.MEJL || !env.MEJL_JAVNI || !env.SALT) return json({ error: "not ready" }, 503);
    if (env.LIMIT) {
      const { success } = await env.LIMIT.limit({ key: request.headers.get("cf-connecting-ip") || "x" });
      if (!success) return json({ error: "limit" }, 429);
    }
    const b = await form(request);
    const w = b.pismo === "cir" ? WORDS.cir : WORDS.lat;
    const address = String(b.adresa || "").trim();
    if (!ADDRESS.test(address)) return b.json ? json({ error: "adresa" }, 400) : page(w, w.bad, "", "");
    const key = await sha(env.SALT + "|mejl|" + address.toLowerCase());
    const now = new Date().toISOString(), day = now.slice(0, 10);
    const row = await env.DB.prepare("SELECT id, potvrda, poslato FROM mejl WHERE kljuc = ?").bind(key).first();
    // The answer is the same whatever was found: a page can't learn from it who is signed up.
    const answer = () => b.json ? json({ ok: true }, 200) : page(w, w.check, w.checkText, "");
    if (row && (row.potvrda || row.poslato === day)) return answer();
    const token = random(16);
    if (row) await env.DB.prepare("UPDATE mejl SET kod = ?, poslato = ?, prijava = ?, cir = ? WHERE id = ?")
      .bind(await sha(token), day, now, w === WORDS.cir ? 1 : 0, row.id).run();
    else await env.DB.prepare("INSERT INTO mejl (id, kljuc, adresa, cir, prijava, kod, poslato) VALUES (?, ?, ?, ?, ?, ?, ?)")
      .bind(random(12), key, await seal(JSON.parse(env.MEJL_JAVNI), address), w === WORDS.cir ? 1 : 0, now, await sha(token), day).run();
    const mail = confirmMail(w, `${SELF}/m/potvrdi?k=${token}`);
    try {
      await env.MEJL.send({ from: FROM, to: address, replyTo: REPLY, subject: w.subject, html: mail.html, text: mail.text });
    } catch (e) {  // it did not go: the same address may ask again at once, not be told all day that it went
      await env.DB.prepare("UPDATE mejl SET poslato = NULL WHERE kljuc = ?").bind(key).run();
      return b.json ? json({ error: "slanje", code: String((e && e.code) || "") }, 502) : page(w, w.fail, w.failText, "");
    }
    return answer();
  }
  if (path === "/m/potvrdi") {
    const k = request.method === "POST" ? String((await form(request)).k || "") : url.searchParams.get("k") || "";
    const row = /^[0-9a-f]{32}$/.test(k)
      ? await env.DB.prepare("SELECT id, cir, prijava FROM mejl WHERE kod = ? AND potvrda IS NULL").bind(await sha(k)).first() : null;
    const w = row && row.cir ? WORDS.cir : WORDS.lat;
    if (!row || Date.now() - Date.parse(row.prijava) > KEEP_UNCONFIRMED) return page(w, w.gone, w.goneText, "");
    if (request.method !== "POST")
      return page(w, w.confirmTitle, w.confirmText, `<form method="post" action="/m/potvrdi"><input type="hidden" name="k" value="${k}"><button>${esc(w.button)}</button></form>`);
    await env.DB.prepare("UPDATE mejl SET potvrda = ?, kod = NULL WHERE id = ?").bind(new Date().toISOString(), row.id).run();
    return page(w, w.done, w.doneText, "");
  }
  if (path === "/m/odjava") {
    const id = url.searchParams.get("i") || "", k = url.searchParams.get("k") || "";
    const row = /^[0-9a-f]{24}$/.test(id) ? await env.DB.prepare("SELECT cir FROM mejl WHERE id = ?").bind(id).first() : null;
    const w = row && row.cir ? WORDS.cir : WORDS.lat;
    const valid = row && env.SALT && k === (await sha(env.SALT + "|odjava|" + id)).slice(0, 32);
    if (request.method !== "POST")
      return valid ? page(w, w.outAsk, w.outAskText, `<form method="post" action="/m/odjava?i=${id}&amp;k=${k}"><input type="hidden" name="strana" value="1"><button>${esc(w.outAsk)}</button></form>`)
        : page(w, w.out, w.outText, "");  // no such row: already gone
    if (valid) await env.DB.prepare("DELETE FROM mejl WHERE id = ?").bind(id).run();
    if (!(await form(request)).strana) return new Response(null, { status: 204 });  // the mail reader's own button
    return page(w, w.out, w.outText, "");
  }
  if (path === "/m/spisak" && request.method === "GET") {
    const auth = request.headers.get("authorization") || "";
    if (!env.PUSH_TOKEN || !env.SALT || !(await same(auth, "Bearer " + env.PUSH_TOKEN))) return json({ error: "token" }, 403);
    const rows = (await env.DB.prepare("SELECT id, adresa, cir FROM mejl WHERE potvrda IS NOT NULL ORDER BY id").all()).results;
    const out = [];
    for (const r of rows) out.push({ id: r.id, adresa: r.adresa, cir: !!r.cir, odjava: await outLink(env, r.id) });
    return json({ primaoci: out }, 200);
  }
  return null;
}

export async function cleanup(env) {
  await env.DB.prepare("DELETE FROM mejl WHERE potvrda IS NULL AND prijava < ?").bind(new Date(Date.now() - KEEP_UNCONFIRMED).toISOString()).run();
}

export async function count(env) {
  const r = await env.DB.prepare("SELECT SUM(potvrda IS NOT NULL) AS potvrdjeno, SUM(potvrda IS NULL) AS ceka FROM mejl").first();
  return { potvrdjeno: (r && r.potvrdjeno) || 0, ceka: (r && r.ceka) || 0 };
}
