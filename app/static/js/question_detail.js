function toggleCategories(categoryId) {
    var categoriesDiv = document.getElementById(categoryId);
    var caretIcon = event.currentTarget.querySelector('.icon-caret');

    if (categoriesDiv.style.display === "none" || !categoriesDiv.style.display) {
        categoriesDiv.style.display = "block";
        caretIcon.classList.add('rotated');
    } else {
        categoriesDiv.style.display = "none";
        caretIcon.classList.remove('rotated');
    }
}
function exportMetadata() {
const questionId = "{{ question.id }}";
const query = `ids=${questionId}`;
window.location.href = "{% url 'export_questions_csv' %}?" + query;
}

$(document).ready(function() {
    // Initialiser les tooltips
    $('[data-toggle="tooltip"]').tooltip({
        position: {
        my: "right center",
        at: "left center",
        collision: "flipfit"
        },
        tooltipClass: "ui-tooltip"
    });

    // Ajouter un gestionnaire d'événement pour les boutons d'accordéon
    $('.header-container-questions').on('click', function() {
        // Changer l'icône de basculement
        var caretIcon = $(this).find('i.fas');
        if (caretIcon.length) {
            var isExpanded = $(this).attr('aria-expanded') === 'true';
            caretIcon.toggleClass('fa-caret-down', !isExpanded);
            caretIcon.toggleClass('fa-caret-up', isExpanded);
        }
    });
});