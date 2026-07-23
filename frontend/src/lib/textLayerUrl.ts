export function buildTextLayerUrl(
  namespace: string,
  pageId: string,
  bubbleId: number,
  cacheKey: string,
): string {
  if (!/^[0-9a-f]{32}$/.test(namespace)) return "";
  if (!Number.isInteger(bubbleId) || bubbleId < 1 || bubbleId > 0x7fffffff) return "";
  if (!/^[0-9a-f]{24}$/.test(cacheKey)) return "";
  const path = `/api/text-layers/${namespace}/${encodeURIComponent(pageId)}/${bubbleId}/${cacheKey}.png`;
  const internals = (window as Window & {
    __TAURI_INTERNALS__?: { convertFileSrc: (path: string, protocol: string) => string };
  }).__TAURI_INTERNALS__;
  return internals?.convertFileSrc(path, "vibecleaner-image") ?? path;
}

