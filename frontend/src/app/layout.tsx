import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "D5: AI Decision for Energy Load Balancing", description: "GAO 217030 BLE-to-MQTT Dashboard" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased">{children}</body>
    </html>
  );
}
