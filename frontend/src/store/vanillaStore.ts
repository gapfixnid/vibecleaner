import { useState, useEffect } from "react";

export class VanillaStore<T> {
  private state: T;
  private listeners: Set<() => void> = new Set();

  constructor(initialState: T) {
    this.state = initialState;
  }

  getState(): T {
    return this.state;
  }

  setState(partial: Partial<T> | ((prev: T) => T)): void {
    const nextState =
      typeof partial === "function"
        ? (partial as Function)(this.state)
        : { ...this.state, ...partial };
    
    // Simple shallow comparison for state updates
    let changed = false;
    if (typeof nextState === "object" && nextState !== null) {
      for (const key in nextState) {
        if ((nextState as any)[key] !== (this.state as any)[key]) {
          changed = true;
          break;
        }
      }
    } else {
      changed = nextState !== this.state;
    }

    if (changed) {
      this.state = nextState;
      this.listeners.forEach((listener) => listener());
    }
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}

export function useStore<T>(store: VanillaStore<T>): T {
  const [state, setState] = useState(store.getState());

  useEffect(() => {
    return store.subscribe(() => {
      setState(store.getState());
    });
  }, [store]);

  return state;
}
