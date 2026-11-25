// Cyrillic typed into a search box finds Latin text, and the other way round: everything is compared in Latin.
var CYR = { "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e", "ж": "ž", "з": "z", "и": "i", "ј": "j",
  "к": "k", "л": "l", "љ": "lj", "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "ћ": "ć",
  "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "č", "џ": "dž", "ш": "š" };
// A use of the quiz or the ballot ("kviz.kraj", "listic.podeljeno", …), told to the counter once per page: it keeps a
// sum per day and nothing else, not even the device's mark. Plain text, so the browser asks nothing first.
var zipCounted = {};
function zipCount(what) {
  var api = document.body && (document.body.dataset.api || "").replace(/\/$/, "");
  if (!api || zipCounted[what]) return;
  zipCounted[what] = 1;
  try { fetch(api + "/e", { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify({ e: what }), keepalive: true }).catch(function () {}); } catch (e) {}
}
// A way taken from the site to the live page, counted by where it was taken (22 Nov 2026: the menu, the home page's
// strip, the announcement before a sitting, the bar of a sitting, an MP at the rostrum; any other link as one).
var MIK = { meni: "sajt.mikrofon-meni", pocetna: "sajt.mikrofon-pocetna", najava: "sajt.mikrofon-najava",
  traka: "sajt.mikrofon-traka", poslanik: "sajt.mikrofon-poslanik" };
document.addEventListener("click", function (e) {
  var a = e.target.closest && e.target.closest("a[href]");
  if (a && a.hostname === "mikrofon.zailiprotiv.rs") zipCount(MIK[a.getAttribute("data-mik")] || "sajt.mikrofon");
}, true);
// The page "Podrži" (23 Nov 2026), as the other uses: a sum per day, nothing of who. The way to it by where it was
// taken; on it, that it was opened (and opened from the live page), the codes in view, a code's picture saved, the
// account copied, PayPal opened.
var DON = { meni: "podrzi.klik-meni", podnozje: "podrzi.klik-podnozje", pocetna: "podrzi.klik-pocetna" };
document.addEventListener("click", function (e) {
  var a = e.target.closest && e.target.closest("a[data-don]");
  if (a && DON[a.getAttribute("data-don")]) zipCount(DON[a.getAttribute("data-don")]);
}, true);
(function () {
  function start() {
    var codes = document.querySelector("#ips.support");
    if (!codes) return;
    zipCount("podrzi.otvori");
    if (/^https:\/\/mikrofon\.zailiprotiv\.rs\//.test(document.referrer)) zipCount("podrzi.od-mikrofona");
    if (window.IntersectionObserver) new IntersectionObserver(function (seen, o) {
      if (seen.some(function (x) { return x.isIntersecting; })) { zipCount("podrzi.kod"); o.disconnect(); }
    }, { threshold: 0.2 }).observe(codes.querySelector(".ips-codes") || codes);
    document.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("a[href]");
      if (!a) return;
      if (a.hasAttribute("download") && codes.contains(a)) zipCount("podrzi.slika");
      else if (/(^|\.)paypal\.(com|me)$/.test(a.hostname)) zipCount("podrzi.paypal");
    }, true);
    document.addEventListener("copy", function () {
      var s = window.getSelection && window.getSelection(), n = s && s.anchorNode;
      if (n && document.getElementById("nalog") && document.getElementById("nalog").contains(n)) zipCount("podrzi.kopiraj");
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
// The parts said only in their hours (the announcement from the day before a sitting until it starts, "sutra" or
// "danas", the strip's day until it has passed): data-show="from,to", seconds since 1970, set when the pages are built.
(function () {
  var now = Date.now() / 1000;
  Array.prototype.forEach.call(document.querySelectorAll("[data-show]"), function (el) {
    var t = el.getAttribute("data-show").split(",");
    el.hidden = !(now >= +t[0] && now < +t[1]);
  });
})();
// An MP's speeches of a day (the MP's page): each one's address among the notes' pages, kept short in the page
// ("dan-3-2.html#g00527 …" beside the sitting's folder) and made into numbered links here.
document.addEventListener("DOMContentLoaded", function () {
  Array.prototype.forEach.call(document.querySelectorAll(".speech-n[data-s]"), function (box) {
    var base = box.dataset.base, parts = box.dataset.s.split(" ");
    if (!/^https:\/\/[a-z0-9.-]+\/[A-Za-z0-9\/_-]*\/$/.test(base)) return;  // the notes' own folder, nothing else
    box.textContent = "";
    if (box.dataset.day) { var b = document.createElement("b"); b.textContent = box.dataset.day + ". dan"; box.appendChild(b); }
    parts.forEach(function (p, i) {
      var m = /^([\d-]+)\.(\d+)$/.exec(p), a = document.createElement("a");
      if (!m && !/^[A-Za-z0-9_.-]+(?:#[A-Za-z0-9_-]+)?$/.test(p)) return;
      a.href = base + (m ? "dan-" + m[1] + ".html#g" + m[2] : p);
      a.textContent = String(i + 1);
      box.appendChild(a);
    });
  });
});
// The Cyrillic edition (cir/): what the scripts write into the page is written in Cyrillic too.
(function () {
  "use strict";
  if (document.documentElement.lang !== "sr-Cyrl") return;
  var LAT = {}, KEEP = /https?:\/\/\S+|[\w.-]+\.(?:rs|com|org|html|json|csv|xml|pdf)\b\S*|\b(?:PDF|RSS|CSV|JSON|AI|API|EXPO|UniCredit|NLB|[IVX]{2,})\b/g;
  Object.keys(CYR).forEach(function (c) { if (CYR[c].length === 1) { LAT[CYR[c]] = c; LAT[CYR[c].toUpperCase()] = c.toUpperCase(); } });
  function plain(t) {
    return t.replace(/lj/g, "љ").replace(/L[jJ]/g, "Љ").replace(/nj/g, "њ").replace(/N[jJ]/g, "Њ").replace(/dž/g, "џ").replace(/D[žŽ]/g, "Џ")
      .replace(/[A-Za-zČĆŽŠĐčćžšđ]/g, function (c) { return LAT[c] || c; });
  }
  function cyr(t) {
    var out = "", last = 0, m; KEEP.lastIndex = 0;
    while ((m = KEEP.exec(t))) { out += plain(t.slice(last, m.index)) + m[0]; last = m.index + m[0].length; }
    return out + plain(t.slice(last));
  }
  function walk(node) {
    if (node.nodeType === 3) { var t = cyr(node.nodeValue); if (t !== node.nodeValue) node.nodeValue = t; return; }
    if (node.nodeType !== 1 || /^(SCRIPT|STYLE|CODE|INPUT|TEXTAREA)$/.test(node.tagName)) return;
    ["placeholder", "aria-label", "title", "alt"].forEach(function (a) { if (node.hasAttribute(a)) node.setAttribute(a, cyr(node.getAttribute(a))); });
    for (var c = node.firstChild; c; c = c.nextSibling) walk(c);
  }
  new MutationObserver(function (changes) {
    changes.forEach(function (ch) {
      if (ch.type === "characterData") { var t = cyr(ch.target.nodeValue); if (t !== ch.target.nodeValue) ch.target.nodeValue = t; }
      else ch.addedNodes.forEach(walk);
    });
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
})();

// Za ili Protiv: search and filters. The site's only script, served from the site itself; pages work without it.
(function () {
  "use strict";
  var body = document.body, root = body.dataset.root || "", data = null, loading = null;
  document.querySelectorAll(".js-only").forEach(function (el) { el.hidden = false; });

  // Phones. All of this only marks things; what it means is in the stylesheet's rules for narrow screens, so a wide
  // screen shows the page as it was.
  var phone = window.matchMedia && window.matchMedia("(max-width: 640px)");
  // A long list shows its first rows and a button for more (data-more="30" on the list). Searching, sorting or a
  // link to a row further down shows all of it.
  document.querySelectorAll("[data-more]").forEach(function (list) {
    var step = parseInt(list.dataset.more, 10) || 30, items = Array.prototype.slice.call(list.children);
    if (items.length <= step + 5) return;
    var btn = document.createElement("button"), at = step;
    btn.type = "button"; btn.className = "more-btn";
    function label() { btn.textContent = "Prikaži još " + Math.min(step, items.length - at) + " (od " + items.length + ")"; }
    function all() { items.forEach(function (li) { li.classList.remove("over"); }); list.classList.remove("capped"); btn.remove(); }
    items.slice(step).forEach(function (li) { li.classList.add("over"); });
    list.classList.add("capped"); label();
    list.parentNode.insertBefore(btn, list.nextSibling);
    btn.addEventListener("click", function () {
      items.slice(at, at + step).forEach(function (li) { li.classList.remove("over"); });
      at += step;
      if (at >= items.length) all(); else label();
    });
    var box = document.querySelector('[data-filter~="' + list.id + '"]');
    if (box) { box.addEventListener("input", all); box.addEventListener("change", all); box.addEventListener("click", function (e) { if (e.target.closest(".chip")) all(); }); }
    function target() { var t = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1))); if (t && list.contains(t)) all(); }
    target(); window.addEventListener("hashchange", target);
  });
  // An MP's page: the sections after the first ones fold under their headings; a link to one opens it.
  if (document.querySelector(".mp-hero")) {
    var folds = Array.prototype.filter.call(document.querySelectorAll("main section"), function (sec) {
      var h = sec.firstElementChild;
      return h && h.tagName === "H2" && !/^(kljucna|aktivnost)$/.test(sec.id) && !sec.classList.contains("outcome") && !sec.classList.contains("mp-brief");  // "Ukratko" is always open, first on the page
    });
    // On a phone the heading's words become a button that says whether its section is open, so the fold can be
    // worked with a keyboard and a screen reader, not a finger alone; on a wide screen, where nothing folds, the
    // heading is left as it was. A heading with a link in it keeps its click only.
    var said = function (sec) { var b = sec.querySelector("h2 > .fold-btn"); if (b) b.setAttribute("aria-expanded", sec.classList.contains("open") ? "true" : "false"); };
    var buttons = function () {
      var on = !!(phone && phone.matches);
      folds.forEach(function (sec) {
        var h = sec.firstElementChild, b = h.querySelector(":scope > .fold-btn");
        if (on && !b && !h.querySelector("a")) {
          b = document.createElement("button"); b.type = "button"; b.className = "fold-btn";
          while (h.firstChild) b.appendChild(h.firstChild);
          h.appendChild(b);
        } else if (!on && b) {
          while (b.firstChild) h.insertBefore(b.firstChild, b);
          b.remove();
        }
        said(sec);
      });
    };
    folds.forEach(function (sec) {
      sec.classList.add("fold");
      var h = sec.firstElementChild;
      h.addEventListener("click", function (e) { if (!e.target.closest("a") && phone && phone.matches) { sec.classList.toggle("open"); said(sec); } });
    });
    buttons();
    if (phone) { if (phone.addEventListener) phone.addEventListener("change", buttons); else if (phone.addListener) phone.addListener(buttons); }
    var unfold = function () {
      var t = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1)));
      var sec = t && t.closest(".fold");
      if (sec) { sec.classList.add("open"); said(sec); if (phone && phone.matches) t.scrollIntoView(); }
    };
    unfold(); window.addEventListener("hashchange", unfold);
  }

  // A link to a folded list opens it.
  window.addEventListener("hashchange", openTarget); openTarget();
  function openTarget() {
    var t = location.hash && document.getElementById(location.hash.slice(1));
    if (t && t.tagName === "DETAILS") t.open = true;
  }

  // MP page: tabs by period (every convocation, or one); without the script the page shows every convocation.
  document.querySelectorAll(".periods").forEach(function (box) {
    var buttons = box.querySelectorAll("[data-period]"), panels = box.querySelectorAll("[data-panel]");
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        buttons.forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
        panels.forEach(function (p) { p.hidden = p.dataset.panel !== b.dataset.period; });
      });
    });
  });

  // A link to a row that is closed (an MP's harsh words on "Ko najviše") opens it.
  (function () {
    var open = function () {
      var t = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1)));
      var d = t && !(t.tagName === "SECTION" && t.closest(".rules")) && t.querySelector("details");  // a part of the Rules is not a row
      if (d) d.open = true;
    };
    open(); window.addEventListener("hashchange", open);
  })();

  // A row of the roll call: the group and the vote as its cells say them (an empty group as the filter names it).
  function rollGroup(tr) {
    return tr.cells[1].textContent.trim() || (document.documentElement.lang === "sr-Cyrl" ? "Без посланичке групе" : "Bez poslaničke grupe");
  }
  function rollVote(tr) { return (/v-text-([a-z_]+)/.exec(tr.cells[2].className) || [])[1] || ""; }

  // Law page: each seat of the chamber becomes an MP, from the roll call on the page: for from the left, against
  // from the right, and between them those who abstained, did not vote or were absent, each group's MPs together.
  // The order is by vote, not by where anyone sits. Without this script the chamber shows the count only.
  (function () {
    var svg = document.querySelector("#sala .chamber"), table = document.getElementById("roll");
    if (!svg || !table) return;
    var NS = "http://www.w3.org/2000/svg", WORD = { za: "za", protiv: "protiv", uzdrzan: "uzdržan", nije_glasao: "nije glasao", nije_prisutan: "nije prisutan" };
    var by = { za: [], protiv: [], uzdrzan: [], nije_glasao: [], nije_prisutan: [] };
    Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
      var a = tr.querySelector("a"), v = rollVote(tr);
      if (a && by[v]) by[v].push({ name: a.textContent, href: a.getAttribute("href"), group: rollGroup(tr), vote: v });
    });
    Object.keys(by).forEach(function (k) { by[k].sort(function (x, y) { return x.group.localeCompare(y.group, "sr") || x.name.localeCompare(y.name, "sr"); }); });
    var seats = Array.prototype.slice.call(svg.querySelectorAll("circle"));
    var left = by.za.concat(by.uzdrzan, by.nije_glasao, by.nije_prisutan), right = by.protiv.slice().reverse();
    function seat(c, mp) {
      var a = document.createElementNS(NS, "a"), t = document.createElementNS(NS, "title");
      a.setAttribute("href", mp.href);
      t.textContent = mp.name + (mp.group ? ", " + mp.group : "") + ": " + WORD[mp.vote];
      c.setAttribute("class", "s-" + mp.vote);
      c.parentNode.insertBefore(a, c); a.appendChild(t); a.appendChild(c);
    }
    if (left.length + right.length > seats.length) return;  // more names than seats: leave the picture of the count
    left.forEach(function (mp, i) { seat(seats[i], mp); });
    right.forEach(function (mp, i) { seat(seats[seats.length - 1 - i], mp); });
    seats.slice(left.length, seats.length - right.length).forEach(function (c) { c.setAttribute("class", "s-prazno"); });
    svg.classList.add("seated");
    var key = document.querySelector("#sala .chamber-key");
    if (key) {
      // The name under the pointer (or the focused seat) is written out at once, above the key.
      var small = phone && phone.matches;  // a finger cannot hit one seat: there the chamber opens the list by vote
      var who = document.createElement("p"), rest = small ? "Dodirni salu za spisak poslanika po glasu." : "Svako sedište je jedan poslanik: pređi mišem ili dodirni.";
      svg.addEventListener("click", function (e) {
        if (!(phone && phone.matches)) return;
        e.preventDefault();
        var d = table.closest("details");
        if (d) { d.open = true; d.scrollIntoView(); }
      });
      who.className = "chamber-who"; who.setAttribute("aria-live", "polite"); who.textContent = rest;
      key.parentNode.insertBefore(who, key);
      var show = function (e) {
        var a = e.target.closest ? e.target.closest("a") : null;
        who.textContent = a ? a.querySelector("title").textContent : rest;
        who.classList.toggle("on", !!a);
      };
      svg.addEventListener("mouseover", show); svg.addEventListener("focusin", show);
      svg.addEventListener("mouseleave", function () { who.textContent = rest; who.classList.remove("on"); });
      key.hidden = false;
      key.innerHTML = ['uzdrzan', 'nije_glasao', 'nije_prisutan'].filter(function (k) { return by[k].length; }).map(function (k) {
          return '<span class="key-dot s-' + k + '"></span>' + WORD[k] + ' ' + by[k].length; }).join(' · ') +
        '<br>Raspored je po glasu, ne po mestu u sali.';
    }
  })();

  // Law page: the roll call filtered by group and by vote.
  var roll = document.getElementById("roll"), rg = document.getElementById("r-g"), rv = document.getElementById("r-v");
  if (roll && rg && rv) {
    var filterRoll = function () {
      var shown = 0, rows = roll.tBodies[0].rows;
      for (var i = 0; i < rows.length; i++) {
        var ok = (!rg.value || rollGroup(rows[i]) === rg.value.trim()) && (!rv.value || rollVote(rows[i]) === rv.value);
        rows[i].hidden = !ok; if (ok) shown++;
      }
      document.getElementById("r-n").textContent = shown === rows.length ? "" : "Prikazano " + shown + " od " + rows.length;
    };
    rg.addEventListener("change", filterRoll); rv.addEventListener("change", filterRoll);
  }

  function load() {
    return loading || (loading = fetch((body.dataset.data || root) + "podaci.json?v=" + (body.dataset.v || "")).then(function (r) { return r.json(); })
      .then(function (d) { data = d; return d; }));
  }
  // "Đorđe", "Djordje" and "dorde" all match.
  function norm(s) {
    return s.toLowerCase().replace(/[\u0400-\u045f]/g, function (c) { return CYR[c] || c; }).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/dj/g, "d");
  }
  // Case endings off, so "budžetu" finds "budžet" and "Vučiću" finds "Vučić". Short words stay whole.
  function stem(w) {
    var m = w.length > 4 && w.match(/^(.{4,}?)(ovima|evima|ama|ima|om|em|og|eg|oj|ih|im|a|e|i|o|u)$/);
    return m ? m[1] : w;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  var MONTHS = ["januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar", "decembar"];
  function day(iso) {
    if (!iso) return "";
    var p = iso.split("-");
    return parseInt(p[2], 10) + ". " + MONTHS[parseInt(p[1], 10) - 1] + " " + p[0] + ".";
  }

  // Search: laws by short and official name, MPs by name. The field is a combobox: the arrows move through what is
  // offered and Enter opens it. The last row, and Enter with nothing chosen, take the words to the search of the
  // whole text (pretraga.html), so a name or a title not found here is never the end of the way.
  function search(input, list, kinds) {
    if (!input || !list) return;
    var at = -1;
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", list.id); input.setAttribute("aria-expanded", "false");
    list.setAttribute("role", "listbox"); list.setAttribute("aria-label", "Predlozi");
    function whole() { return root + "pretraga" + ".html" + "?q=" + encodeURIComponent(input.value.trim()); }
    function rows() { return list.querySelectorAll("a"); }
    function mark(i) {
      var all = rows();
      at = i;
      Array.prototype.forEach.call(all, function (a, k) { a.classList.toggle("on", k === at); a.setAttribute("aria-selected", k === at ? "true" : "false"); });
      if (at >= 0) { input.setAttribute("aria-activedescendant", all[at].id); if (all[at].scrollIntoView) all[at].scrollIntoView({ block: "nearest" }); }
      else input.removeAttribute("aria-activedescendant");
    }
    function show() {
      var q = norm(input.value.trim());
      list.textContent = ""; at = -1; input.removeAttribute("aria-activedescendant");
      if (q.length < 2 || !data) { list.hidden = true; input.setAttribute("aria-expanded", "false"); return; }
      var words = q.split(/\s+/).map(stem), hits = [];
      function has(text) { var t = norm(text); return words.every(function (w) { return t.indexOf(w) >= 0; }); }
      if (kinds.indexOf("mp") >= 0) data.mps.forEach(function (m) {
        if (hits.length < 6 && has(m.n)) hits.push({ href: "poslanik/" + m.s + ".html", title: m.n, sub: m.g || "poslanik" });
      });
      var n = hits.length;
      if (kinds.indexOf("law") >= 0) data.laws.forEach(function (l) {
        if (hits.length < n + 8 && has(l.t + " " + l.f)) hits.push({ href: "zakon/" + l.s + ".html", title: l.t, sub: day(l.d) + (l.za != null ? " · " + l.za + " za, " + l.pr + " protiv" : "") });
      });
      zipCount("pretraga.polje");
      if (!hits.length) zipCount("pretraga.polje-nema");
      if (!hits.length) hits.push({ title: kinds.indexOf("law") >= 0 ? "Nema zakona ni poslanika sa tim rečima u nazivu ili imenu" : "Nema poslanika sa tim imenom", sub: "" });
      hits.push({ all: true, title: "Traži u celom tekstu sajta", sub: "sažeci zakona, rasprave i stenografske beleške, govor po govor" });
      hits.forEach(function (h, k) {
        var li = el("li"), a = el(h.href || h.all ? "a" : "span", h.all ? "hits-all" : null, h.title);
        li.setAttribute("role", "presentation");
        if (h.all) a.href = whole(); else if (h.href) a.href = root + h.href; else a.className = "hits-none";
        if (a.href) { a.id = list.id + "-" + k; a.setAttribute("role", "option"); a.setAttribute("aria-selected", "false"); }
        if (h.sub) a.appendChild(el("small", null, h.sub));
        li.appendChild(a); list.appendChild(li);
      });
      list.hidden = false; input.setAttribute("aria-expanded", "true");
    }
    // What is taken from the list is counted (a sum per day, never the words): a name or title, or the whole text.
    list.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("a");
      if (a) zipCount(a.classList.contains("hits-all") ? "pretraga.polje-ceo" : "pretraga.polje-izbor");
    });
    input.addEventListener("focus", function () { load().then(show); });
    input.addEventListener("input", function () { load().then(show); });
    input.addEventListener("keydown", function (e) {
      var all = rows();
      if (e.key === "Escape") { input.value = ""; show(); }
      else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && !list.hidden && all.length) {
        e.preventDefault();
        mark(e.key === "ArrowDown" ? (at + 1 >= all.length ? -1 : at + 1) : (at < 0 ? all.length - 1 : at - 1));
      } else if (e.key === "Enter" && input.value.trim().length >= 2) {
        e.preventDefault();
        var pick = at >= 0 && all[at];
        zipCount(pick && !pick.classList.contains("hits-all") ? "pretraga.polje-izbor" : "pretraga.polje-ceo");
        location.href = pick ? all[at].href : whole();
      }
    });
  }
  search(document.getElementById("q"), document.getElementById("hits"), ["mp", "law"]);
  search(document.getElementById("qmp"), document.getElementById("hits-mp"), ["mp"]);

  // Filters over the list of laws.
  var list = document.getElementById("lista"), more = document.getElementById("jos"), saziv = document.getElementById("saziv");
  var heading = document.getElementById("lista-naslov"), chips = document.querySelectorAll(".chip[data-f]");
  if (!list || !chips.length) return;
  // On a phone the list opens with three laws, as the page is a long way down already; "Prikaži još" brings the rest.
  var FIRST = window.matchMedia && window.matchMedia("(max-width: 640px)").matches ? 3 : 8;
  var filter = "protiv", shown = FIRST;
  var TITLES = { protiv: "Zakoni koji su podelili Skupštinu", novi: "Najnoviji zakoni", hitan: "Usvojeni po hitnom postupku",
                 finance: "Budžet i javne finansije", treaty: "Međunarodni ugovori" };
  function rows() {
    var c = saziv ? saziv.value : "";
    var xs = data.laws.filter(function (l) {
      if (c && l.c !== c) return false;
      if (filter === "protiv") return l.pr > 0;
      if (filter === "hitan") return l.u === 1;
      if (filter === "finance" || filter === "treaty") return l.k === filter;
      return true;
    });
    xs.sort(filter === "protiv"
      ? function (a, b) { return b.sh - a.sh || b.pr - a.pr || (a.d < b.d ? 1 : -1); }
      : function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : 0; });
    return xs;
  }
  function render() {
    var xs = rows();
    list.textContent = "";
    list.classList.add("live");  // from here the script decides how many show (see the phone's rule in style.css)
    heading.textContent = TITLES[filter];
    xs.slice(0, shown).forEach(function (l, i) {
      var li = el("li", "row");
      if (filter === "protiv") li.appendChild(el("span", "row-n", String(i + 1)));
      var main = el("div", "row-main"), a = el("a", "row-title", l.t);
      a.href = root + "zakon/" + l.s + ".html";
      main.appendChild(a);
      main.appendChild(el("p", "row-meta", day(l.d) + (l.u ? " · hitan postupak" : "")));
      li.appendChild(main);
      if (l.za != null) {
        var vote = el("div", "row-vote"), bar = el("div", "bar");
        bar.setAttribute("role", "img");
        bar.setAttribute("aria-label", l.za + " za, " + l.pr + " protiv");
        var total = l.n || 250;
        [["v-za", l.za], ["v-protiv", l.pr]].forEach(function (p) {
          var s = el("span", p[0]); s.style.width = (100 * p[1] / total) + "%"; bar.appendChild(s);
        });
        var score = el("span", "row-score");
        score.appendChild(el("span", "t-za", String(l.za)));
        score.appendChild(document.createTextNode(" : "));
        score.appendChild(el("span", "t-protiv", String(l.pr)));
        vote.appendChild(bar); vote.appendChild(score); li.appendChild(vote);
      }
      list.appendChild(li);
    });
    if (!xs.length) list.appendChild(el("li", "row", "Nema zakona za ovaj izbor."));
    more.hidden = xs.length <= shown;
    more.textContent = "Prikaži još (" + Math.max(0, xs.length - shown) + ")";
  }
  chips.forEach(function (chip) {
    chip.setAttribute("aria-pressed", chip.classList.contains("on") ? "true" : "false");
    chip.addEventListener("click", function () {
      chips.forEach(function (c) { c.classList.remove("on"); c.setAttribute("aria-pressed", "false"); });
      chip.classList.add("on"); chip.setAttribute("aria-pressed", "true");
      filter = chip.dataset.f; shown = FIRST;
      load().then(render);
    });
  });
  if (saziv) saziv.addEventListener("change", function () { shown = FIRST; load().then(render); });
  more.addEventListener("click", function () { shown += 20; load().then(render); });
})();

// Beside a law in any list, the visitor's own vote on it, if they have cast one (kept in this browser by glas.js
// and the quiz; read here, sent nowhere).
(function () {
  var votes;
  try { votes = JSON.parse(localStorage.getItem("zip.glasovi")) || {}; } catch (e) { return; }
  var WORD = { z: "za", p: "protiv", u: "uzdržan" };
  if (!Object.keys(votes).length) return;
  function mark(scope) {
    scope.querySelectorAll("a.row-title[href*='zakon/']").forEach(function (a) {
      var slug = (a.getAttribute("href").split("zakon/")[1] || "").replace(/\.html$/, "").split(/[?#]/)[0], v = votes[slug];
      if (!WORD[v] || (a.nextElementSibling && a.nextElementSibling.classList.contains("my-vote"))) return;
      var chip = document.createElement("span");
      chip.className = "my-vote " + v; chip.textContent = "tvoj glas: " + WORD[v];
      a.insertAdjacentElement("afterend", chip);
    });
  }
  mark(document);
  // lists the page's scripts fill later (the home page's, "show more")
  if (window.MutationObserver) document.querySelectorAll("ol.rows").forEach(function (list) {
    new MutationObserver(function () { mark(list); }).observe(list, { childList: true });
  });
})();

// Lists that are already on the page (all laws, all MPs of a convocation): search, filter and sort the rows in place.
(function () {
  "use strict";
  var box = document.querySelector("[data-filter]");
  if (!box) return;
  // One list, or several named one after the other (the Rules' terms and articles): the same words look through all.
  var lists = box.dataset.filter.split(" ").map(function (id) { return document.getElementById(id); }).filter(Boolean);
  var list = lists[0], rows = lists.reduce(function (all, l) { return all.concat(Array.prototype.slice.call(l.children)); }, []);
  var q = document.getElementById("f-q"), sort = document.getElementById("f-sort"), group = document.getElementById("f-g");
  var area = document.getElementById("f-a"), year = document.getElementById("f-y");
  var count = document.getElementById("f-n"), chips = box.querySelectorAll(".chip[data-k]"), kind = "";
  function norm(s) {
    return s.toLowerCase().replace(/[\u0400-\u045f]/g, function (c) { return CYR[c] || c; }).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/dj/g, "d");
  }
  // Case endings off, so "budžetu" finds "budžet" and "Vučiću" finds "Vučić". Short words stay whole.
  function stem(w) {
    var m = w.length > 4 && w.match(/^(.{4,}?)(ovima|evima|ama|ima|om|em|og|eg|oj|ih|im|a|e|i|o|u)$/);
    return m ? m[1] : w;
  }
  rows.forEach(function (r) { r._t = norm(r.querySelector(".row-main").textContent); });
  function apply() {
    var words = norm(q.value.trim()).split(/\s+/).filter(Boolean).map(stem), shown = 0;
    var quiet = box.hasAttribute("data-quiet") && !words.length;  // a list that shows nothing until something is typed
    rows.forEach(function (r) {
      var ok = words.every(function (w) {  // a number, where the rows have theirs, is the row's own ("104" is the article, not a mention)
        return r.dataset.n && /^\d+$/.test(w) ? (" " + r.dataset.n + " ").indexOf(" " + w + " ") >= 0 : r._t.indexOf(w) >= 0; })
        && (!kind || (" " + r.dataset.k + " ").indexOf(" " + kind + " ") >= 0)
        && (!group || !group.value || r.dataset.g === group.value)
        && (!area || !area.value || (" " + (r.dataset.a || "")).indexOf(" " + area.value + " ") >= 0)
        && (!year || !year.value || (r.dataset.d || "").slice(0, 4) === year.value);
      r.hidden = !ok || quiet;
      if (ok) shown++;
    });
    box.classList.toggle("on", words.length > 0);
    count.textContent = quiet || shown === rows.length ? "" : (!shown && box.dataset.none || "Prikazano " + shown + " od " + rows.length);  // nothing found: the list's own sentence, or the count
  }
  function order() {
    var key = sort ? sort.value : "";
    var sorted = rows.slice().sort(function (a, b) {
      if (key === "d") return a.dataset.d < b.dataset.d ? 1 : a.dataset.d > b.dataset.d ? -1 : 0;
      if (key) return parseFloat(b.dataset[key]) - parseFloat(a.dataset[key]);
      return parseInt(a.dataset.i, 10) - parseInt(b.dataset.i, 10);
    });
    sorted.forEach(function (r) { list.appendChild(r); });
  }
  q.addEventListener("input", apply);
  if (group) group.addEventListener("change", apply);
  if (area) area.addEventListener("change", apply);
  if (year) year.addEventListener("change", apply);
  if (sort) sort.addEventListener("change", order);
  chips.forEach(function (chip) {
    chip.setAttribute("aria-pressed", chip.classList.contains("on") ? "true" : "false");
    chip.addEventListener("click", function () {
      chips.forEach(function (c) { c.classList.remove("on"); c.setAttribute("aria-pressed", "false"); });
      chip.classList.add("on"); chip.setAttribute("aria-pressed", "true");
      kind = chip.dataset.k; apply();
    });
  });
})();

// The live bar (on the home page, its strip) names who is speaking now and since when, read from "Ko sada govori"
// (our own service's state, kept two seconds by Cloudflare); asked for only while the bar is on the page, every half
// a minute, and left as it was built when the service doesn't answer.
(function () {
  var el = document.querySelector(".live-who[data-src], .mic-who[data-src]");
  if (!el || !window.fetch) return;
  var strip = el.classList.contains("mic-who"), was = el.textContent;
  var cyr = document.documentElement.lang === "sr-Cyrl";
  var MAP = {"lj":"љ","nj":"њ","dž":"џ","Lj":"Љ","Nj":"Њ","Dž":"Џ","a":"а","b":"б","v":"в","g":"г","d":"д","đ":"ђ","e":"е","ž":"ж","z":"з","i":"и","j":"ј","k":"к","l":"л","m":"м","n":"н","o":"о","p":"п","r":"р","s":"с","t":"т","ć":"ћ","u":"у","f":"ф","h":"х","c":"ц","č":"ч","š":"ш","A":"А","B":"Б","V":"В","G":"Г","D":"Д","Đ":"Ђ","E":"Е","Ž":"Ж","Z":"З","I":"И","J":"Ј","K":"К","L":"Л","M":"М","N":"Н","O":"О","P":"П","R":"Р","S":"С","T":"Т","Ć":"Ћ","U":"У","F":"Ф","H":"Х","C":"Ц","Č":"Ч","Š":"Ш"};
  function script(t) { return cyr ? t.replace(/lj|nj|dž|Lj|Nj|Dž|[a-zA-ZđĐžŽćĆčČšŠ]/g, function (m) { return MAP[m] || m; }) : t; }
  function first(name) { var p = name.split(" "); return p.slice(-1).concat(p.slice(0, -1)).join(" "); }
  function ask() {
    fetch(el.getAttribute("data-src")).then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
      var c = s && s.stanje === "govori" && s.sada;
      if (!c) { if (strip) el.textContent = was; else el.hidden = true; return; }
      var d = new Date(c.od * 1000), at = d.toLocaleTimeString("sr-Latn-RS", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Belgrade" });
      el.textContent = strip ? script("Sada govori " + first(c.ime) + ", od " + at) : script(" (" + first(c.ime) + ", od " + at + ")");
      el.hidden = false;
    }).catch(function () {});
  }
  ask();
  setInterval(function () { if (!document.hidden) ask(); }, 30000);
})();

// An MP's page says when that MP is on the floor now, with the way to the broadcast (the same state the live bar
// reads; asked for only on an MP's page that has the line, every half a minute).
(function () {
  var el = document.querySelector(".mp-live[data-src]");
  if (!el || !window.fetch || el.getAttribute("data-src").indexOf("http") !== 0) return;
  function ask() {
    fetch(el.getAttribute("data-src")).then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
      el.hidden = !(s && s.stanje === "govori" && s.sada && s.sada.adresa === el.getAttribute("data-slug"));
    }).catch(function () {});
  }
  ask();
  setInterval(function () { if (!document.hidden) ask(); }, 30000);
})();

// A phone's row of convocations scrolls sideways: the one the page is of is brought into sight.
(function () {
  var on = document.querySelector(".tabs a[aria-current]"), row = on && on.parentNode;
  if (row && row.scrollWidth > row.clientWidth) row.scrollLeft = Math.max(0, on.offsetLeft - row.offsetLeft - 16);
})();

// The phone's menu at the bottom (23 Nov 2026): away while the page is read down, back at the first move up or near the
// top; "Još" closes on a press elsewhere and keeps the bar while open. The part of the site the page is in is marked.
(function () {
  var bar = document.querySelector(".dno"), root = document.documentElement;
  if (!bar) return;
  var more = bar.querySelector("details"), at = window.scrollY, moved = 0;
  var path = location.pathname.replace(/^\/cir\//, "/").slice(1);
  Array.prototype.forEach.call(bar.querySelectorAll("a[data-at]"), function (a) {
    if (path.indexOf(a.getAttribute("data-at")) === 0) a.setAttribute("aria-current", "true");
  });
  window.addEventListener("scroll", function () {
    // held within the page: the bounce at either end of an iPhone's page is no move of the reader's
    var y = Math.max(0, Math.min(window.scrollY, root.scrollHeight - window.innerHeight)), d = y - at;
    at = y;
    if (!d || more.open) return;
    moved = (d > 0) === (moved > 0) ? moved + d : d;
    if (y < 80 || moved < -12) root.classList.remove("dno-away");
    else if (moved > 24) root.classList.add("dno-away");
  }, { passive: true });
  document.addEventListener("click", function (e) { if (more.open && !more.contains(e.target)) more.open = false; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && more.open) { more.open = false; more.firstElementChild.focus(); } });
})();

// "Uživo" is red while a sitting's broadcast is on. The pages are built once an hour, so in the hours a sitting may be
// on (it was at the build, or its announced start has come) the live page is asked, once a page and when it is come
// back to; left as it was built when it doesn't answer.
(function () {
  var el = document.querySelector(".dno-live[data-src]");
  if (!el || !window.fetch || el.getAttribute("data-src").indexOf("http") !== 0) return;
  var from = +el.getAttribute("data-od"), asked = 0;
  function ask() {
    var now = Date.now() / 1000;
    if (document.hidden || now - asked < 60 || (from && (now < from - 600 || now > from + 57600))) return;
    asked = now;
    fetch(el.getAttribute("data-src")).then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
      if (!s || !s.stanje) return;
      Array.prototype.forEach.call(document.querySelectorAll(".dno-live, .nav-live"), function (a) {
        a.classList.toggle("on", s.stanje !== "nema_prenosa");
      });
    }).catch(function () {});
  }
  ask();
  document.addEventListener("visibilitychange", ask);
})();
