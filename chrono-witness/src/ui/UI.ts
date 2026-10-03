import './styles.css';
import { h, clear } from './dom';
import { HUD } from './HUD';
import { buildSettingsPanel } from './SettingsPanel';
import type { Settings } from '../core/Settings';
import type { ChapterConfig, ArtifactDef } from '../chapters/types';
import type { SaveData } from '../save/SaveSystem';
import type { ItemDef, JournalEntry, SourceRef, MissionDef, MissionRuntimeState } from '../missions/types';

export interface JournalData {
  chapter: ChapterConfig | null;
  missions: { def: MissionDef; state: MissionRuntimeState }[];
  items: ItemDef[];
  entries: JournalEntry[];
  sources: Record<string, SourceRef>;
  unlockedScans: number;
  totalScans: number;
}

/** Root of all DOM UI: HUD plus modal screens. Exactly one modal screen is shown at a time. */
export class UI {
  readonly root: HTMLElement;
  readonly hud: HUD;
  private modal = h('div.modal-layer');
  private dialogueLayer = h('div.dialogue-layer');
  private cinematicLayer = h('div.cinematic-layer');
  private loadingLayer = h('div.loading-layer');
  private fade = h('div.fade');
  modalOpen = false;
  onModalClosed: (() => void) | null = null;

  constructor(
    container: HTMLElement,
    private readonly settings: Settings,
  ) {
    this.root = container;
    this.hud = new HUD(settings);
    container.append(this.hud.el, this.dialogueLayer, this.cinematicLayer, this.modal, this.loadingLayer, this.fade);
    this.applyAccessibility();
  }

  applyAccessibility(): void {
    const a = this.settings.accessibility;
    document.documentElement.style.setProperty('--ui-scale', String(a.textScale));
    document.documentElement.style.setProperty('--sub-bg', String(a.subtitleBackground));
  }

  showHUD(v: boolean): void {
    this.hud.el.classList.toggle('hidden', !v);
  }

  setFade(v: number, ms = 500): void {
    this.fade.style.transition = `opacity ${ms}ms`;
    this.fade.style.opacity = String(v);
  }

  // ------------------------------------------------------------- modal plumbing
  private open(el: HTMLElement, opaque = false): void {
    clear(this.modal);
    const ov = h('div.overlay', null, el);
    if (opaque) ov.classList.add('opaque');
    this.modal.append(ov);
    this.modalOpen = true;
    const first = el.querySelector('button.primary, button') as HTMLButtonElement | null;
    first?.focus({ preventScroll: true });
  }

  closeModal(): void {
    clear(this.modal);
    const was = this.modalOpen;
    this.modalOpen = false;
    if (was) this.onModalClosed?.();
  }

  // ------------------------------------------------------------- screens
  mainMenu(o: { canContinue: boolean; continueLabel: string; onContinue: () => void; onHQ: () => void; onSettings: () => void; onCredits: () => void; onBenchmark: () => void; onReset: () => void; storageNote: string | null }): void {
    const p = h(
      'div.panel',
      { style: { minWidth: 'min(90vw, 460px)', background: 'rgba(10,11,12,.72)' } },
      h('h1.title-logo', null, 'CHRONO WITNESS'),
      h('div.title-sub', null, 'What might it have felt like to stand here?'),
      h(
        'div.menu',
        null,
        o.canContinue ? h('button.primary', { onclick: o.onContinue }, o.continueLabel) : null,
        h('button', { class: o.canContinue ? '' : 'primary', onclick: o.onHQ }, 'Enter Headquarters'),
        h('button', { onclick: o.onSettings }, 'Settings'),
        h('button', { onclick: o.onBenchmark }, 'Performance Benchmark'),
        h('button', { onclick: o.onCredits }, 'Credits, Sources & Historical Notes'),
        h('button.small', { onclick: o.onReset, style: { marginTop: '14px', opacity: 0.7 } }, 'Reset all progress…'),
      ),
      h('p.note', { style: { marginTop: '22px' } }, 'Mouse to look · WASD to move · E interact · Q scanner · F observe · J journal · Esc pause'),
      o.storageNote ? h('p.note', { style: { color: '#e8b36a' } }, o.storageNote) : null,
    );
    this.open(p);
  }

  pauseMenu(o: { title: string; onResume: () => void; onJournal: () => void; onInventory: () => void; onSettings: () => void; onRestart: (() => void) | null; onHQ: (() => void) | null; onMain: () => void; onSkip: (() => void) | null }): void {
    const p = h(
      'div.panel',
      { style: { minWidth: '360px' } },
      h('h2', null, 'Paused'),
      h('p', null, o.title),
      h(
        'div.menu',
        null,
        h('button.primary', { onclick: o.onResume }, 'Resume'),
        h('button', { onclick: o.onJournal }, 'Journal'),
        h('button', { onclick: o.onInventory }, 'Inventory'),
        h('button', { onclick: o.onSettings }, 'Settings'),
        o.onSkip ? h('button', { onclick: o.onSkip }, 'Skip current intense sequence (keeps progress)') : null,
        o.onRestart ? h('button', { onclick: o.onRestart }, 'Restart from last checkpoint') : null,
        o.onHQ ? h('button', { onclick: o.onHQ }, 'Return to Headquarters (progress saved)') : null,
        h('button', { onclick: o.onMain }, 'Main menu'),
      ),
    );
    this.open(p);
  }

  settingsScreen(onChange: (graphics: boolean) => void, onClose: () => void): void {
    this.open(
      buildSettingsPanel(
        this.settings,
        (g) => {
          this.applyAccessibility();
          onChange(g);
        },
        onClose,
      ),
    );
  }

  confirm(title: string, text: string, options: { label: string; primary?: boolean; action: () => void }[]): void {
    const p = h('div.panel', { style: { maxWidth: '560px' } }, h('h2', null, title), ...text.split('\n\n').map((t) => h('p', null, t)), h('div.row', { style: { marginTop: '18px', justifyContent: 'flex-end' } }, ...options.map((o) => h(o.primary ? 'button.primary' : 'button', { onclick: o.action }, o.label))));
    this.open(p);
  }

  readDocument(title: string, text: string, onClose: () => void): void {
    this.open(h('div', { style: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' } }, h('div.read-doc', null, h('div', { style: { fontWeight: 'bold', marginBottom: '10px' } }, title), text), h('button.primary', { onclick: onClose }, 'Close')));
  }

  journal(d: JournalData, onClose: () => void, tab: 'objectives' | 'evidence' | 'history' = 'objectives'): void {
    const panel = h('div.panel', { style: { width: 'min(92vw, 900px)' } });
    const bar = h('div.tabs');
    const body = h('div');
    const render = (t: typeof tab): void => {
      clear(bar);
      for (const [k, l] of [['objectives', 'Missions'], ['evidence', 'Evidence & Items'], ['history', 'Historical Record']] as const) bar.append(h('button', { class: k === t ? 'active' : '', onclick: () => render(k) }, l));
      clear(body);
      if (t === 'objectives') {
        if (!d.missions.length) body.append(h('p', null, 'No missions at this location.'));
        for (const m of d.missions) {
          if (m.state.state === 'unavailable') continue;
          const stateLabel = { active: 'Active', completed: 'Completed', failed: 'Failed', unavailable: 'Unavailable' }[m.state.state];
          const sec = h('div.journal-entry', null, h('div.t', null, `${m.def.kind === 'main' ? 'Main mission' : 'Optional'} — ${m.def.title}`, ' ', h('span.tag', { class: `tag ${m.state.state === 'completed' ? 'status-ok' : 'status-dev'}` }, stateLabel)), h('p', null, m.def.summary));
          if (m.state.failReason) sec.append(h('p', { style: { color: 'var(--danger)' } }, `Failed: ${m.state.failReason}. Restart from the last checkpoint to try again.`));
          for (const s of m.def.stages) {
            for (const o of s.objectives) {
              const st = m.state.objectives[o.id];
              if (!st || st === 'inactive') continue;
              sec.append(h(`div.objective-line${st === 'completed' ? '.done' : st === 'failed' ? '.failed' : ''}${o.optional ? '.optional' : ''}` as 'div', null, h('div.box'), h('div', null, h('div.t', null, o.text), o.detail && st === 'active' ? h('div.note', null, o.detail) : null)));
            }
          }
          body.append(sec);
        }
      } else if (t === 'evidence') {
        if (!d.items.length) body.append(h('p', null, 'You are not carrying anything yet.'));
        for (const it of d.items) body.append(h('div.journal-entry', null, h('div.t', null, it.name, ' ', h('span.tag.status-dev', null, it.kind)), h('p', null, it.description), it.readable ? h('p.note', { style: { whiteSpace: 'pre-wrap' } }, it.readable) : null));
      } else {
        body.append(
          h('p.note', null, `Scanner records: ${d.unlockedScans} / ${d.totalScans}. Entries are tagged `, h('span.tag.documented', null, 'documented'), ' (supported by cited sources), ', h('span.tag.reconstruction', null, 'reconstruction'), ' (plausible, not a specific recorded fact) or ', h('span.tag.fiction', null, 'fiction'), ' (invented for the game).'),
        );
        for (const e of d.entries) {
          body.append(
            h(
              'div.journal-entry',
              null,
              h('div.t', null, h(`span.tag.${e.status}` as 'span', null, e.status), e.title),
              h('p', null, e.text),
              e.sources?.length ? h('div.sources', null, 'Sources: ', e.sources.map((s) => d.sources[s]).filter(Boolean).map((s) => `${s!.title} (${s!.publisher})`).join('; ')) : null,
            ),
          );
        }
      }
    };
    render(tab);
    panel.append(h('h2', null, d.chapter ? `Journal — ${d.chapter.destination}, ${d.chapter.dateLabel}` : 'Journal'), bar, body, h('div.row', { style: { marginTop: '16px', justifyContent: 'flex-end' } }, h('button.primary', { onclick: onClose }, 'Close')));
    this.open(panel);
  }

  inventory(items: ItemDef[], onRead: (it: ItemDef) => void, onClose: () => void): void {
    const p = h('div.panel', { style: { width: 'min(92vw, 640px)' } }, h('h2', null, 'Inventory'));
    if (!items.length) p.append(h('p', null, 'Empty.'));
    for (const it of items) p.append(h('div.journal-entry', null, h('div.row', { style: { justifyContent: 'space-between' } }, h('div.t', null, it.name), it.readable ? h('button.small', { onclick: () => onRead(it) }, 'Read') : null), h('p', null, it.description)));
    p.append(h('div.row', { style: { marginTop: '16px', justifyContent: 'flex-end' } }, h('button.primary', { onclick: onClose }, 'Close')));
    this.open(p);
  }

  selector(chapters: ChapterConfig[], save: SaveData, o: { onTravel: (id: string, resume: boolean) => void; onClose: () => void }): void {
    const p = h('div.panel', { style: { width: 'min(94vw, 1080px)' } }, h('h2', null, 'Temporal Destination Selector'), h('p.note', null, 'Missions are fictional personal stories. The documented outcome of major historical events is never changed.'));
    const grid = h('div.chapters');
    const detail = h('div');
    let selected = chapters.find((c) => c.status === 'playable')?.id ?? chapters[0].id;
    const render = (): void => {
      clear(grid);
      for (const c of [...chapters].sort((a, b) => a.year - b.year)) {
        const prog = save.chapters[c.id];
        const status = c.status !== 'playable' ? 'In development' : prog?.status === 'completed' ? `Completed${prog.timesCompleted > 1 ? ` ×${prog.timesCompleted}` : ''}` : prog?.checkpoint ? 'In progress' : 'Available';
        grid.append(
          h(
            'button.chapter-card',
            { class: `chapter-card${c.id === selected ? ' selected' : ''}`, onclick: () => ((selected = c.id), render()) },
            h('div.year', null, c.year < 0 ? `AD ${-c.year}` : c.year < 1000 ? `AD ${c.year}` : String(c.year)),
            h('div.name', null, c.destination),
            h('div.place', null, c.dateLabel),
            h('div', { style: { marginTop: '8px' } }, h('span.tag', { class: `tag ${c.status === 'playable' ? 'status-ok' : 'status-dev'}` }, status)),
          ),
        );
      }
      const c = chapters.find((x) => x.id === selected)!;
      const prog = save.chapters[c.id];
      clear(detail);
      const left = h('div', null, h('h3', null, `${c.destination} · ${c.dateLabel}`), h('div', { style: { fontFamily: 'var(--serif)', fontSize: '1.3em' } }, c.title), h('p', null, c.overview), c.contentNotes ? h('p.note', null, h('strong', null, 'Content note: '), c.contentNotes) : null);
      const right = h('div');
      if (c.status === 'playable') {
        right.append(h('h3', null, 'Missions'));
        for (const m of c.missions) right.append(h('div.objective-line', null, h('div.box'), h('div', null, `${m.title}${m.kind === 'optional' ? ' (optional)' : ''}`)));
        const btns = h('div.menu', { style: { marginTop: '16px' } });
        if (prog?.checkpoint) btns.append(h('button.primary', { onclick: () => o.onTravel(c.id, true) }, `Continue — ${c.checkpoints[prog.checkpoint.id]?.label ?? 'last checkpoint'}`));
        btns.append(h(prog?.checkpoint ? 'button' : 'button.primary', { onclick: () => o.onTravel(c.id, false) }, prog?.status === 'completed' ? 'Replay chapter' : prog?.checkpoint ? 'Restart chapter' : 'Travel'));
        right.append(btns);
        if (prog?.bestTimeSec) right.append(h('p.note', null, `Best completion time: ${Math.round(prog.bestTimeSec / 60)} min`));
      } else {
        right.append(h('h3', null, 'Status'), h('p', null, 'This destination is not playable yet. Research notes and the planned mission outline are below; it uses the same chapter system as the playable chapters.'));
        if (c.plannedMissions?.length) {
          right.append(h('h3', null, 'Planned missions'));
          for (const m of c.plannedMissions) right.append(h('div.objective-line', null, h('div.box'), h('div', null, m)));
        }
      }
      detail.append(h('div.detail-grid', null, left, right));
    };
    render();
    p.append(grid, detail, h('div.row', { style: { marginTop: '18px', justifyContent: 'flex-end' } }, h('button', { onclick: o.onClose }, 'Close')));
    this.open(p);
  }

  artifacts(all: (ArtifactDef & { chapter: string })[], owned: string[], onClose: () => void): void {
    const p = h('div.panel', { style: { width: 'min(92vw, 820px)' } }, h('h2', null, 'Recovered Artifacts'), h('p.note', null, 'Artifacts are replicas or records the agency catalogues after each assignment. Tags show whether each describes documented history or the game’s fiction.'));
    for (const a of all) {
      const have = owned.includes(a.id);
      p.append(h('div.journal-entry', { style: { opacity: have ? 1 : 0.45 } }, h('div.t', null, h(`span.tag.${a.status}` as 'span', null, a.status), have ? a.name : 'Unrecovered artifact', h('span.note', null, ` — ${a.chapter}`)), h('p', null, have ? a.description : 'Complete the related assignment to catalogue this artifact.')));
    }
    p.append(h('div.row', { style: { marginTop: '16px', justifyContent: 'flex-end' } }, h('button.primary', { onclick: onClose }, 'Close')));
    this.open(p);
  }

  records(chapters: ChapterConfig[], unlocked: string[], onClose: () => void): void {
    const p = h('div.panel', { style: { width: 'min(92vw, 900px)' } }, h('h2', null, 'Historical Records'), h('p.note', null, 'Records unlock as you scan objects and complete assignments. Each records whether it is documented, a reconstruction or game fiction, with sources.'));
    for (const c of chapters) {
      const entries = [...c.journal, ...c.scans].filter((e) => e.initiallyKnown || unlocked.includes(e.id));
      if (!entries.length) continue;
      p.append(h('h3', null, `${c.destination} — ${c.dateLabel}`));
      for (const e of entries) p.append(h('div.journal-entry', null, h('div.t', null, h(`span.tag.${e.status}` as 'span', null, e.status), e.title), h('p', null, e.text), e.sources?.length ? h('div.sources', null, 'Sources: ', e.sources.map((s) => c.sources[s]).filter(Boolean).map((s) => `${s!.title} (${s!.publisher})${s!.url ? ` ${s!.url}` : ''}`).join('; ')) : null));
    }
    p.append(h('div.row', { style: { marginTop: '16px', justifyContent: 'flex-end' } }, h('button.primary', { onclick: onClose }, 'Close')));
    this.open(p);
  }

  credits(html: string, onClose: () => void): void {
    const p = h('div.panel', { style: { width: 'min(92vw, 900px)' } }, h('h2', null, 'Credits, Sources & Historical Notes'), h('div', { html }), h('div.row', { style: { marginTop: '16px', justifyContent: 'flex-end' } }, h('button.primary', { onclick: onClose }, 'Close')));
    this.open(p);
  }

  summary(title: string, lines: string[], onContinue: () => void): void {
    const p = h('div.panel', { style: { maxWidth: '640px' } }, h('h2', null, title), ...lines.map((l) => h('p', null, l)), h('div.row', { style: { marginTop: '18px', justifyContent: 'flex-end' } }, h('button.primary', { onclick: onContinue }, 'Return to Headquarters')));
    this.open(p, true);
  }

  benchmarkMenu(routes: { id: string; label: string }[], onRun: (id: string) => void, onClose: () => void, note: string): void {
    const p = h('div.panel', { style: { maxWidth: '640px' } }, h('h2', null, 'Performance Benchmark'), h('p', null, note), h('div.menu', null, ...routes.map((r) => h('button', { onclick: () => onRun(r.id) }, r.label))), h('div.row', { style: { marginTop: '16px', justifyContent: 'flex-end' } }, h('button', { onclick: onClose }, 'Close')));
    this.open(p);
  }

  benchmarkResult(rows: [string, string][], json: string, onClose: () => void): void {
    const table = h('table.stat-table', null, ...rows.map(([k, v]) => h('tr', null, h('th', null, k), h('td', null, v))));
    const dl = h('button', {
      onclick: () => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
        a.download = `chrono-witness-benchmark-${Date.now()}.json`;
        a.click();
      },
    }, 'Download JSON');
    this.open(h('div.panel', { style: { maxWidth: '720px' } }, h('h2', null, 'Benchmark result'), table, h('p.note', null, 'Measured on this machine only. Results depend on browser, GPU driver, resolution and preset.'), h('div.row', { style: { marginTop: '16px', justifyContent: 'flex-end' } }, dl, h('button.primary', { onclick: onClose }, 'Close'))));
  }

  // ------------------------------------------------------------- dialogue
  dialogue(speaker: string, text: string, choices: { text: string; onPick: () => void }[] | null, onContinue: () => void): void {
    clear(this.dialogueLayer);
    const box = h('div.dialogue.interactive', null, this.settings.accessibility.speakerLabels ? h('div.speaker', null, speaker) : null, h('div.line', null, text));
    if (choices && choices.length) {
      const list = h('div.choices');
      choices.forEach((c, i) => list.append(h('button', { onclick: c.onPick }, `${i + 1}. ${c.text}`)));
      box.append(list);
      this.dialogueKeys = (n: number) => choices[n]?.onPick();
    } else {
      box.append(h('div.continue', null, 'Press E, Space or click to continue'));
      box.addEventListener('click', onContinue);
      this.dialogueKeys = null;
      this.dialogueContinue = onContinue;
    }
    this.dialogueLayer.append(box);
  }

  dialogueKeys: ((n: number) => void) | null = null;
  dialogueContinue: (() => void) | null = null;

  closeDialogue(): void {
    clear(this.dialogueLayer);
    this.dialogueKeys = null;
    this.dialogueContinue = null;
  }

  get dialogueOpen(): boolean {
    return this.dialogueLayer.childElementCount > 0;
  }

  // ------------------------------------------------------------- loading
  private loadBar: HTMLElement | null = null;
  private loadStage: HTMLElement | null = null;
  private loadWarn: HTMLElement | null = null;

  loading(c: { destination: string; title: string; date: string; fact?: string }): void {
    clear(this.loadingLayer);
    this.loadBar = h('div');
    this.loadStage = h('div.stage', null, 'Preparing…');
    this.loadWarn = h('div.warn');
    this.loadingLayer.append(h('div.loading', null, h('div.dest', null, c.destination), h('div.title', null, c.title), h('div.date', null, c.date), h('div.bar', null, this.loadBar), this.loadStage, this.loadWarn, c.fact ? h('div.fact', null, c.fact) : null));
  }

  loadingProgress(f: number, label: string): void {
    if (this.loadBar) this.loadBar.style.width = `${Math.round(f * 100)}%`;
    if (this.loadStage) this.loadStage.textContent = `${label} — ${Math.round(f * 100)}%`;
  }

  loadingWarning(text: string): void {
    if (this.loadWarn) this.loadWarn.textContent = text;
  }

  loadingError(message: string, onRetry: () => void, onBack: () => void): void {
    if (!this.loadStage) return;
    this.loadStage.textContent = `Loading failed: ${message}`;
    this.loadStage.style.color = 'var(--danger)';
    this.loadStage.parentElement!.append(h('div.row.interactive', { style: { marginTop: '14px' } }, h('button.primary', { onclick: onRetry }, 'Retry'), h('button', { onclick: onBack }, 'Back to Headquarters')));
  }

  hideLoading(): void {
    clear(this.loadingLayer);
    this.loadBar = this.loadStage = this.loadWarn = null;
  }

  // ------------------------------------------------------------- cinematic
  private capEl: HTMLElement | null = null;
  cinematic(show: boolean): void {
    clear(this.cinematicLayer);
    this.capEl = null;
    if (!show) return;
    this.capEl = h('div.caption');
    this.cinematicLayer.append(h('div.cinematic', null, h('div.bar-top'), h('div.bar-bottom'), this.capEl, h('div.skip', null, h('span.key', null, 'Enter'), ' hold to skip')));
  }

  caption(kicker: string | undefined, text: string, visible: boolean): void {
    if (!this.capEl) return;
    clear(this.capEl);
    if (kicker) this.capEl.append(h('small', null, kicker));
    this.capEl.append(text);
    this.capEl.style.opacity = visible ? '1' : '0';
  }
}
