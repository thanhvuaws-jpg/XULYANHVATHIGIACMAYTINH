export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink:   { 900:'#0b0e18', 800:'#111524', 700:'#161b2d', 600:'#1b2136' },
        line:  { DEFAULT:'#2b3350', soft:'#232a44' },
        brand: { 400:'#a78bfa', 500:'#8b5cf6', 600:'#7c3aed' },
        cyan:  { 400:'#22d3ee' },
        mint:  { 400:'#34d399' },
        amber: { 400:'#fbbf24' },
        rose:  { 400:'#fb7185' },
      },
      fontFamily: { sans: ['Inter','Segoe UI','system-ui','sans-serif'] },
    },
  },
  plugins: [],
}
