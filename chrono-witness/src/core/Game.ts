import * as THREE from 'three';
import { EventBus, type GameEvents } from './Events';
import { Input } from './Input';
import { loadSettings, saveSettings, type Settings } from './Settings';
import type { GameContext } from './GameContext';
import { RenderSystem } from '../render/RenderSystem';
import { PerfStats } from '../render/PerfStats';
import { AdaptiveQuality } from '../render/AdaptiveQuality';
import { Assets } from '../render/Assets';
import { MaterialLibrary } from '../render/Materials';
import { Environment } from '../render/Environment';
import { ResourceTracker, disposeObject } from '../render/Disposal';
import { CollisionWorld } from '../physics/CollisionWorld';
import { Player } from '../player/Player';
import { FirstPersonHands } from '../player/FirstPersonHands';
import { InteractionSystem } from '../player/Interaction';
import { CharacterLibrary } from '../npc/CharacterLibrary';
import { NPCManager } from '../npc/NPCManager';
import type { NPC } from '../npc/NPC';
import { FactStore } from '../missions/FactStore';
import { MissionSystem } from '../missions/MissionSystem';
import type { DialogueDef, DialogueNode, Effect, ItemDef, JournalEntry } from '../missions/types';
import { AudioSystem } from '../audio/AudioSystem';
import { SaveSystem, type CheckpointSnapshot } from '../save/SaveSystem';
import { UI } from '../ui/UI';
import type { ChapterConfig, ChapterRuntime, CinematicShot } from '../chapters/types';
import { CHAPTERS, HQ_ID, creditsHtml } from '../chapters/registry';
import { Benchmark } from '../bench/Benchmark';

type GameState = 'boot' | 'menu' | 'loading' | 'playing' | 'paused' | 'cinematic' | 'summary';

/**
 * Top-level orchestrator. Owns the systems, the frame loop, the game state machine and chapter
 * transitions, and implements the GameContext services that chapters call.
 */
export class Game implements GameContext {
  readonly events = new EventBus<GameEvents>();
  readonly settings: Settings = loadSettings();
  readonly input: Input;
  scene = new THREE.Scene();
  readonly render: RenderSystem;
  readonly world = new CollisionWorld();
  readonly player: Player;
  readonly camera: THREE.PerspectiveCamera;
  readonly hands: FirstPersonHands;
  readonly interactions: InteractionSystem;
  readonly assets: Assets;
  materials: MaterialLibrary;
  readonly characters: CharacterLibrary;
  npcs: NPCManager;
  readonly facts = new FactStore();
  readonly missions: MissionSystem;
  readonly audio: AudioSystem;
  readonly save = new SaveSystem();
  env: Environment;
  tracker = new ResourceTracker();
  readonly ui: UI;
  readonly chapters = CHAPTERS;
  readonly stats = new PerfStats();
  private adaptive: AdaptiveQuality;
  state: GameState = 'boot';
  private chapter: ChapterConfig | null = null;
  private runtime: ChapterRuntime | null = null;
  private time = 0;
  private lastFrame = performance.now();
  private frameBudgetAcc = 0;
  private markers = new Map<string, { pos: THREE.Vector3; label: string }>();
  private scanned = new Set<string>();
  private journalUnlocked = new Set<string>();
  private dialogue: { def: DialogueDef; node: string; npc?: NPC } | null = null;
  private observeEnergy = 1;
  private observingNow = false;
  private scannerOn = false;
  private scanTimer = 0;
  private cine: { shots: CinematicShot[]; i: number; t: number; onDone: () => void; skipHold: number } | null = null;
  private chapterStartTime = 0;
  private fpsVisible = false;
  private benchmark: Benchmark | null = null;
  private pendingIntense: ((r: 'play' | 'skip') => void) | null = null;
  private loadToken = 0;
  private showMarkers = true;

  constructor(private readonly canvas: HTMLCanvasElement, uiRoot: HTMLElement) {
    this.input = new Input(canvas);
    this.player = new Player(this.world, this.settings);
    this.camera = this.player.camera;
    this.render = new RenderSystem(canvas, this.scene, this.camera);
    this.hands = new FirstPersonHands(this.render.overlayScene);
    this.interactions = new InteractionSystem(this.world);
    this.assets = new Assets(this.settings.graphics, this.render.maxAnisotropy);
    this.materials = new MaterialLibrary(this.assets);
    this.characters = new CharacterLibrary(this.assets);
    this.npcs = new NPCManager(this.characters);
    this.missions = new MissionSystem(this.facts, this.events);
    this.audio = new AudioSystem(this.settings, this.events);
    this.env = new Environment(this.scene, this.settings);
    this.ui = new UI(uiRoot, this.settings);
    this.adaptive = new AdaptiveQuality(
      () => this.render.resolutionScale,
      (s) => this.render.setResolutionScale(s),
      this.settings.graphics.resolutionScale,
      this.settings.graphics.adaptiveTarget,
    );
    this.render.apply(this.settings.graphics);
    this.applySettings(true);
    this.wireEvents();
    this.wirePlayerAudio();
    window.addEventListener('resize', this.onResize);
    this.onResize();
    (window as unknown as { __game: Game }).__game = this; // automation hook (benchmarks, smoke tests)
  }

  // ======================================================================= boot
  async start(): Promise<void> {
    this.ui.showHUD(false);
    await Promise.all([this.characters.loadAnimations(), this.hands.load(this.assets)]);
    await this.loadChapter(HQ_ID, false, true);
    this.showMainMenu();
    requestAnimationFrame(this.frame);
  }

  get observing(): boolean {
    return this.observingNow;
  }

  get timeScale(): number {
    return this.observingNow ? 0.35 : 1;
  }

  // ======================================================================= events
  private wireEvents(): void {
    const ev = this.events;
    // Player actions become facts; missions only ever react to facts.
    ev.on('interact', ({ id }) => this.setFact(`interact.${id}`));
    ev.on('enterZone', ({ id }) => this.setFact(`zone.${id}`));
    ev.on('scanned', ({ id }) => this.setFact(`scan.${id}`));
    ev.on('dialogueNode', ({ dialogue, node }) => this.setFact(`dlg.${dialogue}.${node}`));
    ev.on('dialogueEnded', ({ dialogue }) => this.setFact(`dlgdone.${dialogue}`));
    ev.on('itemAdded', ({ id }) => {
      const it = this.itemDef(id);
      this.ui.hud.toast(`Received: ${it?.name ?? id}`, 'item');
      this.audio.ui('confirm');
      this.missions.evaluate();
    });
    ev.on('itemRemoved', () => this.missions.evaluate());
    ev.on('notify', ({ text, kind }) => {
      this.ui.hud.toast(text, kind);
      if (kind === 'journal') this.audio.ui('journal');
      if (kind === 'warning') this.audio.ui('warn');
    });
    ev.on('subtitle', ({ speaker, text, duration }) => this.ui.hud.subtitle(speaker, text, duration));
    ev.on('soundCue', (c) => {
      this.ui.hud.cue(c.label, c.direction, !!c.danger, this.time);
      if (c.danger && this.settings.accessibility.subtitles) this.ui.hud.subtitle('', `[${c.label}]`, 2.2, true);
    });
    ev.on('playerDowned', ({ reason }) => this.onDowned(reason));
    this.facts.onChange = () => this.missions.evaluate();
    this.missions.externalEffects = (e) => this.handleEffect(e);
  }

  private wirePlayerAudio(): void {
    this.player.onFootstep = (s, i) => this.audio.footstep(s, i);
    this.player.onLand = (s, v) => this.audio.footstep(s, Math.min(1, v / 6));
    this.player.controller.onMantle = () => {
      this.hands.setPose('fp_climb');
      window.setTimeout(() => this.refreshHandPose(), 600);
    };
  }

  private setFact(f: string): void {
    this.facts.set(f, true);
  }

  private handleEffect(e: Effect): boolean {
    if ('checkpoint' in e) {
      this.checkpoint(e.checkpoint);
      return true;
    }
    if ('journal' in e) {
      this.unlockJournal(e.journal);
      return true;
    }
    if ('artifact' in e) {
      this.save.addArtifact(e.artifact);
      const a = this.chapter?.artifacts.find((x) => x.id === e.artifact);
      this.ui.hud.toast(`Artifact catalogued: ${a?.name ?? e.artifact}`, 'journal');
      return true;
    }
    if ('event' in e) {
      this.facts.set(`event.${e.event}`, true);
      return true;
    }
    return false;
  }

  private unlockJournal(id: string): void {
    if (this.journalUnlocked.has(id)) return;
    this.journalUnlocked.add(id);
    const entry = this.chapter?.journal.find((j) => j.id === id);
    if (entry) this.ui.hud.toast(`Journal: ${entry.title}`, 'journal');
  }

  itemDef(id: string): ItemDef | undefined {
    return this.chapter?.items.find((i) => i.id === id);
  }

  // ======================================================================= chapters
  async travelTo(chapterId: string, resume: boolean): Promise<void> {
    if (this.state === 'loading') return;
    this.ui.closeModal();
    this.audio.temporalWhoosh();
    // temporal transition (shortened and softened in reduced-flash mode)
    const reduced = this.settings.accessibility.reducedFlash;
    await this.animateUniform((t) => {
      this.render.grade.uniforms.uTransition.value = t * (reduced ? 0.35 : 1) * this.settings.accessibility.motionEffects;
      this.render.grade.uniforms.uFade.value = reduced ? t * 0.9 : Math.max(0, t * 1.4 - 0.4);
    }, reduced ? 1.0 : 1.4);
    await this.loadChapter(chapterId, resume, false);
  }

  returnToHQ(): void {
    void this.travelTo(HQ_ID, false);
  }

  private async loadChapter(id: string, resume: boolean, silent: boolean): Promise<void> {
    const cfg = this.chapters.find((c) => c.id === id);
    if (!cfg || !cfg.load) throw new Error(`Chapter ${id} is not available`);
    const token = ++this.loadToken;
    this.state = 'loading';
    this.input.exitPointerLock();
    this.ui.showHUD(false);
    this.ui.closeDialogue();
    this.ui.hud.clearTransient();
    if (!silent) this.ui.loading({ destination: cfg.destination, title: cfg.title, date: cfg.dateLabel, fact: cfg.loadingFacts ? cfg.loadingFacts[Math.floor(Math.random() * cfg.loadingFacts.length)] : undefined });
    await this.unloadChapter();
    const report = (f: number, label: string): void => {
      if (!silent) this.ui.loadingProgress(f, label);
    };
    try {
      report(0.02, 'Loading chapter code');
      const mod = await cfg.load();
      if (token !== this.loadToken) return;
      this.chapter = cfg;
      this.facts.restore({ flags: {}, inventory: [] });
      this.missions.load(cfg.missions);
      this.scanned.clear();
      this.journalUnlocked = new Set(cfg.journal.filter((j) => j.initiallyKnown).map((j) => j.id));
      const runtime = mod.createRuntime(this, cfg);
      this.runtime = runtime;
      await runtime.build((f, l) => report(0.05 + f * 0.85, l));
      if (token !== this.loadToken) return;
      this.scene.add(runtime.root);
      this.scene.add(this.npcs.group);
      report(0.92, 'Compiling shaders');
      await this.render.precompile(this.scene, this.camera);
      report(1, 'Ready');
      if (this.assets.issues.length && !silent) {
        this.ui.loadingWarning(`${this.assets.issues.length} asset(s) could not be loaded and were replaced with fallbacks: ${this.assets.issues.map((i) => i.url).slice(0, 4).join(', ')}${this.assets.issues.length > 4 ? '…' : ''}`);
        console.warn('Asset issues', this.assets.issues);
      }
      // start state
      const prog = this.save.chapter(cfg.id);
      const snap = resume ? prog.checkpoint : null;
      this.missions.start();
      if (snap) this.restoreSnapshot(snap);
      else {
        const cp = cfg.startCheckpoint;
        this.spawnAt(cp);
        runtime.applyCheckpoint(cp, {});
        this.missions.evaluate();
      }
      this.chapterStartTime = this.time;
      this.ui.hud.setLocation(cfg.destination, cfg.dateLabel);
      this.hands.setEnvironment(this.scene.environment, this.scene.environmentIntensity * 0.9);
      if (!silent) await new Promise((r) => setTimeout(r, this.assets.issues.length ? 1600 : 250));
      this.ui.hideLoading();
      this.render.grade.uniforms.uTransition.value = 0;
      if (silent) {
        this.render.grade.uniforms.uFade.value = 0;
        return;
      }
      await this.animateUniform((t) => (this.render.grade.uniforms.uFade.value = 1 - t), 0.8);
      const introKey = `${cfg.id}`;
      if (!snap && cfg.intro?.length && !this.save.data.seenIntro[introKey]) {
        this.save.data.seenIntro[introKey] = true;
        this.save.write();
        this.playCinematic(cfg.intro, () => this.enterPlay());
      } else this.enterPlay();
    } catch (err) {
      console.error(err);
      if (silent) throw err;
      this.ui.loadingError(String((err as Error)?.message ?? err), () => void this.loadChapter(id, resume, false), () => void this.loadChapter(HQ_ID, false, false));
    }
  }

  private async unloadChapter(): Promise<void> {
    this.runtime?.dispose();
    if (this.runtime) {
      this.scene.remove(this.runtime.root);
      disposeObject(this.runtime.root);
    }
    this.runtime = null;
    this.npcs.dispose();
    this.npcs = new NPCManager(this.characters);
    this.world.dispose();
    this.interactions.clear();
    this.markers.clear();
    this.tracker.disposeAll();
    this.env.dispose();
    this.env = new Environment(this.scene, this.settings);
    this.materials.dispose();
    this.materials = new MaterialLibrary(this.assets);
    this.audio.stopAllLoops();
    await this.assets.purge();
    this.player.controller.ladders = [];
    this.player.surfaceAt = null;
    this.player.carrying = false;
    this.player.scriptSpeed = 1;
    this.hands.hold(null);
    this.hands.setPose('hidden');
    this.observingNow = false;
    this.scannerOn = false;
    this.interactions.scanMode = false;
    this.interactions.observeMode = false;
    this.render.grade.uniforms.uObserve.value = 0;
    // make sure nothing else remains in the scene graph
    for (const c of [...this.scene.children]) {
      this.scene.remove(c);
      disposeObject(c);
    }
    this.scene.add(this.env.group);
    this.chapter = null;
  }

  private spawnAt(cpId: string): void {
    const cp = this.chapter!.checkpoints[cpId];
    if (!cp) throw new Error(`Unknown checkpoint ${cpId}`);
    const p = new THREE.Vector3(...cp.position);
    const g = this.world.groundHeight(p.x, p.y + 1.5, p.z, 8);
    if (g !== null) p.y = g + 0.02;
    this.player.spawn(p, cp.yaw);
  }

  private enterPlay(): void {
    this.state = 'playing';
    this.ui.closeModal();
    this.ui.showHUD(true);
    this.ui.hud.showDeviceBar(this.chapter?.id !== HQ_ID);
    this.canvas.focus();
    this.lockGrace = 1.0;
    // headless automation: pointer lock throttles rAF in headless Chromium, so tests drive input directly
    if (!(window as unknown as { __automation?: boolean }).__automation) this.input.requestPointerLock();
    this.audio.unlock();
  }

  // ======================================================================= checkpoints
  checkpoint(id: string): void {
    if (!this.chapter || !this.runtime || this.chapter.id === HQ_ID) return;
    const snap: CheckpointSnapshot = {
      id,
      savedAt: new Date().toISOString(),
      ...this.facts.snapshot(),
      missions: this.missions.snapshot(),
      scanned: [...this.scanned],
      journal: [...this.journalUnlocked],
      script: this.runtime.scriptState(),
    };
    this.save.saveCheckpoint(this.chapter.id, snap);
    this.save.addRecords([...this.scanned, ...this.journalUnlocked]);
    this.save.chapter(this.chapter.id).playTimeSec += Math.round(this.time - this.chapterStartTime);
    this.chapterStartTime = this.time;
    this.events.emit('checkpoint', { id });
    this.ui.hud.toast(`Checkpoint — ${this.chapter.checkpoints[id]?.label ?? id}`, 'checkpoint');
    this.audio.ui('checkpoint');
  }

  private restoreSnapshot(s: CheckpointSnapshot): void {
    this.facts.restore({ flags: s.flags, inventory: s.inventory });
    this.missions.restore(s.missions);
    this.scanned = new Set(s.scanned);
    this.journalUnlocked = new Set(s.journal);
    this.spawnAt(s.id);
    this.runtime!.applyCheckpoint(s.id, s.script);
    this.missions.evaluate();
  }

  restartFromCheckpoint(): void {
    if (!this.chapter) return;
    const snap = this.save.chapter(this.chapter.id).checkpoint;
    this.ui.closeModal();
    this.ui.hud.clearTransient();
    this.ui.closeDialogue();
    this.dialogue = null;
    this.player.movementLocked = false;
    this.player.lookLocked = false;
    this.player.carrying = false;
    if (snap) this.restoreSnapshot(snap);
    else {
      this.facts.restore({ flags: {}, inventory: [] });
      this.missions.load(this.chapter.missions);
      this.missions.start();
      this.spawnAt(this.chapter.startCheckpoint);
      this.runtime!.applyCheckpoint(this.chapter.startCheckpoint, {});
      this.missions.evaluate();
    }
    this.enterPlay();
  }

  downPlayer(reason: string): void {
    this.events.emit('playerDowned', { reason });
  }

  private onDowned(reason: string): void {
    if (this.state !== 'playing') return;
    this.state = 'summary';
    this.input.exitPointerLock();
    this.player.addTrauma(0.6);
    void this.animateUniform((t) => (this.render.grade.uniforms.uFade.value = t * 0.85), 0.6).then(() => {
      this.ui.confirm('You were caught', `${reason}\n\nThe temporal device pulls you back to your last checkpoint. No progress before that checkpoint is lost.`, [
        {
          label: 'Retry from checkpoint',
          primary: true,
          action: () => {
            this.render.grade.uniforms.uFade.value = 0;
            this.restartFromCheckpoint();
          },
        },
      ]);
    });
  }

  completeChapter(): void {
    if (!this.chapter || !this.runtime) return;
    const cfg = this.chapter;
    const run = this.time - this.chapterStartTime + (this.save.chapter(cfg.id).playTimeSec ?? 0);
    const optionalDone = cfg.missions.filter((m) => m.kind === 'optional' && this.missions.state.get(m.id)?.state === 'completed').map((m) => m.id);
    const artifacts = cfg.artifacts.filter((a) => this.facts.get(`artifact.${a.id}`) || this.save.data.artifacts.includes(a.id)).map((a) => a.id);
    this.save.completeChapter(cfg.id, run, optionalDone, artifacts, [...this.scanned, ...this.journalUnlocked]);
    const finish = (): void => {
      this.state = 'summary';
      this.input.exitPointerLock();
      this.ui.showHUD(false);
      const optTotal = cfg.missions.filter((m) => m.kind === 'optional').length;
      this.ui.summary(`${cfg.title} — complete`, [
        `${cfg.destination}, ${cfg.dateLabel}.`,
        `Optional tasks completed: ${optionalDone.length} / ${optTotal}. Historical records discovered: ${this.scanned.size} / ${cfg.scans.length}.`,
        'Your personal story here was fiction; the documented course of the war continued exactly as it happened. The journal’s Historical Record separates what is documented from what was reconstructed.',
      ], () => this.returnToHQ());
    };
    if (cfg.outro?.length) this.playCinematic(cfg.outro, finish);
    else finish();
  }

  // ======================================================================= dialogue
  startDialogue(id: string, npc?: NPC): void {
    const def = this.chapter?.dialogues.find((d) => d.id === id);
    if (!def) return;
    const entry = def.entries.find((e) => this.facts.test(e.condition));
    if (!entry) return;
    this.dialogue = { def, node: entry.node, npc };
    this.player.movementLocked = true;
    this.player.lookLocked = true;
    this.input.exitPointerLock(); // free the cursor so choices can be clicked (number keys also work)
    if (npc) {
      npc.faceTowards(this.player.position);
      npc.hasLookTarget = true;
      npc.lookTarget.copy(this.camera.position);
      if (npc.mode === 'idle' && ['idle', 'idle_alt'].includes(npc.pose)) npc.play('talk');
    }
    this.showDialogueNode();
  }

  private showDialogueNode(): void {
    const d = this.dialogue;
    if (!d) return;
    const node: DialogueNode | undefined = d.def.nodes[d.node];
    if (!node) return this.endDialogue();
    this.missions.runEffects(node.effects);
    this.events.emit('dialogueNode', { dialogue: d.def.id, node: d.node });
    const choices = node.choices?.filter((c) => this.facts.test(c.condition));
    this.ui.dialogue(
      node.speaker,
      node.text,
      choices?.length
        ? choices.map((c) => ({
            text: c.text,
            onPick: () => {
              this.audio.ui('click');
              this.missions.runEffects(c.effects);
              if (c.next) {
                d.node = c.next;
                this.showDialogueNode();
              } else this.endDialogue();
            },
          }))
        : null,
      () => {
        this.audio.ui('click');
        if (node.next) {
          d.node = node.next;
          this.showDialogueNode();
        } else this.endDialogue();
      },
    );
  }

  private endDialogue(): void {
    const d = this.dialogue;
    this.dialogue = null;
    this.ui.closeDialogue();
    this.player.movementLocked = false;
    this.player.lookLocked = false;
    if (this.state === 'playing') {
      this.lockGrace = 1.2;
      if (!(window as unknown as { __automation?: boolean }).__automation) this.input.requestPointerLock();
    }
    if (d?.npc) {
      d.npc.hasLookTarget = false;
      if (d.npc.currentClip === 'talk' && d.npc.mode === 'idle') d.npc.play(d.npc.pose);
    }
    if (d) this.events.emit('dialogueEnded', { dialogue: d.def.id });
  }

  // ======================================================================= cinematics
  playCinematic(shots: CinematicShot[], onDone: () => void): void {
    this.state = 'cinematic';
    this.ui.showHUD(false);
    this.ui.cinematic(true);
    this.cine = { shots, i: 0, t: 0, onDone, skipHold: 0 };
    this.showShotCaption();
  }

  private showShotCaption(): void {
    const c = this.cine!;
    const s = c.shots[c.i];
    this.ui.caption(s.kicker, s.caption, true);
  }

  private updateCinematic(dt: number): void {
    const c = this.cine!;
    if (this.input.isDown('skip') || this.input.isDown('jump')) c.skipHold += dt;
    else c.skipHold = 0;
    const s = c.shots[c.i];
    c.t += dt;
    const k = Math.min(1, c.t / s.duration);
    const e = k * k * (3 - 2 * k);
    if (s.from) {
      const to = s.to ?? s.from;
      _cp.fromArray(s.from.pos).lerp(_cp2.fromArray(to.pos), e);
      _cl.fromArray(s.from.look).lerp(_cl2.fromArray(to.look), e);
      this.camera.position.copy(_cp);
      this.camera.lookAt(_cl);
      this.camera.updateMatrixWorld();
    }
    if (k > 0.92) this.ui.caption(s.kicker, s.caption, false);
    if (c.skipHold > 0.8 || k >= 1) {
      if (c.skipHold > 0.8 || c.i + 1 >= c.shots.length) {
        this.cine = null;
        this.ui.cinematic(false);
        // restore player camera orientation
        this.player.spawn(this.player.position.clone(), this.player.yaw);
        c.onDone();
        return;
      }
      c.i++;
      c.t = 0;
      this.showShotCaption();
    }
  }

  // ======================================================================= services for chapters
  setDanger(text: string | null, secondsLeft?: number): void {
    this.ui.hud.setDanger(text, secondsLeft);
  }

  setMarker(id: string, pos: THREE.Vector3 | null, label = ''): void {
    if (!pos) this.markers.delete(id);
    else this.markers.set(id, { pos: pos.clone(), label });
  }

  confirmIntense(title: string, description: string): Promise<'play' | 'skip'> {
    if (!this.settings.accessibility.intenseSequencePrompt) return Promise.resolve('play');
    return new Promise((resolve) => {
      this.pendingIntense = resolve;
      this.state = 'paused';
      this.input.exitPointerLock();
      const done = (r: 'play' | 'skip'): void => {
        this.pendingIntense = null;
        this.ui.closeModal();
        this.enterPlay();
        resolve(r);
      };
      this.ui.confirm(title, description, [
        { label: 'Skip this sequence (progress kept)', action: () => done('skip') },
        { label: 'Experience it', primary: true, action: () => done('play') },
      ]);
    });
  }

  readDocument(title: string, text: string): void {
    this.pause(false);
    this.ui.readDocument(title, text, () => this.resume());
  }

  // ======================================================================= menus
  private showMainMenu(): void {
    this.state = 'menu';
    this.ui.showHUD(false);
    const last = Object.entries(this.save.data.chapters).find(([, p]) => p.checkpoint);
    const lastCfg = last ? this.chapters.find((c) => c.id === last[0]) : undefined;
    this.ui.mainMenu({
      canContinue: !!lastCfg,
      continueLabel: lastCfg ? `Continue — ${lastCfg.destination}, ${lastCfg.dateLabel}` : 'Continue',
      onContinue: () => {
        this.audio.unlock();
        if (lastCfg) void this.travelTo(lastCfg.id, true);
      },
      onHQ: () => {
        this.audio.unlock();
        this.ui.closeModal();
        this.enterPlay();
      },
      onSettings: () => this.ui.settingsScreen((g) => this.applySettings(g), () => this.showMainMenu()),
      onCredits: () => this.ui.credits(creditsHtml(), () => this.showMainMenu()),
      onBenchmark: () => this.showBenchmarkMenu(),
      onReset: () =>
        this.ui.confirm('Reset all progress?', 'This deletes every checkpoint, completed chapter and recovered artifact on this device. Settings are kept.', [
          { label: 'Cancel', action: () => this.showMainMenu() },
          {
            label: 'Reset',
            primary: true,
            action: () => {
              this.save.resetAll();
              this.showMainMenu();
            },
          },
        ]),
      storageNote: this.save.persistent ? null : 'Browser storage is unavailable (private mode?) — progress will not persist after closing this tab.',
    });
  }

  pause(showMenu = true): void {
    if (this.state !== 'playing') return;
    this.state = 'paused';
    this.input.exitPointerLock();
    if (showMenu) this.showPauseMenu();
  }

  private showPauseMenu(): void {
    const inChapter = this.chapter && this.chapter.id !== HQ_ID;
    this.ui.pauseMenu({
      title: this.chapter ? `${this.chapter.destination} — ${this.chapter.dateLabel}` : '',
      onResume: () => this.resume(),
      onJournal: () => this.openJournal(() => this.showPauseMenu()),
      onInventory: () => this.openInventory(() => this.showPauseMenu()),
      onSettings: () => this.ui.settingsScreen((g) => this.applySettings(g), () => this.showPauseMenu()),
      onSkip: inChapter && this.runtime?.skipSequence && this.facts.get('sequence.active') ? () => (this.runtime!.skipSequence!(), this.resume()) : null,
      onRestart: inChapter ? () => this.restartFromCheckpoint() : null,
      onHQ: inChapter ? () => this.returnToHQ() : null,
      onMain: () => {
        this.ui.closeModal();
        if (inChapter) void this.loadChapter(HQ_ID, false, false).then(() => this.showMainMenu());
        else this.showMainMenu();
      },
    });
  }

  resume(): void {
    if (this.state !== 'paused' || this.pendingIntense) return;
    this.ui.closeModal();
    this.enterPlay();
  }

  openJournal(onClose: () => void, tab?: 'objectives' | 'evidence' | 'history'): void {
    const c = this.chapter;
    const entries: JournalEntry[] = c ? [...c.journal.filter((j) => this.journalUnlocked.has(j.id)), ...c.scans.filter((s) => this.scanned.has(s.id))] : [];
    this.ui.journal(
      {
        chapter: c,
        missions: c ? c.missions.map((m) => ({ def: m, state: this.missions.state.get(m.id)! })) : [],
        items: this.facts.inventory.map((i) => this.itemDef(i)).filter((x): x is ItemDef => !!x),
        entries,
        sources: c?.sources ?? {},
        unlockedScans: this.scanned.size,
        totalScans: c?.scans.length ?? 0,
      },
      onClose,
      tab,
    );
  }

  openInventory(onClose: () => void): void {
    const items = this.facts.inventory.map((i) => this.itemDef(i)).filter((x): x is ItemDef => !!x);
    this.ui.inventory(items, (it) => this.ui.readDocument(it.name, it.readable ?? '', () => this.openInventory(onClose)), onClose);
  }

  openSelector(): void {
    this.pause(false);
    this.ui.selector(this.chapters.filter((c) => c.id !== HQ_ID), this.save.data, {
      onTravel: (id, resume) => void this.travelTo(id, resume),
      onClose: () => this.resume(),
    });
  }

  private showBenchmarkMenu(): void {
    const routes = Benchmark.routes();
    this.ui.benchmarkMenu(routes, (id) => void this.runBenchmark(id), () => this.showMainMenu(), 'Runs a scripted camera route and records average FPS, 1% lows, frame-time spikes and renderer resources with the current graphics settings. Close other tabs for consistent results.');
  }

  async runBenchmark(routeId: string, seconds = 30): Promise<Record<string, unknown>> {
    this.ui.closeModal();
    this.benchmark = new Benchmark(this);
    const result = await this.benchmark.run(routeId, seconds);
    this.benchmark = null;
    if (!(window as unknown as { __automation?: boolean }).__automation) {
      this.ui.benchmarkResult(Benchmark.rows(result), JSON.stringify(result, null, 2), () => this.showMainMenu());
    }
    return result;
  }

  /** Used by the benchmark to load chapters directly. */
  async loadForBenchmark(chapterId: string): Promise<ChapterRuntime | null> {
    await this.loadChapter(chapterId, false, false);
    this.cine = null;
    this.ui.cinematic(false);
    this.state = 'cinematic'; // benchmark drives the camera
    this.ui.closeModal();
    return this.runtime;
  }

  get currentRuntime(): ChapterRuntime | null {
    return this.runtime;
  }

  get currentChapter(): ChapterConfig | null {
    return this.chapter;
  }

  setBenchmarkCamera(pos: THREE.Vector3, look: THREE.Vector3): void {
    this.camera.position.copy(pos);
    this.camera.lookAt(look);
    this.camera.updateMatrixWorld();
  }

  // ======================================================================= settings
  applySettings(graphicsChanged: boolean): void {
    saveSettings(this.settings);
    const g = this.settings.graphics;
    if (graphicsChanged) {
      this.render.apply(g);
      this.adaptive.maxScale = g.resolutionScale;
    }
    this.adaptive.enabled = g.adaptiveQuality;
    this.adaptive.targetFps = g.adaptiveTarget;
    this.env.applyShadowSettings(this.render.shadowMapSize, g.shadowDistance);
    this.camera.far = g.drawDistance + 400;
    this.camera.updateProjectionMatrix();
    this.npcs.shadowDistance = g.shadowDistance * 0.8;
    this.npcs.animLodDistance = g.npcAnimLodDistance;
    this.audio.applyVolumes();
    this.ui.applyAccessibility();
    this.events.emit('settingsChanged', undefined);
  }

  private onResize = (): void => {
    this.render.resize(window.innerWidth, window.innerHeight);
  };

  // ======================================================================= frame
  private frame = (now: number): void => {
    requestAnimationFrame(this.frame);
    const cap = this.settings.graphics.fpsCap;
    const elapsed = now - this.lastFrame;
    if (cap > 0) {
      this.frameBudgetAcc += elapsed;
      this.lastFrame = now;
      const budget = 1000 / cap;
      if (this.frameBudgetAcc < budget - 0.5) return;
      this.frameBudgetAcc = Math.min(budget, this.frameBudgetAcc - budget);
    } else this.lastFrame = now;
    const frameMs = cap > 0 ? Math.max(elapsed, 1000 / cap) : elapsed;
    const dt = Math.min(0.1, frameMs / 1000);
    if (this.state === 'paused' || this.state === 'summary' || this.state === 'menu') {
      // menus: keep the world visible, animate slowly, no simulation
      if (this.state === 'menu') this.menuCamera(dt);
      else {
        this.input.endFrame();
        return;
      }
    }
    if (this.state === 'loading') {
      this.input.endFrame();
      return;
    }
    this.time += dt;
    this.update(dt);
    this.render.render(this.time);
    this.stats.push(frameMs);
    if (this.state === 'playing') this.adaptive.update(frameMs, dt);
    if (this.fpsVisible) this.showFps();
    this.input.endFrame();
  };

  private menuCamera(dt: number): void {
    // gentle drift so the headquarters reads as a living space behind the menu
    this.player.yaw += dt * 0.02;
    this.player.update(0, this.input, false);
  }

  private update(dt: number): void {
    const inp = this.input;
    if (this.state === 'cinematic') {
      if (this.cine) this.updateCinematic(dt);
      else this.benchmark?.tick(dt);
      this.updateWorld(dt);
      return;
    }
    if (this.state !== 'playing') {
      if (this.state === 'menu') this.updateWorld(dt);
      return;
    }
    // pointer lock lost unexpectedly → pause (accessibility: never trap the cursor)
    const automation = (window as unknown as { __automation?: boolean }).__automation;
    if (!automation && !inp.pointerLocked && !this.dialogue && !this.ui.modalOpen && document.pointerLockElement === null && this.lockGrace <= 0) {
      this.pause();
      return;
    }
    this.lockGrace -= dt;
    if (inp.pressed('pause')) {
      if (this.dialogue) this.endDialogue();
      else this.pause();
      return;
    }
    if (inp.pressed('journal')) return this.pause(false), this.openJournal(() => this.resume());
    if (inp.pressed('inventory')) return this.pause(false), this.openInventory(() => this.resume());
    if (inp.pressed('device') || (inp.pressed('skip') && this.facts.get('sequence.active'))) {
      if (this.runtime?.skipSequence && this.facts.get('sequence.active')) {
        this.runtime.skipSequence();
      }
    }
    if (inp.isDown('jump') && inp.pressed('crouch')) this.fpsVisible = !this.fpsVisible;

    const gameplay = !this.dialogue;
    // dialogue input
    if (this.dialogue) {
      for (let i = 0; i < 4; i++) if (inp.keyPressed(`Digit${i + 1}`) || inp.keyPressed(`Numpad${i + 1}`)) this.ui.dialogueKeys?.(i);
      if (inp.pressed('interact') || inp.pressed('jump')) this.ui.dialogueContinue?.();
    }

    this.updateDevice(dt, gameplay);
    this.player.update(dt, inp, gameplay);
    this.npcs.resolvePlayer(this.player.position, this.player.controller.radius);

    // interactions
    this.interactions.update(this.camera, this.player.forward);
    const f = this.interactions.focused;
    if (f && gameplay) {
      const label = this.scannerOn ? (this.scanned.has(f.scanId ?? '') ? 'Already recorded' : 'Scan') : this.interactions.promptText(f);
      const hold = this.scannerOn ? 0.9 : (f.holdTime ?? 0);
      const key = this.scannerOn ? 'E' : 'E';
      if (inp.isDown('interact') && hold > 0) {
        this.interactions.holdProgress += dt / hold;
        if (this.interactions.holdProgress >= 1) {
          this.interactions.holdProgress = 0;
          this.activate(f);
        }
      } else if (inp.pressed('interact') && hold === 0) this.activate(f);
      else if (!inp.isDown('interact')) this.interactions.holdProgress = 0;
      this.ui.hud.setPrompt(key, label, hold, this.interactions.holdProgress);
    } else this.ui.hud.setPrompt(null);

    // HUD objective
    const cur = this.missions.currentObjective();
    if (cur) {
      const pr = cur.objective.progress;
      this.ui.hud.setObjective(cur.objective.text, pr ? `${this.facts.countFlags(pr.flags)} / ${pr.total}` : undefined, cur.mission.title);
    } else this.ui.hud.setObjective(this.chapter?.id === HQ_ID ? 'Choose a destination at the temporal console' : null, undefined, this.chapter?.id === HQ_ID ? 'Headquarters' : 'Objective');

    this.updateWorld(dt);
    this.ui.hud.updateCues(this.time);
    this.ui.hud.updateMarkers(this.showMarkers ? this.markers : _emptyMarkers, this.camera, this.player.position, window.innerWidth, window.innerHeight);
  }

  private lockGrace = 0;

  private activate(i: import('../player/Interaction').Interactable): void {
    if (this.scannerOn) {
      if (!i.scanId || this.scanned.has(i.scanId)) return;
      this.scanned.add(i.scanId);
      this.audio.ui('scan');
      const e = this.chapter?.scans.find((s) => s.id === i.scanId);
      this.ui.hud.toast(`Recorded: ${e?.title ?? i.scanId}`, 'journal');
      if (e) this.ui.hud.subtitle('Temporal scanner', `${e.title}. ${e.text}`, Math.min(14, 4 + e.text.length / 22));
      this.events.emit('scanned', { id: i.scanId });
      return;
    }
    if (i.scanOnly) return;
    this.hands.reach();
    this.audio.ui('click');
    i.onInteract();
    this.events.emit('interact', { id: i.id });
  }

  /** Temporal device: scanner (Q toggles) and observation mode (F, limited energy). */
  private updateDevice(dt: number, gameplay: boolean): void {
    const inp = this.input;
    const inHQ = this.chapter?.id === HQ_ID;
    if (gameplay && !inHQ && inp.pressed('scan')) {
      this.scannerOn = !this.scannerOn;
      this.audio.ui(this.scannerOn ? 'scan' : 'click');
      this.refreshHandPose();
    }
    if (gameplay && !inHQ && inp.pressed('observe')) {
      if (this.observingNow) this.observingNow = false;
      else if (this.observeEnergy > 0.15) {
        this.observingNow = true;
        this.audio.temporalWhoosh();
      } else this.ui.hud.toast('Temporal device recharging', 'warning');
    }
    if (this.observingNow) {
      this.observeEnergy -= dt / 14;
      if (this.observeEnergy <= 0) {
        this.observeEnergy = 0;
        this.observingNow = false;
      }
    } else this.observeEnergy = Math.min(1, this.observeEnergy + dt / 30);
    this.interactions.observeMode = this.observingNow;
    this.interactions.scanMode = this.scannerOn;
    const g = this.render.grade.uniforms;
    g.uObserve.value += ((this.observingNow ? 1 : 0) - g.uObserve.value) * Math.min(1, dt * 4);
    this.ui.hud.setEnergy(this.observeEnergy);
    this.ui.hud.setMode(this.observingNow ? 'Temporal observation' : this.scannerOn ? 'Scanner active — aim and hold E' : null);
    this.hands.deviceGlow = this.scannerOn || this.observingNow ? 1 : 0.3;
    this.audio.muffled = this.observingNow ? 1 : this.env.indoor;

    // scanner brackets
    this.scanTimer -= dt;
    if (this.scannerOn && this.scanTimer <= 0) {
      this.scanTimer = 0.05;
      const list: { id: string; pos: THREE.Vector3; size: number; done: boolean; focus: boolean }[] = [];
      for (const it of this.interactions.items.values()) {
        if (!it.scanId) continue;
        const p = this.interactions.worldPos(it, new THREE.Vector3());
        if (p.distanceTo(this.camera.position) > 14) continue;
        list.push({ id: it.id, pos: p, size: it.radius, done: this.scanned.has(it.scanId), focus: this.interactions.focused === it });
      }
      this.ui.hud.updateBrackets(list, this.camera, window.innerWidth, window.innerHeight);
    } else if (!this.scannerOn) this.ui.hud.updateBrackets([], this.camera, 1, 1);
  }

  refreshHandPose(): void {
    if (this.scannerOn) this.hands.setPose('fp_scan');
    else if (this.player.carrying) this.hands.setPose('fp_grip_two');
    else if (this.handsHolding) this.hands.setPose('fp_hold');
    else this.hands.setPose('hidden');
  }

  handsHolding = false;

  private updateWorld(dt: number): void {
    const wdt = dt * this.timeScale;
    const focus = this.state === 'cinematic' ? this.camera.position : this.player.position;
    this.env.update(wdt, this.time, focus, this.camera);
    this.runtime?.update(wdt, this.time);
    this.npcs.update(wdt, this.camera, this.player.position);
    this.audio.listenerYaw = this.player.yaw;
    this.audio.listenerX = this.player.position.x;
    this.audio.listenerZ = this.player.position.z;
    if (this.player.controller.onLadder && this.hands.pose !== 'fp_climb') this.hands.setPose('fp_climb');
    else if (!this.player.controller.onLadder && this.hands.pose === 'fp_climb' && this.player.controller.state !== 'mantle') this.refreshHandPose();
    this.hands.update(dt, this.input.mouseDX, this.input.mouseDY, this.player.controller.horizontalSpeed, this.settings.accessibility.motionEffects);
  }

  private showFps(): void {
    const s = this.stats.summary(240);
    const r = PerfStats.resourceInfo(this.render.renderer);
    this.ui.hud.setFps(`${s.avgFps.toFixed(0)} fps  (1% low ${s.low1Fps.toFixed(0)})\n${s.avgMs.toFixed(1)} ms  max ${s.maxMs.toFixed(1)}\ncalls ${r.drawCalls}  tris ${(r.triangles / 1000).toFixed(0)}k\nscale ${this.render.resolutionScale.toFixed(2)}\npos ${this.player.position.x.toFixed(1)} ${this.player.position.y.toFixed(1)} ${this.player.position.z.toFixed(1)}`);
  }

  private animateUniform(fn: (t: number) => void, seconds: number): Promise<void> {
    return new Promise((resolve) => {
      const t0 = performance.now();
      const step = (): void => {
        const t = Math.min(1, (performance.now() - t0) / (seconds * 1000));
        fn(t);
        if (this.state !== 'loading') this.render.render(this.time);
        if (t < 1) requestAnimationFrame(step);
        else resolve();
      };
      step();
    });
  }
}

const _cp = new THREE.Vector3();
const _cp2 = new THREE.Vector3();
const _cl = new THREE.Vector3();
const _cl2 = new THREE.Vector3();
const _emptyMarkers = new Map<string, { pos: THREE.Vector3; label: string }>();
