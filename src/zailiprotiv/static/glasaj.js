// "Glasaj i ti": one law at a time, the chamber's result after each vote, then who voted as the visitor did.
// Each vote goes to the project's own counter once (law and for/against/abstained, nothing else).
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("quiz-data").textContent);
  var list = document.getElementById("quiz"), items = Array.prototype.slice.call(list.querySelectorAll(".q-item"));
  var takeOver = function () { list.classList.add("on"); };  // from here the script shows and hides the laws
  var WORD = { z: "za", p: "protiv", u: "uzdržan" };
  var ROOT = document.body.dataset.root || "";
  // Addresses are made only of what the site's own data may hold: a slug, or a portrait's file name.
  var slug = function (s) { return /^[a-z0-9][a-z0-9-]*$/.test(s || "") ? s : ""; };
  var used = function (what) { if (window.zipCount && ready) window.zipCount(what); }, ready = false;  // site.js
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
    data.groups.forEach(function (x) { x.v = move(x.v.split("")).join(""); });
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
    // Failing the tab's own answers, the visitor's ballot: what they voted on these laws before, here or on a law's page.
    if (!saved) saved = JSON.parse(localStorage.getItem("zip.glasovi") || "null");
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
  // The visitor beside the chamber, law by law: on how many the visitor voted as most MPs did, and the vote shared
  // with the fewest MPs (the visitor's "loneliest" vote). Nothing about any one MP or group.
  function hall(i) { var d = items[i].dataset; return { z: +d.za, p: +d.protiv, rest: +d.ostali }; }
  function versus() {
    var same = 0, of = 0, lonely = null;
    answers.forEach(function (a, i) {
      if (!a) return;
      var h = hall(i);
      of++;
      if (a === (h.z >= h.p ? "z" : "p")) same++;
      if (a !== "u" && (!lonely || h[a] < lonely.n)) lonely = { n: h[a], a: a };
    });
    return { same: same, of: of, lonely: lonely };
  }
  function lonelyText(l) {
    return !l ? "" : l.n === 0 ? "Jednom je tvoj glas bio " + WORD[l.a] + " kad ničiji u sali nije." :
      "Najusamljeniji glas: " + WORD[l.a] + ", kao samo " + l.n + " " + plural(l.n, "poslanik", "poslanika", "poslanika") + ".";
  }

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
    item.querySelector(".q-verdict").textContent = same === null ? "Tvoj glas: uzdržan. Zakon je usvojen." :
      "Tvoj glas: " + WORD[a] + ", kao " + same + " " + plural(same, "poslanik", "poslanika", "poslanika") + ". Zakon je usvojen.";
    // Halfway through, a first look at who votes like the visitor: something of their own for whoever stops here.
    var old = item.querySelector(".q-half");
    if (old) old.remove();
    var half = Math.ceil(answers.length / 2), n = done();
    if (animate && n === half && n < answers.length) {
      var vs = versus();
      if (vs.of) {
        var note = document.createElement("p");
        note.className = "q-half";
        note.textContent = "Na pola si. Zasad glasaš kao većina u sali na " + vs.same + " od " + vs.of + ". Još " +
          (answers.length - n) + " do celog rezultata.";
        box.insertBefore(note, box.firstChild);
      }
    }
    var widths = [za, protiv, rest].map(function (n) { return (100 * n / total) + "%"; });
    if (animate) { bars.forEach(function (s) { s.style.width = "0"; }); void box.offsetWidth; }
    bars.forEach(function (s, k) { s.style.width = widths[k]; });
  }

  function go(i) {
    at = i;
    var end = i === "kraj";
    items.forEach(function (item, k) { item.hidden = end || k !== i; });
    result.hidden = !end; list.hidden = end;
    if (end) used("kviz.kraj");  // reached now, not a finished quiz the page opens on again
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
    document.getElementById("q-count").textContent = "Tvoji glasovi: " + n + " od " + answers.length + " zakona";
    var groups = data.groups.map(function (g) { return { g: g, m: match(g.v) }; }).filter(function (x) { return x.m.both >= need; })
      .sort(function (a, b) { return b.m.share - a.m.share || b.m.both - a.m.both || b.g.m - a.g.m; });
    // The lead: the visitor beside the chamber (17 Nov 2026: no MP or group is named as "like you").
    var vs = versus();
    document.getElementById("q-top-name").textContent = vs.same + " od " + vs.of + " " + plural(vs.of, "zakona", "zakona", "zakona");
    document.getElementById("q-top-score").textContent = lonelyText(vs.lonely);
    var against = answers.filter(function (a) { return a === "p"; }).length;
    card.fact = against === 0 ? "Da se ja pitam, prošlo bi svih " + n + " " + plural(n, "zakon", "zakona", "zakona") + "." :
      against === n ? "Da se ja pitam, ne bi prošao nijedan od " + n + " " + plural(n, "zakona", "zakona", "zakona") + "." :
      "Da se ja pitam, palo bi " + against + " od " + n + " " + plural(n, "zakona", "zakona", "zakona") + ".";
    card.vs = vs;
    document.getElementById("q-fact").textContent = card.fact.replace("Da se ja pitam", "Da se ti pitaš") +
      " Skupština je usvojila svih " + answers.length + ".";
    redraw();
    var gs = document.getElementById("q-groups"); gs.textContent = "";
    groups.forEach(function (x) {
      var tr = el("tr"), td = el("td"), a = el("a", null, x.g.n), cell = el("td", "vote-cell"), bar = el("div", "bar"), s = el("span", "v-za");
      a.href = ROOT + "grupa/" + slug(x.g.s) + ".html"; td.appendChild(a); tr.appendChild(td);
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
        // On a phone the result opens under the buttons, often below the screen: bring "next" and the result into it.
        var r = next.getBoundingClientRect();
        if (r.bottom > window.innerHeight - 120 && next.scrollIntoView) next.scrollIntoView({ block: "center", behavior: "smooth" });
        if (!item.querySelector(".q-half")) soon(item, i);  // the halfway note is read, not passed by on a timer
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
  // Reading is often scrolling: a swipe or the wheel anywhere on the page stops the clock too, not only a touch of
  // the result itself (WCAG 2.2.1: a time limit the reader can turn off).
  ["wheel", "touchmove"].forEach(function (ev) { document.addEventListener(ev, stay, { passive: true }); });
  marks.forEach(function (m) {
    m.addEventListener("click", function () { stay(); send(); go(m.dataset.go === "kraj" ? "kraj" : +m.dataset.go); });
  });

  // The picture to share, drawn here in the browser: the visitor's ballot, what would have happened had it been
  // up to them, and which group voted most like them. Nothing is uploaded; sharing uses the device's own share sheet.
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
    // Dark, "me against the other visitors": what would have happened had it been up to the visitor, then a column
    // per law (how the site's visitors voted, the visitor's vote as a dot over it; no law named), how often the
    // visitor voted as most visitors did and their loneliest vote, and "A ti?". With too few visitors' votes yet
    // (none of the laws has five), the hall stands in for them (the maintainer, 17 Nov 2026).
    var c = document.createElement("canvas"), W = 1080, H = 1350, P = 84, ctx = c.getContext("2d");
    var serif = '"Literata", Georgia, serif', sans = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    var ZA = "#7cc0f5", PROTIV = "#ff9a52", SOFT = "#c9ccd3", DIM = "#30343c", TONE = { z: ZA, p: PROTIV, u: "#9aa0ab", "": DIM };
    c.width = W; c.height = H;
    function paint() {
      var y, x, cr = card.crowd, vs = cr || card.vs || versus();
      ctx.fillStyle = "#111111"; ctx.fillRect(0, 0, W, H);
      ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
      // the mark and the name of the site
      ctx.lineWidth = 19; ctx.strokeStyle = ZA; ctx.beginPath(); ctx.arc(P + 56, 150, 54, Math.PI, Math.PI * 300 / 180); ctx.stroke();
      ctx.strokeStyle = PROTIV; ctx.beginPath(); ctx.arc(P + 56, 150, 54, Math.PI * 310 / 180, Math.PI * 2); ctx.stroke();
      ctx.font = "700 54px " + serif; x = P + 142;
      [["Za", ZA], [" ili ", "#ffffff"], ["Protiv", PROTIV]].forEach(function (p) {
        ctx.fillStyle = p[1]; ctx.fillText(p[0], x, 150); x += ctx.measureText(p[0]).width;
      });
      // what would have happened: "Da se ja pitam," then the rest large, its number in orange
      ctx.fillStyle = SOFT; ctx.font = "400 46px " + sans; ctx.fillText("Da se ja pitam,", P, 290);
      var rest = card.fact.replace(/^Da se ja pitam, /, ""), lines;
      ctx.font = "800 88px " + serif; lines = wrapText(ctx, rest, W - 2 * P, 3); y = 392;
      lines.forEach(function (l) {
        var xx = P;
        l.split(" ").forEach(function (w, k) {
          var word = (k ? " " : "") + w;
          ctx.fillStyle = /\d/.test(w) || /^(svih|nijedan)$/.test(w) ? PROTIV : "#ffffff";
          ctx.fillText(word, xx, y); xx += ctx.measureText(word).width;
        });
        y += 100;
      });
      // the others and me: a column per law, their votes stacked (za below, protiv above, the rest dim), the
      // visitor's vote as a dot above
      var n = answers.length, gap = n > 8 ? 22 : 30, cw = (W - 2 * P - gap * (n - 1)) / n;
      var top = y + 40, CH = 240, base = top + CH;
      answers.forEach(function (a, i) {
        var h = cr ? crowdOf(i) : hall(i), cx = P + i * (cw + gap), k = CH / Math.max(1, cr ? h.n : h.z + h.p + h.rest);
        ctx.fillStyle = "#2a2e36"; ctx.fillRect(cx, top, cw, CH);
        ctx.fillStyle = ZA; ctx.fillRect(cx, base - h.z * k, cw, h.z * k);
        ctx.fillStyle = PROTIV; ctx.fillRect(cx, base - (h.z + h.p) * k, cw, h.p * k);
        var dy = top - 34, r = Math.min(cw / 2 - 2, 20);
        ctx.beginPath(); ctx.arc(cx + cw / 2, dy, r, 0, Math.PI * 2);
        if (a) { ctx.fillStyle = TONE[a]; ctx.fill(); } else { ctx.strokeStyle = DIM; ctx.lineWidth = 4; ctx.stroke(); }
      });
      ctx.fillStyle = SOFT; ctx.font = "400 28px " + sans;
      ctx.fillText(cr ? "Stub je zakon: kako su glasali posetioci sajta. Krug je moj glas." :
        "Svaki stub je jedan zakon i kako je glasala sala. Krug je moj glas.", P, base + 46);
      // how often with the hall's majority, and the loneliest vote
      y = base + 128;
      ctx.fillStyle = "#ffffff"; ctx.font = "800 64px " + serif;
      var sameTxt = vs.same + " od " + vs.of, sw = ctx.measureText(sameTxt).width;
      ctx.fillText(sameTxt, P, y);
      ctx.font = "400 40px " + sans; ctx.fillText(cr ? " puta kao većina posetilaca" : " puta kao većina u sali", P + sw, y);
      var alone = cr ? crowdLonely(cr.lonely) : lonelyText(vs.lonely).replace("tvoj glas", "moj glas");
      if (alone) { ctx.fillStyle = SOFT; ctx.font = "400 34px " + sans; ctx.fillText(alone, P, y + 56); }
      ctx.fillStyle = "#ffffff"; ctx.fillRect(P, H - 176, W - 2 * P, 4);
      ctx.font = "700 64px " + serif; ctx.fillText("A ti?", P, H - 86);
      ctx.font = "400 40px " + sans; ctx.textAlign = "right";
      ctx.fillText("zailiprotiv.rs/glasaj", W - P, H - 86); ctx.textAlign = "left";
      var img = document.getElementById("q-card");
      img.alt = card.fact + (cr ? " Kao većina posetilaca na " : " Kao većina u sali na ") + vs.same + " od " + vs.of + " zakona. " + alone;
      c.toBlob(function (blob) {
        if (!blob) return;
        cardBlob = blob;
        var url = URL.createObjectURL(blob);
        img.src = url; document.getElementById("q-save").href = url;
      }, "image/png");
    }
    var ready = document.fonts && document.fonts.load ? document.fonts.load('800 96px "Literata"').catch(function () {}) : Promise.resolve();
    ready.then(paint);
  }
  var card = { fact: "", vs: null, crowd: null };
  // On how many laws the visitor voted as most visitors did, among the laws five or more visitors voted on, and
  // the vote (za or protiv) the smallest share of them cast.
  function crowdFact() {
    var same = 0, of = 0, lonely = null;
    answers.forEach(function (a, i) {
      var c = crowdOf(i);
      if (!a || c.n < 5) return;
      of++; if (c[a] >= Math.max(c.z, c.p, c.u)) same++;
      if (a !== "u" && (!lonely || c[a] / c.n < lonely.share)) lonely = { share: c[a] / c.n, a: a };
    });
    return of ? { same: same, of: of, lonely: lonely } : null;
  }
  function crowdLonely(l) {
    return !l || l.share > 0.5 ? "" : "Najusamljeniji glas: " + WORD[l.a] + ", kao samo " + Math.max(1, Math.round(100 * l.share)) + "% posetilaca.";
  }
  function redraw() {
    card.crowd = api ? crowdFact() : null;
    var line = document.getElementById("q-crowd-fact");
    line.hidden = !card.crowd;
    if (card.crowd) line.textContent = "Na " + card.crowd.same + " od " + card.crowd.of + " " + plural(card.crowd.of, "zakona", "zakona", "zakona") +
      " glasaš kao većina posetilaca sajta.";
    // The words that are copied or shared: what would have happened, how often with the others, and the question.
    var vs = card.crowd || card.vs || versus();
    shareText = card.fact.replace(/ zakona\.$/, " ovih zakona.") + (vs.of ? (card.crowd ? " Kao većina posetilaca" : " Kao većina u sali") +
      " glasam na " + vs.same + " od " + vs.of + "." : "") + " Kako ti glasaš?";
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(drawCard);
  }
  function note(text) { document.getElementById("q-shared").textContent = text; }
  function shareUrl() { return location.protocol === "file:" ? "https://zailiprotiv.rs/kviz/podelili-salu" : location.href.split("#")[0]; }
  function copyText() {
    var text = shareText + " " + shareUrl();
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject())
      .then(function () { note("Kopirano. Nalepi u poruku ili objavu."); used("kviz.kopiraj"); })
      .catch(function () { note(text); });
  }
  document.getElementById("q-copy").addEventListener("click", copyText);
  document.getElementById("q-save").addEventListener("click", function () { used("kviz.sacuvaj"); });
  var shared = function () { used("kviz.podeljeno"); };
  document.getElementById("q-share").addEventListener("click", function () {
    used("kviz.podeli");
    var file = cardBlob && window.File ? new File([cardBlob], "kako-ja-glasam.png", { type: "image/png" }) : null;
    if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
      navigator.share({ files: [file], text: shareText + " " + shareUrl() }).then(shared, function () {});
    } else if (navigator.share) {
      navigator.share({ text: shareText, url: shareUrl() }).then(shared, function () {});
    } else {  // a computer without a share sheet: the picture is saved, the text copied
      document.getElementById("q-save").click(); copyText();
      note("Slika je sačuvana, a tekst sa linkom kopiran. Dodaj ih u poruku ili objavu.");
    }
  });
  document.getElementById("q-reset").addEventListener("click", function () {
    answers = answers.map(function () { return ""; });
    try { sessionStorage.setItem(KEY, "{}"); } catch (e) {}
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
    // With the device's mark (the same one a law's page uses), these are that device's votes: sent again from a
    // law's page they replace these and do not add to them. The votes are remembered where "glas.js" keeps its own.
    var d = null, kept = {};
    try {
      d = localStorage.getItem("zip.d");
      if (!d || !/^[A-Za-z0-9_-]{16,64}$/.test(d)) {
        var bytes = new Uint8Array(18); window.crypto.getRandomValues(bytes);
        d = Array.prototype.map.call(bytes, function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
        localStorage.setItem("zip.d", d);
      }
      kept = JSON.parse(localStorage.getItem("zip.glasovi")) || {};
      Object.keys(v).forEach(function (law) { kept[law] = v[law]; });
      localStorage.setItem("zip.glasovi", JSON.stringify(kept));
    } catch (e) { d = null; }
    fetch(api, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(d ? { v: v, d: d } : { v: v }), keepalive: true })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { crowd = d; showCrowd(); })
      .catch(function () {
        Object.keys(v).forEach(function (law) { delete sentLaws[law]; });  // not counted: try again with the next law
        try { localStorage.setItem(SENT, JSON.stringify(sentLaws)); } catch (e) {}
      });
  }
  takeOver();
  if (api) fetch(api).then(function (r) { return r.json(); }).then(function (d) { crowd = d; showCrowd(); }).catch(function () {});

  var first = answers.indexOf("");
  go(cameWith >= 0 ? cameWith : (first < 0 ? "kraj" : first));
  if (cameWith >= 0) { showCrowd(); soon(items[cameWith], cameWith); }
  ready = true;
})();
