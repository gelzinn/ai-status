import { useId } from "react";
import { cn } from "@/lib/utils";

export function MacMenu({ compact }: { compact: boolean }) {
  return (
    <div aria-hidden="true" className="flex min-w-0 items-center gap-3 font-sans text-[11px] text-white/95">
      <svg viewBox="0 0 24 24" className="size-3.5 shrink-0 fill-current">
        <path d="M17.1 12.4c0-2.4 2-3.6 2.1-3.7-1.2-1.7-3-1.9-3.7-1.9-1.6-.2-3.1.9-3.9.9-.8 0-2-1-3.3-.9-1.7 0-3.3 1-4.2 2.5-1.8 3.1-.5 7.7 1.2 10.2.8 1.2 1.8 2.5 3.1 2.4 1.2-.1 1.7-.8 3.2-.8s1.9.8 3.3.8c1.4 0 2.2-1.2 3-2.4.9-1.4 1.3-2.7 1.4-2.8-.1 0-2.2-.8-2.2-3.3ZM14.5 5.2c.7-.9 1.2-2.1 1.1-3.2-1.1 0-2.4.7-3.1 1.5-.7.8-1.3 2-1.2 3.1 1.2.1 2.4-.6 3.2-1.4Z" />
      </svg>
      <span className="shrink-0 font-semibold">AI Status</span>
      {!compact && (
        <div className="hidden items-center gap-2 xl:flex">
          <span>File</span>
          <span>Edit</span>
          <span>View</span>
          <span>Help</span>
        </div>
      )}
    </div>
  );
}

function DockIcon({ app, id }: { app: string; id: string }) {
  return (
    <svg viewBox="0 0 48 48" className="size-full overflow-visible" fill="none">
      <defs>
        <linearGradient id={id} x1="24" y1="2" x2="24" y2="46" gradientUnits="userSpaceOnUse">
          <stop stopColor={app === "Finder" ? "#85d8ff" : app === "Messages" ? "#77ec67" : app === "Mail" ? "#5acafa" : app === "AI Status" ? "#545466" : "#515563"} />
          <stop offset="1" stopColor={app === "Finder" ? "#1388e9" : app === "Messages" ? "#19bd35" : app === "Mail" ? "#1675e8" : app === "AI Status" ? "#25252f" : "#20232c"} />
        </linearGradient>
        <linearGradient id={`${id}-compass`} x1="24" y1="5" x2="24" y2="43" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4bd6f7" />
          <stop offset="1" stopColor="#127ce6" />
        </linearGradient>
      </defs>
      {app === "Safari" ? (
        <>
          <circle cx="24" cy="24" r="22" fill="#f5f7fa" />
          <circle cx="24" cy="24" r="19" fill={`url(#${id}-compass)`} />
          {Array.from({ length: 12 }, (_, index) => (
            <path key={index} d="M24 7v3" stroke="white" strokeOpacity=".8" strokeWidth="1.2" transform={`rotate(${index * 30} 24 24)`} />
          ))}
          <path d="m32 14-5 13-11 7 5-13Z" fill="white" />
          <path d="m32 14-5 13-6-6Z" fill="#f45561" />
          <circle cx="24" cy="24" r="1.5" fill="#e9eef2" />
        </>
      ) : app === "Trash" ? (
        <>
          <path d="m12 13 3 29c.3 3 17.7 3 18 0l3-29" fill="#e2e9ee" fillOpacity=".9" stroke="#a3aeb8" />
          <ellipse cx="24" cy="13" rx="12" ry="3.5" fill="#f3f6f8" stroke="#b4bfc9" />
          <ellipse cx="24" cy="13" rx="9" ry="1.8" fill="#9aa6b1" />
          <path d="m19 19 1 20m4-20v20m5-20-1 20" stroke="#a8b3bd" strokeWidth="1.5" />
        </>
      ) : (
        <>
          <rect x="2" y="2" width="44" height="44" rx="10" fill={`url(#${id})`} />
          <rect x="2.5" y="2.5" width="43" height="43" rx="9.5" stroke="white" strokeOpacity=".2" />
          {app === "Finder" && (
            <>
              <path d="M25 2h11a10 10 0 0 1 10 10v24a10 10 0 0 1-10 10H24V28h-5l6-26Z" fill="#e1f0fa" />
              <path d="M14 15v5m20-5v5" stroke="#173954" strokeWidth="2" strokeLinecap="round" />
              <path d="M12 31c6 7 18 7 24 0M25 8l-5 19h6v13" stroke="#173954" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </>
          )}
          {app === "Messages" && <path d="M39 22c0 8-7 13-15 13-2 0-4 0-6-1l-7 4 2-8c-3-2-4-5-4-8 0-7 7-12 15-12s15 5 15 12Z" fill="white" />}
          {app === "Mail" && (
            <>
              <rect x="8" y="13" width="32" height="23" rx="2" fill="white" />
              <path d="m9 14 15 12 15-12M9 35l11-11m19 11L28 24" stroke="#3aa0eb" strokeWidth="1.3" />
            </>
          )}
          {app === "Terminal" && (
            <>
              <rect x="6" y="7" width="36" height="34" rx="4" fill="#11141a" stroke="#a7abb3" strokeWidth="1.2" />
              <path d="m12 15 7 6-7 6m11 0h9" stroke="#f4f5f6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </>
          )}
          {app === "AI Status" && (
            <>
              <rect x="11" y="17" width="26" height="21" rx="6" stroke="#eaeaf1" strokeWidth="2.5" />
              <path d="M24 10v7m-17 8h4m26 0h4M19 31h10" stroke="#eaeaf1" strokeWidth="2.5" strokeLinecap="round" />
              <circle cx="24" cy="9" r="2.5" fill="#eaeaf1" />
              <circle cx="19" cy="25" r="2" fill="#eaeaf1" />
              <circle cx="29" cy="25" r="2" fill="#eaeaf1" />
            </>
          )}
        </>
      )}
    </svg>
  );
}

export function MacDock({ compact, visible }: { compact: boolean; visible: boolean }) {
  const id = useId().replace(/:/g, "");
  return (
    <div aria-hidden="true" className={cn("pointer-events-none absolute inset-x-0 bottom-3 z-20 flex justify-center", !visible && "hidden")}>
      <div className={cn("flex items-center gap-2 rounded-2xl border border-white/30 bg-white/20 px-2.5 pt-2 pb-1.5 shadow-[0_8px_24px_rgba(0,0,0,0.25)] backdrop-blur-2xl", compact && "gap-1.5 px-2 pt-1.5 pb-1")}>
        {["Finder", "Safari", "Mail", "Messages", "Terminal", "AI Status", "Trash"].map((app, index) => (
          <div key={app} className={cn("relative pb-1.5", app === "Trash" && "ml-1 border-l border-white/30 pl-2") }>
            <div className={cn("size-10 drop-shadow-[0_2px_2px_rgba(0,0,0,0.25)]", compact && "size-7 sm:size-8")}>
              <DockIcon app={app} id={`${id}-${index}`} />
            </div>
            {(app === "Finder" || app === "AI Status") && <span className="absolute bottom-0 left-1/2 size-1 -translate-x-1/2 rounded-full bg-white/80" />}
          </div>
        ))}
      </div>
    </div>
  );
}
