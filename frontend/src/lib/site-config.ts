const fallbackSiteUrl = "http://localhost:3000";
const fallbackContactUrl = "https://github.com/camileile/ClipFlow/issues";

function publicUrl(value: string | undefined, fallback: string): URL {
  const parsed = new URL(value?.trim() || fallback);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("Public ClipFlow URLs must use HTTP or HTTPS.");
  }
  return parsed;
}

export const siteConfig = {
  name: "ClipFlow",
  title: "ClipFlow — Media Downloader",
  description:
    "Analise e baixe mídias públicas de plataformas compatíveis em MP4 ou MP3.",
  siteUrl: publicUrl(process.env.NEXT_PUBLIC_SITE_URL, fallbackSiteUrl),
  contactUrl: publicUrl(
    process.env.NEXT_PUBLIC_CONTACT_URL,
    fallbackContactUrl,
  ).toString(),
  repositoryUrl: "https://github.com/camileile/ClipFlow",
} as const;
