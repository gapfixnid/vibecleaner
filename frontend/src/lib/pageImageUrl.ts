import type { PageInfo } from "../types";

interface BuildPageImageUrlOptions {
  page: Pick<PageInfo, "page_id" | "index" | "has_inpaint">;
  pageVersion?: number;
  preview?: boolean;
  thumbnail?: boolean;
  imageType?: "auto" | "original" | "inpainted";
}

export function buildPageImageUrl({
  page,
  pageVersion = 0,
  preview = true,
  thumbnail = false,
  imageType = "auto",
}: BuildPageImageUrlOptions): string {
  const pageId = encodeURIComponent(page.page_id || String(page.index));
  const params = new URLSearchParams({
    type: thumbnail || imageType === "original" || (imageType === "auto" && !page.has_inpaint)
      ? "original"
      : "inpainted",
    v: String(pageVersion),
  });

  if (thumbnail) {
    params.set("thumbnail", "true");
  } else {
    params.set("preview", preview ? "true" : "false");
  }

  const path = `/api/pages/${pageId}/image?${params.toString()}`;
  const internals = (window as Window & {
    __TAURI_INTERNALS__?: { convertFileSrc: (path: string, protocol: string) => string };
  }).__TAURI_INTERNALS__;
  return internals?.convertFileSrc(path, "vibecleaner-image") ?? path;
}
