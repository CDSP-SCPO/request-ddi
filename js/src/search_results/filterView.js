import {filterState, facetState} from "./state.js";
import {updateTableContainerHeight} from "./utils.js";

const FILTER_SELECTOR = {
  search_location: ".search-location-checkbox",
  collection: ".collection-checkbox",
  sub_collection: ".subcollection-checkbox",
  survey: ".survey-checkbox",
  years: ".year-checkbox",
};

let onRemoveFilter = null;

// Loads the callback, useful when a filter is removed using the cross chip
export function configureFilterView({removeFilter}) {
  onRemoveFilter = removeFilter;
}

// Displays the dynamic list of subcollections, and surveys

export function renderSubcollections(subcollections) {
  renderOptions({
    container: "#subcollections-filter",
    options: subcollections,
    type: "sub_collection",
    className: "subcollection-checkbox",
    idPrefix: "subcollection",
  });
}

export function renderSurveys(surveys) {
  renderOptions({
    container: "#survey-filter",
    options: surveys,
    type: "survey",
    className: "survey-checkbox",
    idPrefix: "survey",
  });
}

// Generates checkboxes of a group of dynamic options, then sync with filterState
function renderOptions({container, options, type, className, idPrefix}) {
  const html = options.map(option => `
    <div class="form-check-custom">
      <input
        class="form-check-input ${className} checkbox-custom filter-checkbox"
        data-filter-type="${type}"
        type="checkbox"
        value="${option.id}"
        id="${idPrefix}-${option.id}"
      >
      <label class="form-check-label" for="${idPrefix}-${option.id}">
        ${option.name}
      </label>
    </div>
  `).join("");

  $(container).html(html);
  syncFilterCheckboxes(type);
}

// Sync all checkboxes families with filterState
export function syncAllFilterCheckboxes() {
  Object.keys(FILTER_SELECTOR).forEach(syncFilterCheckboxes);
}

// Checks or unchecks checkboxes of a certain filter type, using filterState
export function syncFilterCheckboxes(type) {
  const selector = FILTER_SELECTOR[type];
  if (!selector) return;

  $(selector).each(function () {
    const value = type === "years" ? Number(this.value) : String(this.value);
    this.checked = filterState[type].has(value);
  });
}

// Rebuilds the selected-filter chips (above the datatable) displayed for each active filter value.
export function renderSelectedFilters() {
  const container = $("#selected-filters-container");
  container.empty();

  Object.entries(filterState).forEach(([type, values]) => {
    values.forEach(value => {
      const card = $(
        `<div class="selected-filter-card">
          <span>${getFilterLabel(type, value)}</span>
          <img type="button" class="remove-filter" src="/static/svg/icons/cross.svg" alt="Retirer">
        </div>`
      );

      card.find(".remove-filter").on("click", () => onRemoveFilter?.(type, value));
      container.append(card);
    });
  });

  container.toggle(container.children().length > 0);
  updateTableContainerHeight();
}

// Updates the number of active filters in the chip next to the global filter name
export function renderFilterCounts() {
  Object.entries(filterState).forEach(([type, values]) => {
    const count = values.size;
    const badge = $(`.accordion-item[data-filter-type="${type}"] .filter-count`);
    badge.text(count).toggle(count > 0);
  });
}

// Finds the name of a filter from a filter value using its checkbox
function getFilterLabel(type, value) {
  const selector = FILTER_SELECTOR[type];
  const checkbox = selector
    ? $(`${selector}[value="${CSS.escape(String(value))}"]`)
    : $();

  if (!checkbox.length) return String(value);

  const label = checkbox.closest(".form-check-custom").find("label").first().clone();
  label.find(".available-count").remove();
  return label.text().trim();
}

// Updates the visibility, result counts, and display order of filter options using the aggregations returned by the latest search
export function renderFacetAvailability(aggregations, {hasSearchQuery}) {
  if (!aggregations) {
    $(Object.values(FILTER_SELECTOR).join(","))
      .closest(".form-check-custom")
      .show();
    $(".available-count").remove();
    return;
  }

  const searchLocations = aggregationMap(
    aggregations,
    "search_location",
  );
  const collections = aggregationMap(
    aggregations,
    "collections",
  );
  const subcollections = aggregationMap(
    aggregations,
    "subcollections",
  );
  const surveys = aggregationMap(
    aggregations,
    "surveys",
  );
  const years = aggregationMap(
    aggregations,
    "years",
    "year",
  );

  facetState.baseYearCounts = years;

  if (hasSearchQuery) {
    updateOptionAvailability(
      ".search-location-checkbox",
      searchLocations,
      true,
    );
  } else {
    $(".search-location-checkbox")
      .closest(".form-check-custom")
      .show()
      .find(".available-count")
      .remove();
  }

  updateOptionAvailability(".collection-checkbox", collections, true);
  updateOptionAvailability(".subcollection-checkbox", subcollections, true);
  updateOptionAvailability(".survey-checkbox", surveys, true);
  updateOptionAvailability(".year-checkbox", years, false);
}

// Converts an aggregation from backend into a Map id -> number of results
function aggregationMap(aggregations, key, idKey = "id") {
  const source = aggregations?.[key] || [];
  return new Map(source.map(item => [String(item[idKey]), item.count]));
}

// Displays available options, adds result counts et order them by frequency
function updateOptionAvailability(selector, available, sortByCount) {
  const items = [];

  $(selector).each(function () {
    const wrapper = $(this).closest(".form-check-custom");
    const label = wrapper.find("label");
    const count = available.get(String(this.value));

    wrapper.toggle(count !== undefined);
    wrapper.find(".available-count").remove();
    if (count !== undefined) {
      label.append(`<span class="available-count">${count}</span>`);
    }

    items.push({wrapper, count: count ?? -1});
  });

  if (sortByCount) {
    items.sort((a, b) => b.count - a.count)
      .forEach(({wrapper}) => wrapper.parent().append(wrapper));
  }
}
