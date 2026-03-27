// 설정 페이지: GET/POST /settings API
const API_BASE = window.APP_CONFIG?.API_BASE || document.location.origin;
const SESSION_STORAGE_KEY =
  window.UnderdogAuthNav?.SESSION_STORAGE_KEY || "underdog_session_id";
const PROVIDER_STORAGE_KEY =
  window.UnderdogAuthNav?.PROVIDER_STORAGE_KEY || "underdog_provider";

const SESSION_ID = (function () {
  window.UnderdogAuthNav?.syncFromUrl?.();
  return window.UnderdogAuthNav?.getSessionId?.() || null;
})();
if (SESSION_ID) {
  try {
    window.UnderdogApp?.setSessionId(SESSION_ID);
  } catch (_) {}
}

const settingFontSize = document.getElementById("settingFontSize");
const settingAlertEnabled = document.getElementById("settingAlertEnabled");
const settingCooldownSec = document.getElementById("settingCooldownSec");
const settingAutoScroll = document.getElementById("settingAutoScroll");
const btnSettingsSave = document.getElementById("btnSettingsSave");
const settingsStatus = document.getElementById("settingsStatus");
const settingsForm = document.getElementById("settingsForm");
const UI_MSG = window.UnderdogMessages?.settings || {
  needLogin: "로그인이 필요합니다. 라이브에서 마이크를 눌러 세션을 시작하세요.",
  loading: "불러오는 중…",
  loadFailed: "불러오기에 실패했습니다.",
  loaded: "불러옴",
  networkFailed: "서버 연결에 실패했습니다.",
  noSession: "세션이 없습니다.",
  saving: "저장 중…",
  saved: "저장되었습니다.",
  saveFailed: "저장에 실패했습니다.",
};

function setStatus(msg, isError) {
  window.UnderdogStatusUI?.setStatus?.(settingsStatus, msg || "", {
    type: isError ? "err" : "muted",
    baseClass: "small",
    classMap: { err: "text-danger", muted: "text-muted" },
  });
}

function showToast(title, body, tone = "danger") {
  window.UnderdogToastUI?.showToast?.({
    title,
    body,
    tone,
    delayMs: 2200,
  });
}

async function loadSettings() {
  if (!SESSION_ID) {
    setStatus(UI_MSG.needLogin, true);
    return;
  }
  setStatus(UI_MSG.loading, false);
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID));
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok || !data.data) {
      setStatus(UI_MSG.loadFailed, true);
      showToast("설정", UI_MSG.loadFailed, "danger");
      return;
    }
    const d = data.data;
    if (settingFontSize) settingFontSize.value = d.font_size ?? 20;
    if (settingAlertEnabled) settingAlertEnabled.checked = d.alert_enabled !== false;
    if (settingCooldownSec) settingCooldownSec.value = d.cooldown_sec ?? 5;
    if (settingAutoScroll) settingAutoScroll.checked = d.auto_scroll !== false;
    setStatus(UI_MSG.loaded, false);
  } catch (e) {
    setStatus(UI_MSG.networkFailed, true);
    showToast("설정", UI_MSG.networkFailed, "danger");
  }
}

async function saveSettings(e) {
  e.preventDefault();
  if (!SESSION_ID) {
    setStatus(UI_MSG.noSession, true);
    return;
  }
  const body = {};
  if (settingFontSize) {
    const v = parseInt(settingFontSize.value, 10);
    if (v >= 10 && v <= 60) body.font_size = v;
  }
  if (settingAlertEnabled) body.alert_enabled = settingAlertEnabled.checked;
  if (settingCooldownSec) {
    const v = parseInt(settingCooldownSec.value, 10);
    if (v >= 0 && v <= 60) body.cooldown_sec = v;
  }
  if (settingAutoScroll) body.auto_scroll = settingAutoScroll.checked;

  setStatus(UI_MSG.saving, false);
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      setStatus(UI_MSG.saved, false);
      showToast("설정", UI_MSG.saved, "success");
    } else {
      const failMsg = data.detail || UI_MSG.saveFailed;
      setStatus(failMsg, true);
      showToast("설정", failMsg, "danger");
    }
  } catch (e) {
    setStatus(UI_MSG.networkFailed, true);
    showToast("설정", UI_MSG.networkFailed, "danger");
  }
}

if (settingsForm) settingsForm.addEventListener("submit", saveSettings);

// 사용자 정보 로드 (드롭다운 상단 표시)
async function loadUserInfo() {
  const userDropdownName = document.getElementById("userDropdownName");
  const userDropdownEmail = document.getElementById("userDropdownEmail");
  if (!userDropdownName || !userDropdownEmail) return;
  if (!SESSION_ID) {
    userDropdownName.textContent = "게스트";
    userDropdownEmail.textContent = "-";
    return;
  }
  await window.UnderdogAuthNav?.loadUserIdentity?.({
    apiBase: API_BASE,
    sessionId: SESSION_ID,
    nameEl: userDropdownName,
    emailEl: userDropdownEmail,
  });
}

// 사용자 드롭다운: 소리등록, 설정, 로그아웃
function setupUserDropdown() {
  const userDropdownSoundReg = document.getElementById("userDropdownSoundReg");
  const userDropdownSettings = document.getElementById("userDropdownSettings");
  const userDropdownLogout = document.getElementById("userDropdownLogout");
  window.UnderdogAuthNav?.bindUserDropdown?.({
    apiBase: API_BASE,
    sessionId: SESSION_ID,
    soundRegEl: userDropdownSoundReg,
    settingsEl: userDropdownSettings,
    logoutEl: userDropdownLogout,
  });
}

setupUserDropdown();
loadUserInfo();

if (SESSION_ID) {
  loadSettings();
} else {
  setStatus(UI_MSG.needLogin, true);
}
