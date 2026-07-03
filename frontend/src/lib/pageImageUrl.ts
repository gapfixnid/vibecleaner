import type { PageInfo } from "../types";

interface BuildPageImageUrlOptions {
  backendUrl: string;
  page: Pick<PageInfo, "page_id" | "index" | "has_inpaint">;
  pageVersion?: number;
  preview?: boolean;
  thumbnail?: boolean;
}

export function buildPageImageUrl({
  backendUrl,
  page,
  pageVersion = 0,
  preview = true,
  thumbnail = false,
}: BuildPageImageUrlOptions): string {
  const pageId = encodeURIComponent(page.page_id || String(page.index));
  const params = new URLSearchParams({
    type: thumbnail || !page.has_inpaint ? "original" : "inpainted",
    v: String(pageVersion),
  });

  if (thumbnail) {
    params.set("thumbnail", "true");
  } else {
    params.set("preview", preview ? "true" : "false");
  }

  return `${backendUrl}/api/pages/${pageId}/image?${params.toString()}`;
}
