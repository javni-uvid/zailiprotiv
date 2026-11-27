// Following a sitting MP (25 Nov 2026) or an area of laws (27 Nov 2026) by mail: who asked, and whom or what they
// follow, kept so that this worker can write both and read neither.
//
// The address and what is followed are each sealed with the public half of the maintainer's key (mejl.js, seal),
// padded first to one length, so that the length of neither says anything. Beside them: the same hash of the address
// as the summary's (to know it again, and to leave everything at once), the script, the day asked and confirmed.
// There is no column, hash or count from which an MP or an area can be told: two hundred and fifty names are guessed
// in a moment. What is followed is sealed as "<kind>|<address>|<name>", every kind padded to the same length, so the
// kind does not show either: "p" a sitting MP, "o" an area (a point of Article 97); another kind is one more entry in
// KINDS, with no change to the tables.
// What is asked for is confirmed by a mail that names it, each one anew, as anybody can write anybody's address.
//
//   POST /m/prati          ← {"adresa", "sta": the address on the site, "vrsta": "p" (none) or "o", "pismo"}, from the site's own pages
//   GET  /m/prati/potvrdi  ?k= → a page with one button; POST (the button) is the consent
//   GET  /m/prati/kraj     ?i=&k= (repeated, when one MP was asked for twice) → a button; POST ends those
//   GET  /m/prati/sve      ?i=&k= → a button; POST ends all of them (also the mail reader's own button: One-Click)
//   GET  /m/prati/svega    ?i=&k= → a button; POST ends all of them and the day's summary
//   GET  /m/prati/spisak   ← with the push's token: the confirmed, sealed, each with its links
// Not confirmed in 48 hours: deleted (cleanup). Ending deletes the row at once, the reader's with the last one.
import { ADDRESS, KEEP_UNCONFIRMED, REPLY, FROM, SELF, PRIVACY, WORDS, seal, sha, random, page, form, esc } from "./mejl.js";

const SITE = "https://zailiprotiv.rs";
// What can be followed, by kind: the site's list of each, {address: [name, the name in Cyrillic]}.
export const KINDS = { p: SITE + "/prati-poslanici.json", o: SITE + "/prati-oblasti.json" };
const PAD = { adresa: 416, sta: 256 };  // bytes: longer than any that is taken
export const MOST = { unconfirmed: 1, confirmed: 5, together: 40, mails: 300 };  // a day, a day, at once, a day from all

const enc = new TextEncoder();
// Padded with spaces to `n` bytes; null for what does not fit.
export function pad(text, n) {
  const over = n - enc.encode(text).length;
  return over < 0 ? null : text + " ".repeat(over);
}

const SAID = {
  lat: { subject: "Potvrdi praćenje: klikni na dugme u ovom mejlu", kicker: "POTVRDI PRAĆENJE",
         what: "Kad govori u sali · najviše jedan mejl dnevno",
         consent: "Koga pratiš može da govori o tvom političkom mišljenju. Dugme je tvoj pristanak da to čuvamo, šifrovano, samo za ovaj mejl. Prekidaš kad hoćeš, dugmetom u svakom mejlu: tada se odmah briše.",
         button: "Pristajem, prati", not: "Nisi ti? Ne radi ništa: bez potvrde se sve briše za 48 sati.",
         check: "Proveri sanduče", checkText: "Proveri sanduče i klikni na dugme u mejlu: bez toga praćenje ne važi. Ako pratiš prvi put, prvo potvrdi taj mejl, pa dodaj sledeće.",
         bad: "Prijava nije uspela: proveri adresu i pokušaj ponovo malo kasnije.",
         confirmTitle: "Poslednji korak", confirmText: "Klikni na dugme: time pristaješ na praćenje koje piše u mejlu. Tek tada važi.",
         done: "Praćenje važi", doneText: "Mejl stiže ujutru posle dana kad ima novog. Prekidaš ga u svakom mejlu.",
         gone: "Link je istekao", goneText: "Praćenje nije potvrđeno u 48 sati ili je već potvrđeno. Zatraži ga ponovo na sajtu, na strani poslanika ili oblasti.",
         end: "Prestani da pratiš", endText: "Jedan klik i praćenje uz koje je bio ovaj link se briše.", ended: "Praćenje je obrisano",
         all: "Prestani sve da pratiš", allText: "Jedan klik i sva tvoja praćenja se brišu. Sažetak dana ostaje ako si se prijavio.", allEnded: "Praćenja su obrisana",
         out: "Odjavi me sa svega", outText: "Jedan klik i tvoja adresa se briše: ne stižu ti ni praćenje ni sažetak dana.", outEnded: "Tvoja adresa je obrisana i više ti ne pišemo.",
         back: "Nazad na sajt", home: SITE + "/" },
  cir: { subject: "Потврди праћење: кликни на дугме у овом мејлу", kicker: "ПОТВРДИ ПРАЋЕЊЕ",
         what: "Кад говори у сали · највише један мејл дневно",
         consent: "Кога пратиш може да говори о твом политичком мишљењу. Дугме је твој пристанак да то чувамо, шифровано, само за овај мејл. Прекидаш кад хоћеш, дугметом у сваком мејлу: тада се одмах брише.",
         button: "Пристајем, прати", not: "Ниси ти? Не ради ништа: без потврде се све брише за 48 сати.",
         check: "Провери сандуче", checkText: "Провери сандуче и кликни на дугме у мејлу: без тога праћење не важи. Ако пратиш први пут, прво потврди тај мејл, па додај следеће.",
         bad: "Пријава није успела: провери адресу и покушај поново мало касније.",
         confirmTitle: "Последњи корак", confirmText: "Кликни на дугме: тиме пристајеш на праћење које пише у мејлу. Тек тада важи.",
         done: "Праћење важи", doneText: "Мејл стиже ујутру после дана кад има новог. Прекидаш га у сваком мејлу.",
         gone: "Линк је истекао", goneText: "Праћење није потврђено у 48 сати или је већ потврђено. Затражи га поново на сајту, на страни посланика или области.",
         end: "Престани да пратиш", endText: "Један клик и праћење уз које је био овај линк се брише.", ended: "Праћење је обрисано",
         all: "Престани све да пратиш", allText: "Један клик и сва твоја праћења се бришу. Сажетак дана остаје ако си се пријавио.", allEnded: "Праћења су обрисана",
         out: "Одјави ме са свега", outText: "Један клик и твоја адреса се брише: не стижу ти ни праћење ни сажетак дана.", outEnded: "Твоја адреса је обрисана и више ти не пишемо.",
         back: "Назад на сајт", home: SITE + "/cir/" },
};

// What changes in the confirmation for an area (the approved words of its sign-up): what comes, and "what" for "whom".
const AREA = {
  lat: { what: "Kad zakon iz ove oblasti uđe u proceduru, dođe na dnevni red ili bude usvojen · najviše jedan mejl dnevno",
         consent: SAID.lat.consent.replace("Koga pratiš", "Šta pratiš") },
  cir: { what: "Кад закон из ове области уђе у процедуру, дође на дневни ред или буде усвојен · највише један мејл дневно",
         consent: SAID.cir.consent.replace("Кога пратиш", "Шта пратиш") },
};
const said = (s, kind) => kind === "o" ? { ...s, ...(s === SAID.cir ? AREA.cir : AREA.lat) } : s;

// A page of the worker's own in the summary's look; the way back is the site's.
function shown(s, title, text, button) {
  return page(s === SAID.cir ? WORDS.cir : WORDS.lat, title, text, button, { href: s.home, text: s.back });
}

// The mail that asks for the consent: whom, and what the button means. No name in the subject.
export function confirmMail(s, name, link) {
  const sans = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;";
  const cir = s === SAID.cir, policy = (cir ? PRIVACY.replace(SITE, SITE + "/cir") : PRIVACY) + "#pracenje", privacy = cir ? "Политика о приватности" : "Politika o privatnosti";
  const brand = cir ? ["За", "или", "Против"] : ["Za", "ili", "Protiv"];
  const html = `<!doctype html><html lang="${cir ? "sr-Cyrl" : "sr-Latn"}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only"><title>${esc(s.subject)}</title></head>
<body style="margin:0;padding:0;background:#eef0f3"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#eef0f3"><tr><td align="center" style="padding:14px 12px 28px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px">
<tr><td style="padding:4px 4px 14px;font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:bold;color:#111111"><span style="color:#1f5fa8">${brand[0]}</span> ${brand[1]} <span style="color:#c2410c">${brand[2]}</span></td></tr>
<tr><td bgcolor="#ffffff" style="background:#ffffff;border-radius:14px;padding:20px">
<div style="${sans}font-size:12px;font-weight:bold;letter-spacing:1.2px;color:#5b616b;padding:0 0 6px">${esc(s.kicker)}</div>
<div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;line-height:1.15;font-weight:bold;color:#111111">${esc(name)}</div>
<div style="${sans}font-size:14px;line-height:1.5;color:#5b616b;padding:2px 0 12px">${esc(s.what)}</div>
<div style="${sans}font-size:16px;line-height:1.55;color:#111111">${esc(s.consent)}</div>
<div style="padding:16px 0 0"><a href="${esc(link)}" style="display:block;${sans}font-size:16px;font-weight:bold;text-align:center;text-decoration:none;border-radius:14px;padding:17px 18px;background:#111111;color:#ffffff;border:1px solid #111111">${esc(s.button)}</a></div>
<div style="${sans}font-size:14px;line-height:1.5;color:#5b616b;padding:12px 0 0">${esc(s.not)}</div></td></tr>
<tr><td style="${sans}font-size:12px;line-height:1.8;color:#5b616b;padding:8px 8px 0;text-align:center"><a href="${policy}" style="color:#5b616b">${privacy}</a><br>${brand.join(" ")} · ${REPLY}</td></tr>
</table></td></tr></table></body></html>`;
  const text = `${s.kicker}\n\n${name}\n${s.what}\n\n${s.consent}\n\n${s.button}: ${link}\n\n${s.not}\n\n${privacy}: ${policy}\n${brand.join(" ")} · ${REPLY}\n`;
  return { html, text };
}

const lists = {};  // by kind: { at, map }
async function listed(kind) {
  const had = lists[kind];
  if (!had || Date.now() - had.at > 3600e3) {
    const r = await fetch(KINDS[kind], { cf: { cacheTtl: 600 } });
    if (r.ok) lists[kind] = { at: Date.now(), map: new Map(Object.entries(await r.json())) };
  }
  return (lists[kind] || {}).map || new Map();
}

// A link's code: a hash with the secret of what it ends, so that none can be made up for another row.
const code = async (env, what, id) => (await sha(`${env.SALT}|${what}|${id}`)).slice(0, 32);
const link = async (env, path, id) => `${SELF}/m/prati/${path}?i=${id}&k=${await code(env, "prati-" + path, id)}`;

const json = (body, status) => new Response(JSON.stringify(body), { status, headers: {
  "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "access-control-allow-origin": SITE, "vary": "origin" } });

async function ask(request, env, from) {
  if (from !== SITE) return json({ error: "origin" }, 403);
  if (!env.MEJL || !env.MEJL_JAVNI || !env.SALT) return json({ error: "not ready" }, 503);
  if (env.LIMIT) {
    const { success } = await env.LIMIT.limit({ key: request.headers.get("cf-connecting-ip") || "x" });
    if (!success) return json({ error: "limit" }, 429);
  }
  const b = await form(request);
  const s = b.pismo === "cir" ? SAID.cir : SAID.lat;
  const refused = (what, status) => b.json ? json({ error: what }, status) : shown(s, s.bad, "", "");
  const address = String(b.adresa || "").trim(), slug = String(b.sta || ""), kind = String(b.vrsta || "p");
  const names = Object.hasOwn(KINDS, kind) && /^[a-z0-9-]{1,80}$/.test(slug) ? (await listed(kind)).get(slug) : null;
  const padded = ADDRESS.test(address) ? pad(address, PAD.adresa) : null;
  const what = Array.isArray(names) ? pad(`${kind}|${slug}|${names[0]}`, PAD.sta) : null;
  if (!padded || !what) return refused("adresa", 400);
  const key = await sha(env.SALT + "|mejl|" + address.toLowerCase());
  const now = new Date().toISOString(), day = now.slice(0, 10);
  // The answer is the same whatever was found: a page can't learn from it who follows anybody.
  const answer = () => b.json ? json({ ok: true }, 200) : shown(s, s.check, s.checkText, "");
  const reader = await env.DB.prepare("SELECT id, potvrda, dan, n FROM pratioci WHERE kljuc = ?").bind(key).first();
  if (reader) {
    if (reader.dan === day && reader.n >= (reader.potvrda ? MOST.confirmed : MOST.unconfirmed)) return answer();
    const has = await env.DB.prepare("SELECT COUNT(*) AS n FROM prati WHERE citalac = ?").bind(reader.id).first();
    if (has && has.n >= MOST.together) return answer();
  }
  const counted = await env.DB.prepare("INSERT INTO prati_dani (dan, n) VALUES (?1, 1) ON CONFLICT (dan) DO UPDATE SET n = n + 1 WHERE n < ?2")
    .bind(day, MOST.mails).run();
  if (!(counted.meta && counted.meta.changes)) return refused("danas", 429);
  const jwk = JSON.parse(env.MEJL_JAVNI), id = reader ? reader.id : random(12), row = random(12), token = random(16);
  const cir = s === SAID.cir ? 1 : 0;
  await env.DB.batch([
    reader ? env.DB.prepare("UPDATE pratioci SET n = CASE WHEN dan = ?1 THEN n + 1 ELSE 1 END, dan = ?1, cir = ?2 WHERE id = ?3").bind(day, cir, id)
           : env.DB.prepare("INSERT INTO pratioci (id, kljuc, adresa, cir, dan, n) VALUES (?, ?, ?, ?, ?, 1)").bind(id, key, await seal(jwk, padded), cir, day),
    env.DB.prepare("INSERT INTO prati (id, citalac, sta, prijava, kod) VALUES (?, ?, ?, ?, ?)").bind(row, id, await seal(jwk, what), now, await sha(token))]);
  const mail = confirmMail(said(s, kind), names[cir] || names[0], `${SELF}/m/prati/potvrdi?k=${token}`);
  try {
    await env.MEJL.send({ from: FROM, to: address, replyTo: REPLY, subject: s.subject, html: mail.html, text: mail.text });
  } catch (e) {  // it did not go: nothing is kept of it, and the same address may ask again at once
    await env.DB.batch([env.DB.prepare("DELETE FROM prati WHERE id = ?").bind(row),
      env.DB.prepare("UPDATE pratioci SET n = n - 1 WHERE id = ?").bind(id),
      env.DB.prepare(EMPTY)]);
    return b.json ? json({ error: "slanje", code: String((e && e.code) || "") }, 502) : shown(s, s.bad, "", "");
  }
  return answer();
}

const EMPTY = "DELETE FROM pratioci WHERE id NOT IN (SELECT citalac FROM prati)";  // a reader who follows nobody

const button = (action, words, hidden) => `<form method="post" action="${action}">${hidden}<button>${esc(words)}</button></form>`;

export async function handle(request, env, path, from, same) {
  const url = new URL(request.url), post = request.method === "POST";
  if (path === "/m/prati") return post ? ask(request, env, from) : null;
  if (path === "/m/prati/potvrdi") {
    const k = post ? String((await form(request)).k || "") : url.searchParams.get("k") || "";
    const row = /^[0-9a-f]{32}$/.test(k) ? await env.DB.prepare("SELECT prati.id, citalac, prijava, cir FROM prati JOIN pratioci ON pratioci.id = citalac " +
      "WHERE kod = ? AND prati.potvrda IS NULL").bind(await sha(k)).first() : null;
    const s = row && row.cir ? SAID.cir : SAID.lat;
    if (!row || Date.now() - Date.parse(row.prijava) > KEEP_UNCONFIRMED) return shown(s, s.gone, s.goneText, "");
    if (!post) return shown(s, s.confirmTitle, s.confirmText, button("/m/prati/potvrdi", s.button, `<input type="hidden" name="k" value="${k}">`));
    const day = new Date().toISOString().slice(0, 10);
    await env.DB.batch([
      env.DB.prepare("UPDATE prati SET potvrda = ?1, prijava = substr(prijava, 1, 10), kod = NULL WHERE id = ?2").bind(day, row.id),
      env.DB.prepare("UPDATE pratioci SET potvrda = COALESCE(potvrda, ?1) WHERE id = ?2").bind(day, row.citalac)]);
    return shown(s, s.done, s.doneText, "");
  }
  const what = { "/m/prati/kraj": "kraj", "/m/prati/sve": "sve", "/m/prati/svega": "svega" }[path];
  if (what) {
    const ids = url.searchParams.getAll("i").slice(0, MOST.together), ks = url.searchParams.getAll("k"), valid = [];
    let cir = 0;
    for (const [n, id] of ids.entries()) {
      if (!env.SALT || !/^[0-9a-f]{24}$/.test(id) || ks[n] !== await code(env, "prati-" + what, id)) continue;
      const row = await env.DB.prepare(what === "kraj" ? "SELECT prati.id, cir FROM prati JOIN pratioci ON pratioci.id = citalac WHERE prati.id = ?"
                                                       : "SELECT id, kljuc, cir FROM pratioci WHERE id = ?").bind(id).first();
      if (row) { valid.push(row); cir = row.cir; }
    }
    const s = cir ? SAID.cir : SAID.lat;
    const words = { kraj: [s.end, s.endText, s.ended, ""], sve: [s.all, s.allText, s.allEnded, ""], svega: [s.out, s.outText, s.outEnded, ""] }[what];
    if (!post && valid.length) return shown(s, words[0], words[1], button(esc(path + url.search), words[0], '<input type="hidden" name="strana" value="1">'));
    if (post) {
      for (const row of valid) {
        if (what === "kraj") await env.DB.prepare("DELETE FROM prati WHERE id = ?").bind(row.id).run();
        else await env.DB.batch([env.DB.prepare("DELETE FROM prati WHERE citalac = ?").bind(row.id),
          env.DB.prepare("DELETE FROM pratioci WHERE id = ?").bind(row.id),
          ...(what === "svega" ? [env.DB.prepare("DELETE FROM mejl WHERE kljuc = ?").bind(row.kljuc)] : [])]);
      }
      await env.DB.prepare(EMPTY).run();
      if (!(await form(request)).strana) return new Response(null, { status: 204 });  // the mail reader's own button
    }
    return shown(s, words[2], words[3], "");  // ended now, or no such row: ended before
  }
  if (path === "/m/prati/spisak" && !post) {
    const auth = request.headers.get("authorization") || "";
    if (!env.PUSH_TOKEN || !env.SALT || !(await same(auth, "Bearer " + env.PUSH_TOKEN))) return json({ error: "token" }, 403);
    const rows = (await env.DB.prepare("SELECT prati.id, citalac, sta, prati.potvrda AS od, pratioci.adresa, pratioci.cir, mejl.id AS mejl FROM prati " +
      "JOIN pratioci ON pratioci.id = citalac LEFT JOIN mejl ON mejl.kljuc = pratioci.kljuc AND mejl.potvrda IS NOT NULL " +
      "WHERE prati.potvrda IS NOT NULL ORDER BY citalac, prati.potvrda, prati.id").all()).results;
    const out = new Map();
    for (const r of rows) {
      if (!out.has(r.citalac)) out.set(r.citalac, { id: r.citalac, adresa: r.adresa, cir: !!r.cir, mejl: r.mejl || "", prati: [],
        sve: await link(env, "sve", r.citalac), svega: await link(env, "svega", r.citalac) });
      out.get(r.citalac).prati.push({ id: r.id, sta: r.sta, od: r.od, kraj: await link(env, "kraj", r.id) });
    }
    return json({ pratioci: [...out.values()] }, 200);
  }
  return null;
}

export async function cleanup(env) {
  await env.DB.batch([
    env.DB.prepare("DELETE FROM prati WHERE potvrda IS NULL AND prijava < ?").bind(new Date(Date.now() - KEEP_UNCONFIRMED).toISOString()),
    env.DB.prepare(EMPTY),
    env.DB.prepare("DELETE FROM prati_dani WHERE dan < ?").bind(new Date(Date.now() - 14 * 864e5).toISOString().slice(0, 10))]);
}

// How many readers follow somebody, how many ask to: never whom, nor how many one MP.
export async function count(env) {
  const r = await env.DB.prepare("SELECT (SELECT COUNT(*) FROM pratioci WHERE potvrda IS NOT NULL) AS citalaca, " +
    "(SELECT COUNT(*) FROM prati WHERE potvrda IS NULL) AS ceka").first();
  return { citalaca: (r && r.citalaca) || 0, ceka: (r && r.ceka) || 0 };
}
