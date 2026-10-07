import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradePulse — Análise de Mercado",
  description: "Protótipo de análise quantitativa com sinais explicáveis e dados demonstrativos.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased">{children}</body>
    </html>
  );
}
