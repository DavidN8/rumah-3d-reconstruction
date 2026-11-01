// Camera navigation uses model-viewer's public camera API. Units remain the
// reconstruction's arbitrary units; movement is scaled to the model bounds.
export const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
export const add = (a, b) => a.map((v, i) => v + b[i]);
export const multiply = (v, s) => v.map(x => x * s);
export function offset({theta, phi, radius}) {
  return [radius * Math.sin(phi) * Math.sin(theta), radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.cos(theta)];
}
export function wheelRadius(radius, delta, minimum, maximum) {
  // A large/coalesced wheel event can change distance by at most 6%.
  return clamp(radius * Math.exp(clamp(delta, -120, 120) * 0.00045), minimum, maximum);
}
export function movement(keys, theta, distance) {
  const forward = Number(keys.has('KeyW')) - Number(keys.has('KeyS'));
  const side = Number(keys.has('KeyD')) - Number(keys.has('KeyA'));
  const vertical = Number(keys.has('KeyE')) - Number(keys.has('KeyQ'));
  const length = Math.hypot(forward, side, vertical) || 1;
  return multiply([-forward * Math.sin(theta) + side * Math.cos(theta), vertical,
    -forward * Math.cos(theta) - side * Math.sin(theta)], distance / length);
}
export function fittedCamera(bounds, aspect = 1.5, theta = 80 * Math.PI / 180, phi = 40 * Math.PI / 180, points = null) {
  const target = bounds[0].map((v, i) => (v + bounds[1][i]) / 2);
  const fov = 35, tanV = Math.tan(fov * Math.PI / 360), tanH = tanV * aspect;
  const back = offset({theta, phi, radius: 1});
  const right = [Math.cos(theta), 0, -Math.sin(theta)];
  const up = [-Math.cos(phi) * Math.sin(theta), Math.sin(phi), -Math.cos(phi) * Math.cos(theta)];
  const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);
  let radius = 0;
  const vertices = points?.length ? points : Array.from({length:8},(_,i)=>target.map((t,j)=>bounds[(i >> j) & 1][j]));
  for (const point of vertices) {
    const v = point.map((p, j) => p - target[j]);
    radius = Math.max(radius, dot(v, back) + Math.max(Math.abs(dot(v, right)) / tanH, Math.abs(dot(v, up)) / tanV));
  }
  return {target, theta, phi, radius: radius * 1.12, fov};
}

const movementCodes = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE']);
const isForm = element => element?.closest?.('input,select,textarea,button,a,[contenteditable=true]');

export class MeshNavigation {
  constructor(viewer, surface, {onChange = () => {}, onMode = () => {}} = {}) {
    this.viewer = viewer;
    this.surface = surface;
    this.onChange = onChange;
    this.onMode = onMode;
    this.keys = new Set();
    this.mode = 'orbit';
    this.speed = 1;
    this.ready = false;
    this.bounds = [[-1, 0, -1], [1, 1, 1]];
    this.scale = 3;
    this.state = fittedCamera(this.bounds);
    surface.addEventListener('pointerdown', e => this.pointerDown(e));
    surface.addEventListener('pointermove', e => this.pointerMove(e));
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) {
      surface.addEventListener(event, () => { this.pointer = null; });
    }
    surface.addEventListener('contextmenu', e => e.preventDefault());
    surface.addEventListener('wheel', e => {
      if (!this.ready) return;
      e.preventDefault();
      const delta = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? surface.clientHeight : 1);
      this.zoom(delta);
    }, {passive: false});
    window.addEventListener('keydown', e => this.keyDown(e));
    window.addEventListener('keyup', e => this.keyUp(e));
    window.addEventListener('blur', () => this.release());
    document.addEventListener('visibilitychange', () => { if (document.hidden) this.release(); });
    let last = 0;
    const frame = now => {
      const dt = Math.min((now - (last || now)) / 1000, 0.05);
      last = now;
      if (this.ready && [...this.keys].some(k => movementCodes.has(k))) this.move(dt);
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }
  configure(bounds, framingPoints = null) {
    this.bounds = bounds;
    this.framingPoints = framingPoints;
    this.scale = Math.hypot(...bounds[1].map((v, i) => v - bounds[0][i]));
    this.ready = true;
    this.home();
  }
  apply() {
    const s = this.state;
    this.viewer.cameraTarget = s.target.map(v => `${v}m`).join(' ');
    this.viewer.cameraOrbit = `${s.theta}rad ${s.phi}rad ${s.radius}m`;
    this.viewer.fieldOfView = `${s.fov}deg`;
    this.viewer.jumpCameraToGoal();
    // Readable diagnostics for browser verification, not persisted user settings.
    this.surface.dataset.camera = JSON.stringify({...s, position: add(s.target, offset(s)), mode: this.mode});
    this.onChange(s);
  }
  focus() { this.surface.focus({preventScroll: true}); }
  release() { this.keys.clear(); this.pointer = null; }
  keyDown(e) {
    if (!this.ready || isForm(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.code === 'Escape') { this.release(); return; }
    if (e.code === 'Home' || e.code === 'KeyR') { e.preventDefault(); this.home(); return; }
    if (!movementCodes.has(e.code) && !['ShiftLeft', 'ShiftRight'].includes(e.code)) return;
    e.preventDefault();
    const fresh = !this.keys.has(e.code);
    this.keys.add(e.code);
    // A short tap must move even if released between animation frames.
    if (fresh && movementCodes.has(e.code)) this.move(1 / 30);
  }
  keyUp(e) { this.keys.delete(e.code); }
  move(dt) {
    const fast = this.keys.has('ShiftLeft') || this.keys.has('ShiftRight') ? 3 : 1;
    const distance = this.scale * 0.09 * this.speed * fast * dt;
    this.state.target = add(this.state.target, movement(this.keys, this.state.theta, distance));
    this.apply();
  }
  pointerDown(e) {
    if (!this.ready) return;
    this.focus();
    this.surface.setPointerCapture(e.pointerId);
    this.pointer = {id: e.pointerId, x: e.clientX, y: e.clientY, pan: e.button !== 0 || e.shiftKey};
    e.preventDefault();
  }
  pointerMove(e) {
    const p = this.pointer;
    if (!p || p.id !== e.pointerId) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    const s = this.state;
    if (p.pan) {
      const amount = (this.mode === 'walk' ? this.scale * 0.6 : s.radius) * 0.0012;
      const right = [Math.cos(s.theta), 0, -Math.sin(s.theta)];
      const up = [-Math.cos(s.phi) * Math.sin(s.theta), Math.sin(s.phi), -Math.cos(s.phi) * Math.cos(s.theta)];
      s.target = add(s.target, add(multiply(right, -dx * amount), multiply(up, dy * amount)));
    } else {
      const position = add(s.target, offset(s));
      s.theta -= dx * 0.004;
      s.phi = clamp(s.phi - dy * 0.004, 0.03, Math.PI - 0.03);
      if (this.mode === 'walk') s.target = add(position, multiply(offset(s), -1));
    }
    this.apply();
  }
  zoom(delta) {
    if (this.mode === 'walk') {
      // A wheel notch makes a small forward/back step inside a room.
      const forward = multiply(offset({...this.state, radius: 1}), -1);
      this.state.target = add(this.state.target, multiply(forward, -clamp(delta, -120, 120) * this.scale * 0.00008 * this.speed));
    } else {
      this.state.radius = wheelRadius(this.state.radius, delta, this.scale * 0.015, this.homeRadius * 2);
    }
    this.apply();
  }
  setMode(mode) {
    if (!this.ready || mode === this.mode) return;
    this.release();
    const s = this.state, position = add(s.target, offset(s));
    if (mode === 'walk') {
      s.radius = this.scale * 0.01;
      s.target = add(position, multiply(offset(s), -1));
    } else {
      // Orbit around a point ahead of the current view without teleporting.
      s.radius = this.scale * 0.35;
      s.target = add(position, multiply(offset(s), -1));
    }
    this.mode = mode;
    // model-viewer derives its near clipping plane from the maximum orbit.
    // An arbitrary huge limit clips an entire room when the camera is inside.
    this.viewer.maxCameraOrbit = `auto 180deg ${mode === 'walk' ? this.scale * 2 : this.homeRadius * 2}m`;
    this.onMode(mode);
    this.apply();
  }
  home(top = false) {
    this.release();
    this.mode = 'orbit';
    this.state = fittedCamera(this.bounds, this.surface.clientWidth / Math.max(1, this.surface.clientHeight), 80 * Math.PI / 180, top ? 0.03 : 40 * Math.PI / 180, this.framingPoints);
    this.homeRadius = this.state.radius;
    this.viewer.maxCameraOrbit = `auto 180deg ${this.homeRadius * 2}m`;
    this.onMode(this.mode);
    this.apply();
  }
  rotate() { this.state.theta += Math.PI / 2; this.apply(); }
  jump(camera) {
    this.release();
    const convert = p => [p[0], p[2], -p[1]];
    const position = convert(camera.position), target = convert(camera.target);
    const d = position.map((v, i) => v - target[i]);
    const length = Math.hypot(...d);
    this.state = {target, theta: Math.atan2(d[0], d[2]), phi: Math.acos(clamp(d[1] / length, -1, 1)), radius: length, fov: 75};
    this.mode = 'walk';
    this.viewer.maxCameraOrbit = `auto 180deg ${this.scale * 2}m`;
    this.onMode(this.mode);
    this.apply();
    this.focus();
  }
}
