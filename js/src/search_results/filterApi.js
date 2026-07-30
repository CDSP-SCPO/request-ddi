async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function apiUrl(path, params = {}) {
  const url = new URL(
    `/api/${window.requestDdiData.apiVersion}/${path}`,
    window.location.origin
  );

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  return url;
}

export async function fetchSubcollections(collectionIds) {
  const data = await fetchJson(
    apiUrl("get-subcollections-by-collections/", {
      collections_ids: collectionIds.join(","),
    })
  );
  return data.subcollections;
}

export async function fetchSurveys(subcollectionIds) {
  const data = await fetchJson(
    apiUrl("get-surveys-by-subcollections/", {
      subcollections_ids: subcollectionIds.join(","),
    })
  );
  return data.surveys;
}

export async function fetchDecades({collectionIds, subcollectionIds, surveyIds}) {
  const data = await fetchJson(
    apiUrl("get-decades/", {
      collections_ids: collectionIds.join(","),
      subcollections_ids: subcollectionIds.join(","),
      survey_ids: surveyIds.join(","),
    })
  );
  return data.decades;
}

export async function fetchYears({decade, collectionIds, subcollectionIds, surveyIds}) {
  const data = await fetchJson(
    apiUrl("get-years-by-decade/", {
      decade,
      collections_ids: collectionIds.join(","),
      subcollections_ids: subcollectionIds.join(","),
      survey_ids: surveyIds.join(","),
    })
  );
  return data.years;
}
