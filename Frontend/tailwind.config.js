/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#FAF8F2",
        ink: "#24332D",
        pine: {
          50: "#F0F5F1",
          600: "#39735A",
          700: "#285941",
          800: "#1F4533",
        },
        marigold: {
          300: "#F8D985",
          400: "#F2C14E",
        },
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        display: ["Georgia", "serif"],
      },
    },
  },
  plugins: [],
};