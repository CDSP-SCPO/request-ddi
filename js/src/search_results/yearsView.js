import {fetchDecades, fetchYears} from "./filterApi.js";
import {facetState, filterState} from "./state.js";

const yearsByDecade = new Map();
let currentView = {mode: "decades", decade: null};
let callbacks = {};

// Saves callbacks used by the year view to delegate changes to the controller
export function configureYearsView(config) {
  callbacks = config;
}

// Replaces years navigation to the general decades view
export function showDecadesView() {
  currentView = {mode: "decades", decade: null};
}

// Recharges the actual opened view, either decades or years
export async function refreshYearsView() {
  if (currentView.mode === "years") {
    await renderYears(currentView.decade);
  } else {
    await renderDecades();
  }
}

// Calculates the state checked or intermediary of each decade from the selected years
export function syncDecadeCheckboxes() {
  $(".decade-checkbox").each(function () {
    const years = yearsByDecade.get(String(this.value)) || [];
    const allSelected = years.length > 0 && years.every(year => filterState.years.has(year));
    const someSelected = years.some(year => filterState.years.has(year));

    this.checked = allSelected;
    this.indeterminate = !allSelected && someSelected;
  });
}

// Charges then displays available decades et their number of results
async function renderDecades() {
  const decades = await fetchDecades(currentParentFilters());
  const container = $("#years-filter").empty();
  yearsByDecade.clear();

  const sortedDecades = Object.keys(decades)
    .sort((a, b) => Number(b) - Number(a));

  sortedDecades.forEach(decade => {
    const years = decades[decade]
      .map(Number)
      .filter(Number.isInteger)
      .filter(year => facetState.baseYearCounts.size === 0 || facetState.baseYearCounts.has(String(year)));

    if (!years.length && facetState.baseYearCounts.size > 0) return;

    yearsByDecade.set(String(decade), years);
    const count = getDecadeCount(years);

    container.append(`
      <div class="form-check-custom decade-item">
        <div class="checkbox-and-label">
          <input
            type="checkbox"
            class="form-check-input decade-checkbox checkbox-custom"
            value="${decade}"
            id="decade-${decade}"
          >
          <label class="form-check-label" for="decade-${decade}">
            Années ${decade}
            ${count === null ? "" : `<span class="available-count">${count}</span>`}
          </label>
        </div>
        <img
          src="/static/svg/icons/chevron_right.svg"
          class="chevron-icon decade-chevron"
          data-decade="${decade}"
          alt="chevron"
        >
      </div>
    `);
  });

  removeInvalidSelectedYears();
  syncDecadeCheckboxes();
}

// Charges then displays available years for a given decade
async function renderYears(decade) {
  currentView = {mode: "years", decade: String(decade)};
  const years = await fetchYears({decade, ...currentParentFilters()});
  const container = $("#years-filter").empty();

  container.append("<img src=\"/static/svg/icons/chevron_left.svg\" class=\"back-button\" alt=\"Retour\">");

  years.map(Number)
    .filter(Number.isInteger)
    .filter(year => facetState.baseYearCounts.size === 0 || facetState.baseYearCounts.has(String(year)))
    .sort((a, b) => b - a)
    .forEach(year => {
      const count = facetState.baseYearCounts.get(String(year)) ?? 0;
      container.append(`
        <div class="form-check-custom year-item">
          <input
            type="checkbox"
            class="form-check-input year-checkbox checkbox-custom filter-checkbox"
            data-filter-type="years"
            value="${year}"
            id="year-${year}"
            ${filterState.years.has(year) ? "checked" : ""}
          >
          <label class="form-check-label" for="year-${year}">
            ${year}<span class="available-count">${count}</span>
          </label>
        </div>
      `);
    });
}

// Links decades events to carets and return button
export function attachYearsEvents() {
  $(document)
    .off("change.requestDdiDecade", ".decade-checkbox")
    .on("change.requestDdiDecade", ".decade-checkbox", function () {
      callbacks.toggleDecade?.(yearsByDecade.get(String(this.value)) || [], this.checked);
    })
    .off("click.requestDdiDecade", ".decade-chevron")
    .on("click.requestDdiDecade", ".decade-chevron", function () {
      renderYears(this.dataset.decade);
    })
    .off("click.requestDdiDecade", ".back-button")
    .on("click.requestDdiDecade", ".back-button", function () {
      showDecadesView();
      renderDecades();
    });
}

// Returns collections, subcollections and surveys used to filter years
function currentParentFilters() {
  return {
    collectionIds: [...filterState.collection],
    subcollectionIds: [...filterState.sub_collection],
    surveyIds: [...filterState.survey],
  };
}

// Adds the number of results of years belonging to a decade
function getDecadeCount(years) {
  if (facetState.baseYearCounts.size === 0) return null;
  return years.reduce(
    (total, year) => total + (facetState.baseYearCounts.get(String(year)) ?? 0),
    0
  );
}

// Removes selected years no longer available in current aggs
function removeInvalidSelectedYears() {
  if (facetState.baseYearCounts.size === 0) return;
  [...filterState.years].forEach(year => {
    if (!facetState.baseYearCounts.has(String(year))) filterState.years.delete(year);
  });
}
