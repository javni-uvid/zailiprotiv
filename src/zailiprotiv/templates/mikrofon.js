// The mikrofon page's script, in both its versions (the live service's page and the site's), inline in each.
(function () {
  // The player (AGENTS.md, principle 5): nothing from YouTube or the archive loads until a click asks for it.
  var screen = document.getElementById("screen");
  if (!screen) return;
  var ARCHIVE = /^https:\/\/arhiva\.videonet\.co\.rs\//, ID = /^[\w-]{6,20}$/;
  function put(el) { screen.textContent = ""; screen.appendChild(el); }
  function yt(id, t) {
    var f = document.createElement("iframe");
    f.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1" + (t > 0 ? "&start=" + t : "");
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.title = "YouTube";
    put(f);
  }
  function file(url, t) {
    var v = screen.querySelector("video");
    if (!v || v.getAttribute("src") !== url) {
      v = document.createElement("video");
      v.controls = true; v.playsInline = true; v.preload = "metadata";
      v.setAttribute("src", url);
      v.addEventListener("ended", function () {  // a day in several files: on to the next one
        var parts = document.querySelectorAll(".part[data-file]");
        for (var i = 0; i < parts.length - 1; i++) if (parts[i].getAttribute("data-file") === url) { file(parts[i + 1].getAttribute("data-file"), 0); break; }
      });
      put(v);
    }
    var parts = document.querySelectorAll(".part[data-file]");
    for (var j = 0; j < parts.length; j++) parts[j].classList.toggle("on", parts[j].getAttribute("data-file") === url);
    var go = function () { v.currentTime = t || 0; var p = v.play(); if (p && p.catch) p.catch(function () {}); };
    if (v.readyState >= 1) go(); else v.addEventListener("loadedmetadata", go, { once: true });
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("[data-file], [data-yt]") : null;
    if (!a) return;
    var url = a.getAttribute("data-file"), id = a.getAttribute("data-yt"), t = +a.getAttribute("data-t") || 0;
    if (url ? !ARCHIVE.test(url) : !ID.test(id || "")) return;
    e.preventDefault();
    if (url) file(url, t); else yt(id, t);
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
