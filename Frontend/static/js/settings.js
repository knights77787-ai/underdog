// 설정 페이지: GET/POST /settings API
const API_BASE = window.APP_CONFIG?.API_BASE || document.location.origin;
const SESSION_STORAGE_KEY = "underdog_session_id";
const PROVIDER_STORAGE_KEY = "underdog_provider";

const SESSION_ID = (function () {
  const params = new URLSearchParams(document.location.search);
  const fromUrl = params.get("session_id");
  const providerFromUrl = params.get("provider");
  if (fromUrl) {
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, fromUrl);
    } catch (_) {}
  }
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

function setStatus(msg, isError) {
  if (settingsStatus) {
    settingsStatus.textContent = msg || "";
    settingsStatus.className = "small " + (isError ? "text-danger" : "text-muted");
  }
}

async function loadSettings() {
  if (!SESSION_ID) {
    setStatus("로그인이 필요합니다. 라이브에서 마이크를 눌러 세션을 시작하세요.", true);
    return;
  }
  setStatus("불러오는 중…", false);
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID));
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok || !data.data) {
      setStatus("불러오기 실패", true);
      return;
    }
    const d = data.data;
    if (settingFontSize) settingFontSize.value = d.font_size ?? 20;
    if (settingAlertEnabled) settingAlertEnabled.checked = d.alert_enabled !== false;
    if (settingCooldownSec) settingCooldownSec.value = d.cooldown_sec ?? 5;
    if (settingAutoScroll) settingAutoScroll.checked = d.auto_scroll !== false;
    setStatus("불러옴", false);
  } catch (e) {
    setStatus("연결 실패", true);
  }
}

async function saveSettings(e) {
  e.preventDefault();
  if (!SESSION_ID) {
    setStatus("세션이 없습니다.", true);
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

  setStatus("저장 중…", false);
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      setStatus("저장되었습니다.", false);
    } else {
      setStatus(data.detail || "저장 실패", true);
    }
  } catch (e) {
    setStatus("연결 실패", true);
  }
}

if (settingsForm) settingsForm.addEventListener("submit", saveSettings);

// 헬퍼: session_id, provider 포함한 base URL 생성
function buildUrlWithSession(path) {
  let sid = SESSION_ID;
  if (!sid && typeof localStorage !== "undefined") {
    sid = localStorage.getItem(SESSION_STORAGE_KEY);
  }
  sid = (sid && String(sid).trim()) || null;
  let prov = new URLSearchParams(document.location.search).get("provider");
  if (!prov && typeof localStorage !== "undefined") {
    prov = localStorage.getItem(PROVIDER_STORAGE_KEY);
  }
  prov = (prov && String(prov).trim()) || null;
  const params = new URLSearchParams();
  if (sid) params.set("session_id", sid);
  if (prov) params.set("provider", prov);
  const qs = params.toString();
  return qs ? path + "?" + qs : path;
}

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
  try {
    const res = await fetch(API_BASE + "/auth/me?session_id=" + encodeURIComponent(SESSION_ID));
    const data = await res.json().catch(() => ({}));
    const ok = res.ok && data && (data.ok === true || data.ok === "true");
    const name = (data && (data.name ?? data.user?.name)) || "사용자";
    const email = (data && (data.email ?? data.user?.email)) || "-";
    userDropdownName.textContent = ok ? name : "사용자";
    userDropdownEmail.textContent = ok ? email : "-";
  } catch (_) {
    if (userDropdownName) userDropdownName.textContent = "사용자";
    if (userDropdownEmail) userDropdownEmail.textContent = "-";
  }
}

// 사용자 드롭다운: 소리등록, 설정, 로그아웃
function setupUserDropdown() {
  const userDropdownSoundReg = document.getElementById("userDropdownSoundReg");
  const userDropdownSettings = document.getElementById("userDropdownSettings");
  const userDropdownLogout = document.getElementById("userDropdownLogout");

  if (userDropdownSoundReg) {
    userDropdownSoundReg.addEventListener("click", (e) => {
      e.preventDefault();
      window.location.href = buildUrlWithSession("/new-sound");
    });
  }
  if (userDropdownSettings) {
    userDropdownSettings.addEventListener("click", (e) => {
      e.preventDefault();
      window.location.href = buildUrlWithSession("/settings-page");
    });
  }
  if (userDropdownLogout) {
    userDropdownLogout.addEventListener("click", (e) => {
      e.preventDefault();
      try {
        localStorage.removeItem(SESSION_STORAGE_KEY);
        localStorage.removeItem(PROVIDER_STORAGE_KEY);
      } catch (_) {}
      window.location.href = "/";
    });
  }
}

setupUserDropdown();
loadUserInfo();

if (SESSION_ID) {
  loadSettings();
} else {
  setStatus("로그인이 필요합니다.", true);
}
