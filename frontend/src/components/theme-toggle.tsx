"use client";

import { MoonIcon, SunIcon } from "@/components/icons";

export function ThemeToggle() {
  function toggleTheme() {
    const root = document.documentElement;
    const followsDarkSystemTheme = window.matchMedia(
      "(prefers-color-scheme: dark)",
    ).matches;
    const isDark =
      root.classList.contains("dark") ||
      (!root.classList.contains("light") && followsDarkSystemTheme);
    const nextTheme = isDark ? "light" : "dark";

    window.localStorage.setItem("clipflow-theme", nextTheme);
    root.classList.toggle("dark", nextTheme === "dark");
    root.classList.toggle("light", nextTheme === "light");
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="grid size-10 place-items-center rounded-full border border-line bg-surface text-muted shadow-xs transition hover:-translate-y-0.5 hover:border-accent/35 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      aria-label="Alternar entre tema claro e escuro"
      title="Alternar tema"
    >
      <SunIcon className="theme-icon-sun size-[18px]" />
      <MoonIcon className="theme-icon-moon size-[18px]" />
    </button>
  );
}
