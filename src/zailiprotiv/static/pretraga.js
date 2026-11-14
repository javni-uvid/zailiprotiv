// The search page: Pagefind's own interface over the index built from the site's pages (pagefind/) and, when it
// answers, the index of the stenographic notes' pages (their own address, a bucket), where a hit is a speech:
// the notes' pages have a heading with an address for each speech, so a result leads to the speech itself.
window.addEventListener("DOMContentLoaded", function () {
  if (!window.PagefindUI) return;
  var box = document.getElementById("search"), notes = box.dataset.notes || "";
  function start(merge) {
    var ui = new PagefindUI({ element: "#search", showSubResults: true, showImages: false, resetStyles: false, autofocus: true,
      mergeIndex: merge ? [{ bundlePath: notes + "pagefind/", baseUrl: notes }] : [],
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
