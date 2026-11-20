// The search page: Pagefind's own interface over the index built from the site's pages (pagefind/) and, when it
// answers, the index of the stenographic notes' pages (their own address, a bucket), where a hit is a speech:
// the notes' pages have a heading with an address for each speech, so a result leads to the speech itself.
window.addEventListener("DOMContentLoaded", function () {
  if (!window.PagefindUI) return;
  var box = document.getElementById("search"), notes = box.dataset.notes || "";
  // Latin without its marks finds the words with them, and the other way round: Pagefind (from 1.5) takes c for č
  // and ć, s for š, z for ž. It does not take "dj" for "đ", so that is done here: for each word typed with "dj" or
  // "đ" both spellings are counted, and the search runs with the one that finds more. Counting is asked of the same
  // index and takes a moment, so the first search runs as typed and is run again when the count says otherwise.
  var better = {}, asked = {}, ui = null, engine = null;
  // Counted for the counter's sum per day (site.js, once per page): a search run, one that still has no result two
  // seconds after the last letter typed, a result opened. Never the words: only that it happened.
  var quiet = null;
  function counted(text) {
    if (!window.zipCount || text.trim().length < 2) return;
    zipCount("pretraga.trazi");
    clearTimeout(quiet);
    quiet = setTimeout(function () {
      var msg = document.querySelector("#search .pagefind-ui__message");
      if (msg && msg.textContent.trim() && !document.querySelector("#search .pagefind-ui__result")
          && !/^Tražim|^Тражим/.test(msg.textContent.trim())) zipCount("pretraga.prazno");
    }, 2000);
  }
  box.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest(".pagefind-ui__result a");
    if (a && window.zipCount) zipCount("pretraga.klik");
  });
  function spellings(word) {
    var low = word.toLowerCase(), out = [];
    if (low.indexOf("dj") >= 0) out.push(word.replace(/dj/g, "đ").replace(/Dj|DJ/g, "Đ"));
    if (/đ/i.test(word)) out.push(word.replace(/đ/g, "dj").replace(/Đ/g, "Dj"));
    return out;
  }
  function term(text) {
    return text.split(/(\s+)/).map(function (w) { return better[w] || w; }).join("");
  }
  function count(text) {
    text.split(/\s+/).forEach(function (w) {
      var others = spellings(w.replace(/["“”„]/g, ""));
      if (!others.length || asked[w]) return;
      asked[w] = 1;
      (engine = engine || import(new URL("pagefind/pagefind.js", document.baseURI).href)).then(function (pf) {
        return Promise.all([w].concat(others).map(function (x) { return pf.search(x.replace(/["“”„]/g, "")).then(function (r) { return [x, r.results.length]; }); }));
      }).then(function (found) {
        var best = found.slice().sort(function (a, b) { return b[1] - a[1]; })[0];
        if (best[0] !== w && best[1] > found[0][1]) {
          better[w] = best[0];
          var input = document.querySelector("#search .pagefind-ui__search-input");
          if (ui && input && input.value.split(/\s+/).indexOf(w) >= 0) {
            // The same words again would not be searched again, so a space is added (or taken away) to ask anew.
            ui.triggerSearch(/ $/.test(input.value) ? input.value.replace(/ +$/, "") : input.value + " ");
          }
        }
      }).catch(function () {});
    });
  }
  function start(merge) {
    ui = new PagefindUI({ processTerm: function (t) { count(t); counted(t); return term(t); }, element: "#search", showSubResults: true, showImages: false, resetStyles: false, autofocus: true,
      mergeIndex: merge ? [{ bundlePath: notes + "pagefind/", baseUrl: notes }] : [],
      // A result from the notes is a whole day's page. Its heading becomes the speaker of the speech with the most
      // hits and leads to that speech, not to the top of the day; the other speeches of the day follow beneath. Every
      // link into the notes carries the words searched for, which the notes' pages then mark.
      processResult: function (r) {
        var input = document.querySelector("#search .pagefind-ui__search-input");
        var words = input ? input.value.replace(/["“”„]/g, " ").trim().split(/\s+/).filter(Boolean) : [];
        var marked = function (url) {
          if (!notes || url.indexOf(notes) !== 0 || !words.length) return url;
          var at = url.indexOf("#"), base = at < 0 ? url : url.slice(0, at), hash = at < 0 ? "" : url.slice(at);
          return base + (base.indexOf("?") < 0 ? "?" : "&") + words.map(function (w) { return "highlight=" + encodeURIComponent(w); }).join("&") + hash;
        };
        var subs = (r.sub_results || []).filter(function (x) { return x.url && x.url.indexOf("#") > 0; });
        (r.sub_results || []).forEach(function (x) { x.url = marked(x.url); });
        if (subs.length) {
          var best = subs.slice().sort(function (a, b) { return (b.locations || []).length - (a.locations || []).length; })[0];
          r.url = best.url;
          r.excerpt = best.excerpt;
          r.meta = Object.assign({}, r.meta, { title: best.title + " · " + (r.meta && r.meta.title || "") });
        } else r.url = marked(r.url);
        return r;
      },
      translations: { placeholder: "Reč, zakon ili ime", clear_search: "Obriši", load_more: "Još rezultata", search_label: "Pretraga sajta",
        zero_results: "Nema rezultata za [SEARCH_TERM]", many_results: "[COUNT] rezultata za [SEARCH_TERM]", one_result: "[COUNT] rezultat za [SEARCH_TERM]",
        searching: "Tražim [SEARCH_TERM]…" } });
    var q = new URLSearchParams(location.search).get("q");
    if (q) ui.triggerSearch(q);
  }
  // The notes' index is asked for first: if it does not answer (not built yet, or the bucket does not let this
  // site read it), the search goes on over the site alone.
  if (!notes || !window.fetch) return start(false);
  var done = false, go = function (ok) { if (!done) { done = true; start(ok); } };
  fetch(notes + "pagefind/pagefind-entry.json", { mode: "cors" }).then(function (r) { go(r.ok); }).catch(function () { go(false); });
  setTimeout(function () { go(false); }, 2500);
});
