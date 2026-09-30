/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      // Premium SOC theme: warm paper canvas, deep-teal focus, brick critical.
      // Stepped tints follow the Bootstrap scale methodology (tint-80 subtle
      // backgrounds, tint-60 subtle borders) with WCAG-AA text emphasis.
      // "Fractul" resolves to licensed files if dropped in src/assets/fonts;
      // otherwise falls back to downloaded Space Grotesk (geometric match).
      fontFamily: {
        fractul: ['Fractul', 'Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['Fractul', 'Space Grotesk', 'Consolas', 'monospace'],
      },
      colors: {
        qf: {
          primary: '#0F766E',
          secondary: '#57534E',
          tertiary: '#1C1917',
          neutral: '#FFFFFF',
          surface: '#F4F3EF',
          onSurface: '#1C1917',
          error: '#B42318',
          border: '#E2DED4',
          canvas: '#F4F3EF',
          card: '#FFFFFF',
          ok: '#067647',
          warn: '#D97706',
        },
        // deprecated aliases — kept so old classes still compile during migration
        ivory: { DEFAULT: '#FFFFFF', soft: '#F4F3EF', deep: '#E8E6E0' },
        ink: { DEFAULT: '#1C1917', soft: '#57534E', faint: '#A8A29E' },
        line: '#E2DED4',
      },
      borderRadius: { sm: '4px', md: '8px' },
      spacing: { xs: '16px', sm: '20px', md: '24px', lg: '40px', xl: '64px' },
      boxShadow: { none: 'none' },
    },
  },
  plugins: [],
}
