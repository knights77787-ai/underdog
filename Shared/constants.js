/**
 * API·WS 상수 (프론트엔드 웹에서 스크립트로 로드용)
 * Shared/src/api.ts, ws.ts 와 동일한 값 유지.
 * 사용: <script src=".../Shared/constants.js"></script> → window.UNDERDOG_API_PATHS, window.UNDERDOG_WS_MSG
 */
(function () {
  window.UNDERDOG_API_PATHS = {
    AUTH_GUEST: '/auth/guest',
    AUTH_GOOGLE_LOGIN: '/auth/google/login',
    AUTH_KAKAO_LOGIN: '/auth/kakao/login',
    LOGS: '/logs',
    SETTINGS: '/settings',
    FEEDBACK: '/feedback',
    HEALTH: '/health',
    CUSTOM_SOUNDS: '/custom-sounds',
    CUSTOM_PHRASE_AUDIO: '/custom-phrase-audio',
    ADMIN_HEALTH: '/admin/health',
    ADMIN_ALERTS: '/admin/alerts',
    ADMIN_DEMO_EMIT: '/admin/demo/emit',
  };

  window.UNDERDOG_WS_MSG = {
    HELLO: 'hello',
    JOIN: 'join',
    JOIN_ACK: 'join_ack',
    CAPTION: 'caption',
    ALERT: 'alert',
    AUDIO_CHUNK: 'audio_chunk',
    SEND_CAPTION: 'send_caption',
  };

  window.UNDERDOG_AUDIO_CHUNK_SAMPLES = 8000;
  window.UNDERDOG_AUDIO_TARGET_SR = 16000;
})();
