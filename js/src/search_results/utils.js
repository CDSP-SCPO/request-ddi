export let selectedIds = new Set();
export let table;


export const state = {
  currentLimit: 10
};


// Setters
export function setTable(newTable) {
  table = newTable;
}

export function incrementLimit() {
  state.currentLimit += 10;
}

export function getCurrentLimit() {
  return state.currentLimit;
}

// Getters de filtres
export function getFilterValues(className) {
  return $(`.${className}:checked`).map(function () {
    return this.value;
  }).get();
}

export function getSearchLocation() {
  return getFilterValues("search-location-checkbox");
}

// Fonctions UI
export function toggleCategories(button, categoryId) {
  const categoriesDiv = document.getElementById(categoryId);
  if (!categoriesDiv) return;

  const caretIcon = button.querySelector(".icon-caret");
  if (!caretIcon) return;

  const isHidden = categoriesDiv.style.display === "none" || !categoriesDiv.style.display;

  categoriesDiv.style.display = isHidden ? "block" : "none";
  caretIcon.classList.toggle("rotated", isHidden);
}

export function updateTableContainerHeight() {
  const selectedFiltersContainer = $("#selected-filters-container");
  if (selectedFiltersContainer.is(":visible") && selectedFiltersContainer.children().length > 0) {
    const height = selectedFiltersContainer.outerHeight(true);
    document.documentElement.style.setProperty("--selected-filters-container-height", height + "px");
  } else {
    document.documentElement.style.setProperty("--selected-filters-container-height", "0px");
  }
}

export function updateCheckboxes() {
  $("#survey-table tbody input[type=\"checkbox\"]").each(function() {
    this.checked = selectedIds.has(this.value);
  });
}

export function updateFilters() {
  $("#survey-table").DataTable().ajax.reload();
}

// Pour les onclick dans le HTML généré par DataTables
window.toggleCategories = toggleCategories;