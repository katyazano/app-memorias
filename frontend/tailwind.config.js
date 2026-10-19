/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border, 214.3 31.8% 91.4%))",
        input: "hsl(var(--input, 214.3 31.8% 91.4%))",
        ring: "hsl(var(--ring, 222.2 84% 4.9%))",
        background: "hsl(var(--background, 0 0% 100%))",
        foreground: "hsl(var(--foreground, 222.2 84% 4.9%))",
        primary: {
          DEFAULT: "#18181b", // zinc-900 sobrio
          foreground: "#fafafa",
        },
        secondary: {
          DEFAULT: "#f4f4f5", // zinc-100
          foreground: "#18181b",
        },
        muted: {
          DEFAULT: "#f4f4f5",
          foreground: "#71717a", // zinc-500
        },
        accent: {
          DEFAULT: "#27272a", // zinc-800
          foreground: "#fafafa",
        },
        card: {
          DEFAULT: "#ffffff",
          foreground: "#18181b",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          '"SFMono-Regular"',
          "Consolas",
          '"Liberation Mono"',
          "Menlo",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
}
