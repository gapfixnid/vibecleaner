import { useCallback, useEffect } from "react";
import type { PageInfo } from "../types";
import { buildPageImageUrl as buildPageImageRequestUrl } from "../lib/pageImageUrl";

interface UsePageImageRequestsDeps {
  pages: PageInfo[];
  currentIndex: number;
  pageVersions: Record<number, number>;
}

export function usePageImageRequests({ pages, currentIndex, pageVersions }: UsePageImageRequestsDeps) {
  const buildPageImageUrl = useCallback(
    (page: PageInfo, preview = true, imageType: "auto" | "original" | "inpainted" = "auto") => {
      return buildPageImageRequestUrl({
        page,
        pageVersion: pageVersions[page.index] || 0,
        preview,
        imageType,
      });
    },
    [pageVersions]
  );

  useEffect(() => {
    if (currentIndex < 0 || pages.length === 0) return;
    const adjacentPages = [pages[currentIndex + 1], pages[currentIndex - 1]].filter(
      (page): page is PageInfo => Boolean(page)
    );
    const prefetchers = adjacentPages.map((page) => {
      const img = new Image();
      img.decoding = "async";
      img.src = buildPageImageUrl(page);
      return img;
    });
    return () => {
      prefetchers.forEach((img) => {
        img.src = "";
      });
    };
  }, [buildPageImageUrl, currentIndex, pages]);

  return {
    buildPageImageUrl,
  };
}
