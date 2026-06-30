import { VanillaStore } from "./vanillaStore";

export interface SelectionState {
  selectedPageId: string | null;
  selectedBubbleId: string | null;
  selectedPageIds: string[];
}

export const selectionStore = new VanillaStore<SelectionState>({
  selectedPageId: null,
  selectedBubbleId: null,
  selectedPageIds: [],
});
