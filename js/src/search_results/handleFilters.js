import { selectedIds } from "./utils.js";
import { filterState, updateFiltersDisplay, updateFilterCounts, clearChildFilters } from "./filters.js";
import { updateSubcollections, updateSurveys } from "./filtersAPI.js";
import { loadDecades } from "./decades.js";
import { updateURLWithFilters } from "./events.js";
import { clearCache, resetCurrentLimit } from "./utils.js";

export async function handleFilterChange(filterType, filterValue) {
  selectedIds.clear();

  if (!filterState[filterType]) return;

  // Toggle état central
  if (filterState[filterType].has(filterValue)) {
    filterState[filterType].delete(filterValue);
  } else {
    filterState[filterType].add(filterValue);
  }

  clearChildFilters(filterType);

  if (filterType === "collection") {
    const collectionIds = Array.from(filterState.collection);
    const subIds = await updateSubcollections(collectionIds);

    const subIdsForSurveys =
      filterState.sub_collection.size > 0
        ? Array.from(filterState.sub_collection)
        : subIds;

    await updateSurveys(subIdsForSurveys);
  }

  if (filterType === "sub_collection") {
    const subIds = Array.from(filterState.sub_collection);
    await updateSurveys(subIds);
  }

  // 🔁 Recharger les années si les filtres parents changent
  if (["collection", "sub_collection", "survey"].includes(filterType)) {
    await loadDecades();
  }

  updateFiltersDisplay();
  updateFilterCounts();
  updateURLWithFilters();
  clearCache();
  resetCurrentLimit();

  // Reload table
  $("#survey-table").DataTable().ajax.reload();
}