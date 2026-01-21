// ---------------------------
// ÉTAT CENTRALISÉ
// ---------------------------
window.filterState = {
    search_location: new Set(),
    collections: new Set(),
    sub_collections: new Set(),
    survey: new Set(),
    years: new Set(),
};

// ---------------------------
// Cache des années disponibles par décennie
// ---------------------------
window.dataForDecades = {};

function getYearsFilter() {
    return Array.from(filterState.years);
}


// ---------------------------
// FONCTIONS GLOBALES
// ---------------------------
window.updateFilterCounts = function() {
    Object.keys(filterState).forEach(filterType => {
        const count = filterState[filterType].size;
        const accordionItem = $(`.accordion-item[data-filter-type="${filterType}"]`);
        const filterCountElement = accordionItem.find('.filter-count');

        if (count > 0) {
            filterCountElement.text(count).css('display', 'flex').show();
        } else {
            filterCountElement.hide();
        }
    });
};


window.updateDecadeCheckboxes = function() {
    $('.decade-checkbox').each(function() {
        const decade = parseInt(this.value, 10);
        const yearsInDecade = window.dataForDecades[decade] || [];

        const allSelected = yearsInDecade.every(y => filterState.years.has(y));
        const someSelected = yearsInDecade.some(y => filterState.years.has(y));

        this.checked = allSelected;
        this.indeterminate = !allSelected && someSelected;
    });
};

window.updateFiltersDisplay = function() {
    const filterContainer = $('#selected-filters-container');
    filterContainer.empty();

    let hasFilters = false;

    Object.entries(filterState).forEach(([key, values]) => {
        if (values.size === 0) return;

        hasFilters = true;

        values.forEach(value => {
            const label = getFilterLabel(key, value);
            const crossIconPath = '/static/svg/icons/cross.svg';

            const card = $(`
                <div class="selected-filter-card">
                    <span>${label}</span>
                    <img type="button" class="remove-filter" src="${crossIconPath}">
                </div>
            `);

            card.find('.remove-filter').on('click', function () {
                filterState[key].delete(value);
                $(`.${key}-checkbox[value="${value}"]`).prop('checked', false);

                if (key === 'years') window.updateDecadeCheckboxes();

                window.updateFiltersDisplay();
                window.updateFilterCounts();
                updateURLWithFilters();
                $('#survey-table').DataTable().ajax.reload();
            });

            filterContainer.append(card);
        });
    });

    filterContainer.toggle(hasFilters);
    updateTableContainerHeight();
};

function getFilterLabel(filterType, value) {
    const filterClassMap = {
        search_location: 'search-location-checkbox',
        collections: 'collection-checkbox',
        sub_collections: 'subcollection-checkbox',
        survey: 'survey-checkbox',
        years: 'year-checkbox'
    };

    const checkboxClass = filterClassMap[filterType];
    if (!checkboxClass) return value;

    const checkbox = $(`.${checkboxClass}[value="${value}"]`);
    if (checkbox.length === 0) return value;

    return checkbox.closest('.form-check-custom').find('label').text().trim();
}
