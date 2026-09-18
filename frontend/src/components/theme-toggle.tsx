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
      className="theme-toggle retro-button grid size-7 min-h-0 place-items-center p-0 text-muted"
      aria-label="Alternar entre tema claro e escuro"
      title="Alternar modo diurno/noturno"
    >
      <SunIcon className="theme-icon-sun size-4" />
      <MoonIcon className="theme-icon-moon size-4" />
    </button>
  );
}
