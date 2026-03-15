/**
 * WebSocket 메시지 타입·페이로드 (ws_protocol.md 기준)
 * 프론트·모바일 동일 규격으로 사용.
 */

// ========== 메시지 타입 상수 ==========
export const WS_MSG = {
  HELLO: 'hello',
  JOIN: 'join',
  JOIN_ACK: 'join_ack',
  CAPTION: 'caption',
  ALERT: 'alert',
  AUDIO_CHUNK: 'audio_chunk',
  SEND_CAPTION: 'send_caption',
} as const;

export type WsMessageType = (typeof WS_MSG)[keyof typeof WS_MSG];

// ========== 페이로드 타입 (서버 → 클라이언트) ==========
export interface WsHello {
  type: typeof WS_MSG.HELLO;
}

export interface WsJoinAck {
  type: typeof WS_MSG.JOIN_ACK;
  session_id: string;
}

export interface WsCaption {
  type: typeof WS_MSG.CAPTION;
  session_id: string;
  text: string;
  ts_ms: number;
}

export interface WsAlert {
  type: typeof WS_MSG.ALERT;
  session_id: string;
  text: string;
  ts_ms: number;
  event_type: 'danger' | 'alert' | 'info';
  keyword?: string;
  event_id?: number;
  source?: 'text' | 'audio' | 'custom_phrase' | 'demo';
  category?: 'warning' | 'daily';
  score?: number;
}

// ========== 페이로드 타입 (클라이언트 → 서버) ==========
export interface WsJoin {
  type: typeof WS_MSG.JOIN;
  session_id: string;
}

export interface WsAudioChunk {
  type: typeof WS_MSG.AUDIO_CHUNK;
  session_id: string;
  ts_ms: number;
  sr: 16000;
  format: 'pcm_s16le';
  data_b64: string;
}

export interface WsSendCaption {
  type: typeof WS_MSG.SEND_CAPTION;
  session_id: string;
  text: string;
}

// ========== 공통 ==========
export interface WsMessageBase {
  type: string;
  [key: string]: unknown;
}

/** 메시지가 특정 type인지 확인 */
export function isWsType<T extends WsMessageBase>(
  msg: WsMessageBase,
  type: string
): msg is T {
  return msg.type === type;
}

/** 오디오 청크 규격: 0.5초 = 8000 samples @ 16kHz */
export const AUDIO_CHUNK_SAMPLES = 8000;
export const AUDIO_TARGET_SR = 16000;
