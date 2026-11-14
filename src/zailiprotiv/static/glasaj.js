// "Glasaj i ti": one law at a time, the chamber's result after each vote, then who voted as the visitor did.
// Each vote goes to the project's own counter once (law and for/against/abstained, nothing else).
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("quiz-data").textContent);
  var list = document.getElementById("quiz"), items = Array.prototype.slice.call(list.querySelectorAll(".q-item"));
  var WORD = { z: "za", p: "protiv", u: "uzdržan" };
  var slugs = function () { return data.laws.map(function (l) { return l.s; }); };
  // What is kept for the tab: the answers by law (so the order of the laws may change), and the law to show first.
  var KEY = "glasaj:" + slugs().sort().join("|"), FIRST = "glasaj:prvi", at = 0;
  // A vote cast on the home page's band comes in the address (?z=<law>&g=z|p|u): it is taken as cast here, that law
  // becomes the first of the quiz, and the page opens on it with its result. The address is then cleaned, so a
  // reload does not cast the vote again.
  var came = null;
  try {
    var qp = new URLSearchParams(location.search), qz = qp.get("z"), qg = qp.get("g");
    if (qz && WORD[qg] && slugs().indexOf(qz) >= 0) {
      came = { law: qz, vote: qg };
      try { sessionStorage.setItem(FIRST, qz); } catch (e) {}
    }
    if (qz) history.replaceState(null, "", location.pathname);
  } catch (e) {}
  var lead = null;
  try { lead = sessionStorage.getItem(FIRST); } catch (e) {}
  var from = slugs().indexOf(lead);
  if (from > 0) {  // that law first: in the data (every group's and MP's votes are a letter per law) and on the page
    var move = function (xs) { xs.unshift(xs.splice(from, 1)[0]); return xs; };
    move(data.laws);
    data.groups.concat(data.mps).forEach(function (x) { x.v = move(x.v.split("")).join(""); });
    list.insertBefore(items[from], items[0]);
    move(items);
    items.forEach(function (item, k) {
      var n = item.querySelector(".q-n"), go_ = item.querySelector(".q-go");
      item.dataset.i = k;
      n.textContent = n.textContent.replace(/^Zakon \d+ od/, "Zakon " + (k + 1) + " od");
      go_.textContent = k === items.length - 1 ? "Vidi rezultat" : "Sledeći zakon";
    });
  }
  var strip = document.getElementById("q-strip"), marks = strip.querySelectorAll("[data-go]");
  var result = document.getElementById("rezultat"), answers = items.map(function () { return ""; });
  function keep() {
    var m = {};
    data.laws.forEach(function (l, k) { if (answers[k]) m[l.s] = answers[k]; });
    try { sessionStorage.setItem(KEY, JSON.stringify(m)); } catch (e) {}
  }
  try {
    var saved = JSON.parse(sessionStorage.getItem(KEY) || "null");
    if (saved && !Array.isArray(saved)) answers = data.laws.map(function (l) { return WORD[saved[l.s]] ? saved[l.s] : ""; });
  } catch (e) {}
  var cameWith = came ? slugs().indexOf(came.law) : -1;
  if (cameWith >= 0) { answers[cameWith] = came.vote; keep(); }
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
    // The one MP on the picture: of those level at the top, one with a portrait when there is one (the maintainer,
    // 13 Nov 2026); which of several is fixed by the answers, not chosen by us.
    var faces = top.filter(function (x) { return x.p.f; }), pool = faces.length ? faces : top, cs = 0;
    answers.join("").split("").forEach(function (ch, k) { cs = (cs * 31 + ch.charCodeAt(0) + k) % 9973; });
    card.mp = pool.length ? pool[cs % pool.length].p : null; card.more = Math.max(0, top.length - 1);
    document.getElementById("q-fact").textContent = card.fact.replace("Da se ja pitam", "Da se ti pitaš") +
      " Skupština je usvojila svih " + answers.length + ".";
    // Something the closest MP said (the shortest verbatim quote of the overview of their speeches), when one of
    // those level at the top has one; which of them is taken the same way as the three below.
    var tq = document.getElementById("q-top-quote"), withQuote = top.filter(function (x) { return x.p.q; });
    tq.hidden = !withQuote.length;
    if (withQuote.length) {
      var qs = 0; answers.join("").split("").forEach(function (ch, k) { qs = (qs * 31 + ch.charCodeAt(0) + k) % 9973; });
      var pick = withQuote[qs % withQuote.length], foot = tq.querySelector("footer"), link = el("a", "", pick.p.n);
      tq.querySelector("p").textContent = "„" + pick.p.q + "“";
      link.href = "poslanik/" + pick.p.s + ".html"; foot.textContent = "";
      foot.appendChild(link); foot.appendChild(document.createTextNode(", u raspravi u Skupštini"));
    }
    redraw();
    // Three MPs. When more are level, which three is not ours to choose: they are taken from the level ones starting
    // at a place that depends on the answers, and the page says how many more there are.
    var ms = document.getElementById("q-mps"), three = [], seed = 0; ms.textContent = "";
    answers.join("").split("").forEach(function (ch, k) { seed = (seed * 31 + ch.charCodeAt(0) + k) % 9973; });
    for (var k = 0; k < Math.min(3, top.length); k++) three.push(top[(seed + k) % top.length]);
    mps.slice(top.length).slice(0, 3 - three.length).forEach(function (x) { three.push(x); });
    three.forEach(function (x) {
      var li = el("li", "row"), main = el("div", "row-main"), a = el("a", "row-title", x.p.n);
      { var im = el("img", "q-face"); im.src = x.p.f ? "foto/" + x.p.f : "bez-slike.svg"; im.alt = ""; im.width = 56; im.height = 75; im.loading = "lazy"; li.appendChild(im); }
      a.href = "poslanik/" + x.p.s + ".html"; main.appendChild(a);
      if (x.p.g) main.appendChild(el("p", "row-meta", x.p.g));
      li.appendChild(main); li.appendChild(el("div", "row-vote row-score", x.m.same + " od " + x.m.both)); ms.appendChild(li);
    });
    document.getElementById("q-mps-note").textContent = top.length > 3 ? "Još " + (top.length - 3) + " " +
      plural(top.length - 3, "poslanik ima", "poslanika imaju", "poslanika ima") + " isti broj istih glasova; ova tri su izabrana nasumično." : "";
    var gs = document.getElementById("q-groups"); gs.textContent = "";
    groups.forEach(function (x) {
      var tr = el("tr"), td = el("td"), a = el("a", null, x.g.n), cell = el("td", "vote-cell"), bar = el("div", "bar"), s = el("span", "v-za");
      a.href = "grupa/" + x.g.s + ".html"; td.appendChild(a); tr.appendChild(td);
      s.style.width = (100 * x.m.share) + "%"; bar.appendChild(s); cell.appendChild(bar); tr.appendChild(cell);
      tr.appendChild(el("td", "num", x.m.same + " od " + x.m.both));
      gs.appendChild(tr);
    });
  }

  // After a vote the law's result is shown, and a few seconds later the quiz moves on by itself (the maintainer,
  // 13 Nov 2026); "Sledeći zakon" moves on at once. Anything the visitor does with the result (opening "Više",
  // following a link, changing the vote, moving the pointer over it) stops the clock, and so does a setting for
  // reduced motion: then only the button moves on.
  var AUTO = 4000, timer = null, still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  function stay() {
    if (timer) { clearTimeout(timer); timer = null; }
    list.querySelectorAll(".q-auto.run").forEach(function (b) { b.classList.remove("run"); });
  }
  function advance(i) {
    stay(); send();
    go(i + 1 < items.length ? i + 1 : "kraj");
    window.scrollTo({ top: strip.getBoundingClientRect().top + window.scrollY - 12 });
  }
  function soon(item, i) {
    stay();
    if (still) return;
    var bar = item.querySelector(".q-auto");
    if (bar) { void bar.offsetWidth; bar.classList.add("run"); }
    timer = setTimeout(function () { if (at === i) advance(i); }, AUTO);
  }
  list.classList.add("q-live");
  items.forEach(function (item, i) {
    reveal(item, i, false);
    var next = item.querySelector(".q-go"), bar = el("span", "q-auto");
    bar.setAttribute("aria-hidden", "true");
    next.parentNode.insertBefore(bar, next);
    item.querySelectorAll("[data-a]").forEach(function (b) {
      b.addEventListener("click", function () {
        answers[i] = b.dataset.a;
        keep();
        reveal(item, i, true); go(i); showCrowd();
        next.focus({ preventScroll: true });
        soon(item, i);
      });
    });
    next.addEventListener("click", function () { advance(i); });
    var box = item.querySelector(".q-reveal");
    ["pointerdown", "keydown", "mouseenter", "touchstart"].forEach(function (ev) {
      box.addEventListener(ev, function (e) { if (e.target !== next) stay(); }, { passive: true });
    });
    var more = item.querySelector(".q-more");
    if (more) more.addEventListener("toggle", stay);
  });
  marks.forEach(function (m) {
    m.addEventListener("click", function () { stay(); send(); go(m.dataset.go === "kraj" ? "kraj" : +m.dataset.go); });
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
    // Dark, with one message: the MP who voted most like the visitor (portrait, name, how many votes alike), the
    // ballot as a strip, and "A ti?". Without a matching MP, the fact about the laws takes the name's place.
    var c = document.createElement("canvas"), W = 1080, H = 1350, P = 84, ctx = c.getContext("2d");
    var serif = '"Literata", Georgia, serif', sans = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    var ZA = "#7cc0f5", PROTIV = "#ff9a52", SOFT = "#c9ccd3", TONE = { z: ZA, p: PROTIV, u: "#7d8390", "": "#30343c" };
    c.width = W; c.height = H;
    function paint(face) {
      var y, x;
      ctx.fillStyle = "#111111"; ctx.fillRect(0, 0, W, H);
      ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
      // the mark and the name of the site
      ctx.lineWidth = 19; ctx.strokeStyle = ZA; ctx.beginPath(); ctx.arc(P + 56, 150, 54, Math.PI, Math.PI * 300 / 180); ctx.stroke();
      ctx.strokeStyle = PROTIV; ctx.beginPath(); ctx.arc(P + 56, 150, 54, Math.PI * 310 / 180, Math.PI * 2); ctx.stroke();
      ctx.font = "700 54px " + serif; x = P + 142;
      [["Za", ZA], [" ili ", "#ffffff"], ["Protiv", PROTIV]].forEach(function (p) {
        ctx.fillStyle = p[1]; ctx.fillText(p[0], x, 150); x += ctx.measureText(p[0]).width;
      });
      if (card.mp) {
        ctx.fillStyle = SOFT; ctx.font = "400 46px " + sans; ctx.fillText("U Skupštini glasam kao", P, 282);
        var fw = 330, fh = 440, fy = 322;
        ctx.fillStyle = "#30343c"; ctx.fillRect(P, fy, fw, fh);
        if (face) {  // cover the frame, keeping the portrait's proportions
          var k = Math.max(fw / face.width, fh / face.height), sw = fw / k, sh = fh / k;
          ctx.drawImage(face, (face.width - sw) / 2, Math.max(0, (face.height - sh) / 4), sw, sh, P, fy, fw, fh);
        }
        var nx = P + fw + 50, lines;
        ctx.fillStyle = "#ffffff"; ctx.font = "800 96px " + serif;
        lines = wrapText(ctx, card.mp.n, W - P - nx, 4);
        if (lines.length > 3) { ctx.font = "800 76px " + serif; lines = wrapText(ctx, card.mp.n, W - P - nx, 4); }
        lines = lines.filter(Boolean);
        y = fy + fh - (lines.length - 1) * 102 - 8;
        lines.forEach(function (l) { ctx.fillText(l, nx, y); y += 102; });
        y = fy + fh + 112;
        ctx.fillStyle = PROTIV; ctx.font = "800 92px " + serif; ctx.fillText(card.score, P, y);
        x = P + ctx.measureText(card.score).width + 24;
        ctx.fillStyle = "#ffffff"; ctx.font = "400 46px " + sans; ctx.fillText(plural(+card.score.split(" ").pop(), "isti glas", "ista glasa", "istih glasova"), x, y);
        if (card.more) {
          ctx.fillStyle = SOFT; ctx.font = "400 34px " + sans;
          ctx.fillText("i kao još " + card.more + " " + plural(card.more, "poslanik", "poslanika", "poslanika"), P, y + 58);
        }
      } else {
        ctx.fillStyle = "#ffffff"; ctx.font = "800 104px " + serif; y = 420;
        wrapText(ctx, card.fact, W - 2 * P, 4).forEach(function (l) { ctx.fillText(l, P, y); y += 118; });
      }
      // the ballot: a strip, one piece per law
      var n = answers.length, gap = 12, w = (W - 2 * P - gap * (n - 1)) / n, by = H - 318;
      if (card.mp) { ctx.fillStyle = SOFT; ctx.font = "400 34px " + sans; ctx.fillText(card.fact, P, by - 28); }
      answers.forEach(function (a, i) { ctx.fillStyle = TONE[a]; ctx.fillRect(P + i * (w + gap), by, w, 52); });
      ctx.fillStyle = "#ffffff"; ctx.fillRect(P, H - 206, W - 2 * P, 6);
      ctx.font = "700 64px " + serif; ctx.fillText("A ti?", P, H - 104);
      ctx.font = "400 40px " + sans; ctx.textAlign = "right";
      ctx.fillText((location.host || "zailiprotiv.rs") + "/glasaj", W - P, H - 104); ctx.textAlign = "left";
      var img = document.getElementById("q-card");
      img.alt = (card.mp ? "U Skupštini glasam kao " + card.mp.n + ": " + card.score + " istih glasova. " : "") + card.fact;
      c.toBlob(function (blob) {
        if (!blob) return;
        cardBlob = blob;
        var url = URL.createObjectURL(blob);
        img.src = url; document.getElementById("q-save").href = url;
      }, "image/png");
    }
    var ready = document.fonts && document.fonts.load ? document.fonts.load('800 96px "Literata"').catch(function () {}) : Promise.resolve();
    ready.then(function () {
      if (!card.mp) return paint(null);
      var face = new Image();
      face.onload = function () { paint(face); };
      face.onerror = function () { paint(null); };
      face.src = card.mp.f ? "foto/" + card.mp.f : "bez-slike.svg";
    });
  }
  var card = { fact: "", who: "", score: "", crowd: null, mp: null, more: 0 };
  // On how many laws the visitor voted as most visitors did, among the laws five or more visitors voted on.
  function crowdFact() {
    var same = 0, of = 0;
    answers.forEach(function (a, i) {
      var c = crowdOf(i);
      if (!a || c.n < 5) return;
      of++; if (c[a] >= Math.max(c.z, c.p, c.u)) same++;
    });
    return of ? { same: same, of: of } : null;
  }
  function redraw() {
    card.crowd = api ? crowdFact() : null;
    var line = document.getElementById("q-crowd-fact");
    line.hidden = !card.crowd;
    if (card.crowd) line.textContent = "Na " + card.crowd.same + " od " + card.crowd.of + " " + plural(card.crowd.of, "zakona", "zakona", "zakona") +
      " glasao si kao većina posetilaca sajta.";
    // The words that are copied or shared: the laws of this quiz, the MP on the picture (name first, as people say
    // it; the site lists surnames first), and the question. The link follows.
    var mpName = card.mp ? card.mp.n.replace(/^(.*)\s(\S+)$/, "$2 $1") : "";
    shareText = card.fact.replace(/ zakona\.$/, " ovih zakona.") + (mpName ? " Najviše glasova kao ja: " + mpName + "." : "") + " Koji si ti poslanik?";
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(drawCard);
  }
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
    if (at === "kraj") { others(); redraw(); }
  }
  // At the end: every law, the chamber beside the visitors.
  function others() {
    var box = document.getElementById("q-others"), any = false;
    if (!box) return;
    box.textContent = "";
    function line(label, za, protiv, uzd) {
      var n = za + protiv + uzd, row = el("div", "qo-line"), bar = el("div", "bar");
      row.appendChild(el("span", "qo-who", label));
      [["v-za", za], ["v-protiv", protiv], ["v-uzdrzan", uzd]].forEach(function (p) {
        if (n && p[1]) { var sp = el("span", p[0]); sp.style.width = (100 * p[1] / n) + "%"; bar.appendChild(sp); }
      });
      row.appendChild(bar);
      var nums = el("span", "qo-nums");
      nums.appendChild(el("b", "t-za", za + " za")); nums.appendChild(document.createTextNode(" · "));
      nums.appendChild(el("b", "t-protiv", protiv + " protiv"));
      row.appendChild(nums);
      return row;
    }
    items.forEach(function (item, i) {
      var c = crowdOf(i), li = el("li", "qo-law"), head = el("p", "qo-title"), a = el("a", null, item.querySelector("h2").textContent);
      if (!c.n) return;
      any = true;
      a.href = item.querySelector("h2 a").getAttribute("href"); head.appendChild(a);
      if (answers[i]) {
        head.appendChild(document.createTextNode(" "));
        head.appendChild(el("span", "qo-you v-text-" + { z: "za", p: "protiv", u: "uzdrzan" }[answers[i]], "ti: " + WORD[answers[i]]));
      }
      li.appendChild(head);
      li.appendChild(line("Skupština", +item.dataset.za, +item.dataset.protiv, 0));
      li.appendChild(line("Posetioci", c.z, c.p, c.u));
      box.appendChild(li);
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
  go(cameWith >= 0 ? cameWith : (first < 0 ? "kraj" : first));
  if (cameWith >= 0) { showCrowd(); soon(items[cameWith], cameWith); }
})();
