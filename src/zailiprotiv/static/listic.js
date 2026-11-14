// "Glasaj i ti" with the visitor's ballot ("Moj listić"): everything they voted on, on laws' and bills' pages and in
// the quiz, beside the Assembly's result, with the MPs and groups that voted the same. The ballot is in this
// browser only (localStorage "zip.glasovi"); the page reads the Assembly's votes from small files of the site and
// compares here. Nothing about the visitor is sent.
(function () {
  "use strict";
  var root = document.body.dataset.root || "";
  var WORD = { z: "za", p: "protiv", u: "uzdržan" };
  var MONTHS = ["januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar", "decembar"];
  function $(id) { return document.getElementById(id); }
  function read(key, empty) { try { return JSON.parse(localStorage.getItem(key)) || empty; } catch (e) { return empty; } }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function plural(n, one, few, many) { var d = n % 10, h = n % 100; return d === 1 && h !== 11 ? one : d >= 2 && d <= 4 && (h < 12 || h > 14) ? few : many; }
  function day(iso) { var p = (iso || "").split("-"); return p.length < 3 ? "" : (+p[2]) + ". " + MONTHS[+p[1] - 1] + " " + p[0] + "."; }
  function json(path) { return fetch(root + path).then(function (r) { if (!r.ok) throw new Error(path); return r.json(); }); }
  function fact(against, n) {
    return against === 0 ? "prošlo bi svih " + n : against === n ? (n === 1 ? "pao bi i taj jedan" : "palo bi svih " + n) : "palo bi " + against + " od " + n;
  }

  // A vote cast on the home page's band used to come here; the quiz has its own page now.
  try {
    if (new URLSearchParams(location.search).get("z")) { location.replace(root + "kviz/podelili-salu" + ".html" + location.search); return; }
  } catch (e) {}

  var state = null, filter = "", all = false, cleared = 0;

  function quizCard(votes) {
    var card = $("lb-quiz");
    if (!card) return;
    var laws = card.dataset.laws.split(" "), mine = laws.filter(function (s) { return votes[s]; });
    if (!mine.length) return;
    if (mine.length < laws.length) { $("lb-quiz-go").textContent = "Nastavi kviz · " + mine.length + " od " + laws.length; return; }
    var against = mine.filter(function (s) { return votes[s] === "p"; }).length;
    $("lb-quiz-k").textContent = "Kviz · završen, " + laws.length + " od " + laws.length;
    $("lb-quiz-p").textContent = "Da se ti pitaš, " + fact(against, laws.length) + " " + (against === 0 || against === laws.length ? "ovih zakona" : "ovih zakona") + ".";
    $("lb-quiz-go").textContent = "Vidi rezultat i podeli";
  }

  function start() {
    var votes = read("zip.glasovi", {}), items = Object.keys(votes).filter(function (k) { return WORD[votes[k]]; });
    quizCard(votes);
    if (!items.length) { $("lb-mine").hidden = $("lb-rest").hidden = true; $("lb-title").textContent = "Kako bi ti glasao?"; $("lb-sum").innerHTML = "Moj listić · <b>prazan</b>, popuni ga glasanjem"; return; }
    $("lb-title").textContent = "Moj listić";
    Promise.all([json("listic/zakoni.json"), json("listic/predlozi.json")]).then(function (got) {
      var where = got[0], bills = got[1], rows = [], convs = {};
      items.forEach(function (item) {
        var v = votes[item];
        if (item.slice(0, 2) === "p.") {
          var b = bills[item.slice(2)];
          if (!b) return;
          if (b.z && where[b.z]) { if (!votes[b.z]) rows.push({ law: b.z, conv: where[b.z], my: v, early: true }); }
          else rows.push({ bill: item.slice(2), t: b.t, d: b.d, my: v, gone: !!b.x });
        } else if (where[item]) rows.push({ law: item, conv: where[item], my: v });
      });
      rows.forEach(function (r) { if (r.conv) convs[r.conv] = 1; });
      return Promise.all(Object.keys(convs).map(function (c) { return json("listic/" + c + ".json"); })).then(function (files) {
        var by = {};
        files.forEach(function (f) { by[f.c] = f; });
        rows = rows.filter(function (r) { return !r.law || (by[r.conv] && by[r.conv].laws[r.law]); });
        rows.forEach(function (r) { if (r.law) { r.data = by[r.conv].laws[r.law]; r.t = r.data.t; r.d = r.data.d; } });
        rows.sort(function (a, b) { return (a.law ? 1 : 0) - (b.law ? 1 : 0) || (a.d < b.d ? 1 : a.d > b.d ? -1 : 0); });
        state = compare(rows, by);
        show();
      });
    }).catch(function () { $("lb-sum").textContent = "Listić trenutno ne može da se učita. Tvoji glasovi su sačuvani u ovom pregledaču."; });
  }

  function compare(rows, by) {
    var laws = rows.filter(function (r) { return r.law; }), perConv = {}, mps = {}, groups = [], many = Object.keys(by).length > 1;
    laws.forEach(function (r) { (perConv[r.conv] = perConv[r.conv] || []).push(r); });
    Object.keys(perConv).forEach(function (c) {
      var f = by[c], mine = perConv[c], both = [], same = [], members = {};
      f.mps.forEach(function (m, i) { both[i] = same[i] = 0; (members[m[2]] = members[m[2]] || []).push(i); });
      mine.forEach(function (r) {
        var v = r.data.v;
        for (var i = 0; i < v.length; i++) if (v[i] !== "-") { both[i]++; if (v[i] === r.my) same[i]++; }
      });
      f.mps.forEach(function (m, i) {
        var p = mps[m[0]] = mps[m[0]] || { slug: m[0], name: m[1], group: m[2], conv: +c, both: 0, same: 0, could: 0 };
        if (+c >= p.conv) { p.group = m[2]; p.conv = +c; }
        p.both += both[i]; p.same += same[i]; p.could += mine.length;
      });
      Object.keys(members).forEach(function (g) {
        if (!g) return;
        var b = 0, s = 0;
        mine.forEach(function (r) {
          var n = { z: 0, p: 0, u: 0 }, top = "", tie = false;
          members[g].forEach(function (i) { var ch = r.data.v[i]; if (ch in n) n[ch]++; });
          ["z", "p", "u"].forEach(function (k) { if (n[k] && (!top || n[k] > n[top])) { top = k; tie = false; } else if (top && n[k] === n[top] && k !== top) tie = true; });
          if (top && !tie) { b++; if (top === r.my) s++; }
        });
        var need = Math.min(mine.length, Math.max(3, Math.ceil(mine.length / 2)));
        if (b >= need) groups.push({ name: g + (many ? " · " + c + ". saziv" : ""), both: b, same: s, share: s / b });
      });
    });
    // Shown: those who voted on at least half of the visitor's laws (three at least), so no one leads on a vote or
    // two. A ballot spread over convocations may leave no such MP; then half of the laws of the MP's own time.
    var everyone = Object.keys(mps).map(function (k) { return mps[k]; }), half = Math.min(laws.length, Math.max(3, Math.ceil(laws.length / 2)));
    var list = everyone.filter(function (p) { return p.both >= half && p.both > 0; });
    if (!list.length) list = everyone.filter(function (p) { return p.both >= Math.min(p.could, Math.max(3, Math.ceil(p.could / 2))) && p.both > 0; });
    var wide = groups.filter(function (g) { return g.both >= half; });
    if (wide.length) groups = wide;
    list.forEach(function (p) { p.share = p.same / p.both; });
    var order = function (a, b) { return b.share - a.share || b.both - a.both || a.name.localeCompare(b.name, "sr"); };
    list.sort(order); groups.sort(order);
    // The law that stands out on this ballot, by rule: how it split the chamber (3), the sparks in its debate (2),
    // its amendments (1), each as the law's place among its convocation's, and whether the visitor voted against (2).
    var pick = null;
    laws.forEach(function (r) {
      var parts = [3 * r.data.r[0], 2 * r.data.r[1], r.data.r[2], r.my === "p" ? 2 : 0], sum = parts[0] + parts[1] + parts[2] + parts[3];
      if (!pick || sum > pick.sum) pick = { row: r, sum: sum, parts: parts };
    });
    return { rows: rows, laws: laws, mps: list, groups: groups, pick: laws.length > 1 && pick && pick.sum > 0 ? pick : null,
             against: laws.filter(function (r) { return r.my === "p"; }).length };
  }

  // The rolls write the surname first ("Jefić Branković Sanja"); the given name is the last word.
  function lastFirst(name) { var w = name.split(" "); return w.length > 1 ? [w[w.length - 1]].concat(w.slice(0, -1)).join(" ") : name; }

  function show() {
    var s = state, n = s.laws.length, marks = read("zip.citati", {});
    var count = function (v) { return s.rows.filter(function (r) { return r.my === v; }).length; };
    var total = s.rows.length;
    $("lb-sum").innerHTML = "";
    [[total + " " + plural(total, "glas", "glasa", "glasova"), ""], [count("z") + " za", "z"], [count("p") + " protiv", "p"], [count("u") + " " + plural(count("u"), "uzdržan", "uzdržana", "uzdržanih"), ""]]
      .forEach(function (p, i) { if (i) $("lb-sum").appendChild(document.createTextNode(" · ")); $("lb-sum").appendChild(el(i === 3 ? "span" : "b", p[1], p[0])); });
    $("lb-mine").hidden = $("lb-rest").hidden = false;
    var top = s.mps[0], ties = top ? s.mps.filter(function (p) { return p.share === top.share && p.both === top.both; }).length - 1 : 0;
    $("lb-mp").textContent = ""; $("lb-mp-n").textContent = "";
    if (top) {
      var a = el("a", "", lastFirst(top.name)); a.href = root + "poslanik/" + top.slug + ".html"; $("lb-mp").appendChild(a);
      $("lb-mp-n").textContent = top.same + " od " + top.both + " " + plural(top.both, "zajedničkog glasanja", "zajednička glasanja", "zajedničkih glasanja") + (ties ? " · i još " + ties + " sa istim brojem" : "");
    } else { $("lb-mp").textContent = "—"; $("lb-mp-n").textContent = n ? "Nema poslanika sa dovoljno zajedničkih glasanja." : "Pojaviće se kad glasaš o usvojenom zakonu."; }
    var g = s.groups[0];
    $("lb-group").textContent = g ? g.name : "—";
    $("lb-group-n").textContent = g ? "isti glas kao većina grupe na " + g.same + " od " + g.both + " " + plural(g.both, "zakona", "zakona", "zakona") : (n ? "Treba bar tri zakona iz istog saziva." : "");
    $("lb-fact").textContent = n ? fact(s.against, n) : "—";
    $("lb-fact-n").textContent = n ? plural(n, "zakon koji je Skupština usvojila", "zakona koje je Skupština usvojila", "zakona koje je Skupština usvojila") : "Još nisi glasao o usvojenom zakonu.";
    $("lb-share-open").hidden = !n;

    var pick = s.pick, box = $("lb-pick");
    box.hidden = !pick;
    if (pick) {
      var r = pick.row, d = r.data, best = pick.parts.indexOf(Math.max.apply(null, pick.parts));
      $("lb-pick-why").textContent = "Sa tvog listića · " + ["najviše je podelio salu", "najviše varnica u raspravi", "najviše amandmana", "ovde si glasao drugačije od Skupštine"][best];
      $("lb-pick-law").textContent = d.t; $("lb-pick-law").href = root + "zakon/" + r.law + ".html";
      var nums = [d.k[1] + " " + plural(d.k[1], "glas protiv", "glasa protiv", "glasova protiv")];
      if (d.g[0]) nums.push(d.g[0] + " " + plural(d.g[0], "mera predsedavajućeg", "mere predsedavajućeg", "mera predsedavajućeg"));
      if (d.g[1]) nums.push(d.g[1] + " " + plural(d.g[1], "razmena replika", "razmene replika", "razmena replika"));
      if (d.g[2]) nums.push(d.g[2] + " " + plural(d.g[2], "amandman", "amandmana", "amandmana"));
      nums.push("ti: " + WORD[r.my] + ", Skupština: usvojila");
      $("lb-pick-nums").textContent = nums.join(" · ");
      pick.text = nums.slice(0, -1).join(" · ");
    }

    // The rows, and what they can be narrowed to.
    var kinds = [["", "Svi", total], ["p", "Drugačije od Skupštine", s.against], ["b", "U proceduri", s.rows.filter(function (r) { return r.bill; }).length],
                 ["c", "Sa obeleženim citatima", s.rows.filter(function (r) { return r.law && (marks[r.law] || []).length; }).length]];
    var fs = $("lb-filters"); fs.textContent = "";
    kinds.forEach(function (k) {
      if (k[0] && !k[2]) return;
      var b = el("button", "chip" + (filter === k[0] ? " on" : ""), k[1] + " "); b.type = "button"; b.appendChild(el("span", "", String(k[2])));
      b.addEventListener("click", function () { filter = k[0]; show(); });
      fs.appendChild(b);
    });
    var body = $("lb-rows"), shown = s.rows.filter(function (r) {
      return !filter || (filter === "p" && r.law && r.my === "p") || (filter === "b" && r.bill) || (filter === "c" && r.law && (marks[r.law] || []).length);
    });
    body.textContent = "";
    var cap = all || filter ? shown.length : 15;
    shown.slice(0, cap).forEach(function (r) {
      var tr = el("tr"), td = el("td"), a = el("a", "", r.t);
      a.href = root + (r.law ? "zakon/" + r.law : "predlog/" + r.bill) + ".html"; td.appendChild(a);
      td.appendChild(el("small", "", r.law ? day(r.d) + (r.early ? " · glasao si pre poslanika" : "") : "podnet " + day(r.d)));
      tr.appendChild(td);
      td = el("td"); td.appendChild(el("span", "lb-chip " + r.my, WORD[r.my])); tr.appendChild(td);
      td = el("td", "sk");
      if (r.law) { var b = el("b"); b.appendChild(el("span", "z", String(r.data.k[0]))); b.appendChild(document.createTextNode(" : ")); b.appendChild(el("span", "p", String(r.data.k[1]))); td.appendChild(b); }
      else td.appendChild(el("small", "", r.gone ? "više nije na spisku" : "čeka glasanje"));
      tr.appendChild(td);
      var like = "";
      if (!r.law) like = r.gone ? "Povučen ili je postupak prestao" : "Skupština još nije glasala";
      else if (r.my === "u") { var u = r.data.v.split("u").length - 1; like = "Uzdržanih u sali: " + u; }
      else { var m = r.data.k[r.my === "z" ? 0 : 1]; like = m ? "Kao " + m + " " + plural(m, "poslanik", "poslanika", "poslanika") : "Niko u sali nije glasao tako"; }
      tr.appendChild(el("td", "same" + (r.law && r.my === "z" ? "" : " no"), like));
      body.appendChild(tr);
    });
    var more = $("lb-more"); more.hidden = shown.length <= cap;
    more.textContent = "Prikaži još " + (shown.length - cap);

    function ranked(list, target, link) {
      target.textContent = "";
      list.slice(0, 5).forEach(function (x) {
        var li = el("li"), name = el("span");
        if (link) { var a = el("a", "", lastFirst(x.name)); a.href = root + "poslanik/" + x.slug + ".html"; name.appendChild(a); name.appendChild(el("small", "", " " + x.group)); }
        else name.textContent = x.name;
        li.appendChild(name); li.appendChild(el("b", "", Math.round(100 * x.share) + "%"));
        li.appendChild(el("small", "n", x.same + " od " + x.both));
        var bar = el("i"), fill = el("u"); fill.style.width = (100 * x.share) + "%"; bar.appendChild(fill); li.appendChild(bar);
        target.appendChild(li);
      });
      if (!list.length) target.appendChild(el("li", "none", "Još nema dovoljno zajedničkih glasanja."));
    }
    ranked(s.mps, $("lb-mps"), true); ranked(s.groups, $("lb-groups"), false);
    if (!$("lb-share").hidden) draw();
  }

  // The picture to share: the sentence, the closest MP, the law that stands out, and the ballot as squares (framed
  // where the visitor voted against a law the Assembly passed). No law is named beside a vote.
  var blob = null;
  function shareText() {
    var s = state, top = s.mps[0];
    return "Da se ja pitam, " + fact(s.against, s.laws.length) + " " + plural(s.laws.length, "zakon", "zakona", "zakona") + "." +
      (top ? " Najviše glasova kao ja: " + lastFirst(top.name) + "." : "") + " Kako bi ti glasao?";
  }
  function draw() {
    var s = state, W = 1080, H = 1350, P = 72, c = document.createElement("canvas"), ctx = c.getContext("2d");
    var INK = "#111111", SOFT = "#555555", TONE = { z: "#1f5fa8", p: "#c2410c", u: "#8a8f99" };
    var serif = '"Literata", Georgia, serif', sans = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    c.width = W; c.height = H;
    function words(parts, font, x, y, width, lead) {  // [[text, colour]…], wrapped word by word; returns the next line's y
      ctx.font = font;
      var cx = x, space = ctx.measureText(" ").width;
      parts.forEach(function (p) {
        p[0].split(" ").forEach(function (w) {
          if (!w) return;
          var ww = ctx.measureText(w).width;
          if (cx > x && cx + ww > x + width) { cx = x; y += lead; }
          ctx.fillStyle = p[1]; ctx.fillText(w, cx, y); cx += ww + space;
        });
      });
      return y + lead;
    }
    function paint() {
      ctx.fillStyle = "#f3f3f1"; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = INK; ctx.fillRect(0, 0, W, 16);
      ctx.textBaseline = "alphabetic";
      words([["Za", TONE.z], ["ili", INK], ["Protiv", TONE.p]], "700 46px " + serif, P, 118, 600, 0);
      ctx.font = "400 30px " + sans; ctx.fillStyle = SOFT; ctx.textAlign = "right";
      ctx.fillText("Moj listić · " + s.laws.length + " " + plural(s.laws.length, "zakon", "zakona", "zakona"), W - P, 114); ctx.textAlign = "left";
      var y = words([["Da se ja pitam,", INK], [fact(s.against, s.laws.length), TONE.p], [plural(s.laws.length, "zakon.", "zakona.", "zakona."), INK]], "800 98px " + serif, P, 300, W - 2 * P, 108);
      var top = s.mps[0];
      if (top) { y = words([["Najviše glasova kao ja:", INK]], "400 40px " + sans, P, y - 30, W - 2 * P, 56); y = words([[lastFirst(top.name), INK]], "700 48px " + serif, P, y, W - 2 * P, 60); }
      // the squares, from the bottom up
      var votes = s.laws.map(function (r) { return r.my; }), size = 14, gap = 4;
      [62, 48, 38, 30, 24, 18].some(function (z) {
        var g = Math.round(z / 5), cols = Math.floor((W - 2 * P + g) / (z + g));
        if (Math.ceil(votes.length / cols) <= 4) { size = z; gap = g; return true; }
        return false;
      });
      var cols = Math.floor((W - 2 * P + gap) / (size + gap)), rowsN = Math.ceil(votes.length / cols), gy = H - 290 - rowsN * (size + gap);
      votes.forEach(function (v, i) {
        var x = P + (i % cols) * (size + gap), yy = gy + Math.floor(i / cols) * (size + gap);
        ctx.fillStyle = TONE[v]; ctx.fillRect(x, yy, size, size);
        if (v === "p") { var b = Math.max(3, Math.round(size / 9)); ctx.strokeStyle = INK; ctx.lineWidth = b; ctx.strokeRect(x + b / 2, yy + b / 2, size - b, size - b); }
      });
      var cnt = function (v) { return votes.filter(function (x) { return x === v; }).length; };
      words([[cnt("z") + " za ·", INK], [cnt("p") + " protiv ·", INK], [cnt("u") + " uzdržan ·", INK], ["uokvireno: drugačije od Skupštine", SOFT]], "400 27px " + sans, P, H - 240, W - 2 * P, 36);
      if (s.pick && gy - y > 190) {
        var py = y + Math.max(10, (gy - y - 200) / 2);
        ctx.fillStyle = INK; ctx.fillRect(P, py - 34, 8, 190);
        py = words([[$("lb-pick-why").textContent, SOFT]], "400 28px " + sans, P + 32, py, W - 2 * P - 32, 40);
        ctx.font = "700 44px " + serif;
        var title = s.pick.row.data.t; while (ctx.measureText(title).width > 2 * (W - 2 * P - 32) - 60 && title.length > 20) title = title.slice(0, -2).trim() + "…";
        py = words([[title, INK]], "700 44px " + serif, P + 32, py + 16, W - 2 * P - 32, 54);
        words([[s.pick.text.split(" · ").slice(0, 3).join(" · "), SOFT]], "400 28px " + sans, P + 32, py - 4, W - 2 * P - 32, 38);
      }
      ctx.fillStyle = INK; ctx.fillRect(P, H - 160, W - 2 * P, 4);
      ctx.font = "700 42px " + serif; ctx.fillText("Kako bi ti glasao?", P, H - 84);
      ctx.font = "400 36px " + sans; ctx.textAlign = "right"; ctx.fillText("zailiprotiv.rs/glasaj", W - P, H - 84); ctx.textAlign = "left";
      var img = $("lb-card"); img.alt = shareText();
      c.toBlob(function (b) {
        if (!b) return;
        blob = b;
        var url = URL.createObjectURL(b); img.src = url; $("lb-save").href = url;
      }, "image/png");
    }
    var ready = document.fonts && document.fonts.load ? Promise.all([document.fonts.load('800 98px "Literata"'), document.fonts.load('700 46px "Literata"')]).catch(function () {}) : Promise.resolve();
    ready.then(paint);
  }
  function note(text) { $("lb-shared").textContent = text; }
  var URL_ = "https://zailiprotiv.rs/glasaj";
  $("lb-share-open").addEventListener("click", function () { $("lb-share").hidden = !$("lb-share").hidden; if (!$("lb-share").hidden) draw(); });
  $("lb-copy").addEventListener("click", function () {
    var text = shareText() + " " + URL_;
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { note("Kopirano. Nalepi u poruku ili objavu."); }).catch(function () { note(text); });
    else note(text);
  });
  $("lb-share-img").addEventListener("click", function () {
    var file = blob && window.File ? new File([blob], "moj-listic.png", { type: "image/png" }) : null;
    if (file && navigator.canShare && navigator.canShare({ files: [file] })) navigator.share({ files: [file], text: shareText() + " " + URL_ }).catch(function () {});
    else if (navigator.share) navigator.share({ text: shareText(), url: URL_ }).catch(function () {});
    else note("Ovaj pregledač ne ume da podeli sliku: sačuvaj je, pa je pošalji.");
  });
  $("lb-more").addEventListener("click", function () { all = true; show(); });
  $("lb-clear").addEventListener("click", function () {
    var b = $("lb-clear");
    if (Date.now() - cleared > 6000) { cleared = Date.now(); b.textContent = "Klikni još jednom da obrišeš sve glasove iz ovog pregledača"; return; }
    try { localStorage.removeItem("zip.glasovi"); localStorage.removeItem("zip.citati"); Object.keys(localStorage).forEach(function (k) { if (k.indexOf("glasaj:") === 0) localStorage.removeItem(k); }); sessionStorage.clear(); } catch (e) {}
    location.reload();
  });
  // The bill's card: after a vote (or instead of one) the next bill not voted on yet takes its place in the same box.
  var billBox = $("glasaj"), billList = [], seen = {};
  try { billList = JSON.parse($("lb-bills").textContent); } catch (e) {}
  function unvoted() {
    var votes = read("zip.glasovi", {}), now = billBox.dataset.item;
    var left = billList.filter(function (b) { return !votes["p." + b.s] && "p." + b.s !== now; });
    var fresh = left.filter(function (b) { return !seen[b.s]; });  // those passed over come round again only at the end
    if (!fresh.length) seen = {};
    return fresh.length ? fresh.concat(left.filter(function (b) { return seen[b.s]; })) : left;
  }
  function nextBill() {
    if (!billBox) return;
    var votes = read("zip.glasovi", {}), left = unvoted(), voted = !!votes[billBox.dataset.item], b = $("lb-bill-next");
    b.hidden = !left.length;
    b.className = voted ? "lb-btn" : "linklike";
    b.textContent = voted ? "Sledeći predlog" : "Preskoči: sledeći predlog";
    $("lb-bill-n").textContent = left.length ? "još " + left.length + " u proceduri o " + plural(left.length, "kom", "kojima", "kojima") + " nisi glasao" : (voted ? "Glasao si o svim predlozima u proceduri." : "");
  }
  function putBill(b) {
    seen[billBox.dataset.item.slice(2)] = 1;
    billBox.dataset.item = "p." + b.s;
    $("lb-bill-k").textContent = "U proceduri · podnet " + day(b.d);
    $("lb-bill-t").textContent = b.t; $("lb-bill-t").href = $("lb-bill-more").href = root + "predlog/" + b.s + ".html";
    $("lb-bill-g").textContent = b.g;
    document.dispatchEvent(new CustomEvent("zip:predlog"));
    nextBill();
  }
  if (billBox && billList.length) {
    $("lb-bill-next").addEventListener("click", function () { var left = unvoted(); if (left.length) putBill(left[0]); });
    // Someone who has voted on the bill shown first finds the next one waiting.
    if (read("zip.glasovi", {})[billBox.dataset.item] && unvoted().length) putBill(unvoted()[0]); else nextBill();
  }
  document.addEventListener("zip:glas", function () { start(); nextBill(); });
  start();
})();
