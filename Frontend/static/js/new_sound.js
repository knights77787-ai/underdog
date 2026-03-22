// 배포(HTTPS)에서는 config 미적재 시에도 현재 오리진 사용 (API/WS 도메인 일치)
const API_BASE = window.APP_CONFIG?.API_BASE || (typeof location !== "undefined" && location.origin && !/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(location.origin) ? location.origin : "http://127.0.0.1:8000");
const SESSION_STORAGE_KEY = "underdog_session_id";
const PROVIDER_STORAGE_KEY = "underdog_provider";

function getProvider() {
  try {
    return (localStorage.getItem(PROVIDER_STORAGE_KEY) || "").toLowerCase();
  } catch (_) {
    return "";
  }
}
// 라이브와 동일한 session_id 사용 → 등록한 소리가 실시간 감지에 연동됨
let SESSION_ID = (function () {
  const params = new URLSearchParams(document.location.search);
  const fromUrl = params.get("session_id");
  if (fromUrl) {
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, fromUrl);
    } catch (_) {}
    return fromUrl;
  }
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) return stored;
    const fallback = "S1";
    localStorage.setItem(SESSION_STORAGE_KEY, fallback);
    return fallback;
  } catch (_) {
    return "S1";
  }
})();
if (SESSION_ID) {
  try {
    window.UnderdogApp?.setSessionId(SESSION_ID);
  } catch (_) {}
}

// ===== elements =====
const btnStart = document.getElementById("btnStart");
const btnStop = document.getElementById("btnStop");
const recRerecordHint = document.getElementById("recRerecordHint");
const timerEl = document.getElementById("timer");
const audioPreview = document.getElementById("audioPreview");
const recIndicatorWrap = document.getElementById("recIndicatorWrap");

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
const userDropdownSettings = document.getElementById("userDropdownSettings");
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

/** 녹음 완료 후 실제 오디오 길이로 타이머 표시 갱신 */
function updateTimerFromAudioDuration(audioEl) {
  if (!audioEl) return;
  const onLoaded = () => {
    if (Number.isFinite(audioEl.duration) && timerEl) {
      timerEl.textContent = fmtTime(audioEl.duration);
    }
    audioEl.removeEventListener("loadedmetadata", onLoaded);
  };
  audioEl.addEventListener("loadedmetadata", onLoaded);
  if (audioEl.readyState >= 1) {
    onLoaded();
  }
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
  const allowedExtensions = [".mp3", ".wav", ".weba", ".m4a"];
  const lowerName = file.name.toLowerCase();
  return allowedExtensions.some((ext) => lowerName.endsWith(ext));
}

function categoryToApi(category) {
  return { event_type: category };
}

function eventTypeDisplay(eventType) {
  const map = { danger: "경고", caution: "주의", alert: "생활알림" };
  return map[eventType] || eventType || "";
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

  const base = (typeof API_BASE !== "undefined" ? API_BASE : "").replace(/\/$/, "");
  let path = normalized;

  if (normalized.startsWith("/")) {
    path = normalized;
  } else if (normalized.startsWith("data/")) {
    path = "/" + normalized;
  } else {
    path = "/data/" + normalized;
  }
  return base ? base + path : path;
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

function setPreviewFromFile(file, source) {
  revokePreviewUrl();

  if (!file) {
    audioPreview.hidden = true;
    audioPreview.src = "";
    recRerecordHint?.classList.add("d-none");
    if (timerEl) timerEl.textContent = "00:00";
    return;
  }

  previewUrl = URL.createObjectURL(file);
  audioPreview.src = previewUrl;
  audioPreview.hidden = false;
  if (source === "record") {
    recRerecordHint?.classList.remove("d-none");
  } else {
    recRerecordHint?.classList.add("d-none");
  }
}

function setSelectedAudio(file, source) {
  selectedAudioFile = file;
  selectedAudioSource = source;
  setPreviewFromFile(file, source);
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
    return { ok: false, message: "지원하는 파일 형식은 mp3, wav, weba, m4a 입니다." };
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
  recIndicatorWrap?.classList.remove("recording");
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
      const canPlay = r.audio_available !== false;
      const playTitle = canPlay
        ? "재생"
        : "보관 기간이 지나 원본 파일이 없어 재생할 수 없습니다. 목록에는 그대로 보이며 실시간 감지는 유지됩니다.";
      const playDisabled = canPlay ? "" : " disabled";
      const playClass = canPlay ? "icon-btn play-toggle-btn" : "icon-btn play-toggle-btn opacity-50";
      return `
      <div class="sound-row" data-id="${r.custom_sound_id}">
        <div class="sound-left">
          <div class="sound-title-line">
            <span class="sound-badge ${r.event_type === "danger" ? "danger" : r.event_type === "caution" ? "caution" : "daily"}">
              ${escapeHtml(eventTypeDisplay(r.event_type))}
            </span>
            <span class="sound-name">${escapeHtml(r.name)}</span>
          </div>
          <div class="sound-date text-muted small">
            ${escapeHtml(eventTypeDisplay(r.event_type))}${dateStr}
          </div>
        </div>

        <div class="sound-right">
          <button
            type="button"
            class="${playClass}"
            data-id="${r.custom_sound_id}"
            data-audio-path="${escapeHtml(r.audio_path || "")}"
            aria-label="${canPlay ? "재생" : "재생 불가(보관 기간 만료)"}"
            title="${escapeHtml(playTitle)}"
            tabindex="0"${playDisabled}
          >
            <i class="bi bi-play-fill"></i>
          </button>

          <button
            type="button"
            class="icon-btn delete-sound-btn"
            data-id="${r.custom_sound_id}"
            aria-label="삭제"
            title="삭제"
            tabindex="0"
          >
            <i class="bi bi-trash-fill"></i>
          </button>
        </div>
      </div>
    `;
    })
    .join("");
}

/** 기존 등록 소리 목록을 API에서 가져옴. { ok, data, audio_retention_hours } 반환 */
async function fetchExistingSoundList() {
  try {
    const url = API_BASE + "/custom-sounds?session_id=" + encodeURIComponent(SESSION_ID);
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    const ok = res.ok && data.ok && Array.isArray(data.data);
    const hours =
      typeof data.audio_retention_hours === "number" ? data.audio_retention_hours : null;
    return { ok, data: ok ? data.data : [], audio_retention_hours: hours };
  } catch {
    return { ok: false, data: [], audio_retention_hours: null };
  }
}

async function loadSoundList() {
  if (!soundListEl || !soundListStatusEl) return;

  stopListAudioPlayback();
  soundListStatusEl.textContent = "불러오는 중…";

  const retentionNote = document.getElementById("soundListRetentionNote");

  try {
    const { ok, data, audio_retention_hours } = await fetchExistingSoundList();
    if (!ok) {
      soundListStatusEl.textContent = "목록을 불러오지 못했습니다.";
      soundListEl.innerHTML = "";
      return;
    }
    if (retentionNote && audio_retention_hours != null && audio_retention_hours > 0) {
      const days = audio_retention_hours / 24;
      const dayLabel = Number.isInteger(days) ? String(days) : String(Math.round(days * 10) / 10);
      retentionNote.textContent = `등록 시점부터 원본은 최대 약 ${dayLabel}일간 목록에서 재생할 수 있습니다. 이후에는 서버의 원본 파일만 없어져 재생은 할 수 없고, 등록한 소리 항목은 목록에 그대로 보이며 실시간 감지(임베딩)는 유지됩니다.`;
    }
    if (data.length === 0) {
      soundListStatusEl.textContent = "등록된 소리가 없습니다.";
    } else {
      soundListStatusEl.textContent = `총 ${data.length}건`;
    }
    renderSoundList(data);
  } catch (err) {
    console.error(err);
    soundListStatusEl.textContent = "서버에 연결할 수 없습니다.";
    soundListEl.innerHTML = "";
  }
}

// ===== initial ui =====
updateFileMeta(null);
btnStop.disabled = true;
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
    setStatus("업로드 가능한 파일 형식은 mp3, wav, weba, m4a 입니다.", "err");
    return;
  }

  setSelectedAudio(f, "upload");
  updateTimerFromAudioDuration(audioPreview);
  updateFileMeta(f);
  setStatus("업로드 파일이 선택되었습니다.", "ok");
});

// ===== recorder =====
/** 권한 허용 직후 스트림으로 MediaRecorder 시작 (메인 live.js와 같이 getUserMedia는 사용자 제스처 턴에서 동기 호출) */
function startMediaRecorderFromStream(stream) {
  const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm"];
  const mimeType = mimeCandidates.find((t) => MediaRecorder.isTypeSupported(t)) || "";

  try {
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  } catch (e) {
    console.error("MediaRecorder init failed", e);
    try {
      stream.getTracks().forEach((tr) => tr.stop());
    } catch (_) {}
    setStatus("이 브라우저에서 녹음 형식을 시작할 수 없습니다.", "err");
    resetRecordingUi();
    return;
  }

  recordedChunks = [];

  stream.getTracks().forEach((t) => {
    t.onended = () => {
      if (!mediaRecorder || mediaRecorder.state === "inactive") return;
      try {
        mediaRecorder.stop();
      } catch (_) {}
      resetRecordingUi();
      setStatus("마이크 연결이 끊겼습니다.", "err");
    };
  });

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) {
      recordedChunks.push(e.data);
    }
  };

  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((tr) => tr.stop());

    const blobType = mediaRecorder.mimeType || "audio/webm";
    recordedBlob = new Blob(recordedChunks, { type: blobType });

      const ext = blobType.includes("ogg") ? "ogg" : "weba";
      const recordedFile = new File([recordedBlob], `recorded_sound.${ext}`, {
        type: blobType,
      });

    stopTimer();
    setSelectedAudio(recordedFile, "record");
    updateTimerFromAudioDuration(audioPreview);
    updateFileMeta(recordedFile);

    btnStop.disabled = true;
    btnStart.disabled = false;

    recIndicatorWrap?.classList.remove("recording");
    setStatus("녹음이 저장되었습니다.", "ok");
  };

  try {
    mediaRecorder.start();
  } catch (e) {
    console.error("mediaRecorder.start failed", e);
    try {
      stream.getTracks().forEach((tr) => tr.stop());
    } catch (_) {}
    setStatus("녹음을 시작할 수 없습니다.", "err");
    resetRecordingUi();
    return;
  }

  btnStart.disabled = true;
  btnStop.disabled = false;

  recIndicatorWrap?.classList.add("recording");
  startTimer();
  setStatus("녹음 중...", "ok");
}

btnStart?.addEventListener("click", () => {
  clearStatus();

  if (!navigator?.mediaDevices?.getUserMedia) {
    console.error("getUserMedia not available", navigator, navigator?.mediaDevices);
    setStatus("이 환경에서는 마이크 기능이 지원되지 않아요 (HTTPS/localhost 또는 브라우저 확인).", "err");
    return;
  }

  resetRecordedState();
  setSelectedAudio(null, null);
  updateFileMeta(null);

  // async/await 금지: 권한 대화 후에도 스트림이 바로 이어지도록 이 이벤트 루프 턴에서 getUserMedia 호출 (live.js requestMicPermission과 동일 패턴)
  navigator.mediaDevices
    .getUserMedia({ audio: true })
    .then((stream) => {
      startMediaRecorderFromStream(stream);
    })
    .catch((err) => {
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
    });
});

btnStop?.addEventListener("click", () => {
  if (!mediaRecorder) return;
  if (mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
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

  if (playBtn.disabled) {
    return;
  }

  const soundId = playBtn.dataset.id;

  if (!soundId) {
    setStatus("재생할 소리 정보가 없습니다.", "err");
    return;
  }

  if (currentPlayingId === soundId && listAudio) {
    stopListAudioPlayback();
    return;
  }

  stopListAudioPlayback();

  const audioUrl =
    API_BASE +
    "/custom-sounds/" +
    encodeURIComponent(soundId) +
    "/audio?session_id=" +
    encodeURIComponent(SESSION_ID);

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
      setStatus(
        "오디오를 불러오지 못했습니다. 보관 기간 만료 또는 파일 없음일 수 있습니다.",
        "err"
      );
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

  // 같은 소리 이름이 이미 등록되어 있는지 검사
  const { ok, data: existingList } = await fetchExistingSoundList();
  if (ok && existingList.length > 0) {
    const nameLower = result.name.trim().toLowerCase();
    const hasSameName = existingList.some(
      (r) => (r.name || "").trim().toLowerCase() === nameLower
    );
    if (hasSameName) {
      alert("이미 등록하신 소리입니다.");
      return;
    }
  }

  if (!confirm(`"${result.name}" 소리를 등록하시겠습니까?`)) {
    return;
  }

  const { event_type } = categoryToApi(result.category);

  const form = new FormData();
  form.append("name", result.name);
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

    soundName.value = "";
    soundCategory.value = "";
    resetSelection();

    await loadSoundList();

    // 등록 직후 목록 탭으로 전환해 방금 등록한 소리를 바로 볼 수 있게
    const listTab = document.getElementById("list-tab");
    if (listTab && window.bootstrap) {
      const tab = new bootstrap.Tab(listTab);
      tab.show();
    }
    setStatus(`"${data.data?.name || result.name}" 소리가 등록되었습니다.`, "ok");
  } catch (err) {
    console.error(err);
    setStatus("서버에 연결할 수 없습니다. 백엔드를 확인하세요.", "err");
  } finally {
    btnSubmit.disabled = false;
  }
});

// ===== 사용자 섹션 =====
// 새로운 소리 페이지는 로그인한 사용자만 접근 가능(드롭다운 '소리등록'으로만 진입).
// session_id + provider(google/kakao)가 있으면 사용자 드롭다운 표시.
async function updateUserSection() {
  if (!userDropdownWrap) return;
  const urlSessionId = new URLSearchParams(document.location.search).get("session_id");
  const provider = getProvider();
  const showDropdown =
    urlSessionId && (provider === "google" || provider === "kakao");
  if (!showDropdown) {
    if (btnLogin) btnLogin.classList.remove("d-none");
    userDropdownWrap.classList.add("d-none");
    return;
  }
  if (btnLogin) btnLogin.classList.add("d-none");
  userDropdownWrap.classList.remove("d-none");
  try {
    const res = await fetch(API_BASE + "/auth/me?session_id=" + encodeURIComponent(urlSessionId || ""));
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
    const url = "/new-sound" + (SESSION_ID ? "?session_id=" + encodeURIComponent(SESSION_ID) : "");
    window.location.href = url;
  });

  if (userDropdownSettings) {
    userDropdownSettings.addEventListener("click", (e) => {
      e.preventDefault();
      const url = "/settings-page" + (SESSION_ID ? "?session_id=" + encodeURIComponent(SESSION_ID) : "");
      window.location.href = url;
    });
  }

  userDropdownLogout.addEventListener("click", (e) => {
    e.preventDefault();
    try {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      localStorage.removeItem(PROVIDER_STORAGE_KEY);
    } catch (_) {}
    window.location.href = "/";
  });
}

updateUserSection();
setupUserDropdown();

// 등록 가이드 모달: 닫힌 상태 inert·표시 시 해제 (접근성)
(function setupRegisterGuideModalA11y() {
  const el = document.getElementById("registerGuideModal");
  if (!el) return;
  el.addEventListener("shown.bs.modal", () => {
    el.removeAttribute("inert");
    el.setAttribute("aria-hidden", "false");
  });
  el.addEventListener("hidden.bs.modal", () => {
    const ae = document.activeElement;
    if (ae && typeof ae.blur === "function" && el.contains(ae)) {
      try {
        ae.blur();
      } catch (_) {}
    }
    el.setAttribute("inert", "");
    el.setAttribute("aria-hidden", "true");
  });
})();