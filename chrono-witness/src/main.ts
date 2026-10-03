import { Game } from './core/Game';

function fatal(msg: string): void {
  const ui = document.getElementById('ui')!;
  ui.innerHTML = `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:auto"><div style="max-width:560px;padding:28px;background:#121315;border:1px solid #333;border-radius:6px;font-family:system-ui;color:#eee;line-height:1.5"><h2 style="margin-top:0">CHRONO WITNESS could not start</h2><p>${msg}</p></div></div>`;
}

const canvas = document.getElementById('view') as HTMLCanvasElement;
const probe = document.createElement('canvas').getContext('webgl2');
if (!probe) {
  fatal('This browser or GPU does not support WebGL 2. Please use a current version of Chrome, Edge, Firefox or Safari with hardware acceleration enabled.');
} else {
  try {
    const game = new Game(canvas, document.getElementById('ui')!);
    game.start().catch((e) => {
      console.error(e);
      fatal(`Startup error: ${String(e?.message ?? e)}`);
    });
  } catch (e) {
    console.error(e);
    fatal(`Startup error: ${String((e as Error)?.message ?? e)}`);
  }
}
