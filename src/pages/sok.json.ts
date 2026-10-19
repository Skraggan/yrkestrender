// Search index loaded by the search box on first focus.
import type { APIRoute } from 'astro';
import { categoryName, occupationIndex, skill, skillIndex } from '../lib/data';

const KIND_LABEL: Record<string, string> = { kompetens: 'Kompetens', krav: 'Krav', egenskap: 'Egenskap', villkor: 'Villkor' };

export const GET: APIRoute = () => {
  const occ = occupationIndex().map((o) => ({ k: 'o', id: o.id, l: o.label, a: o.titles, c: '', n: o.L12 }));
  const skills = skillIndex().map((s) => ({
    k: 's',
    id: s.id,
    l: s.name,
    a: skill(s.id)
      .terms.map((t) => t.replace(/\*$/, ''))
      .filter((t) => t.length > 2 && t !== s.name.toLowerCase()),
    c: `${KIND_LABEL[s.kind] ?? 'Kompetens'}, ${categoryName(s.category).toLowerCase()}`,
    n: s.L12,
  }));
  return new Response(JSON.stringify([...occ, ...skills]), { headers: { 'content-type': 'application/json' } });
};
