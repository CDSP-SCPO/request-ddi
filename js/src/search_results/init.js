import { updateTableContainerHeight, resetCurrentLimit, clearCache } from "./utils.js";
import { updateFiltersDisplay, updateFilterCounts } from "./filters.js";
import { initializeDataTable } from "./datatable.js";
import { attachStaticEventListeners, attachDynamicCheckboxEvents, updateURLWithFilters } from "./events.js";
import { loadDecades } from "./decades.js";
import { applyFiltersFromURL } from "./applyFiltersFromURL.js";
import { loadInitialData } from "./datatable.js";


$(document).ready(async function () {
  document.documentElement.style.setProperty("--selected-filters-container-height", "0px");
  resetCurrentLimit();
  clearCache();
  updateTableContainerHeight();
  initializeDataTable();
  attachStaticEventListeners();
  attachDynamicCheckboxEvents();
  await loadDecades();
  await applyFiltersFromURL();
  updateFiltersDisplay();
  updateFilterCounts();
  updateURLWithFilters();
  loadInitialData();

  const targetNode = document.getElementById("selected-filters-container");
  if (targetNode) {
    const observer = new MutationObserver(function (mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.attributeName === "style" || mutation.type === "childList") {
          updateTableContainerHeight();
        }
      });
    });
    observer.observe(targetNode, { attributes: true, attributeFilter: ["style"], childList: true });
  }
});

document.querySelectorAll(".accordion-button").forEach(button => {
  button.addEventListener("click", function() {
    const caretIcon = this.querySelector(".icon-caret");
    caretIcon.classList.toggle("rotated");
  });
});
