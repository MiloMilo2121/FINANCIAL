import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Bloomberg Terminal-inspired color palette
        terminal: {
          bg: '#0a0a0a',        // Deep black background
          panel: '#111111',     // Panel background
          border: '#1e1e1e',    // Subtle border
          text: '#e0e0e0',      // Primary text
          muted: '#666666',     // Secondary text
          accent: '#f0a500',    // Bloomberg amber/gold accent
          positive: '#00c851',  // Green for gains
          negative: '#ff3547',  // Red for losses
          neutral: '#4a90d9',   // Blue for neutral/info
          warning: '#ff8f00',   // Orange for warnings
          critical: '#ff1744',  // Bright red for critical alerts
        },
        gold: {
          50: '#fff9e6',
          100: '#fef0b3',
          200: '#fde37d',
          300: '#fbd547',
          400: '#f9c811',
          500: '#f0a500',  // Primary gold
          600: '#c07d00',
          700: '#8f5c00',
          800: '#5f3d00',
          900: '#2f1f00',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xs': ['0.65rem', { lineHeight: '1rem' }],
        'sm': ['0.75rem', { lineHeight: '1.125rem' }],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config
