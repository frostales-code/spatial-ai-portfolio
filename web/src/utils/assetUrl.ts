/**
 * Normalize static asset paths so both root deploys (`/`) and subpath
 * hosts such as GitHub Pages (`/spatial-ai-portfolio/`) resolve reliably.
 */
export function resolvePublicUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim();
  if (!trimmed) return trimmed;
  if (/^(https?:|data:|blob:)/i.test(trimmed)) {
    return trimmed;
  }

  const rawBase = import.meta.env.BASE_URL || '/';
  const base = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;

  if (base !== '/' && trimmed.startsWith(base)) {
    return trimmed;
  }

  const cleanPath = trimmed.replace(/^\/+/, '');
  return `${base}${cleanPath}`;
}
