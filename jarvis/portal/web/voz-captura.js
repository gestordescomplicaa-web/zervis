// O microfone do navegador em pedaços de 80 ms (PCM de 16 bits) para o canal de voz do Zé.
class Captura extends AudioWorkletProcessor {
  constructor() { super(); this.tamanho = Math.round(sampleRate * 0.08); this.novo(); }
  novo() { this.pedaco = new Int16Array(this.tamanho); this.n = 0; }
  process(entradas) {
    const canal = entradas[0][0];
    if (canal) for (const s of canal) {
      this.pedaco[this.n++] = Math.max(-1, Math.min(1, s)) * 32767;
      if (this.n === this.tamanho) { this.port.postMessage(this.pedaco.buffer, [this.pedaco.buffer]); this.novo(); }
    }
    return true;
  }
}
registerProcessor("captura", Captura);
