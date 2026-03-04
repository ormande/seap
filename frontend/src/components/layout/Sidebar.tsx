'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FileSearch,
  History,
  Moon,
  SunMedium,
} from "lucide-react";
import { useTheme } from "next-themes";
import { signOut, useSession } from "next-auth/react";

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
};

const NAV_ITEMS: NavItem[] = [
  {
    label: "Análise",
    href: "/",
    icon: FileSearch,
  },
  {
    label: "Histórico",
    href: "/historico",
    icon: History,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { data: session } = useSession();
  const user = session?.user;

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = (theme ?? resolvedTheme) === "dark";

  return (
    <aside
      className={[
        "sticky top-0 flex h-screen flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-sidebar)]/95 backdrop-blur-sm transition-[width] duration-300 ease-out self-start",
        "supports-[backdrop-filter]:bg-[color-mix(in_srgb,var(--bg-sidebar)_90%,transparent)]",
        collapsed ? "w-[68px]" : "w-[240px]",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2 px-3 py-4">
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border-subtle)]/80 bg-[var(--bg-card)] text-[var(--text-secondary)] shadow-sm transition hover:border-emerald-500/70 hover:text-emerald-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-sidebar)]"
          aria-label={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>

        <div
          className={[
            "flex items-center gap-2 overflow-hidden transition-opacity duration-200",
            collapsed ? "w-0 opacity-0" : "w-auto opacity-100",
          ].join(" ")}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-sm shadow-emerald-500/40">
            <span className="text-sm font-semibold tracking-tight">S</span>
          </div>
          <div className="mr-1">
            <p className="text-sm font-semibold tracking-tight text-[var(--text-primary)]">
              SEAP
            </p>
            <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--text-secondary)]">
              Análise de Processos
            </p>
          </div>
        </div>

        {collapsed && (
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-sm shadow-emerald-500/40">
            <span className="text-sm font-semibold tracking-tight">S</span>
          </div>
        )}
      </div>

      <nav className="mt-4 flex-1 space-y-1 px-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "group flex items-center rounded-xl px-2 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-emerald-100 text-slate-900 shadow-sm ring-1 ring-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200"
                  : "text-slate-700 hover:bg-emerald-50/90 hover:text-slate-900 dark:text-[var(--text-secondary)] dark:hover:bg-emerald-500/10 dark:hover:text-emerald-50",
              ].join(" ")}
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-emerald-500 transition-colors group-hover:bg-emerald-500/10 dark:text-emerald-300">
                <Icon className="h-4 w-4" />
              </span>
              <span
                className={[
                  "ml-2 truncate text-sm transition-[opacity,transform,width] duration-200",
                  collapsed
                    ? "pointer-events-none w-0 -translate-x-2 opacity-0"
                    : "w-auto translate-x-0 opacity-100",
                ].join(" ")}
              >
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-[var(--border-subtle)]/80 px-3 py-3 space-y-3">
        {user && (
          <div className="flex items-center justify-between gap-2 rounded-xl bg-[var(--bg-card)] px-2 py-2 text-xs text-[var(--text-secondary)] shadow-sm">
            <div className="flex items-center gap-2 overflow-hidden">
              {user.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.image}
                  alt={user.name ?? "Usuário"}
                  className="h-8 w-8 flex-shrink-0 rounded-full object-cover"
                />
              ) : (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-600 dark:bg-emerald-500/30 dark:text-emerald-200">
                  <span className="text-xs font-semibold">
                    {(user.name ?? user.email ?? "?").slice(0, 1).toUpperCase()}
                  </span>
                </div>
              )}
              {!collapsed && (
                <div className="min-w-0">
                  <p className="truncate text-[11px] font-semibold text-[var(--text-primary)]">
                    {user.name ?? "Usuário"}
                  </p>
                  <p className="truncate text-[10px] text-[var(--text-secondary)]">
                    {user.email ?? ""}
                  </p>
                </div>
              )}
            </div>
            {!collapsed && (
              <button
                type="button"
                onClick={() => signOut({ callbackUrl: "/login" })}
                className="rounded-full px-2 py-0.5 text-[10px] font-semibold text-emerald-600 transition hover:bg-emerald-500/10 dark:text-emerald-200"
              >
                Sair
              </button>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          className="flex w-full items-center justify-between rounded-xl bg-[var(--bg-card)] px-2 py-2 text-xs font-medium text-[var(--text-secondary)] shadow-sm transition hover:text-emerald-600 hover:shadow-md dark:hover:text-emerald-200"
        >
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-200">
              {mounted &&
                (isDark ? (
                  <Moon className="h-4 w-4" />
                ) : (
                  <SunMedium className="h-4 w-4" />
                ))}
            </div>
            {!collapsed && (
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em]">
                  Tema
                </p>
                <p className="text-[11px] text-[var(--text-secondary)]">
                  {mounted ? (isDark ? "Modo escuro" : "Modo claro") : ""}
                </p>
              </div>
            )}
          </div>
          {!collapsed && (
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-600 dark:text-emerald-200">
              {mounted ? (isDark ? "Dark" : "Light") : ""}
            </span>
          )}
        </button>
      </div>
    </aside>
  );
}

