/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dce8ff",
          500: "#3b5bdb",
          600: "#2f47ad",
          700: "#293f94",
        },
      },
    },
  },
  plugins: [],
};
