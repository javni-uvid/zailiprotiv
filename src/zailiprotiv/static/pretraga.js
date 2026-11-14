// The search page: Pagefind's own interface over the index built from the site's pages (pagefind/) and, when it
// answers, the index of the stenographic notes' pages (their own address, a bucket), where a hit is a speech:
// the notes' pages have a heading with an address for each speech, so a result leads to the speech itself.
window.addEventListener("DOMContentLoaded", function () {
  if (!window.PagefindUI) return;
  var box = document.getElementById("search"), notes = box.dataset.notes || "";
  function start(merge) {
    var ui = new PagefindUI({ element: "#search", showSubResults: true, showImages: false, resetStyles: false, autofocus: true,
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
