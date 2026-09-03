import Swal from "sweetalert2";
import {loadMoreResults} from "./results.js";
import {resetAllFilters, resetFiltersForNewSearch, toggleFilter, restoreFiltersFromUrl} from "./filterController.js";
import {buildSearchUrlParams, getSearchQuery} from "./searchParams.js";
import {selectedIds} from "./state.js";
import {updateTableContainerHeight} from "./utils.js";
import {attachYearsEvents} from "./yearsView.js";

// Attach all the user events of the results page towards appropriate actions (checkboxes, export, reset...)
export function attachEventListeners() {
  $(document)
    .off("change.requestDdiFilter", ".filter-checkbox")
    .on("change.requestDdiFilter", ".filter-checkbox", function () {
      toggleFilter(this.dataset.filterType, this.value);
    });

  attachYearsEvents();

  $("#reset-filters").off("click").on("click", resetAllFilters);
  $("#load-more").off("click").on("click", loadMoreResults);
  $("#export-all").off("click").on("click", exportAll);
  $("#export-selected").off("click").on("click", exportSelected);

  $("#survey-table tbody")
    .off("change.requestDdiSelection", "input[type='checkbox']")
    .on("change.requestDdiSelection", "input[type='checkbox']", updateSelection);

  $("form.search-bar")
    .off("submit.requestDdiSearch")
    .on("submit.requestDdiSearch", event => {
      event.preventDefault();
      resetFiltersForNewSearch();
      window.location.reload();
    });

  $(window).off("resize.requestDdi").on("resize.requestDdi", updateTableContainerHeight);
}

function exportAll() {
  const params = buildSearchUrlParams();
  const exportParams = new URLSearchParams();

  if (getSearchQuery()) exportParams.set("q", getSearchQuery());
  params.getAll("survey").forEach(value => exportParams.append("survey", value));
  params.getAll("collection").forEach(value => exportParams.append("collections", value));
  params.getAll("sub_collection").forEach(value => exportParams.append("sub_collections", value));
  params.getAll("search_location").forEach(value => exportParams.append("search_location", value));
  params.getAll("years").forEach(value => exportParams.append("years", value));

  window.location.href = `/export/questions/?${exportParams.toString()}`;
}

function exportSelected() {
  if (selectedIds.size === 0) {
    Swal.fire({
      html: `
        <div style="text-align: center;">
          <img src="/static/svg/icons/checkbox_checked_swal.svg" style="width: 32px;">
        </div>
        <div>Veuillez sélectionner au moins une question à exporter.</div>
      `,
      confirmButtonText: "Fermer",
      confirmButtonColor: "#536254",
    });
    return;
  }

  const params = new URLSearchParams();
  selectedIds.forEach(id => params.append("ids", id));
  window.location.href = `/export/questions/?${params.toString()}`;
}

function updateSelection() {
  if (this.checked) selectedIds.add(this.value);
  else selectedIds.delete(this.value);

  const all = $("#survey-table tbody input[type='checkbox']");
  const checked = $("#survey-table tbody input[type='checkbox']:checked");
  $("#select-all")
    .prop("checked", all.length > 0 && all.length === checked.length)
    .prop("indeterminate", checked.length > 0 && all.length !== checked.length);
}

window.addEventListener("popstate", async () => {
  await restoreFiltersFromUrl(true, false);
});