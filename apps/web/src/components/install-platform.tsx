"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export type InstallPlatform = "Linux" | "macOS" | "Windows";

const InstallPlatformContext = createContext<{
  activeOs: InstallPlatform;
  setActiveOs: (platform: InstallPlatform) => void;
} | null>(null);

export function InstallPlatformProvider({ children }: { children: ReactNode }) {
  const [activeOs, setActiveOs] = useState<InstallPlatform>("Linux");

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
