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

  const fn = (selectedAudioFile.name || "").toLowerCase();
  if (!fn.endsWith(".wav") && !fn.endsWith(".mp3")) {
    return {
      ok: false,
      message: "등록은 .wav, .mp3 파일만 지원합니다. (서버 제한)",
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

/** category(danger|alert) → API용 group_type(warning|daily), event_type(danger|alert) */
function categoryToApi(category) {
  if (category === "danger") return { group_type: "warning", event_type: "danger" };
  return { group_type: "daily", event_type: "alert" };
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

// ===== submit → POST /custom-sounds =====
btnSubmit?.addEventListener("click", async () => {
  clearStatus();

  const result = validateStep1Form();
  if (!result.ok) {
    setStatus(result.message, "err");
    return;
  }

  const { group_type, event_type } = categoryToApi(result.category);
  const form = new FormData();
  form.append("name", result.name);
  form.append("group_type", group_type);
  form.append("event_type", event_type);
  form.append("file", result.audioFile);

  btnSubmit.disabled = true;
  setStatus("등록 중…", "ok");

  try {
    const url = API_BASE + "/custom-sounds?session_id=" + encodeURIComponent(SESSION_ID);
    const res = await fetch(url, { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));

    if (res.ok && data.ok) {
      setStatus('등록되었습니다. "' + (data.data?.name || result.name) + '"', "ok");
      soundName.value = "";
      fileInput.value = "";
      setSelectedAudio(null, null);
      updateFileMeta(null);
      loadSoundList();
    } else {
      setStatus(data.detail || res.statusText || "등록에 실패했습니다.", "err");
    }
  } catch (e) {
    setStatus("서버에 연결할 수 없습니다. 백엔드를 확인하세요.", "err");
  } finally {
    btnSubmit.disabled = false;
  }
});

// ===== GET /custom-sounds → 목록 탭 =====
const soundListEl = document.getElementById("soundList");
const soundListStatusEl = document.getElementById("soundListStatus");

function loadSoundList() {
  if (!soundListEl || !soundListStatusEl) return;
  soundListStatusEl.textContent = "불러오는 중…";
  const url = API_BASE + "/custom-sounds?session_id=" + encodeURIComponent(SESSION_ID);
  fetch(url)
    .then((res) => res.json())
    .then((data) => {
      if (!data.ok || !Array.isArray(data.data)) {
        soundListStatusEl.textContent = "목록을 불러오지 못했습니다.";
        soundListEl.innerHTML = "";
        return;
      }
      const list = data.data;
      soundListStatusEl.textContent = list.length ? "총 " + list.length + "건" : "등록된 소리가 없습니다.";
      soundListEl.innerHTML = list
        .map(
          (r) => `
        <div class="sound-row" data-id="${r.custom_sound_id}">
          <div class="sound-left">
            <div class="sound-title-line">
              <span class="sound-name">${escapeHtml(r.name)}</span>
              <span class="sound-badge ${r.event_type === "danger" ? "danger" : "alert"}">${r.event_type === "danger" ? "경고" : "일상생활"}</span>
            </div>
            <div class="sound-date text-muted small">${r.group_type} · ${r.event_type}</div>
          </div>
          <div class="sound-right">
            <button type="button" class="btn btn-sm btn-outline-secondary" disabled>수정</button>
            <button type="button" class="btn btn-sm btn-outline-danger" disabled>삭제</button>
          </div>
        </div>`
        )
        .join("");
    })
    .catch(() => {
      soundListStatusEl.textContent = "서버에 연결할 수 없습니다.";
      soundListEl.innerHTML = "";
    });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

document.getElementById("list-tab")?.addEventListener("shown.bs.tab", loadSoundList);

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