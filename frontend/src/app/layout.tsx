import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const themeInitializer = `
  try {
    const savedTheme = localStorage.getItem("clipflow-theme");
    if (savedTheme === "light" || savedTheme === "dark") {
      document.documentElement.classList.add(savedTheme);
    }
  } catch {}
`;

export const metadata: Metadata = {
  title: "ClipFlow — Baixe. Converta. Simples assim.",
  description:
    "Uma interface simples e moderna para preparar suas mídias no formato ideal.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitializer }} />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
