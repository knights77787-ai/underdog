/**
 * API/WS 기본 주소 설정.
 * - 같은 서버에서 프론트 서빙(127.0.0.1, lumen.ai.kr, EC2 IP): location 기반으로 동적 WS URL.
 *   (도메인 접속 시 자동으로 wss://lumen.ai.kr/ws 사용, Mixed Content 방지)
 * - 메인 도메인(lumen.ai.kr) 또는 EC2 탄력적 IP에서 접속 시: API/WS는 동일 오리진 사용.
 */
(function () {
  const location = typeof document !== "undefined" && document.location ? document.location : null;
  const origin = location ? location.origin : "";
  const isLocal = !origin || /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(origin);
  /** EC2 탄력적 IP (AWS 콘솔에서 확인). IP로 직접 접속 시에도 동일 호스트로 API/WS 사용 */
  const EC2_ELASTIC_IP = "52.79.135.6";
  const isApiHost = /lumen\.ai\.kr$/i.test(origin) || (origin && origin.indexOf(EC2_ELASTIC_IP) !== -1);

  /** 다른 호스트에서 접속한 경우 사용할 API 호스트 (EC2 단일 도메인) */
  const PRODUCTION_API_ORIGIN = "https://lumen.ai.kr";

  let apiBase, wsUrl;
  if (isLocal || isApiHost) {
    apiBase = origin || "http://127.0.0.1:8000";
    // 이미지 원인 1·2: 동적 WS 주소 + HTTPS면 반드시 wss (Mixed Content 방지)
    const wsProtocol = location && location.protocol === "https:" ? "wss" : "ws";
    const host = location && location.host ? location.host : "127.0.0.1:8000";
    wsUrl = wsProtocol + "://" + host + "/ws";
  } else {
    apiBase = PRODUCTION_API_ORIGIN;
    wsUrl = "wss://lumen.ai.kr/ws";
  }

  window.APP_CONFIG = {
    API_BASE: apiBase,
    WS_URL: wsUrl,
    LIVE_PATH: "/",
  };
})();
