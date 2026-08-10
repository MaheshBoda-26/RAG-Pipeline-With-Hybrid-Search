import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Cormorant_Garamond } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  weight: ["400", "500"], // humanist sans (StyreneB/Inter 400-500)
});

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
  weight: ["500"], // Anthropic display serif regular (Copernicus substitute)
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
  weight: ["400"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://rag-pipeline.dev"),
  title: {
    default: "RAG Pipeline | Hybrid Search Over Internal Docs",
    template: "%s | RAG Pipeline",
  },
  description:
    "Production-grade RAG pipeline with dense vector search, BM25 sparse retrieval, reciprocal rank fusion, LLM-as-judge reranking, and grounded generation with verified inline citations.",
  keywords: [
    "RAG",
    "retrieval-augmented generation",
    "hybrid search",
    "vector search",
    "BM25",
    "Qdrant",
    "LLM reranking",
    "citations",
  ],
  authors: [{ name: "Mahesh Boda" }],
  creator: "Mahesh Boda",
  publisher: "RAG Pipeline",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://rag-pipeline.dev",
    siteName: "RAG Pipeline",
    title: "RAG Pipeline | Hybrid Search Over Internal Docs",
    description:
      "Production-grade RAG pipeline with dense vector search, BM25 sparse retrieval, reciprocal rank fusion, LLM-as-judge reranking, and grounded generation with verified inline citations.",
    images: [
      {
        url: "/og-image.svg",
        width: 1200,
        height: 630,
        alt: "RAG Pipeline - Hybrid Search Over Internal Docs",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@ragpipeline",
    creator: "@maheshboda",
    title: "RAG Pipeline | Hybrid Search Over Internal Docs",
    description:
      "Production-grade RAG pipeline with hybrid search, LLM reranking, and verified citations.",
    images: ["/og-image.svg"],
  },
  verification: {
    google: "google-site-verification-token",
  },
  alternates: {
    canonical: "https://rag-pipeline.dev",
    types: {
      "application/rss+xml": "https://rag-pipeline.dev/feed.xml",
    },
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
    { media: "(prefers-color-scheme: dark)", color: "#12151B" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body
        className={`${inter.variable} ${cormorant.variable} ${jetbrainsMono.variable} font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  );
}