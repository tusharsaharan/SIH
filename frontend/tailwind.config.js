/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { mono: ['JetBrains Mono', 'Consolas', 'monospace'] },
      colors: {
        ivory: {
          DEFAULT: '#FFFEF7',
          soft: '#FAF6EA',
          deep: '#F1EAD6',
        },
        ink: {
          DEFAULT: '#3F3A2E',
          soft: '#8A8272',
          faint: '#B9B09A',
        },
        line: '#E7DFC8',
      },
      boxShadow: {
        soft: '0 2px 12px rgba(63, 58, 46, 0.06)',
        lift: '0 6px 24px rgba(63, 58, 46, 0.10)',
      },
    },
  },
  plugins: [],
}
