// ---------------------------
// 4. Chargement AJAX (décennies/années)
// ---------------------------
function loadDecades() {
    return new Promise((resolve, reject) => {
        const collections = getFilterValues('collection-checkbox');
        const subcollections = getFilterValues('subcollection-checkbox');
        const surveys = getFilterValues('survey-checkbox');
        $.ajax({
            url: '/api/get-decades/',
            type: 'GET',
            data: {
                collections_ids: collections.join(','),
                subcollections_ids: subcollections.join(','),
                survey_ids: surveys.join(',')
            },
            success: function (data) {
                const decadesFilter = $('#years-filter');
                decadesFilter.empty();
                const sortedDecades = Object.keys(data.decades).sort((a, b) => b - a);
                sortedDecades.forEach(decade => {
                    const years = data.decades[decade];
                    const chevronIconPath = '/static/svg/icons/chevron_right.svg';
                    const decadeDiv = $('<div class="form-check-custom decade-item"></div>');
                    const checkboxAndLabelDiv = $('<div class="checkbox-and-label"></div>');
                    const decadeCheckbox = $('<input type="checkbox" class="form-check-input decade-checkbox checkbox-custom" value="' + decade + '" id="decade-' + decade + '">');
                    const decadeLabel = $('<label class="form-check-label" for="decade-' + decade + '">Années ' + decade + '</label>');
                    checkboxAndLabelDiv.append(decadeCheckbox).append(decadeLabel);
                    const chevronIcon = $('<img src="' + chevronIconPath + '" class="chevron-icon decade-chevron" alt="chevron">');
                    decadeDiv.append(checkboxAndLabelDiv).append(chevronIcon);
                    decadesFilter.append(decadeDiv);
                    const allSelected = years.every(year => selectedYears.has(parseInt(year)));
                    const someSelected = years.some(year => selectedYears.has(parseInt(year)));
                    decadeCheckbox.prop('checked', allSelected);
                    decadeCheckbox[0].indeterminate = someSelected && !allSelected;
                    decadeCheckbox.on('change', function () {
                        const isChecked = this.checked;
                        const isIndeterminate = this.indeterminate;
                        if (isIndeterminate) {
                            years.forEach(year => {
                                selectedYears.delete(parseInt(year));
                                if (selectedFilters['year']) {
                                    selectedFilters['year'] = selectedFilters['year'].filter(f => f.value !== year.toString());
                                }
                            });
                            this.indeterminate = false;
                            $(this).prop('checked', false);
                        } else if (isChecked) {
                            years.forEach(year => {
                                selectedYears.add(parseInt(year));
                                if (!selectedFilters['year']) selectedFilters['year'] = [];
                                if (!selectedFilters['year'].some(f => f.value === year.toString())) {
                                    selectedFilters['year'].push({value: year.toString(), label: `Année ${year}`});
                                }
                            });
                        } else {
                            years.forEach(year => {
                                selectedYears.delete(parseInt(year));
                                if (selectedFilters['year']) {
                                    selectedFilters['year'] = selectedFilters['year'].filter(f => f.value !== year.toString());
                                }
                            });
                        }
                        updateFiltersDisplay();
                        updateFilterCounts();
                        updateFilters();
                        $('#survey-table').DataTable().ajax.reload();
                    });
                    chevronIcon.on('click', function () {
                        loadYears(decade);
                    });
                });
                resolve();
            },
            error: function () {
                reject();
            }
        });
    });
}

function loadYears(decade) {
    const collections = getFilterValues('collection-checkbox');
    const subcollections = getFilterValues('subcollection-checkbox');
    const surveys = getFilterValues('survey-checkbox');
    $.ajax({
        url: '/api/get-years-by-decade/',
        type: 'GET',
        data: {
            decade: decade,
            collections_ids: collections.join(','),
            subcollections_ids: subcollections.join(','),
            survey_ids: surveys.join(',')
        },
        success: function (data) {
            const decadesFilter = $('#years-filter');
            decadesFilter.empty();
            const chevronIconPathReturn = '/static/svg/icons/chevron_left.svg';
            const backButton = $('<img src="' + chevronIconPathReturn + '" class="back-button" alt="Retour">');
            backButton.on('click', function () {
                loadDecades();
            });
            decadesFilter.append(backButton);
            data.years.forEach(year => {
                const yearDiv = $('<div class="form-check-custom year-item"></div>');
                const yearCheckbox = $('<input type="checkbox" class="form-check-input year-checkbox checkbox-custom" value="' + year + '" id="year-' + year + '">');
                const yearLabel = $('<label class="form-check-label" for="year-' + year + '">' + year + '</label>');
                if (selectedYears.has(year)) {
                    yearCheckbox.prop('checked', true);
                }
                yearDiv.append(yearCheckbox).append(yearLabel);
                decadesFilter.append(yearDiv);
                yearCheckbox.on('change', function () {
                    const year = parseInt($(this).val());
                    if ($(this).is(':checked')) {
                        addYearToFilters(year);
                    } else {
                        selectedYears.delete(year);
                        if (selectedFilters['year']) {
                            selectedFilters['year'] = selectedFilters['year'].filter(f => f.value !== year.toString());
                        }
                        updateDecadeCheckboxes();
                    }
                    updateFiltersDisplay();
                    updateFilterCounts();
                    $('#survey-table').DataTable().ajax.reload();
                });
            });
        }
    });
}
