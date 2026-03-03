// Frontend/static/js/new_sound.js
// ====== user menu ======
const userMenuBtn = document.getElementById("userMenuBtn");
const userMenu = document.getElementById("userMenu");

userMenuBtn?.addEventListener("click", () => {
  const isOpen = userMenu.style.display === "block";
  userMenu.style.display = isOpen ? "none" : "block";
  userMenuBtn.setAttribute("aria-expanded", String(!isOpen));
  userMenu.setAttribute("aria-hidden", String(isOpen));
});

document.addEventListener("click", (e) => {
  if (!userMenu || !userMenuBtn) return;
  if (!userMenu.contains(e.target) && !userMenuBtn.contains(e.target)) {
    userMenu.style.display = "none";
    userMenuBtn.setAttribute("aria-expanded", "false");
    userMenu.setAttribute("aria-hidden", "true");
  }
});

// ====== recorder ======
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

let mediaRecorder = null;
let recordedChunks = [];
let recordedBlob = null;
let recordedUrl = null;

let t0 = 0;
let timerId = null;

function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className = "status " + type;
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

btnStart.addEventListener("click", async () => {
  setStatus("");
  // 업로드 파일이 선택되어 있으면, 사용자가 녹음을 시작할 때 안내
  if (fileInput.files && fileInput.files.length > 0) {
    setStatus("업로드 파일이 선택되어 있습니다. 녹음을 사용하려면 파일 선택을 해제하세요.", "");
  }

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
      // 스트림 종료
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
    // 권한/보안 관련 에러 분기
    if (err && (err.name === "NotAllowedError" || err.name === "PermissionDeniedError")) {
      // 사용자가 팝업에서 차단했거나, 이미 차단 상태라 팝업이 재노출되지 않는 케이스
      setStatus("마이크 권한이 거부되었습니다. 주소창의 🔒(권한)에서 마이크를 '허용'으로 바꿔주세요.", "err");
    } else if (err && err.name === "NotFoundError") {
      // 마이크 장치 없음
      setStatus("마이크 장치를 찾지 못했습니다. 마이크 연결/설정을 확인해주세요.", "err");
    } else if (err && (err.name === "NotReadableError" || err.name === "TrackStartError")) {
      // 다른 앱이 마이크 점유 등
      setStatus("마이크를 사용할 수 없습니다. 다른 앱(줌/디코/녹음기 등)이 마이크를 사용 중인지 확인해주세요.", "err");
    } else if (err && err.name === "SecurityError") {
      // http 환경 등 보안 컨텍스트 문제
      setStatus("보안상 마이크 접근이 차단되었습니다. HTTPS(또는 localhost)에서 실행해주세요.", "err");
    } else {
      setStatus("마이크를 사용할 수 없습니다. 브라우저/권한/HTTPS 환경을 확인해주세요.", "err");
    }
  }
});

btnStop.addEventListener("click", () => {
  if (!mediaRecorder) return;
  if (mediaRecorder.state !== "inactive") mediaRecorder.stop();
});

btnPlay.addEventListener("click", async () => {
  try {
    if (audioPreview.hidden) audioPreview.hidden = false;
    await audioPreview.play();
  } catch (e) {
    // autoplay 정책 등
  }
});

fileInput.addEventListener("change", () => {
  setStatus("");
  const f = fileInput.files && fileInput.files[0];
  if (!f) {
    fileMeta.textContent = "선택된 파일 없음";
    return;
  }

  // 업로드 파일 선택 시, 녹음 blob은 무시(프론트 기준)
  fileMeta.textContent = `${f.name} (${Math.round(f.size / 1024)} KB)`;
  setStatus("업로드 파일이 선택되었습니다. ‘다음’을 누르면 업로드 파일로 저장됩니다.", "");
});

// ====== submit ======
btnSubmit.addEventListener("click", async () => {
  setStatus("");

  const name = (soundName.value || "").trim();
  const cat = soundCategory.value;

  if (!name) return setStatus("소리 이름을 입력하세요.", "err");
  if (!cat) return setStatus("소리 분류를 선택하세요.", "err");

  // 우선순위: 업로드 파일 > 녹음 파일
  const uploadFile = fileInput.files && fileInput.files[0];
  const hasRecorded = !!recordedBlob;

  if (!uploadFile && !hasRecorded) {
    return setStatus("녹음하거나 파일을 업로드하세요.", "err");
  }

  const form = new FormData();
  form.append("sound_name", name);
  form.append("sound_category", cat);

  if (uploadFile) {
    form.append("audio_file", uploadFile, uploadFile.name);
  } else {
    // 파일명은 webm으로 저장
    form.append("audio_file", recordedBlob, "recorded.webm");
  }

  btnSubmit.disabled = true;
  setStatus("업로드 중...", "");

  try {
    const res = await fetch("/api/sounds", {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || "upload failed");
    }

    const data = await res.json();
    setStatus(`저장 완료: #${data.sound_id} (다음 단계로 이동 가능)`, "ok");

    // TODO: 실제로는 학습 페이지로 이동
    // location.href = `/train?sound_id=${data.sound_id}`;
  } catch (err) {
    console.error(err);
    setStatus("저장 실패. 서버 실행/라우트(/api/sounds) 확인 필요", "err");
  } finally {
    btnSubmit.disabled = false;
  }
});