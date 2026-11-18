import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { APP_NAME, FULL_NAME } from "@/lib/brand";
import "./globals.css";

// next/font scarica Inter in fase di build e la serve dal nostro dominio: nessuna richiesta a Google dal browser.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: `${FULL_NAME} · Appuntamenti e promemoria`, template: `%s · ${APP_NAME}` },
  description: "Agenda online per studi professionali: prenotazioni, promemoria WhatsApp e conferme automatiche.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f5f7" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="it" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen font-sans">{children}</body>
    </html>
  );
}
