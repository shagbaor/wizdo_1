# Wizdo Portfolio

A static, dependency-free portfolio site for **Wizdo, Web3 Growth Strategist**.

- `index.html`: content and structure
- `styles.css`: glassmorphism design system, animations and responsive breakpoints
- `script.js`: scroll reveals, count-ups, 3D tilt, magnetic buttons, nav pill, mobile menu

## Run locally

Open `index.html` in a browser, or serve the folder:

```bash
npx serve portfolio
```

## Personalise

Search `index.html` for these placeholders and replace them:
- `t.me/wizdo`: Telegram (still a placeholder)
- `x.com/wizdo_1`: X profile, also used by each "Proof of Work" card link
- `Wizdo002@gmail.com`: email

Brand assets live in `assets/`: `logo.svg` (favicon/logo), PNG icons, and the
portrait (`wizdo.webp` with `wizdo.jpg` fallback).

The site respects `prefers-reduced-motion` and `prefers-reduced-transparency`.
