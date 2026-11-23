'use client';

import React, { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

export const ThemeToggle: React.FC = () => {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted && resolvedTheme === 'dark';

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => setTheme(isDark ? 'light' : 'dark')}
          aria-label={isDark ? '切换为建筑浅色工作室主题' : '切换为暗夜空间实验室主题'}
          className="h-8 w-8 rounded-md shrink-0"
        >
          {isDark ? (
            <Sun className="h-3.5 w-3.5 text-amber-400" strokeWidth={1.75} />
          ) : (
            <Moon className="h-3.5 w-3.5 text-foreground" strokeWidth={1.75} />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        <p>{isDark ? '切换为浅色主题' : '切换为深色主题'}</p>
      </TooltipContent>
    </Tooltip>
  );
};
