// Frontend/static/js/live.js
// =======================
// 0) 서버 주소
// =======================
const WS_URL = "ws://127.0.0.1:8000/ws";

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

const captionBox = document.getElementById("captionBox");

const testInput = document.getElementById("testInput");
const btnSendCaption = document.getElementById("btnSendCaption");

const toastContainer = document.getElementById("toastContainer");

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

function appendLogRow({ ts, type, text, score, event_type, keyword }) {
  const tr = document.createElement("tr");
  const kind = (type === "alert") ? "경고" : "자막";
  const prob = (typeof score === "number") ? `${Math.round(score * 100)}%` : "-";
  const extra = keyword ? ` [${keyword}]` : "";

  tr.innerHTML = `
    <td>${ts || nowTS()}</td>
    <td>${kind}</td>
    <td>${text}${extra}${event_type ? ` (${event_type})` : ""}</td>
    <td>${prob}</td>
  `;
  logTbody.prepend(tr);

  while (logTbody.children.length > 30) {
    logTbody.removeChild(logTbody.lastChild);
  }
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
// 3) Mic UI
// =======================
btnMic.addEventListener("click", async () => {
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true });
    micTitle.textContent = "마이크 승인 완료";
    micDesc.textContent  = "서버 연결 후 감지 대기중입니다.";
  } catch {
    micTitle.textContent = "마이크 권한 거부됨";
    micDesc.textContent  = "브라우저 설정에서 마이크 허용이 필요합니다.";
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

  btnSendCaption.disabled = false;
  btnFeedbackYes.disabled = false;
  btnFeedbackNo.disabled = false;

  micTitle.textContent = "소리 감지 대기중";
  micDesc.textContent  = "서버 연결됨. 이벤트 수신을 기다립니다.";
});

client.on("close", () => {
  setBadge("disconnected");
  btnConnect.disabled = false;
  btnDisconnect.disabled = true;

  btnSendCaption.disabled = true;
  btnFeedbackYes.disabled = true;
  btnFeedbackNo.disabled = true;
});

// 서버가 caption 보내면
client.on("caption", (msg) => {
  const text = msg.text || "";
  const danger = isDanger(text);

  appendCaption(text, danger);
  appendLogRow({ ts: msg.ts, type: "caption", text, score: msg.score });

  if (danger) {
    setHeroDanger(text);
    showToast("위험 감지", text, true);
  }
});

// 서버가 alert 보내면
client.on("alert", (msg) => {
  const text = msg.text || "";
  const keyword = msg.keyword || "";
  const event_type = msg.event_type || "danger";

  appendCaption(`[ALERT] ${text}`, true);
  appendLogRow({ ts: msg.ts, type: "alert", text, keyword, event_type, score: msg.score });

  setHeroDanger(`${keyword ? "["+keyword+"] " : ""}${text}`);
  showToast("알림", `${keyword ? "["+keyword+"] " : ""}${text}`, true);
});

// Buttons
btnConnect.addEventListener("click", () => client.connect());
btnDisconnect.addEventListener("click", () => client.disconnect());

// Feedback UI only
btnFeedbackYes.addEventListener("click", () => showToast("피드백", "맞아요(정탐) (UI만)", false));
btnFeedbackNo.addEventListener("click", () => showToast("피드백", "아니에요(오탐) (UI만)", true));

// Test sender (server must support)
btnSendCaption.addEventListener("click", () => {
  const text = testInput.value.trim();
  if (!text) return;

  client.send("send_caption", { text, save: saveToggle.checked });
  testInput.value = "";
});

// Init
setBadge("disconnected");
setHeroNormal();