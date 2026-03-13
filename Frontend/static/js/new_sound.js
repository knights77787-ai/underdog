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

const btnLogin = document.getElementById("btnLogin");
const userDropdownWrap = document.getElementById("userDropdownWrap");
const btnUserIcon = document.getElementById("btnUserIcon");
const userDropdownName = document.getElementById("userDropdownName");
const userDropdownEmail = document.getElementById("userDropdownEmail");
const userDropdownSoundReg = document.getElementById("userDropdownSoundReg");
const userDropdownLogout = document.getElementById("userDropdownLogout");

// ===== shared state =====
let selectedAudioFile = null;
let selectedAudioSource = null; // "upload" | "record" | null
let previewUrl = null;

let listAudio = null;
let currentPlayingId = null;
let currentPlayButton = null;

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

/** ISO 날짜 문자열을 "YYYY-MM-DD"로 포맷. 수정일이 있으면 수정일을, 없으면 등록일 표시용 라벨/날짜 반환 */
function formatSoundDateLabel(createdAt, updatedAt) {
  const toYmd = (s) => {
    if (!s) return "";
    const d = new Date(s);
    return isNaN(d.getTime()) ? "" : d.toISOString().slice(0, 10);
  };
  const created = toYmd(createdAt);
  const updated = toYmd(updatedAt);
  if (updated && updated !== created) {
    return { label: "수정", date: updated };
  }
  return { label: "등록", date: created };
}

// ===== list audio helpers =====
function normalizeAudioPath(audioPath) {
  if (!audioPath) return "";
  return audioPath.replace(/\\/g, "/");
}

function buildAudioUrl(audioPath) {
  const normalized = normalizeAudioPath(audioPath);
  if (!normalized) return "";

  if (normalized.startsWith("http://") || normalized.startsWith("https://")) {
    return normalized;
  }

  if (normalized.startsWith("/")) {
    return normalized;
  }

  // DB 값이 data/custom_sounds/... 형태인 경우
  if (normalized.startsWith("data/")) {
    return "/" + normalized;
  }

  // 혹시 custom_sounds/... 만 들어오면 /data 붙여줌
  return "/data/" + normalized;
}

function resetPlayButtonUi(btn) {
  if (!btn) return;
  btn.innerHTML = '<i class="bi bi-play-fill"></i>';
  btn.setAttribute("title", "재생");
  btn.setAttribute("aria-label", "재생");
  btn.classList.remove("is-playing");
}

function setPlayButtonUi(btn) {
  if (!btn) return;
  btn.innerHTML = '<i class="bi bi-stop-fill"></i>';
  btn.setAttribute("title", "정지");
  btn.setAttribute("aria-label", "정지");
  btn.classList.add("is-playing");
}

function stopListAudioPlayback() {
  if (listAudio) {
    listAudio.pause();
    listAudio.currentTime = 0;
    listAudio = null;
  }

  if (currentPlayButton) {
    resetPlayButtonUi(currentPlayButton);
  }

  currentPlayingId = null;
  currentPlayButton = null;
}

// ===== preview helpers =====
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

// ===== list render =====
function renderSoundList(list) {
  if (!soundListEl || !soundListStatusEl) return;

  if (!Array.isArray(list) || list.length === 0) {
    soundListStatusEl.textContent = "등록된 소리가 없습니다.";
    soundListEl.innerHTML = "";
    return;
  }

  soundListStatusEl.textContent = `총 ${list.length}건`;

  soundListEl.innerHTML = list
    .map((r) => {
      const { label, date } = formatSoundDateLabel(r.created_at, r.updated_at);
      const dateStr = date ? ` · ${label}: ${date}` : "";
      return `
      <div class="sound-row" data-id="${r.custom_sound_id}">
        <div class="sound-left">
          <div class="sound-title-line">
            <span class="sound-badge ${r.event_type === "danger" ? "danger" : "alert"}">
              ${r.event_type === "danger" ? "경고" : "일상생활"}
            </span>
            <span class="sound-name">${escapeHtml(r.name)}</span>
          </div>
          <div class="sound-date text-muted small">
            ${escapeHtml(r.group_type)} · ${escapeHtml(r.event_type)}${dateStr}
          </div>
        </div>

        <div class="sound-right">
          <button
            type="button"
            class="icon-btn play-toggle-btn"
            data-id="${r.custom_sound_id}"
            data-audio-path="${escapeHtml(r.audio_path || "")}"
            aria-label="재생"
            title="재생"
          >
            <i class="bi bi-play-fill"></i>
          </button>

          <button
            type="button"
            class="btn btn-sm btn-outline-danger delete-sound-btn"
            data-id="${r.custom_sound_id}"
          >
            삭제
          </button>
        </div>
      </div>
    `;
    })
    .join("");
}

async function loadSoundList() {
  if (!soundListEl || !soundListStatusEl) return;

  stopListAudioPlayback();
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

  if (!navigator?.mediaDevices?.getUserMedia) {
    console.error("getUserMedia not available", navigator, navigator?.mediaDevices);
    setStatus("이 환경에서는 마이크 기능이 지원되지 않아요 (HTTPS/localhost 또는 브라우저 확인).", "err");
    return;
  }

  try {
    resetRecordedState();

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    const mimeCandidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
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
  stopListAudioPlayback();
  clearStatus();
});

// ===== list audio play / stop / delete =====
soundListEl?.addEventListener("click", async (e) => {
  const playBtn = e.target.closest(".play-toggle-btn");
  const deleteBtn = e.target.closest(".delete-sound-btn");

  // 삭제
  if (deleteBtn) {
    const soundId = deleteBtn.dataset.id;
    if (!soundId) return;

    const ok = window.confirm(
      "정말 삭제하시겠습니까? 이 소리는 즉시 삭제되며 복구할 수 없습니다."
    );
    if (!ok) return;

    stopListAudioPlayback();

    try {
      soundListStatusEl.textContent = "삭제 중…";
      const url =
        API_BASE +
        "/custom-sounds/" +
        encodeURIComponent(soundId) +
        "?session_id=" +
        encodeURIComponent(SESSION_ID);

      const res = await fetch(url, { method: "DELETE" });
      const data = await res.json().catch(() => ({}));

      if (!res.ok || !data.ok) {
        setStatus(data.detail || "삭제에 실패했습니다.", "err");
        soundListStatusEl.textContent = "삭제 실패";
        await loadSoundList();
        return;
      }

      setStatus("소리가 삭제되었습니다.", "ok");
      await loadSoundList();
    } catch (err) {
      console.error(err);
      setStatus("삭제 요청 중 오류가 발생했습니다.", "err");
      soundListStatusEl.textContent = "삭제 오류";
      await loadSoundList();
    }
    return;
  }

  // 재생
  if (!playBtn) return;

  const soundId = playBtn.dataset.id;
  const audioPath = playBtn.dataset.audioPath;

  if (!audioPath) {
    setStatus("재생할 오디오 경로가 없습니다.", "err");
    return;
  }

  if (currentPlayingId === soundId && listAudio) {
    stopListAudioPlayback();
    return;
  }

  stopListAudioPlayback();

  const audioUrl = buildAudioUrl(audioPath);

  try {
    listAudio = new Audio(audioUrl);
    currentPlayingId = soundId;
    currentPlayButton = playBtn;

    setPlayButtonUi(playBtn);

    listAudio.addEventListener("ended", () => {
      stopListAudioPlayback();
    });

    listAudio.addEventListener("error", () => {
      stopListAudioPlayback();
      setStatus("오디오 파일을 불러오지 못했습니다.", "err");
    });

    await listAudio.play();
  } catch (err) {
    console.error(err);
    stopListAudioPlayback();
    setStatus("오디오를 재생할 수 없습니다.", "err");
  }
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

// ===== 사용자 섹션 =====
// 새로운 소리 페이지는 로그인한 사용자만 접근 가능(드롭다운 '소리등록'으로만 진입).
// session_id가 있으면 항상 사용자 아이콘 표시.
async function updateUserSection() {
  if (!btnLogin || !userDropdownWrap) return;
  const urlSessionId = new URLSearchParams(document.location.search).get("session_id");
  if (!urlSessionId) {
    btnLogin.classList.remove("d-none");
    userDropdownWrap.classList.add("d-none");
    return;
  }
  // session_id 있음 = 로그인 사용자. 항상 사용자 아이콘 표시
  btnLogin.classList.add("d-none");
  userDropdownWrap.classList.remove("d-none");
  try {
    const res = await fetch(API_BASE + "/auth/me?session_id=" + encodeURIComponent(urlSessionId));
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      if (userDropdownName) userDropdownName.textContent = data.name || "사용자";
      if (userDropdownEmail) userDropdownEmail.textContent = data.email || "-";
    } else {
      if (userDropdownName) userDropdownName.textContent = "사용자";
      if (userDropdownEmail) userDropdownEmail.textContent = "-";
    }
  } catch (_) {
    if (userDropdownName) userDropdownName.textContent = "사용자";
    if (userDropdownEmail) userDropdownEmail.textContent = "-";
  }
}

function setupUserDropdown() {
  if (!userDropdownWrap || !btnUserIcon || !userDropdownSoundReg || !userDropdownLogout) return;
  userDropdownSoundReg.addEventListener("click", (e) => {
    e.preventDefault();
    const url = "/new-sound" + (SESSION_ID && SESSION_ID !== "S1" ? "?session_id=" + encodeURIComponent(SESSION_ID) : "");
    window.location.href = url;
  });
  userDropdownLogout.addEventListener("click", (e) => {
    e.preventDefault();
    window.location.href = "/";
  });
}

updateUserSection();
setupUserDropdown();