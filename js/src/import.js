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
  const csvFiles = getCsvFiles(csvForm);

  if (csvFiles.length === 0) {
    showNoFileSelectedAlert("Veuillez sélectionner un fichier CSV avant d'envoyer.");
    return;
  }

  Promise.all(csvFiles.map(readFileAsText))
    .then((contents) => {
      const missingUrlDois = [...new Set(contents.flatMap(findDoisMissingUrl))];

      if (missingUrlDois.length === 0) {
        submitForm(csvForm, overlay, handleUploadResponse);
        return;
      }

      confirmMissingUrlDois(missingUrlDois).then((confirmed) => {
        if (confirmed) {
          submitForm(csvForm, overlay, handleUploadResponse);
        }
      });
    })
    .catch(() => {
      // Lecture impossible côté client (encodage exotique, etc.) : on laisse le
      // serveur faire foi et renvoyer l'erreur appropriée le cas échéant.
      submitForm(csvForm, overlay, handleUploadResponse);
    });
}

function getCsvFiles(csvForm) {
  return Array.from(csvForm.querySelector("input[name=\"csv_file\"]")?.files ?? []);
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

// Détecte les lignes du CSV sans URL, pour prévenir l'utilisateur avant l'envoi que
// l'import de ces DOIs dépend d'un fichier XML déjà déposé (voir DDICXMLUploadView).
// Volontairement permissif : c'est un avertissement côté client, pas une validation —
// le serveur reste seul juge de la validité réelle du fichier.
function findDoisMissingUrl(csvText) {
  const lines = csvText.split(/\r\n|\r|\n/).filter((line) => line.trim() !== "");
  if (lines.length < 2) return [];

  const delimiter = detectCsvDelimiter(lines[0]);
  const headers = parseCsvLine(lines[0], delimiter).map((h) => h.trim().toLowerCase());
  const doiIndex = headers.indexOf("doi");
  const urlIndex = headers.indexOf("url");

  if (doiIndex === -1) return [];

  return lines
    .slice(1)
    .map((line) => parseCsvLine(line, delimiter))
    .filter((fields) => urlIndex === -1 || !fields[urlIndex]?.trim())
    .map((fields) => fields[doiIndex]?.trim())
    .filter(Boolean);
}

function detectCsvDelimiter(headerLine) {
  const candidates = [",", ";", "\t"];
  return candidates.reduce(
    (best, candidate) =>
      headerLine.split(candidate).length > headerLine.split(best).length ? candidate : best,
    candidates[0],
  );
}

// Parseur CSV minimal (une ligne), gère les champs entre guillemets doubles avec
// séparateur ou saut de ligne échappé — suffisant pour un simple avertissement client,
// pas une implémentation RFC4180 complète.
function parseCsvLine(line, delimiter) {
  const fields = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (inQuotes) {
      if (char === "\"" && line[i + 1] === "\"") {
        current += "\"";
        i++;
      } else if (char === "\"") {
        inQuotes = false;
      } else {
        current += char;
      }
      continue;
    }

    if (char === "\"") {
      inQuotes = true;
    } else if (char === delimiter) {
      fields.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  fields.push(current);
  return fields;
}

function confirmMissingUrlDois(dois) {
  return Swal.fire({
    icon: "warning",
    title: "Fichiers XML déjà déposés ?",
    html: `
      <p style="text-align:left">Les enquêtes suivantes n'ont pas d'URL dans le CSV : l'import ira
      chercher un fichier XML déjà déposé pour leur DOI. Assurez-vous de l'avoir déposé avant de
      continuer, sinon l'import échouera pour ces enquêtes.</p>
      <ul style="text-align:left">${dois.map((doi) => `<li>${escapeHtml(doi)}</li>`).join("")}</ul>
    `,
    showCancelButton: true,
    confirmButtonText: "Continuer l'import",
    cancelButtonText: "Annuler",
  }).then((result) => result.isConfirmed);
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
    }).then(() => {
      // Sans ça, la modale Bootstrap "Dépose des fichiers XML" reste affichée en
      // arrière-plan une fois le Swal fermé, obligeant l'utilisateur à cliquer
      // ailleurs pour la faire disparaître.
      $("#xmlUploadModal").modal("hide");
    });
    return;
  }

  showErrorAlert(data, overlay, "xmlUploadModal");
}

document.addEventListener("DOMContentLoaded", initCsvUploadCollection);
document.addEventListener("DOMContentLoaded", initXmlUpload);

