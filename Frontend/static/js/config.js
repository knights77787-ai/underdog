/**
 * API/WS 기본 주소 설정.
 * 같은 서버에서 프론트 서빙 시 document.location.origin 사용.
 * 경로·메시지 타입 상수: Shared/constants.js 로드 시 window.UNDERDOG_API_PATHS, UNDERDOG_WS_MSG 사용 가능.
 */
(function () {
  const origin = typeof document !== "undefined" && document.location ? document.location.origin : "";
  window.APP_CONFIG = {
    API_BASE: origin || "http://127.0.0.1:8000",
    WS_URL: (origin || "http://127.0.0.1:8000").replace(/^http/, "ws") + "/ws",
    LIVE_PATH: "/",
  };
})();
