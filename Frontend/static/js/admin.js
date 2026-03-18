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

const EVENT_TYPE_LABEL = { danger: "위험/경고", caution: "주의", alert: "일상" };
const VOTE_LABEL = { up: "맞아요", down: "아니에요" };

// ========== 2. 피드백 목록 ==========
async function loadFeedback() {
  const tbody = document.getElementById("feedbackTbody");
  const emptyEl = document.getElementById("feedbackEmpty");
  const errEl = document.getElementById("feedbackError");

  const dateFrom = document.getElementById("filterDateFrom")?.value || "";
  const dateTo = document.getElementById("filterDateTo")?.value || "";
  const eventType = document.getElementById("filterEventType")?.value || "";
  const vote = document.getElementById("filterVote")?.value || "";

  let url = "/admin/feedback?limit=100";
  if (dateFrom) url += "&date_from=" + encodeURIComponent(dateFrom);
  if (dateTo) url += "&date_to=" + encodeURIComponent(dateTo);
  if (eventType) url += "&event_type=" + encodeURIComponent(eventType);
  if (vote) url += "&vote=" + encodeURIComponent(vote);

  try {
    const res = await adminFetch(url);
    const data = await res.json();

    if (!data.ok) throw new Error("피드백 로드 실패");

    const items = data.data || [];
    tbody.innerHTML = "";
    if (items.length === 0) {
      emptyEl.classList.remove("d-none");
    } else {
      emptyEl.classList.add("d-none");
      items.forEach((it) => {
        const tr = document.createElement("tr");
        const tsStr = it.segment_start_ms ? formatTs(it.segment_start_ms) : (it.created_at ? it.created_at.slice(11, 19) : "-");
        const dateStr = it.segment_start_ms ? formatDate(it.segment_start_ms) : "-";
        const typeLabel = EVENT_TYPE_LABEL[it.event_type] || it.event_type || "-";
        const voteLabel = VOTE_LABEL[it.vote] || it.vote || "-";
        const sess = (it.client_session_uuid || "").slice(0, 8) + (it.client_session_uuid && it.client_session_uuid.length > 8 ? "…" : "");
        tr.innerHTML = `
          <td class="small">${dateStr} ${tsStr}</td>
          <td><span class="badge bg-${it.vote === "up" ? "success" : "danger"}">${voteLabel}</span></td>
          <td class="small">${typeLabel}</td>
          <td class="text-truncate small" style="max-width:100px" title="${(it.keyword || "").replace(/"/g, "&quot;")}">${it.keyword || "-"}</td>
          <td class="text-truncate small" style="max-width:180px" title="${(it.text || "").replace(/"/g, "&quot;")}">${it.text || "-"}</td>
          <td class="small">${sess || "-"}</td>
          <td class="text-truncate small" style="max-width:120px" title="${(it.comment || "").replace(/"/g, "&quot;")}">${it.comment || "-"}</td>
        `;
        tbody.appendChild(tr);
      });
    }
    errEl.classList.add("d-none");
  } catch (e) {
    errEl.textContent = "피드백 로드 실패: " + (e.message || "알 수 없음");
    errEl.classList.remove("d-none");
  }
}

// ========== 초기화 ==========
document.addEventListener("DOMContentLoaded", () => {
  loadOverview();
  loadFeedback();

  document.getElementById("btnLoadFeedback")?.addEventListener("click", loadFeedback);

  // 주기적 갱신 (개요만 30초마다)
  setInterval(loadOverview, 30000);
});
