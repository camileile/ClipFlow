import type { Metadata } from "next";
import "./globals.css";

const themeInitializer = `
  try {
    const savedTheme = localStorage.getItem("clipflow-theme");
    if (savedTheme === "light" || savedTheme === "dark") {
      document.documentElement.classList.add(savedTheme);
    }
  } catch {}
`;

export const metadata: Metadata = {
  title: "ClipFlow Media Utility",
  description:
    "Utilitário retrô para analisar e preparar mídias do YouTube em MP4 ou MP3.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className="h-full"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitializer }} />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
