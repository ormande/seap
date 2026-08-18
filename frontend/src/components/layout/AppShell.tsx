'use client';

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { FileSearch, History } from "lucide-react";

type Props = {
  children: ReactNode;
};

function getPageMeta(pathname: string) {
  if (pathname.startsWith("/historico")) {
    return {
      title: "Histórico",
      description: "Consulte análises anteriores de processos licitatórios.",
      icon: History,
    };
  }

  return {
    title: "Análise",
    description: "Envie um PDF de licitação para extrair e revisar os dados.",
    icon: FileSearch,
  };
}

export function AppShell({ children }: Props) {
  const pathname = usePathname();
  const { title, description, icon: Icon } = getPageMeta(pathname);

  // Página de login: layout limpo, sem sidebar nem header.
  if (pathname === "/login") {
    return (
      <div className="min-h-screen bg-[var(--bg-main)] text-[var(--text-primary)]">
        {children}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[var(--bg-main)] text-[var(--text-primary)]">
      <Sidebar />

      <div className="flex min-h-screen flex-1 flex-col bg-[var(--bg-muted)]/60">
        <header className="border-b border-[var(--border-subtle)] bg-[var(--bg-main)]/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-200">
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
                <p className="text-xs text-[var(--text-secondary)]">
                  {description}
                </p>
              </div>
            </div>
            <div className="hidden text-right text-[11px] text-[var(--text-secondary)] sm:block">
              <p className="font-semibold tracking-tight text-emerald-600 dark:text-emerald-300">
                SEAP
              </p>
              <p>Sistema de Extração e Análise de Processos</p>
            </div>
          </div>
        </header>

        <main className="flex-1">
          <div className="mx-auto max-w-6xl px-6 py-6 lg:py-8">{children}</div>
        </main>
      </div>
    </div>
  );
}

