import { filterState, updateFiltersDisplay, updateFilterCounts, updateDecadeCheckboxes } from "./filters.js";
import { updateSubcollections, updateSurveys } from "./filtersAPI.js";
import { loadDecades } from "./decades.js";
import { updateURLWithFilters } from "./events.js";

export async function applyFiltersFromURL() {
  const urlParams = new URLSearchParams(window.location.search);

  const q = urlParams.get("q");
  if (q) $("input[name=\"q\"]").val(q);

  const collections = urlParams.getAll("collection");
  filterState.collection.clear();
  collections.forEach(val => filterState.collection.add(val));

  $(".collection-checkbox").each(function() {
    $(this).prop("checked", filterState.collection.has(this.value));
  });

  const subCollections = urlParams.getAll("sub_collection");
  filterState.sub_collection.clear();
  subCollections.forEach(val => filterState.sub_collection.add(val));

  const collectionIds = filterState.collection.size > 0
    ? Array.from(filterState.collection)
    : $(".collection-checkbox").map(function() { return this.value; }).get();

  const loadedSubcollections = await updateSubcollections(collectionIds);

  $(".subcollection-checkbox").each(function() {
    $(this).prop("checked", filterState.sub_collection.has(this.value));
  });

  const surveys = urlParams.getAll("survey");
  filterState.survey.clear();
  surveys.forEach(val => filterState.survey.add(val));

  const subIdsForSurvey = loadedSubcollections.length > 0
    ? loadedSubcollections
    : $(".subcollection-checkbox").map(function() { return this.value; }).get();

  await updateSurveys(subIdsForSurvey);
  surveys.forEach(val => filterState.survey.add(val));

  $(".survey-checkbox").each(function() {
    $(this).prop("checked", filterState.survey.has(this.value));
  });

  const searchLocations = urlParams.getAll("search_location");
  filterState.search_location.clear();
  searchLocations.forEach(val => filterState.search_location.add(val));

  $(".search-location-checkbox").each(function() {
    $(this).prop("checked", filterState.search_location.has(this.value));
  });

  const years = urlParams.getAll("years").map(y => parseInt(y));
  filterState.years.clear();
  years.forEach(y => filterState.years.add(y));

  await loadDecades();

  updateDecadeCheckboxes();
  updateFiltersDisplay();
  updateFilterCounts();
  updateURLWithFilters();
}