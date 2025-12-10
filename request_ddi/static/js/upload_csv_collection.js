document.addEventListener("DOMContentLoaded", function() {
    const csvForm = document.getElementById('csvUploadFormCollection');
    csvForm.addEventListener('submit', function(event) {
        event.preventDefault();  // Prevent the default form submission

        const formData = new FormData(csvForm);

        // Show the loading overlay
        document.getElementById('overlay').classList.add('show');

        fetch(csvForm.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csvForm.querySelector('[name=csrfmiddlewaretoken]').value,
            },
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('overlay').classList.remove('show'); // Hide the loading overlay
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
                Swal.fire({
                    icon: 'error',
                    title: 'Erreur',
                    text: data.message,
                });
            }
        })
        .catch(error => {
            document.getElementById('overlay').classList.remove('show'); // Hide the loading overlay

            Swal.fire({
                icon: 'error',
                title: 'Erreur',
                text: 'Une erreur s\'est produite lors de l\'importation du fichier CSV.',
            });
        });
    });
});