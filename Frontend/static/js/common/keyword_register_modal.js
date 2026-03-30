/**
 * 사용자 드롭다운「키워드 등록」→ Bootstrap 모달. POST /user-keywords
 */
(function initKeywordRegisterModal(global) {
  const API_BASE =
    global.APP_CONFIG?.API_BASE ||
    (typeof location !== "undefined" &&
    location.origin &&
    !/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(location.origin)
      ? location.origin
      : "http://127.0.0.1:8000");

  const SESSION_STORAGE_KEY =
    global.UnderdogAuthNav?.SESSION_STORAGE_KEY || "underdog_session_id";

  let injected = false;
  let submitBound = false;

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

  async function ensureSessionId() {
    global.UnderdogAuthNav?.syncFromUrl?.();
    let sid = global.UnderdogAuthNav?.getSessionId?.() || null;
    if (sid) return String(sid);
    try {
      const res = await fetch(API_BASE + "/auth/guest", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      const id = data && (data.session_id ?? data.sessionId);
      if (!res.ok || !(data.ok === true || data.ok === "true") || !id) {
        throw new Error(data?.detail || res.statusText || "session_id 발급 실패");
      }
      sid = String(id);
      safeSet(SESSION_STORAGE_KEY, sid);
      const url = new URL(document.location.href);
      url.searchParams.set("session_id", sid);
      history.replaceState(null, "", url.toString());
      return sid;
    } catch (e) {
      console.error("ensureSessionId (keyword modal)", e);
      throw e;
    }
  }

  function showToast(title, body, tone) {
    global.UnderdogToastUI?.showToast?.({
      title,
      body,
      tone: tone || "danger",
      delayMs: 2600,
    });
  }

  function ensureModalDom() {
    if (injected) return;
    injected = true;
    document.body.insertAdjacentHTML(
      "beforeend",
      [
        '<div class="modal fade" id="userKeywordRegisterModal" tabindex="-1" aria-labelledby="userKeywordRegisterModalLabel" aria-hidden="true" inert>',
        '  <div class="modal-dialog modal-dialog-centered">',
        '    <div class="modal-content">',
        '      <div class="modal-header">',
        '        <h5 class="modal-title" id="userKeywordRegisterModalLabel">키워드 등록</h5>',
        '        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>',
        '      </div>',
        '      <div class="modal-body">',
        '        <div class="mb-3">',
        '          <label for="userKeywordRegisterPhrase" class="form-label fw-semibold">키워드</label>',
        '          <input type="text" class="form-control" id="userKeywordRegisterPhrase" maxlength="255" placeholder="감지할 말(문구)을 입력하세요" autocomplete="off">',
        '        </div>',
        '        <div class="mb-0">',
        '          <label for="userKeywordRegisterType" class="form-label fw-semibold">소리 알림 분류</label>',
        '          <select id="userKeywordRegisterType" class="form-select">',
        '            <option value="">선택</option>',
        '            <option value="danger">위험</option>',
        '            <option value="caution">경고</option>',
        '            <option value="alert">생활알림</option>',
        '          </select>',
        '        </div>',
        '      </div>',
        '      <div class="modal-footer">',
        '        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>',
        '        <button type="button" class="btn btn-outline-primary" id="userKeywordRegisterSubmit">등록</button>',
        '      </div>',
        '    </div>',
        '  </div>',
        "</div>",
      ].join("")
    );

    const modalEl = document.getElementById("userKeywordRegisterModal");
    if (modalEl) {
      modalEl.addEventListener("shown.bs.modal", () => {
        modalEl.removeAttribute("inert");
        modalEl.setAttribute("aria-hidden", "false");
      });
      modalEl.addEventListener("hidden.bs.modal", () => {
        modalEl.setAttribute("inert", "");
        modalEl.setAttribute("aria-hidden", "true");
      });
    }

    if (!submitBound) {
      submitBound = true;
      document.getElementById("userKeywordRegisterSubmit")?.addEventListener("click", async () => {
        const phraseEl = document.getElementById("userKeywordRegisterPhrase");
        const typeEl = document.getElementById("userKeywordRegisterType");
        const phrase = (phraseEl?.value || "").trim();
        const eventType = (typeEl?.value || "").trim();
        if (!phrase) {
          showToast("입력 확인", "키워드를 입력해 주세요.", "warning");
          return;
        }
        if (!eventType) {
          showToast("입력 확인", "소리 알림 분류를 선택해 주세요.", "warning");
          return;
        }
        if (!window.confirm("등록 하시겠습니까")) {
          return;
        }
        const btn = document.getElementById("userKeywordRegisterSubmit");
        try {
          const sid = await ensureSessionId();
          if (btn) btn.disabled = true;
          const res = await fetch(
            API_BASE + "/user-keywords?session_id=" + encodeURIComponent(sid),
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ phrase, event_type: eventType }),
            }
          );
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.ok) {
            const detail = data.detail;
            const msg =
              typeof detail === "string"
                ? detail
                : Array.isArray(detail) && detail[0]?.msg
                  ? detail[0].msg
                  : "등록에 실패했습니다.";
            showToast("등록 실패", msg, "danger");
            return;
          }
          showToast("등록 완료", `"${data.data?.phrase || phrase}" 키워드가 등록되었습니다.`, "success");
          const inst = global.bootstrap?.Modal?.getInstance(modalEl);
          if (inst) inst.hide();
          if (phraseEl) phraseEl.value = "";
          if (typeEl) typeEl.selectedIndex = 0;
        } catch (e) {
          console.error(e);
          showToast("연결 실패", "세션을 만들 수 없거나 서버에 연결할 수 없습니다.", "danger");
        } finally {
          if (btn) btn.disabled = false;
        }
      });
    }
  }

  function open() {
    if (typeof global.bootstrap === "undefined" || !global.bootstrap.Modal) {
      showToast("오류", "모달을 열 수 없습니다. 페이지를 새로고침 해 주세요.", "danger");
      return;
    }
    ensureModalDom();
    const phraseEl = document.getElementById("userKeywordRegisterPhrase");
    const typeEl = document.getElementById("userKeywordRegisterType");
    if (phraseEl) phraseEl.value = "";
    if (typeEl) typeEl.selectedIndex = 0;
    const el = document.getElementById("userKeywordRegisterModal");
    if (!el) return;
    global.bootstrap.Modal.getOrCreateInstance(el).show();
  }

  global.UnderdogKeywordRegisterModal = { open };
})(window);
