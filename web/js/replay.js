// Plays a recorded event list on its own clock: speed 1x/2x/4x, pause, seek.
export class Replay {
  constructor(events, onEvent, onReset) {
    this.events = events; this.onEvent = onEvent; this.onReset = onReset;
    this.t = 0; this.i = 0; this.speed = 1; this.playing = false; this.last = null; this.skipGaps = true;
    this.end = events.length ? events[events.length - 1].ts : 0;
    this._tick = this._tick.bind(this);
  }
  play() { if (!this.playing) { this.playing = true; this.last = performance.now(); requestAnimationFrame(this._tick); } }
  pause() { this.playing = false; }
  setSpeed(x) { this.speed = x; }
  seek(t) {
    this.onReset(); this.t = 0; this.i = 0; this._advance(Math.max(0, Math.min(t, this.end)));
  }
  _advance(t) {
    this.t = t;
    while (this.i < this.events.length && this.events[this.i].ts <= t) this.onEvent(this.events[this.i++]);
  }
  _tick(now) {
    if (!this.playing) return;
    const dt = (now - this.last) / 1000; this.last = now;
    let t = this.t + dt * this.speed;
    // skip dead air (waiting on the model) so the audience never stares at an idle screen
    const next = this.events[this.i];
    if (this.skipGaps && next && next.ts - t > 2.5) t = next.ts - 1.2;
    this._advance(t);
    if (this.i >= this.events.length) { this.playing = false; return; }
    requestAnimationFrame(this._tick);
  }
}

// Live: server-sent events. The browser reconnects and sends Last-Event-ID by itself.
export function connectLive(src, onEvent, onStatus) {
  const es = new EventSource(src);
  es.onopen = () => onStatus("live");
  es.onerror = () => onStatus("reconnecting");
  es.onmessage = (m) => {
    const e = JSON.parse(m.data);
    onEvent(e);
    if (e.type === "run.finished" || e.type === "run.failed") { es.close(); onStatus("finished"); }
  };
  return es;
}
