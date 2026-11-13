// "Glasaj i ti": compares the visitor's votes with groups and MPs. Everything stays in the browser.
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("quiz-data").textContent);
  var items = document.querySelectorAll(".q-item"), answers = new Array(items.length).fill("");
  var result = document.getElementById("rezultat"), KEY = "glasaj:" + data.laws.map(function (l) { return l.s; }).join("|");
  try { var saved = JSON.parse(sessionStorage.getItem(KEY) || "null"); if (saved && saved.length === answers.length) answers = saved; } catch (e) {}
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function match(v) {
    var same = 0, both = 0;
    for (var i = 0; i < answers.length; i++) {
      if (answers[i] && v[i] !== "-") { both++; if (answers[i] === v[i]) same++; }
    }
    return { same: same, both: both, share: both ? same / both : 0 };
  }
  function row(href, name, sub, m) {
    var li = el("li", "row"), main = el("div", "row-main"), a = el("a", "row-title", name);
    a.href = href; main.appendChild(a);
    if (sub) main.appendChild(el("p", "row-meta", sub));
    li.appendChild(main);
    li.appendChild(el("div", "row-vote row-score", m.same + " od " + m.both));
    return li;
  }
  function show() {
    var n = answers.filter(Boolean).length;
    items.forEach(function (item, i) {
      item.querySelectorAll("[data-a]").forEach(function (b) {
        var on = answers[i] === b.dataset.a;
        b.classList.toggle("on", on); b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      item.querySelector(".q-real").hidden = !answers[i];
    });
    result.hidden = n < 3;
    if (n < 3) return;
    document.getElementById("q-count").textContent = "Glasao si o " + n + " od " + answers.length + " zakona.";
    var gs = document.getElementById("q-groups"); gs.textContent = "";
    var need = Math.max(3, Math.ceil(n / 2));  // a group or MP that voted on one or two of them would top the list by chance
    data.groups.map(function (g) { return { g: g, m: match(g.v) }; }).filter(function (x) { return x.m.both >= need; })
      .sort(function (a, b) { return b.m.share - a.m.share || b.m.both - a.m.both || b.g.m - a.g.m; })
      .forEach(function (x) {
        var tr = el("tr"), td = el("td"), a = el("a", null, x.g.n), cell = el("td", "vote-cell"), bar = el("div", "bar"), s = el("span", "v-za");
        a.href = "grupa/" + x.g.s + ".html"; td.appendChild(a); tr.appendChild(td);
        s.style.width = (100 * x.m.share) + "%"; bar.appendChild(s); cell.appendChild(bar); tr.appendChild(cell);
        tr.appendChild(el("td", "num", x.m.same + " od " + x.m.both));
        gs.appendChild(tr);
      });
    var ms = document.getElementById("q-mps"); ms.textContent = "";
    data.mps.map(function (p) { return { p: p, m: match(p.v) }; }).filter(function (x) { return x.m.both >= need; })
      .sort(function (a, b) { return b.m.share - a.m.share || b.m.both - a.m.both || a.p.n.localeCompare(b.p.n, "sr"); })
      .slice(0, 10).forEach(function (x) { ms.appendChild(row("poslanik/" + x.p.s + ".html", x.p.n, x.p.g, x.m)); });
  }
  items.forEach(function (item, i) {
    item.querySelectorAll("[data-a]").forEach(function (b) {
      b.addEventListener("click", function () {
        answers[i] = answers[i] === b.dataset.a ? "" : b.dataset.a;
        try { sessionStorage.setItem(KEY, JSON.stringify(answers)); } catch (e) {}
        show();
      });
    });
  });
  // Visitors' votes: shown under a law once the visitor has answered it; sent only when the visitor asks.
  var api = (document.getElementById("q-api") || {}).dataset ? document.getElementById("q-api").dataset.api : "";
  var crowd = null, SENT = KEY + ":poslato";
  function showCrowd() {
    items.forEach(function (item, i) {
      var p = item.querySelector(".q-crowd"), c = crowd && crowd[data.laws[i].s];
      var n = c ? c.z + c.p + c.u : 0;
      p.hidden = !(answers[i] && n >= 10);  // a handful of votes says nothing
      if (!p.hidden) p.textContent = "Posetioci sajta: " + Math.round(100 * c.z / n) + "% za, " + Math.round(100 * c.p / n) +
        "% protiv (" + n + " glasova)";
    });
  }
  if (api) {
    fetch(api).then(function (r) { return r.json(); }).then(function (d) { crowd = d; showCrowd(); }).catch(function () {});
    var submit = document.getElementById("q-submit"), sent = document.getElementById("q-sent");
    var already = false;
    try { already = !!localStorage.getItem(SENT); } catch (e) {}
    if (already) { submit.disabled = true; sent.textContent = "Već si poslao glasove. Hvala!"; }
    submit.addEventListener("click", function () {
      var v = {};
      answers.forEach(function (a, i) { if (a) v[data.laws[i].s] = a; });
      submit.disabled = true; sent.textContent = "Šaljem…";
      fetch(api, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ v: v }) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) {
          crowd = d; showCrowd(); sent.textContent = "Poslato. Hvala!";
          try { localStorage.setItem(SENT, "1"); } catch (e) {}
        })
        .catch(function () { submit.disabled = false; sent.textContent = "Nije uspelo, pokušaj ponovo kasnije."; });
    });
    items.forEach(function (item) { item.addEventListener("click", function () { setTimeout(showCrowd, 0); }); });
  }

  document.getElementById("q-reset").addEventListener("click", function () {
    answers = answers.map(function () { return ""; });
    try { sessionStorage.removeItem(KEY); } catch (e) {}
    show(); window.scrollTo(0, 0);
  });
  show();
})();
