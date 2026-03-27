(function initUnderdogAuthNav(global) {
  const SESSION_STORAGE_KEY = "underdog_session_id";
  const PROVIDER_STORAGE_KEY = "underdog_provider";

  function safeGet(key) {
    try {
      return localStorage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  function safeSet(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (_) {}
  }

  function safeRemove(key) {
    try {
      localStorage.removeItem(key);
    } catch (_) {}
  }

  function readFromUrl(name) {
    try {
      return new URLSearchParams(document.location.search).get(name);
    } catch (_) {
      return null;
    }
  }

  function getSessionId() {
    return readFromUrl("session_id") || safeGet(SESSION_STORAGE_KEY) || null;
  }

  function getProvider() {
    return readFromUrl("provider") || safeGet(PROVIDER_STORAGE_KEY) || null;
  }

  function syncFromUrl() {
    const sid = readFromUrl("session_id");
    const provider = readFromUrl("provider");
    if (sid) safeSet(SESSION_STORAGE_KEY, sid);
    if (provider) safeSet(PROVIDER_STORAGE_KEY, provider);
    return { session_id: sid || null, provider: provider || null };
  }

  function buildUrlWithSession(path, opts) {
    const options = opts || {};
    const includeProvider = options.includeProvider !== false;
    const sid = getSessionId();
    const provider = includeProvider ? getProvider() : null;
    const params = new URLSearchParams();
    if (sid) params.set("session_id", sid);
    if (provider) params.set("provider", provider);
    const qs = params.toString();
    return qs ? path + "?" + qs : path;
  }

  async function logoutAndCleanup(apiBase, sid) {
    const sessionId = sid || getSessionId();
    if (sessionId) {
      try {
        await fetch(String(apiBase || "") + "/auth/clear-session-events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId }),
        });
      } catch (_) {}
    }
    safeRemove(SESSION_STORAGE_KEY);
    safeRemove(PROVIDER_STORAGE_KEY);
  }

  async function fetchMe(apiBase, sessionId) {
    const sid = sessionId || getSessionId();
    if (!sid) return { ok: false, guest: true, name: "", email: "" };
    try {
      const res = await fetch(
        String(apiBase || "") + "/auth/me?session_id=" + encodeURIComponent(sid)
      );
      const data = await res.json().catch(() => ({}));
      const ok = !!(res.ok && data && (data.ok === true || data.ok === "true"));
      return {
        ok,
        guest: !ok,
        name: ok ? (data.name || data.user?.name || "사용자") : "사용자",
        email: ok ? (data.email || data.user?.email || "-") : "-",
        status: res.status,
        raw: data,
      };
    } catch (_) {
      return { ok: false, guest: true, name: "사용자", email: "-", status: 0, raw: {} };
    }
  }

  async function loadUserIdentity(opts) {
    const o = opts || {};
    const result = await fetchMe(o.apiBase || "", o.sessionId || null);
    if (o.nameEl) o.nameEl.textContent = result.name || "사용자";
    if (o.emailEl) o.emailEl.textContent = result.email || "-";
    return result;
  }

  function bindUserDropdown(opts) {
    const o = opts || {};
    const apiBase = o.apiBase || "";
    const sessionId = o.sessionId || null;
    const soundRegEl = o.soundRegEl || null;
    const settingsEl = o.settingsEl || null;
    const logoutEl = o.logoutEl || null;
    const onBeforeLogout = typeof o.onBeforeLogout === "function" ? o.onBeforeLogout : null;
    const onAfterLogout = typeof o.onAfterLogout === "function" ? o.onAfterLogout : null;

    if (soundRegEl) {
      soundRegEl.addEventListener("click", (e) => {
        e.preventDefault();
        const url = buildUrlWithSession("/new-sound", { includeProvider: false });
        window.location.href = url;
      });
    }
    if (settingsEl) {
      settingsEl.addEventListener("click", (e) => {
        e.preventDefault();
        const url = buildUrlWithSession("/settings-page", { includeProvider: true });
        window.location.href = url;
      });
    }
    if (logoutEl) {
      logoutEl.addEventListener("click", async (e) => {
        e.preventDefault();
        if (onBeforeLogout) {
          try {
            await onBeforeLogout();
          } catch (_) {}
        }
        await logoutAndCleanup(apiBase, sessionId || getSessionId());
        if (onAfterLogout) {
          try {
            await onAfterLogout();
          } catch (_) {}
        }
        window.location.href = "/";
      });
    }
  }

  global.UnderdogAuthNav = {
    SESSION_STORAGE_KEY,
    PROVIDER_STORAGE_KEY,
    getSessionId,
    getProvider,
    syncFromUrl,
    buildUrlWithSession,
    logoutAndCleanup,
    bindUserDropdown,
    fetchMe,
    loadUserIdentity,
  };
})(window);
