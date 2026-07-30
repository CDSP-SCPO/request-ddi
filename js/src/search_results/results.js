import {
  facetState,
  filterState,
  resetFacetCache,
  resultState,
} from "./state.js";
import {buildSearchPayload, buildSearchUrlParams, getSearchQuery} from "./searchParams.js";
import {renderFacetAvailability} from "./filterView.js";
import {refreshYearsView} from "./yearsView.js";
import {updateResultCheckboxes} from "./utils.js";

let table = null;

function getTranslations() {
  return JSON.parse(sessionStorage.getItem("request_ddi_search_translations"));
}

export function initializeResultsTable() {
  const translations = getTranslations();

  table = $("#survey-table").DataTable({
    processing: false,
    serverSide: false,
    paging: false,
    dom: "rt",
    info: false,
    ordering: false,
    drawCallback: updateResultCheckboxes,
    ajax: {
      url: `/api/${window.requestDdiData.apiVersion}/search-results/`,
      traditional: true,
      type: "POST",
      data: () => buildSearchPayload({
        start: resultState.cachedResults.length,
        limit: resultState.currentLimit - resultState.cachedResults.length,
      }),
      headers: {"X-CSRFToken": $("input[name=csrfmiddlewaretoken]").val()},
      dataSrc: json => processSearchResponse(json, translations),
      error: (_jqXHR, textStatus, errorThrown) => {
        console.error("DataTables AJAX Error:", textStatus, errorThrown);
      },
    },
    columns: [{data: "id", render: (_data, _type, row) => renderResultCard(row, translations)}],
    language: {
      url: "//cdn.datatables.net/plug-ins/1.10.20/i18n/French.json",
      emptyTable: "Aucun élément à afficher.",
    },
  });

  return table;
}

export function reloadResults({keepExistingRows = false} = {}) {
  if (!table) return;

  table.ajax.reload(() => updateResultCheckboxes(), !keepExistingRows);
}

export function resetAndReloadResults() {
  resultState.currentLimit = 10;
  resultState.cachedResults = [];
  reloadResults();
}

export function loadMoreResults() {
  resultState.currentLimit += 10;
  reloadResults({keepExistingRows: true});
}


// Handles received hits and aggregations, updates cache and returns rows to the datatable
function processSearchResponse(json, translations) {
  const currentQuery = getSearchQuery();
  if (currentQuery !== facetState.lastSearchQuery) {
    resetFacetCache();
    facetState.lastSearchQuery = currentQuery;
  }

  const resolvedAggregations = resolveFacetAggregations(json.aggregations || {});
  renderFacetAvailability(resolvedAggregations, {hasSearchQuery: currentQuery.length > 0});

  if (resultState.cachedResults.length === 0) {
    resultState.cachedResults = [...json.data];
  } else {
    resultState.cachedResults.push(...json.data);
  }

  resultState.totalRecords = json.recordsTotal;
  $("#results-count").text(`${resultState.totalRecords}${translations.resultats}`);
  $("#load-more").toggle(resultState.cachedResults.length < resultState.totalRecords);

  refreshYearsView().catch(error => {
    console.error("Erreur lors du rafraîchissement des années :", error);
  });

  return resultState.cachedResults;
}

// Selects the aggregation data to use for each filter category, between the latest ES aggs and their cached version (depending on whether we want to keep the aggregations from sides unchecked filters or not)
function resolveFacetAggregations(currentAggregations) {
  const resolved = {};

  Object.keys(filterState).forEach(type => {
    if (filterState[type].size === 0) {
      facetState.cache[type] = currentAggregations;
      resolved[type] = currentAggregations;
    } else {
      resolved[type] = facetState.cache[type] || currentAggregations;
    }
  });

  return resolved;
}

// Transforms a search result into a complete HTML card
function renderResultCard(row, translations) {
  const searchParams = buildSearchUrlParams();
  const url = `/question/${row.id}/?${searchParams.toString()}`;
  const doiUrl = `https://doi.org/${row.survey_doi}`;
  const hasHighlightedModalities = row.is_category_search
    && row.categories
    && row.categories.includes("<mark style=");
  const caretIcon = hasHighlightedModalities
    ? "<span class=\"background-red-caret\"><img src=\"/static/svg/buttons/caret_down.svg\" alt=\"Caret Down\" class=\"icon-caret\"></span>"
    : "<img src=\"/static/svg/buttons/caret_down.svg\" alt=\"Caret Down\" class=\"icon-caret\">";

  return `
    <div class="custom-card-dt">
      <div class="custom-content-card">
        <div class="custom-card-first-part">
          <div class="title-checkbox">
            <input type="checkbox" class="form-check-input checkbox-custom" value="${row.id}">
            <div class="custom-title-2 custom-title-2-bold">
              <a class="custom-name-card color-black-1" type="button" href="${url}">${row.question_text || row.internal_label}</a>
            </div>
          </div>
          <div class="custom-metadatas">
            <div class="flex-grow-1 d-flex flex-column inner-container-metadatas custom-body">
              <div class="card-subtitle">${translations.enquete}<span class="ft-600"> ${row.survey_name} </span></div>
              <div class="card-subtitle">${translations.nomVariable}<span class="ft-600">${row.variable_name}</span></div>
              <div class="card-subtitle">${translations.libelleVariable}<span class="ft-600">${row.internal_label}</span></div>
            </div>
          </div>
        </div>
        <div class="custom-card-second-part">
          <div class="container-buttons-card">
            <span type="button" onclick="window.requestDdiJsHelpers.toggleCategories(this, 'categories-${row.id}')" class="button-card button-modalities-card">
              <img src="/static/svg/icons/modalites.svg" alt="Modalités" class="icon-modalites">
              <span>${translations.modalites}</span>
              ${caretIcon}
            </span>
            <span type="button" onclick="window.open('${doiUrl}','_blank')" class="button-card button-access-data button-access-data-card-hover">
              <img src="/static/svg/icons/doi.svg" alt="Données" class="icon-access-data">
              <span>${translations.accederAuxDonnees}</span>
            </span>
          </div>
          <div id="categories-${row.id}" class="categories-list mt-3" style="display: none;">
            ${row.categories}
          </div>
        </div>
      </div>
    </div>`;
}
