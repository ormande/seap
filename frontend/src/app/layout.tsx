import type { Metadata } from "next";
import { Comfortaa } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "../components/theme/ThemeProvider";
import { AppShell } from "../components/layout/AppShell";
import AuthProvider from "../components/AuthProvider";

const comfortaa = Comfortaa({
  variable: "--font-comfortaa",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "SEAP - Sistema de Extração e Análise de Processos",
  description: "Análise profissional de processos licitatórios a partir de PDFs.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className={`${comfortaa.variable} font-sans antialiased`}>
        <AuthProvider>
          <ThemeProvider>
            <AppShell>{children}</AppShell>
          </ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
