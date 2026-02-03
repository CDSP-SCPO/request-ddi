function exportMetadata() {
  const storedData = sessionStorage.getItem("request_ddi_question_detail");
  if (!storedData) return;

  const { exportUrl, questionId } = JSON.parse(storedData);
  const query = `ids=${questionId}`;

  window.location.href = `${exportUrl}?${query}`;
}

function initQuestionDetailPage() {
  $("[data-toggle=\"tooltip\"]").tooltip({
    position: {
      my: "right center",
      at: "left center",
      collision: "flipfit"
    },
    tooltipClass: "ui-tooltip"
  });

  $(".header-container-questions").on("click", function () {
    const caretIcon = $(this).find("i.fas");
    if (!caretIcon.length) return;

    const isExpanded = $(this).attr("aria-expanded") === "true";
    caretIcon.toggleClass("fa-caret-down", !isExpanded);
    caretIcon.toggleClass("fa-caret-up", isExpanded);
  });
}

// 👉 Comme avant, mais compatible Vite
document.addEventListener("DOMContentLoaded", initQuestionDetailPage);

// 👉 On rend la fonction accessible au HTML (onclick, etc.)
document.getElementsByClassName("export-access-container")[0].addEventListener("click", exportMetadata);
