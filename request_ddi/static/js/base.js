$(document).ready(function () {
    let $currentPopover = null;
    $('[data-toggle="custom-popover"]').on('click', function (e) {
        e.stopPropagation();

        if ($currentPopover) {
            $currentPopover.remove();
            $currentPopover = null;
            return;
        }

        const content = $(this).next('.custom-popover-content').html();
        const $popover = $('<div class="custom-popover-box ui-tooltip"></div>').html(content);

        $('body').append($popover);

        const offset = $(this).offset();
        const elementHeight = $(this).outerHeight();
        const popoverWidth = $popover.outerWidth();
        const popoverHeight = $popover.outerHeight();

        let topPosition = offset.top + elementHeight / 2 - popoverHeight / 2 - 50;

        const windowHeight = $(window).height();
        const maxTopPosition = windowHeight - popoverHeight - 10;

        if (topPosition + popoverHeight > windowHeight) {
            topPosition = maxTopPosition;
        }

        $popover.css({
            position: 'absolute',
            top: topPosition,
            left: offset.left - popoverWidth - 20,
            zIndex: 9999
        });

        $currentPopover = $popover;
    });

    $(document).on('click', function () {
        if ($currentPopover) {
            $currentPopover.remove();
            $currentPopover = null;
        }
    });
});