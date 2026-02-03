import Swal from "sweetalert2";

export function initUploadXml() {
  const fileInput = document.getElementById("xml_file");
  const fileList = document.getElementById("file-list");
  const uploadForm = document.getElementById("xmlUploadForm");
  if (!fileInput || !fileList || !uploadForm) return;

  const checkDuplicatesUrl = window.requestDdiData.checkDuplicatesUrl; // <-- récupère l'URL ici

  let dataTransfer = new DataTransfer();

  uploadForm.addEventListener("submit", function (event) {
    event.preventDefault();  // Empêche l'envoi immédiat du formulaire

    if (dataTransfer.files.length === 0) {
      Swal.fire({
        icon: "warning",
        title: "Aucun fichier sélectionné",
        text: "Veuillez sélectionner au moins un fichier avant d'envoyer."
      });
      return;
    }

    var formData = new FormData(this);
    for (let file of dataTransfer.files) {
      formData.append("xml_file", file);
    }

    // Affiche l'overlay de chargement
    document.getElementById("overlay").classList.add("show");

    // Vérification des doublons
    fetch(checkDuplicatesUrl, {
      method: "POST",
      body: formData,
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === "exists") {
          Swal.fire({
            title: "Doublons détectés",
            text: "Certaines variables de ce document existent déjà. Voulez-vous les mettre à jour ?",
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Oui, mettre à jour",
            cancelButtonText: "Annuler",
          }).then((result) => {
            if (result.isConfirmed) {
              // Confirme l'envoi final du formulaire
              document.getElementById("xmlUploadForm").submit();
            } else {
              document.getElementById("overlay").classList.remove("show");
            }
          });
        } else {
          document.getElementById("xmlUploadForm").submit();
        }
      })
      .catch((err) => { // eslint-disable-line
        Swal.fire({
          icon: "error",
          title: "Erreur",
          text: "Une erreur s'est produite lors de la vérification des doublons."
        });
        document.getElementById("overlay").classList.remove("show");
      });
  });
}

document.addEventListener("DOMContentLoaded", initUploadXml);
