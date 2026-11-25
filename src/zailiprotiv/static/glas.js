// A law's page: the visitor's own vote, and the quotes that convinced them. One vote to a device (a random mark
// this browser makes up and keeps; the counter stores only its hash), replaced by a later one. What other visitors
// chose is shown after voting. Everything is kept in this browser too, so the page remembers without asking.
(function () {
  "use strict";
  var box = document.getElementById("glasaj");
  if (!box || !window.fetch || !window.localStorage) return;
  var api = box.dataset.api.replace(/\/$/, ""), item = box.dataset.item;
  var WORD = { z: "za", p: "protiv", u: "uzdržan" }, ROLL = { z: "za", p: "protiv", u: "uzdrzan" };
  function read(key, empty) { try { return JSON.parse(localStorage.getItem(key)) || empty; } catch (e) { return empty; } }
  function write(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {} }
  function device() {
    var d = null;
    try { d = localStorage.getItem("zip.d"); } catch (e) {}
    if (!d || !/^[A-Za-z0-9_-]{16,64}$/.test(d)) {
      var a = new Uint8Array(18); (window.crypto || window.msCrypto).getRandomValues(a);
      d = Array.prototype.map.call(a, function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
      try { localStorage.setItem("zip.d", d); } catch (e) {}
    }
    return d;
  }
  var votes = read("zip.glasovi", {}), marks = read("zip.citati", {}), mine = votes[item] || "";
  var bill = !box.dataset.svi;  // a bill in procedure: the Assembly has not voted, so there is nothing to compare with yet
  var ask = box.querySelector(".yv-ask"), btns = box.querySelector(".yv-btns"), done = box.querySelector(".yv-done"), cmp = box.querySelector(".yv-cmp");
  var quotes = Array.prototype.slice.call(document.querySelectorAll("blockquote.quote[data-q]"));
  box.hidden = false;

  function bar(el, z, rest, p) {
    var all = z + rest + p || 1, parts = el.querySelectorAll("i");
    parts[0].style.width = (100 * z / all) + "%"; parts[1].style.width = (100 * rest / all) + "%"; parts[2].style.width = (100 * p / all) + "%";
  }
  function num(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function plural(n, one, few, many) { var d = n % 10, h = n % 100; return d === 1 && h !== 11 ? one : d >= 2 && d <= 4 && (h < 12 || h > 14) ? few : many; }
  function show(t) {  // t: this law's totals from the counter, or null when it did not answer
    ask.hidden = btns.hidden = !!mine; done.hidden = cmp.hidden = !mine;
    if (!mine) return;
    var you = box.querySelector(".yv-you"); you.textContent = WORD[mine]; you.className = "yv-you v-" + mine;
    var like = box.querySelector(".yv-like"), n = mine === "z" ? +box.dataset.za : mine === "p" ? +box.dataset.protiv : 0;
    like.innerHTML = "";
    if (bill) like.appendChild(document.createTextNode("Poslanici još nisu glasali. "));
    else if (mine !== "u") {
      like.appendChild(document.createTextNode("Kao " + n + " " + plural(n, "poslanik", "poslanika", "poslanika") + ". "));
      var who = document.createElement("a"); who.href = "#roll"; who.textContent = "Ko su"; like.appendChild(who);
      like.appendChild(document.createTextNode(" · "));
      who.addEventListener("click", function () {
        var sel = document.getElementById("r-v"), roll = document.getElementById("roll"), d = roll && roll.closest("details");
        if (sel) { sel.value = ROLL[mine]; sel.dispatchEvent(new Event("change")); }
        if (d) d.open = true;
      });
    }
    if (!bill) bar(box.querySelector(".yv-bar-a"), +box.dataset.za, +box.dataset.svi - box.dataset.za - box.dataset.protiv, +box.dataset.protiv);
    if (t) {
      box.querySelector(".yv-nz").textContent = num(t.z); box.querySelector(".yv-np").textContent = num(t.p);
      box.querySelector(".yv-nu").textContent = t.u ? num(t.u) + " " + plural(t.u, "uzdržan", "uzdržana", "uzdržanih") : "";
      bar(box.querySelector(".yv-bar-b"), t.z, t.u, t.p);
      quotes.forEach(function (q) { var c = q.querySelector(".mark span"); if (c) c.textContent = (t.c && t.c[q.dataset.q]) || 0; });
    }
  }
  function post(path, body) {
    if (!window.zipOwn) return Promise.reject(new Error("host"));  // site.js: only on the project's own hosts
    return fetch(api + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }
  btns.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-v]"); if (!b) return;
    votes = read("zip.glasovi", {});  // another tab may have voted meanwhile
    mine = b.dataset.v; votes[item] = mine; write("zip.glasovi", votes);
    try { document.dispatchEvent(new CustomEvent("zip:glas")); } catch (e) {}
    show(null);
    var sent = item;
    post("/z", { d: device(), item: item, v: mine }).then(function (t) { if (sent === item) show(t); }).catch(function () {
      box.querySelector(".yv-nu").textContent = "Zbir posetilaca trenutno nije dostupan; tvoj glas je zapamćen u ovom pregledaču.";
    });
  });
  box.querySelector(".yv-again").addEventListener("click", function () { mine = ""; show(null); });

  // Each quote of the debate can be marked as convincing, as many as one likes; the counts show once one has voted.
  var own = marks[item] || [];
  quotes.forEach(function (q) {
    var b = document.createElement("button"), c = document.createElement("span");
    b.type = "button"; b.className = "mark"; b.setAttribute("aria-pressed", own.indexOf(q.dataset.q) >= 0 ? "true" : "false");
    b.appendChild(document.createTextNode("Ubedljivo ")); b.appendChild(c);
    q.appendChild(b);
    b.addEventListener("click", function () {
      var on = b.getAttribute("aria-pressed") !== "true";
      b.setAttribute("aria-pressed", on ? "true" : "false");
      own = own.filter(function (x) { return x !== q.dataset.q; }); if (on) own.push(q.dataset.q);
      marks[item] = own; write("zip.citati", marks);
      post("/c", { d: device(), item: item, q: q.dataset.q, on: on }).then(function (t) { if (mine) show(t); }).catch(function () {});
    });
  });
  function open() {
    var asked = item;
    box.querySelector(".yv-nz").textContent = box.querySelector(".yv-np").textContent = "…"; box.querySelector(".yv-nu").textContent = "";
    bar(box.querySelector(".yv-bar-b"), 0, 0, 0);
    show(null);
    if (mine && window.zipOwn) fetch(api + "/z/" + encodeURIComponent(item)).then(function (r) { return r.ok ? r.json() : null; }).then(function (t) { if (t && asked === item) show(t); }).catch(function () {});
  }
  open();
  // "Glasaj i ti" puts another bill into the same box (listic.js): the box then starts again with that one.
  document.addEventListener("zip:predlog", function () {
    item = box.dataset.item; votes = read("zip.glasovi", {}); mine = votes[item] || "";
    open();
  });
})();
