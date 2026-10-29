/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  // classes construites dynamiquement (anneau de score)
  safelist: ['stroke-bull', 'stroke-warn', 'stroke-bear', 'stroke-muted'],
  theme: {
    extend: {
      colors: {
        bg: '#0D1117',
        panel: '#161B22',
        panel2: '#1C2230',
        line: '#30363D',
        muted: '#8B949E',
        bull: '#00FF88',
        bear: '#FF4444',
        warn: '#FFC53D',
      },
      fontFamily: {
        sans: ['Inter', 'Roboto', 'system-ui', 'sans-serif'],
      },
      screens: { xs: '375px' },
    },
  },
  plugins: [],
}
