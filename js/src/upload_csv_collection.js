import Swal from "sweetalert2";

function initCsvUploadCollection() {
  const csvForm = document.getElementById("csvUploadFormCollection");
  if (!csvForm) return;

  const overlay = document.getElementById("overlay");
  
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
    overlay.classList.add("show");

    fetch(csvForm.action, {
      method: "POST",
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        overlay.classList.remove("show");
        if (data.status === "duplicates") {
          Swal.fire({
            title: "Doublons détectés",
            html: formatDuplicatesHtml(data.duplicates),
            icon: "warning",
          });
        } else if (data.status === "success") {
          Swal.fire({ icon: "success", title: "Succès", text: data.message })
            .then(() => location.reload());
        } else if (data.status === "partial_success") {
          const allSkipped = data.data[0].num_surveys === 0 && data.data[0].total_variables === 0;
          const skippedErrors = data.errors?.filter(e => e.startsWith("Doublon ignoré")) ?? [];
          const otherErrors = data.errors?.filter(e => !e.startsWith("Doublon ignoré")) ?? [];
          const successfulSurveys = data.data[0].successful_surveys ?? [];
          Swal.fire({
            icon: "warning",
            title: allSkipped ? "Aucun import effectué" : "Import partiel",
            html: `
              <strong>${data.message}</strong><br><br>
              ${successfulSurveys.length > 0 ? `<strong>Enquêtes importées :</strong> ${successfulSurveys.join(", ")}<br><br>` : ""}
              <strong> ${data.data[0].num_surveys} enquête(s), ${data.data[0].total_variables} variable(s), ${data.data[0].total_bindings} binding(s) créé(s).<br><br></strong>
              ${skippedErrors.length > 0 ? `<strong>⚠️ Doublons ignorés (cochez "Ignorer les doublons" pour forcer l'import) :</strong><br>${skippedErrors.map(e => e.replace("Doublon ignoré : ", "")).join("<br>")}<br><br>` : ""}
              ${otherErrors.length > 0 ? `<strong>Erreurs :</strong><br>${otherErrors.join("<br>")}` : ""}
            `,
          });
        }
        else {
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
    .catch((err) => { // eslint-disable-line
        overlay.classList.remove("show");
        Swal.fire({
          icon: "error",
          title: "Erreur",
          text: `Impossible de vérifier les doublons : ${err}`
        });
      });
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

