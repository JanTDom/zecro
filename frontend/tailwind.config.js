/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        paper: {
          50: '#fdfcfb',
          100: '#f7f4ed',
          200: '#ede7db',
          300: '#ded4c0',
          400: '#c5b59a',
          800: '#2c2822',
          900: '#1b1915',
        },
        ink: {
          50: '#0d1117',
          100: '#151821',
          200: '#303646',
          300: '#4f5663',
          400: '#747b87',
          500: '#8f96a3',
          600: '#b4bac2',
          700: '#d3d7dc',
          800: '#e4e6e9',
          900: '#ffffff',
          950: '#f4f4f1',
        },
        editorial: {
          crimson: '#2451f5',
          vermilion: '#ff6b4a',
          ochre: '#f5b820',
          gold: '#e8a914',
          navy: '#151821',
          cyan: '#23c6ac',
          forest: '#1e947a',
          violet: '#6842f5',
        }
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', '"Times New Roman"', 'serif'],
        headline: ['"Fraunces"', '"Playfair Display"', 'Georgia', 'serif'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        condensed: ['"Barlow Semi Condensed"', '"Oswald"', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      boxShadow: {
        'page': '0 20px 40px -15px rgba(28, 34, 49, 0.18), 0 0 1px 1px rgba(28, 34, 49, 0.08)',
        'page-elevated': '0 30px 60px -12px rgba(28, 34, 49, 0.22), 0 0 1px 1px rgba(28, 34, 49, 0.08)',
      },
    },
  },
  plugins: [],
}
