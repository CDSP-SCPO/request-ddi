const {exportUrl, questionId} = JSON.parse(sessionStorage.getItem('request_question_detail'));


function exportMetadata() {
    const query = `ids=${questionId}`;
    window.location.href = `${exportUrl}?${query}`;
}

$(document).ready(function () {
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
    $('.header-container-questions').on('click', function () {
        // Changer l'icône de basculement
        var caretIcon = $(this).find('i.fas');
        if (caretIcon.length) {
            var isExpanded = $(this).attr('aria-expanded') === 'true';
            caretIcon.toggleClass('fa-caret-down', !isExpanded);
            caretIcon.toggleClass('fa-caret-up', isExpanded);
        }
    });
});