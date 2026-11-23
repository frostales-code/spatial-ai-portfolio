/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Archivo', 'Noto Sans SC', 'system-ui', 'sans-serif'],
        sans: ['Manrope', 'Noto Sans SC', 'system-ui', 'sans-serif'],
        mono: ['Chivo Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        paper: '#FFFFFF',
        surface: '#F4F5F7',
        hairline: '#E2E5EA',
        'hairline-strong': '#CBD0D8',
        ink: '#0E1015',
        muted: '#525866',
        cobalt: '#153CE8',
        'cobalt-deep': '#0E2BB5',
        'cobalt-tint': '#EEF2FF',
        'teal-ok': '#0F766E',
        crimson: '#C62828',
      },
    },
  },
  plugins: [],
};
