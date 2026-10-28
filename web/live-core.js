/* A single-flight inference loop; late responses cannot update a stopped session. */
(function(root) {
  class LiveRecognitionLoop {
    constructor({capture, infer, onResult, onError, intervalMs = 750, timeoutMs = 15000,
                 schedule = setTimeout, cancel = clearTimeout, clock = () => performance.now()}) {
      Object.assign(this, {capture, infer, onResult, onError, intervalMs, timeoutMs, schedule, cancel, clock});
      this.running = false; this.generation = 0; this.timer = null; this.controller = null;
    }
    start() {
      if(this.running) return;
      this.running = true;
      void this.step(++this.generation);
    }
    stop() {
      this.running = false; ++this.generation;
      if(this.timer !== null) this.cancel(this.timer);
      this.timer = null; this.controller?.abort(); this.controller = null;
    }
    active(generation) { return this.running && generation === this.generation; }
    async step(generation) {
      if(!this.active(generation)) return;
      const started = this.clock(); const controller = new AbortController();
      this.controller = controller; let failed = false;
      const deadline = this.schedule(() => controller.abort(), this.timeoutMs);
      try {
        const frame = await this.capture();
        if(frame && this.active(generation) && !controller.signal.aborted) {
          const result = await this.infer(frame, controller.signal);
          if(this.active(generation) && !controller.signal.aborted) this.onResult(result, this.clock() - started);
        }
      } catch(error) {
        if(this.active(generation)) {
          failed = true;
          if(this.onError(error) === false) this.stop();
        }
      } finally {
        this.cancel(deadline);
        if(this.active(generation)) {
          this.controller = null;
          const delay = failed ? Math.max(2000, this.intervalMs) : Math.max(0, this.intervalMs - (this.clock() - started));
          this.timer = this.schedule(() => { this.timer = null; void this.step(generation); }, delay);
        }
      }
    }
  }
  if(typeof module !== 'undefined' && module.exports) module.exports = {LiveRecognitionLoop};
  else root.LiveRecognitionLoop = LiveRecognitionLoop;
})(typeof globalThis !== 'undefined' ? globalThis : this);
