// "Glasaj i ti": one law at a time, the chamber's result after each vote, then who voted as the visitor did.
// The answers stay in the browser unless the visitor sends them to the counter.
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("quiz-data").textContent);
  var list = document.getElementById("quiz"), items = Array.prototype.slice.call(list.querySelectorAll(".q-item"));
  var strip = document.getElementById("q-strip"), marks = strip.querySelectorAll("[data-go]");
  var result = document.getElementById("rezultat"), answers = items.map(function () { return ""; });
  var KEY = "glasaj:" + data.laws.map(function (l) { return l.s; }).join("|"), at = 0;
  var WORD = { z: "za", p: "protiv", u: "uzdržan" };
  try { var saved = JSON.parse(sessionStorage.getItem(KEY) || "null"); if (saved && saved.length === answers.length) answers = saved; } catch (e) {}
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function plural(n, one, few, many) { return n % 10 === 1 && n % 100 !== 11 ? one : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? few : many); }
  function match(v) {
    var same = 0, both = 0;
    for (var i = 0; i < answers.length; i++) if (answers[i] && v[i] !== "-") { both++; if (answers[i] === v[i]) same++; }
    return { same: same, both: both, share: both ? same / both : 0 };
  }
  function done() { return answers.filter(Boolean).length; }

  // After a vote: what the chamber did, and how many MPs voted the same way.
  function reveal(item, i, animate) {
    var za = +item.dataset.za, protiv = +item.dataset.protiv, rest = +item.dataset.ostali, total = za + protiv + rest || 1;
    var a = answers[i], box = item.querySelector(".q-reveal"), bars = item.querySelectorAll(".q-hall span");
    item.querySelectorAll("[data-a]").forEach(function (b) {
      b.classList.toggle("on", a === b.dataset.a); b.setAttribute("aria-pressed", a === b.dataset.a ? "true" : "false");
    });
    item.classList.toggle("answered", !!a);
    box.hidden = !a;
    if (!a) return;
    var same = a === "z" ? za : a === "p" ? protiv : null;
    item.querySelector(".q-verdict").textContent = same === null ? "Uzdržao si se. Zakon je usvojen." :
      "Glasao si " + WORD[a] + ", kao " + same + " " + plural(same, "poslanik", "poslanika", "poslanika") + ". Zakon je usvojen.";
    var widths = [za, protiv, rest].map(function (n) { return (100 * n / total) + "%"; });
    if (animate) { bars.forEach(function (s) { s.style.width = "0"; }); void box.offsetWidth; }
    bars.forEach(function (s, k) { s.style.width = widths[k]; });
  }

  function go(i) {
    at = i;
    var end = i === "kraj";
    items.forEach(function (item, k) { item.hidden = end || k !== i; });
    result.hidden = !end; list.hidden = end;
    marks.forEach(function (m, k) {
      var a = answers[k];
      m.className = (m.dataset.go === "kraj" ? "q-strip-end" : "") + (a ? " a-" + a : "") + (String(i) === m.dataset.go ? " now" : "");
      if (m.dataset.go === "kraj") m.disabled = done() < 3;
    });
    if (end) summary();
  }

  function names(xs) { return xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " i " + xs[xs.length - 1]; }
  var shareText = "";
  function summary() {
    var n = done(), need = Math.max(3, Math.ceil(n / 2));  // one common vote would top the list by chance
    document.getElementById("q-count").textContent = "Glasao si o " + n + " od " + answers.length + " zakona";
    var groups = data.groups.map(function (g) { return { g: g, m: match(g.v) }; }).filter(function (x) { return x.m.both >= need; })
      .sort(function (a, b) { return b.m.share - a.m.share || b.m.both - a.m.both || b.g.m - a.g.m; });
    var top = groups.filter(function (x) { return groups.length && x.m.share === groups[0].m.share && x.m.both === groups[0].m.both; });
    var name = document.getElementById("q-top-name"), score = document.getElementById("q-top-score");
    // Several groups can vote alike on these laws: three by name, the rest counted, none left unsaid.
    name.textContent = !top.length ? "—" : top.length <= 3 ? names(top.map(function (x) { return x.g.n; })) :
      top.slice(0, 3).map(function (x) { return x.g.n; }).join(", ") + " i još " + (top.length - 3);
    score.textContent = top.length ? top[0].m.same + " od " + top[0].m.both + " " + plural(top[0].m.both, "zakona", "zakona", "zakona") +
      ": isti glas kao većina te grupe" : "Nema grupe koja je glasala o dovoljno istih zakona.";
    shareText = top.length ? "Glasao sam o " + n + " zakona kao poslanik. Najviše istih glasova: " + name.textContent + " (" +
      top[0].m.same + " od " + top[0].m.both + "). A ti?" : "Glasaj o zakonima kao poslanik i vidi ko je glasao kao ti.";
    var gs = document.getElementById("q-groups"); gs.textContent = "";
    groups.forEach(function (x) {
      var tr = el("tr"), td = el("td"), a = el("a", null, x.g.n), cell = el("td", "vote-cell"), bar = el("div", "bar"), s = el("span", "v-za");
      a.href = "grupa/" + x.g.s + ".html"; td.appendChild(a); tr.appendChild(td);
      s.style.width = (100 * x.m.share) + "%"; bar.appendChild(s); cell.appendChild(bar); tr.appendChild(cell);
      tr.appendChild(el("td", "num", x.m.same + " od " + x.m.both));
      gs.appendChild(tr);
    });
    var ms = document.getElementById("q-mps"); ms.textContent = "";
    data.mps.map(function (p) { return { p: p, m: match(p.v) }; }).filter(function (x) { return x.m.both >= need; })
      .sort(function (a, b) { return b.m.share - a.m.share || b.m.both - a.m.both || a.p.n.localeCompare(b.p.n, "sr"); })
      .slice(0, 8).forEach(function (x) {
        var li = el("li", "row"), main = el("div", "row-main"), a = el("a", "row-title", x.p.n);
        a.href = "poslanik/" + x.p.s + ".html"; main.appendChild(a);
        if (x.p.g) main.appendChild(el("p", "row-meta", x.p.g));
        li.appendChild(main); li.appendChild(el("div", "row-vote row-score", x.m.same + " od " + x.m.both)); ms.appendChild(li);
      });
  }

  list.classList.add("q-live");
  items.forEach(function (item, i) {
    reveal(item, i, false);
    item.querySelectorAll("[data-a]").forEach(function (b) {
      b.addEventListener("click", function () {
        answers[i] = b.dataset.a;
        try { sessionStorage.setItem(KEY, JSON.stringify(answers)); } catch (e) {}
        reveal(item, i, true); go(i); showCrowd();
        item.querySelector(".q-go").focus({ preventScroll: true });
      });
    });
    item.querySelector(".q-go").addEventListener("click", function () {
      go(i + 1 < items.length ? i + 1 : "kraj");
      window.scrollTo({ top: strip.getBoundingClientRect().top + window.scrollY - 12 });
    });
  });
  marks.forEach(function (m) {
    m.addEventListener("click", function () { go(m.dataset.go === "kraj" ? "kraj" : +m.dataset.go); });
  });

  // Sharing: the device's own share sheet, or the clipboard. Nothing is sent anywhere by us.
  document.getElementById("q-share").addEventListener("click", function () {
    var url = location.href.split("#")[0], note = document.getElementById("q-shared");
    if (navigator.share) { navigator.share({ text: shareText, url: url }).catch(function () {}); return; }
    (navigator.clipboard ? navigator.clipboard.writeText(shareText + " " + url) : Promise.reject())
      .then(function () { note.textContent = "Kopirano, nalepi gde želiš."; })
      .catch(function () { note.textContent = shareText + " " + url; });
  });
  document.getElementById("q-reset").addEventListener("click", function () {
    answers = answers.map(function () { return ""; });
    try { sessionStorage.removeItem(KEY); } catch (e) {}
    items.forEach(function (item, i) { reveal(item, i, false); });
    go(0); window.scrollTo(0, 0);
  });

  // Visitors' votes: shown under a law once the visitor has answered it; sent only when the visitor asks.
  var apiEl = document.getElementById("q-api"), api = apiEl ? apiEl.dataset.api : "";
  var crowd = null, SENT = KEY + ":poslato";
  function showCrowd() {
    items.forEach(function (item, i) {
      var p = item.querySelector(".q-crowd"), c = crowd && crowd[data.laws[i].s];
      var n = c ? c.z + c.p + c.u : 0;
      p.hidden = !(answers[i] && n >= 10);  // a handful of votes says nothing
      if (!p.hidden) p.textContent = "Posetioci sajta: " + Math.round(100 * c.z / n) + "% za, " + Math.round(100 * c.p / n) +
        "% protiv (" + n + " " + plural(n, "glas", "glasa", "glasova") + ")";
    });
  }
  if (api) {
    fetch(api).then(function (r) { return r.json(); }).then(function (d) { crowd = d; showCrowd(); }).catch(function () {});
    var submit = document.getElementById("q-submit"), sent = document.getElementById("q-sent"), already = false;
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
  }

  var first = answers.indexOf("");
  go(first < 0 ? "kraj" : first);
})();
