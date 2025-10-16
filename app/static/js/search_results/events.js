// ---------------------------
// 6. Gestion des événements
// ---------------------------
function attachDynamicCheckboxEvents() {
    $('.subcollection-checkbox, .survey-checkbox').off('change').on('change', function () {
        var checkbox = $(this);
        var filterType = checkbox.attr('class').split(' ')[1].split('-')[0];
        var filterValue = checkbox.val();
        var filterLabel = $('label[for="' + checkbox.attr('id') + '"]').text();
        handleFilterChange(filterType, filterValue, filterLabel);
        updateFilterCounts();
        resetDependentSurveyFilters();
        if (filterType === 'subcollection') {
            const selectedSubcollections = $('.subcollection-checkbox:checked').map(function () {
                return this.value;
            }).get();
            if (selectedSubcollections.length === 0) {
                const allSubcollections = $('.subcollection-checkbox').map(function () {
                    return this.value;
                }).get();
                updateSurveys(allSubcollections);
            } else {
                updateSurveys(selectedSubcollections);
            }
        }
        $('#survey-table').DataTable().ajax.reload();
        updateURLWithFilters();
    });
    $('.survey-checkbox').off('change').on('change', function () {
        var checkbox = $(this);
        var filterType = checkbox.attr('class').split(' ')[1].split('-')[0];
        var filterValue = checkbox.val();
        var filterLabel = $('label[for="' + checkbox.attr('id') + '"]').text();
        handleFilterChange(filterType, filterValue, filterLabel);
        updateFilterCounts();
        updateURLWithFilters();
    });
}

function attachStaticEventListeners() {
    $('.collection-checkbox, .search-location-checkbox').on('change', function () {
        var checkbox = $(this);
        var filterType = checkbox.attr('class').split(' ')[1].split('-')[0];
        var filterValue = checkbox.val();
        var filterLabel = $('label[for="' + checkbox.attr('id') + '"]').text();
        handleFilterChange(filterType, filterValue, filterLabel);
        updateFilterCounts();
        resetDependentFilters();
        if (filterType === 'collection') {
            const selectedCollections = $('.collection-checkbox:checked').map(function () {
                return this.value;
            }).get();
            updateSubcollections(selectedCollections);
        }
        $('#survey-table').DataTable().ajax.reload();
        updateURLWithFilters();
    });
    $('#reset-filters').on('click', async function () {
        selectedFilters = {};
        selectedIds.clear();
        selectedYears.clear();
        $('.form-check-input').prop('checked', false);
        updateDecadeCheckboxes();
        updateFiltersDisplay();
        updateFilterCounts();
        await loadDecades();
        table.ajax.reload();
    });
    $('#load-more').on('click', function () {
        currentLimit += 10;
        table.ajax.reload(updateCheckboxes, false);
    });
    $('#export-all').on('click', function () {
        const params = {};
        params.q = $("input[name='q']").val();
        params.survey = getFilterValues('survey-checkbox');
        params.collections = getFilterValues('collection-checkbox');
        params.sub_collections = getFilterValues('subcollection-checkbox');
        params.search_location = getSearchLocation();
        params.years = getYearsFilter();
        const searchParams = new URLSearchParams(params).toString();
        window.location.href = `/export/questions/?${searchParams}`;
    });
    $('#export-selected').on('click', function () {
        if (selectedIds.size === 0) {
            Swal.fire({
                html: `
                    <div style="text-align: center;">
                        <img src="/static/svg/icons/checkbox_checked_swal.svg" alt="Checked Box" style="width: 32px; height: 32px;">
                    </div>
                    <div>
                        Veuillez sélectionner au moins une question à exporter.
                    </div>
                `,
                confirmButtonText: 'Fermer',
                confirmButtonColor: '#536254',
                customClass: {
                    popup: 'custom-swal-popup custom-title-2',
                    confirmButton: 'custom-swal-button '
                }
            });
            return;
        }
        const query = Array.from(selectedIds).map(id => `ids=${id}`).join('&');
        window.location.href = `/export/questions/?${query}`;
    });
    $('#survey-table tbody').on('change', 'input[type="checkbox"]', function () {
        if (this.checked) {
            selectedIds.add(this.value);
        } else {
            selectedIds.delete(this.value);
        }
        const all = $('#survey-table tbody input[type="checkbox"]');
        const checked = $('#survey-table tbody input[type="checkbox"]:checked');
        $('#select-all').prop('checked', all.length === checked.length);
        $('#select-all').prop('indeterminate', checked.length > 0 && all.length !== checked.length);
    });
    $(window).resize(updateTableContainerHeight);
}

function updateURLWithFilters() {
    const url = new URL(window.location.href);
    const params = new URLSearchParams();
    const searchQuery = $('input[name="q"]').val();
    if (searchQuery) {
        params.set('q', searchQuery);
    }
    $('.search-location-checkbox:checked').each(function() {
        params.append('search_location', $(this).val());
    });
    $('.collection-checkbox:checked').each(function() {
        params.append('collections', $(this).val());
    });
    $('.subcollection-checkbox:checked').each(function() {
        params.append('sub_collections', $(this).val());
    });
    $('.survey-checkbox:checked').each(function() {
        params.append('survey', $(this).val());
    });
    Array.from(selectedYears).forEach(year => {
        params.append('years', year);
    });
    url.search = params.toString();
    window.history.pushState({}, '', url);
}
