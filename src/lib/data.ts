// Reads the JSON produced by pipeline/aggregate.py (data/site) at build time.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const SITE_DIR = join(process.cwd(), 'data', 'site');

export interface Meta {
  generated: string;
  firstMonth: string;
  lastMonth: string;
  windows: { L12: [string, string]; P12: [string, string]; B12: [string, string] };
  years: number[];
  partialLastYear: boolean;
  /** First year with occupation codes on (nearly) all ads. */
  occupationFirstYear: number;
  totalAds: number;
  dupesSkipped: number;
  noGroup: number;
  noRegion: number;
  nationalMonths: Record<string, number>;
  nationalYears: Record<string, number>;
  adsL12: number;
  adsB12: number;
  sources: string[];
  skillCount: number;
  occupationCount: number;
}

export type KindId = 'kompetens' | 'krav' | 'egenskap' | 'villkor';

export interface Kind {
  id: KindId;
  name: string;
}

export interface Category {
  id: string;
  name: string;
  kind: KindId;
}

export interface SkillIndexItem {
  id: string;
  name: string;
  category: string;
  kind: KindId;
  L12: number;
  B12: number;
  sh: number | null;
  sh3: number | null;
  spark: (number | null)[];
  top: string[];
}

export interface OccupationIndexItem {
  id: string;
  cid: string;
  label: string;
  ssyk: string | null;
  field: string | null;
  L12: number;
  P12: number;
  B12: number;
  years: Record<string, number>;
  titles: string[];
  top: string[];
}

export interface OccSkill {
  s: string;
  n: number;
  sh: number | null;
  sh3: number | null;
  y: Record<string, number>;
}

export interface Conditions {
  fulltime: number | null;
  permanent: number | null;
  experience: number | null;
  english: number | null;
}

export interface Occupation {
  id: string;
  cid: string;
  label: string;
  ssyk: string | null;
  field: string | null;
  months: Record<string, number>;
  ads: { L12: number; P12: number; B12: number };
  skills: OccSkill[];
  regions: { r: string; n: number; lq: number | null }[];
  conditions: Record<string, Conditions>;
  titles: { t: string; n: number }[];
  employers: { e: string; n: number }[];
  related: { id: string; sim: number }[];
}

export interface Skill {
  id: string;
  name: string;
  category: string;
  kind: KindId;
  terms: string[];
  ads: { L12: number; P12: number; B12: number };
  share: { L12: number | null; B12: number | null };
  years: Record<string, number>;
  quarters: Record<string, number>;
  occupations: { o: string; n: number; sh: number }[];
  occupationsByShare: { o: string; n: number; sh: number }[];
  regions: { r: string; n: number; sh: number }[];
  related: { s: string; n: number; lift: number; p: number }[];
}

export interface RegionIndexItem {
  id: string;
  code: string;
  label: string;
  L12: number;
  B12: number;
}

export interface Region {
  id: string;
  code: string;
  label: string;
  months: Record<string, number>;
  occupations: { o: string; n: number; lq: number | null; prev: number }[];
  skills: { s: string; n: number; sh: number; sh3: number }[];
}

export interface Field {
  id: string;
  cid: string;
  label: string;
  L12: number;
  B12: number;
  occupations: string[];
}

const cache = new Map<string, unknown>();
function load<T>(rel: string): T {
  if (!cache.has(rel)) cache.set(rel, JSON.parse(readFileSync(join(SITE_DIR, rel), 'utf-8')));
  return cache.get(rel) as T;
}
function list(dir: string): string[] {
  return readdirSync(join(SITE_DIR, dir))
    .filter((f) => f.endsWith('.json'))
    .map((f) => f.slice(0, -5));
}

export const meta = () => load<Meta>('meta.json');
export const categories = () => load<Category[]>('categories.json');
export const kinds = () => load<Kind[]>('kinds.json');
export const skillIndex = () => load<SkillIndexItem[]>('skills.json');
export const occupationIndex = () => load<OccupationIndexItem[]>('occupations.json');
export const regionIndex = () => load<RegionIndexItem[]>('regions.json');
export const fields = () => load<Field[]>('fields.json');
export const occupation = (id: string) => load<Occupation>(`occupations/${id}.json`);
export const skill = (id: string) => load<Skill>(`skills/${id}.json`);
export const region = (id: string) => load<Region>(`regions/${id}.json`);
export const occupationIds = () => list('occupations');
export const skillIds = () => list('skills');
export const regionIds = () => list('regions');

/** National ad count in one of the comparison windows (L12, P12, B12). */
export function nationalWindow(key: 'L12' | 'P12' | 'B12'): number {
  const m = meta();
  const [from, to] = m.windows[key];
  let n = 0;
  for (const [ym, c] of Object.entries(m.nationalMonths)) if (ym >= from && ym <= to) n += c;
  return n;
}

export function skillById(id: string): SkillIndexItem | undefined {
  return skillIndex().find((s) => s.id === id);
}
export function occById(id: string): OccupationIndexItem | undefined {
  return occupationIndex().find((o) => o.id === id);
}
export function regionByCode(code: string): RegionIndexItem | undefined {
  return regionIndex().find((r) => r.code === code);
}
export function fieldById(id: string | null): Field | undefined {
  return id ? fields().find((f) => f.id === id) : undefined;
}
export function categoryName(id: string): string {
  return categories().find((c) => c.id === id)?.name ?? id;
}

export function kindName(id: string): string {
  return kinds().find((k) => k.id === id)?.name ?? id;
}

/** Short lowercase noun used in sentences: "kompetenser", "krav", ... */
export const KIND_NOUN: Record<KindId, string> = {
  kompetens: 'kompetenser',
  krav: 'krav och behörigheter',
  egenskap: 'personliga egenskaper',
  villkor: 'villkor och förmåner',
};
