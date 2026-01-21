window.updateSubcollections = async function(selectedCollections) {
    const idsParam = selectedCollections?.length ? selectedCollections.join(',') : '';

    const response = await fetch(
        `/api/${window.requestdata.api_version}/get-subcollections-by-collections/?collections_ids=${idsParam}`
    );

    if (!response.ok) {
        console.error('Erreur API subcollections');
        return [];
    }

    const data = await response.json();

    const subcollectionsFilter = $('#subcollections-filter');
    subcollectionsFilter.empty();

    const availableIds = data.subcollections.map(sc => sc.id);

    data.subcollections.forEach(sc => {
        subcollectionsFilter.append(`
            <div class="form-check-custom">
                <input class="form-check-input subcollection-checkbox checkbox-custom"
                       type="checkbox"
                       value="${sc.id}"
                       id="subcollection-${sc.id}">
                <label class="form-check-label" for="subcollection-${sc.id}">
                    ${sc.name}
                </label>
            </div>
        `);
    });

    filterState.sub_collections.forEach(id => {
        if (!availableIds.includes(id)) {
            filterState.sub_collections.delete(id);
        }
    });

    $('.subcollection-checkbox').each(function () {
        $(this).prop('checked', filterState.sub_collections.has(this.value));
    });

    attachDynamicCheckboxEvents();
    updateFilterCounts();

    return availableIds;
};

window.updateSurveys = async function(selectedSubcollections) {
    const idsParam = selectedSubcollections?.length ? selectedSubcollections.join(',') : '';

    const response = await fetch(
        `/api/${window.requestdata.api_version}/get-surveys-by-subcollections/?subcollections_ids=${idsParam}`
    );

    if (!response.ok) {
        console.error('Erreur API surveys');
        return [];
    }

    const data = await response.json();

    const surveysFilter = $('#survey-filter');
    surveysFilter.empty();

    const availableIds = data.surveys.map(s => s.id);

    data.surveys.forEach(s => {
        surveysFilter.append(`
            <div class="form-check-custom">
                <input class="form-check-input survey-checkbox checkbox-custom"
                       type="checkbox"
                       value="${s.id}"
                       id="survey-${s.id}">
                <label class="form-check-label" for="survey-${s.id}">
                    ${s.name}
                </label>
            </div>
        `);
    });

    filterState.survey.forEach(id => {
        if (!availableIds.includes(id)) {
            filterState.survey.delete(id);
        }
    });

    $('.survey-checkbox').each(function () {
        $(this).prop('checked', filterState.survey.has(this.value));
    });

    attachDynamicCheckboxEvents();
    updateFiltersDisplay();
    updateFilterCounts();

    return availableIds;
};
