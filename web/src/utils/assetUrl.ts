/**
 * Normalize static asset paths so both root deploys (`/`) and subpath
 * hosts such as GitHub Pages (`/spatial-ai-portfolio`) resolve reliably
 * under Next.js static export (`NEXT_PUBLIC_BASE_PATH`).
 */
export function resolvePublicUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim();
  if (!trimmed) return trimmed;
  if (/^(https?:|data:|blob:)/i.test(trimmed)) {
    return trimmed;
  }

  const rawBase = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const cleanBase = rawBase.replace(/\/+$/, '');

  if (cleanBase && (trimmed === cleanBase || trimmed.startsWith(`${cleanBase}/`))) {
    return trimmed;
  }

  const cleanPath = trimmed.replace(/^\/+/, '');
  return cleanBase ? `${cleanBase}/${cleanPath}` : `/${cleanPath}`;
}
