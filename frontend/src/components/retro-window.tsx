import type { KeyboardEvent, ReactNode } from "react";

import { ClipFlowIcon } from "@/components/icons";
import { ThemeToggle } from "@/components/theme-toggle";

export type RetroTabId = "downloader" | "activity" | "about";

interface RetroWindowProps {
  activeTab: RetroTabId;
  children: ReactNode;
  onTabChange: (tab: RetroTabId) => void;
  statusText: string;
  statusTone?: "default" | "busy" | "success" | "warning" | "danger";
}

const tabs: Array<{ id: RetroTabId; label: string; shortcut: string }> = [
  { id: "downloader", label: "Downloader", shortcut: "D" },
  { id: "activity", label: "Atividade", shortcut: "A" },
  { id: "about", label: "Sobre", shortcut: "S" },
];

export function RetroWindow({
  activeTab,
  children,
  onTabChange,
  statusText,
  statusTone = "default",
}: RetroWindowProps) {
  function handleTabKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;

    event.preventDefault();
    onTabChange(tabs[nextIndex].id);
    event.currentTarget.parentElement
      ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
      [nextIndex]?.focus();
  }

  return (
    <section className="retro-window" aria-label="ClipFlow Media Utility">
      <div className="retro-titlebar">
        <div className="flex min-w-0 items-center gap-2">
          <span className="retro-app-icon" aria-hidden="true">
            <ClipFlowIcon className="size-4" />
          </span>
          <h1 className="truncate text-sm font-bold text-white [text-shadow:1px_1px_0_rgb(0_38_104/0.8)] sm:text-[15px]">
            <span>ClipFlow</span>
            <span className="titlebar-detail"> Media Utility</span>
          </h1>
        </div>
        <div className="retro-window-controls" aria-hidden="true">
          <span className="retro-window-control">_</span>
          <span className="retro-window-control">□</span>
          <span className="retro-window-control retro-window-control-close">×</span>
        </div>
      </div>

      <div className="retro-menubar" aria-label="Menu do aplicativo">
        <div className="flex min-w-0 items-center">
          <button type="button" onClick={() => onTabChange("downloader")}>
            <u>A</u>rquivo
          </button>
          <button type="button" onClick={() => onTabChange("activity")}>
            A<u>t</u>ividade
          </button>
          <button type="button" onClick={() => onTabChange("about")}>
            A<u>j</u>uda
          </button>
        </div>
        <ThemeToggle />
      </div>

      <div className="retro-tabs" role="tablist" aria-label="Seções do ClipFlow">
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            aria-controls={`panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => onTabChange(tab.id)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
            className="retro-tab"
          >
            <span aria-hidden="true" className="retro-tab-key">
              {tab.shortcut}
            </span>
            {tab.label}
          </button>
        ))}
      </div>

      <div
        id={`panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`tab-${activeTab}`}
        className="retro-workspace"
      >
        {children}
      </div>

      <div className="retro-statusbar" role="status">
        <span className="retro-status-cell min-w-0 flex-1">
          <span
            className={`status-led status-led-${statusTone}`}
            aria-hidden="true"
          />
          <span className="truncate">{statusText}</span>
        </span>
        <span className="retro-status-cell status-secondary">YouTube conectado</span>
        <span className="retro-status-cell status-version">
          <span className="status-version-full">ClipFlow v0.6</span>
          <span className="status-version-short">v0.6</span>
        </span>
        <span className="retro-resize-grip" aria-hidden="true" />
      </div>
    </section>
  );
}
