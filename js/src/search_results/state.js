export const FILTER_TYPES = [
  "search_location",
  "collection",
  "sub_collection",
  "survey",
  "years",
];

export const filterState = Object.fromEntries(
  FILTER_TYPES.map(type => [type, new Set()])
);

export const resultState = {
  currentLimit: 10,
  cachedResults: [],
  totalRecords: 0,
};

export const facetState = {
  lastSearchQuery: null,
  cache: Object.fromEntries(FILTER_TYPES.map(type => [type, null])),
  baseYearCounts: new Map(),
};

export const selectedIds = new Set();

// Completely replaces filter values in central state
export function replaceFilterValues(type, values) {
  filterState[type].clear();
  values.forEach(value => filterState[type].add(value));
}

// Add a missing value or remove a value already there
export function toggleFilterValue(type, value) {
  const values = filterState[type];
  if (values.has(value)) values.delete(value);
  else values.add(value);
}

// Remove a specific value in a filter
export function removeFilterValue(type, value) {
  filterState[type].delete(value);
}

// Empty some filters or all filters if no type is given
export function clearFilters(types = FILTER_TYPES) {
  types.forEach(type => filterState[type].clear());
}

// Resets limit, results cache, and export selection
export function resetResults() {
  resultState.currentLimit = 10;
  resultState.cachedResults = [];
  selectedIds.clear();
}

// Empties aggs in cache, et years counts
export function resetFacetCache() {
  FILTER_TYPES.forEach(type => {
    facetState.cache[type] = null;
  });
  facetState.baseYearCounts = new Map();
}
