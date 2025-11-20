document.addEventListener('DOMContentLoaded', function () {
    const collectionsFilter = document.getElementById('collections-filter');
    const subcollectionsFilter = document.getElementById('subcollections-filter');
    const surveyFilter = document.getElementById('survey-filter');

    $('.selectpicker').selectpicker();

    // Fonction pour mettre à jour les surveys à partir des sous-collections
    function updateSurveys(subcollectionIds) {
        if (subcollectionIds.length === 0) return;

            fetch(`/api/${window.requestdata.api_version}/get-surveys-by-subcollections/?subcollections_ids=${subcollectionIds.join(',')}`)
            .then(response => response.json())
            .then(surveyData => {
                surveyFilter.innerHTML = '';
                surveyData.surveys.forEach(survey => {
                    const option = document.createElement('option');
                    option.value = survey.id;
                    option.textContent = survey.name;
                    surveyFilter.appendChild(option);
                });
                $('.selectpicker').selectpicker('refresh');
            });
    }

    // Quand on change la sélection des collections
    collectionsFilter.addEventListener('change', function () {
        const selectedCollections = Array.from(collectionsFilter.selectedOptions).map(opt => opt.value);

        // Récupérer les sous-collections pour ces collections
        fetch(`/api/${window.requestdata.api_version}/get-subcollections-by-collections/?collections_ids=${selectedCollections.join(',')}`)
            .then(response => response.json())
            .then(data => {
                subcollectionsFilter.innerHTML = '';
                data.subcollections.forEach(sub => {
                    const option = document.createElement('option');
                    option.value = sub.id;
                    option.textContent = sub.name;
                    subcollectionsFilter.appendChild(option);
                });
                $('.selectpicker').selectpicker('refresh');

                // Mettre à jour les surveys pour ces sous-collections
                const subIds = data.subcollections.map(sub => sub.id);
                updateSurveys(subIds);
            });
    });

    // Quand on change la sélection des sous-collections directement
    subcollectionsFilter.addEventListener('change', function () {
        const selectedSubcollections = Array.from(subcollectionsFilter.selectedOptions).map(opt => opt.value);
        if (selectedSubcollections.length > 0) {
            updateSurveys(selectedSubcollections);
        }
    });
});
