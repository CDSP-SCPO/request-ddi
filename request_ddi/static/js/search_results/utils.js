var selectedIds = new Set();
var currentLimit = 10;
var table;



function getFilterValues(className) {
    return $(`.${className}:checked`).map(function () {
        return this.value;
    }).get();
}


function getSearchLocation() {
    return getFilterValues('search-location-checkbox');
}


function toggleCategories(button, categoryId) {
    const categoriesDiv = document.getElementById(categoryId);
    if (!categoriesDiv) return;

    const caretIcon = button.querySelector('.icon-caret');
    if (!caretIcon) return;

    const isHidden = categoriesDiv.style.display === "none" || !categoriesDiv.style.display;

    categoriesDiv.style.display = isHidden ? "block" : "none";
    caretIcon.classList.toggle('rotated', isHidden);
}


function updateTableContainerHeight() {
    const selectedFiltersContainer = $('#selected-filters-container');
    if (selectedFiltersContainer.is(':visible') && selectedFiltersContainer.children().length > 0) {
        const height = selectedFiltersContainer.outerHeight(true);
        document.documentElement.style.setProperty('--selected-filters-container-height', height + 'px');
    } else {
        document.documentElement.style.setProperty('--selected-filters-container-height', '0px');
    }
}


function updateCheckboxes() {
    $('#survey-table tbody input[type="checkbox"]').each(function() {
        this.checked = selectedIds.has(this.value);
    });
}

function updateFilters() {
    $('#survey-table').DataTable().ajax.reload();
}

// rendre accessibles globalement
window.updateCheckboxes = updateCheckboxes;
window.updateFilters = updateFilters;

