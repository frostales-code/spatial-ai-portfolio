import type { Metadata, Viewport } from 'next';
import React from 'react';
import { ThemeProvider } from '@/components/ThemeProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'AetherVault & TectonicLoop — Spatial AI Studio',
  description:
    'Spatial AI 双引擎旗舰作品集：AetherVault（正交美学光谱编译器与 3D 空间流形）与 TectonicLoop（物理建构排雷、H/H⁻¹ 单应性投影与 Zero-LLM Decimal 造价闭环）。',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Chivo+Mono:wght@400;500;600&family=Manrope:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
