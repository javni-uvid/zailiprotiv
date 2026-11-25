
(function () {
  var base = document.body.getAttribute("data-base");
  // The clock beside the speaker: the seconds the page was given, plus those passed since; never back within a turn.
  var got = Date.now(), last = { od: "", s: 0 };
  function hms(s) { var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    return (h ? h + ":" + (m < 10 ? "0" : "") : "") + m + ":" + (x < 10 ? "0" : "") + x; }
  function seconds(c) {
    var od = c.getAttribute("data-od"), s = (+c.getAttribute("data-sek")) + Math.round((Date.now() - got) / 1000);
    if (last.od === od && last.s > s) s = last.s;
    last = { od: od, s: s };
    return s;
  }
  // One line about the speaker at a time, the next every fifteen seconds or on a tap; from the first for each speaker.
  var turn = { od: "", t: 0, skip: 0 };
  function rotate() {
    var u = document.querySelector(".rot"), c = document.querySelector(".clk");
    if (!u) return;
    var od = c ? c.getAttribute("data-od") : "";
    if (turn.od !== od) turn = { od: od, t: Date.now(), skip: 0 };
    var n = u.children.length, k = (Math.floor((Date.now() - turn.t) / 15000) + turn.skip) % n;
    u.classList.add("js");
    for (var i = 0; i < n; i++) u.children[i].classList.toggle("on", i === k);
    var no = document.querySelector(".rot-n");
    if (no) no.textContent = (k + 1) + "/" + n;
  }
  // The next sitting's countdown, written as page.left writes it.
  function until() {
    var b = document.querySelector(".nx-in");
    if (!b) return;
    var w = function (k) { return b.getAttribute("data-" + k); };
    var s = Math.floor(+w("at") - Date.now() / 1000), out;
    if (s <= 0) { out = w("soon"); if (b.previousElementSibling) b.previousElementSibling.hidden = true; }
    else {
      var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
      out = d ? d + " " + (d % 10 === 1 && d % 100 !== 11 ? w("d1") : w("dn")) + (h ? " " + h + " " + w("h") : "")
        : h ? h + " " + w("h") + " " + m + " " + w("m") : Math.max(1, m) + " " + w("m");
    }
    if (b.textContent !== out) b.textContent = out;
  }
  // The speaker beside the small picture (the styles show it only there, 24 Nov 2026): the name, the list and the clock of the part, the list's
  // colour beside them (22 Nov 2026, the maintainer). Only on YouTube's broadcast, whose speaker is the part's.
  var stage = document.querySelector(".player .stage"), oa = stage && stage.querySelector(".on-air");
  // The player shows an earlier moment (a step's time, "▶ snimak", or set back by hand): the part's speaker is not the
  // one on the picture (24 Nov 2026). By the player's own clock of the broadcast; before it tells it, by where it began.
  function past() {
    var f = stage.querySelector("iframe");
    if (shows && Date.now() - shows.at < 5000) return Date.now() / 1000 - shows.t > 120;
    return !!f && /[?&]start=[1-9]/.test(f.src);
  }
  function onAir() {
    if (!oa) return;
    var d = document.getElementById("deo"), w = d && d.querySelector(".sp-head .who"), k = d && d.querySelector(".sp-head .clk");
    var on = !!(w && k && d.getAttribute("data-stanje") === "govori" && stage.querySelector("iframe") && !past());
    if (oa.hidden === on) oa.hidden = !on;
    if (!on) return;
    var side = d.querySelector(".sp-head .side"), cls = "on-air" + (d.className ? " " + d.className : "");
    if (oa.className !== cls) oa.className = cls;
    var put = function (el, text) { if (el.textContent !== text) el.textContent = text; };
    put(oa.querySelector("b"), w.textContent.trim());
    put(oa.querySelector(".oa-side"), side ? side.textContent.trim() : "");
    put(oa.querySelector(".oa-clk"), hms(seconds(k)));
    var rk = d.querySelector(".sp-head .rk");  // a reply's two minutes, where heard
    put(oa.querySelector(".oa-rk"), rk ? rk.textContent.trim().split("·")[0].trim() : "");
  }
  // The line under the picture (22 Nov 2026): the part's newest lines of the automatic transcript, each shown the
  // page's delay after it first came (the viewer's player is behind the broadcast), the last two, while YouTube's
  // player plays; gone when no new line has come for 40 s.
  // With the sound (22 Nov 2026, the maintainer): YouTube's player says by messages which moment of the broadcast it
  // shows (mediaReferenceTime, the broadcast's own clock); each phrase carries its moment by the same clock
  // (data-pt), and is shown when the player reaches it, whatever that viewer's player is behind. Without those, a
  // line is shown the page's delay after it came.
  var cc = stage && stage.querySelector(".cc"), ccSeen = {}, shows = null;
  window.addEventListener("message", function (e) {
    if (!/^https:\/\/www\.youtube(-nocookie)?\.com$/.test(e.origin) || typeof e.data !== "string") return;
    var d; try { d = JSON.parse(e.data); } catch (x) { return; }
    var i = d && d.info, t = i && (i.mediaReferenceTime || (i.progressState && i.progressState.ingestionTime));
    if (typeof t === "number" && t > 1e9) {
      shows = { t: t, at: Date.now(), playing: shows ? shows.playing : true, ct: i.currentTime, since: shows ? shows.since : Date.now() };
    }
    if (i && typeof i.playerState === "number" && shows) shows.playing = i.playerState === 1;
  });
  function tell(msg) {  // to the player, as YouTube's own script does
    var f = cc && stage.querySelector("iframe");
    if (f && f.contentWindow) f.contentWindow.postMessage(JSON.stringify(msg), "https://www.youtube-nocookie.com");
  }
  setInterval(function () { tell({ event: "listening", id: 1, channel: "widget" }); }, 1000);
  // A player close behind the broadcast (6.5 s on a Serbian channel, 22 Nov 2026, against 16-20 s on another) can
  // reach a phrase before it comes. Then the player is set back by as much and 3 s more, once in 20 s at most and
  // 30 s in all, so that the line keeps up with the sound (the maintainer: "da titl bude istovremen sa zvukom").
  var late = 0, setBack = 0, lastBack = 0;
  function keepUp(now) {
    if (late < 0.5 || setBack >= 30 || now - lastBack < 20000 || !shows || !shows.playing || typeof shows.ct !== "number") return;
    var back = Math.min(30 - setBack, late + 3);
    tell({ event: "command", func: "seekTo", args: [Math.max(0, shows.ct + (now - shows.at) / 1000 - back), true], id: 1, channel: "widget" });
    setBack += back; lastBack = now; late = 0;
  }
  function captions() {
    if (!cc) return;
    var delay = (+cc.getAttribute("data-delay") || 0) * 1000, now = Date.now(), lines = [], newest = 0;
    var at = shows && now - shows.at < 5000 ? shows.t + (shows.playing ? (now - shows.at) / 1000 : 0) : null;
    [].forEach.call(document.querySelectorAll("#deo .cc-src li"), function (li) {
      var k = li.getAttribute("data-od"), pt = +li.getAttribute("data-pt") || 0;
      if (!(k in ccSeen)) {
        ccSeen[k] = now;
        // a phrase new to the page whose moment the player has passed already: how late (not those of the start)
        if (at !== null && pt && now - shows.since > 8000 && at > pt) late = Math.max(late, at - pt);
      }
      if (at !== null && pt) {  // by the broadcast's clock: from its moment, for 15 s
        if (pt <= at && at - pt < 15) { lines.push(li.textContent); newest = now; }
      } else if (now - ccSeen[k] >= delay) { lines.push(li.textContent); newest = Math.max(newest, ccSeen[k] + delay); }
    });
    keepUp(now);
    var on = lines.length > 0 && now - newest < 40000 && !!stage.querySelector("iframe");
    if (cc.hidden === on) cc.hidden = !on;
    if (!on) return;
    var text = lines.slice(-2).join(" "), span = cc.querySelector(".cc-t span");
    if (span.textContent !== text) span.textContent = text;
  }
  function tick() {
    var d = document.getElementById("deo"), c = document.querySelector("#checked span"), k = document.querySelector(".clk");
    if (d && c) c.textContent = Math.max(0, Math.round(Date.now() / 1000 - (+d.getAttribute("data-checked"))));
    if (k) k.textContent = hms(seconds(k));
    rotate();
    until();
    onAir();
    captions();
  }
  // Every five seconds, as the caption is read once a segment (five seconds); not while the tab is out of sight,
  // and once at once when it comes back. Each ask is a request through Cloudflare and to the computer it runs on.
  var heard = null;
  function said() {
    var w = document.querySelector("#deo .who"), side = document.querySelector("#deo .sp .side"), line = document.getElementById("ko");
    var now = w ? w.textContent.trim() : "";
    if (heard !== null && now && now !== heard && line) line.textContent = now + (side ? ", " + side.textContent.trim() : "");
    heard = now;
  }
  // Asked again with the last answer's mark (ETag): an unchanged part comes back as a 304, from the browser's copy,
  // and is not put in again.
  var shown = null;
  // Each fold of the part by its id, or its kind and place among its kind: open or not (or the element, when asked).
  function folds(els) {
    var m = {}, seen = {};
    [].forEach.call(document.querySelectorAll("#deo details"), function (d) {
      var k = d.id || d.className; seen[k] = (seen[k] || 0) + 1; if (!d.id) k += "|" + seen[k];
      m[k] = els ? d : d.open;
    });
    return m;
  }
  function load() {
    if (document.hidden) return;
    fetch(base + "deo", { cache: "no-cache" }).then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) return;
        if (html === shown) { got = Date.now(); tick(); return; }
        shown = html;
        // what the reader opened or closed (the agenda, the folded steps) stays so when the part is replaced
        var was = folds();
        // the keyboard's place too: the same kind of thing, the same one in order, has the focus again
        var deo = document.getElementById("deo"), f = document.activeElement, keep = null;
        if (f && deo.contains(f)) {
          var sel = f.tagName.toLowerCase() + (typeof f.className === "string" && f.className.trim() ? "." + f.className.trim().split(" ").filter(Boolean).join(".") : "");
          keep = [sel, [].indexOf.call(deo.querySelectorAll(sel), f)];
        }
        deo.outerHTML = html;
        document.dispatchEvent(new Event("deo"));  // a shared speech's row is marked again (mikrofon.js)
        var now = folds(true);
        Object.keys(now).forEach(function (k) { if (k in was) now[k].open = was[k]; });
        if (keep) { var again = document.querySelectorAll("#deo " + keep[0])[keep[1]]; if (again) again.focus({ preventScroll: true }); }
        got = Date.now(); tick(); said();
      })
      .catch(function () {});
  }
  // Every 5 s while there is a broadcast; every 30 s while there is none (20 Nov 2026: between sittings every open
  // tab still asked the computer every 5 s for a part that did not change).
  (function loop() {
    var d = document.getElementById("deo");
    setTimeout(function () { load(); loop(); }, d && d.getAttribute("data-stanje") === "nema_prenosa" ? 30000 : 5000);
  })();
  setInterval(tick, 1000); tick(); said();
  // a turn folded away among the earlier ones is opened when a link leads to it
  function unfold() {
    var id = location.hash.slice(1), e = id && document.getElementById(id), d = e && e.closest("details");
    if (d && !d.open) { d.open = true; e.scrollIntoView({ block: "center" }); }
  }
  window.addEventListener("hashchange", unfold); unfold();
  // The picture kept on top while the page is read: once it plays and its place has gone up out of sight, it stands
  // in a band at the top, small, the speaker beside it; its place keeps its height. × puts it back until the next ▶.
  // On a phone (24 Nov 2026, the maintainer) the picture stays as wide as the screen, pinned as soon as its top edge
  // reaches the top, so nothing jumps, with the speaker in one line under it.
  var player = stage && stage.parentNode, back = stage && stage.querySelector(".mini-x"), seen = true, away = false;
  function mini(on) {
    if (!player || on === player.classList.contains("mini")) return;
    player.style.minHeight = on ? player.offsetHeight + "px" : "";
    player.classList.toggle("mini", on);
    back.hidden = !on;
  }
  var phone = window.matchMedia && window.matchMedia("(max-width: 720px)"), top = null;
  function check() { mini(!seen && !away && !!stage.querySelector("iframe, video")); }
  if (player && "IntersectionObserver" in window) {
    // a line at the player's top: out of sight upwards is when its top edge has gone, the whole of it on a wide screen
    top = document.createElement("div");
    top.className = "pin";
    player.insertBefore(top, player.firstChild);
    var gone = function (r, what) { return !r.isIntersecting && r.boundingClientRect[what] <= 0; };
    new IntersectionObserver(function (es) { if (phone && phone.matches) { seen = !gone(es[0], "top"); check(); } }).observe(top);
    new IntersectionObserver(function (es) { if (!(phone && phone.matches)) { seen = es[0].isIntersecting || es[0].boundingClientRect.top > 0; check(); } }).observe(player);
    document.addEventListener("click", function (e) {
      if (!e.target.closest) return;
      if (e.target.closest(".mini-x")) { away = true; mini(false); return; }
      if (e.target.closest("[data-file], [data-yt]")) { away = false; setTimeout(check, 0); }
    });
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) load(); });

  // "Podeli ovaj trenutak": a picture drawn here, in the browser, of who speaks and for how long, with the page's
  // address; handed to the share sheet where there is one, else saved, with the text copied.
  function fit(g, text, weight, size, family, width) {
    do { g.font = weight + " " + size + "px " + family; size -= 4; } while (g.measureText(text).width > width && size > 24);
  }
  function picture(b, minutes) {
    var W = 1200, H = 675, P = 64, c = document.createElement("canvas"), g = c.getContext("2d");
    var serif = '"Literata", Georgia, serif', sans = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    var d = function (k) { return b.getAttribute("data-" + k) || ""; };
    c.width = W; c.height = H;
    g.fillStyle = "#fff"; g.fillRect(0, 0, W, H);
    g.textBaseline = "alphabetic";
    var brand = document.querySelector(".brand"), x = P;
    g.font = "700 40px " + serif;
    (brand ? brand.textContent : "Za ili Protiv").split(" ").forEach(function (w, i) {
      g.fillStyle = i === 0 ? "#1f5fa8" : i === 2 ? "#c2410c" : "#111";
      g.fillText(w, x, 84); x += g.measureText(w + " ").width;
    });
    g.fillStyle = "#555"; g.font = "400 26px " + sans; g.textAlign = "right";
    g.fillText(location.host, W - P, 82); g.textAlign = "left";
    g.fillStyle = "#111"; g.fillRect(P, 108, W - 2 * P, 4);
    g.fillStyle = "#c2410c"; g.beginPath(); g.arc(P + 11, 166, 11, 0, 7); g.fill();
    g.fillStyle = "#555"; g.font = "700 26px " + sans; g.fillText(d("head").toUpperCase(), P + 36, 175);
    g.fillStyle = "#111"; fit(g, d("name"), 700, 104, serif, W - 2 * P); g.fillText(d("name"), P, 290);
    g.fillStyle = "#555"; fit(g, d("side"), 400, 36, sans, W - 2 * P); g.fillText(d("side"), P, 344);
    g.fillStyle = "#555"; g.font = "400 34px " + sans; g.fillText(d("already"), P, 452);
    var w0 = g.measureText(d("already") + " ").width;
    g.fillStyle = "#111"; g.font = "700 150px " + serif; g.fillText(String(minutes), P + w0 + 6, 480);
    var w1 = g.measureText(String(minutes)).width;
    g.font = "700 56px " + serif; g.fillText(d("min"), P + w0 + w1 + 26, 480);
    g.fillStyle = "#111"; fit(g, d("line"), 600, 34, sans, W - 2 * P); g.fillText(d("line"), P, 548);
    g.fillStyle = "#555"; g.font = "400 24px " + sans;
    g.fillText(d("when") + " · " + d("note"), P, 622);
    return c;
  }
  var story = null;
  function stories() {
    var data = document.querySelector(".st-data");
    if (!data || story) return;
    var cards = [].slice.call(data.children).map(function (c) { return c.outerHTML; }), i = -1, timer = null;
    var secs = [].slice.call(data.children).map(function (c) { return +c.getAttribute("data-t") || 6; });  // more to read: longer
    var calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var el = document.createElement("div");
    el.className = "st"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true");
    el.innerHTML = '<div class="st-bar">' + cards.map(function () { return "<i><b></b></i>"; }).join("") + '</div>' +
      '<button type="button" class="st-x">×</button><div class="st-stage"></div><p class="st-hint"></p>';
    el.querySelector(".st-x").setAttribute("aria-label", data.getAttribute("data-close") || "");  // as text, never as markup
    el.querySelector(".st-hint").textContent = data.getAttribute("data-hint") || "";
    document.body.appendChild(el);
    var stage = el.querySelector(".st-stage"), bars = el.querySelectorAll(".st-bar i");
    function close() {
      clearTimeout(timer); el.remove(); story = null; document.removeEventListener("keydown", key);
      var back = document.querySelector(".st-open"); if (back) back.focus({ preventScroll: true });
    }
    function show(k) {
      if (k >= cards.length) { close(); return; }
      i = Math.max(0, k);
      stage.innerHTML = cards[i];
      for (var j = 0; j < bars.length; j++) { bars[j].className = j < i ? "done" : ""; }
      bars[i].style.setProperty("--st-t", secs[i] + "s");
      void bars[i].offsetWidth; bars[i].className = "on";
      clearTimeout(timer);
      if (!calm && i < cards.length - 1) timer = setTimeout(function () { show(i + 1); }, secs[i] * 1000);
    }
    function key(e) { if (e.key === "Escape") close(); else if (e.key === "ArrowRight") show(i + 1); else if (e.key === "ArrowLeft") show(i - 1); }
    el.addEventListener("click", function (e) {
      if (e.target.closest(".st-x")) { close(); return; }
      if (e.target.closest("a")) return;
      show(e.clientX < window.innerWidth / 3 ? i - 1 : i + 1);
    });
    document.addEventListener("keydown", key);
    story = el; show(0); el.querySelector(".st-x").focus();
  }
  function shareDay(b) {
    var url = location.origin + location.pathname, text = b.getAttribute("data-text") + " " + url;
    var said = b.parentNode.parentNode.querySelector(".share-said");
    var plain = function () {
      if (navigator.share) { navigator.share({ text: text }).catch(function () {}); return; }
      if (navigator.clipboard) navigator.clipboard.writeText(text).catch(function () {});
      if (said) { said.textContent = b.getAttribute("data-done"); said.hidden = false; }
    };
    fetch(b.getAttribute("data-src") + "?" + Date.now()).then(function (r) { if (!r.ok) throw 0; return r.blob(); }).then(function (blob) {
      var file = new File([blob], "ko-je-koliko-govorio.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], text: text }).catch(function () {}); return;
      }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(file); a.download = file.name; document.body.appendChild(a); a.click(); a.remove();
      if (navigator.clipboard) navigator.clipboard.writeText(text).catch(function () {});
      if (said) { said.textContent = b.getAttribute("data-done"); said.hidden = false; }
    }).catch(plain);
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target : null;
    if (t && t.closest(".rot-next, .rot")) { turn.skip++; rotate(); return; }
    var b = t && t.closest(".share-now");
    if (!b) return;
    if (b.classList.contains("st-open")) { stories(); return; }
    if (b.classList.contains("share-day")) { shareDay(b); return; }
    var k = document.querySelector(".clk"), minutes = Math.max(1, Math.floor((k ? seconds(k) : 0) / 60));
    var url = location.origin + location.pathname;
    var text = b.getAttribute("data-text").replace("%1", b.getAttribute("data-name")).replace("%2", minutes)
      .replace("%3", b.getAttribute("data-line")) + " " + url;
    var said = document.querySelector(".share-said");
    try {
      var c = picture(b, minutes), bin = atob(c.toDataURL("image/png").split(",")[1]), bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      var file = new File([bytes], "ko-sada-govori.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], text: text }).catch(function () {});
        return;
      }
      if (navigator.share) { navigator.share({ text: text }).catch(function () {}); return; }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(file); a.download = file.name; document.body.appendChild(a); a.click(); a.remove();
    } catch (err) { if (navigator.share) { navigator.share({ text: text }).catch(function () {}); return; } }
    if (navigator.clipboard) navigator.clipboard.writeText(text).catch(function () {});
    if (said) { said.textContent = b.getAttribute("data-done"); said.hidden = false; }
  });
})();
// More of the page's uses for the same counter as the broadcast's ▶ (mikrofon.js, "mikrofon.pusti"): a sum per day
// (1min and 5min per hour too), nothing with it, each at most once per page opened, so every count is "pages where
// this happened". Time out of sight is not counted. Only on the project's own hosts (25 Nov 2026), as in mikrofon.js:
// a test's page, or the service's own at 127.0.0.1, sends none of it.
(function () {
  var api = (document.body.getAttribute("data-api") || "").replace(/\/$/, "");
  if (!/^(mikrofon\.)?zailiprotiv\.rs$/.test(location.hostname) || !/^https:\/\//.test(api) || !window.fetch) return;
  var sent = {};
  function use(what) {
    if (sent[what]) return;
    sent[what] = 1;
    try {
      fetch(api + "/e", { method: "POST", headers: { "content-type": "text/plain" }, keepalive: true,
                          body: JSON.stringify({ e: "mikrofon." + what }) }).catch(function () {});
    } catch (err) {}
  }
  use("otvori");
  var seen = 0, marks = [[60, "1min"], [300, "5min"], [900, "15min"], [1800, "30min"]];
  var clock = setInterval(function () {
    if (document.hidden) return;
    seen++;
    for (var i = 0; i < marks.length; i++) if (seen >= marks[i][0]) use(marks[i][1]);
    if (seen >= 1800) clearInterval(clock);
  }, 1000);
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target : null;
    if (!t) return;
    if (t.closest(".play:not(.facade), .part")) use("snimak");
    else if (t.closest("#dnevni-red > summary")) use("tacke");
    else if (t.closest("#nx-ag > summary")) use("sledeca");
    else if (t.closest(".rot-next, .rot")) use("redovi");
    else if (t.closest(".st-open")) use("kartice");
    else if (t.closest(".share-day")) use("dan");
    else if (t.closest(".share-now")) use("podeli");
    var a = t.closest("a[href]");
    if (a && a.hostname === "zailiprotiv.rs") use("sajt");
  }, true);
  window.mikrofonUse = use;
})();
// "Ne propustite sednicu": the page on the phone's home screen, and a notification when a sitting's broadcast begins.
// Home screen (20 Nov 2026): opened from there is counted; elsewhere the browser's own offer to add the page is shown
// as our button when the browser makes one (Chrome, Edge, Samsung), and on an iPhone, which makes none, a line saying
// where Safari keeps it. Nothing is installed but the page's address and icon.
// Notifications (20 Nov 2026): on a press, the browser is asked for leave, the page's service worker (/sw.js) is
// registered and the browser's push address sent to the site's counter; "Isključi" takes it back there too. Counted
// (20 Nov 2026, one device had asked): the offer shown, pressed, refused by the browser's question, failed, and done.
(function () {
  var use = function (w) { if (window.mikrofonUse) window.mikrofonUse(w); };
  var box = document.querySelector(".add-home");
  if (!box) return;
  var part = function (k) { return box.querySelector("." + k); };
  function show(k, on) {
    var el = part(k); if (el) el.hidden = !on;
    if (k === "nt") document.documentElement.toggleAttribute("data-nt", on);  // the card's bell is shown with it
    box.hidden = ![].some.call(box.querySelectorAll(".nt, .add, .nt-done, .nt-blocked, .nt-err, .add-ios"), function (c) { return !c.hidden; });
  }
  var home = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone;
  if (home) use("ekran");
  else {
    var ask = null;
    window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); ask = e; show("add", true); });
    window.addEventListener("appinstalled", function () { show("add", false); use("dodato"); });
    // an iPhone makes no offer: the same button, and a press says where Safari keeps it (22 Nov 2026: no text under)
    var ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
    if (ios) show("add", true);
    part("add-go").addEventListener("click", function () {
      if (!ask) { if (ios) { show("add-ios", part("add-ios").hidden); use("dodaj"); } return; }
      use("dodaj"); ask.prompt();
      ask.userChoice.then(function () { ask = null; show("add", false); }).catch(function () {});
    });
  }
  var key = box.getAttribute("data-key") || "", api = (document.body.getAttribute("data-api") || "").replace(/\/$/, "");
  var cir = document.documentElement.lang === "sr-Cyrl";
  if (!key || !/^https:\/\//.test(api) || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return;
  function bytes(s) {
    var b = atob(s.replace(/-/g, "+").replace(/_/g, "/")), out = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) out[i] = b.charCodeAt(i);
    return out;
  }
  function tell(path, sub) {
    return fetch(api + path, { method: "POST", headers: { "content-type": "text/plain" },
                               body: JSON.stringify({ endpoint: sub.endpoint, cir: cir }) })
      .then(function (r) { if (!r.ok) throw new Error("counter " + r.status); });
  }
  function state(on) { show("nt", !on); show("nt-done", on); show("nt-err", false); }
  function failed() { show("nt-err", true); use("obavesti-greska"); }
  if (Notification.permission === "denied") { show("nt-blocked", true); return; }
  navigator.serviceWorker.getRegistration("/").then(function (r) { return r ? r.pushManager.getSubscription() : null; })
    .then(function (s) { state(!!s); if (!s) use("obavesti-moze"); }).catch(function () { state(false); });
  // the bell on the sitting's card (drawn anew with the part, so listened for from above) presses the same button
  document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest(".st-bell")) part("nt-on").click(); });
  part("nt-on").addEventListener("click", function () {
    use("obavesti-klik");
    Notification.requestPermission().then(function (p) {
      if (p !== "granted") { show("nt", false); show("nt-blocked", p === "denied"); use("obavesti-odbijeno"); return; }
      return navigator.serviceWorker.register("/sw.js" + (cir ? "?j=cir" : ""), { scope: "/" })
        .then(function () { return navigator.serviceWorker.ready; })
        .then(function (r) { return r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes(key) }); })
        .then(function (s) { return tell("/p", s); })
        .then(function () { state(true); use("obavesti"); });
    }).catch(failed);
  });
  part("nt-off").addEventListener("click", function () {
    navigator.serviceWorker.getRegistration("/").then(function (r) { return r ? r.pushManager.getSubscription() : null; })
      .then(function (s) { if (!s) return; return tell("/p/odjava", s).then(function () { return s.unsubscribe(); }); })
      .then(function () { state(false); use("odjavi"); }).catch(failed);
  });
})();
// "Sažetak dana na mejl": the form sent to the counter from the page (the reader stays here), and its answer shown.
// Without the script the form goes there itself and the counter answers with a page of its own.
(function () {
  var form = document.querySelector(".ml-box");
  if (!form || !window.fetch) return;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var body = new URLSearchParams(new FormData(form)); body.set("js", "1");
    var btn = form.querySelector("button"); btn.disabled = true;
    fetch(form.action, { method: "POST", body: body }).then(function (r) { return r.ok; }, function () { return false; }).then(function (ok) {
      form.querySelector(".ml-done").hidden = !ok; form.querySelector(".ml-err").hidden = ok;
      if (ok) { form.querySelector(".ml-row").hidden = true; if (window.mikrofonUse) window.mikrofonUse("mejl"); document.dispatchEvent(new Event("mejl-prijavljen")); }
      btn.disabled = false;
    });
  });
})();
// "Sažetak dana na mejl" put away, at the reader's word (24 Nov 2026, the maintainer): kept in this browser only, and
// taken back from the line at the foot. Signing up puts it away too. Nothing is sent.
(function () {
  var box = document.querySelector("details.ml"), x = document.querySelector(".ml-x"), back = document.querySelector(".ml-back");
  if (!box || !x || !back) return;
  function read() { try { return localStorage.getItem("mejl-sklonjen") === "1"; } catch (e) { return false; } }
  function keep(on) { try { if (on) localStorage.setItem("mejl-sklonjen", "1"); else localStorage.removeItem("mejl-sklonjen"); } catch (e) {} }
  function show(away) { box.hidden = away; x.hidden = away; back.hidden = !away; document.documentElement.toggleAttribute("data-ml-off", away); }
  show(read() && location.hash !== "#mejl");
  x.addEventListener("click", function () { keep(true); show(true); });
  back.querySelector("button").addEventListener("click", function () { keep(false); show(false); box.open = true; box.scrollIntoView({ block: "center" }); });
  document.addEventListener("mejl-prijavljen", function () { keep(true); });
})();
