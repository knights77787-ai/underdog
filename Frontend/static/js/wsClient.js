/**
 * WS + REST
 * 단일 사용자 기준 WS 클라이언트
 * - connect(): 연결 (자동 재연결 활성화)
 * - disconnect(): 끊기 (자동 재연결 비활성화)
 * - send(type, payload): 서버로 JSON 전송
 * - on(type, handler): 서버에서 특정 type 메시지 수신
 * - 상태: connecting | connected | disconnected
 * - 끊기면 1s→2s→4s→8s... 재시도 (최대 30s)
 */
window.WSClient = class WSClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.handlers = {};
    this.isConnected = false;
    this.autoReconnect = false;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.MAX_BACKOFF_MS = 30000;
  }

  on(type, handler) {
    this.handlers[type] = this.handlers[type] || [];
    this.handlers[type].push(handler);
  }

  emit(type, data) {
    (this.handlers[type] || []).forEach((fn) => fn(data));
  }

  _doConnect() {
    if (this.ws && this.ws.readyState !== WebSocket.CLOSED) return;
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.emit("open");
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      this.ws = null;
      this.emit("close");
      if (this.autoReconnect) {
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.MAX_BACKOFF_MS);
        this.reconnectAttempts++;
        this.emit("connecting", { attempt: this.reconnectAttempts, delayMs: delay });
        this.reconnectTimer = setTimeout(() => this._doConnect(), delay);
      }
    };

    this.ws.onerror = () => {
      // onclose에서 재연결 처리
    };

    this.ws.onmessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (!msg || typeof msg !== "object" || !msg.type) return;
      try {
        this.emit(msg.type, msg);
      } catch (err) {
        console.warn("[WSClient] handler error for type=" + msg.type, err);
      }
    };
  }

  connect() {
    this.autoReconnect = true;
    this.reconnectAttempts = 0;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.emit("connecting", { attempt: 0, delayMs: 0 });
    this._doConnect();
  }

  disconnect() {
    this.autoReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }

  send(type, payload = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify({ type, ...payload }));
    return true;
  }
};
