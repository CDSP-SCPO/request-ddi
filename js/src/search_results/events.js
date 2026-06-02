import Swal from "sweetalert2";
import { selectedIds, updateCheckboxes, updateTableContainerHeight, incrementLimit, clearCache, resetCurrentLimit } from "./utils.js";
import {
  filterState,
  updateFiltersDisplay,
  updateFilterCounts,
  updateDecadeCheckboxes
} from "./filters.js";
import { handleFilterChange } from "./handleFilters.js";
import { updateSubcollections, updateSurveys } from "./filtersAPI.js";
import { loadDecades } from "./decades.js";
import { loadInitialData } from "./datatable.js";

export function attachDynamicCheckboxEvents() {
  $(".subcollection-checkbox, .survey-checkbox")
    .off("change")
    .on("change", async function () {
      const checkbox = $(this);
      const className = checkbox
        .attr("class")
        .split(" ")
        .find(c => c.endsWith("-checkbox"));

      let filterType = className.replace("-checkbox", "");

      // 🔧 Normalisation pour correspondre aux clés de filterState
      if (filterType === "subcollection") filterType = "sub_collection";
      if (filterType === "survey") filterType = "survey";

      const filterValue = checkbox.val();

      await handleFilterChange(filterType, filterValue);

      // 🔁 Dépendances pour les subcollections
      if (filterType === "sub_collection") {
        const selectedSubcollections = Array.from(filterState.sub_collection);
        if (selectedSubcollections.length === 0) {
          const allSubcollections = $(".subcollection-checkbox").map(function () {
            return this.value;
          }).get();
          updateSurveys(allSubcollections);
        } else {
          updateSurveys(selectedSubcollections);
        }
      }
    });
}

export function attachStaticEventListeners() {
  // Collections & search locations
  $(".collection-checkbox, .search-location-checkbox")
    .off("change")
    .on("change", function () {
      const checkbox = $(this);
      const className = checkbox
        .attr("class")
        .split(" ")
        .find(c => c.endsWith("-checkbox"));

      let filterType = className.replace("-checkbox", "");

      // 🔧 Normalisation pour correspondre aux clés de filterState
      if (filterType === "search-location") filterType = "search_location";
      if (filterType === "collection") filterType = "collection";

      const filterValue = checkbox.val();

      handleFilterChange(filterType, filterValue);

      // 🔁 Dépendances pour les collections
      if (filterType === "collection") {
        const selectedCollections = Array.from(filterState.collection);
        updateSubcollections(selectedCollections);
      }
      clearCache();
      resetCurrentLimit();
      loadInitialData();
    });

  // Reset filtres
  $("#reset-filters").off("click").on("click", async function () {
    Object.keys(filterState).forEach(key => filterState[key].clear());
    selectedIds.clear();

    // Reset UI
    $(".form-check-input").prop("checked", false);
    updateDecadeCheckboxes();
    updateFiltersDisplay();
    updateFilterCounts();

    clearCache();
    resetCurrentLimit();
    await loadDecades();
    loadInitialData();
    updateURLWithFilters();
  });

  // Load more
  $("#load-more").off("click").on("click", function () {
    incrementLimit();
    $("#survey-table").DataTable().ajax.reload(function() {
      updateCheckboxes();
    }, false);  // false = n'efface pas les lignes existantes
  });

  // Export all
  $("#export-all").off("click").on("click", function () {
    const params = {
      q: $("input[name='q']").val(),
      survey: Array.from(filterState.survey),
      collections: Array.from(filterState.collection),
      sub_collections: Array.from(filterState.sub_collection),
      search_location: Array.from(filterState.search_location),
      years: Array.from(filterState.years),
    };
    const searchParams = new URLSearchParams(params).toString();
    window.location.href = `/export/questions/?${searchParams}`;
  });

  // Export selected
  $("#export-selected").off("click").on("click", function () {
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
    const query = Array.from(selectedIds).map(id => `ids=${id}`).join("&");
    window.location.href = `/export/questions/?${query}`;
  });

  // Sélection DataTable
  $("#survey-table tbody").on("change", "input[type=\"checkbox\"]", function () {
    this.checked ? selectedIds.add(this.value) : selectedIds.delete(this.value);

    const all = $("#survey-table tbody input[type=\"checkbox\"]");
    const checked = $("#survey-table tbody input[type=\"checkbox\"]:checked");

    $("#select-all")
      .prop("checked", all.length === checked.length)
      .prop("indeterminate", checked.length > 0 && all.length !== checked.length);
  });

  $(window).resize(updateTableContainerHeight);
}

export function updateURLWithFilters() {
  const url = new URL(window.location.href);
  const params = new URLSearchParams();

  // Mot-clé de recherche
  const searchQuery = $("input[name=\"q\"]").val();
  if (searchQuery) {
    params.set("q", searchQuery);
  }

  // Search locations
  filterState.search_location.forEach(value => {
    params.append("search_location", value);
  });

  // Collections
  filterState.collection.forEach(value => {
    params.append("collection", value);
  });

  // Sous-collections
  filterState.sub_collection.forEach(value => {
    params.append("sub_collection", value);
  });

  // Surveys
  filterState.survey.forEach(value => {
    params.append("survey", value);
  });

  // Années
  filterState.years.forEach(year => {
    params.append("years", year);
  });

  url.search = params.toString();
  window.history.pushState({}, "", url);
}
