// frontend/src/themes.ts
// Single source of truth for available themes. Adding a theme later = one entry
// here + a matching [data-theme="<id>"] block in styles/tokens.css.

export interface ThemeMeta {
  id: string;
  label: string;
  scheme: "light" | "dark";
  /** Colors used to render the preview swatch in the picker (mirror tokens.css). */
  preview: {
    bar: string;
    body: string;
    panel: string;
    accent: string;
  };
}

export const THEMES: ThemeMeta[] = [
  {
    id: "light",
    label: "Light",
    scheme: "light",
    preview: { bar: "#ffffff", body: "#f5f5f7", panel: "#ffffff", accent: "#007aff" },
  },
  {
    id: "dark",
    label: "Dark",
    scheme: "dark",
    preview: { bar: "#262628", body: "#0e0e0f", panel: "#2c2c2e", accent: "#0a84ff" },
  },
];

export const DEFAULT_THEME = "light";

const THEME_IDS = THEMES.map((t) => t.id);

export function isValidTheme(id: string | null | undefined): id is string {
  return !!id && THEME_IDS.includes(id);
}
