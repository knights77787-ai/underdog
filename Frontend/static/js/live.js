// Frontend/static/js/live.js
// =======================
// 0) 서버 주소 · 세션 (백엔드 연동: join 시 사용)
// =======================
const API_BASE = window.APP_CONFIG?.API_BASE || "http://127.0.0.1:8000";
const WS_URL = (window.APP_CONFIG?.WS_URL || "ws://127.0.0.1:8000/ws").replace(/^http/, "ws");
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
}
// 피드백 대상: 가장 최근 수신한 alert의 event_id
let lastAlertEventId = null;

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

const saveToggle = document.getElementById("saveToggle");

const heroBadge = document.getElementById("heroBadge");
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
    modalEl.setAttribute("inert", "");
    modalEl.setAttribute("aria-hidden", "true");
  });
}
setupModalA11y(micPermissionModal);
setupModalA11y(micStopModal);

const captionBox = document.getElementById("captionBox");

const toastContainer = document.getElementById("toastContainer");
const sessionLabel = document.getElementById("sessionLabel");
const btnLogin = document.getElementById("btnLogin");
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

const LOCAL_LOG_KEY = "underdog_event_log";
const MAX_LOCAL_LOGS = 30;

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

function appendLogRow({ ts, ts_ms, type, text, score, event_type, keyword }) {
  const tr = document.createElement("tr");
  const kind = (type === "alert") ? "경고" : "자막";
  const prob = (typeof score === "number") ? `${Math.round(score * 100)}%` : "-";
  const extra = keyword ? ` [${keyword}]` : "";
  const timeStr = formatTs(ts_ms ?? ts);

  tr.innerHTML = `
    <td>${timeStr}</td>
    <td>${kind}</td>
    <td>${text}${extra}${event_type ? ` (${event_type})` : ""}</td>
    <td>${prob}</td>
  `;
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
    score: typeof score === "number" ? score : null,
  });
}

// 세션 확보 + WebSocket 연결 (세션 없으면 /auth/guest 호출)
async function ensureSessionAndConnect() {
  if (!SESSION_ID) {
    try {
      const res = await fetch(API_BASE + "/auth/guest", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!data.ok || !data.session_id) {
        const msg = data.detail || (res.ok ? "세션 ID를 받지 못했습니다." : "서버 오류 " + res.status);
        showToast("세션 발급 실패", msg, true);
        return false;
      }
      SESSION_ID = data.session_id;
      try {
        localStorage.setItem(SESSION_STORAGE_KEY, SESSION_ID);
      } catch (_) {}
      const url = new URL(document.location.href);
      url.searchParams.set("session_id", SESSION_ID);
      history.replaceState(null, "", url.toString());
      updateSessionLabel();
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
  micTitle.textContent = "소리 감지 대기중";
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

function setHeroNormal() {
  heroBadge.className = "badge bg-secondary-subtle text-secondary border px-3 py-2";
  heroBadge.textContent = "상태";
  heroTitle.textContent = "대기중";
  heroDesc.textContent = "아직 이벤트가 없습니다.";
}

function setHeroDanger(text) {
  heroBadge.className = "badge bg-danger-subtle text-danger border px-3 py-2";
  heroBadge.textContent = "경고";
  heroTitle.textContent = "위험 감지";
  heroDesc.textContent = text;
}

// 진동: 위험 단계별 패턴 (API는 세기 미지원, 지속시간·횟수로 구분)
function vibrateByLevel(eventType) {
  if (!navigator.vibrate) return;
  if (eventType === "danger") {
    navigator.vibrate([300, 100, 300, 100, 300]);  // 위험: 긴 3회 (강한 느낌)
  } else {
    navigator.vibrate([150, 100, 150]);             // 일상알림: 짧은 2회 (부드러운 느낌)
  }
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
    micTitle.textContent = "마이크 전송 중";
    micDesc.textContent = "실시간 음성을 서버로 전송 중입니다.";
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
  micTitle.textContent = micStream ? "마이크 전송 시작" : "소리 감지 대기중";
  micDesc.textContent  = micStream ? "실시간 음성을 서버로 전송 중입니다." : "마이크 권한 요청 후 전송됩니다.";
  // join이 서버에서 처리된 뒤 오디오 전송 시작 (STT 수신 보장)
  if (micStream && SESSION_ID) {
    setTimeout(() => startAudioSend().catch(console.error), 150);
  }
});

client.on("close", () => {
  stopAudioSend();
  if (micStream) {
    micTitle.textContent = "마이크 승인 완료";
    micDesc.textContent = "마이크를 다시 눌러 재연결하세요.";
  }
  updateMicStatusUI();

  btnFeedbackYes.disabled = true;
  btnFeedbackNo.disabled = true;
});

// 서버가 caption 보내면 (백엔드는 ts_ms 필드 사용)
client.on("caption", (msg) => {
  const text = msg.text || "";
  const danger = isDanger(text);

  appendCaption(text, danger);
  appendLogRow({ ts_ms: msg.ts_ms, ts: msg.ts, type: "caption", text, score: msg.score });

  if (danger) {
    setHeroDanger(text);
    showToast("위험 감지", text, true);
    vibrateByLevel("danger");
  }
});

// 서버가 alert 보내면 (백엔드는 ts_ms, event_id 필드 사용)
client.on("alert", (msg) => {
  const text = msg.text || "";
  const keyword = msg.keyword || "";
  const event_type = msg.event_type || "danger";
  if (msg.event_id != null) lastAlertEventId = msg.event_id;

  appendCaption(`[ALERT] ${text}`, true);
  appendLogRow({ ts_ms: msg.ts_ms, ts: msg.ts, type: "alert", text, keyword, event_type, score: msg.score });

  setHeroDanger(`${keyword ? "["+keyword+"] " : ""}${text}`);
  showToast("알림", `${keyword ? "["+keyword+"] " : ""}${text}`, true);
  vibrateByLevel(event_type);
});

// Feedback: POST /feedback (event_id, vote, session_id)
async function sendFeedback(vote) {
  if (lastAlertEventId == null) {
    showToast("피드백", "대상 알림이 없습니다. 알림이 온 뒤에 눌러주세요.", true);
    return;
  }
  try {
    const res = await fetch(API_BASE + "/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_id: lastAlertEventId,
        vote: vote,
        session_id: SESSION_ID || undefined,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      showToast("피드백", "저장되었습니다.", false);
    } else {
      showToast("피드백 실패", data.detail || res.statusText || "다시 시도해 주세요.", true);
    }
  } catch (e) {
    showToast("오류", "연결할 수 없습니다. 서버를 확인하세요.", true);
  }
}
btnFeedbackYes.addEventListener("click", () => sendFeedback("up"));
btnFeedbackNo.addEventListener("click", () => sendFeedback("down"));

function updateSessionLabel() {
  if (sessionLabel) sessionLabel.textContent = SESSION_ID ? "세션: " + SESSION_ID.slice(0, 8) + "…" : "";
}

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
  if (!btnLogin || !userDropdownWrap) return;
  const provider = getProvider();
  if (provider === "google" || provider === "kakao") {
    btnLogin.classList.add("d-none");
    userDropdownWrap.classList.remove("d-none");
    if (SESSION_ID) loadUserInfo();
  } else {
    btnLogin.classList.remove("d-none");
    userDropdownWrap.classList.add("d-none");
  }
  updateLogSectionVisibility();
}

function updateLogSectionVisibility() {
  const saveWrap = document.getElementById("saveToggleWrap");
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
  if (saveWrap) {
    saveWrap.classList.toggle("d-none", isGuest());
  }
}

async function loadUserInfo() {
  if (!SESSION_ID || !userDropdownName || !userDropdownEmail) return;
  try {
    const res = await fetch(API_BASE + "/auth/me?session_id=" + encodeURIComponent(SESSION_ID));
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      userDropdownName.textContent = data.name || "사용자";
      userDropdownEmail.textContent = data.email || "-";
    } else {
      userDropdownName.textContent = "사용자";
      userDropdownEmail.textContent = "-";
    }
  } catch (_) {
    userDropdownName.textContent = "사용자";
    userDropdownEmail.textContent = "-";
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

  // mouseover 시 드롭다운 표시
  let hideTimer = null;
  userDropdownWrap.addEventListener("mouseenter", () => {
    if (hideTimer) clearTimeout(hideTimer);
    const dropdown = bootstrap.Dropdown.getOrCreateInstance(btnUserIcon);
    dropdown.show();
  });
  userDropdownWrap.addEventListener("mouseleave", () => {
    hideTimer = setTimeout(() => {
      const dropdown = bootstrap.Dropdown.getInstance(btnUserIcon);
      if (dropdown) dropdown.hide();
    }, 150);
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
  if (!SESSION_ID || !captionBox) return;
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID));
    const data = await res.json().catch(() => ({}));
    if (res.ok && data?.ok && data?.data?.font_size != null) {
      applyFontSizeToCaption(data.data.font_size);
    }
  } catch (_) {}
}

// Init
updateMicStatusUI();
setHeroNormal();
updateSessionLabel();
updateUserSection();
updateLogSectionVisibility();
setupUserDropdown();
if (SESSION_ID) loadSettingsForCaption();