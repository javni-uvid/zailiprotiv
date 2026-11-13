// Cyrillic typed into a search box finds Latin text, and the other way round: everything is compared in Latin.
var CYR = { "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e", "ж": "ž", "з": "z", "и": "i", "ј": "j",
  "к": "k", "л": "l", "љ": "lj", "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "ћ": "ć",
  "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "č", "џ": "dž", "ш": "š" };
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
      var d = t && t.querySelector("details");
      if (d) d.open = true;
    };
    open(); window.addEventListener("hashchange", open);
  })();

  // Law page: each seat of the chamber becomes an MP, from the roll call on the page: for from the left, against
  // from the right, and between them those who abstained, did not vote or were absent, each group's MPs together.
  // The order is by vote, not by where anyone sits. Without this script the chamber shows the count only.
  (function () {
    var svg = document.querySelector("#sala .chamber"), table = document.getElementById("roll");
    if (!svg || !table) return;
    var NS = "http://www.w3.org/2000/svg", WORD = { za: "za", protiv: "protiv", uzdrzan: "uzdržan", nije_glasao: "nije glasao", nije_prisutan: "nije prisutan" };
    var by = { za: [], protiv: [], uzdrzan: [], nije_glasao: [], nije_prisutan: [] };
    Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
      var a = tr.querySelector("a"), v = tr.dataset.v;
      if (a && by[v]) by[v].push({ name: a.textContent, href: a.getAttribute("href"), group: tr.dataset.g || "", vote: v });
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
      var who = document.createElement("p"), rest = "Svako sedište je jedan poslanik: pređi mišem ili dodirni.";
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
        var ok = (!rg.value || rows[i].dataset.g === rg.value) && (!rv.value || rows[i].dataset.v === rv.value);
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

  // Search: laws by short and official name, MPs by name.
  function search(input, list, kinds) {
    if (!input || !list) return;
    function show() {
      var q = norm(input.value.trim());
      list.textContent = "";
      if (q.length < 2 || !data) { list.hidden = true; return; }
      var words = q.split(/\s+/).map(stem), hits = [];
      function has(text) { var t = norm(text); return words.every(function (w) { return t.indexOf(w) >= 0; }); }
      if (kinds.indexOf("mp") >= 0) data.mps.forEach(function (m) {
        if (hits.length < 6 && has(m.n)) hits.push({ href: "poslanik/" + m.s + ".html", title: m.n, sub: m.g || "poslanik" });
      });
      var n = hits.length;
      if (kinds.indexOf("law") >= 0) data.laws.forEach(function (l) {
        if (hits.length < n + 8 && has(l.t + " " + l.f)) hits.push({ href: "zakon/" + l.s + ".html", title: l.t, sub: day(l.d) + (l.za != null ? " · " + l.za + " za, " + l.pr + " protiv" : "") });
      });
      if (!hits.length) hits.push({ title: "Nema rezultata", sub: "" });
      hits.forEach(function (h) {
        var li = el("li"), a = el(h.href ? "a" : "span", null, h.title);
        if (h.href) a.href = root + h.href; else a.style.cssText = "display:block;padding:.6rem .9rem";
        if (h.sub) a.appendChild(el("small", null, h.sub));
        li.appendChild(a); list.appendChild(li);
      });
      list.hidden = false;
    }
    input.addEventListener("focus", function () { load().then(show); });
    input.addEventListener("input", function () { load().then(show); });
    input.addEventListener("keydown", function (e) { if (e.key === "Escape") { input.value = ""; show(); } });
  }
  search(document.getElementById("q"), document.getElementById("hits"), ["mp", "law"]);
  search(document.getElementById("qmp"), document.getElementById("hits-mp"), ["mp"]);

  // Filters over the list of laws.
  var list = document.getElementById("lista"), more = document.getElementById("jos"), saziv = document.getElementById("saziv");
  var heading = document.getElementById("lista-naslov"), chips = document.querySelectorAll(".chip[data-f]");
  if (!list || !chips.length) return;
  var filter = "protiv", shown = 8;
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
      filter = chip.dataset.f; shown = 8;
      load().then(render);
    });
  });
  if (saziv) saziv.addEventListener("change", function () { shown = 8; load().then(render); });
  more.addEventListener("click", function () { shown += 20; load().then(render); });
})();

// Lists that are already on the page (all laws, all MPs of a convocation): search, filter and sort the rows in place.
(function () {
  "use strict";
  var box = document.querySelector("[data-filter]");
  if (!box) return;
  var list = document.getElementById(box.dataset.filter), rows = Array.prototype.slice.call(list.children);
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
      var ok = words.every(function (w) { return r._t.indexOf(w) >= 0; })
        && (!kind || (" " + r.dataset.k + " ").indexOf(" " + kind + " ") >= 0)
        && (!group || !group.value || r.dataset.g === group.value)
        && (!area || !area.value || (" " + (r.dataset.a || "")).indexOf(" " + area.value + " ") >= 0)
        && (!year || !year.value || (r.dataset.d || "").slice(0, 4) === year.value);
      r.hidden = !ok || quiet;
      if (ok) shown++;
    });
    count.textContent = quiet || shown === rows.length ? "" : (shown ? "Prikazano " + shown + " od " + rows.length : "Niko pod tim imenom među govornicima ovog saziva.");
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
