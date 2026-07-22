/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Deep space navy, not pure black -- the "night sky" the
        // constellation/knowledge-graph motif lives against.
        void: {
          DEFAULT: "#0A0E17",
          panel: "#111827",
          raised: "#161F32",
        },
        phosphor: {
          DEFAULT: "#5EEAD4", // graph edges, active states, data
          dim: "#2C7A6E",
        },
        discovery: {
          DEFAULT: "#F2B44D", // claims, highlights, "new finding" accent
          dim: "#8A6425",
        },
        ink: {
          DEFAULT: "#EAF0F6", // primary text
          muted: "#8B96AB", // secondary text
          faint: "#4B5568", // tertiary / disabled
        },
        glass: {
          border: "rgba(255,255,255,0.08)",
          borderStrong: "rgba(255,255,255,0.16)",
        },
      },
      fontFamily: {
        display: ["var(--font-newsreader)", "Georgia", "serif"],
        sans: ["var(--font-manrope)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
      backdropBlur: {
        glass: "20px",
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0,0,0,0.35)",
        glow: "0 0 24px rgba(94,234,212,0.25)",
      },
      keyframes: {
        twinkle: {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" },
        },
        drift: {
          "0%": { transform: "translate(0,0)" },
          "50%": { transform: "translate(6px,-8px)" },
          "100%": { transform: "translate(0,0)" },
        },
      },
      animation: {
        twinkle: "twinkle 4s ease-in-out infinite",
        drift: "drift 18s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
