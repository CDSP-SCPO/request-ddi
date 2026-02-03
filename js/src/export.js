export function initFiltersCascade() {
  const collectionsFilter = document.getElementById("collections-filter");
  const subcollectionsFilter = document.getElementById("subcollections-filter");
  const surveyFilter = document.getElementById("survey-filter");

  // Sécurité : si la page n'a pas ces éléments, on ne fait rien
  if (!collectionsFilter || !subcollectionsFilter || !surveyFilter) return;

  $(".selectpicker").selectpicker();

  function getApiUrl(endpoint, params) {
    const query = new URLSearchParams(params).toString();
    return `/api/${window.requestDdiData.apiVersion}/${endpoint}/?${query}`;
  }

  function populateSelect(selectElement, items) {
    selectElement.innerHTML = "";

    items.forEach(item => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name;
      selectElement.appendChild(option);
    });

    $(".selectpicker").selectpicker("refresh");
  }

  async function fetchSubcollections(collectionIds) {
    if (!collectionIds.length) return [];

    const response = await fetch(
      getApiUrl("get-subcollections-by-collections", {
        collections_ids: collectionIds.join(",")
      })
    );

    const data = await response.json();
    return data.subcollections || [];
  }

  async function fetchSurveys(subcollectionIds) {
    if (!subcollectionIds.length) return [];

    const response = await fetch(
      getApiUrl("get-surveys-by-subcollections", {
        subcollections_ids: subcollectionIds.join(",")
      })
    );

    const data = await response.json();
    return data.surveys || [];
  }

  collectionsFilter.addEventListener("change", async () => {
    const collectionIds = Array.from(collectionsFilter.selectedOptions).map(o => o.value);

    const subcollections = await fetchSubcollections(collectionIds);
    populateSelect(subcollectionsFilter, subcollections);

    const subIds = subcollections.map(sub => sub.id);
    const surveys = await fetchSurveys(subIds);
    populateSelect(surveyFilter, surveys);
  });

  subcollectionsFilter.addEventListener("change", async () => {
    const subIds = Array.from(subcollectionsFilter.selectedOptions).map(o => o.value);
    const surveys = await fetchSurveys(subIds);
    populateSelect(surveyFilter, surveys);
  });
}

document.addEventListener("DOMContentLoaded", initFiltersCascade);
