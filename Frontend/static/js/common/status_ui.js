(function initUnderdogStatusUI(global) {
  function setStatus(el, msg, opts) {
    if (!el) return;
    const o = opts || {};
    const type = o.type || "";
    const baseClass = o.baseClass || "";
    const classMap = o.classMap || {};
    el.textContent = msg || "";
    if (baseClass) {
      const suffix = type && classMap[type] ? " " + classMap[type] : "";
      el.className = baseClass + suffix;
    }
  }

  function clearStatus(el, opts) {
    setStatus(el, "", opts);
  }

  global.UnderdogStatusUI = {
    setStatus,
    clearStatus,
  };
})(window);
