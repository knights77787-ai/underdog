(function initUnderdogToastUI(global) {
  function ensureContainer(containerId) {
    const id = containerId || "toastContainer";
    let container = document.getElementById(id);
    if (container) return container;
    container = document.createElement("div");
    container.id = id;
    container.className = "toast-container position-fixed top-0 end-0 p-3";
    document.body.appendChild(container);
    return container;
  }

  function showToast(opts) {
    const o = opts || {};
    if (typeof bootstrap === "undefined" || !bootstrap.Toast) return;
    const container = ensureContainer(o.containerId);
    const tone = (o.tone || "").toString().toLowerCase();
    const legacyDanger = o.danger !== false;
    const variantByTone = {
      danger: "danger",
      error: "danger",
      warning: "warning",
      caution: "warning",
      success: "success",
      info: "primary",
      primary: "primary",
      dark: "dark",
    };
    const variant = variantByTone[tone] || (legacyDanger ? "danger" : "primary");
    const title = o.title || "";
    const body = o.body || "";
    const delay = Number.isFinite(o.delayMs) ? o.delayMs : 2200;

    const wrap = document.createElement("div");
    wrap.className = "toast text-bg-" + variant + " border-0";
    wrap.role = "alert";
    wrap.ariaLive = "assertive";
    wrap.ariaAtomic = "true";
    wrap.innerHTML = `
      <div class="d-flex">
        <div class="toast-body"><strong>${title}</strong><br>${body}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="닫기"></button>
      </div>
    `;
    container.appendChild(wrap);

    const t = new bootstrap.Toast(wrap, { delay });
    wrap.addEventListener("hidden.bs.toast", () => wrap.remove());
    t.show();
  }

  global.UnderdogToastUI = {
    showToast,
  };
})(window);
