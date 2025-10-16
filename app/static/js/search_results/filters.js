// ---------------------------
// 3. Filtres : affichage, comptage, reset
// ---------------------------
function updateFiltersDisplay() {
    const filterContainer = $('#selected-filters-container');
    filterContainer.empty();
    let hasFilters = false;
    $.each(selectedFilters, function (key, filters) {
        const validFilters = filters.filter(function (filter) {
            if (key === 'year') return true;
            return $('input[type="checkbox"][value="' + filter.value + '"]').length > 0;
        });
        selectedFilters[key] = validFilters;
        if (validFilters.length > 0) {
            hasFilters = true;
            validFilters.forEach(function (filter) {
                const crossIconPath = '/static/svg/icons/cross.svg';
                var card = $('<div class="selected-filter-card"> <span>' + filter.label + '</span><img type="button" class="remove-filter" src="' + crossIconPath + '"></div>');
                card.find('.remove-filter').click(function () {
                    var index = selectedFilters[key].findIndex(f => f.value === filter.value);
                    if (index !== -1) {
                        selectedFilters[key].splice(index, 1);
                        $('input[type="checkbox"][value="' + filter.value + '"]').prop('checked', false);
                        if (key === 'year') {
                            selectedYears.delete(parseInt(filter.value));
                            updateDecadeCheckboxes();
                        }
                        updateURLWithFilters();
                        updateFiltersDisplay();
                        updateFilterCounts();
                        $('#survey-table').DataTable().ajax.reload();
                    }
                });
                filterContainer.append(card);
            });
        }
    });
    if (hasFilters) {
        filterContainer.show();
    } else {
        filterContainer.hide();
    }
    updateTableContainerHeight();
}

function updateFilterCounts() {
    $('.accordion-item').each(function () {
        var accordionItem = $(this);
        var checkboxes = accordionItem.find('.form-check-input:checked');
        var count = checkboxes.length;
        var filterCountElement = accordionItem.find('.filter-count');
        if (count > 0) {
            filterCountElement.text(count).css('display', 'flex').show();
        } else {
            filterCountElement.hide();
        }
    });
    const yearCount = selectedYears.size;
    const yearFilterCount = $('#headingFive .filter-count');
    if (yearCount > 0) {
        yearFilterCount.text(yearCount).show();
    } else {
        yearFilterCount.hide();
    }
}
