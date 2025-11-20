// ---------------------------
// 5. Initialisation DataTable
// ---------------------------
function initializeDataTable() {
    table = $('#survey-table').DataTable({
        "processing": true,
        "serverSide": true,
        "paging": false,
        "dom": 'rt',
        "info": false,
        "ordering": false,
        "drawCallback": function(settings) {
            updateCheckboxes();
        },
        "ajax": {
            url: `/api/${window.requestdata.api_version}/search-results/`,
            "type": "POST",
            "async": true,
            "data": function (d) {
                d.start = d.start || 0;
                d.limit = currentLimit;
                d.q = $("input[name='q']").val();
                d.survey = getFilterValues('survey-checkbox');
                d.collections = getFilterValues('collection-checkbox');
                d.sub_collections = getFilterValues('subcollection-checkbox');
                d.search_location = getSearchLocation();
                d.years = getYearsFilter();
            },
            "headers": {'X-CSRFToken': $("input[name=csrfmiddlewaretoken]").val()},
            "dataSrc": function (json) {
                totalRecords = json.recordsTotal;
                currentRecords = json.data.length;
                $('#results-count').text(totalRecords + window.translations.resultats);
                if (currentRecords < totalRecords) {
                    $('#load-more').show();
                } else {
                    $('#load-more').hide();
                }
                return json.data;
            },
            "error": function (jqXHR, textStatus, errorThrown) {
                console.error('DataTables AJAX Error:', textStatus, errorThrown);
            }
        },
        "columns": [
            {
                "data": "id",
                "render": function (data, type, row) {
                    const searchParams = new URLSearchParams();
                    const searchInput = document.querySelector('input[name="q"]');
                    if (searchInput && searchInput.value) {
                        searchParams.set('q', searchInput.value);
                    }
                    getFilterValues('survey-checkbox').forEach(val => searchParams.append('survey', val));
                    getFilterValues('collection-checkbox').forEach(val => searchParams.append('collections', val));
                    getFilterValues('subcollection-checkbox').forEach(val => searchParams.append('sub_collections', val));
                    getYearsFilter().forEach(val => searchParams.append('years', val));
                    getSearchLocation().forEach(val => searchParams.append('search_location', val));
                    const url = '/question/' + row.id + '/?' + searchParams.toString();
                    var categoriesDisplay = row.categories;
                    var survey_doi = row.survey_doi;
                    var doiUrl = 'https://doi.org/' + survey_doi;
                    var hasHighlightedModalities = row.is_category_search && row.categories && row.categories.includes('<mark style=');
                    var caretIcon = hasHighlightedModalities ?
                        '<span class="background-red-caret"><img src="/static/svg/buttons/caret_down.svg" alt="Caret Down" class="icon-caret"></span>' :
                        '<img src="/static/svg/buttons/caret_down.svg" alt="Caret Down" class="icon-caret">'
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
                                                        <div class="card-subtitle">${window.translations.enquete}<span class="ft-600"> ${row.survey_name} </span> </div>
                                                        <div class="card-subtitle">${window.translations.nomVariable}<span class="ft-600">${row.variable_name}</span></div>
                                                        <div class="card-subtitle">${window.translations.libelleVariable}<span class="ft-600">${row.internal_label}</span></div>
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="custom-card-second-part">
                                                <div class="container-buttons-card">
                                                    <span type="button" id="toggle-categories" onclick="toggleCategories('categories-${row.id}')" class="button-card button-modalities-card">
                                                        <img src="/static/svg/icons/modalites.svg" alt="Modalités" class="icon-modalites">
                                                        <span>${window.translations.modalites}</span>
                                                        ${caretIcon}
                                                    </span>
                                                    <span type="button" onclick="window.location.href='${doiUrl}'" class="button-card button-access-data button-access-data-card-hover">
                                                        <img src="/static/svg/icons/doi.svg" alt="Données" class="icon-access-data">
                                                        <span>${window.translations.accederAuxDonnees}</span>
                                                    </span>
                                                </div>
                                                <div id="categories-` + row.id + `" class="categories-list mt-3" style="display: none;">
                                                    ` + categoriesDisplay + `
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
}
