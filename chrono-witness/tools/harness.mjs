// Shared in-page harness for automated playthroughs: walking with collision, aiming, using
// interactables, scanning and answering dialogue through the real game simulation.
// Harness installed in the page: movement along nav paths, aiming, interacting, dialogue.
export async function installHarness(page, missionId) {
  await page.evaluate((missionId) => {
    const g = window.__game;
    const H = (window.__H = {});
    H.pos = () => {
      const p = g.player.position;
      return [+p.x.toFixed(2), +p.y.toFixed(2), +p.z.toFixed(2)];
    };
    H.stage = () => g.missions.state.get(missionId)?.stage ?? null;
    H.missionState = (id) => g.missions.state.get(id)?.state;
    H.flag = (f) => g.facts.get(f);
    H.face = (x, z, y) => {
      const p = g.player.position;
      g.player.yaw = Math.atan2(-(x - p.x), -(z - p.z));
      if (y !== undefined) {
        const eye = p.y + g.player.controller.eyeHeight;
        g.player.pitch = Math.atan2(y - eye, Math.hypot(x - p.x, z - p.z));
      } else g.player.pitch = 0;
    };
    // walk a list of points; returns {ok, stuckAt, minY}
    H.walkPoints = (pts, opts = {}) => {
      const sprint = !!opts.sprint;
      let minDrop = 0;
      for (let pi = 0; pi < pts.length; pi++) {
        const [x, z] = pts[pi];
        const last = pi === pts.length - 1;
        let best = 1e9;
        let stall = 0;
        for (let i = 0; i < 2400; i++) {
          const p = g.player.position;
          const d = Math.hypot(x - p.x, z - p.z);
          if (d < (last ? (opts.tol ?? 0.45) : 0.8)) break;
          if (d < best - 0.05) {
            best = d;
            stall = 0;
          } else if (++stall > 150) {
            if (!last && d < 1.6) break; // intermediate node occupied (NPC) — carry on
            g.input.simulate('KeyW', false);
            g.input.simulate('ShiftLeft', false);
            return { ok: false, stuckAt: H.pos(), target: [x, z], stage: H.stage() };
          }
          H.face(x, z);
          g.input.simulate('KeyW', true);
          if (sprint) g.input.simulate('ShiftLeft', true);
          if (opts.jumpEvery && i % opts.jumpEvery === 0) g.input.simulate('Space', true);
          g.step(1 / 30);
          g.input.simulate('Space', false);
          if (g.state !== 'playing') {
            g.input.simulate('KeyW', false);
            return { ok: false, stuckAt: H.pos(), reason: 'state ' + g.state, stage: H.stage() };
          }
          const ground = g.world.groundHeight(p.x, p.y + 0.5, p.z, 40);
          if (ground === null) minDrop = Math.min(minDrop, -999);
          else minDrop = Math.min(minDrop, p.y - ground);
        }
      }
      g.input.simulate('KeyW', false);
      g.input.simulate('ShiftLeft', false);
      g.step(0.2);
      return { ok: true, pos: H.pos(), minDrop: +minDrop.toFixed(2) };
    };
    H.navPath = (x, z) => {
      const nav = g.npcs.nav;
      const p = g.player.position;
      const path = nav.findPath(p, { x, y: p.y, z, clone() { return { x, y: p.y, z }; } });
      return path ? path.map((v) => [v.x, v.z]) : null;
    };
    H.walkTo = (x, z, opts) => {
      const path = H.navPath(x, z);
      if (!path) return { ok: false, reason: 'no path' };
      return H.walkPoints(path, opts);
    };
    // aim at interactable and press E (hold if needed)
    H.use = (id, holdSec) => {
      const it = g.interactions.items.get(id);
      if (!it) return { ok: false, reason: 'no interactable ' + id };
      const tp = g.interactions.worldPos(it, it.position.clone());
      H.face(tp.x, tp.z, tp.y);
      g.step(1 / 30);
      const focused = g.interactions.focused?.id;
      if (focused !== id) return { ok: false, reason: `focused ${focused ?? 'nothing'} instead of ${id}`, dist: Math.hypot(tp.x - g.player.position.x, tp.z - g.player.position.z).toFixed(2) };
      g.input.simulate('KeyE', true);
      g.step(holdSec ?? 1 / 30);
      g.input.simulate('KeyE', false);
      g.step(1 / 30);
      return { ok: true };
    };
    H.scan = (id) => {
      g.input.simulate('KeyQ', true);
      g.step(1 / 30);
      g.input.simulate('KeyQ', false);
      const r = H.use(id, 1.0);
      g.input.simulate('KeyQ', true);
      g.step(1 / 30);
      g.input.simulate('KeyQ', false);
      return r;
    };
    // dialogue: pick choice index (1-based) or continue
    H.dialogueOpen = () => g.ui.dialogueOpen;
    H.dialogueText = () => document.querySelector('.dialogue .line')?.textContent ?? '';
    H.say = (choices = []) => {
      const seen = [];
      let guard = 0;
      while (g.ui.dialogueOpen && guard++ < 30) {
        seen.push(H.dialogueText().slice(0, 50));
        const btns = document.querySelectorAll('.dialogue .choices button');
        if (btns.length) {
          const c = choices.length ? choices.shift() : 1;
          btns[Math.min(btns.length, c) - 1].click();
        } else {
          g.input.simulate('KeyE', true);
          g.step(1 / 30);
          g.input.simulate('KeyE', false);
        }
        g.step(1 / 30);
      }
      return seen;
    };
    H.clickButton = (text) => {
      const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes(text));
      if (b) b.click();
      return !!b;
    };
    H.modalText = () => document.querySelector('.modal-layer .panel')?.textContent?.slice(0, 120) ?? '';
  }, missionId);
}
