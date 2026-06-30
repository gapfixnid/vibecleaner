import { useState, useEffect, useCallback } from "react";
import { THEMES, DEFAULT_THEME, isValidTheme, type ThemeMeta } from "../themes";

const STORAGE_KEY = "vibecleaner.theme";

function readStoredTheme(): string | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return isValidTheme(saved) ? saved : null;
  } catch {
    return null;
  }
}

function applyTheme(id: string) {
  document.documentElement.setAttribute("data-theme", id);
}

/**
 * App theme state. Defaults to Light on first run (no system following),
 * persists the user's choice, and applies it via `data-theme` on <html>.
 * The theme list comes from the registry so the picker stays in sync.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<string>(() => readStoredTheme() ?? DEFAULT_THEME);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((id: string) => {
    if (!isValidTheme(id)) return;
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore persistence failures */
    }
    setThemeState(id);
  }, []);

  return { theme, setTheme, themes: THEMES as ThemeMeta[] };
}
