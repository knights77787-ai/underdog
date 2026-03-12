/**
 * Frontend/static/js/config.js
 * API/WS 주소 설정. 현재 페이지 origin 기반으로 자동 설정.
 *
 * - PC: http://localhost:8000/ 접속 → API_BASE = http://localhost:8000
 * - Android 에뮬레이터: http://10.0.2.2:8000/ 접속 → API_BASE = http://10.0.2.2:8000
 *   (에뮬레이터에서 PC의 localhost에 접근하려면 10.0.2.2 사용)
 */
(function () {
  const origin = window.location.origin || "http://127.0.0.1:8000";
  const apiBase = origin.replace(/\/$/, "");
  const wsUrl = apiBase.replace(/^http/, "ws") + "/ws";

  window.APP_CONFIG = window.APP_CONFIG || {};
  if (window.APP_CONFIG.API_BASE == null) window.APP_CONFIG.API_BASE = apiBase;
  if (window.APP_CONFIG.WS_URL == null) window.APP_CONFIG.WS_URL = wsUrl;
  if (window.APP_CONFIG.LIVE_PATH == null) window.APP_CONFIG.LIVE_PATH = "/";
})();
