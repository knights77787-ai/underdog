/**
 * API/WS 기본 주소 설정.
 * - 같은 서버에서 프론트 서빙(127.0.0.1, api.lumen.ai.kr): location 기반으로 동적 WS URL.
 *   (도메인 접속 시 자동으로 wss://api.lumen.ai.kr/ws 사용, Mixed Content 방지)
 * - 메인 도메인(lumen.ai.kr 등)에서 접속 시: API/WS는 api.lumen.ai.kr로 고정.
 */
(function () {
  const location = typeof document !== "undefined" && document.location ? document.location : null;
  const origin = location ? location.origin : "";
  const isLocal = !origin || /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(origin);
  const isApiHost = /api\.lumen\.ai\.kr$/i.test(origin);

  /** 메인 도메인에서 접속한 경우 사용할 API 호스트 */
  const PRODUCTION_API_ORIGIN = "https://api.lumen.ai.kr";

  let apiBase, wsUrl;
  if (isLocal || isApiHost) {
    apiBase = origin || "http://127.0.0.1:8000";
    // 이미지 원인 1·2: 동적 WS 주소 + HTTPS면 반드시 wss (Mixed Content 방지)
    const wsProtocol = location && location.protocol === "https:" ? "wss" : "ws";
    const host = location && location.host ? location.host : "127.0.0.1:8000";
    wsUrl = wsProtocol + "://" + host + "/ws";
  } else {
    apiBase = PRODUCTION_API_ORIGIN;
    wsUrl = "wss://api.lumen.ai.kr/ws";
  }

  window.APP_CONFIG = {
    API_BASE: apiBase,
    WS_URL: wsUrl,
    LIVE_PATH: "/",
  };
})();
