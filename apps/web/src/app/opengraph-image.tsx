
import { ImageResponse } from "next/og";
import { Logo } from "@/components/logo";
import { PROJECT_NAME, PROJECT_DESCRIPTION, REPO_API_URL } from "@/lib/env";
import { PROVIDERS } from "@/lib/providers";

export const runtime = "nodejs";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = `${PROJECT_NAME} - ${PROJECT_DESCRIPTION}`;

// Satori silently falls back to a serif face unless fonts are embedded explicitly.
// Fetch from Google Fonts at build time to avoid monorepo hoisting issues with node_modules paths.
const geistRegular = fetch(
  "https://cdn.jsdelivr.net/npm/geist@1.5.1/dist/fonts/geist-sans/Geist-Regular.ttf",
).then((res) => res.arrayBuffer());
const geistSemiBold = fetch(
  "https://cdn.jsdelivr.net/npm/geist@1.5.1/dist/fonts/geist-sans/Geist-SemiBold.ttf",
).then((res) => res.arrayBuffer());

const PAGE_BG = "#09090b";
const BORDER = "rgba(250, 250, 250, 0.10)";
const FG = "#fafafa";
const FG_MUTED = "#a1a1aa";

export default async function OgImage() {
  let version = "v0.1.0";
  try {
    const res = await fetch(REPO_API_URL, { next: { revalidate: 3600 } });
    if (res.ok) {
      const data = await res.json();
      if (data.tag_name) {
        version = data.tag_name;
      }
    }
  } catch (error) {
    console.error("Failed to fetch GitHub version for OG Image:", error);
  }

  return new ImageResponse(
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        display: "flex",
        background: PAGE_BG,
        color: FG,
        fontFamily: "Geist",
        overflow: "hidden",
      }}
    >
      {/* Core Glow matching Desktop Wallpaper */}
      <div
        style={{
          position: "absolute",
          top: "-20%",
          right: "-10%",
          width: "80%",
          height: "120%",
          background:
            "radial-gradient(ellipse at center, rgba(59,130,246,0.15) 0%, transparent 60%)",
        }}
      />

      {/* Waybar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 80,
          background: "rgba(0,0,0,0.8)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 32px",
          borderBottom: `1px solid ${BORDER}`,
          zIndex: 20,
        }}
      >
        <div style={{ display: "flex", gap: 16 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              style={{
                width: 16,
                height: 16,
                borderRadius: 16,
                background: i === 0 ? "#52525b" : "#3f3f46",
              }}
            />
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              background: "rgba(255,255,255,0.03)",
              padding: "8px 16px",
              borderRadius: 8,
              border: `1px solid ${BORDER}`,
            }}
          >
            <span
              style={{ color: "#d4d4d8", fontSize: 24, fontWeight: 500 }}
            >{`Gemini (${PROVIDERS.ANTIGRAVITY.name}) 27%`}</span>
          </div>
        </div>
      </div>

      {/* Left Side: Branding */}
      <div
        style={{
          position: "absolute",
          left: 80,
          top: 140,
          display: "flex",
          flexDirection: "column",
          gap: 24,
          zIndex: 10,
          maxWidth: 520,
        }}
      >
        <Logo style={{ width: 140, height: 140 }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              display: "flex",
              fontSize: 72,
              fontWeight: 600,
              letterSpacing: "-0.04em",
              color: FG,
            }}
          >
            {PROJECT_NAME}
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 28,
              color: FG_MUTED,
              lineHeight: 1.4,
            }}
          >
            {PROJECT_DESCRIPTION}
          </div>
        </div>
      </div>

      {/* Right Side: Tooltip Replica */}
      <div
        style={{
          position: "absolute",
          right: 48,
          top: 100,
          width: 500,
          display: "flex",
          flexDirection: "column",
          background: "rgba(0,0,0,0.95)",
          border: `1px solid ${BORDER}`,
          borderRadius: 24,
          padding: 32,
          gap: 32,
          boxShadow: "0 0 100px rgba(0,0,0,0.9)",
          zIndex: 10,
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: `1px solid #27272a`,
            paddingBottom: 24,
          }}
        >
          <div
            style={{
              display: "flex",
              fontSize: 28,
              fontWeight: 600,
              color: "#d4d4d8",
            }}
          >
            {PROJECT_NAME}
          </div>
          <div style={{ display: "flex", fontSize: 24, color: "#71717a" }}>
            {version}
          </div>
        </div>

        {/* Provider 1 (Active) */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              position: "relative",
              paddingLeft: 40,
            }}
          >
            <span
              style={{
                position: "absolute",
                left: 0,
                color: "#e4e4e7",
                fontSize: 28,
                fontWeight: 500,
              }}
            >
              →
            </span>
            <img
              src={PROVIDERS.ANTIGRAVITY.logo}
              style={{
                width: 28,
                height: 28,
                opacity: 0.8,
                filter: "brightness(1.1)",
              }}
            />
            <div
              style={{
                display: "flex",
                color: "#e4e4e7",
                fontSize: 28,
                fontWeight: 600,
              }}
            >{`Gemini (${PROVIDERS.ANTIGRAVITY.name})`}</div>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              paddingLeft: 40,
              gap: 16,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                position: "relative",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  left: -24,
                  top: 4,
                  color: "#e4e4e7",
                  fontSize: 20,
                }}
              >
                •
              </span>
              <span style={{ color: "#e4e4e7", fontSize: 24 }}>
                Rolling Usage:
              </span>
              <div
                style={{
                  display: "flex",
                  flex: 1,
                  height: 16,
                  background: "#3f3f46",
                  borderRadius: 2,
                  overflow: "hidden",
                  border: "1px solid rgba(255,255,255,0.1)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    width: "27%",
                    height: "100%",
                    background: "#e4e4e7",
                  }}
                />
              </div>
              <span style={{ color: "#e4e4e7", fontSize: 24 }}>27%</span>
            </div>
            <span style={{ color: "#a1a1aa", fontSize: 24 }}>
              Resets in 2h 54m
            </span>
          </div>
        </div>

        {/* Provider 2 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              paddingLeft: 40,
            }}
          >
            <img
              src={PROVIDERS.CLAUDE.logo}
              style={{
                width: 28,
                height: 28,
                opacity: 0.8,
                filter: "brightness(1.1)",
              }}
            />
            <div
              style={{
                display: "flex",
                color: "#a1a1aa",
                fontSize: 28,
                fontWeight: 600,
              }}
            >{`${PROVIDERS.CLAUDE.name} (Pro)`}</div>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              paddingLeft: 44,
              gap: 16,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                position: "relative",
              }}
            >
              <span style={{ color: "#a1a1aa", fontSize: 24 }}>
                Weekly Usage:
              </span>
              <div
                style={{
                  display: "flex",
                  flex: 1,
                  height: 16,
                  background: "#27272a",
                  borderRadius: 2,
                  overflow: "hidden",
                  border: "1px solid rgba(255,255,255,0.05)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    width: "64%",
                    height: "100%",
                    background: "#52525b",
                  }}
                />
              </div>
              <span style={{ color: "#a1a1aa", fontSize: 24 }}>64%</span>
            </div>
            <span style={{ color: "#71717a", fontSize: 24 }}>
              Resets in 3d 14h
            </span>
          </div>
        </div>
      </div>
    </div>,
    {
      ...size,
      fonts: [
        { name: "Geist", data: await geistRegular, weight: 400, style: "normal" },
        { name: "Geist", data: await geistSemiBold, weight: 600, style: "normal" },
      ],
    },
  );
}
