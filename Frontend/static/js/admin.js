// 관리자 대시보드 - 모니터링 & 피드백 수집·분석
// API 호출 시 쿠키 포함 (credentials: 'include')
const API_BASE = window.APP_CONFIG?.API_BASE || "";

async function adminFetch(path, options = {}) {
  const url = (API_BASE || "") + path;
  const res = await fetch(url, {
    ...options,
    credentials: "include",
    headers: { ...(options.headers || {}) },
  });
  if (res.status === 401) {
    window.location.href = "/admin-login";
    throw new Error("Unauthorized");
  }
  return res;
}

function formatTs(tsMs) {
  if (!tsMs) return "-";
  const d = new Date(Number(tsMs));
  return isNaN(d.getTime()) ? "-" : d.toLocaleTimeString("ko-KR", { hour12: false });
}

function formatDate(tsMs) {
  if (!tsMs) return "-";
  const d = new Date(Number(tsMs));
  return isNaN(d.getTime()) ? "-" : d.toLocaleDateString("ko-KR");
}

// ========== 1. 개요·실시간 현황 ==========
async function loadOverview() {
  const cardsEl = document.getElementById("overviewCards");
  const queuesEl = document.getElementById("overviewQueues");
  const metricsEl = document.getElementById("overviewMetrics");
  const errEl = document.getElementById("overviewError");

  try {
    const [healthRes, metricsRes] = await Promise.all([
      adminFetch("/admin/health"),
      adminFetch("/admin/metrics"),
    ]);

    const health = await healthRes.json();
    const metrics = await metricsRes.json();

    if (!health.ok || !metrics.ok) {
      throw new Error("데이터 로드 실패");
    }

    // 카드: DB, STT, YAMNet, 세션
    const dbOk = health.db_ok;
    const sttTask = health.tasks?.stt || {};
    const yamnetTask = health.tasks?.yamnet || {};
    const sessionCount = metrics.sessions?.session_count ?? 0;

    const sttRunning = sttTask.exists && !sttTask.done && !sttTask.cancelled;
    const yamnetRunning = yamnetTask.exists && !yamnetTask.done && !yamnetTask.cancelled;

    cardsEl.innerHTML = `
      <div class="col-6 col-md-3">
        <div class="border rounded p-2 text-center">
          <div class="small text-muted">DB</div>
          <div class="fw-semibold ${dbOk ? "text-success" : "text-danger"}">${dbOk ? "정상" : "오류"}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="border rounded p-2 text-center">
          <div class="small text-muted">STT</div>
          <div class="fw-semibold ${sttRunning ? "text-success" : "text-secondary"}">${sttRunning ? "동작중" : "-"}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="border rounded p-2 text-center">
          <div class="small text-muted">YAMNet</div>
          <div class="fw-semibold ${yamnetRunning ? "text-success" : "text-secondary"}">${yamnetRunning ? "동작중" : "-"}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="border rounded p-2 text-center">
          <div class="small text-muted">연결 세션</div>
          <div class="fw-semibold">${sessionCount}</div>
        </div>
      </div>
    `;

    // 큐
    const yq = health.queues?.yamnet_qsize ?? metrics.queues?.yamnet_queue_size ?? 0;
    const sq = health.queues?.stt_qsize ?? metrics.queues?.stt_queue_size ?? 0;
    queuesEl.textContent = `큐: YAMNet ${yq} / STT ${sq}`;

    // 처리 지표
    const c = metrics.counters || health.metrics || {};
    const yamnetAvg = c.yamnet_avg_ms ?? "-";
    const sttAvg = c.stt_avg_ms ?? "-";
    metricsEl.textContent = `처리: YAMNet ${c.yamnet_processed ?? 0}건 (평균 ${yamnetAvg}ms) / STT ${c.stt_processed ?? 0}건 (평균 ${sttAvg}ms)`;

    errEl.classList.add("d-none");
  } catch (e) {
    errEl.textContent = "개요 로드 실패: " + (e.message || "알 수 없음");
    errEl.classList.remove("d-none");
  }
}

// ========== 2. 이벤트·알림 ==========
let nextUntilTsMs = null;
let hasMoreAlerts = false;

async function loadAlerts(append = false) {
  const tbody = document.getElementById("alertsTbody");
  const statusEl = document.getElementById("alertsStatus");
  const errEl = document.getElementById("alertsError");
  const btnMore = document.getElementById("btnLoadMoreAlerts");
  const summaryEl = document.getElementById("summaryText");

  const dateVal = document.getElementById("filterDate").value;
  const sessionVal = document.getElementById("filterSession").value.trim() || undefined;

  let sinceTs = null;
  let untilTs = null;
  if (append) {
    untilTs = nextUntilTsMs;
  } else if (dateVal) {
    const start = new Date(dateVal);
    start.setHours(0, 0, 0, 0);
    sinceTs = start.getTime();
  }

  try {
    let url = "/admin/alerts?limit=30";
    if (sessionVal) url += "&session_id=" + encodeURIComponent(sessionVal);
    if (sinceTs) url += "&since_ts_ms=" + sinceTs;
    if (untilTs) url += "&until_ts_ms=" + untilTs;

    const res = await adminFetch(url);
    const data = await res.json();

    if (!data.ok) throw new Error("알림 로드 실패");

    const items = data.data || [];

    if (!append) tbody.innerHTML = "";

    items.forEach((it) => {
      const tr = document.createElement("tr");
      const typeBadge = it.event_type === "danger" ? "danger" : "warning";
      tr.innerHTML = `
        <td>${formatTs(it.ts_ms)}</td>
        <td><span class="badge bg-${typeBadge}">${it.event_type || "-"}</span></td>
        <td class="text-truncate" style="max-width:120px" title="${(it.keyword || "").replace(/"/g, "&quot;")}">${it.keyword || "-"}</td>
        <td class="text-truncate" style="max-width:200px" title="${(it.text || "").replace(/"/g, "&quot;")}">${it.text || "-"}</td>
        <td class="small">${it.session_id ? it.session_id.slice(0, 8) + "…" : "-"}</td>
      `;
      tbody.appendChild(tr);
    });

    nextUntilTsMs = data.next_until_ts_ms ?? null;
    hasMoreAlerts = data.has_more ?? false;
    btnMore.style.display = hasMoreAlerts ? "inline-block" : "none";
    statusEl.textContent = `${items.length}건 로드됨${hasMoreAlerts ? " (더 있음)" : ""}`;

    // 요약 (같은 조건으로 summary 호출)
    loadSummary(sessionVal, sinceTs, dateVal ? 86400 : 300).then((s) => {
      if (s) summaryEl.textContent = s;
    });

    errEl.classList.add("d-none");
  } catch (e) {
    errEl.textContent = "알림 로드 실패: " + (e.message || "알 수 없음");
    errEl.classList.remove("d-none");
  }
}

async function loadSummary(sessionId, sinceTs, recentSec = 300) {
  try {
    let url = "/admin/summary?recent_window_sec=" + recentSec;
    if (sessionId) url += "&session_id=" + encodeURIComponent(sessionId);
    if (sinceTs) url += "&since_ts_ms=" + sinceTs;

    const res = await adminFetch(url);
    const data = await res.json();
    if (!data.ok || !data.summary) return null;

    const s = data.summary;
    const recent = s.alerts_recent || {};
    return `caption ${s.total_captions ?? 0}건 / alert ${s.total_alerts ?? 0}건 / 최근 ${recent.window_sec ?? 300}초 ${recent.count ?? 0}건`;
  } catch (_) {
    return null;
  }
}

// ========== 3. 피드백 분석 ==========
async function loadFeedback() {
  const tbody = document.getElementById("feedbackSummaryTbody");
  const emptyEl = document.getElementById("feedbackSummaryEmpty");
  const errEl = document.getElementById("feedbackSummaryError");
  const listEl = document.getElementById("feedbackSuspectsList");
  const suspectsEmpty = document.getElementById("feedbackSuspectsEmpty");
  const suspectsErr = document.getElementById("feedbackSuspectsError");

  try {
    const [summaryRes, suspectsRes] = await Promise.all([
      adminFetch("/admin/feedback-summary?limit=50"),
      adminFetch("/admin/feedback-suspects?min_count=5&min_down_rate=0.6&limit=20"),
    ]);

    const summaryData = await summaryRes.json();
    const suspectsData = await suspectsRes.json();

    // 키워드별 피드백
    const items = summaryData.ok ? (summaryData.data || []) : [];
    tbody.innerHTML = "";
    if (items.length === 0) {
      emptyEl.classList.remove("d-none");
    } else {
      emptyEl.classList.add("d-none");
      items.forEach((it) => {
        const tr = document.createElement("tr");
        const rate = (it.down_rate * 100).toFixed(1);
        const suspect = rate >= 60 ? ' <span class="badge bg-warning text-dark">의심</span>' : "";
        tr.innerHTML = `
          <td class="text-truncate" style="max-width:150px" title="${(it.keyword || "").replace(/"/g, "&quot;")}">${it.keyword || "-"}${suspect}</td>
          <td>${it.event_type || "-"}</td>
          <td>${it.up ?? 0}</td>
          <td>${it.down ?? 0}</td>
          <td>${rate}%</td>
        `;
        tbody.appendChild(tr);
      });
    }
    errEl.classList.add("d-none");

    // 오탐 의심
    const suspects = suspectsData.ok ? (suspectsData.data || []) : [];
    listEl.innerHTML = "";
    suspectsEmpty.classList.add("d-none");
    if (suspects.length === 0) {
      suspectsEmpty.classList.remove("d-none");
    } else {
      suspects.forEach((it) => {
        const li = document.createElement("li");
        li.className = "list-group-item py-2 small";
        const rate = (it.down_rate * 100).toFixed(1);
        li.innerHTML = `<strong>${it.keyword || "-"}</strong> (${rate}%, 총 ${it.total}건)`;
        listEl.appendChild(li);
      });
    }
    suspectsErr.classList.add("d-none");
  } catch (e) {
    errEl.textContent = "피드백 로드 실패: " + (e.message || "알 수 없음");
    errEl.classList.remove("d-none");
    suspectsErr.textContent = "오탐 의심 로드 실패: " + (e.message || "알 수 없음");
    suspectsErr.classList.remove("d-none");
  }
}

// ========== 초기화 ==========
document.addEventListener("DOMContentLoaded", () => {
  loadOverview();
  loadAlerts();
  loadFeedback();

  document.getElementById("btnLoadAlerts").addEventListener("click", () => {
    nextUntilTsMs = null;
    loadAlerts(false);
  });

  document.getElementById("btnLoadMoreAlerts").addEventListener("click", () => {
    loadAlerts(true);
  });

  // 주기적 갱신 (개요만 30초마다)
  setInterval(loadOverview, 30000);
});
