document.addEventListener('DOMContentLoaded', function () {
    const collectionsFilter = document.getElementById('collections-filter');
    const surveyFilter = document.getElementById('survey-filter');
    $('.selectpicker').selectpicker();

    collectionsFilter.addEventListener('change', function () {
        const selectedCollections = Array.from(collectionsFilter.selectedOptions).map(option => option.value);

        fetch(`/api/get-surveys-by-collections/?collections_ids=${selectedCollections.join(',')}`)
            .then(response => response.json())
            .then(data => {
                surveyFilter.innerHTML = '';

                data.surveys.forEach(survey => {
                    const option = document.createElement('option');
                    option.value = survey.id;
                    option.textContent = survey.name;
                    surveyFilter.appendChild(option);
                });

                $('.selectpicker').selectpicker('refresh');
            });
    });
});