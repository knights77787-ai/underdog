/**
 * AudioWorklet: 마이크 입력을 메인 스레드로 전달 (ScriptProcessorNode 대체)
 */
class MicProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input.length) return true;
    const ch0 = input[0];
    if (!ch0 || ch0.length === 0) return true;
    this.port.postMessage({ type: "audio", samples: Float32Array.from(ch0) });
    return true;
  }
}
registerProcessor("mic-processor", MicProcessor);
