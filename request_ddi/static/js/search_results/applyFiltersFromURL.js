window.applyFiltersFromURL = async function() {
    const urlParams = new URLSearchParams(window.location.search);


    const q = urlParams.get('q');
    if (q) $('input[name="q"]').val(q);


    const collections = urlParams.getAll('collections');
    filterState.collections.clear();
    collections.forEach(val => filterState.collections.add(val));

    $('.collection-checkbox').each(function() {
        $(this).prop('checked', filterState.collections.has(this.value));
    });

    const subCollections = urlParams.getAll('sub_collections');
    filterState.sub_collections.clear();
    subCollections.forEach(val => filterState.sub_collections.add(val));

    const collectionIds = filterState.collections.size > 0
        ? Array.from(filterState.collections)
        : $('.collection-checkbox').map(function() { return this.value; }).get();

    const loadedSubcollections = await updateSubcollections(collectionIds);

    $('.subcollection-checkbox').each(function() {
        $(this).prop('checked', filterState.sub_collections.has(this.value));
    });

    const surveys = urlParams.getAll('survey');
    filterState.survey.clear();
    surveys.forEach(val => filterState.survey.add(val));

    const subIdsForSurvey = loadedSubcollections.length > 0
        ? loadedSubcollections
        : $('.subcollection-checkbox').map(function() { return this.value; }).get();

    await updateSurveys(subIdsForSurvey);

    $('.survey-checkbox').each(function() {
        $(this).prop('checked', filterState.survey.has(this.value));
    });

    const searchLocations = urlParams.getAll('search_location');
    filterState.search_location.clear();
    searchLocations.forEach(val => filterState.search_location.add(val));

    $('.search-location-checkbox').each(function() {
        $(this).prop('checked', filterState.search_location.has(this.value));
    });

    const years = urlParams.getAll('years').map(y => parseInt(y));
    filterState.years.clear();
    years.forEach(y => filterState.years.add(y));

    await loadDecades();

    updateDecadeCheckboxes();
    updateFiltersDisplay();
    updateFilterCounts();
    updateURLWithFilters();
    $('#survey-table').DataTable().ajax.reload();
};
