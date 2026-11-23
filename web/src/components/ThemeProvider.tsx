'use client';

import React from 'react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';
import { MotionConfig } from 'framer-motion';
import { TooltipProvider } from '@/components/ui/tooltip';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      <MotionConfig reducedMotion="user">
        <TooltipProvider delayDuration={180}>{children}</TooltipProvider>
      </MotionConfig>
    </NextThemesProvider>
  );
}
