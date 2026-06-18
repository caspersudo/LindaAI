import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LindaAI — Is your website safe?",
  description:
    "Plain-language security checks for Kenyan businesses. Verify your own domain, run a passive scan, get a clear report in English or Kiswahili.",
};

export const viewport: Viewport = {
  themeColor: "#0A2540",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
