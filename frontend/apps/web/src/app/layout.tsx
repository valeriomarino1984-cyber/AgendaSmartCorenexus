import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CoreNexus Agenda",
  description: "Gestione appuntamenti e promemoria automatici per studi professionali",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="it" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
