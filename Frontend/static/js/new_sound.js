const API_BASE = "http://127.0.0.1:8000";
const SESSION_ID = "S1";

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

// ===== shared state =====
// 1차에서는 업로드 파일만 우선 사용
// 2차/3차에서 녹음 파일도 여기에 통합할 예정
let selectedAudioFile = null;
let selectedAudioSource = null; // "upload" | "record" | null

// ===== recorder state (2차용 대비만 해둠) =====
let mediaRecorder = null;
let recordedChunks = [];
let recordedBlob = null;
let recordedUrl = null;

let t0 = 0;
let timerId = null;

// ===== helpers =====
function setStatus(message, type = "") {
  statusEl.textContent = message;
  statusEl.className = "status small mb-3" + (type ? ` ${type}` : "");
}

function clearStatus() {
  setStatus("");
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

function updateFileMeta(file) {
  if (!file) {
    fileMeta.textContent = "선택된 파일 없음";
    return;
  }

  fileMeta.textContent = `${file.name} (${formatFileSize(file.size)})`;
}

function setSelectedAudio(file, source) {
  selectedAudioFile = file;
  selectedAudioSource = source;
}

function validateStep1Form() {
  const name = (soundName.value || "").trim();
  const category = soundCategory.value;

  if (!selectedAudioFile) {
    return {
      ok: false,
      message: "mp3, wav, webm 파일을 업로드하거나 녹음을 먼저 준비해주세요.",
    };
  }

  if (!name) {
    return {
      ok: false,
      message: "소리 이름을 입력해주세요.",
    };
  }

  if (!category) {
    return {
      ok: false,
      message: "소리 알림 분류를 선택해주세요.",
    };
  }

  return {
    ok: true,
    name,
    category,
    audioFile: selectedAudioFile,
    audioSource: selectedAudioSource,
  };
}

// ===== initial ui =====
updateFileMeta(null);
btnPlay.disabled = true;
btnStop.disabled = true;

// ===== file select =====
fileInput?.addEventListener("change", () => {
  clearStatus();

  const file = fileInput.files?.[0];

  if (!file) {
    setSelectedAudio(null, null);
    updateFileMeta(null);
    return;
  }

  if (!isAllowedAudioFile(file)) {
    fileInput.value = "";
    setSelectedAudio(null, null);
    updateFileMeta(null);
    setStatus("업로드 가능한 파일 형식은 mp3, wav, webm 입니다.", "err");
    return;
  }

  setSelectedAudio(file, "upload");
  updateFileMeta(file);
  setStatus("업로드 파일이 선택되었습니다.", "ok");
});

// ===== live validation helper (optional UX) =====
soundName?.addEventListener("input", () => {
  if (statusEl.classList.contains("err")) clearStatus();
});

soundCategory?.addEventListener("change", () => {
  if (statusEl.classList.contains("err")) clearStatus();
});

// ===== submit (1차: 검증만) =====
btnSubmit?.addEventListener("click", async () => {
  clearStatus();

  const result = validateStep1Form();

  if (!result.ok) {
    setStatus(result.message, "err");
    return;
  }

  const sourceLabel =
    result.audioSource === "upload"
      ? "업로드 파일"
      : result.audioSource === "record"
      ? "녹음 파일"
      : "오디오 파일";

  setStatus(
    `1차 검증 통과: ${sourceLabel}, 이름 "${result.name}", 분류 "${result.category}"`,
    "ok"
  );

  console.log("1차 검증 통과", {
    name: result.name,
    category: result.category,
    audioFile: result.audioFile,
    audioSource: result.audioSource,
  });

  // 4차에서 여기서 FormData 만들어 FastAPI로 전송
});

// ===== placeholders for 2차/3차 =====
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
  if (recordedUrl) {
    URL.revokeObjectURL(recordedUrl);
  }

  recordedUrl = null;
  recordedBlob = null;
  recordedChunks = [];
  audioPreview.hidden = true;
  audioPreview.src = "";
  btnPlay.disabled = true;
  recDot.classList.remove("on");
}