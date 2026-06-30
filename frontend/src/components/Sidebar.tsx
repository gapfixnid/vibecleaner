// frontend/src/components/Sidebar.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { 
  Plus,
  Save,
  Pencil,
  Copy, 
  Trash2, 
  Layers,
  Languages,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Search,
  Download
} from "lucide-react";
import type { PageInfo } from "../types";
import { derivePageStatus, pageStatusLabel } from "../lib/pageStatus";

const PAGE_ROW_HEIGHT = 78;
const PAGE_OVERSCAN = 6;
const MAX_THUMBNAIL_REQUESTS = 4;

let activeThumbnailRequests = 0;
const thumbnailQueue: Array<() => void> = [];

const drainThumbnailQueue = () => {
  while (activeThumbnailRequests < MAX_THUMBNAIL_REQUESTS && thumbnailQueue.length > 0) {
    const next = thumbnailQueue.shift();
    if (next) next();
  }
};

const acquireThumbnailSlot = (start: () => void) => {
  let cancelled = false;
  const run = () => {
    if (cancelled) {
      drainThumbnailQueue();
      return;
    }
    activeThumbnailRequests += 1;
    start();
  };

  thumbnailQueue.push(run);
  drainThumbnailQueue();

  return () => {
    cancelled = true;
    const idx = thumbnailQueue.indexOf(run);
    if (idx >= 0) {
      thumbnailQueue.splice(idx, 1);
    }
  };
};

const releaseThumbnailSlot = () => {
  activeThumbnailRequests = Math.max(0, activeThumbnailRequests - 1);
  drainThumbnailQueue();
};

const QueuedThumbnail: React.FC<{ src: string; alt: string }> = ({ src, alt }) => {
  const [queuedSrc, setQueuedSrc] = useState<string | null>(null);
  const releasedRef = useRef(false);
  const acquiredRef = useRef(false);

  useEffect(() => {
    releasedRef.current = false;
    acquiredRef.current = false;
    setQueuedSrc(null);
    const cancel = acquireThumbnailSlot(() => {
      acquiredRef.current = true;
      setQueuedSrc(src);
    });
    return () => {
      cancel();
      if (acquiredRef.current && !releasedRef.current) {
        releasedRef.current = true;
        releaseThumbnailSlot();
      }
    };
  }, [src]);

  const handleDone = () => {
    if (!releasedRef.current) {
      releasedRef.current = true;
      releaseThumbnailSlot();
    }
  };

  if (!queuedSrc) {
    return <div className="page-thumbnail placeholder" aria-label={alt} />;
  }

  return (
    <img
      src={queuedSrc}
      alt={alt}
      className="page-thumbnail"
      loading="lazy"
      onLoad={handleDone}
      onError={handleDone}
    />
  );
};

interface SidebarProps {
  pages: PageInfo[];
  currentIndex: number;
  selectedPageIds: number[];
  onSelectPage: (idx: number) => void;
  onPageClick: (e: React.MouseEvent, idx: number) => void;
  onSelectAllPages: () => void;
  onDuplicatePage: (idx: number) => void;
  onDeletePage: (idx: number) => void;
  onReorderPages: (fromIdx: number, toIdx: number) => void;
  /** Import images into the current project (the "+" button). */
  onImportImages: () => void;
  /** Export the currently selected pages (diskette button). */
  onExportSelectedImages: () => void;
  /** Rename a page's display name (stem only; extension preserved). */
  onRenamePage: (idx: number, name: string) => void;
  /** Translate the right-clicked page (or the whole multi-selection). */
  onTranslatePages: (idx: number) => void;
  /** Save image(s) for the right-clicked page (or the whole multi-selection). */
  onSaveImages: (idx: number) => void;
  backendUrl: string;
  /** Pages currently being processed, keyed by page index. */
  processingPages: Record<number, "translate">;
  /** Image version per page — bumps when the underlying image changes. */
  pageVersions: Record<number, number>;
}

export const Sidebar: React.FC<SidebarProps> = ({
  pages,
  currentIndex: _currentIndex,
  selectedPageIds,
  onSelectPage,
  onPageClick,
  onSelectAllPages,
  onDuplicatePage,
  onDeletePage,
  onReorderPages,
  onImportImages,
  onExportSelectedImages,
  onRenamePage,
  onTranslatePages,
  onSaveImages,
  backendUrl,
  processingPages,
  pageVersions,
}) => {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const pagesListRef = useRef<HTMLDivElement>(null);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [scrollTop, setScrollTop] = useState(0);
  const [scrollHeight, setScrollHeight] = useState(0);
  const [isImagesExpanded, setIsImagesExpanded] = useState(true);
  // Inline rename state: which page index is being renamed + the draft stem.
  const [renamingIndex, setRenamingIndex] = useState<number | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);
  const [contextMenu, setContextMenu] = useState<{
    visible: boolean;
    x: number;
    y: number;
    pageIndex: number;
  } | null>(null);

  useEffect(() => {
    const closeMenu = () => setContextMenu(null);
    window.addEventListener("click", closeMenu);
    return () => window.removeEventListener("click", closeMenu);
  }, []);

  // Focus + select the rename input when entering rename mode.
  useEffect(() => {
    if (renamingIndex !== null) {
      renameInputRef.current?.focus();
      renameInputRef.current?.select();
    }
  }, [renamingIndex]);

  // Split a filename into editable stem + preserved extension.
  const splitName = (filename: string) => {
    const dot = filename.lastIndexOf(".");
    if (dot > 0) return { stem: filename.slice(0, dot), ext: filename.slice(dot) };
    return { stem: filename, ext: "" };
  };

  const startRename = (idx: number) => {
    const page = pages.find((p) => p.index === idx);
    if (!page) return;
    setRenameDraft(splitName(page.filename).stem);
    setRenamingIndex(idx);
  };

  const cancelRename = () => {
    setRenamingIndex(null);
    setRenameDraft("");
  };

  const commitRename = (idx: number) => {
    const trimmed = renameDraft.trim();
    const page = pages.find((p) => p.index === idx);
    if (page && trimmed && trimmed !== splitName(page.filename).stem) {
      onRenamePage(idx, trimmed);
    }
    setRenamingIndex(null);
    setRenameDraft("");
  };

  const handleContextMenu = (e: React.MouseEvent, index: number) => {
    e.preventDefault();
    const menuHeight = 210; // estimated height (5 items + separators)
    const menuWidth = 180; // estimated width
    let y = e.clientY;
    let x = e.clientX;
    
    if (y + menuHeight > window.innerHeight) {
      y = window.innerHeight - menuHeight - 10;
    }
    if (x + menuWidth > window.innerWidth) {
      x = window.innerWidth - menuWidth - 10;
    }

    setContextMenu({
      visible: true,
      x,
      y,
      pageIndex: index
    });
  };

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent, _index: number) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex !== null && draggedIndex !== index) {
      onReorderPages(draggedIndex, index);
    }
    setDraggedIndex(null);
  };

  const filteredPages = useMemo(
    () => pages.filter((page) => page.filename.toLowerCase().includes(searchQuery.toLowerCase())),
    [pages, searchQuery]
  );

  const updateScrollMetrics = useCallback(() => {
    const scrollArea = scrollAreaRef.current;
    if (!scrollArea) return;
    setScrollTop(scrollArea.scrollTop);
    setScrollHeight(scrollArea.clientHeight);
  }, []);

  useEffect(() => {
    updateScrollMetrics();
    window.addEventListener("resize", updateScrollMetrics);
    return () => window.removeEventListener("resize", updateScrollMetrics);
  }, [updateScrollMetrics, pages.length, isImagesExpanded, searchQuery]);

  const pagesListTop = pagesListRef.current?.offsetTop ?? 0;
  const visibleTop = Math.max(0, scrollTop - pagesListTop);
  const visibleBottom = visibleTop + scrollHeight;
  const startIndex = Math.max(0, Math.floor(visibleTop / PAGE_ROW_HEIGHT) - PAGE_OVERSCAN);
  const endIndex = Math.min(
    filteredPages.length,
    Math.ceil(visibleBottom / PAGE_ROW_HEIGHT) + PAGE_OVERSCAN
  );
  const visiblePages = filteredPages.slice(startIndex, endIndex);

  return (
    <aside className="sidebar-container">
      <div className="sidebar-header">
        <div className="sidebar-title">
          <Layers size={14} className="title-icon" />
          <div className="sidebar-title-copy">
            <span className="sidebar-title-main">Pages</span>
            <span className="sidebar-title-sub">{pages.length} imported</span>
          </div>
        </div>
      </div>

      <div className="sidebar-search-container">
        <div className="search-input-wrapper">
          <Search size={13} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Filter pages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="sidebar-scroll-area" ref={scrollAreaRef} onScroll={updateScrollMetrics}>
        {/* PAGES GROUP */}
        <div className="sidebar-group">
          <div className="sidebar-group-header pages-group-header">
            <div
              className="pages-group-toggle"
              role="button"
              tabIndex={0}
              aria-expanded={isImagesExpanded}
              onClick={() => setIsImagesExpanded(!isImagesExpanded)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setIsImagesExpanded(!isImagesExpanded);
                }
              }}
            >
              <span className="sidebar-group-chevron">
                {isImagesExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </span>
              <span className="sidebar-group-title">Pages ({pages.length})</span>
            </div>
            <div className="pages-header-actions">
              <button
                type="button"
                className="pages-add-btn"
                data-tooltip="Add Images"
                aria-label="Add Images"
                onClick={(e) => {
                  e.stopPropagation();
                  onImportImages();
                }}
              >
                <Plus size={14} />
              </button>

              <button
                type="button"
                className="pages-add-btn"
                data-tooltip="Save Selected Images"
                aria-label="Save Selected Images"
                disabled={selectedPageIds.length === 0}
                onClick={(e) => {
                  e.stopPropagation();
                  onExportSelectedImages();
                }}
              >
                <Save size={14} />
              </button>
            </div>
          </div>

          {isImagesExpanded && (
            <div className="pages-list" ref={pagesListRef}>
              {filteredPages.length === 0 ? (
                <div className="empty-pages" role="status">
                  <div className="empty-pages-icon" aria-hidden="true">
                    <Layers size={18} />
                  </div>
                  <p className="empty-pages-title">
                    {searchQuery ? "No matching pages" : "No images loaded"}
                  </p>
                  <p className="empty-pages-copy">
                    {searchQuery ? "Try a different filename filter." : "Import manga or comic pages to begin cleanup."}
                  </p>
                  {!searchQuery && (
                    <button type="button" className="empty-pages-action" onClick={onImportImages}>
                      <Plus size={13} />
                      <span>Add Images</span>
                    </button>
                  )}
                </div>
              ) : (
                <div className="pages-virtual-spacer" style={{ height: `${filteredPages.length * PAGE_ROW_HEIGHT}px` }}>
                {visiblePages.map((page, visibleIdx) => {
                  const itemIndex = startIndex + visibleIdx;
                  const pageIdx = page.index;
                  const isSelected = selectedPageIds.includes(pageIdx);
                  const thumbUrl = `${backendUrl}/api/pages/${pageIdx}/image?type=original&thumbnail=true`;
                  return (
                    <div
                      key={pageIdx}
                      className={`page-item ${isSelected ? "selected" : ""}`}
                      style={{ top: `${itemIndex * PAGE_ROW_HEIGHT}px` }}
                      role="button"
                      tabIndex={0}
                      aria-current={isSelected}
                      draggable={renamingIndex !== pageIdx}
                      onDragStart={(e) => handleDragStart(e, pageIdx)}
                      onDragOver={(e) => handleDragOver(e, pageIdx)}
                      onDrop={(e) => handleDrop(e, pageIdx)}
                      onClick={(e) => onPageClick(e, pageIdx)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelectPage(pageIdx);
                        }
                      }}
                      onContextMenu={(e) => handleContextMenu(e, pageIdx)}
                    >
                      <div className="page-thumbnail-wrapper">
                        <QueuedThumbnail
                          src={thumbUrl}
                          alt={`Page ${pageIdx + 1}`}
                        />
                        <span className="page-number-badge">{pageIdx + 1}</span>
                        {(() => {
                          const status = derivePageStatus(
                            page, pageVersions[pageIdx] ?? 0,
                            processingPages[pageIdx],
                          );
                          const label = pageStatusLabel(status.kind);
                          return label ? (
                            <span
                              className={`page-status-dot status-${status.kind}${status.blink ? " status-blink" : ""}`}
                              title={label}
                              aria-label={label}
                            />
                          ) : null;
                        })()}
                      </div>
                      <div className="page-meta-info">
                        {renamingIndex === pageIdx ? (
                          <div className="page-rename" onClick={(e) => e.stopPropagation()}>
                            <input
                              ref={renameInputRef}
                              className="page-rename-input"
                              value={renameDraft}
                              onChange={(e) => setRenameDraft(e.target.value)}
                              onKeyDown={(e) => {
                                e.stopPropagation();
                                if (e.key === "Enter") {
                                  e.preventDefault();
                                  commitRename(pageIdx);
                                } else if (e.key === "Escape") {
                                  e.preventDefault();
                                  cancelRename();
                                }
                              }}
                              onBlur={cancelRename}
                              spellCheck={false}
                            />
                            <span className="page-rename-ext">{splitName(page.filename).ext}</span>
                          </div>
                        ) : (
                          <div className="page-filename" title={page.filename}>{page.filename}</div>
                        )}
                        <div className="page-stats">
                          {page.width}x{page.height} • {page.bubble_count} bubbles
                        </div>
                      </div>
                    </div>
                  );
                })
                }
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {contextMenu && contextMenu.visible && createPortal(
        (() => {
          // When the right-clicked page is part of an active multi-selection,
          // actions apply to the whole selection (mirrors the delete behavior).
          const isMulti =
            selectedPageIds.length > 1 && selectedPageIds.includes(contextMenu.pageIndex);
          const pageIndex = contextMenu.pageIndex;
          return (
            <div
              className="sidebar-context-menu"
              style={{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }}
              onClick={(e) => e.stopPropagation()}
            >
              {!isMulti && (
                <button onClick={() => { startRename(pageIndex); setContextMenu(null); }}>
                  <Pencil size={12} />
                  <span>Rename</span>
                </button>
              )}
              <button onClick={() => { onDuplicatePage(pageIndex); setContextMenu(null); }}>
                <Copy size={12} />
                <span>Duplicate</span>
              </button>
              <button className="danger" onClick={() => { onDeletePage(pageIndex); setContextMenu(null); }}>
                <Trash2 size={12} />
                <span>Delete</span>
              </button>
              <div className="sidebar-context-menu-separator" />
              <button onClick={() => { onTranslatePages(pageIndex); setContextMenu(null); }}>
                <Languages size={12} />
                <span>{isMulti ? "Translate Pages" : "Translate Page"}</span>
              </button>
              <button onClick={() => { onSaveImages(pageIndex); setContextMenu(null); }}>
                <Download size={12} />
                <span>{isMulti ? "Save Images…" : "Save Image…"}</span>
              </button>
              <div className="sidebar-context-menu-separator" />
              <button onClick={() => { onSelectAllPages(); setContextMenu(null); }}>
                <CheckSquare size={12} />
                <span>Select All</span>
              </button>
            </div>
          );
        })(),
        document.body
      )}

      <style>{`
        .sidebar-container {
          width: var(--sidebar-width);
          border-right: 1px solid var(--border-color);
          background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0)),
            var(--bg-sidebar);
          backdrop-filter: var(--glass-blur);
          -webkit-backdrop-filter: var(--glass-blur);
          display: flex;
          flex-direction: column;
          height: 100%;
          user-select: none;
        }

        .sidebar-header {
          padding: 15px 14px 11px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .sidebar-title {
          display: flex;
          align-items: center;
          gap: 9px;
          min-width: 0;
        }

        .title-icon {
          width: 24px;
          height: 24px;
          padding: 5px;
          border-radius: 7px;
          color: var(--text-secondary);
          background: var(--fill-3);
          border: 1px solid var(--border-color);
          flex: 0 0 auto;
        }

        .sidebar-title-copy {
          display: flex;
          flex-direction: column;
          gap: 1px;
          min-width: 0;
        }

        .sidebar-title-main {
          font-size: 13px;
          font-weight: 650;
          line-height: 1.1;
          color: var(--text-primary);
          letter-spacing: 0;
        }

        .sidebar-title-sub {
          font-size: 10.5px;
          font-weight: 500;
          line-height: 1.1;
          color: var(--text-tertiary);
          white-space: nowrap;
        }

        .sidebar-search-container {
          padding: 0 12px 11px;
          border-bottom: 1px solid var(--border-color);
        }

        .search-input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
          width: 100%;
        }

        .search-icon {
          position: absolute;
          left: 8px;
          color: var(--text-tertiary);
          pointer-events: none;
        }

        .search-input {
          background-color: var(--field-bg);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md);
          color: var(--text-primary);
          padding: 6px 8px 6px 27px;
          font-size: 12px;
          font-family: var(--font-family);
          width: 100%;
          outline: none;
          transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
        }

        .search-input:focus {
          border-color: var(--border-focus);
          background-color: var(--bg-input-focus);
          box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.16);
        }

        .sidebar-scroll-area {
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
          padding-bottom: 20px;
        }

        .sidebar-group {
          margin-top: 14px;
        }

        .sidebar-group-header {
          display: flex;
          align-items: center;
          padding: 5px 12px;
          gap: 4px;
          cursor: pointer;
          user-select: none;
        }

        .sidebar-group-chevron {
          display: flex;
          align-items: center;
          color: var(--text-tertiary);
          width: 16px;
          justify-content: center;
        }

        .sidebar-group-title {
          font-size: 11px;
          font-weight: 650;
          color: var(--text-secondary);
          letter-spacing: 0;
        }

        .pages-group-header {
          justify-content: space-between;
          cursor: default;
          padding-right: 8px;
        }

        .pages-group-toggle {
          display: flex;
          align-items: center;
          gap: 4px;
          flex: 1;
          min-width: 0;
          cursor: pointer;
        }

        .pages-add-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 22px;
          height: 22px;
          background: var(--fill-3);
          border: 1px solid transparent;
          color: var(--text-secondary);
          cursor: pointer;
          padding: 0;
          border-radius: 6px;
          flex-shrink: 0;
          transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.12s ease;
        }

        .pages-add-btn:hover {
          background: var(--fill-hover);
          border-color: var(--border-color);
          color: var(--text-primary);
        }

        .pages-add-btn:active {
          transform: translateY(1px) scale(0.98);
        }

        .pages-add-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .pages-add-btn:disabled:hover {
          background: transparent;
          color: var(--text-secondary);
        }

        .pages-header-actions {
          display: flex;
          align-items: center;
          gap: 2px;
          flex-shrink: 0;
        }

        /* Header action tooltips sit at the top-right inside the scroll area, so
           anchor them to the button's right edge (open leftward) to avoid the
           overflow clip / horizontal scroll at the sidebar boundary. */
        .pages-header-actions [data-tooltip]::after {
          left: auto;
          right: 0;
          transform: translateX(0) translateY(-2px);
        }

        .pages-header-actions [data-tooltip]:hover::after {
          transform: translateX(0) translateY(0);
        }

        .page-rename {
          display: flex;
          align-items: center;
          gap: 1px;
        }

        .page-rename-input {
          flex: 1;
          min-width: 0;
          background: var(--bg-input);
          border: 1px solid var(--border-focus);
          border-radius: 4px;
          color: var(--text-primary);
          font-size: 12px;
          font-family: var(--font-family);
          font-weight: 500;
          padding: 1px 4px;
          outline: none;
        }

        .page-rename-ext {
          font-size: 12px;
          color: var(--text-tertiary);
          flex-shrink: 0;
        }

        .operations-list {
          display: flex;
          flex-direction: column;
          padding: 4px 8px;
          gap: 2px;
        }

        .sidebar-row-btn {
          background: transparent;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 10px;
          border-radius: 6px;
          width: 100%;
          text-align: left;
          color: var(--text-secondary);
          font-size: 12.5px;
          font-weight: 500;
          transition: all 0.15s;
        }

        .sidebar-row-btn:hover:not(:disabled) {
          background: var(--bg-input);
          color: var(--text-primary);
        }

        .sidebar-row-btn:disabled {
          opacity: 0.35;
          cursor: not-allowed;
        }

        .row-icon {
          color: var(--system-blue);
        }

        .pages-list {
          padding: 4px 0;
          position: relative;
        }

        .pages-virtual-spacer {
          position: relative;
        }

        .empty-pages {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 7px;
          padding: 28px 18px 26px;
          text-align: center;
          color: var(--text-tertiary);
        }

        .empty-pages-icon {
          width: 34px;
          height: 34px;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--fill-3);
          border: 1px solid var(--border-color);
          color: var(--text-secondary);
          box-shadow: var(--control-active-shadow);
        }

        .empty-pages-title {
          margin-top: 2px;
          font-size: 12.5px;
          font-weight: 650;
          color: var(--text-primary);
          line-height: 1.25;
        }

        .empty-pages-copy {
          max-width: 170px;
          font-size: 11.5px;
          line-height: 1.35;
          color: var(--text-tertiary);
        }

        .empty-pages-action {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          height: 28px;
          margin-top: 5px;
          padding: 0 10px;
          border: 1px solid var(--border-color);
          border-radius: 8px;
          background: var(--control-active-bg);
          color: var(--text-primary);
          box-shadow: var(--control-active-shadow);
          font-family: var(--font-family);
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.15s ease, color 0.15s ease, transform 0.12s ease;
        }

        .empty-pages-action:hover {
          background: var(--fill-hover);
        }

        .empty-pages-action:active {
          transform: translateY(1px) scale(0.98);
        }

        .page-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 6px 8px;
          margin: 1px 8px;
          height: 70px;
          left: 0;
          right: 0;
          border-radius: 6px;
          background: transparent;
          cursor: pointer;
          transition: all 0.15s cubic-bezier(0.25, 0.8, 0.25, 1);
          position: absolute;
        }

        .page-item:hover {
          background: var(--fill-3);
        }

        .page-item.selected {
          background: var(--system-blue);
          color: white;
        }

        .page-thumbnail-wrapper {
          position: relative;
          width: 44px;
          height: 52px;
          background: #000;
          border-radius: 4px;
          overflow: hidden;
          border: 1px solid var(--separator-strong);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .page-thumbnail {
          max-width: 100%;
          max-height: 100%;
          object-fit: cover;
        }

        .page-thumbnail.placeholder {
          width: 100%;
          height: 100%;
          background: linear-gradient(135deg, var(--fill-3), var(--fill-1));
        }

        .page-number-badge {
          position: absolute;
          bottom: 2px;
          left: 2px;
          background: rgba(0, 0, 0, 0.7);
          color: white;
          font-size: 8px;
          padding: 1px 3px;
          border-radius: 2px;
          font-weight: 600;
        }

        .page-status-dot {
          position: absolute;
          top: 3px;
          left: 3px;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          border: 1.5px solid rgba(0, 0, 0, 0.55);
          box-sizing: border-box;
        }

        .page-status-dot.status-orange { background: var(--system-orange); }
        .page-status-dot.status-green { background: var(--system-green); }
        .page-status-dot.status-orange-blink { background: var(--system-orange); }

        .page-status-dot.status-blink {
          animation: status-blink 0.8s ease-in-out infinite;
        }

        @keyframes status-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.25; }
        }

        .page-meta-info {
          flex: 1;
          min-width: 0;
        }

        .page-filename {
          font-size: 12px;
          font-weight: 500;
          color: var(--text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .page-item.selected .page-filename {
          color: white;
        }

        .page-stats {
          font-size: 10px;
          color: var(--text-secondary);
          margin-top: 1px;
        }

        .page-item.selected .page-stats {
          color: rgba(255, 255, 255, 0.7);
        }

        .sidebar-context-menu {
          position: fixed;
          background: var(--bg-panel);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25), var(--shadow-lg, none);
          padding: 4px;
          z-index: 1000;
          display: flex;
          flex-direction: column;
          min-width: 140px;
          backdrop-filter: var(--glass-blur);
        }

        .sidebar-context-menu button {
          background: transparent;
          border: none;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 10px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 5px;
          cursor: pointer;
          color: var(--text-primary);
          text-align: left;
          width: 100%;
          transition: background 0.12s, color 0.12s;
        }

        .sidebar-context-menu button:hover {
          background: var(--system-blue, #007aff);
          color: white;
        }

        .sidebar-context-menu button.danger {
          color: var(--system-red, #ff3b30);
        }

        .sidebar-context-menu button.danger:hover {
          background: var(--system-red, #ff3b30);
          color: white;
        }

        .sidebar-context-menu-separator {
          height: 1px;
          background: var(--border-color);
          margin: 4px 0;
        }
      `}</style>
    </aside>
  );
};
