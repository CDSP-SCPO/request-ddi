import $ from "jquery";

import { toggleCategories } from "./search_results/utils.js";

function initPopovers() {
  let $currentPopover = null;

  document.addEventListener("click", () => {
    if ($currentPopover) {
      $currentPopover.remove();
      $currentPopover = null;
    }
  });

  $("[data-toggle=\"custom-popover\"]").on("click", function (e) {
    e.stopPropagation();

    if ($currentPopover) {
      $currentPopover.remove();
      $currentPopover = null;
      return;
    }

    const content = $(this).next(".custom-popover-content").html();
    const $popover = $("<div class=\"custom-popover-box ui-tooltip\"></div>").html(content);

    $("body").append($popover);

    const offset = $(this).offset();
    const elementHeight = $(this).outerHeight();
    const popoverWidth = $popover.outerWidth();
    const popoverHeight = $popover.outerHeight();

    let topPosition = offset.top + elementHeight / 2 - popoverHeight / 2 - 50;
    const windowHeight = $(window).height();
    const maxTopPosition = windowHeight - popoverHeight - 10;

    if (topPosition + popoverHeight > windowHeight) {
      topPosition = maxTopPosition;
    }

    $popover.css({
      position: "absolute",
      top: topPosition,
      left: offset.left - popoverWidth - 20,
      zIndex: 9999
    });

    $currentPopover = $popover;
  });
}

function showAnalyticsConsentModal() {
  const overlay = document.getElementById("analytics-consent-overlay");

  if (overlay) {
    overlay.hidden = false;
  }
}

function hideAnalyticsConsentModal() {
  const overlay = document.getElementById("analytics-consent-overlay");

  if (overlay) {
    overlay.hidden = true;
  }
}

function updateAnalyticsConsentStatus() {
  const consent = localStorage.getItem("analyticsConsent");
  const status = document.getElementById("analytics-consent-status");

  if (!status) {
    return;
  }

  status.classList.remove(
    "analytics-consent-status--accepted",
    "analytics-consent-status--declined",
    "analytics-consent-status--unset"
  );

  if (consent === "accepted") {
    status.textContent = status.dataset.accepted;
    status.classList.add("analytics-consent-status--accepted");
  } else if (consent === "declined") {
    status.textContent = status.dataset.declined;
    status.classList.add("analytics-consent-status--declined");
  } else {
    status.textContent = status.dataset.unset;
    status.classList.add("analytics-consent-status--unset");
  }
}

function initAnalyticsConsent() {
  const analyticsConsent = localStorage.getItem("analyticsConsent");
  const acceptButton = document.getElementById("analytics-accept");
  const declineButton = document.getElementById("analytics-decline");

  updateAnalyticsConsentStatus();

  if (!analyticsConsent) {
    showAnalyticsConsentModal();
  }

  if (acceptButton) {
    acceptButton.addEventListener("click", () => {
      localStorage.setItem("analyticsConsent", "accepted");
      updateAnalyticsConsentStatus();
      window.location.reload();
    });
  }

  if (declineButton) {
    declineButton.addEventListener("click", () => {
      localStorage.setItem("analyticsConsent", "declined");
      updateAnalyticsConsentStatus();
      hideAnalyticsConsentModal();
    });
  }

  document.addEventListener("click", (event) => {
    const preferencesButton = event.target.closest("#analytics-preferences");

    if (preferencesButton) {
      showAnalyticsConsentModal();
    }
  });
}

function initBase() {
  initPopovers();
  initAnalyticsConsent();
}

document.addEventListener("DOMContentLoaded", initBase);

// Pour les onclick dans le HTML généré par DataTables
window.requestDdiJsHelpers = {"toggleCategories": toggleCategories};