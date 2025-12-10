$(document).ready(function () {
    let $currentPopover = null;

    $('[data-toggle="custom-popover"]').on('click', function (e) {
        e.stopPropagation();

        // Fermer le popover actuel s'il existe
        if ($currentPopover) {
            $currentPopover.remove();
            $currentPopover = null;
            return;
        }

        // Créer le popover
        const content = $(this).next('.custom-popover-content').html();
        const $popover = $('<div class="custom-popover-box ui-tooltip"></div>').html(content);

        $('body').append($popover);

        // Positionner à gauche de l'élément cliqué
        const offset = $(this).offset();
        const elementHeight = $(this).outerHeight();
        const popoverWidth = $popover.outerWidth();

        $popover.css({
            top: offset.top + elementHeight / 2 - $popover.outerHeight() / 2 - 50,
            left: offset.left - popoverWidth - 20
        });

        $currentPopover = $popover;
    });

    // Fermer si on clique ailleurs
    $(document).on('click', function () {
        if ($currentPopover) {
            $currentPopover.remove();
            $currentPopover = null;
        }
    });
});