document.addEventListener("DOMContentLoaded", function() {
    const csvForm = document.getElementById('csvUploadForm');
        csvForm.addEventListener('submit', function(event) {
                event.preventDefault();  // Empêche l'envoi immédiat du formulaire

                const formData = new FormData(csvForm);

                fetch(csvForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': csvForm.querySelector('[name=csrfmiddlewaretoken]').value,
                    },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        Swal.fire({
                            icon: 'success',
                            title: 'Succès',
                            text: data.message,
                        }).then(() => {
                            $('#csvUploadModal').modal('hide');
                        });
                    } else {
                        Swal.fire({
                            icon: 'error',
                            title: 'Erreur',
                            text: data.message,
                        }).then(() => {
                            $('#csvUploadModal').modal('hide');
                        });
                    }
                })
                .catch(error => {
                    Swal.fire({
                        icon: 'error',
                        title: 'Erreur',
                        text: 'Une erreur s\'est produite lors de l\'importation du fichier CSV.',
                    }).then(() => {
                        $('#csvUploadModal').modal('hide');
                    });
                });
            });
        });
