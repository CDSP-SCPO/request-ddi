import { filterState, updateDecadeCheckboxes, updateFiltersDisplay, updateFilterCounts, dataForDecades } from "./filters.js";
import { updateURLWithFilters } from "./events.js";
import { clearCache, resetCurrentLimit } from "./utils.js";

export function loadDecades() {
  return new Promise((resolve, reject) => {
    const collections = Array.from(filterState.collections);
    const subcollections = Array.from(filterState.sub_collections);
    const surveys = Array.from(filterState.survey);

    $.ajax({
      url: `/api/${window.requestDdiData.apiVersion}/get-decades/`,
      type: "GET",
      data: {
        collections_ids: collections.join(","),
        subcollections_ids: subcollections.join(","),
        survey_ids: surveys.join(",")
      },
      success: function (data) {
        const decadesFilter = $("#years-filter");
        decadesFilter.empty();

        const sortedDecades = Object.keys(data.decades).sort((a, b) => b - a);

        // Stocker toutes les années disponibles par décennie
        sortedDecades.forEach(decade => {
          dataForDecades[decade] = data.decades[decade].map(y => parseInt(y, 10));
        });

        // 🔥 Supprimer les années invalides du filterState
        const validYears = new Set();
        Object.values(dataForDecades).forEach(years => years.forEach(y => validYears.add(y)));
        filterState.years.forEach(year => { 
          if (!validYears.has(year)) filterState.years.delete(year); 
        });

        // Créer les checkboxes des décennies
        sortedDecades.forEach(decade => {
          const yearsInDecade = dataForDecades[decade];

          const decadeDiv = $("<div class=\"form-check-custom decade-item\"></div>");
          const checkboxAndLabel = $("<div class=\"checkbox-and-label\"></div>");

          const decadeCheckbox = $(`<input type="checkbox" class="form-check-input decade-checkbox checkbox-custom" value="${decade}" id="decade-${decade}">`);
          const decadeLabel = $(`<label class="form-check-label" for="decade-${decade}">Années ${decade}</label>`);

          checkboxAndLabel.append(decadeCheckbox, decadeLabel);
          const chevronIcon = $("<img src=\"/static/svg/icons/chevron_right.svg\" class=\"chevron-icon decade-chevron\" alt=\"chevron\">");

          decadeDiv.append(checkboxAndLabel, chevronIcon);
          decadesFilter.append(decadeDiv);

          // ✅ Initialiser l'état des checkboxes décennies
          updateDecadeCheckboxes();

          // Coche / décoche toutes les années de la décennie
          decadeCheckbox.on("change", function () {
            if (this.checked) {
              yearsInDecade.forEach(y => filterState.years.add(y));
            } else {
              yearsInDecade.forEach(y => filterState.years.delete(y));
            }

            updateDecadeCheckboxes();
            updateFiltersDisplay();
            updateFilterCounts();
            updateURLWithFilters();
            clearCache();
            resetCurrentLimit();
            $("#survey-table").DataTable().ajax.reload();
          });

          // Afficher les années de la décennie
          chevronIcon.on("click", function () {
            loadYears(decade);
          });
        });

        resolve();
      },
      error: function (err) {
        console.error("❌ Erreur loadDecades():", err);
        reject(err);
      }
    });
  });
}

function loadYears(decade) {
  const collections = Array.from(filterState.collections);
  const subcollections = Array.from(filterState.sub_collections);
  const surveys = Array.from(filterState.survey);

  $.ajax({
    url: `/api/${window.requestDdiData.apiVersion}/get-years-by-decade/`,
    type: "GET",
    data: {
      decade: decade,
      collections_ids: collections.join(","),
      subcollections_ids: subcollections.join(","),
      survey_ids: surveys.join(",")
    },
    success: function (data) {
      const decadesFilter = $("#years-filter");
      decadesFilter.empty();

      // Bouton retour pour revenir aux décennies
      const backButton = $("<img src=\"/static/svg/icons/chevron_left.svg\" class=\"back-button\" alt=\"Retour\">");
      backButton.on("click", () => loadDecades());
      decadesFilter.append(backButton);

      // Affichage des années
      data.years.forEach(year => {
        const numericYear = parseInt(year, 10);
        const yearDiv = $("<div class=\"form-check-custom year-item\"></div>");
        const yearCheckbox = $(`<input type="checkbox" class="form-check-input year-checkbox checkbox-custom" value="${numericYear}" id="year-${numericYear}">`);
        const yearLabel = $(`<label class="form-check-label" for="year-${numericYear}">${numericYear}</label>`);

        yearDiv.append(yearCheckbox, yearLabel);
        decadesFilter.append(yearDiv);

        // Si l'année est déjà dans filterState, coche la checkbox
        if (filterState.years.has(numericYear)) yearCheckbox.prop("checked", true);

        // Gérer la sélection/déselection
        yearCheckbox.on("change", function () {
          const y = parseInt($(this).val(), 10);
          if ($(this).is(":checked")) filterState.years.add(y);
          else filterState.years.delete(y);

          updateDecadeCheckboxes();
          updateFiltersDisplay();
          updateFilterCounts();
          updateURLWithFilters();
          clearCache();
          resetCurrentLimit();
          $("#survey-table").DataTable().ajax.reload();
        });
      });
    },
    error: function (err) {
      console.error("❌ Erreur loadYears():", err);
    }
  });
}