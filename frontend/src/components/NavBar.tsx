"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Orbit, Search, Sparkles, LayoutDashboard } from "lucide-react";
import { api } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/search", label: "Discover", icon: Search },
  { href: "/research", label: "Run Research", icon: Sparkles },
];

type BackendStatus = "checking" | "online" | "offline";

export function NavBar() {
  const pathname = usePathname();
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        await api.health();
        if (!cancelled) setStatus("online");
      } catch {
        if (!cancelled) setStatus("offline");
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="sticky top-0 z-50 px-4 pt-4">
      <nav className="mx-auto flex max-w-6xl items-center justify-between glass-panel px-5 py-3">
        <Link href="/" className="flex items-center gap-2.5 group">
          <Orbit className="h-5 w-5 text-phosphor transition-transform group-hover:rotate-45 duration-500" />
          <span className="font-display text-lg tracking-tight text-ink">
            AI Research<span className="text-phosphor">OS</span>
          </span>
        </Link>

        <div className="flex items-center gap-1">
          {LINKS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-sans transition-colors ${
                  active
                    ? "bg-phosphor/10 text-phosphor"
                    : "text-ink-muted hover:text-ink hover:bg-white/5"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </Link>
            );
          })}
        </div>

        <div
          className="flex items-center gap-1.5 pl-3"
          title={
            status === "online"
              ? "Backend connected"
              : status === "offline"
                ? "Backend unreachable -- is docker compose running?"
                : "Checking backend connection..."
          }
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              status === "online"
                ? "bg-phosphor"
                : status === "offline"
                  ? "bg-red-400"
                  : "bg-ink-faint animate-pulse"
            }`}
          />
          <span className="hidden sm:inline text-xs font-mono text-ink-faint">
            {status === "online" ? "online" : status === "offline" ? "offline" : "..."}
          </span>
        </div>
      </nav>
    </header>
  );
}
