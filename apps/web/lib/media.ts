/** Mirrors the API's `is_vertical_9_16` tolerance (apps/api/app/providers/video.py):
 * anything else needs a centre-crop or blurred-pad choice before a render (FR-009). */
export function isVertical916(width: number | null, height: number | null): boolean {
  if (!width || !height) return false;
  return Math.abs(width / height - 9 / 16) <= 0.01;
}
