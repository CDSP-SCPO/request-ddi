$(document).ready(function() {
    var autocompleteUrl = $('meta[name="autocomplete-url"]').attr('content');
    $("#autocomplete-input").autocomplete({
        source: function(request, response) {
            $.ajax({
                url: autocompleteUrl,
                data: {
                    q: request.term  // 'term' est la valeur saisie dans l'input
                },
                success: function(data) {
                    response(data.suggestions);  // Affiche les suggestions dans le dropdown
                }
            });
        },
        minLength: 2,  // Nombre de caractères minimum avant de lancer la requête
        select: function(event, ui) {
            // Action lorsque l'utilisateur sélectionne une suggestion
            $("#autocomplete-input").val(ui.item.value);
            return false;
        }
    });
});