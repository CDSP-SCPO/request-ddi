(function () {
  const POLL_INTERVAL_MS = 5000;
  const STATUS_LABELS = {
    READY:      "En attente",
    RUNNING:    "En cours",
    SUCCESSFUL: "Succès",
    FAILED:     "Échec",
  };
  
  let pollTimer = null;
  let currentTasks = [];
  
  // ── DOM refs ──
  const taskListEl    = document.getElementById("taskList");
  const summaryEl     = document.getElementById("statusSummary");
  const lastUpdatedEl = document.getElementById("lastUpdated");
  const refreshEl     = document.getElementById("refreshIndicator");
  const modal         = document.getElementById("tracebackModal");
  const modalDoi      = document.getElementById("tracebackDoi");
  const modalContent  = document.getElementById("tracebackContent");
  const modalClose    = document.getElementById("tracebackClose");
  const modalBackdrop = document.getElementById("tracebackBackdrop");
  
  // ── Fetch ──
  function fetchStatus() {
    refreshEl.textContent = "↻ actualisation…";
    fetch(window.location.href, { headers: { Accept: "application/json" } })
      .then(r => r.json())
      .then(data => {
        currentTasks = data.tasks;
        render(data.tasks);
        scheduleNext(data.has_pending);
        refreshEl.textContent = "";
        lastUpdatedEl.textContent = "Dernière mise à jour : " + new Date().toLocaleTimeString("fr-FR");
      })
      .catch(() => {
        refreshEl.textContent = "⚠ erreur réseau";
        scheduleNext(true);
      });
  }
  
  function scheduleNext(hasPending) {
    clearTimeout(pollTimer);
    if (hasPending) {
      pollTimer = setTimeout(fetchStatus, POLL_INTERVAL_MS);
    }
  }
  
  // ── Render ──
  function render(tasks) {
    renderSummary(tasks);
    renderTasks(tasks);
  }
  
  function renderSummary(tasks) {
    const counts = { READY: 0, RUNNING: 0, SUCCESSFUL: 0, FAILED: 0 };
    tasks.forEach(t => { if (counts[t.status] !== undefined) counts[t.status]++; });
  
    const chips = [];
    chips.push(chipHtml("total", `${tasks.length} tâche${tasks.length !== 1 ? "s" : ""}`, false));
    if (counts.READY)      chips.push(chipHtml("pending",  `${counts.READY} en attente`));
    if (counts.RUNNING)    chips.push(chipHtml("running",  `${counts.RUNNING} en cours`));
    if (counts.SUCCESSFUL) chips.push(chipHtml("success",  `${counts.SUCCESSFUL} réussie${counts.SUCCESSFUL !== 1 ? "s" : ""}`));
    if (counts.FAILED)     chips.push(chipHtml("failed",   `${counts.FAILED} en erreur`));
  
    summaryEl.innerHTML = chips.join("");
  }
  
  function chipHtml(variant, label, dot = true) {
    return `<span class="summary-chip summary-chip--${variant}">${dot ? "<span class=\"summary-chip__dot\" aria-hidden=\"true\"></span>" : ""}${label}</span>`;
  }
  
  function renderTasks(tasks) {
    if (!tasks.length) {
      taskListEl.innerHTML = "<p class=\"task-list__empty\">Aucune tâche d'import dans les dernières 48&nbsp;h.</p>";
      return;
    }
    taskListEl.innerHTML = tasks.map(taskCardHtml).join("");
  
    taskListEl.querySelectorAll(".btn-error-detail").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.taskId;
        const task = currentTasks.find(t => t.id === id);
        if (task) openTraceback(task);
      });
    });
  
    taskListEl.querySelectorAll(".btn-retry").forEach(btn => {
      btn.addEventListener("click", () => retryTask(btn));
    });
  }
  
  function taskCardHtml(t) {
    const statusLow = t.status.toLowerCase();
    const doiLabel  = t.doi || "DOI inconnu";
    const doiClass  = t.doi ? "" : " task-card__doi--unknown";
  
    const icon  = iconSvg(t.status);
    const badge = `<span class="status-badge status-badge--${statusLow}">${STATUS_LABELS[t.status] || t.status}</span>`;
  
    const meta = [];
    if (t.enqueued_at) {
      meta.push(`<span class="task-card__meta-item">Soumise&nbsp;<strong>${fmtDatetime(t.enqueued_at)}</strong></span>`);
    }
    if (t.started_at && t.status === "RUNNING") {
      meta.push(`<span class="task-card__meta-item">Démarrée&nbsp;<strong>${fmtDatetime(t.started_at)}</strong></span>`);
    }
    if (t.duration_seconds !== null && t.duration_seconds !== undefined) {
      meta.push(`<span class="task-card__meta-item">Durée&nbsp;<strong>${fmtDuration(t.duration_seconds)}</strong></span>`);
    }
    if (t.num_records !== null && t.num_records !== undefined) {
      meta.push(`<span class="task-card__meta-item">Variables&nbsp;<strong>${t.num_records}</strong></span>`);
    }
    if (t.num_new_variables !== null && t.num_new_variables !== undefined) {
      meta.push(`<span class="task-card__meta-item">Nouvelles RV&nbsp;<strong>${t.num_new_variables}</strong></span>`);
    }
    if (t.num_new_bindings !== null && t.num_new_bindings !== undefined) {
      meta.push(`<span class="task-card__meta-item">Nouveaux bindings&nbsp;<strong>${t.num_new_bindings}</strong></span>`);
    }
    if (t.error_message || t.exception_class) {
      meta.push(`<span class="task-card__meta-item" style="color:#dc2626;">${t.error_message || t.exception_class}</span>`);
    }
  
    const progressBar = t.status === "RUNNING"
      ? "<div class=\"task-card__progress\" aria-hidden=\"true\"><div class=\"task-card__progress-bar\"></div></div>"
      : "";
  
    const errorBtn = (t.status === "FAILED" && t.traceback)
      ? `<button class="btn-error-detail" data-task-id="${t.id}" aria-label="Voir le détail de l'erreur">Voir l'erreur</button>`
      : "";
  
    const retryBtn = t.can_retry
      ? `<button class="btn-retry" data-task-id="${t.id}" aria-label="Relancer l'import">
             <span class="btn-retry__spinner" aria-hidden="true"></span>
             <span class="btn-retry__label">↺ Relancer</span>
           </button>`
      : "";
  
    return `
  <div class="task-card task-card--${statusLow}" role="listitem">
    <div class="task-card__icon task-card__icon--${statusLow}" aria-hidden="true">${icon}</div>
    <div class="task-card__body">
      <p class="task-card__doi${doiClass}" title="${doiLabel}">${doiLabel}</p>
      <div class="task-card__meta">${meta.join("")}</div>
    </div>
    <div class="task-card__right">
      ${badge}
      ${errorBtn}
      ${retryBtn}
    </div>
    ${progressBar}
  </div>`;
  }
  
  // ── Icônes SVG inline ──
  function iconSvg(status) {
    switch (status) {
      case "READY":
        return "<svg width=\"14\" height=\"14\" viewBox=\"0 0 14 14\" fill=\"none\"><circle cx=\"7\" cy=\"7\" r=\"5.5\" stroke=\"currentColor\" stroke-width=\"1.5\"/></svg>";
      case "RUNNING":
        return "<svg width=\"14\" height=\"14\" viewBox=\"0 0 14 14\" fill=\"none\"><path d=\"M7 2v5l3 2\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\"/><circle cx=\"7\" cy=\"7\" r=\"5.5\" stroke=\"currentColor\" stroke-width=\"1.5\"/></svg>";
      case "SUCCESSFUL":
        return "<svg width=\"14\" height=\"14\" viewBox=\"0 0 14 14\" fill=\"none\"><path d=\"M3 7l3 3 5-5\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/></svg>";
      case "FAILED":
        return "<svg width=\"14\" height=\"14\" viewBox=\"0 0 14 14\" fill=\"none\"><path d=\"M4 4l6 6M10 4l-6 6\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\"/></svg>";
      default:
        return "";
    }
  }
  
  // ── Retry ──
  function retryTask(btn) {
    const taskId = btn.dataset.taskId;
    btn.disabled = true;
    btn.classList.add("btn-retry--loading");
  
    fetch("/import/status/retry/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ task_id: taskId }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.status === "enqueued") {
          clearTimeout(pollTimer);
          fetchStatus();
        } else {
          btn.disabled = false;
          btn.classList.remove("btn-retry--loading");
          alert("Erreur : " + (data.error || "inconnue"));
        }
      })
      .catch(() => {
        btn.disabled = false;
        btn.classList.remove("btn-retry--loading");
        alert("Erreur réseau lors de la relance.");
      });
  }
  
  function getCsrfToken() {
    const cookie = document.cookie.split(";").find(c => c.trim().startsWith("csrftoken="));
    return cookie ? cookie.trim().split("=")[1] : "";
  }
  
  // ── Modal traceback ──
  function openTraceback(task) {
    modalDoi.textContent = task.doi || "DOI inconnu";
    modalContent.textContent = task.traceback || "(pas de traceback disponible)";
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    modalClose.focus();
  }
  
  function closeTraceback() {
    modal.hidden = true;
    document.body.style.overflow = "";
  }
  
  modalClose.addEventListener("click", closeTraceback);
  modalBackdrop.addEventListener("click", closeTraceback);
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeTraceback(); });
  
  // ── Formatage ──
  function fmtDatetime(iso) {
    const d = new Date(iso);
    return d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }
  
  function fmtDuration(s) {
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const rem = Math.round(s % 60);
    return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  }
  
  // ── Init ──
  fetchStatus();
})();