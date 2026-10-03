import type { Condition } from './types';

/** Flags and inventory for the active chapter; the single source of truth missions evaluate against. */
export class FactStore {
  readonly flags = new Map<string, boolean>();
  readonly inventory: string[] = [];
  onChange: (() => void) | null = null;

  set(flag: string, value = true): void {
    if ((this.flags.get(flag) ?? false) === value) return;
    this.flags.set(flag, value);
    this.onChange?.();
  }

  get(flag: string): boolean {
    return this.flags.get(flag) ?? false;
  }

  hasItem(id: string): boolean {
    return this.inventory.includes(id);
  }

  addItem(id: string): boolean {
    if (this.inventory.includes(id)) return false;
    this.inventory.push(id);
    this.flags.set(`item.${id}`, true);
    this.onChange?.();
    return true;
  }

  removeItem(id: string): boolean {
    const i = this.inventory.indexOf(id);
    if (i < 0) return false;
    this.inventory.splice(i, 1);
    this.onChange?.();
    return true;
  }

  test(c: Condition | undefined): boolean {
    if (!c) return true;
    if ('flag' in c) return this.get(c.flag);
    if ('notFlag' in c) return !this.get(c.notFlag);
    if ('item' in c) return this.hasItem(c.item);
    if ('count' in c) {
      let n = 0;
      for (const f of c.count.flags) if (this.get(f)) n++;
      return n >= c.count.atLeast;
    }
    if ('all' in c) return c.all.every((x) => this.test(x));
    if ('any' in c) return c.any.some((x) => this.test(x));
    return false;
  }

  countFlags(flags: string[]): number {
    let n = 0;
    for (const f of flags) if (this.get(f)) n++;
    return n;
  }

  snapshot(): { flags: Record<string, boolean>; inventory: string[] } {
    return { flags: Object.fromEntries(this.flags), inventory: [...this.inventory] };
  }

  restore(s: { flags: Record<string, boolean>; inventory: string[] }): void {
    this.flags.clear();
    for (const [k, v] of Object.entries(s.flags)) this.flags.set(k, v);
    this.inventory.length = 0;
    this.inventory.push(...s.inventory);
    this.onChange?.();
  }
}
