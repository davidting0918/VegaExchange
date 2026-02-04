/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Background colors
        'bg-primary': '#0D1117',
        'bg-secondary': '#161B22',
        'bg-tertiary': '#21262D',
        
        // Accent colors
        'accent-green': '#3FB950',
        'accent-red': '#F85149',
        'accent-blue': '#58A6FF',
        'accent-yellow': '#D29922',
        
        // Text colors
        'text-primary': '#F0F6FC',
        'text-secondary': '#8B949E',
        'text-tertiary': '#6E7681',
        
        // Border colors
        'border-default': '#30363D',
        'border-hover': '#8B949E',
      },
      boxShadow: {
        'glow-green': '0 0 20px rgba(63, 185, 80, 0.3)',
        'glow-red': '0 0 20px rgba(248, 81, 73, 0.3)',
        'glow-blue': '0 0 20px rgba(88, 166, 255, 0.3)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
      },
    },
  },
  plugins: [],
}
