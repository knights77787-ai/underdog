/**
 * REST API 경로·응답 타입 (api_contract.md 기준)
 * 프론트·모바일 동일 규격으로 사용.
 */

// ========== 경로 상수 ==========
export const API_PATHS = {
  AUTH_GUEST: '/auth/guest',
  AUTH_GOOGLE_LOGIN: '/auth/google/login',
  AUTH_GOOGLE_CALLBACK: '/auth/google/callback',
  AUTH_KAKAO_LOGIN: '/auth/kakao/login',
  AUTH_KAKAO_CALLBACK: '/auth/kakao/callback',

  LOGS: '/logs',
  SETTINGS: '/settings',
  FEEDBACK: '/feedback',
  HEALTH: '/health',

  CUSTOM_SOUNDS: '/custom-sounds',
  CUSTOM_PHRASE_AUDIO: '/custom-phrase-audio',

  ADMIN_HEALTH: '/admin/health',
  ADMIN_ALERTS: '/admin/alerts',
  ADMIN_SUMMARY: '/admin/summary',
  ADMIN_METRICS: '/admin/metrics',
  ADMIN_FEEDBACK_SUMMARY: '/admin/feedback-summary',
  ADMIN_FEEDBACK_SUSPECTS: '/admin/feedback-suspects',
  ADMIN_DEMO_EMIT: '/admin/demo/emit',
  ADMIN_RELOAD_KEYWORDS: '/admin/reload-keywords',
  ADMIN_RELOAD_AUDIO_RULES: '/admin/reload-audio-rules',
} as const;

// ========== 응답 타입 ==========
export interface AuthGuestResponse {
  ok: boolean;
  session_id: string;
  user: {
    id: number | null;
    name: string | null;
    email: string | null;
    provider: string;
  };
}

export interface LogItemCaption {
  type: 'caption';
  session_id: string;
  text: string;
  ts_ms: number;
}

export interface LogItemAlert {
  type: 'alert';
  session_id: string;
  text: string;
  ts_ms: number;
  event_type: 'danger' | 'alert';
  keyword?: string;
  event_id?: number;
}

export type LogItem = LogItemCaption | LogItemAlert;

export interface LogsResponse {
  ok: boolean;
  type: string;
  session_id: string | null;
  limit: number;
  count: number;
  data: LogItem[];
  next_until_ts_ms: number;
  has_more: boolean;
}

export interface SettingsData {
  font_size: number;
  alert_enabled: boolean;
  cooldown_sec: number;
  auto_scroll: boolean;
}

export interface SettingsResponse {
  ok: boolean;
  session_id: string;
  data: SettingsData;
}

export interface FeedbackResponse {
  ok: boolean;
  message?: string;
}

export interface HealthResponse {
  ok?: boolean;
  db_ok?: boolean;
  [key: string]: unknown;
}

/** API 베이스 URL과 경로를 합쳐 전체 URL 반환 */
export function buildApiUrl(apiBase: string, path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${apiBase.replace(/\/$/, '')}${p}`;
}
