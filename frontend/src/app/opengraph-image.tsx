import { ImageResponse } from "next/og";

export const alt = "ClipFlow Media Downloader em uma janela de utilitário retrô";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        alignItems: "center",
        background: "linear-gradient(145deg, #087f8c, #064d68)",
        display: "flex",
        fontFamily: "Arial, sans-serif",
        height: "100%",
        justifyContent: "center",
        width: "100%",
      }}
    >
      <div style={{ background: "#ecebdc", border: "6px solid #f9f8ef", boxShadow: "12px 16px 0 #043d4c", display: "flex", flexDirection: "column", width: 920 }}>
        <div style={{ background: "linear-gradient(90deg, #083d9c, #2475d8, #4a96ed)", color: "white", display: "flex", fontSize: 32, fontWeight: 700, padding: "18px 24px" }}>
          ClipFlow Media Utility
        </div>
        <div style={{ color: "#17202a", display: "flex", flexDirection: "column", padding: "54px 58px 48px" }}>
          <div style={{ fontSize: 64, fontWeight: 800, letterSpacing: -2 }}>ClipFlow</div>
          <div style={{ color: "#0c3f91", fontSize: 32, marginTop: 12 }}>Media Downloader</div>
          <div style={{ color: "#53606a", fontSize: 24, marginTop: 28 }}>
            YouTube · TikTok · Instagram · X/Twitter
          </div>
        </div>
        <div style={{ borderTop: "3px solid #a7a69d", color: "#075f3b", display: "flex", fontSize: 22, padding: "12px 20px" }}>
          ● Ready — MP4 & MP3
        </div>
      </div>
    </div>,
    size,
  );
}
