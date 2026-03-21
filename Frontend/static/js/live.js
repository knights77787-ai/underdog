// Frontend/static/js/live.js
// =======================
// 0) 공용 unhandledrejection 가드 (초기 로드 초반부터 등록)
// =======================
// 브라우저 확장(core.js 등) · 결제/기부 위젯이 던지는 payload 관련 Promise rejection을 삼킨다.
// capture: true 로 다른 스크립트보다 먼저 처리해 콘솔 Uncaught 노이즈를 줄인다.
(() => {
  try {
    if (window.__underdogUnhandledRejectionPayloadGuardInstalled) return;
    window.__underdogUnhandledRejectionPayloadGuardInstalled = true;

    function rejectionToMessage(reason) {
      if (reason == null) return "";
      if (typeof reason === "string") return reason;
      if (reason instanceof Error) return reason.message || String(reason);
      try {
        const m = reason && reason.message;
        if (typeof m === "string") return m;
        return String(reason);
      } catch (_) {
        return "";
      }
    }

    function stackOf(reason) {
      return reason instanceof Error && reason.stack ? String(reason.stack) : "";
    }

    function shouldSilenceExternalRejection(msg, reason) {
      if (!msg || typeof msg !== "string") return false;
      const s = msg.toLowerCase();
      const st = stackOf(reason).toLowerCase();
      const extStack =
        st.includes("chrome-extension://") ||
        st.includes("moz-extension://") ||
        /\bcore\.js\b/.test(st);
      const payloadish =
        s.includes("payload") ||
        (s.includes("undefined") && (s.includes("read") || s.includes("읽을")));
      if (extStack && payloadish) return true;
      return (
        s.includes("payload") ||
        s.includes("reading 'payload'") ||
        s.includes('reading "payload"') ||
        (s.includes("cannot read properties") && s.includes("payload")) ||
        (s.includes("cannot read") && s.includes("payload")) ||
        s.includes("checkout popup") ||
        s.includes("checkoutpopup") ||
        s.includes("no checkout popup config") ||
        s.includes("gf config") ||
        s.includes("no gf config") ||
        s.includes("checkoutpouploggerenabled")
      );
    }

    window.addEventListener(
      "unhandledrejection",
      (ev) => {
        const msg = rejectionToMessage(ev && ev.reason);
        if (!shouldSilenceExternalRejection(msg, ev && ev.reason)) return;
        try {
          ev.preventDefault();
          ev.stopImmediatePropagation();
        } catch (_) {}
      },
      { capture: true }
    );
  } catch (_) {}
})();
// =======================
// 0) 서버 주소 · 세션 (백엔드 연동: join 시 사용)
// =======================
// 배포(HTTPS)에서는 config 미적재 시에도 현재 오리진 사용. 로컬만 127.0.0.1 폴백
function getDefaultApiBase() {
  if (window.APP_CONFIG?.API_BASE) return window.APP_CONFIG.API_BASE;
  if (typeof location !== "undefined" && location.origin && !/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(location.origin))
    return location.origin;
  return "http://127.0.0.1:8000";
}
const API_BASE = getDefaultApiBase();
// config 미적재 시에도 HTTPS면 wss 사용 (Mixed Content 방지)
function getDefaultWsUrl() {
  if (window.APP_CONFIG?.WS_URL) return window.APP_CONFIG.WS_URL;
  if (typeof location !== "undefined" && location.host) {
    const p = location.protocol === "https:" ? "wss" : "ws";
    return p + "://" + location.host + "/ws";
  }
  return "ws://127.0.0.1:8000/ws";
}
const WS_URL = getDefaultWsUrl();
const SESSION_STORAGE_KEY = "underdog_session_id";
const PROVIDER_STORAGE_KEY = "underdog_provider";
let SESSION_ID = (function () {
  const params = new URLSearchParams(document.location.search);
  const fromUrl = params.get("session_id");
  const providerFromUrl = params.get("provider");
  if (providerFromUrl) {
    try {
      localStorage.setItem(PROVIDER_STORAGE_KEY, providerFromUrl);
    } catch (_) {}
  }
  if (fromUrl) return fromUrl;
  try {
    return localStorage.getItem(SESSION_STORAGE_KEY) || null;
  } catch (_) {
    return null;
  }
})();
if (SESSION_ID) {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, SESSION_ID);
  } catch (_) {}
  try {
    window.UnderdogApp?.setSessionId(SESSION_ID);
  } catch (_) {}
}
// 피드백 대상: 가장 최근 수신한 alert 정보
let lastAlertEventInfo = null;
// 테스트: 전체 자막(caption_all) 상태
let captionAllEnabled = false;

// 사용자 정보(/auth/me) 조회 중복 호출 방지:
// 로그인 상태(provider)는 남아있는데 세션이 게스트로 돌아가는 케이스에서
// 404가 무한 반복될 수 있어서, 단일 in-flight + 최소 간격(쿨다운)을 둡니다.
let userInfoInFlight = false;
let userInfoLastFetchTs = 0;
let userInfoStopUntilTs = 0;

// 마이크 → audio_chunk 전송
let micStream = null;
let audioContext = null;
let audioProcessor = null;
let audioWorkletNode = null;
let audioSource = null;
let audioBuffer = [];
let rawBuffer = [];
let currentSr = 0;
const TARGET_SR = 16000;
// 청크 0.5~3초 범위 지원: 8000(0.5s) / 16000(1s) / 32000(2s) / 48000(3s) 등
const CHUNK_SAMPLES = 32000; // 2 sec at 16kHz (기본값, 변경 시 8000~48000)
const WORKLET_URL = (window.location.origin || "http://127.0.0.1:8000") + "/static/js/audio-processor-worklet.js";

// =======================
// 1) DOM
// =======================

const heroCard = document.getElementById("heroCard");
const heroBadge = document.getElementById("heroBadge");
const heroMatchedPhrase = document.getElementById("heroMatchedPhrase");
const heroTitle = document.getElementById("heroTitle");
const heroDesc  = document.getElementById("heroDesc");
const btnFeedbackYes = document.getElementById("btnFeedbackYes");
const btnFeedbackNo  = document.getElementById("btnFeedbackNo");

const logTbody = document.getElementById("logTbody");
const logSection = document.getElementById("logSection");
const guestCtaSection = document.getElementById("guestCtaSection");

const micTitle = document.getElementById("micTitle");
const micDesc  = document.getElementById("micDesc");
const btnMic   = document.getElementById("btnMic");
const btnVibrateTest = document.getElementById("btnVibrateTest");
const micPermissionModal = document.getElementById("micPermissionModal");
const micPermissionConfirm = document.getElementById("micPermissionConfirm");
const micStopModal = document.getElementById("micStopModal");
const micStopConfirm = document.getElementById("micStopConfirm");

// 모달 접근성: 표시 시 inert 제거·aria-hidden=false, 숨김 시 inert 설정 (Blocked aria-hidden 경고 방지)
function setupModalA11y(modalEl) {
  if (!modalEl) return;
  modalEl.addEventListener("shown.bs.modal", () => {
    modalEl.removeAttribute("inert");
    modalEl.setAttribute("aria-hidden", "false");
  });
  modalEl.addEventListener("hidden.bs.modal", () => {
    const ae = document.activeElement;
    if (ae && typeof ae.blur === "function" && modalEl.contains(ae)) {
      try {
        ae.blur();
      } catch (_) {}
    }
    modalEl.setAttribute("inert", "");
    modalEl.setAttribute("aria-hidden", "true");
  });
}
setupModalA11y(micPermissionModal);
setupModalA11y(micStopModal);

const captionBox = document.getElementById("captionBox");
const btnCaptionTestAll = document.getElementById("btnCaptionTestAll");

const toastContainer = document.getElementById("toastContainer");
const userDropdownWrap = document.getElementById("userDropdownWrap");
const btnUserIcon = document.getElementById("btnUserIcon");
const userDropdownName = document.getElementById("userDropdownName");
const userDropdownEmail = document.getElementById("userDropdownEmail");
const userDropdownSoundReg = document.getElementById("userDropdownSoundReg");
const userDropdownLogout = document.getElementById("userDropdownLogout");

// =======================
// 2) Helpers
// =======================
// 마이크 스트림 존재 여부 + 트랙 활성 상태로 마이크 켜짐 판단 (브라우저 탭 아이콘과 동기화)
function isMicOn() {
  if (!micStream) return false;
  try {
    const tracks = micStream.getAudioTracks();
    if (tracks.length === 0) return true; // 스트림 존재 시 켜짐으로 간주
    return tracks.some((t) => t.readyState === "live");
  } catch {
    return true; // 예외 시 스트림만 있으면 켜짐
  }
}

function updateMicStatusUI() {
  const on = isMicOn();
  const label = on ? "마이크 켜짐" : "마이크 끔";
  const iconClass = "mic-status-icon bi " + (on ? "bi-mic-fill" : "bi-mic-mute-fill");
  const baseClass = "mic-status-indicator " + (on ? "mic-on" : "mic-off");

  const micCard = document.getElementById("micStatusCard");
  if (micCard) {
    const icon = micCard.querySelector(".mic-status-icon");
    if (icon) icon.className = iconClass;
    micCard.className = baseClass + " mic-status-card mb-2";
    micCard.title = label;
    micCard.setAttribute("aria-label", label);
  }

  if (btnMic) btnMic.textContent = on ? "마이크 중단" : "마이크 실행";
}

function nowTS() {
  return new Date().toTimeString().slice(0, 8);
}

function formatTs(tsMs) {
  if (tsMs == null) return nowTS();
  const d = new Date(Number(tsMs));
  return isNaN(d.getTime()) ? nowTS() : d.toTimeString().slice(0, 8);
}

function isDanger(text) {
  return ["불", "도와", "살려", "화재", "위험"].some(k => (text || "").includes(k));
}

function appendCaption(text, danger=false) {
  const div = document.createElement("div");
  div.className = "caption-line" + (danger ? " danger" : "");
  div.textContent = `[${nowTS()}] ${text}`;
  captionBox.appendChild(div);
  captionBox.scrollTop = captionBox.scrollHeight;

  while (captionBox.children.length > 60) {
    captionBox.removeChild(captionBox.firstChild);
  }
}

function updateCaptionTestButtonUI(enabled) {
  captionAllEnabled = !!enabled;
  if (!btnCaptionTestAll) return;
  if (!SESSION_ID) {
    btnCaptionTestAll.disabled = true;
    btnCaptionTestAll.textContent = "테스트: 전체 자막 OFF";
    btnCaptionTestAll.className = "btn btn-sm btn-outline-secondary";
    return;
  }
  btnCaptionTestAll.disabled = false;
  btnCaptionTestAll.textContent = captionAllEnabled ? "테스트: 전체 자막 ON" : "테스트: 전체 자막 OFF";
  btnCaptionTestAll.className = "btn btn-sm " + (captionAllEnabled ? "btn-outline-success" : "btn-outline-secondary");
}

const LOCAL_LOG_KEY = "underdog_event_log";
const MAX_LOCAL_LOGS = 30;
/** 알림 로그 행(tr) → 피드백용 메타 (event_id 등) */
const logRowAlertMeta = new WeakMap();

function saveToLocalLog(entry) {
  try {
    let list = [];
    const raw = localStorage.getItem(LOCAL_LOG_KEY);
    if (raw) {
      try {
        list = JSON.parse(raw);
      } catch (_) {}
    }
    list.unshift(entry);
    if (list.length > MAX_LOCAL_LOGS) list = list.slice(0, MAX_LOCAL_LOGS);
    localStorage.setItem(LOCAL_LOG_KEY, JSON.stringify(list));
  } catch (_) {}
}

function clearLogRowSelection() {
  if (!logTbody) return;
  logTbody.querySelectorAll("tr.table-active").forEach((r) => r.classList.remove("table-active"));
}

function selectLogRowForFeedback(tr) {
  const meta = logRowAlertMeta.get(tr);
  if (!meta || meta.event_id == null) {
    showToast("피드백", "이 기록은 서버 이벤트와 연결되지 않아 피드백을 보낼 수 없어요.", true);
    return;
  }
  clearLogRowSelection();
  tr.classList.add("table-active");
  lastAlertEventInfo = {
    event_id: meta.event_id,
    text: meta.text,
    keyword: meta.keyword,
    event_type: meta.event_type,
    ts_ms: meta.ts_ms,
    subgroup: meta.subgroup || "",
    matched_phrase: meta.matched_phrase || "",
  };
  const titleSub = heroTitleSubgroupFromParts(meta.subgroup, meta.keyword);
  setHeroAlert(
    buildHeroAlertDesc(meta.keyword, meta.text || "", titleSub),
    meta.event_type,
    titleSub,
    meta.matched_phrase || ""
  );
}

function setupLogTableFeedbackClicks() {
  if (!logTbody) return;
  logTbody.addEventListener("click", (e) => {
    const tr = e.target && e.target.closest ? e.target.closest("tr.log-row-clickable") : null;
    if (!tr || !logTbody.contains(tr)) return;
    selectLogRowForFeedback(tr);
  });
  logTbody.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const tr = e.target && e.target.tagName === "TR" && e.target.classList.contains("log-row-clickable")
      ? e.target
      : null;
    if (!tr || !logTbody.contains(tr)) return;
    e.preventDefault();
    selectLogRowForFeedback(tr);
  });
}

function appendLogRow({ ts, ts_ms, type, text, score, event_type, keyword, event_id, subgroup, matched_phrase }) {
  const tr = document.createElement("tr");
  const kind = (type === "alert")
    ? (event_type === "danger" ? "위험/경고" : event_type === "caution" ? "주의" : "생활알림")
    : "자막";
  const prob = (typeof score === "number") ? `${Math.round(score * 100)}%` : "-";
  const extra = keyword ? ` [${keyword}]` : "";
  const timeStr = formatTs(ts_ms ?? ts);
  const mp = (matched_phrase || "").toString().trim();
  const matchHint = mp ? ` · 매칭:「${mp}」` : "";
  const contentLine = `${text || ""}${extra}${matchHint}${event_type ? ` (${event_type})` : ""}`;

  const tdTime = document.createElement("td");
  tdTime.textContent = timeStr;
  const tdKind = document.createElement("td");
  tdKind.textContent = kind;
  const tdContent = document.createElement("td");
  tdContent.textContent = contentLine;
  const tdProb = document.createElement("td");
  tdProb.textContent = prob;
  tr.append(tdTime, tdKind, tdContent, tdProb);

  if (type === "alert" && event_id != null) {
    tr.classList.add("log-row-clickable");
    tr.setAttribute("role", "button");
    tr.tabIndex = 0;
    tr.title = "클릭하면 이 알림에 피드백할 수 있어요";
    logRowAlertMeta.set(tr, {
      event_id,
      text: text || "",
      keyword: keyword || "",
      subgroup: (subgroup || "").toString(),
      matched_phrase: (matched_phrase || "").toString(),
      event_type: event_type || "danger",
      ts_ms: ts_ms ?? ts ?? Date.now(),
    });
  } else if (type === "alert") {
    tr.title = "이 기록은 서버 이벤트 ID가 없어 피드백을 보낼 수 없습니다";
  }

  logTbody.prepend(tr);

  while (logTbody.children.length > 30) {
    logTbody.removeChild(logTbody.lastChild);
  }

  saveToLocalLog({
    ts_ms: ts_ms ?? ts ?? Date.now(),
    type,
    text,
    category: event_type || (type === "alert" ? "alert" : "caption"),
    keyword: keyword || null,
    subgroup: subgroup || null,
    matched_phrase: matched_phrase || null,
    score: typeof score === "number" ? score : null,
    event_id: event_id != null ? event_id : undefined,
  });
}

// 세션 확보 + WebSocket 연결 (세션 없으면 /auth/guest 호출)
async function ensureSessionAndConnect() {
  if (!SESSION_ID) {
    try {
        const res = await fetch(API_BASE + "/auth/guest", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      const sid = data && (data.session_id ?? data.sessionId);
      if (!data || !(data.ok === true || data.ok === "true") || !sid) {
        const msg = (data && data.detail) || (res.ok ? "세션 ID를 받지 못했습니다." : "서버 오류 " + res.status);
        showToast("세션 발급 실패", msg, true);
        return false;
      }
      SESSION_ID = String(sid);
      try {
        localStorage.setItem(SESSION_STORAGE_KEY, SESSION_ID);
      } catch (_) {}
      const url = new URL(document.location.href);
      url.searchParams.set("session_id", SESSION_ID);
      history.replaceState(null, "", url.toString());
      try {
        window.UnderdogApp?.setSessionId(SESSION_ID);
      } catch (_) {}
      updateUserSection();
      loadSettingsForCaption();
    } catch (e) {
      showToast("오류", "서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.", true);
      return false;
    }
  }
  if (!client.isConnected) {
    client.connect();
  }
  return true;
}

// 마이크 권한 요청 + 허용 시 바로 세션·연결·소리 감지 시작
function requestMicPermission() {
  if (!navigator?.mediaDevices?.getUserMedia) {
    console.error("getUserMedia not available", navigator, navigator?.mediaDevices);
    micTitle.textContent = "마이크 사용 불가";
    micDesc.textContent = "이 환경에서는 마이크를 지원하지 않습니다.";
    if (typeof alert === "function") {
      alert("이 환경에서는 마이크 기능이 지원되지 않아요 (HTTPS/localhost 또는 브라우저 확인).");
    }
    return;
  }
  navigator.mediaDevices.getUserMedia({ audio: true }).then(async (stream) => {
    micStream = stream;
    stream.getTracks().forEach((t) => {
      t.onended = () => {
        stopAudioSend();
        updateMicStatusUI();
      };
    });
    updateMicStatusUI();
    micTitle.textContent = "마이크 승인 완료";
    micDesc.textContent = "연결 중…";
    const ok = await ensureSessionAndConnect();
    if (!ok) {
      micDesc.textContent = "세션 생성 실패. 마이크를 다시 눌러 재시도하세요.";
      return;
    }
    if (client.isConnected && SESSION_ID) {
      startAudioSend().catch(console.error);
    }
  }).catch((err) => {
    console.error("getUserMedia failed", err);
    updateMicStatusUI();
    micTitle.textContent = "마이크 권한 거부됨";
    micDesc.textContent = "브라우저 설정에서 마이크 허용이 필요합니다.";
  });
}

function stopMicAndRelease() {
  stopAudioSend();
  if (micStream) {
    try {
      micStream.getTracks().forEach((t) => t.stop());
    } catch (_) {}
    micStream = null;
  }
  updateMicStatusUI();
  micTitle.textContent = "마이크 대기 중";
  micDesc.textContent = "마이크 사용 승인이 필요합니다.";
}

function showToast(title, body, danger=true) {
  const toastEl = document.createElement("div");
  toastEl.className = `toast ${danger ? "text-bg-danger" : "text-bg-primary"} border-0`;
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        <div class="fw-semibold">${title}</div>
        <div>${body}</div>
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;
  toastContainer.appendChild(toastEl);
  const t = new bootstrap.Toast(toastEl, { delay: 2500 });
  t.show();
  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

/** 배지: 소리 등록 폼「소리 알림 분류」와 동일 (danger / caution / alert) */
const HERO_LABELS = { danger: "위험/경고", caution: "주의", alert: "생활알림" };
/** 하위그룹 없을 때 #heroTitle 폴백 */
const HERO_TITLE_FALLBACK = { danger: "위험 감지", caution: "주의", alert: "생활알림" };

function stripLeadingBracketTag(descText, tag) {
  if (!tag || descText == null) return descText;
  const t = String(descText);
  const re = new RegExp("^\\s*\\[" + String(tag).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\]\\s*");
  const s = t.replace(re, "").trim();
  return s || t;
}

/** 서버 keyword(쿨다운용) + subgroup(표시용)에 맞춰 본문 한 줄 구성 */
function buildHeroAlertDesc(keyword, text, titleSubgroup) {
  const kw = (keyword || "").toString().trim();
  const body = (text || "").toString();
  const sub = (titleSubgroup || "").toString().trim();
  if (sub && kw.includes(":")) return body;
  if (kw && !kw.includes(":")) {
    const line = `[${kw}] ${body}`.trim();
    return sub ? stripLeadingBracketTag(line, sub) : line;
  }
  return body;
}

function heroTitleSubgroupFromParts(subgroup, keyword) {
  const s = (subgroup || "").toString().trim();
  if (s) return s;
  const kw = (keyword || "").toString().trim();
  if (kw && !kw.includes(":")) return kw;
  return "";
}

function setHeroNormal() {
  if (heroCard) heroCard.classList.remove("hero-alert-danger", "hero-alert-caution", "hero-alert-alert");
  heroBadge.className = "badge bg-secondary-subtle text-secondary border px-3 py-2";
  heroBadge.textContent = "상태";
  if (heroMatchedPhrase) {
    heroMatchedPhrase.textContent = "";
    heroMatchedPhrase.classList.add("d-none");
  }
  heroTitle.textContent = "대기중";
  heroTitle.className = "fs-5 fw-bold";
  heroDesc.textContent = "";
  heroDesc.className = "text-muted small";
}

/** STT 등: 실제 매칭된 규칙 문구를 배지 옆에 표시(하위그룹과 다를 때만). */
function applyHeroMatchedPhrase(matchedPhrase, titleSubgroup) {
  if (!heroMatchedPhrase) return;
  const p = (matchedPhrase && String(matchedPhrase).trim()) || "";
  const sub = (titleSubgroup && String(titleSubgroup).trim()) || "";
  if (p && p !== sub) {
    heroMatchedPhrase.textContent = `매칭:「${p}」`;
    heroMatchedPhrase.classList.remove("d-none");
  } else {
    heroMatchedPhrase.textContent = "";
    heroMatchedPhrase.classList.add("d-none");
  }
}

function setHeroAlert(descText, event_type, titleSubgroup, matchedPhrase) {
  const et = event_type === "caution" ? "caution" : event_type === "alert" ? "alert" : "danger";
  if (heroCard) {
    heroCard.classList.remove("hero-alert-danger", "hero-alert-caution", "hero-alert-alert");
    heroCard.classList.add("hero-alert-" + et);
  }
  heroBadge.className = "badge px-3 py-2 hero-badge hero-badge-" + et;
  heroBadge.textContent = HERO_LABELS[et];
  const sub = (titleSubgroup && String(titleSubgroup).trim()) || "";
  heroTitle.textContent = sub || HERO_TITLE_FALLBACK[et];
  heroTitle.className = "fs-5 fw-bold hero-title-" + et;
  heroDesc.textContent = descText || "";
  heroDesc.className = "small hero-desc-" + et;
  applyHeroMatchedPhrase(matchedPhrase, sub);
}

function setHeroDanger(text) {
  setHeroAlert(text, "danger", "", "");
}

// =======================
// Vibration (Web Vibration API + user-gesture gated + cooldown)
// - iOS Safari: 진동 API 없음 → 알림만 뜨고 진동 없음이 정상
// - PC 크롬·iPad 에뮬레이터: 대부분 진동 없음
// - 실제 안드로이드 폰 + 크롬(HTTPS): 여기서만 확실히 동작
// =======================
let vibrationUnlockedByUser = false;
let lastVibrateAtMs = 0;
let vibrateUnsupportedHintShown = false;

function isAndroidDevice() {
  const ua = (navigator.userAgent || "").toLowerCase();
  return ua.includes("android");
}

/** 브라우저가 진동 API를 노출하는지 (기기가 실제로 울리는지는 별개) */
function supportsVibrateAPI() {
  if (typeof navigator === "undefined" || typeof navigator.vibrate !== "function") return false;
  try {
    if (typeof window !== "undefined" && window.isSecureContext === false) return false;
  } catch (_) {}
  return true;
}

function unlockVibrationByUserGesture() {
  vibrationUnlockedByUser = true;
}

function canVibrate() {
  if (!vibrationUnlockedByUser) return false;
  return supportsVibrateAPI();
}

/** 알림은 떴는데 진동만 안 될 때 1회만 안내 (iOS/PC 등) */
function maybeWarnVibrateUnsupported() {
  if (vibrateUnsupportedHintShown) return;
  if (!vibrationUnlockedByUser) return;
  if (supportsVibrateAPI()) return;
  vibrateUnsupportedHintShown = true;
  showToast(
    "진동 안내",
    "이 환경(iOS·일부 태블릿·PC)에서는 웹 진동이 지원되지 않아요. 실제 안드로이드 폰 크롬에서 확인해 주세요.",
    false
  );
}

function vibrateWithCooldown(pattern, cooldownMs) {
  if (!canVibrate()) return;
  const now = Date.now();
  if (now - lastVibrateAtMs < cooldownMs) return;
  lastVibrateAtMs = now;
  try {
    navigator.vibrate(0);
    navigator.vibrate(pattern);
  } catch (_) {}
}

// 진동: 위험 단계별 패턴 (웹 API는 강도 불가 → 길이·간격·반복을 최대한 길게)
// 브라우저/OS가 한 번에 허용하는 길이에 잘릴 수 있음.
function vibrateByLevel(eventType) {
  maybeWarnVibrateUnsupported();
  if (!canVibrate()) return;
  if (eventType === "danger") {
    // 위험: 약 4.6초 분량 (긴 펄스 4회 + 마지막 길게)
    vibrateWithCooldown(
      [700, 150, 700, 150, 700, 150, 700, 150, 1200],
      5200
    );
  } else {
    // 주의·일상 알림: 약 2.2초 분량
    vibrateWithCooldown([400, 140, 400, 140, 400, 140, 600], 3200);
  }
}

function setupVibrationTestButton() {
  if (!btnVibrateTest) return;
  if (!isAndroidDevice() && !supportsVibrateAPI()) return;

  btnVibrateTest.classList.remove("d-none");
  btnVibrateTest.disabled = !vibrationUnlockedByUser;

  btnVibrateTest.addEventListener("click", () => {
    unlockVibrationByUserGesture();
    btnVibrateTest.disabled = false;

    if (!canVibrate()) {
      showToast("진동 불가", "이 기기/브라우저에서는 웹 진동을 지원하지 않아요.", true);
      return;
    }

    showToast("진동 테스트", "긴 패턴으로 진동합니다.", false);
    vibrateWithCooldown([500, 150, 500, 150, 500, 200, 800], 0);
  });
}

// =======================
// 3) Mic UI + audio_chunk 전송
// =======================
function float32ToInt16(float32Arr) {
  const int16 = new Int16Array(float32Arr.length);
  for (let i = 0; i < float32Arr.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Arr[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return int16;
}

function downsample(input, inputSr, outputSr) {
  const ratio = inputSr / outputSr;
  const outLen = Math.floor(input.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const srcIdx = i * ratio;
    const j = Math.floor(srcIdx);
    const f = srcIdx - j;
    out[i] = j + 1 < input.length
      ? input[j] * (1 - f) + input[j + 1] * f
      : input[j];
  }
  return out;
}

function stopAudioSend() {
  if (audioWorkletNode) {
    try {
      audioWorkletNode.disconnect();
      audioSource?.disconnect();
    } catch (_) {}
    audioWorkletNode = null;
  }
  if (audioProcessor) {
    try {
      audioProcessor.disconnect();
      audioSource?.disconnect();
    } catch (_) {}
  }
  audioProcessor = null;
  audioSource = null;
  if (audioContext && audioContext.state !== "closed") {
    audioContext.close().catch(() => {});
  }
  audioContext = null;
  audioBuffer = [];
  rawBuffer = [];
}


function flushRawToChunks() {
  if (!currentSr || !client.isConnected || !SESSION_ID) return;
  const needRaw = Math.ceil((CHUNK_SAMPLES * currentSr) / TARGET_SR);
  while (rawBuffer.length >= needRaw) {
    const raw = rawBuffer.splice(0, needRaw);
    const down = downsample(raw, currentSr, TARGET_SR);
    if (down.length < CHUNK_SAMPLES) continue;
    const chunk = down.length > CHUNK_SAMPLES ? down.subarray(0, CHUNK_SAMPLES) : down;
    const int16 = float32ToInt16(chunk);
    const uint8 = new Uint8Array(int16.buffer);
    let binary = "";
    for (let i = 0; i < uint8.length; i++) binary += String.fromCharCode(uint8[i]);
    client.send("audio_chunk", {
      session_id: SESSION_ID,
      ts_ms: Date.now(),
      sr: TARGET_SR,
      format: "pcm_s16le",
      data_b64: btoa(binary),
    });
  }
}

async function startAudioSend() {
  if (!micStream || !SESSION_ID || !client.isConnected) return;
  stopAudioSend();

  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    audioContext.onstatechange = () => {
      if (audioContext && audioContext.state === "closed") stopAudioSend();
    };
    currentSr = audioContext.sampleRate;
    audioSource = audioContext.createMediaStreamSource(micStream);
    rawBuffer = [];

    if (audioContext.audioWorklet && typeof audioContext.audioWorklet.addModule === "function") {
      await audioContext.audioWorklet.addModule(WORKLET_URL);
      audioWorkletNode = new AudioWorkletNode(audioContext, "mic-processor");
      audioWorkletNode.port.onmessage = (e) => {
        try {
          if (e.data?.type === "audio" && e.data.samples) {
            for (let i = 0; i < e.data.samples.length; i++) rawBuffer.push(e.data.samples[i]);
            flushRawToChunks();
          }
        } catch (err) {
          console.error("worklet audio process error", err);
          stopAudioSend();
        }
      };
      const gain = audioContext.createGain();
      gain.gain.value = 0;
      gain.connect(audioContext.destination);
      audioSource.connect(audioWorkletNode);
      audioWorkletNode.connect(gain);
    } else {
      const bufferSize = 4096;
      audioProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);
      audioBuffer = [];
      audioProcessor.onaudioprocess = (e) => {
        try {
          if (!client.isConnected || !SESSION_ID) return;
          const input = e.inputBuffer.getChannelData(0);
          const down = downsample(input, currentSr, TARGET_SR);
          for (let i = 0; i < down.length; i++) audioBuffer.push(down[i]);
          while (audioBuffer.length >= CHUNK_SAMPLES) {
            const chunk = audioBuffer.splice(0, CHUNK_SAMPLES);
            const floatArr = new Float32Array(chunk);
            const int16 = float32ToInt16(floatArr);
            const uint8 = new Uint8Array(int16.buffer);
            let binary = "";
            for (let i = 0; i < uint8.length; i++) binary += String.fromCharCode(uint8[i]);
            client.send("audio_chunk", {
              session_id: SESSION_ID,
              ts_ms: Date.now(),
              sr: TARGET_SR,
              format: "pcm_s16le",
              data_b64: btoa(binary),
            });
          }
        } catch (err) {
          console.error("audio_chunk process error", err);
          stopAudioSend();
        }
      };
      const gain = audioContext.createGain();
      gain.gain.value = 0;
      gain.connect(audioContext.destination);
      audioSource.connect(audioProcessor);
      audioProcessor.connect(gain);
    }
    micTitle.textContent = "소리 듣는 중";
    micDesc.textContent = "주변 소리를 감지하고 있어요.";
    if (btnMic) btnMic.textContent = "마이크 중단";
    updateMicStatusUI();
  } catch (e) {
    console.error("audio_chunk start failed:", e);
    stopAudioSend();
    micTitle.textContent = "마이크 오류";
    micDesc.textContent = "오디오 초기화에 실패했습니다.";
  }
}

btnMic.addEventListener("click", () => {
  // 사용자 액션(버튼 클릭) 이후에만 진동을 허용하도록 unlock
  unlockVibrationByUserGesture();
  if (btnVibrateTest) btnVibrateTest.disabled = false;
  // 이미 마이크 사용 중이면 종료 안내 모달
  if (micStream) {
    if (micStopModal && micStopConfirm && window.bootstrap) {
      const modal = new bootstrap.Modal(micStopModal);
      micStopModal.removeAttribute("inert");
      micStopModal.setAttribute("aria-hidden", "false");
      modal.show();
      micStopConfirm.addEventListener("click", () => {
        modal.hide();
        stopMicAndRelease();
      }, { once: true });
    } else {
      stopMicAndRelease();
    }
    return;
  }

  // 마이크 미사용 → 바로 브라우저 마이크 권한 요청 (허용 시 자동 연결·소리 감지 시작)
  requestMicPermission();
});

// =======================
// 4) WS
// =======================
const client = new WSClient(WS_URL);

client.on("open", () => {
  // 백엔드는 join을 받아야 caption/alert 수신 가능 → 반드시 join 먼저 전송
  client.send("join", { session_id: SESSION_ID });

  btnFeedbackYes.disabled = false;
  btnFeedbackNo.disabled = false;

  if (btnMic) btnMic.textContent = micStream ? "마이크 중단" : "마이크 실행";
  updateMicStatusUI();
  micTitle.textContent = micStream ? "소리 듣는 중" : "마이크 대기 중";
  micDesc.textContent  = micStream ? "주변 소리를 감지하고 있어요." : "마이크를 켜면 이벤트를 감지해요.";
  // join이 서버에서 처리된 뒤 오디오 전송 시작 (STT 수신 보장)
  if (micStream && SESSION_ID) {
    setTimeout(() => startAudioSend().catch(console.error), 150);
  }
});

client.on("close", () => {
  stopAudioSend();
  if (micStream) {
    if (client.autoReconnect) {
      micTitle.textContent = "연결 중…";
      micDesc.textContent = "서버에 다시 연결하는 중이에요.";
    } else {
      micTitle.textContent = "연결 끊김";
      micDesc.textContent = "마이크를 다시 눌러 재연결하세요.";
    }
  }
  updateMicStatusUI();

  btnFeedbackYes.disabled = true;
  btnFeedbackNo.disabled = true;
});

// 서버가 caption 보내면 (STT 결과 = 말한 내용). 실시간 자막에만 표시.
// 토스트/진동은 alert에서 처리 (키워드 시 caption+alert 둘 다 오므로 중복 방지).
client.on("caption", (msg) => {
  if (!msg || typeof msg !== "object") return;
  const text = (msg.text ?? msg.payload?.text ?? "").toString();
  const danger = isDanger(text);

  appendCaption(text, danger);

  if (danger) {
    setHeroAlert(text, "danger", "", "");
  }
});

// 서버가 alert 보내면 (키워드/YAMNet/커스텀 소리 등). 최근 감지 로그 + 실시간 자막에 표시.
client.on("alert", (msg) => {
  if (!msg || typeof msg !== "object") return;
  const p = (msg && typeof msg.payload === "object" && msg.payload !== null) ? msg.payload : undefined;
  const text = (msg.text ?? p?.text ?? "").toString();
  const keyword = (msg.keyword ?? p?.keyword ?? "").toString();
  const subgroupRaw = (msg.subgroup ?? p?.subgroup ?? "").toString().trim();
  const event_type = msg.event_type ?? p?.event_type ?? "danger";
  const event_id = msg.event_id ?? p?.event_id;
  const ts_ms = msg.ts_ms ?? p?.ts_ms;
  const source = msg.source ?? p?.source ?? "text";
  const matchedPhraseRaw = (msg.matched_phrase ?? p?.matched_phrase ?? "").toString().trim();
  const titleSubgroup = heroTitleSubgroupFromParts(subgroupRaw, keyword);
  if (event_id != null) {
    lastAlertEventInfo = {
      event_id,
      text,
      keyword,
      subgroup: titleSubgroup,
      matched_phrase: matchedPhraseRaw,
      event_type,
      ts_ms,
    };
  }

  // alert는 UI에서 반드시 보이게 한다.
  // 원래는 "키워드면 caption에서 이미 넣음"이었지만, caption_all=OFF에서 caption이 누락되는 케이스가 있어
  // alert(text)를 자막에도 폴백으로 추가해준다(중복은 감수, UX 우선).
  appendCaption(text, event_type === "danger");
  clearLogRowSelection();
  appendLogRow({
    ts_ms: msg.ts_ms ?? p?.ts_ms,
    ts: msg.ts ?? p?.ts,
    type: "alert",
    text,
    keyword,
    subgroup: titleSubgroup,
    matched_phrase: matchedPhraseRaw,
    event_type,
    score: msg.score ?? p?.score,
    event_id: event_id != null ? event_id : undefined,
  });

  setHeroAlert(
    buildHeroAlertDesc(keyword, text, titleSubgroup),
    event_type,
    titleSubgroup,
    source === "text" ? matchedPhraseRaw : ""
  );
  const toastTitle =
    event_type === "danger" ? "위험/경고" : event_type === "caution" ? "주의" : "생활알림";
  let toastBody =
    titleSubgroup && keyword.includes(":")
      ? text
      : `${keyword && !keyword.includes(":") ? "[" + keyword + "] " : ""}${text}`;
  if (source === "text" && matchedPhraseRaw) {
    toastBody += ` · 매칭:「${matchedPhraseRaw}」`;
  }
  showToast(toastTitle, toastBody, true);
  vibrateByLevel(event_type);
});

// Feedback: 맞아요=즉시 POST, 아니에요=모달에서 comment 필수 후 POST
async function sendFeedback(vote, comment) {
  if (!lastAlertEventInfo) {
    showToast("피드백", "대상 알림이 없습니다. 알림이 온 뒤에 눌러주세요.", true);
    return;
  }
  const body = {
    event_id: lastAlertEventInfo.event_id,
    vote: vote,
    session_id: SESSION_ID || undefined,
  };
  if (comment != null && comment.trim() !== "") body.comment = comment.trim();
  try {
    const res = await fetch(API_BASE + "/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      showToast("피드백", "저장되었습니다.", false);
      lastAlertEventInfo = null;  // 제출 후 초기화
      clearLogRowSelection();
      setHeroNormal();
    } else {
      showToast("피드백 실패", data.detail || res.statusText || "다시 시도해 주세요.", true);
    }
  } catch (e) {
    showToast("오류", "연결할 수 없습니다. 서버를 확인하세요.", true);
  }
}

function showFeedbackCommentModal() {
  if (!lastAlertEventInfo) {
    showToast("피드백", "대상 알림이 없습니다.", true);
    return;
  }
  const info = lastAlertEventInfo;
  const kind = info.event_type === "danger" ? "위험/경고" : info.event_type === "caution" ? "주의" : "생활알림";
  const timeStr = formatTs(info.ts_ms);
  const eventInfoEl = document.getElementById("feedbackModalEventInfo");
  const inputEl = document.getElementById("feedbackCommentInput");
  if (eventInfoEl) {
    eventInfoEl.innerHTML = `<strong>${kind}</strong> · ${info.keyword ? "[" + info.keyword + "] " : ""}${info.text || "-"} · ${timeStr}`;
  }
  if (inputEl) inputEl.value = "";
  const modal = new bootstrap.Modal(document.getElementById("feedbackCommentModal"));
  modal.show();
  inputEl?.focus();
}

function setupFeedbackCommentModal() {
  const modalEl = document.getElementById("feedbackCommentModal");
  const inputEl = document.getElementById("feedbackCommentInput");
  const submitBtn = document.getElementById("feedbackCommentSubmit");
  if (!modalEl || !inputEl || !submitBtn) return;
  modalEl.addEventListener("shown.bs.modal", () => modalEl.removeAttribute("inert"));
  modalEl.addEventListener("hidden.bs.modal", () => modalEl.setAttribute("inert", ""));
  submitBtn.addEventListener("click", () => {
    const comment = (inputEl.value || "").trim();
    if (!comment) {
      showToast("피드백", "코멘트를 입력해 주세요.", true);
      inputEl.focus();
      return;
    }
    bootstrap.Modal.getInstance(modalEl)?.hide();
    sendFeedback("down", comment);
  });
}

btnFeedbackYes.addEventListener("click", () => sendFeedback("up"));
btnFeedbackNo.addEventListener("click", () => showFeedbackCommentModal());
setupFeedbackCommentModal();

// 로그인 상태: provider 있으면 사용자 아이콘+드롭다운, 없으면 '다른 계정' 버튼
function getProvider() {
  const fromUrl = new URLSearchParams(document.location.search).get("provider");
  if (fromUrl) return fromUrl;
  try {
    return localStorage.getItem(PROVIDER_STORAGE_KEY) || null;
  } catch (_) {
    return null;
  }
}

function isGuest() {
  const p = getProvider();
  return p !== "google" && p !== "kakao";
}

function updateUserSection() {
  if (!userDropdownWrap) return;
  const provider = getProvider();
  if (provider === "google" || provider === "kakao") {
    userDropdownWrap.classList.remove("d-none");
    if (SESSION_ID) loadUserInfo();
  } else {
    userDropdownWrap.classList.add("d-none");
  }
  updateLogSectionVisibility();
}

function updateLogSectionVisibility() {
  if (logSection && guestCtaSection) {
    if (isGuest()) {
      logSection.classList.add("d-none");
      guestCtaSection.classList.remove("d-none");
      document.getElementById("mainContentRow")?.classList.add("guest-layout");
    } else {
      logSection.classList.remove("d-none");
      guestCtaSection.classList.add("d-none");
      document.getElementById("mainContentRow")?.classList.remove("guest-layout");
    }
  }
}

async function loadUserInfo() {
  if (!SESSION_ID || !userDropdownName || !userDropdownEmail) return;
  const now = Date.now();
  if (now < userInfoStopUntilTs) return;
  if (userInfoInFlight) return;
  if (userInfoLastFetchTs && now - userInfoLastFetchTs < 10000) return; // 10초 쿨다운

  userInfoInFlight = true;
  userInfoLastFetchTs = now;
  try {
    const res = await fetch(API_BASE + "/auth/me?session_id=" + encodeURIComponent(SESSION_ID));
    // provider(localStorage)는 남아있는데 실제 세션이 게스트이거나 유저가 없는 경우 404가 날 수 있음.
    // 이 경우 provider 상태를 정리해서 이후 반복 호출/콘솔 노이즈를 줄인다.
    if (res.status === 404) {
      try {
        localStorage.removeItem(PROVIDER_STORAGE_KEY);
      } catch (_) {}
      // 30초간 /auth/me 재호출 중단 (updateUserSection에서 다시 호출될 수 있어 선적용)
      userInfoStopUntilTs = Date.now() + 30000;
      // 게스트 UI로 전환(로그 섹션/CTA 포함)
      updateUserSection();
      return;
    }
    const data = await res.json().catch(() => ({}));
    const ok = res.ok && data && (data.ok === true || data.ok === "true");
    const name = (data && (data.name ?? data.user?.name)) || "사용자";
    const email = (data && (data.email ?? data.user?.email)) || "-";
    if (!ok) {
      // provider는 남아있지만 실제로는 유저가 없는 상태일 수 있음.
      try {
        localStorage.removeItem(PROVIDER_STORAGE_KEY);
      } catch (_) {}
      userInfoStopUntilTs = Date.now() + 30000;
      updateUserSection();
      return;
    }
    userDropdownName.textContent = name;
    userDropdownEmail.textContent = email;
  } catch (_) {
    if (userDropdownName) userDropdownName.textContent = "사용자";
    if (userDropdownEmail) userDropdownEmail.textContent = "-";
  } finally {
    userInfoInFlight = false;
  }
}

function setupUserDropdown() {
  const userDropdownSettings = document.getElementById("userDropdownSettings");
  if (!userDropdownWrap || !btnUserIcon || !userDropdownSoundReg || !userDropdownLogout) return;

  // 소리등록: /new-sound?session_id=xxx (같은 세션으로 커스텀 소리 등록 → 마이크에서 감지)
  userDropdownSoundReg.addEventListener("click", (e) => {
    e.preventDefault();
    const sid = SESSION_ID || (typeof localStorage !== "undefined" && localStorage.getItem(SESSION_STORAGE_KEY));
    const url = "/new-sound" + (sid ? "?session_id=" + encodeURIComponent(sid) : "");
    window.location.href = url;
  });

  // 설정: 설정 페이지로 이동 (session_id, provider 전달)
  if (userDropdownSettings) {
    userDropdownSettings.addEventListener("click", (e) => {
      e.preventDefault();
      const sid = SESSION_ID || (typeof localStorage !== "undefined" && localStorage.getItem(SESSION_STORAGE_KEY));
      const prov = getProvider();
      const params = new URLSearchParams();
      if (sid) params.set("session_id", sid);
      if (prov) params.set("provider", prov);
      const qs = params.toString();
      window.location.href = "/settings-page" + (qs ? "?" + qs : "");
    });
  }

  // 로그아웃: 메인으로 이동, session_id·provider 제거
  userDropdownLogout.addEventListener("click", (e) => {
    e.preventDefault();
    try {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      localStorage.removeItem(PROVIDER_STORAGE_KEY);
    } catch (_) {}
    window.location.href = "/";
  });

  // mouseover 시 드롭다운 표시 (Bootstrap/요소 없으면 무시)
  let hideTimer = null;
  userDropdownWrap.addEventListener("mouseenter", () => {
    if (hideTimer) clearTimeout(hideTimer);
  });
  userDropdownWrap.addEventListener("mouseleave", () => {
    hideTimer = setTimeout(() => {
      try {
        if (window.bootstrap && btnUserIcon) {
          const dropdown = bootstrap.Dropdown.getInstance(btnUserIcon);
          if (dropdown) dropdown.hide();
        }
      } catch (_) {}
    }, 150);
  });
}

// 푸터: 소리등록/설정 링크 - 게스트 클릭 시 로그인 유도
function setupFooterAuthLinks() {
  const footerSoundReg = document.getElementById("footerSoundReg");
  const footerSettings = document.getElementById("footerSettings");
  const intercept = (e, link) => {
    if (!link) return;
    if (isGuest()) {
      e.preventDefault();
      alert("로그인이 필요한 서비스입니다.");
      window.location.href = "/login";
    }
  };
  if (footerSoundReg) footerSoundReg.addEventListener("click", (e) => intercept(e, footerSoundReg));
  if (footerSettings) footerSettings.addEventListener("click", (e) => intercept(e, footerSettings));
}

function setupCaptionTestAllButton() {
  if (!btnCaptionTestAll) return;
  updateCaptionTestButtonUI(false);
  btnCaptionTestAll.addEventListener("click", async () => {
    if (!SESSION_ID) {
      showToast("세션 없음", "마이크를 눌러 세션을 만든 뒤 다시 시도해 주세요.", true);
      return;
    }
    const next = !captionAllEnabled;
    btnCaptionTestAll.disabled = true;
    try {
      const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caption_all: next }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.ok) {
        updateCaptionTestButtonUI(captionAllEnabled); // 롤백
        return;
      }
      updateCaptionTestButtonUI(next);
    } catch (_) {
      updateCaptionTestButtonUI(captionAllEnabled); // 롤백
    }
  });
}
// 설정: 자막 글자 크기만 로드 (설정 페이지는 /settings-page 에서 편집)
function applyFontSizeToCaption(px) {
  if (captionBox && px != null) {
    const num = Math.min(60, Math.max(10, Number(px)));
    captionBox.style.fontSize = num + "px";
  }
}

async function loadSettingsForCaption() {
  if (!SESSION_ID) return;
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID));
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data?.ok) return;
    const d = data?.data ?? data;
    const fontSize = d?.font_size;
    if (fontSize != null && captionBox) {
      applyFontSizeToCaption(fontSize);
    }
    updateCaptionTestButtonUI(d?.caption_all === true);
  } catch (_) {}
}

// Init (한 곳에서 예외 나와도 나머지 동작하도록 보호)
(function init() {
  try {
    updateMicStatusUI();
    setHeroNormal();
    updateUserSection();
    updateLogSectionVisibility();
    setupLogTableFeedbackClicks();
    setupVibrationTestButton();
    setupUserDropdown();
    setupFooterAuthLinks();
    setupCaptionTestAllButton();
    if (SESSION_ID) loadSettingsForCaption();
  } catch (e) {
    console.warn("[Lumen] init error", e);
  }
})();

// 상단 IIFE에서 capture:true 로 이미 처리 — 중복 리스너 제거 (이중 preventDefault 방지)