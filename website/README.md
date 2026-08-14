# RAG Pipeline Website

Production-grade website for the RAG Pipeline project built with Next.js 15, Tailwind CSS 4, Framer Motion, and React Three Fiber.

## Features

- **Landing Page** - Hero with interactive 3D vector space visualization, features, architecture, live demo, and docs
- **Dashboard** - Interactive query interface with real-time vector space visualization
- **3D Vector Space** - Real UMAP projection of document embeddings with query highlighting
- **Animations** - Framer Motion transitions, scroll animations, and micro-interactions
- **Theme** - Light/dark mode with CSS variables and OKLCH color palette

## Tech Stack

- Next.js 15 (App Router)
- React 19
- Tailwind CSS 4
- Framer Motion 11
- Three.js + React Three Fiber + Drei
- TypeScript
- Lucide React icons

## Getting Started

```bash
cd website
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the website.

## Project Structure

```
website/
├── src/
│   ├── app/
│   │   ├── globals.css          # Global styles, theme variables, animations
│   │   ├── layout.tsx           # Root layout with metadata, fonts
│   │   └── page.tsx             # Landing page composition
│   ├── components/
│   │   ├── ui/
│   │   │   └── button.tsx       # Button component with variants
│   │   ├── navigation.tsx       # Navigation with theme toggle
│   │   ├── hero.tsx             # Hero section with 3D visualization
│   │   ├── features.tsx         # Features grid
│   │   ├── architecture.tsx     # Architecture diagram with code
│   │   ├── demo.tsx             # Interactive query demo
│   │   ├── docs.tsx             # Quickstart guide
│   │   ├── footer.tsx           # Footer with links
│   │   └── vector-space-3d.tsx  # 3D vector space component
│   └── lib/
│       └── utils.ts             # Utility functions (cn, etc.)
├── package.json
├── tsconfig.json
├── next.config.js
└── tailwind.config.ts (or CSS-based config)
```

## Design System

Based on the Design.md specification:

- **Primary**: Aegis Blue (#2554C7)
- **Secondary**: Slate (#33405B)
- **Accent**: Violet (#7C3AED)
- **Semantic**: Success, Warning, Error, Info
- **Motion**: 120ms micro, 200ms standard, 240ms page, 480ms emphasis
- **Typography**: IBM Plex Sans + JetBrains Mono
- **Spacing**: 4px base unit scale

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint