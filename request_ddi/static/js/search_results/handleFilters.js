window.handleFilterChange = async function(filterType, filterValue) {
    selectedIds.clear();

    if (!filterState[filterType]) return;

    // Toggle état central
    if (filterState[filterType].has(filterValue)) {
        filterState[filterType].delete(filterValue);
    } else {
        filterState[filterType].add(filterValue);
    }

    if (filterType === 'collections') {
        const collectionIds = Array.from(filterState.collections);
        const subIds = await window.updateSubcollections(collectionIds);

        const subIdsForSurveys =
            filterState.sub_collections.size > 0
                ? Array.from(filterState.sub_collections)
                : subIds;

        await window.updateSurveys(subIdsForSurveys);
    }

    if (filterType === 'sub_collections') {
        const subIds = Array.from(filterState.sub_collections);
        await window.updateSurveys(subIds);
    }

    // 🔁 Recharger les années si les filtres parents changent
    if (['collections', 'sub_collections', 'survey'].includes(filterType)) {
        await loadDecades();
    }

    updateFiltersDisplay();
    updateFilterCounts();
    updateURLWithFilters();

    // Reload table
    $('#survey-table').DataTable().ajax.reload();
};
