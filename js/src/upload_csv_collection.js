import Swal from "sweetalert2";

function initCsvUploadCollection() {
  const csvForm = document.getElementById("csvUploadFormCollection");
  if (!csvForm) return;

  const overlay = document.getElementById("overlay");

  const checkDuplicatesUrl = window.requestDdiData.checkDuplicatesUrl; // <-- récupère l'URL ici
  
  csvForm.addEventListener("submit", function(event) {
    event.preventDefault();  // Prevent the default form submission

    const csvFile = csvForm.querySelector("input[name=\"csv_file\"]").files[0];

    if (!csvFile) {
      Swal.fire({
        icon: "warning",
        title: "Aucun fichier sélectionné",
        text: "Veuillez sélectionner un fichier CSV avant d'envoyer."
      });
      return;
    }

    const formData = new FormData(csvForm);
    const csrfToken = csvForm.querySelector("[name=csrfmiddlewaretoken]").value;
    overlay.classList.add("show");

    fetch(checkDuplicatesUrl, {
      method: "POST",
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === "duplicates") {
          overlay.classList.remove("show");
          Swal.fire({
            title: "Doublons détectés",
            html: formatDuplicatesHtml(data.duplicates),
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Mettre à jour",
            cancelButtonText: "Annuler",
          }).then(result => {
            overlay.classList.remove("show");

            if (result.isConfirmed) {
              $("#csvUploadModal").modal("hide");
              $("#csvUploadModal").one("hidden.bs.modal", function () {
                overlay.classList.add("show");
              });
              submitFinalImport(this, formData, overlay, csrfToken)
            }
          });
        } else {
          $("#csvUploadModal").modal("hide");

          $("#csvUploadModal").one("hidden.bs.modal", function () {
            overlay.classList.add("show");
          });
          submitFinalImport(this, formData, overlay, csrfToken)
        }
      })
    .catch((err) => { // eslint-disable-line
        overlay.classList.remove("show");
        Swal.fire({
          icon: "error",
          title: "Erreur",
          text: "Impossible de vérifier les doublons."
        });
        overlay.classList.remove("show");
      });
  });
}

function submitFinalImport(csvForm, formData, overlay, csrfToken) {
  fetch(csvForm.action + "?force_update=true", {
    method: "POST",
    body: formData,
    headers: {
      "X-CSRFToken": csrfToken,
    },
  })
    .then(response => response.json())
    .then(data => {
      overlay.classList.remove("show");
      if (data.status === "success") {
        Swal.fire({
          icon: "success",
          title: "Succès",
          text: data.message,
        }).then(() => {
          $("#csvUploadModal").modal("hide");
          location.reload();
        });
      } else if (data.status === "partial_success") {
        Swal.fire({
          icon: "warning",
          title: "Import partiel",
          html: `
            <strong>${data.message}</strong><br><br>
            <strong>Enquêtes importées :</strong> ${data.data[0].successful_surveys.join(", ")}<br><br>
            <strong> ${data.data[0].num_surveys} enquête(s), ${data.data[0].total_variables} variable(s), ${data.data[0].total_bindings} binding(s) créé(s).<br><br>
            <strong>Erreurs :</strong><br>${data.errors.join("<br>")}
            `,
        });
      } else {
        $("#csvUploadModal").off("hidden.bs.modal");
        overlay.classList.remove("show");
        const errorDetails = data.errors?.join("<br>") ?? data.message;
        Swal.fire({
          icon: "error",
          title: "Erreur",
          html: `<strong>${data.message}</strong><br><br><strong>Erreurs :</strong><br>${errorDetails}`,
        });
      }
    })
    .catch(error => {
      overlay.classList.remove("show");
      Swal.fire({ icon: "error", title: "Erreur réseau", text: error.message });

    });
}

function formatDuplicatesHtml(duplicates) {
  let html = "<ul style=\"text-align:left\">";
  for (const doi of duplicates) {
    html += `<li><strong>${doi}</strong><ul>`;
    html += "</ul></li>";
  }
  html += "</ul>";
  return html;
}

// 👉 Comme avant
document.addEventListener("DOMContentLoaded", initCsvUploadCollection);
