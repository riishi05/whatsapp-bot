/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        wa: {
          green: "#25D366",
          dark: "#075E54",
          teal: "#128C7E",
          bubble: "#DCF8C6",
        },
      },
    },
  },
  plugins: [],
};
