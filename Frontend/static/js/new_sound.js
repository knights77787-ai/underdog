const API_BASE = window.APP_CONFIG?.API_BASE || "http://127.0.0.1:8000";
const SESSION_ID = (function () {
  const params = new URLSearchParams(document.location.search);
  return params.get("session_id") || "S1";
})();

// ===== elements =====
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

const soundListEl = document.getElementById("soundList");
const soundListStatusEl = document.getElementById("soundListStatus");

// ===== shared state =====
let selectedAudioFile = null;
let selectedAudioSource = null; // "upload" | "record" | null
let previewUrl = null;

// ===== recorder state =====
let mediaRecorder = null;
let recordedChunks = [];
let recordedBlob = null;
let recordedUrl = null;

let t0 = 0;
let timerId = null;

// ===== helpers =====
function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className = "status small mb-3" + (type ? ` ${type}` : "");
}

function clearStatus() {
  setStatus("");
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

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return `${bytes} B`;

  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;

  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

function isAllowedAudioFile(file) {
  if (!file) return false;
  const allowedExtensions = [".mp3", ".wav", ".webm"];
  const lowerName = file.name.toLowerCase();
  return allowedExtensions.some((ext) => lowerName.endsWith(ext));
}

function categoryToApi(category) {
  if (category === "danger") {
    return { group_type: "warning", event_type: "danger" };
  }
  return { group_type: "daily", event_type: "alert" };
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

function revokePreviewUrl() {
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }
}

function setPreviewFromFile(file) {
  revokePreviewUrl();

  if (!file) {
    audioPreview.hidden = true;
    audioPreview.src = "";
    btnPlay.disabled = true;
    return;
  }

  previewUrl = URL.createObjectURL(file);
  audioPreview.src = previewUrl;
  audioPreview.hidden = false;
  btnPlay.disabled = false;
}

function setSelectedAudio(file, source) {
  selectedAudioFile = file;
  selectedAudioSource = source;
  setPreviewFromFile(file);
}

function updateFileMeta(file) {
  if (!file) {
    fileMeta.textContent = "선택된 파일 없음";
    return;
  }
  fileMeta.textContent = `${file.name} (${formatFileSize(file.size)})`;
}

function resetRecordedState() {
  recordedChunks = [];
  recordedBlob = null;

  if (recordedUrl) {
    URL.revokeObjectURL(recordedUrl);
    recordedUrl = null;
  }
}

function resetSelection() {
  setSelectedAudio(null, null);
  updateFileMeta(null);
  fileInput.value = "";
  resetRecordedState();
}

function validateBeforeSubmit() {
  const name = (soundName.value || "").trim();
  const category = soundCategory.value;

  if (!selectedAudioFile) {
    return { ok: false, message: "업로드 파일을 선택하거나 녹음을 먼저 진행해주세요." };
  }

  if (!name) {
    return { ok: false, message: "소리 이름을 입력해주세요." };
  }

  if (!category) {
    return { ok: false, message: "소리 알림 분류를 선택해주세요." };
  }

  if (!isAllowedAudioFile(selectedAudioFile)) {
    return { ok: false, message: "지원하는 파일 형식은 mp3, wav, webm 입니다." };
  }

  return {
    ok: true,
    name,
    category,
    audioFile: selectedAudioFile,
    audioSource: selectedAudioSource,
  };
}

function resetRecordingUi() {
  btnStart.disabled = false;
  btnStop.disabled = true;
  recDot.classList.remove("on");
  stopTimer();
  timerEl.textContent = "00:00";
}

function renderSoundList(list) {
  if (!soundListEl || !soundListStatusEl) return;

  if (!Array.isArray(list) || list.length === 0) {
    soundListStatusEl.textContent = "등록된 소리가 없습니다.";
    soundListEl.innerHTML = "";
    return;
  }

  soundListStatusEl.textContent = `총 ${list.length}건`;

  soundListEl.innerHTML = list
    .map(
      (r) => `
      <div class="sound-row" data-id="${r.custom_sound_id}">
        <div class="sound-left">
          <div class="sound-title-line">
            <span class="sound-name">${escapeHtml(r.name)}</span>
            <span class="sound-badge ${r.event_type === "danger" ? "danger" : "alert"}">
              ${r.event_type === "danger" ? "경고" : "일상생활"}
            </span>
          </div>
          <div class="sound-date text-muted small">
            ${escapeHtml(r.group_type)} · ${escapeHtml(r.event_type)}
          </div>
        </div>

        <div class="sound-right">
          <button type="button" class="btn btn-sm btn-outline-secondary" disabled>수정</button>
          <button type="button" class="btn btn-sm btn-outline-danger" disabled>삭제</button>
        </div>
      </div>
    `
    )
    .join("");
}

async function loadSoundList() {
  if (!soundListEl || !soundListStatusEl) return;

  soundListStatusEl.textContent = "불러오는 중…";

  try {
    const url = API_BASE + "/custom-sounds?session_id=" + encodeURIComponent(SESSION_ID);
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));

    if (!res.ok || !data.ok || !Array.isArray(data.data)) {
      soundListStatusEl.textContent = "목록을 불러오지 못했습니다.";
      soundListEl.innerHTML = "";
      return;
    }

    renderSoundList(data.data);
  } catch (err) {
    console.error(err);
    soundListStatusEl.textContent = "서버에 연결할 수 없습니다.";
    soundListEl.innerHTML = "";
  }
}

// ===== initial ui =====
updateFileMeta(null);
btnStop.disabled = true;
btnPlay.disabled = true;
audioPreview.hidden = true;

// ===== file select =====
fileInput?.addEventListener("change", () => {
  clearStatus();

  const f = fileInput.files?.[0];

  if (!f) {
    if (selectedAudioSource === "upload") {
      setSelectedAudio(null, null);
      updateFileMeta(null);
    }
    return;
  }

  if (!isAllowedAudioFile(f)) {
    fileInput.value = "";
    updateFileMeta(null);
    setSelectedAudio(null, null);
    setStatus("업로드 가능한 파일 형식은 mp3, wav, webm 입니다.", "err");
    return;
  }

  setSelectedAudio(f, "upload");
  updateFileMeta(f);
  setStatus("업로드 파일이 선택되었습니다.", "ok");
});

// ===== recorder =====
btnStart?.addEventListener("click", async () => {
  clearStatus();

  try {
    resetRecordedState();

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    const mimeCandidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg"
    ];
    const mimeType = mimeCandidates.find((t) => MediaRecorder.isTypeSupported(t)) || "";

    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recordedChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        recordedChunks.push(e.data);
      }
    };

    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((tr) => tr.stop());

      const blobType = mediaRecorder.mimeType || "audio/webm";
      recordedBlob = new Blob(recordedChunks, { type: blobType });

      const ext = blobType.includes("ogg") ? "ogg" : "webm";
      const recordedFile = new File([recordedBlob], `recorded_sound.${ext}`, {
        type: blobType,
      });

      setSelectedAudio(recordedFile, "record");
      updateFileMeta(recordedFile);

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
    setStatus("녹음 중...", "ok");
  } catch (err) {
    console.error(err);

    if (err?.name === "NotAllowedError" || err?.name === "PermissionDeniedError") {
      setStatus("마이크 권한이 거부되었습니다. 주소창에서 마이크를 허용해주세요.", "err");
    } else if (err?.name === "NotFoundError") {
      setStatus("마이크 장치를 찾지 못했습니다.", "err");
    } else if (err?.name === "NotReadableError" || err?.name === "TrackStartError") {
      setStatus("다른 앱이 마이크를 사용 중일 수 있습니다.", "err");
    } else if (err?.name === "SecurityError") {
      setStatus("HTTPS 또는 localhost 환경에서 실행해주세요.", "err");
    } else {
      setStatus("마이크를 사용할 수 없습니다. 브라우저/권한/환경을 확인해주세요.", "err");
    }

    resetRecordingUi();
  }
});

btnStop?.addEventListener("click", () => {
  if (!mediaRecorder) return;
  if (mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
});

btnPlay?.addEventListener("click", async () => {
  try {
    if (audioPreview.hidden) {
      audioPreview.hidden = false;
    }
    audioPreview.currentTime = 0;
    await audioPreview.play();
  } catch (err) {
    console.error(err);
  }
});

// ===== tabs =====
document.getElementById("list-tab")?.addEventListener("shown.bs.tab", () => {
  loadSoundList();
});

document.getElementById("register-tab")?.addEventListener("shown.bs.tab", () => {
  clearStatus();
});

// ===== submit =====
btnSubmit?.addEventListener("click", async () => {
  clearStatus();

  const result = validateBeforeSubmit();
  if (!result.ok) {
    setStatus(result.message, "err");
    return;
  }

  const { group_type, event_type } = categoryToApi(result.category);

  const form = new FormData();
  form.append("name", result.name);
  form.append("group_type", group_type);
  form.append("event_type", event_type);
  form.append("file", result.audioFile, result.audioFile.name);

  btnSubmit.disabled = true;
  setStatus("등록 중…", "ok");

  try {
    const url = API_BASE + "/custom-sounds?session_id=" + encodeURIComponent(SESSION_ID);
    const res = await fetch(url, {
      method: "POST",
      body: form,
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok || !data.ok) {
      setStatus(data.detail || res.statusText || "등록에 실패했습니다.", "err");
      return;
    }

    setStatus(`등록되었습니다. "${data.data?.name || result.name}"`, "ok");

    soundName.value = "";
    soundCategory.value = "";
    resetSelection();

    await loadSoundList();
  } catch (err) {
    console.error(err);
    setStatus("서버에 연결할 수 없습니다. 백엔드를 확인하세요.", "err");
  } finally {
    btnSubmit.disabled = false;
  }
});