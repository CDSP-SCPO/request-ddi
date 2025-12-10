// ---------------------------
// 1. Variables globales
// ---------------------------
var selectedIds = new Set();
var selectedFilters = {};
const selectedYears = new Set();
var currentLimit = 10;
var table;

// ---------------------------
// 2. Fonctions utilitaires
// ---------------------------
function getFilterValues(className) {
    return $(`.${className}:checked`).map(function () {
        return this.value;
    }).get();
}

function getSearchLocation() {
    return getFilterValues('search-location-checkbox');
}

function getYearsFilter() {
    return Array.from(selectedYears);
}

function toggleCategories(categoryId) {
    var categoriesDiv = document.getElementById(categoryId);
    var caretIcon = event.currentTarget.querySelector('.icon-caret');
    if (categoriesDiv.style.display === "none" || !categoriesDiv.style.display) {
        categoriesDiv.style.display = "block";
        caretIcon.classList.add('rotated');
    } else {
        categoriesDiv.style.display = "none";
        caretIcon.classList.remove('rotated');
    }
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

function updateDecadeCheckboxes() {
    const decades = {};
    // Récupérer toutes les décennies disponibles dans le DOM
    $('.decade-checkbox').each(function() {
        const decade = parseInt($(this).val());
        decades[decade] = Array.from({ length: 10 }, (_, i) => decade + i);
    });
    // Pour chaque décennie, vérifier l'état des années
    Object.entries(decades).forEach(([decade, years]) => {
        const decadeCheckbox = $(`#decade-${decade}`);
        if (decadeCheckbox.length === 0) return;
        const allSelected = years.every(year => selectedYears.has(year));
        const someSelected = years.some(year => selectedYears.has(year));
        decadeCheckbox.prop('checked', allSelected);
        decadeCheckbox[0].indeterminate = someSelected && !allSelected;
    });
}

function waitForElement(selector, timeout = 5000) {
    return new Promise((resolve, reject) => {
        const intervalTime = 100;
        let timeElapsed = 0;
        const interval = setInterval(() => {
            if ($(selector).length > 0) {
                clearInterval(interval);
                resolve();
            } else if (timeElapsed >= timeout) {
                clearInterval(interval);
                reject(`⏰ Élément "${selector}" introuvable après ${timeout} ms`);
            }
            timeElapsed += intervalTime;
        }, intervalTime);
    });
}

function addYearToFilters(year) {
    const yearStr = year.toString();
    selectedYears.add(parseInt(yearStr));
    if (!selectedFilters['year']) selectedFilters['year'] = [];
    if (!selectedFilters['year'].some(f => f.value === yearStr)) {
        selectedFilters['year'].push({ value: yearStr, label: `Année ${yearStr}` });
    }
    updateURLWithFilters();
    updateDecadeCheckboxes();
}

function resetDependentFilters() {
    $('.subcollection-checkbox').prop('checked', false);
    $('.survey-checkbox').prop('checked', false);
    selectedFilters['subcollection'] = [];
    selectedFilters['survey'] = [];
    updateFiltersDisplay();
    updateFilterCounts();
}

function resetDependentSurveyFilters() {
    $('.survey-checkbox').prop('checked', false);
    selectedFilters['survey'] = [];
    updateFiltersDisplay();
    updateFilterCounts();
}
