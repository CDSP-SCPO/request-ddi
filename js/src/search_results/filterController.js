import {fetchSubcollections, fetchSurveys} from "./filterApi.js";
import {
  clearFilters,
  filterState,
  removeFilterValue,
  replaceFilterValues,
  resetResults,
  toggleFilterValue,
} from "./state.js";
import {
  configureFilterView,
  renderFilterCounts,
  renderSelectedFilters,
  renderSubcollections,
  renderSurveys,
  syncAllFilterCheckboxes,
} from "./filterView.js";
import {readFiltersFromUrl, syncBrowserUrl} from "./searchParams.js";
import {resetAndReloadResults} from "./results.js";
import {
  configureYearsView,
  showDecadesView,
  syncDecadeCheckboxes,
} from "./yearsView.js";

const CHILD_FILTERS = {
  collection: ["sub_collection", "survey", "years"],
  sub_collection: ["survey", "years"],
  survey: ["years"],
  search_location: [],
  years: [],
};

/**
 * Provides the views with the controller callbacks they need to invoke
 * in response to user interactions, without requiring them to import
 * the controller directly.
 *
 * This prevents circular dependencies between the controller and the views.
 */
export function configureFilterController() {
  configureFilterView({removeFilter: removeFilter});
  configureYearsView({toggleDecade});
}

export async function restoreFiltersFromUrl(reloadResults = false, updateUrl = false,) {
  const {query, values} = readFiltersFromUrl();
  $("input[name='q']").val(query);

  Object.entries(values).forEach(([type, filterValues]) => {
    replaceFilterValues(type, filterValues);
  });

  await refreshDependentOptions("collection", {preserveCurrentSelection: true});
  syncFilterUi();

  if (updateUrl) {
    syncBrowserUrl({replace: true});
  }

  if (reloadResults) {
    resetAndReloadResults();
  }
}


// Adds or removes a filter value, actualizes dependancies then applies the new state.
export async function toggleFilter(type, rawValue) {
  const value = normalizeValue(type, rawValue);
  if (!filterState[type]) return;

  toggleFilterValue(type, value);
  clearFilters(CHILD_FILTERS[type]);

  if (["collection", "sub_collection", "survey"].includes(type)) {
    showDecadesView();
  }

  await refreshDependentOptions(type);
  commitFilterChange();
}


// Removes a filter value, from a cross chip, then applies the new state
export async function removeFilter(type, rawValue) {
  const value = normalizeValue(type, rawValue);
  removeFilterValue(type, value);
  clearFilters(CHILD_FILTERS[type]);

  if (["collection", "sub_collection", "survey"].includes(type)) {
    showDecadesView();
  }

  await refreshDependentOptions(type);
  commitFilterChange();
}

export async function resetAllFilters() {
  clearFilters();
  showDecadesView();
  await refreshDependentOptions("collection");
  commitFilterChange();
}

// Handles the click on a whole decade
export function toggleDecade(years, checked) {
  years.forEach(year => {
    if (checked) filterState.years.add(year);
    else filterState.years.delete(year);
  });
  commitFilterChange();
}

// Reloads all subcollections or surveys that depend on the newly changed filter
async function refreshDependentOptions(changedType, {preserveCurrentSelection = false} = {}) {
  if (changedType === "collection") {
    const collectionIds = selectedOrAllCollectionIds();
    const subcollections = await fetchSubcollections(collectionIds);
    keepOnlyAvailable("sub_collection", subcollections, preserveCurrentSelection);
    renderSubcollections(subcollections);

    const subcollectionIds = filterState.sub_collection.size
      ? [...filterState.sub_collection]
      : subcollections.map(item => String(item.id));
    const surveys = await fetchSurveys(subcollectionIds);
    keepOnlyAvailable("survey", surveys, preserveCurrentSelection);
    renderSurveys(surveys);
    return;
  }

  if (changedType === "sub_collection") {
    const surveys = await fetchSurveys([...filterState.sub_collection]);
    keepOnlyAvailable("survey", surveys, preserveCurrentSelection);
    renderSurveys(surveys);
  }
}

// Returns all selected collections or all the available ones if none is selected
function selectedOrAllCollectionIds() {
  if (filterState.collection.size) return [...filterState.collection];
  return $(".collection-checkbox").map(function () {
    return String(this.value);
  }).get();
}

// Ensures coherence between checked filters and filter state
function keepOnlyAvailable(type, options, preserveCurrentSelection) {
  if (preserveCurrentSelection) return;
  const available = new Set(options.map(item => String(item.id)));
  [...filterState[type]].forEach(value => {
    if (!available.has(String(value))) filterState[type].delete(value);
  });
}

// Finalizes a filter change, synchronizing the visual state, the URL and the results
function commitFilterChange() {
  resetResults();
  syncFilterUi();
  syncBrowserUrl();
  resetAndReloadResults();
}

// Reproduces the filter state in checkboxes, decades, facets and chips
function syncFilterUi() {
  syncAllFilterCheckboxes();
  syncDecadeCheckboxes();
  renderSelectedFilters();
  renderFilterCounts();
}

function normalizeValue(type, value) {
  return type === "years" ? Number(value) : String(value);
}
