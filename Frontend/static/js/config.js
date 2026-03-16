/**
 * API/WS 기본 주소 설정.
 * - 같은 서버에서 프론트 서빙(127.0.0.1, api.lumen.ai.kr): document.location.origin 사용.
 * - 메인 도메인(lumen.ai.kr 등)에서 접속 시: API/WS는 api.lumen.ai.kr로 고정.
 */
(function () {
  const origin = typeof document !== "undefined" && document.location ? document.location.origin : "";
  const isLocal = !origin || /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(origin);
  const isApiHost = /api\.lumen\.ai\.kr$/i.test(origin);

  /** 메인 도메인에서 접속한 경우 사용할 API 호스트 */
  const PRODUCTION_API_ORIGIN = "https://api.lumen.ai.kr";

  let apiBase, wsUrl;
  if (isLocal || isApiHost) {
    apiBase = origin || "http://127.0.0.1:8000";
    wsUrl = (origin || "http://127.0.0.1:8000").replace(/^http/, "ws") + "/ws";
  } else {
    apiBase = PRODUCTION_API_ORIGIN;
    wsUrl = PRODUCTION_API_ORIGIN.replace(/^http/, "ws") + "/ws";
  }

  window.APP_CONFIG = {
    API_BASE: apiBase,
    WS_URL: wsUrl,
    LIVE_PATH: "/",
  };
})();
