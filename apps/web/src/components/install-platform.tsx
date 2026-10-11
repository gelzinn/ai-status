"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type InstallPlatform = "Linux" | "macOS" | "Windows";
const PLATFORM_STORAGE_KEY = "ai-status.install-platform";

const InstallPlatformContext = createContext<{
  activeOs: InstallPlatform;
  setActiveOs: (platform: InstallPlatform) => void;
} | null>(null);

export function InstallPlatformProvider({ children }: { children: ReactNode }) {
  const [activeOs, updateActiveOs] = useState<InstallPlatform>("Linux");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(PLATFORM_STORAGE_KEY);
      if (saved === "Linux" || saved === "macOS" || saved === "Windows") {
        updateActiveOs(saved);
        return;
      }
    } catch {
      // OS detection and manual selection also work when storage is blocked.
    }

    const platform = (navigator as Navigator & { userAgentData?: { platform: string } }).userAgentData?.platform;
    if (platform === "Windows" || /^Win/i.test(navigator.platform) || /Windows NT/i.test(navigator.userAgent)) {
      updateActiveOs("Windows");
    } else if (platform === "macOS" || /^Mac/i.test(navigator.platform) || /Macintosh/i.test(navigator.userAgent)) {
      updateActiveOs("macOS");
    }
  }, []);

  function setActiveOs(platform: InstallPlatform) {
    updateActiveOs(platform);
    try {
      localStorage.setItem(PLATFORM_STORAGE_KEY, platform);
    } catch {
      // Keep the current choice usable without browser storage.
    }
  }

  return (
    <InstallPlatformContext.Provider value={{ activeOs, setActiveOs }}>
      {children}
    </InstallPlatformContext.Provider>
  );
}

export function useInstallPlatform() {
  const context = useContext(InstallPlatformContext);
  if (!context) throw new Error("InstallPlatformProvider is required");
  return context;
}

/** Select server-rendered content without sending its rendering logic to the client. */
export function PlatformContent({ linux, mac, windows }: { linux: ReactNode; mac: ReactNode; windows: ReactNode }) {
  const { activeOs } = useInstallPlatform();
  if (activeOs === "macOS") return mac;
  return activeOs === "Windows" ? windows : linux;
}
