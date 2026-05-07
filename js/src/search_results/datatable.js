import {
  updateCheckboxes,
  getFilterValues,
  getSearchLocation,
  getCurrentLimit,
  setTable,
  getCachedResults,
  setCachedResults,
  appendCachedResults,
} from "./utils.js";
import { getYearsFilter } from "./filters.js";


let totalRecords = 0;

export function initializeDataTable() {
  var translations = JSON.parse(sessionStorage.getItem("request_ddi_search_translations"));
  const table = $("#survey-table").DataTable({
    "processing": false,
    "serverSide": false,
    "paging": false,
    "dom": "rt",
    "info": false,
    "ordering": false,
    "drawCallback": function() {
      updateCheckboxes();
    },
    "ajax": {
      url: `/api/${window.requestDdiData.apiVersion}/search-results/`,
      traditional: true,
      "type": "POST",
      "async": true,
      "data": function () {
        const currentLimit = getCurrentLimit();
        const cachedLength = getCachedResults().length;
        return {
          start: cachedLength,
          limit: currentLimit - cachedLength,
          q: $("input[name='q']").val(),
          survey: getFilterValues("survey-checkbox"),
          collections: getFilterValues("collection-checkbox"),
          sub_collections: getFilterValues("subcollection-checkbox"),
          search_location: getSearchLocation(),
          years: getYearsFilter()
        };
      },
      "headers": {"X-CSRFToken": $("input[name=csrfmiddlewaretoken]").val()},
      "dataSrc": function (json) {
  
        totalRecords = json.recordsTotal;
        
        appendCachedResults(json.data);
        const allCachedResults = getCachedResults();
        
        $("#results-count").text(totalRecords + translations.resultats);
        
        if (allCachedResults.length < totalRecords) {
          $("#load-more").show();
        } else {
          $("#load-more").hide();
        }
        
        return allCachedResults;
      },
      "error": function (jqXHR, textStatus, errorThrown) {
        console.error("DataTables AJAX Error:", textStatus, errorThrown);
      }
    },
    "columns": [
      {
        "data": "id",
        "render": function (data, type, row) {
          const searchParams = new URLSearchParams();
          const searchInput = document.querySelector("input[name=\"q\"]");
          if (searchInput && searchInput.value) {
            searchParams.set("q", searchInput.value);
          }
          getFilterValues("survey-checkbox").forEach(val => searchParams.append("survey", val));
          getFilterValues("collection-checkbox").forEach(val => searchParams.append("collections", val));
          getFilterValues("subcollection-checkbox").forEach(val => searchParams.append("sub_collections", val));
          getYearsFilter().forEach(val => searchParams.append("years", val));
          getSearchLocation().forEach(val => searchParams.append("search_location", val));
          const url = "/question/" + row.id + "/?" + searchParams.toString();
          var categoriesDisplay = row.categories;
          var survey_doi = row.survey_doi;
          var doiUrl = "https://doi.org/" + survey_doi;
          var hasHighlightedModalities = row.is_category_search && row.categories && row.categories.includes("<mark style=");
          var caretIcon = hasHighlightedModalities ?
            "<span class=\"background-red-caret\"><img src=\"/static/svg/buttons/caret_down.svg\" alt=\"Caret Down\" class=\"icon-caret\"></span>" :
            "<img src=\"/static/svg/buttons/caret_down.svg\" alt=\"Caret Down\" class=\"icon-caret\">"
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
                                    <div class="card-subtitle">${translations.enquete}<span class="ft-600"> ${row.survey_name} </span> </div>
                                    <div class="card-subtitle">${translations.nomVariable}<span class="ft-600">${row.variable_name}</span></div>
                                    <div class="card-subtitle">${translations.libelleVariable}<span class="ft-600">${row.internal_label}</span></div>
                                </div>
                            </div>
                        </div>
                        <div class="custom-card-second-part">
                            <div class="container-buttons-card">
                                <span type="button" id="toggle-categories" onclick="window.requestDdiJsHelpers.toggleCategories(this, 'categories-${row.id}')" class="button-card button-modalities-card">
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
                                ${categoriesDisplay}
                            </div>
                        </div>
                    </div>
                </div>`;
        }
      },
    ],
    "language": {
      "url": "//cdn.datatables.net/plug-ins/1.10.20/i18n/French.json",
      "emptyTable": "Aucun élément à afficher.",
    },
  });

  // Sauvegarder la référence de table
  setTable(table);
}

export function loadInitialData() {
  const table = $("#survey-table").DataTable();
  $.ajax({
    url: `/api/${window.requestDdiData.apiVersion}/search-results/`,
    traditional: true,
    type: "POST",
    data: {
      start: 0,
      limit: getCurrentLimit(),
      q: $("input[name='q']").val(),
      survey: getFilterValues("survey-checkbox"),
      collections: getFilterValues("collection-checkbox"),
      sub_collections: getFilterValues("subcollection-checkbox"),
      search_location: getSearchLocation(),
      years: getYearsFilter()
    },
    headers: {"X-CSRFToken": $("input[name=csrfmiddlewaretoken]").val()},
    success: function(json) {
      setCachedResults(json.data);
      table.clear();
      table.rows.add(json.data).draw();
      
      const translations = JSON.parse(sessionStorage.getItem("request_ddi_search_translations"));
      $("#results-count").text(json.recordsTotal + translations.resultats);
      
      if (json.data.length < json.recordsTotal) {
        $("#load-more").show();
      }
    }
  });
}