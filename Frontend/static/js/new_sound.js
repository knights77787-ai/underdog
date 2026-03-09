const API_BASE = "http://127.0.0.1:8000";
const SESSION_ID = "S1";

// ===== recorder =====
const btnStart = document.getElementById("btnStart");
const btnStop = document.getElementById("btnStop");
const btnPlay = document.getElementById("btnPlay");
const timerEl = document.getElementById("timer");
const audioPreview = document.getElementById("audioPreview");
const recDot = document.getElementById("recDot");

const fileInput = document.getElementById("fileInput");
const fileMeta = document.getElementById("fileMeta");

const soundName = document.getElementById("soundName");
const soundCategory = document.getElementById("soundCategory");
const btnSubmit = document.getElementById("btnSubmit");
const statusEl = document.getElementById("status");

const refreshListBtn = document.getElementById("refreshListBtn");

let mediaRecorder = null;
let recordedChunks = [];
let recordedBlob = null;
let recordedUrl = null;

let t0 = 0;
let timerId = null;

function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className = "status small mb-3 " + type;
}

function fmtTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

function startTimer() {
  t0 = Date.now();
  timerEl.textContent = "00:00";
  timerId = setInterval(() => {
    const sec = (Date.now() - t0) / 1000;
    timerEl.textContent = fmtTime(sec);
  }, 250);
}

function stopTimer() {
  if (timerId) clearInterval(timerId);
  timerId = null;
}

function resetPreview() {
  if (recordedUrl) URL.revokeObjectURL(recordedUrl);
  recordedUrl = null;
  recordedBlob = null;
  recordedChunks = [];
  audioPreview.hidden = true;
  audioPreview.src = "";
  btnPlay.disabled = true;
}

btnStart?.addEventListener("click", async () => {
  setStatus("");

  try {
    resetPreview();

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeCandidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg"
    ];
    const mimeType = mimeCandidates.find(t => MediaRecorder.isTypeSupported(t)) || "";

    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recordedChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(tr => tr.stop());

      recordedBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
      recordedUrl = URL.createObjectURL(recordedBlob);

      audioPreview.src = recordedUrl;
      audioPreview.hidden = false;

      btnPlay.disabled = false;
      btnStop.disabled = true;
      btnStart.disabled = false;

      recDot.classList.remove("on");
      stopTimer();
      setStatus("녹음이 저장되었습니다. 재생으로 확인하세요.", "ok");
    };

    mediaRecorder.start();
    btnStart.disabled = true;
    btnStop.disabled = false;
    btnPlay.disabled = true;

    recDot.classList.add("on");
    startTimer();
    setStatus("녹음 중...", "");
  } catch (err) {
    console.error(err);

    if (err && (err.name === "NotAllowedError" || err.name === "PermissionDeniedError")) {
      setStatus("마이크 권한이 거부되었습니다. 주소창의 권한 설정에서 마이크를 허용해 주세요.", "err");
    } else if (err && err.name === "NotFoundError") {
      setStatus("마이크 장치를 찾지 못했습니다. 장치 연결 상태를 확인해 주세요.", "err");
    } else if (err && (err.name === "NotReadableError" || err.name === "TrackStartError")) {
      setStatus("다른 앱이 마이크를 사용 중일 수 있습니다. 점유 앱을 종료해 주세요.", "err");
    } else if (err && err.name === "SecurityError") {
      setStatus("보안 문제로 마이크 접근이 차단되었습니다. HTTPS 또는 localhost에서 실행해 주세요.", "err");
    } else {
      setStatus("마이크를 사용할 수 없습니다. 브라우저/권한/환경을 확인해 주세요.", "err");
    }
  }
});

btnStop?.addEventListener("click", () => {
  if (!mediaRecorder) return;
  if (mediaRecorder.state !== "inactive") mediaRecorder.stop();
});

btnPlay?.addEventListener("click", async () => {
  try {
    if (audioPreview.hidden) audioPreview.hidden = false;
    await audioPreview.play();
  } catch (_) {}
});

fileInput?.addEventListener("change", () => {
  setStatus("");
  const f = fileInput.files && fileInput.files[0];

  if (!f) {
    fileMeta.textContent = "선택된 파일 없음";
    return;
  }

  fileMeta.textContent = `${f.name} (${Math.round(f.size / 1024)} KB)`;
  setStatus("업로드 파일이 선택되었습니다. ‘다음’을 누르면 업로드 파일로 저장됩니다.", "");
});

// ===== submit =====
btnSubmit?.addEventListener("click", async () => {
  setStatus("");

  const name = (soundName.value || "").trim();
  const cat = soundCategory.value;

  if (!name) return setStatus("소리 이름을 입력하세요.", "err");
  if (!cat) return setStatus("소리 분류를 선택하세요.", "err");

  const uploadFile = fileInput.files && fileInput.files[0];
  const hasRecorded = !!recordedBlob;

  if (uploadFile && !uploadFile.name.toLowerCase().endsWith(".wav")) {
    return setStatus("서버는 .wav 파일만 지원합니다. WAV 파일을 선택해 주세요.", "err");
  }
  if (hasRecorded && !uploadFile) {
    return setStatus("서버는 .wav만 지원합니다. WAV 파일을 업로드해 주세요.", "err");
  }
  if (!uploadFile) {
    return setStatus("WAV 파일을 업로드하세요.", "err");
  }

  const form = new FormData();
  form.append("name", name);

  form.append("group_type", cat === "danger" ? "warning" : "daily");
  form.append("event_type", cat === "danger" ? "danger" : "alert");
  form.append("file", uploadFile, uploadFile.name);

  btnSubmit.disabled = true;
  setStatus("업로드 중...", "");

  try {
    const url = `${API_BASE}/custom-sounds?session_id=${encodeURIComponent(SESSION_ID)}`;
    const res = await fetch(url, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || "upload failed");
    }

    const data = await res.json();
    const id = data.data && data.data.custom_sound_id != null ? data.data.custom_sound_id : data.sound_id;
    setStatus(`저장 완료${id != null ? ": #" + id : ""}`, "ok");
  } catch (err) {
    console.error(err);
    setStatus("저장 실패. 백엔드 주소 및 CORS 설정을 확인하세요.", "err");
  } finally {
    btnSubmit.disabled = false;
  }
});

// ===== list placeholder =====
refreshListBtn?.addEventListener("click", () => {
  alert("다음 단계에서 GET /custom-sounds 목록 조회를 연결합니다.");
});