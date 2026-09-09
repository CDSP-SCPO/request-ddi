import { FILTER_TYPES, filterState } from "./state.js";

export function getSearchQuery() {
  return $("input[name='q']").val()?.trim() || "";
}

// Builds the serach POST payload exclusively from q and filter state
export function buildSearchPayload({start = 0, limit = 10} = {}) {
  return {
    start,
    limit,
    q: getSearchQuery(),
    survey: [...filterState.survey],
    collection: [...filterState.collection],
    sub_collection: [...filterState.sub_collection],
    search_location: [...filterState.search_location],
    years: [...filterState.years],
  };
}

// Serialize serach and filter State into URL parameters
export function buildSearchUrlParams() {
  const params = new URLSearchParams();
  const query = getSearchQuery();

  if (query) params.set("q", query);

  FILTER_TYPES.forEach(type => {
    filterState[type].forEach(value => params.append(type, String(value)));
  });

  return params;
}

// Replace or add the URL matching current State without reloading the page
export function syncBrowserUrl({replace = false} = {}) {
  const url = new URL(window.location.href);
  url.search = buildSearchUrlParams().toString();

  const method = replace ? "replaceState" : "pushState";
  window.history[method]({}, "", url);
}

export function readFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const query = params.get("q") || "";

  const values = {
    search_location: params.getAll("search_location"),
    collection: params.getAll("collection"),
    sub_collection: params.getAll("sub_collection"),
    survey: params.getAll("survey"),
    years: params.getAll("years").map(Number).filter(Number.isInteger),
  };

  return {query, values};
}
