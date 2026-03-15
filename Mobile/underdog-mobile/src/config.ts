/**
 * API / WebSocket 베이스 URL 설정
 * - 배포 서버: https://api.lumen.ai.kr (Render)
 * - 개발 시 로컬: 개발 PC IP + 포트 (같은 Wi‑Fi에서 실기기 테스트용)
 * - 경로·타입은 Shared(api_contract, ws_protocol)와 동일하게 사용
 */
import { buildApiUrl } from '../../../Shared/src/api';

const PROD_API_BASE = 'https://api.lumen.ai.kr';
const PROD_WS_URL = 'wss://api.lumen.ai.kr/ws';

// 로컬 서버 사용 시 true로 바꾸고, DEV_* 값을 PC IP로 설정
const USE_LOCAL_SERVER = false;
const DEV_API_BASE = 'http://192.168.0.10:8000';
const DEV_WS_URL = 'ws://192.168.0.10:8000/ws';

export const API_BASE = __DEV__ && USE_LOCAL_SERVER ? DEV_API_BASE : PROD_API_BASE;
export const WS_URL = __DEV__ && USE_LOCAL_SERVER ? DEV_WS_URL : PROD_WS_URL;

/** REST 전체 URL (Shared buildApiUrl 사용) */
export function apiPath(path: string): string {
  return buildApiUrl(API_BASE, path);
}

export { API_PATHS, buildApiUrl } from '../../../Shared/src/api';
export { WS_MSG, AUDIO_CHUNK_SAMPLES, AUDIO_TARGET_SR } from '../../../Shared/src/ws';
export type { AuthGuestResponse, LogsResponse, LogItem, SettingsResponse } from '../../../Shared/src/api';
export type { WsCaption, WsAlert, WsJoin } from '../../../Shared/src/ws';
