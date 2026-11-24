// The mikrofon page's script, in both its versions (the live service's page and the site's), inline in each.
(function () {
  // The player (AGENTS.md, principle 5): nothing from YouTube or the archive loads until a click asks for it.
  var screen = document.getElementById("screen");
  if (!screen) return;
  var ARCHIVE = /^https:\/\/arhiva\.videonet\.co\.rs\//, ID = /^[\w-]{6,20}$/;
  function put(el) { screen.textContent = ""; screen.appendChild(el); }
  // A press on the broadcast's ▶ told to the site's counter, once per page: a sum per day, nothing with it.
  var told = {};
  function count(what) {
    var api = (document.body.getAttribute("data-api") || "").replace(/\/$/, "");
    if (!what || !/^https:\/\//.test(api) || told[what]) return;
    told[what] = 1;
    try { fetch(api + "/e", { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify({ e: what }), keepalive: true }).catch(function () {}); } catch (e) {}
  }
  // Each checks what it is given itself: whoever calls them, only a YouTube id or an archive file is ever played.
  function yt(id, t) {
    if (!ID.test(id || "")) return;
    var f = document.createElement("iframe");
    // enablejsapi: the player tells the page by messages which moment it shows (the live page's line under it)
    f.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(id) + "?autoplay=1&enablejsapi=1&origin=" +
      encodeURIComponent(location.origin) + (t > 0 ? "&start=" + t : "");
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.title = "YouTube";
    put(f);
  }
  // The day's turns with their place in the archive's files (each turn's "▶ snimak"), from the page as it is now:
  // who speaks at a moment of a file, and the turn before or after it.
  function turns(url) {
    var out = [];
    [].forEach.call(document.querySelectorAll("li[id] [data-file][data-t]"), function (a) {
      if (a.getAttribute("data-file") !== url) return;
      var li = a.closest("li"), name = li.querySelector("a[href*='poslanik/']") || null;
      // the line beside the name (the list or the office): not the hours, not "· 3 min", not a link
      var side = [].filter.call(li.children, function (m) {
        return /\b(meta|label)\b/.test(m.className) && m.tagName === "SPAN" && !/^[·\d]/.test(m.textContent.trim());
      })[0];
      var who = name ? name.textContent.trim() : (li.textContent.replace(/^[\s\d:–-]+/, "").split("·")[0].trim());
      var said = li.querySelector("details.prepis p");
      out.push({ t: +a.getAttribute("data-t") || 0, who: who, side: side ? side.textContent.trim() : "",
                 said: said ? said.textContent.trim() : "", li: li });
    });
    return out.sort(function (x, y) { return x.t - y.t; });
  }
  function at(list, sec) { var k = -1; for (var i = 0; i < list.length; i++) if (list[i].t <= sec + 1) k = i; return k; }
  // The lock screen's (and a car's, where the phone shows it) player (22 Nov 2026, the maintainer: the page as an
  // app, to listen in the car): who speaks now, the sitting's day, back and on by 15 and 30 s, and ⏮ ⏭ to the
  // turn before or after. Only for the archive's files, which the page plays itself; YouTube's player keeps its own.
  var title = (document.querySelector("h1") || {}).textContent || "Narodna skupština";
  var day = document.querySelector(".sec-h h2, main h2");
  function session(v, url) {
    if (!("mediaSession" in navigator)) return;
    var ms = navigator.mediaSession, shown = null;
    function now() {
      var list = turns(url), k = at(list, v.currentTime), x = k >= 0 ? list[k] : null;
      var key = x ? x.who + "|" + x.t : "";
      if (key !== shown) {
        shown = key;
        try {
          ms.metadata = new MediaMetadata({ title: x ? x.who : title.trim(), artist: x && x.side ? x.side : "Narodna skupština",
            album: (day ? day.textContent.trim() + " · " : "") + "Za ili Protiv",
            artwork: [{ src: "/ikona-512.png", sizes: "512x512", type: "image/png" }] });
        } catch (e) {}
        var card = screen.querySelector(".listen-now");
        if (card) {
          card.querySelector("b").textContent = x ? x.who : "";
          card.querySelector("span").textContent = x && x.side ? x.side : "";
          var p = card.querySelector("p"); p.textContent = x && x.said ? x.said.slice(0, 400) + (x.said.length > 400 ? " …" : "") : ""; p.hidden = !p.textContent;
        }
        [].forEach.call(document.querySelectorAll("li.now-playing"), function (li) { li.classList.remove("now-playing"); });
        if (x) x.li.classList.add("now-playing");
      }
      if (ms.setPositionState && isFinite(v.duration) && v.duration > 0) {
        try { ms.setPositionState({ duration: v.duration, position: Math.min(v.currentTime, v.duration), playbackRate: v.playbackRate || 1 }); } catch (e) {}
      }
    }
    function turn(step) {  // ⏭ the next turn; ⏮ the start of this one, or the one before when just begun
      var list = turns(url), k = at(list, v.currentTime);
      var to = step > 0 ? k + 1 : (k >= 0 && v.currentTime - list[k].t > 5 ? k : k - 1);
      if (to >= 0 && to < list.length) v.currentTime = list[to].t;
    }
    var h = { play: function () { v.play(); }, pause: function () { v.pause(); },
              seekbackward: function (d) { v.currentTime = Math.max(0, v.currentTime - ((d && d.seekOffset) || 15)); },
              seekforward: function (d) { v.currentTime = v.currentTime + ((d && d.seekOffset) || 30); },
              seekto: function (d) { if (d && typeof d.seekTime === "number") v.currentTime = d.seekTime; },
              previoustrack: function () { turn(-1); }, nexttrack: function () { turn(1); } };
    Object.keys(h).forEach(function (k) { try { ms.setActionHandler(k, h[k]); } catch (e) {} });
    var last = 0;
    v.addEventListener("timeupdate", function () { var n = Date.now(); if (n - last > 1000) { last = n; now(); } });
    v.addEventListener("play", function () { ms.playbackState = "playing"; now(); });
    v.addEventListener("pause", function () { ms.playbackState = "paused"; });
  }
  // Only the sound ("Slušaj zvuk"): the same file in an <audio>, which a phone keeps playing with the screen locked,
  // and over it who speaks and, where the page has it, the automatic transcript of that turn.
  function file(url, t, sound) {
    if (!ARCHIVE.test(url || "")) return;
    var v = screen.querySelector("video, audio");
    if (sound === undefined) sound = !!(v && v.tagName === "AUDIO");  // a turn's ▶ keeps the way the day is played
    if (!v || v.getAttribute("src") !== url || (v.tagName === "AUDIO") !== sound) {
      v = document.createElement(sound ? "audio" : "video");
      v.controls = true; v.preload = "metadata";
      if (!sound) v.playsInline = true;
      v.setAttribute("src", url);
      v.addEventListener("ended", function () {  // a day in several files: on to the next one
        var parts = document.querySelectorAll(".part[data-file]");
        for (var i = 0; i < parts.length - 1; i++) if (parts[i].getAttribute("data-file") === url) { file(parts[i + 1].getAttribute("data-file"), 0, sound); break; }
      });
      if (sound) {
        var box = document.createElement("div");
        box.className = "listen-box";
        box.innerHTML = '<div class="listen-now"><b></b><span></span><p hidden></p></div>';
        box.appendChild(v);
        put(box);
      } else put(v);
      session(v, url);
    }
    var parts = document.querySelectorAll(".part[data-file]");
    for (var j = 0; j < parts.length; j++) parts[j].classList.toggle("on", parts[j].getAttribute("data-file") === url);
    var go = function () { v.currentTime = t || 0; var p = v.play(); if (p && p.catch) p.catch(function () {}); };
    if (v.readyState >= 1) go(); else v.addEventListener("loadedmetadata", go, { once: true });
  }
  // The live sound, ours (live/uzivo/slusaj.py): only that one address, on this page's own host. Who speaks comes
  // from the page's part, which is asked again every 5 s; the lock screen's player says it too.
  function sound(url) {
    if (url !== "/slusaj/z.m3u8" && !/^https:\/\/zvuk\.zailiprotiv\.rs\/uzivo\/z\.m3u8$/.test(url || "")) return;
    var box = document.createElement("div"), v = document.createElement("audio");
    box.className = "listen-box";
    box.innerHTML = '<div class="listen-now"><b></b><span></span><p hidden></p></div>';
    box.querySelector(".listen-now").insertAdjacentHTML("afterbegin", '<i class="listen-k">🎧 ' + (document.documentElement.lang === "sr-Cyrl" ? "Само звук, уживо" : "Samo zvuk, uživo") + "</i>");
    v.controls = true; v.preload = "none"; v.setAttribute("src", url);
    box.appendChild(v);
    put(box);
    var shown = "";
    function now() {
      if (!screen.contains(v)) { clearInterval(timer); return; }
      var w = document.querySelector("#deo .who"), s = document.querySelector("#deo .side");
      var who = w ? w.textContent.trim() : "", side = s ? s.textContent.trim() : "";
      box.querySelector("b").textContent = who; box.querySelector("span").textContent = side;
      if ("mediaSession" in navigator && who + side !== shown) {
        shown = who + side;
        try {
          navigator.mediaSession.metadata = new MediaMetadata({ title: who || "Narodna skupština", artist: side || "Narodna skupština",
            album: "Skupština uživo · Za ili Protiv", artwork: [{ src: "/ikona-512.png", sizes: "512x512", type: "image/png" }] });
        } catch (e) {}
      }
    }
    var timer = setInterval(now, 2000);
    now();
    var p = v.play(); if (p && p.catch) p.catch(function () {});
  }
  // The button under the broadcast swaps: while our sound plays it offers the picture, while the picture plays the
  // sound, so that either is one press away (22 Nov 2026, the maintainer: "probati i jednu i drugu opciju").
  var swap = document.querySelector(".listen-live"), facade = document.querySelector(".play.facade");
  var liveSound = swap ? swap.getAttribute("data-uzivo") : "", swapText = swap ? swap.innerHTML : "", watchText = facade ? facade.getAttribute("data-text") || "" : "";
  function offer(picture) {
    if (!swap || !facade) return;
    if (picture) { swap.removeAttribute("data-uzivo"); swap.setAttribute("data-yt", facade.getAttribute("data-yt")); swap.setAttribute("data-t", "0"); swap.textContent = watchText; }
    else { swap.removeAttribute("data-yt"); swap.setAttribute("data-uzivo", liveSound); swap.innerHTML = swapText; }
  }
  document.addEventListener("click", function (e) {
    var live = e.target.closest ? e.target.closest("[data-uzivo]") : null;
    if (live) { e.preventDefault(); sound(live.getAttribute("data-uzivo")); offer(true); count("mikrofon.slusaj"); screen.scrollIntoView({ behavior: "smooth", block: "center" }); return; }
    var a = e.target.closest ? e.target.closest("[data-file], [data-yt]") : null;
    if (!a) return;
    var url = a.getAttribute("data-file"), id = a.getAttribute("data-yt"), t = +a.getAttribute("data-t") || 0;
    if (url ? !ARCHIVE.test(url) : !ID.test(id || "")) return;
    e.preventDefault();
    if (url) file(url, t, a.hasAttribute("data-zvuk") ? true : undefined); else { yt(id, t); offer(false); }
    count(a.getAttribute("data-e"));
    if (!screen.contains(a)) screen.scrollIntoView({ behavior: "smooth", block: "center" });
  });
})();
(function () {
  // The quiz: one question at a time, like the site's quiz; a score and a share at the end. Without the script
  // every question shows, each answer under "Odgovor". All the words are in the page, none in here.
  var box = document.getElementById("mq");
  if (!box) return;
  var qs = Array.prototype.slice.call(box.querySelectorAll(".mq-q")), end = box.querySelector(".mq-end");
  var strip = box.querySelector(".mq-strip"), marks = strip ? Array.prototype.slice.call(strip.querySelectorAll("button")) : [];
  var got = 0, done = 0, at = 0, timer = null, AUTO = 4000;
  box.classList.add("on");
  if (strip) strip.hidden = false;
  function show(i) {
    at = i;
    qs.forEach(function (q, k) { q.hidden = k !== i; });
    end.hidden = i !== qs.length;
    marks.forEach(function (m, k) { m.classList.toggle("mq-now", k === i); });
  }
  function stay() { clearTimeout(timer); var r = box.querySelector(".mq-auto.run"); if (r) r.classList.remove("run"); }
  function next(i) {
    stay();
    show(Math.min(i + 1, qs.length));
    if (box.getBoundingClientRect().top < 0) box.scrollIntoView({ block: "start" });
  }
  qs.forEach(function (q, i) {
    q.querySelectorAll(".mq-o").forEach(function (b) {
      b.addEventListener("click", function () {
        if (q.classList.contains("done")) return;
        var a = +q.getAttribute("data-a"), ok = +b.getAttribute("data-i") === a;
        q.querySelectorAll(".mq-o")[a].classList.add("right");
        if (!ok) b.classList.add("wrong");
        q.classList.add("done", ok ? "ok" : "miss");
        q.querySelector("details").open = true;
        if (ok) got++;
        done++;
        if (marks[i]) marks[i].classList.add(ok ? "m-ok" : "m-miss");
        box.querySelectorAll(".mq-got").forEach(function (g) { g.textContent = got; });
        if (done === qs.length) {
          var key = got === qs.length ? "all" : got ? "some" : "none";
          end.querySelectorAll("[data-k]").forEach(function (p) { p.hidden = p.getAttribute("data-k") !== key; });
        }
        var bar = q.querySelector(".mq-auto");
        if (bar) { void bar.offsetWidth; bar.classList.add("run"); }
        timer = setTimeout(function () { if (at === i) next(i); }, AUTO);
      });
    });
    q.querySelector(".mq-go").addEventListener("click", function () { next(i); });
    ["pointerdown", "keydown", "touchstart"].forEach(function (ev) {
      q.querySelector(".mq-why").addEventListener(ev, function (e) { if (!e.target.closest(".mq-go")) stay(); }, { passive: true });
    });
  });
  marks.forEach(function (m, k) { m.addEventListener("click", function () { stay(); show(k); }); });
  end.querySelector(".mq-again").addEventListener("click", function () {
    got = done = 0;
    qs.forEach(function (q) {
      q.classList.remove("done", "ok", "miss");
      q.querySelector("details").open = false;
      q.querySelectorAll(".mq-o").forEach(function (b) { b.classList.remove("right", "wrong"); });
    });
    marks.forEach(function (m) { m.classList.remove("m-ok", "m-miss"); });
    end.querySelectorAll("[data-k]").forEach(function (p) { p.hidden = true; });
    box.querySelectorAll(".mq-got").forEach(function (g) { g.textContent = 0; });
    show(0);
  });
  end.querySelector(".mq-share").addEventListener("click", function () {
    var text = end.querySelector(".mq-share-text").textContent.replace(/\s+/g, " ").trim(), url = location.href.split("#")[0];
    var said = end.querySelector(".mq-shared");
    if (navigator.share) navigator.share({ text: text, url: url }).catch(function () {});
    else if (navigator.clipboard) navigator.clipboard.writeText(text + " " + url).then(function () { said.hidden = false; });
  });
  show(0);
})();

// "podeli" beside a turn (govornici/<date>): the page's address at that turn, by the share sheet or copied.
(function () {
  "use strict";
  document.addEventListener("click", function (e) {
    var b = e.target.closest ? e.target.closest(".share-turn") : null;
    if (!b) return;
    var url = location.href.split("#")[0] + b.getAttribute("data-share"), text = b.getAttribute("data-text") || "";
    if (navigator.share) { navigator.share({ text: text, url: url }).catch(function () {}); return; }
    var done = document.querySelector(".share-done");
    if (navigator.clipboard) navigator.clipboard.writeText(text + " " + url).then(function () { if (done) done.hidden = false; });
  });
})();
