// "Glasaj i ti": one law at a time, the chamber's result after each vote, then who voted as the visitor did.
// Each vote goes to the project's own counter once (law and for/against/abstained, nothing else).
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
    if (end) { summary(); others(); }
  }

  function names(xs) { return xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " i " + xs[xs.length - 1]; }
  var shareText = "";
  function summary() {
    var n = done(), need = Math.max(3, Math.ceil(n / 2));  // one common vote would top the list by chance
    document.getElementById("q-count").textContent = "Glasao si o " + n + " od " + answers.length + " zakona";
    var groups = data.groups.map(function (g) { return { g: g, m: match(g.v) }; }).filter(function (x) { return x.m.both >= need; })
      .sort(function (a, b) { return b.m.share - a.m.share || b.m.both - a.m.both || b.g.m - a.g.m; });
    var mps = data.mps.map(function (p) { return { p: p, m: match(p.v) }; }).filter(function (x) { return x.m.both >= need; })
      .sort(function (a, b) { return b.m.share - a.m.share || b.m.both - a.m.both || a.p.n.localeCompare(b.p.n, "sr"); });
    // MPs first. Many can tie on a few laws: up to three by name, more as a number, and the list below shows them all.
    var top = mps.filter(function (x) { return x.m.share === mps[0].m.share && x.m.both === mps[0].m.both; });
    var name = document.getElementById("q-top-name"), score = document.getElementById("q-top-score");
    var who = !top.length ? "" : top.length <= 3 ? names(top.map(function (x) { return x.p.n; })) :
      top.length + " " + plural(top.length, "poslanik", "poslanika", "poslanika");
    name.textContent = who || "—";
    score.textContent = top.length ? "Isti glas kao ti na " + top[0].m.same + " od " + top[0].m.both + " " +
      plural(top[0].m.both, "zakona", "zakona", "zakona") + " o kojima ste oboje glasali." : "Nijedan poslanik nije glasao o dovoljno istih zakona.";
    var against = answers.filter(function (a) { return a === "p"; }).length;
    card.fact = against === 0 ? "Da se ja pitam, prošlo bi svih " + n + " " + plural(n, "zakon", "zakona", "zakona") + "." :
      against === n ? "Da se ja pitam, ne bi prošao nijedan od " + n + " " + plural(n, "zakona", "zakona", "zakona") + "." :
      "Da se ja pitam, palo bi " + against + " od " + n + " " + plural(n, "zakona", "zakona", "zakona") + ".";
    card.who = who; card.score = top.length ? top[0].m.same + " od " + top[0].m.both : "";
    document.getElementById("q-fact").textContent = card.fact.replace("Da se ja pitam", "Da se ti pitaš") +
      " Skupština je usvojila svih " + answers.length + ".";
    shareText = card.fact + (who ? " Najviše glasova kao ja: " + who + " (" + card.score + ")." : "") + " A ti?";
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(drawCard);
    var ms = document.getElementById("q-mps"), shown = Math.min(Math.max(8, top.length), 40); ms.textContent = "";
    mps.slice(0, shown).forEach(function (x) {
      var li = el("li", "row"), main = el("div", "row-main"), a = el("a", "row-title", x.p.n);
      a.href = "poslanik/" + x.p.s + ".html"; main.appendChild(a);
      if (x.p.g) main.appendChild(el("p", "row-meta", x.p.g));
      li.appendChild(main); li.appendChild(el("div", "row-vote row-score", x.m.same + " od " + x.m.both)); ms.appendChild(li);
    });
    document.getElementById("q-mps-note").textContent = top.length > shown ? "Prikazano prvih " + shown + " od " + top.length +
      " poslanika sa istim brojem, po azbučnom redu." : "";
    var gs = document.getElementById("q-groups"); gs.textContent = "";
    groups.forEach(function (x) {
      var tr = el("tr"), td = el("td"), a = el("a", null, x.g.n), cell = el("td", "vote-cell"), bar = el("div", "bar"), s = el("span", "v-za");
      a.href = "grupa/" + x.g.s + ".html"; td.appendChild(a); tr.appendChild(td);
      s.style.width = (100 * x.m.share) + "%"; bar.appendChild(s); cell.appendChild(bar); tr.appendChild(cell);
      tr.appendChild(el("td", "num", x.m.same + " od " + x.m.both));
      gs.appendChild(tr);
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
      send();
      go(i + 1 < items.length ? i + 1 : "kraj");
      window.scrollTo({ top: strip.getBoundingClientRect().top + window.scrollY - 12 });
    });
  });
  marks.forEach(function (m) {
    m.addEventListener("click", function () { send(); go(m.dataset.go === "kraj" ? "kraj" : +m.dataset.go); });
  });

  // The picture to share, drawn here in the browser: the visitor's ballot, what would have happened had it been
  // up to them, and who voted most like them. Nothing is uploaded; sharing uses the device's own share sheet.
  var COLORS = { z: "#1f5fa8", p: "#c2410c", u: "#8a8f99", "": "#e8e8e8" }, cardBlob = null;
  function wrapText(ctx, text, width, lines) {
    var out = [], line = "";
    text.split(" ").forEach(function (w) {
      var t = line ? line + " " + w : w;
      if (ctx.measureText(t).width <= width) line = t; else { out.push(line); line = w; }
    });
    out.push(line);
    if (out.length > lines) { out = out.slice(0, lines); out[lines - 1] += " …"; }
    return out;
  }
  function drawCard() {
    var c = document.createElement("canvas"), W = 1080, H = 1350, P = 84, ctx = c.getContext("2d"), y;
    var serif = '"Source Serif 4", Georgia, serif', sans = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    c.width = W; c.height = H;
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, W, H);
    ctx.textBaseline = "alphabetic";
    ctx.font = "700 52px " + serif;
    var x = P; [["Za", COLORS.z], [" ili ", "#111"], ["Protiv", COLORS.p]].forEach(function (p) {
      ctx.fillStyle = p[1]; ctx.fillText(p[0], x, 130); x += ctx.measureText(p[0]).width;
    });
    ctx.fillStyle = "#111"; ctx.fillRect(P, 160, W - 2 * P, 6);
    ctx.fillStyle = "#555"; ctx.font = "400 38px " + sans; ctx.fillText("Kako bih ja glasao u Skupštini", P, 236);
    ctx.fillStyle = "#111"; ctx.font = "700 96px " + serif; y = 370;
    wrapText(ctx, card.fact, W - 2 * P, 3).forEach(function (l) { ctx.fillText(l, P, y); y += 108; });
    // the ballot: one square per law
    var n = answers.length, gap = 14, size = Math.min(96, (W - 2 * P - gap * (n - 1)) / n); y += 10;
    answers.forEach(function (a, i) {
      ctx.fillStyle = COLORS[a]; ctx.fillRect(P + i * (size + gap), y, size, size);
      ctx.fillStyle = a ? "#fff" : "#888"; ctx.font = "700 " + Math.round(size * .42) + "px " + sans; ctx.textAlign = "center";
      ctx.fillText(String(i + 1), P + i * (size + gap) + size / 2, y + size * .65); ctx.textAlign = "left";
    });
    y += size + 48;
    ctx.font = "400 30px " + sans; x = P;
    [["za", COLORS.z], ["protiv", COLORS.p], ["uzdržan", COLORS.u]].forEach(function (k) {
      ctx.fillStyle = k[1]; ctx.fillRect(x, y - 24, 26, 26); ctx.fillStyle = "#555"; ctx.fillText(k[0], x + 38, y);
      x += 38 + ctx.measureText(k[0]).width + 40;
    });
    if (card.who) {
      y += 120; ctx.fillStyle = "#555"; ctx.font = "400 38px " + sans; ctx.fillText("Najviše glasova kao ja", P, y);
      ctx.fillStyle = "#111"; ctx.font = "700 60px " + serif; y += 74;
      wrapText(ctx, card.who, W - 2 * P, 3).forEach(function (l) { ctx.fillText(l, P, y); y += 70; });
      ctx.fillStyle = "#555"; ctx.font = "400 36px " + sans; ctx.fillText("isti glas na " + card.score + " zakona", P, y - 8);
    }
    ctx.fillStyle = "#111"; ctx.fillRect(P, H - 150, W - 2 * P, 3);
    ctx.font = "700 44px " + serif; ctx.fillText("A ti?", P, H - 78);
    ctx.font = "400 38px " + sans; ctx.fillStyle = "#555"; ctx.textAlign = "right";
    ctx.fillText(location.host ? location.host + "/glasaj.html" : "zailiprotiv.rs/glasaj.html", W - P, H - 78); ctx.textAlign = "left";
    var img = document.getElementById("q-card");
    img.alt = card.fact + " " + (card.who ? "Najviše glasova kao ja: " + card.who + " (" + card.score + ")." : "");
    c.toBlob(function (blob) {
      cardBlob = blob;
      var url = URL.createObjectURL(blob);
      img.src = url; document.getElementById("q-save").href = url;
    }, "image/png");
  }
  var card = { fact: "", who: "", score: "" };
  function note(text) { document.getElementById("q-shared").textContent = text; }
  function shareUrl() { return location.protocol === "file:" ? "https://zailiprotiv.rs/glasaj.html" : location.href.split("#")[0]; }
  function copyText() {
    var text = shareText + " " + shareUrl();
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject())
      .then(function () { note("Kopirano. Nalepi u poruku ili objavu."); })
      .catch(function () { note(text); });
  }
  document.getElementById("q-copy").addEventListener("click", copyText);
  document.getElementById("q-share").addEventListener("click", function () {
    var file = cardBlob && window.File ? new File([cardBlob], "kako-bih-ja-glasao.png", { type: "image/png" }) : null;
    if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
      navigator.share({ files: [file], text: shareText + " " + shareUrl() }).catch(function () {});
    } else if (navigator.share) {
      navigator.share({ text: shareText, url: shareUrl() }).catch(function () {});
    } else {  // a computer without a share sheet: the picture is saved, the text copied
      document.getElementById("q-save").click(); copyText();
      note("Slika je sačuvana, a tekst sa linkom kopiran. Dodaj ih u poruku ili objavu.");
    }
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
  var sentLaws = {};
  try { sentLaws = JSON.parse(localStorage.getItem(SENT) || "{}"); } catch (e) {}
  if (!sentLaws || typeof sentLaws !== "object") sentLaws = {};
  // What visitors chose for a law: the counter's totals, plus this visitor's own vote while it is not sent yet.
  function crowdOf(i) {
    var law = data.laws[i].s, c = (crowd && crowd[law]) || { z: 0, p: 0, u: 0 };
    c = { z: c.z, p: c.p, u: c.u };
    if (answers[i] && !sentLaws[law]) c[answers[i]]++;
    c.n = c.z + c.p + c.u;
    return c;
  }
  function showCrowd() {
    if (!api) return;
    items.forEach(function (item, i) {
      var box = item.querySelector(".q-crowd"), c = crowdOf(i);
      box.hidden = !(answers[i] && c.n);
      if (box.hidden) return;
      var bars = box.querySelectorAll(".q-hall span");
      [c.z, c.p, c.u].forEach(function (n, k) { bars[k].style.width = (100 * n / c.n) + "%"; });
      box.querySelector(".q-crowd-key").textContent = c.z + " za, " + c.p + " protiv" + (c.u ? ", " + c.u + " uzdržano" : "") +
        (c.n < 10 ? " (za sada samo " + c.n + " " + plural(c.n, "glas", "glasa", "glasova") + ")" : "");
    });
    if (at === "kraj") others();
  }
  // At the end: every law, the chamber beside the visitors.
  function others() {
    var body = document.getElementById("q-others"), any = false;
    if (!body) return;
    body.textContent = "";
    items.forEach(function (item, i) {
      var c = crowdOf(i), tr = el("tr"), td = el("td"), a = el("a", null, item.querySelector("h2").textContent);
      if (c.n) any = true;
      a.href = item.querySelector("h2 a").getAttribute("href"); td.appendChild(a); tr.appendChild(td);
      tr.appendChild(el("td", "num" + (answers[i] ? " v-text-" + { z: "za", p: "protiv", u: "uzdrzan" }[answers[i]] : ""), answers[i] ? WORD[answers[i]] : "—"));
      tr.appendChild(el("td", "num", item.dataset.za + " : " + item.dataset.protiv));
      var cell = el("td", "vote-cell"), bar = el("div", "bar");
      [["v-za", c.z], ["v-protiv", c.p], ["v-uzdrzan", c.u]].forEach(function (p) {
        if (c.n && p[1]) { var sp = el("span", p[0]); sp.style.width = (100 * p[1] / c.n) + "%"; bar.appendChild(sp); }
      });
      cell.appendChild(bar); tr.appendChild(cell);
      tr.appendChild(el("td", "num", c.n ? c.z + " : " + c.p : "—"));
      body.appendChild(tr);
    });
    document.getElementById("q-others-box").hidden = !any;
  }

  // Each law's vote is sent once, when the visitor moves on from it (the page says so before the first vote).
  function send() {
    if (!api) return;
    var v = {}, any = false;
    answers.forEach(function (a, i) { var law = data.laws[i].s; if (a && !sentLaws[law]) { v[law] = a; any = true; } });
    if (!any) return;
    Object.keys(v).forEach(function (law) { sentLaws[law] = 1; });  // marked first, so a second click can't send twice
    try { localStorage.setItem(SENT, JSON.stringify(sentLaws)); } catch (e) {}
    fetch(api, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ v: v }), keepalive: true })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { crowd = d; showCrowd(); })
      .catch(function () {
        Object.keys(v).forEach(function (law) { delete sentLaws[law]; });  // not counted: try again with the next law
        try { localStorage.setItem(SENT, JSON.stringify(sentLaws)); } catch (e) {}
      });
  }
  if (api) fetch(api).then(function (r) { return r.json(); }).then(function (d) { crowd = d; showCrowd(); }).catch(function () {});

  var first = answers.indexOf("");
  go(first < 0 ? "kraj" : first);
})();
