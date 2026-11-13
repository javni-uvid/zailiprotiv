// The search page: Pagefind's own interface over the index built from the site's pages (pagefind/).
window.addEventListener("DOMContentLoaded", function () {
  if (!window.PagefindUI) return;
  var ui = new PagefindUI({ element: "#search", showSubResults: false, showImages: false, resetStyles: false, autofocus: true,
    translations: { placeholder: "Reč, zakon ili ime", clear_search: "Obriši", load_more: "Još rezultata", search_label: "Pretraga sajta",
      zero_results: "Nema rezultata za [SEARCH_TERM]", many_results: "[COUNT] rezultata za [SEARCH_TERM]", one_result: "[COUNT] rezultat za [SEARCH_TERM]",
      searching: "Tražim [SEARCH_TERM]…" } });
  var q = new URLSearchParams(location.search).get("q");
  if (q) ui.triggerSearch(q);
});
