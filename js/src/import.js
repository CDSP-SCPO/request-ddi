import Swal from "sweetalert2";

function initCsvUploadCollection() {
  const csvForm = document.getElementById("csvUploadFormCollection");
  if (!csvForm) return;

  csvForm.addEventListener("submit", handleCsvUploadSubmit);
}

function handleCsvUploadSubmit(event) {
  event.preventDefault();

  const csvForm = event.currentTarget;
  const overlay = document.getElementById("overlay");
  const csvFile = getCsvFile(csvForm);

  if (!csvFile) {
    showNoFileSelectedAlert("Veuillez sélectionner un fichier CSV avant d'envoyer.");
    return;
  }

  submitForm(csvForm, overlay, handleUploadResponse);
}

function getCsvFile(csvForm) {
  return csvForm.querySelector("input[name=\"csv_file\"]")?.files[0];
}

function submitForm(form, overlay, onResponse) {
  const formData = new FormData(form);
  showOverlay(overlay);

  fetch(form.action, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => onResponse(data, overlay))
    .catch((err) => handleUploadError(err, overlay));
}

// Échappe une chaîne avant de l'injecter dans du HTML (Swal `html:`) — nécessaire
// puisque certains messages d'erreur embarquent des chaînes fournies par
// l'utilisateur (ex: nom de fichier uploadé), qui ne doivent jamais être interprétées
// comme du HTML actif.
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function handleUploadResponse(data, overlay) {
  hideOverlay(overlay);

  if (data.status === "duplicates") {
    showDuplicatesAlert(data.duplicates);
    return;
  }

  if (data.status === "success") {
    showSuccessAlert(data.message);
    return;
  }

  if (data.status === "partial_success") {
    showPartialSuccessAlert(data);
    return;
  }

  showErrorAlert(data, overlay);
}

function showNoFileSelectedAlert(text) {
  Swal.fire({
    icon: "warning",
    title: "Aucun fichier sélectionné",
    text,
  });
}

function showDuplicatesAlert(duplicates) {
  Swal.fire({
    title: "Doublons détectés",
    html: formatDuplicatesHtml(duplicates),
    icon: "warning",
  });
}

function showSuccessAlert(message) {
  Swal.fire({
    icon: "success",
    title: "Succès",
    text: message,
  }).then(() => {
    window.location = "/import/status/";
  });
}

function showPartialSuccessAlert(data) {
  const importData = data.data[0];
  const allSkipped = importData.num_surveys === 0;
  const skippedErrors = data.errors?.filter((e) => e.startsWith("Doublon ignoré")) ?? [];
  const otherErrors = data.errors?.filter((e) => !e.startsWith("Doublon ignoré")) ?? [];
  const successfulSurveys = importData.successful_surveys ?? [];

  Swal.fire({
    icon: "warning",
    title: allSkipped ? "Aucun import effectué" : "Import partiel",
    html: formatPartialSuccessHtml(data.message, importData, skippedErrors, otherErrors, successfulSurveys),
  }).then(() => {
    if (!allSkipped) {
      window.location = "/import/status/";
    }
  });
}

function formatPartialSuccessHtml(message, importData, skippedErrors, otherErrors, successfulSurveys) {
  return `
    <strong>${message}</strong><br><br>
    ${successfulSurveys.length > 0 ? `<strong>Enquêtes traitée(s) :</strong> ${successfulSurveys.join(", ")}<br><br>` : ""}
    <strong>${importData.num_surveys} enquête(s) seront importée(s).<br><br></strong>
    ${skippedErrors.length > 0 ? `<strong>⚠️ Doublons ignorés (cochez "Ignorer les doublons" pour forcer l'import) :</strong><br>${skippedErrors.map((e) => e.replace("Doublon ignoré : ", "")).join("<br>")}<br><br>` : ""}
    ${otherErrors.length > 0 ? `<strong>Erreurs :</strong><br>${otherErrors.join("<br>")}` : ""}
  `;
}

function showErrorAlert(data, overlay, modalId = "csvUploadModal") {
  $(`#${modalId}`).off("hidden.bs.modal");
  hideOverlay(overlay);

  const errorDetails = data.errors?.length
    ? data.errors.map(escapeHtml).join("<br>")
    : escapeHtml(data.message);

  Swal.fire({
    icon: "error",
    title: "Erreur",
    html: `<strong>${escapeHtml(data.message)}</strong><br><br><strong>Erreurs :</strong><br>${errorDetails}`,
  });
}

function handleUploadError(err, overlay) {
  hideOverlay(overlay);

  Swal.fire({
    icon: "error",
    title: "Erreur",
    text: `Impossible de vérifier les doublons : ${err}`,
  });
}

function showOverlay(overlay) {
  overlay?.classList.add("show");
}

function hideOverlay(overlay) {
  overlay?.classList.remove("show");
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

function initXmlUpload() {
  const xmlForm = document.getElementById("xmlUploadForm");
  if (!xmlForm) return;

  xmlForm.addEventListener("submit", handleXmlUploadSubmit);
}

function handleXmlUploadSubmit(event) {
  event.preventDefault();

  const xmlForm = event.currentTarget;
  const overlay = document.getElementById("overlay");
  const xmlFiles = xmlForm.querySelector("input[name=\"xml_files\"]")?.files;

  if (!xmlFiles || xmlFiles.length === 0) {
    showNoFileSelectedAlert("Veuillez sélectionner au moins un fichier XML avant d'envoyer.");
    return;
  }

  submitForm(xmlForm, overlay, handleXmlUploadResponse);
}

function handleXmlUploadResponse(data, overlay) {
  hideOverlay(overlay);

  if (data.status === "success" || data.status === "partial_success") {
    const dois = data.data?.[0]?.dois ?? [];
    Swal.fire({
      icon: data.status === "success" ? "success" : "warning",
      title: data.status === "success" ? "Succès" : "Dépôt partiel",
      html: `
        <strong>${escapeHtml(data.message)}</strong><br><br>
        ${dois.length > 0 ? `<strong>Fichier(s) déposé(s) :</strong> ${dois.map(escapeHtml).join(", ")}<br><br>` : ""}
        ${data.errors?.length ? `<strong>Erreurs :</strong><br>${data.errors.map(escapeHtml).join("<br>")}` : ""}
      `,
    });
    return;
  }

  showErrorAlert(data, overlay, "xmlUploadModal");
}

document.addEventListener("DOMContentLoaded", initCsvUploadCollection);
document.addEventListener("DOMContentLoaded", initXmlUpload);

