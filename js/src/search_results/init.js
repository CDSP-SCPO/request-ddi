import {configureFilterController, restoreFiltersFromUrl} from "./filterController.js";
import {attachEventListeners} from "./events.js";
import {initializeResultsTable} from "./results.js";
import {updateTableContainerHeight} from "./utils.js";

$(document).ready(async function () {
  document.documentElement.style.setProperty("--selected-filters-container-height", "0px");

  configureFilterController();
  await restoreFiltersFromUrl(false, false);
  initializeResultsTable();
  attachEventListeners();
  observeSelectedFiltersHeight();
  updateTableContainerHeight();
});

function observeSelectedFiltersHeight() {
  const target = document.getElementById("selected-filters-container");
  if (!target) return;

  const observer = new MutationObserver(updateTableContainerHeight);
  observer.observe(target, {
    attributes: true,
    attributeFilter: ["style"],
    childList: true,
  });
}

document.querySelectorAll(".accordion-button").forEach(button => {
  button.addEventListener("click", function () {
    this.querySelector(".icon-caret")?.classList.toggle("rotated");
  });
});
