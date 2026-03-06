
/**
 * Frontend/static/js/wsClient.js
=======
/** WS + REST

 * 단일 사용자 기준 WS 클라이언트
 * - connect(): 연결
 * - disconnect(): 끊기
 * - send(type, payload): 서버로 JSON 전송
 * - on(type, handler): 서버에서 특정 type 메시지 수신
 */

// API_BASE / WS 주소는 live.js 등 사용처에서 정의 (중복 선언 방지)
window.WSClient = class WSClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.handlers = {};
    this.isConnected = false;
  }

  on(type, handler) {
    this.handlers[type] = this.handlers[type] || [];
    this.handlers[type].push(handler);
  }

  emit(type, data) {
    (this.handlers[type] || []).forEach(fn => fn(data));
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.isConnected = true;
      this.emit("open");
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      this.emit("close");
    };

    this.ws.onmessage = (e) => {
      let msg;
      try { msg = JSON.parse(e.data); }
      catch { return; }
      if (!msg.type) return;
      this.emit(msg.type, msg);
    };
  }

  disconnect() {
    if (this.ws) this.ws.close();
  }

  send(type, payload = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify({ type, ...payload }));
    return true;
  }
};