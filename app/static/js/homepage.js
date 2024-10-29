const searchLocation = document.getElementById('search-location');
const searchQuery = document.getElementById('autocomplete-input');

// Fonction pour changer le placeholder en fonction de l'option sélectionnée
function updatePlaceholder() {
    let placeholderText = '';

    switch (searchLocation.value) {
        case 'questions':
            placeholderText = 'Rechercher une question...';
            break;
        case 'categories':
            placeholderText = 'Rechercher par catégorie...';
            break;
        case 'variable_name':
            placeholderText = 'Rechercher par nom de variable...';
            break;
        default:
            placeholderText = 'Rechercher...';
    }

    // Mettre à jour le placeholder
    searchQuery.placeholder = placeholderText;
}

// Écouter les changements dans le select
searchLocation.addEventListener('change', updatePlaceholder);

// Mettre à jour le placeholder au chargement de la page
document.addEventListener('DOMContentLoaded', updatePlaceholder);