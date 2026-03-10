// Frontend/static/js/live.js
// =======================
// 0) 서버 주소 · 세션 (백엔드 연동: join 시 사용)
// =======================
const API_BASE = window.APP_CONFIG?.API_BASE || "http://127.0.0.1:8000";
const WS_URL = (window.APP_CONFIG?.WS_URL || "ws://127.0.0.1:8000/ws").replace(/^http/, "ws");
let SESSION_ID = (function () {
  const params = new URLSearchParams(document.location.search);
  return params.get("session_id") || null;
})();
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
const CHUNK_SAMPLES = 8000; // 0.5 sec at 16kHz
const WORKLET_URL = (window.location.origin || "http://127.0.0.1:8000") + "/static/js/audio-processor-worklet.js";

// =======================
// 1) DOM
// =======================
const wsBadge = document.getElementById("wsBadge");
const btnConnect = document.getElementById("btnConnect");
const btnDisconnect = document.getElementById("btnDisconnect");

const saveToggle = document.getElementById("saveToggle");

const heroBadge = document.getElementById("heroBadge");
const heroTitle = document.getElementById("heroTitle");
const heroDesc  = document.getElementById("heroDesc");
const btnFeedbackYes = document.getElementById("btnFeedbackYes");
const btnFeedbackNo  = document.getElementById("btnFeedbackNo");

const logTbody = document.getElementById("logTbody");

const micTitle = document.getElementById("micTitle");
const micDesc  = document.getElementById("micDesc");
const btnMic   = document.getElementById("btnMic");
const micPermissionModal = document.getElementById("micPermissionModal");
const micPermissionConfirm = document.getElementById("micPermissionConfirm");
const micStopModal = document.getElementById("micStopModal");
const micStopConfirm = document.getElementById("micStopConfirm");

// 모달 표시 시 aria-hidden 보정 (포커스 가능한데 숨김 처리되면 접근성 경고 발생)
if (micPermissionModal) {
  micPermissionModal.addEventListener("shown.bs.modal", () => micPermissionModal.setAttribute("aria-hidden", "false"));
  micPermissionModal.addEventListener("hidden.bs.modal", () => micPermissionModal.setAttribute("aria-hidden", "true"));
}
if (micStopModal) {
  micStopModal.addEventListener("shown.bs.modal", () => micStopModal.setAttribute("aria-hidden", "false"));
  micStopModal.addEventListener("hidden.bs.modal", () => micStopModal.setAttribute("aria-hidden", "true"));
}

const captionBox = document.getElementById("captionBox");

const testInput = document.getElementById("testInput");
const btnSendCaption = document.getElementById("btnSendCaption");

const toastContainer = document.getElementById("toastContainer");
const sessionLabel = document.getElementById("sessionLabel");
const loginLabel = document.getElementById("loginLabel");

// 설정 패널
const settingFontSize = document.getElementById("settingFontSize");
const settingAlertEnabled = document.getElementById("settingAlertEnabled");
const settingCooldownSec = document.getElementById("settingCooldownSec");
const settingAutoScroll = document.getElementById("settingAutoScroll");
const btnSettingsSave = document.getElementById("btnSettingsSave");
const settingsStatus = document.getElementById("settingsStatus");
const settingsCollapse = document.getElementById("settingsCollapse");

// =======================
// 2) Helpers
// =======================
function setBadge(state) {
  wsBadge.className = "badge ms-2";
  if (state === "disconnected") {
    wsBadge.classList.add("text-bg-secondary");
    wsBadge.textContent = "Disconnected";
  } else {
    wsBadge.classList.add("text-bg-primary");
    wsBadge.textContent = "Connected";
  }
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
}

// 마이크 권한 요청 + 해제 유틸
function requestMicPermission() {
  navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    micStream = stream;
    micTitle.textContent = "마이크 승인 완료";
    micDesc.textContent = client.isConnected && SESSION_ID
      ? "전송 시작 중…"
      : "Connect 후 자동 전송됩니다.";
    if (client.isConnected && SESSION_ID) startAudioSend().catch(console.error);
  }).catch(() => {
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
    currentSr = audioContext.sampleRate;
    audioSource = audioContext.createMediaStreamSource(micStream);
    rawBuffer = [];

    if (audioContext.audioWorklet && typeof audioContext.audioWorklet.addModule === "function") {
      await audioContext.audioWorklet.addModule(WORKLET_URL);
      audioWorkletNode = new AudioWorkletNode(audioContext, "mic-processor");
      audioWorkletNode.port.onmessage = (e) => {
        if (e.data?.type === "audio" && e.data.samples) {
          for (let i = 0; i < e.data.samples.length; i++) rawBuffer.push(e.data.samples[i]);
          flushRawToChunks();
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
      };
      const gain = audioContext.createGain();
      gain.gain.value = 0;
      gain.connect(audioContext.destination);
      audioSource.connect(audioProcessor);
      audioProcessor.connect(gain);
    }
    micTitle.textContent = "마이크 전송 중";
    micDesc.textContent = "실시간 음성을 서버로 전송 중입니다.";
  } catch (e) {
    console.error("audio_chunk start failed:", e);
    micTitle.textContent = "마이크 오류";
    micDesc.textContent = "오디오 초기화에 실패했습니다.";
  }
}

btnMic.addEventListener("click", () => {
  // 이미 마이크 사용 중이면 종료 안내 모달
  if (micStream) {
    if (micStopModal && micStopConfirm && window.bootstrap) {
      const modal = new bootstrap.Modal(micStopModal);
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

  // 마이크 미사용 → 권한 안내 모달 후 권한 요청
  if (micPermissionModal && micPermissionConfirm && window.bootstrap) {
    const modal = new bootstrap.Modal(micPermissionModal);
    micPermissionModal.setAttribute("aria-hidden", "false");
    modal.show();
    micPermissionConfirm.addEventListener("click", () => {
      modal.hide();
      requestMicPermission();
    }, { once: true });
  } else {
    requestMicPermission();
  }
});

// =======================
// 4) WS
// =======================
const client = new WSClient(WS_URL);

client.on("open", () => {
  setBadge("connected");
  btnConnect.disabled = true;
  btnDisconnect.disabled = false;

  // 백엔드는 join을 받아야 이 세션으로 caption/alert를 보냄
  client.send("join", { session_id: SESSION_ID });

  btnSendCaption.disabled = false;
  btnFeedbackYes.disabled = false;
  btnFeedbackNo.disabled = false;

  micTitle.textContent = micStream ? "마이크 전송 시작" : "소리 감지 대기중";
  micDesc.textContent  = micStream ? "실시간 음성을 서버로 전송 중입니다." : "마이크 권한 요청 후 전송됩니다.";
  if (micStream && SESSION_ID) startAudioSend().catch(console.error);
});

client.on("close", () => {
  stopAudioSend();
  if (micStream) {
    micTitle.textContent = "마이크 승인 완료";
    micDesc.textContent = "Connect 후 자동 전송됩니다.";
  }
  setBadge("disconnected");
  btnConnect.disabled = false;
  btnDisconnect.disabled = true;

  btnSendCaption.disabled = true;
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
});

// Buttons
btnConnect.addEventListener("click", async () => {
  if (!SESSION_ID) {
    btnConnect.disabled = true;
    try {
      const res = await fetch(API_BASE + "/auth/guest", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (data.ok && data.session_id) {
        SESSION_ID = data.session_id;
        const url = new URL(document.location.href);
        url.searchParams.set("session_id", SESSION_ID);
        history.replaceState(null, "", url.toString());
        updateSessionLabel();
        updateLoginLabel();
        loadSettings();
      } else {
        const msg = data.detail || (res.ok ? "세션 ID를 받지 못했습니다." : "서버 오류 " + res.status);
        showToast("세션 발급 실패", msg, true);
        btnConnect.disabled = false;
        return;
      }
    } catch (e) {
      showToast("오류", "서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.", true);
      btnConnect.disabled = false;
      return;
    } finally {
      btnConnect.disabled = false;
    }
  }
  client.connect();
});
btnDisconnect.addEventListener("click", () => client.disconnect());

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

// 타이핑 자막 전송 (서버 send_caption 처리 필요)
btnSendCaption.addEventListener("click", () => {
  const text = testInput.value.trim();
  if (!text) return;
  if (!SESSION_ID) {
    if (typeof showToast === "function") showToast("자막 전송", "먼저 Connect를 눌러 세션을 만드세요.", true);
    return;
  }
  const sent = client.send("send_caption", {
    text,
    save: saveToggle.checked,
    session_id: SESSION_ID,
  });
  testInput.value = "";
  if (!sent && typeof showToast === "function") {
    showToast("자막 전송", "WebSocket이 연결되지 않았습니다. Connect 후 다시 시도하세요.", true);
  }
});

function updateSessionLabel() {
  if (sessionLabel) sessionLabel.textContent = SESSION_ID ? "세션: " + SESSION_ID.slice(0, 8) + "…" : "";
}

// 로그인 상태 표시 (URL의 provider 또는 게스트)
function updateLoginLabel() {
  if (!loginLabel) return;
  const params = new URLSearchParams(document.location.search);
  const provider = params.get("provider");
  if (SESSION_ID) {
    if (provider === "google") {
      loginLabel.textContent = "Google 로그인됨";
      loginLabel.style.display = "";
    } else if (provider === "kakao") {
      loginLabel.textContent = "카카오 로그인됨";
      loginLabel.style.display = "";
    } else {
      loginLabel.textContent = "게스트";
      loginLabel.style.display = "";
    }
  } else {
    loginLabel.style.display = "none";
  }
}

// =======================
// 설정 패널 (GET/POST /settings)
// =======================
function setSettingsStatus(msg, isError) {
  if (settingsStatus) {
    settingsStatus.textContent = msg || "";
    settingsStatus.className = "col-auto small " + (isError ? "text-danger" : "text-muted");
  }
}

function applyFontSizeToCaption(px) {
  if (captionBox && px != null) {
    const num = Math.min(60, Math.max(10, Number(px)));
    captionBox.style.fontSize = num + "px";
  }
}

async function loadSettings() {
  if (!SESSION_ID || !settingFontSize) return;
  setSettingsStatus("불러오는 중…", false);
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID));
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok || !data.data) {
      setSettingsStatus("불러오기 실패", true);
      return;
    }
    const d = data.data;
    if (settingFontSize) settingFontSize.value = d.font_size ?? 20;
    if (settingAlertEnabled) settingAlertEnabled.checked = d.alert_enabled !== false;
    if (settingCooldownSec) settingCooldownSec.value = d.cooldown_sec ?? 5;
    if (settingAutoScroll) settingAutoScroll.checked = d.auto_scroll !== false;
    applyFontSizeToCaption(d.font_size);
    setSettingsStatus("불러옴", false);
  } catch (e) {
    setSettingsStatus("연결 실패", true);
  }
}

async function saveSettings() {
  if (!SESSION_ID) {
    setSettingsStatus("세션이 없습니다. Connect 하세요.", true);
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

  setSettingsStatus("저장 중…", false);
  try {
    const res = await fetch(API_BASE + "/settings?session_id=" + encodeURIComponent(SESSION_ID), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      setSettingsStatus("저장됨", false);
      applyFontSizeToCaption(body.font_size);
      showToast("설정", "저장되었습니다.", false);
    } else {
      setSettingsStatus(data.detail || "저장 실패", true);
    }
  } catch (e) {
    setSettingsStatus("연결 실패", true);
  }
}

if (btnSettingsSave) btnSettingsSave.addEventListener("click", saveSettings);
if (settingsCollapse) {
  settingsCollapse.addEventListener("show.bs.collapse", function () {
    if (SESSION_ID) loadSettings();
  });
}

// Init
setBadge("disconnected");
setHeroNormal();
updateSessionLabel();
updateLoginLabel();
if (SESSION_ID) loadSettings();