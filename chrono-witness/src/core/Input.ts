/**
 * Keyboard/mouse input with an action map. Mouse look uses pointer lock; when the pointer is not
 * locked (menus) gameplay input is suppressed by the owner.
 */
export type Action =
  | 'forward'
  | 'back'
  | 'left'
  | 'right'
  | 'jump'
  | 'sprint'
  | 'crouch'
  | 'interact'
  | 'scan'
  | 'observe'
  | 'journal'
  | 'inventory'
  | 'pause'
  | 'skip'
  | 'device';

const DEFAULT_BINDINGS: Record<Action, string[]> = {
  forward: ['KeyW', 'ArrowUp'],
  back: ['KeyS', 'ArrowDown'],
  left: ['KeyA', 'ArrowLeft'],
  right: ['KeyD', 'ArrowRight'],
  jump: ['Space'],
  sprint: ['ShiftLeft', 'ShiftRight'],
  crouch: ['KeyC', 'ControlLeft'],
  interact: ['KeyE'],
  scan: ['KeyQ'],
  observe: ['KeyF'],
  journal: ['KeyJ', 'Tab'],
  inventory: ['KeyI'],
  pause: ['Escape', 'KeyP'],
  skip: ['Enter'],
  device: ['KeyT'],
};

export class Input {
  readonly bindings: Record<Action, string[]> = structuredClone(DEFAULT_BINDINGS);
  private down = new Set<string>();
  private pressedThisFrame = new Set<string>();
  private releasedThisFrame = new Set<string>();
  mouseDX = 0;
  mouseDY = 0;
  mouseButtons = 0;
  private mousePressed = 0;
  private mouseReleased = 0;
  pointerLocked = false;
  /** Set when gameplay should ignore input (menus, dialogue). */
  gameplayEnabled = true;

  constructor(private readonly element: HTMLElement) {
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
    window.addEventListener('blur', this.onBlur);
    element.addEventListener('mousedown', this.onMouseDown);
    window.addEventListener('mouseup', this.onMouseUp);
    window.addEventListener('mousemove', this.onMouseMove);
    document.addEventListener('pointerlockchange', this.onLockChange);
  }

  dispose(): void {
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    window.removeEventListener('blur', this.onBlur);
    this.element.removeEventListener('mousedown', this.onMouseDown);
    window.removeEventListener('mouseup', this.onMouseUp);
    window.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('pointerlockchange', this.onLockChange);
  }

  requestPointerLock(): void {
    if (document.pointerLockElement === this.element) return;
    const p = this.element.requestPointerLock?.() as unknown as Promise<void> | undefined;
    if (p && typeof p.catch === 'function') p.catch(() => undefined);
  }

  exitPointerLock(): void {
    if (document.pointerLockElement) document.exitPointerLock();
  }

  isDown(a: Action): boolean {
    for (const k of this.bindings[a]) if (this.down.has(k)) return true;
    return false;
  }

  pressed(a: Action): boolean {
    for (const k of this.bindings[a]) if (this.pressedThisFrame.has(k)) return true;
    return false;
  }

  released(a: Action): boolean {
    for (const k of this.bindings[a]) if (this.releasedThisFrame.has(k)) return true;
    return false;
  }

  /** Raw key-code press (for keys outside the action map, e.g. dialogue number keys). */
  keyPressed(code: string): boolean {
    return this.pressedThisFrame.has(code);
  }

  mousePressedButton(b: number): boolean {
    return (this.mousePressed & (1 << b)) !== 0;
  }

  mouseDownButton(b: number): boolean {
    return (this.mouseButtons & (1 << b)) !== 0;
  }

  /** Synthesised key press for automation/tests and on-screen buttons. */
  simulate(code: string, down: boolean): void {
    if (down) {
      if (!this.down.has(code)) this.pressedThisFrame.add(code);
      this.down.add(code);
    } else {
      this.down.delete(code);
      this.releasedThisFrame.add(code);
    }
  }

  /** Call at the end of each frame. */
  endFrame(): void {
    this.pressedThisFrame.clear();
    this.releasedThisFrame.clear();
    this.mouseDX = 0;
    this.mouseDY = 0;
    this.mousePressed = 0;
    this.mouseReleased = 0;
  }

  private onKeyDown = (e: KeyboardEvent): void => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
    if (e.code === 'Tab' || e.code === 'Space') e.preventDefault();
    if (!this.down.has(e.code)) this.pressedThisFrame.add(e.code);
    this.down.add(e.code);
  };

  private onKeyUp = (e: KeyboardEvent): void => {
    this.down.delete(e.code);
    this.releasedThisFrame.add(e.code);
  };

  private onBlur = (): void => {
    for (const k of this.down) this.releasedThisFrame.add(k);
    this.down.clear();
    this.mouseButtons = 0;
  };

  private onMouseDown = (e: MouseEvent): void => {
    this.mouseButtons |= 1 << e.button;
    this.mousePressed |= 1 << e.button;
  };

  private onMouseUp = (e: MouseEvent): void => {
    this.mouseButtons &= ~(1 << e.button);
    this.mouseReleased |= 1 << e.button;
  };

  private onMouseMove = (e: MouseEvent): void => {
    if (!this.pointerLocked) return;
    // Clamp single-event spikes (some browsers report huge deltas when lock is re-acquired).
    const dx = Math.max(-250, Math.min(250, e.movementX));
    const dy = Math.max(-250, Math.min(250, e.movementY));
    this.mouseDX += dx;
    this.mouseDY += dy;
  };

  private onLockChange = (): void => {
    this.pointerLocked = document.pointerLockElement === this.element;
  };
}
