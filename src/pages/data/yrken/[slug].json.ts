// Yearly skill shares within one occupation; used by the compare page.
import type { APIRoute } from 'astro';
import { meta, occupation, occupationIds } from '../../../lib/data';

export function getStaticPaths() {
  return occupationIds().map((slug) => ({ params: { slug } }));
}

export const GET: APIRoute = ({ params }) => {
  const o = occupation(params.slug!);
  const m = meta();
  const years = m.years.filter((y) => y >= m.occupationFirstYear).map(String);
  const skills: Record<string, (number | null)[]> = {};
  for (const s of o.skills) skills[s.s] = years.map((y) => s.y[y] ?? null);
  return new Response(JSON.stringify({ label: o.label, years, skills }), { headers: { 'content-type': 'application/json' } });
};
