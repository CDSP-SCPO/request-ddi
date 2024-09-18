$(document).ready(function() {
    var autocompleteUrl = $('meta[name="autocomplete-url"]').attr('content');

    $("#autocomplete-input").autocomplete({
        source: function(request, response) {
            $.ajax({
                url: autocompleteUrl,
                data: {
                    q: request.term
                },
                success: function(data) {
                    response(data.suggestions);
                }
            });
        },
        minLength: 2,
        select: function(event, ui) {
            $("#autocomplete-input").val(ui.item.value);
            return false;
        }
    });

    $("#autocomplete-input").on("focus", function() {
        var currentValue = $(this).val();
        if (currentValue.length >= 2) {
            $(this).autocomplete("search", currentValue);
        }
    });
});
