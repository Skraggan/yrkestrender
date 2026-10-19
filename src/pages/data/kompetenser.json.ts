// Quarterly national share for every skill; used by the compare page.
import type { APIRoute } from 'astro';
import { skill, skillIndex } from '../../lib/data';

export const GET: APIRoute = () => {
  const index = skillIndex();
  const quarters = Object.keys(skill(index[0].id).quarters);
  const skills: Record<string, { n: string; q: (number | null)[] }> = {};
  for (const s of index) {
    const q = skill(s.id).quarters;
    skills[s.id] = { n: s.name, q: quarters.map((x) => q[x] ?? null) };
  }
  return new Response(JSON.stringify({ quarters, skills }), { headers: { 'content-type': 'application/json' } });
};
