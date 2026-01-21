// ---------------------------
// 6. Gestion des événements
// ---------------------------
function attachDynamicCheckboxEvents() {

    $('.subcollection-checkbox, .survey-checkbox')
        .off('change')
        .on('change', function () {
            const checkbox = $(this);
            const className = checkbox
                .attr('class')
                .split(' ')
                .find(c => c.endsWith('-checkbox'));

            let filterType = className.replace('-checkbox', '');

            // 🔧 Normalisation pour correspondre aux clés de filterState
            if (filterType === 'subcollection') filterType = 'sub_collections';
            if (filterType === 'survey') filterType = 'survey';

            const filterValue = checkbox.val();

            handleFilterChange(filterType, filterValue);

            // 🔁 Dépendances pour les subcollections
            if (filterType === 'sub_collections') {
                const selectedSubcollections = Array.from(filterState.sub_collections);
                if (selectedSubcollections.length === 0) {
                    const allSubcollections = $('.subcollection-checkbox').map(function () {
                        return this.value;
                    }).get();
                    updateSurveys(allSubcollections);
                } else {
                    updateSurveys(selectedSubcollections);
                }
            }

            // 🔁 Recharger le tableau
            $('#survey-table').DataTable().ajax.reload();
        });
}


function attachStaticEventListeners() {

    // Collections & search locations
    $('.collection-checkbox, .search-location-checkbox')
        .off('change')
        .on('change', function () {
            const checkbox = $(this);
            const className = checkbox
                .attr('class')
                .split(' ')
                .find(c => c.endsWith('-checkbox'));

            let filterType = className.replace('-checkbox', '');

            // 🔧 Normalisation pour correspondre aux clés de filterState
            if (filterType === 'search-location') filterType = 'search_location';
            if (filterType === 'collection') filterType = 'collections';

            const filterValue = checkbox.val();

            handleFilterChange(filterType, filterValue);

            // 🔁 Dépendances pour les collections
            if (filterType === 'collections') {
                const selectedCollections = Array.from(filterState.collections);
                updateSubcollections(selectedCollections);
            }
        });

    // Reset filtres
    $('#reset-filters').off('click').on('click', async function () {
        Object.keys(filterState).forEach(key => filterState[key].clear());
        selectedIds.clear();

        // Reset UI
        $('.form-check-input').prop('checked', false);
        updateDecadeCheckboxes();
        updateFiltersDisplay();
        updateFilterCounts();

        await loadDecades();
        $('#survey-table').DataTable().ajax.reload();
        updateURLWithFilters();

    });

    // Load more
    $('#load-more').off('click').on('click', function () {
        currentLimit += 10;
        $('#survey-table').DataTable().ajax.reload(updateCheckboxes, false);
    });

    // Export all
    $('#export-all').off('click').on('click', function () {
        const params = {
            q: $("input[name='q']").val(),
            survey: Array.from(filterState.survey),
            collections: Array.from(filterState.collections),
            sub_collections: Array.from(filterState.sub_collections),
            search_location: Array.from(filterState.search_location),
            years: Array.from(filterState.years),
        };
        const searchParams = new URLSearchParams(params).toString();
        window.location.href = `/export/questions/?${searchParams}`;
    });

    // Export selected
    $('#export-selected').off('click').on('click', function () {
        if (selectedIds.size === 0) {
            Swal.fire({
                html: `
                    <div style="text-align: center;">
                        <img src="/static/svg/icons/checkbox_checked_swal.svg" style="width: 32px;">
                    </div>
                    <div>Veuillez sélectionner au moins une question à exporter.</div>
                `,
                confirmButtonText: 'Fermer',
                confirmButtonColor: '#536254',
            });
            return;
        }
        const query = Array.from(selectedIds).map(id => `ids=${id}`).join('&');
        window.location.href = `/export/questions/?${query}`;
    });

    // Sélection DataTable
    $('#survey-table tbody').on('change', 'input[type="checkbox"]', function () {
        this.checked ? selectedIds.add(this.value) : selectedIds.delete(this.value);

        const all = $('#survey-table tbody input[type="checkbox"]');
        const checked = $('#survey-table tbody input[type="checkbox"]:checked');

        $('#select-all')
            .prop('checked', all.length === checked.length)
            .prop('indeterminate', checked.length > 0 && all.length !== checked.length);
    });

    $(window).resize(updateTableContainerHeight);
}


function updateURLWithFilters() {
    const url = new URL(window.location.href);
    const params = new URLSearchParams();

    // Mot-clé de recherche
    const searchQuery = $('input[name="q"]').val();
    if (searchQuery) {
        params.set('q', searchQuery);
    }

    // Search locations
    filterState.search_location.forEach(value => {
        params.append('search_location', value);
    });

    // Collections
    filterState.collections.forEach(value => {
        params.append('collections', value);
    });

    // Sous-collections
    filterState.sub_collections.forEach(value => {
        params.append('sub_collections', value);
    });

    // Surveys
    filterState.survey.forEach(value => {
        params.append('survey', value);
    });

    // Années
    filterState.years.forEach(year => {
        params.append('years', year);
    });

    url.search = params.toString();
    window.history.pushState({}, '', url);
}


