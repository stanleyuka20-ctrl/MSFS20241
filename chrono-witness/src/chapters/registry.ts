import type { ChapterConfig } from './types';
import { HQ_CONFIG } from './hq/config';
import { WW1_CONFIG } from './ww1/config';
import { LONDON_CONFIG } from './london/config';
import { BERLIN45_CONFIG } from './berlin45/config';
import { PLANNED_CHAPTERS } from './planned';

export const HQ_ID = 'hq';

/** Every destination registered with the shared chapter system. Adding a chapter = adding a config here. */
export const CHAPTERS: ChapterConfig[] = [HQ_CONFIG, WW1_CONFIG, LONDON_CONFIG, BERLIN45_CONFIG, ...PLANNED_CHAPTERS];

export function creditsHtml(): string {
  return `
  <h3>Project</h3>
  <p>CHRONO WITNESS: an original game. Code, procedural environments, procedural audio and generated textures are original work for this project.</p>
  <h3>Third-party assets</h3>
  <p>Human base meshes, skeleton and skin weights are derived from <strong>MakeHuman</strong> assets (CC0 1.0, © Data Collection AB, Joel Palmius, Jonas Hauquier). The complete list, with any motion-capture sources, is in <code>ASSETS.md</code>.</p>
  <p>Libraries: three.js (MIT), three-mesh-bvh (MIT).</p>
  <h3>History</h3>
  <p>Missions, characters, units, the Somme sector and farm names, and the London street, station and residents are <strong>fiction</strong>. The journal separates <span class="tag documented">documented</span> facts (with sources) from <span class="tag reconstruction">reconstruction</span> and <span class="tag fiction">fiction</span>. Research notes and sources are in <code>docs/history/</code>. The sandbox used for research could not open the cited pages directly; facts were checked against search summaries of those pages and still need a full source review.</p>
  <h3>Time-travel rule</h3>
  <p>The player can change fictional personal stories. The documented outcome of major historical events is always preserved.</p>`;
}
