import {selectedIds} from "./state.js";

// Displays or hides question catefories and turns the caret associated
export function toggleCategories(button, categoryId) {
  const categoriesDiv = document.getElementById(categoryId);
  const caretIcon = button.querySelector(".icon-caret");
  if (!categoriesDiv || !caretIcon) return;

  const isHidden = categoriesDiv.style.display === "none" || !categoriesDiv.style.display;
  categoriesDiv.style.display = isHidden ? "block" : "none";
  caretIcon.classList.toggle("rotated", isHidden);
}

export function updateTableContainerHeight() {
  const container = $("#selected-filters-container");
  const height = container.is(":visible") && container.children().length
    ? container.outerHeight(true)
    : 0;
  document.documentElement.style.setProperty(
    "--selected-filters-container-height",
    `${height}px`
  );
}

// Visually restores selected questions after a datatable reload
export function updateResultCheckboxes() {
  $("#survey-table tbody input[type='checkbox']").each(function () {
    this.checked = selectedIds.has(this.value);
  });
}
