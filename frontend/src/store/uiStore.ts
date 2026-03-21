/**
 * Zustand store for UI state (panels visibility, progressive disclosure).
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  // Progressive disclosure: which advanced panels are expanded
  expandedPanels: Set<string>;
  // Chart resolution
  chartResolution: string;
  // Whether to show Monte Carlo bands on chart
  showMonteCarloBands: boolean;
  // Whether to show LSTM overlay on chart
  showLSTMOverlay: boolean;
  // Whether to show geopolitical marks on chart
  showGeopoliticalMarks: boolean;
  // Sidebar open state
  sidebarOpen: boolean;

  // Actions
  togglePanel: (panelId: string) => void;
  setChartResolution: (resolution: string) => void;
  toggleMonteCarloBands: () => void;
  toggleLSTMOverlay: () => void;
  toggleGeopoliticalMarks: () => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      expandedPanels: new Set<string>(),
      chartResolution: 'D',
      showMonteCarloBands: true,
      showLSTMOverlay: true,
      showGeopoliticalMarks: true,
      sidebarOpen: true,

      togglePanel: (panelId) =>
        set((state) => {
          const next = new Set(state.expandedPanels);
          if (next.has(panelId)) {
            next.delete(panelId);
          } else {
            next.add(panelId);
          }
          return { expandedPanels: next };
        }),

      setChartResolution: (chartResolution) => set({ chartResolution }),
      toggleMonteCarloBands: () =>
        set((state) => ({ showMonteCarloBands: !state.showMonteCarloBands })),
      toggleLSTMOverlay: () =>
        set((state) => ({ showLSTMOverlay: !state.showLSTMOverlay })),
      toggleGeopoliticalMarks: () =>
        set((state) => ({ showGeopoliticalMarks: !state.showGeopoliticalMarks })),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    }),
    {
      name: 'financial-ui-state',
      // Only persist user preferences, not ephemeral state
      partialize: (state) => ({
        chartResolution: state.chartResolution,
        showMonteCarloBands: state.showMonteCarloBands,
        showLSTMOverlay: state.showLSTMOverlay,
        showGeopoliticalMarks: state.showGeopoliticalMarks,
      }),
    }
  )
);
