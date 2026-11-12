// Za ili Protiv: search and filters. The site's only script, served from the site itself; pages work without it.
(function () {
  "use strict";
  var body = document.body, root = body.dataset.root || "", data = null, loading = null;
  document.querySelectorAll(".js-only").forEach(function (el) { el.hidden = false; });

  function load() {
    return loading || (loading = fetch(root + "podaci.json?v=" + (body.dataset.v || "")).then(function (r) { return r.json(); })
      .then(function (d) { data = d; return d; }));
  }
  // "Đorđe", "Djordje" and "dorde" all match.
  function norm(s) {
    return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/dj/g, "d");
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
      var words = q.split(/\s+/), hits = [];
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
  var filter = "protiv", shown = 10;
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
      filter = chip.dataset.f; shown = 10;
      load().then(render);
    });
  });
  if (saziv) saziv.addEventListener("change", function () { shown = 10; load().then(render); });
  more.addEventListener("click", function () { shown += 20; load().then(render); });
})();
