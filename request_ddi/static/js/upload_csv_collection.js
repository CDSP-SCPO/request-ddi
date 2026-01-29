document.addEventListener("DOMContentLoaded", function() {
    const csvForm = document.getElementById('csvUploadFormCollection');
    const overlay = document.getElementById('overlay');
    

    csvForm.addEventListener('submit', function(event) {
        event.preventDefault();  // Prevent the default form submission

        const csvFile = csvForm.querySelector('input[name="csv_file"]').files[0];

        if (!csvFile) {
            Swal.fire({
                icon: "warning",
                title: "Aucun fichier sélectionné",
                text: "Veuillez sélectionner un fichier CSV avant d'envoyer."
            });
            return;
        }


        const formData = new FormData(csvForm);
        const csrfToken = csvForm.querySelector('[name=csrfmiddlewaretoken]').value;
        overlay.classList.add('show');
        fetch(CHECK_DUPLICATES_URL, {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "duplicates") {
                overlay.classList.remove('show');
                Swal.fire({
                    title: "Doublons détectés",
                    html: formatDuplicatesHtml(data.duplicates),
                    icon: "warning",
                    showCancelButton: true,
                    confirmButtonText: "Mettre à jour",
                    cancelButtonText: "Annuler",
                }).then(result => {
                    overlay.classList.remove('show');

                    if (result.isConfirmed) {
                        $('#csvUploadModal').modal('hide');
                        $('#csvUploadModal').one('hidden.bs.modal', function () {
                            overlay.classList.add('show');
                        });
                        submitFinalImport(formData, csrfToken)
                    } else {
                    }
                });
            } else {
                $('#csvUploadModal').modal('hide');

                $('#csvUploadModal').one('hidden.bs.modal', function () {
                    overlay.classList.add('show');
                });
                submitFinalImport(formData, csrfToken)
            }
        })
        .catch(err => {
            overlay.classList.remove('show');
            Swal.fire({
                icon: "error",
                title: "Erreur",
                text: "Impossible de vérifier les doublons."
            });
            overlay.classList.remove("show");
        });
    });
    function submitFinalImport(formData, csrfToken) {
        fetch(csvForm.action + '?force_update=true', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken,
            },
        })
        .then(response => response.json())
        .then(data => {
            overlay.classList.remove('show');
            if (data.status === 'success') {
                Swal.fire({
                    icon: 'success',
                    title: 'Succès',
                    text: data.message,
                }).then(() => {
                    $('#csvUploadModal').modal('hide');
                    location.reload();
                });
            } else {
                overlay.classList.remove('show');
                throw new Error(data.message);
            }
        })
        .catch(error => {
            overlay.classList.remove('show');
            Swal.fire({
                icon: 'error',
                title: 'Erreur',
                text: error.message || 'Erreur lors de l’import',
            });
        });
    }

    function formatDuplicatesHtml(duplicates) {
        let html = '<ul style="text-align:left">';
        for (const doi in duplicates) {
            html += `<li><strong>${doi}</strong><ul>`;
            html += '</ul></li>';
        }
        html += '</ul>';
        return html;
    }
});