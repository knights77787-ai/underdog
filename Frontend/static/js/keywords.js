const API_BASE =
  window.APP_CONFIG?.API_BASE ||
  (typeof location !== "undefined" &&
  location.origin &&
  !/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(location.origin)
    ? location.origin
    : "http://127.0.0.1:8000");
const SESSION_STORAGE_KEY =
  window.UnderdogAuthNav?.SESSION_STORAGE_KEY || "underdog_session_id";
const PROVIDER_STORAGE_KEY =
  window.UnderdogAuthNav?.PROVIDER_STORAGE_KEY || "underdog_provider";

let SESSION_ID = (function () {
  window.UnderdogAuthNav?.syncFromUrl?.();
  return window.UnderdogAuthNav?.getSessionId?.() || null;
})();

async function ensureSessionId() {
  if (SESSION_ID) return SESSION_ID;
  try {
    const res = await fetch(API_BASE + "/auth/guest", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    const sid = data && (data.session_id ?? data.sessionId);
    if (!res.ok || !(data.ok === true || data.ok === "true") || !sid) {
      throw new Error(data?.detail || res.statusText || "session_id 발급 실패");
    }
    SESSION_ID = String(sid);
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, SESSION_ID);
    } catch (_) {}
    const url = new URL(document.location.href);
    url.searchParams.set("session_id", SESSION_ID);
    history.replaceState(null, "", url.toString());
  } catch (e) {
    console.error("ensureSessionId failed", e);
    setStatus("세션을 만들 수 없습니다. 새로고침 후 다시 시도해 주세요.", "err");
    throw e;
  }
  return SESSION_ID;
}

function getProvider() {
  return (window.UnderdogAuthNav?.getProvider?.() || "").toLowerCase();
}

const kwPhrase = document.getElementById("kwPhrase");
const kwCategory = document.getElementById("kwCategory");
const kwEditingId = document.getElementById("kwEditingId");
const btnKwSubmit = document.getElementById("btnKwSubmit");
const btnKwCancelEdit = document.getElementById("btnKwCancelEdit");
const kwStatusEl = document.getElementById("kwStatus");
const kwListEl = document.getElementById("kwList");
const kwListStatusEl = document.getElementById("kwListStatus");

const userDropdownWrap = document.getElementById("userDropdownWrap");
const btnUserIcon = document.getElementById("btnUserIcon");
const userDropdownName = document.getElementById("userDropdownName");
const userDropdownEmail = document.getElementById("userDropdownEmail");
const userDropdownSoundReg = document.getElementById("userDropdownSoundReg");
const userDropdownKeywordReg = document.getElementById("userDropdownKeywordReg");
const userDropdownSettings = document.getElementById("userDropdownSettings");
const userDropdownLogout = document.getElementById("userDropdownLogout");

/** 목록 탭에서 편집 시 안전하게 phrase/type 참조 */
let _kwListCache = [];

function setStatus(msg, type = "") {
  window.UnderdogStatusUI?.setStatus?.(kwStatusEl, msg, {
    type,
    baseClass: "status small mb-3",
    classMap: { ok: "ok", err: "err" },
  });
}

function clearStatus() {
  window.UnderdogStatusUI?.clearStatus?.(kwStatusEl, {
    baseClass: "status small mb-3",
    classMap: { ok: "ok", err: "err" },
  });
}

function showToast(title, body, tone) {
  window.UnderdogToastUI?.showToast?.({
    title,
    body,
    tone: tone || "danger",
    delayMs: 2600,
  });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

function eventTypeDisplay(eventType) {
  const map = { danger: "위험", caution: "경고", alert: "생활알림" };
  return map[eventType] || eventType || "";
}

function resetEditState() {
  if (kwEditingId) kwEditingId.value = "";
  if (btnKwSubmit) btnKwSubmit.textContent = "등록";
  if (btnKwCancelEdit) btnKwCancelEdit.classList.add("d-none");
}

function showEditState() {
  if (btnKwSubmit) btnKwSubmit.textContent = "수정 저장";
  if (btnKwCancelEdit) btnKwCancelEdit.classList.remove("d-none");
}

function switchToRegisterTab() {
  const tabBtn = document.getElementById("kw-register-tab");
  if (tabBtn && window.bootstrap?.Tab) {
    try {
      new bootstrap.Tab(tabBtn).show();
    } catch (_) {}
  }
}

function switchToListTab() {
  const tabBtn = document.getElementById("kw-list-tab");
  if (tabBtn && window.bootstrap?.Tab) {
    try {
      new bootstrap.Tab(tabBtn).show();
    } catch (_) {}
  }
}

function formatYmd(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toISOString().slice(0, 10);
}

function renderKeywordList(list) {
  if (!kwListEl || !kwListStatusEl) return;
  _kwListCache = Array.isArray(list) ? list.slice() : [];
  if (!Array.isArray(list) || list.length === 0) {
    kwListStatusEl.textContent = "등록된 키워드가 없습니다.";
    kwListEl.innerHTML = "";
    return;
  }
  kwListStatusEl.textContent = `총 ${list.length}건`;
  kwListEl.innerHTML = list
    .map((r) => {
      const badgeClass =
        r.event_type === "danger"
          ? "danger"
          : r.event_type === "caution"
            ? "caution"
            : "daily";
      const dateStr = formatYmd(r.created_at);
      const dateLine = dateStr ? ` · 등록: ${escapeHtml(dateStr)}` : "";
      return `
      <div class="sound-row" data-id="${r.user_custom_keyword_id}">
        <div class="sound-left">
          <div class="sound-title-line">
            <span class="sound-badge ${badgeClass}">${escapeHtml(eventTypeDisplay(r.event_type))}</span>
            <span class="sound-name">${escapeHtml(r.phrase)}</span>
          </div>
          <div class="sound-date text-muted small">${escapeHtml(eventTypeDisplay(r.event_type))}${dateLine}</div>
        </div>
        <div class="sound-right">
          <button type="button" class="icon-btn edit-kw-btn" data-id="${r.user_custom_keyword_id}"
            aria-label="편집" title="편집" tabindex="0">
            <i class="bi bi-pencil-fill"></i>
          </button>
          <button type="button" class="icon-btn delete-kw-btn" data-id="${r.user_custom_keyword_id}"
            aria-label="삭제" title="삭제" tabindex="0">
            <i class="bi bi-trash-fill"></i>
          </button>
        </div>
      </div>`;
    })
    .join("");
}

async function loadKeywordList() {
  if (!kwListEl || !kwListStatusEl) return;
  if (!SESSION_ID) {
    try {
      await ensureSessionId();
    } catch (_) {
      return;
    }
  }
  kwListStatusEl.textContent = "불러오는 중…";
  kwListEl.innerHTML = "";
  try {
    const url =
      API_BASE + "/user-keywords?session_id=" + encodeURIComponent(SESSION_ID);
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok || !Array.isArray(data.data)) {
      kwListStatusEl.textContent = "목록을 불러오지 못했습니다.";
      return;
    }
    renderKeywordList(data.data);
  } catch (e) {
    console.error(e);
    kwListStatusEl.textContent = "서버에 연결할 수 없습니다.";
  }
}

document.getElementById("kw-list-tab")?.addEventListener("shown.bs.tab", () => {
  loadKeywordList();
});

btnKwCancelEdit?.addEventListener("click", () => {
  if (kwPhrase) kwPhrase.value = "";
  if (kwCategory) kwCategory.value = "";
  clearStatus();
  resetEditState();
});

kwListEl?.addEventListener("click", (e) => {
  const editBtn = e.target.closest(".edit-kw-btn");
  const delBtn = e.target.closest(".delete-kw-btn");

  if (editBtn) {
    const id = editBtn.dataset.id;
    if (!id) return;
    const r = _kwListCache.find((x) => String(x.user_custom_keyword_id) === String(id));
    if (!r) return;
    const phrase = r.phrase || "";
    const eventType = r.event_type || "";
    if (kwEditingId) kwEditingId.value = id;
    if (kwPhrase) kwPhrase.value = phrase;
    if (kwCategory) kwCategory.value = eventType;
    showEditState();
    clearStatus();
    switchToRegisterTab();
    kwPhrase?.focus();
    return;
  }

  if (delBtn) {
    const id = delBtn.dataset.id;
    if (!id) return;
    if (!window.confirm("정말 삭제하시겠습니까?")) return;
    (async () => {
      try {
        if (!SESSION_ID) await ensureSessionId();
        const url =
          API_BASE +
          "/user-keywords/" +
          encodeURIComponent(id) +
          "?session_id=" +
          encodeURIComponent(SESSION_ID);
        const res = await fetch(url, { method: "DELETE" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
          const detail = data.detail;
          const msg = typeof detail === "string" ? detail : "삭제에 실패했습니다.";
          showToast("삭제 실패", msg, "danger");
          await loadKeywordList();
          return;
        }
        showToast("삭제됨", "키워드가 삭제되었습니다.", "success");
        await loadKeywordList();
      } catch (err) {
        console.error(err);
        showToast("오류", "삭제 요청 중 오류가 발생했습니다.", "danger");
      }
    })();
  }
});

btnKwSubmit?.addEventListener("click", async () => {
  clearStatus();
  const phrase = (kwPhrase?.value || "").trim();
  const eventType = (kwCategory?.value || "").trim();
  const editing = (kwEditingId?.value || "").trim();

  if (!phrase) {
    setStatus("키워드를 입력해 주세요.", "err");
    return;
  }
  if (!eventType) {
    setStatus("소리 알림 분류를 선택해 주세요.", "err");
    return;
  }

  const isEdit = !!editing;
  if (!window.confirm(isEdit ? "수정 하시겠습니까?" : "등록 하시겠습니까?")) {
    return;
  }

  try {
    if (!SESSION_ID) await ensureSessionId();
  } catch (_) {
    return;
  }

  btnKwSubmit.disabled = true;
  try {
    if (isEdit) {
      const url =
        API_BASE +
        "/user-keywords/" +
        encodeURIComponent(editing) +
        "?session_id=" +
        encodeURIComponent(SESSION_ID);
      const res = await fetch(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase, event_type: eventType }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        const detail = data.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail) && detail[0]?.msg
              ? detail[0].msg
              : "수정에 실패했습니다.";
        setStatus(msg, "err");
        showToast("수정 실패", msg, "danger");
        return;
      }
      setStatus(`"${data.data?.phrase || phrase}" 로 수정되었습니다.`, "ok");
      showToast("수정 완료", `"${data.data?.phrase || phrase}" 키워드를 저장했습니다.`, "success");
    } else {
      const url =
        API_BASE + "/user-keywords?session_id=" + encodeURIComponent(SESSION_ID);
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase, event_type: eventType }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        const detail = data.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail) && detail[0]?.msg
              ? detail[0].msg
              : "등록에 실패했습니다.";
        setStatus(msg, "err");
        showToast("등록 실패", msg, "danger");
        return;
      }
      setStatus(`"${data.data?.phrase || phrase}" 키워드가 등록되었습니다.`, "ok");
      showToast("등록 완료", `"${data.data?.phrase || phrase}" 키워드를 등록했습니다.`, "success");
    }

    if (kwPhrase) kwPhrase.value = "";
    if (kwCategory) kwCategory.value = "";
    resetEditState();
    await loadKeywordList();
    switchToListTab();
  } catch (err) {
    console.error(err);
    setStatus("서버에 연결할 수 없습니다.", "err");
    showToast("연결 실패", "네트워크 또는 서버를 확인해 주세요.", "danger");
  } finally {
    btnKwSubmit.disabled = false;
  }
});

async function updateUserSection() {
  if (!userDropdownWrap) return;
  const urlSessionId = new URLSearchParams(document.location.search).get("session_id");
  const provider = getProvider();
  const showDropdown =
    urlSessionId && (provider === "google" || provider === "kakao");
  if (!showDropdown) {
    userDropdownWrap.classList.add("d-none");
    return;
  }
  userDropdownWrap.classList.remove("d-none");
  await window.UnderdogAuthNav?.loadUserIdentity?.({
    apiBase: API_BASE,
    sessionId: urlSessionId || SESSION_ID,
    nameEl: userDropdownName,
    emailEl: userDropdownEmail,
  });
}

function setupUserDropdown() {
  if (!userDropdownWrap || !btnUserIcon || !userDropdownSoundReg || !userDropdownLogout) return;
  window.UnderdogAuthNav?.bindUserDropdown?.({
    apiBase: API_BASE,
    sessionId: SESSION_ID,
    soundRegEl: userDropdownSoundReg,
    keywordRegEl: userDropdownKeywordReg,
    settingsEl: userDropdownSettings,
    logoutEl: userDropdownLogout,
  });
}

ensureSessionId()
  .then(() => {
    updateUserSection();
    setupUserDropdown();
    loadKeywordList();
  })
  .catch(() => {});
