import { Metadata } from "next";
import { Navigation } from "@/components/navigation";
import { Hero } from "@/components/hero";
import { Features } from "@/components/features";
import { Architecture } from "@/components/architecture";
import { Demo } from "@/components/demo";
import { VectorSpaceExplorer } from "@/components/vector-space-explorer";
import { BenchmarkBand } from "@/components/benchmark-band";
import { CalloutCoral } from "@/components/CalloutCoral";
import { Docs } from "@/components/docs";
import { Footer } from "@/components/footer";

export const metadata: Metadata = {
  title: "RAG Pipeline | Hybrid Search Over Internal Docs",
  description:
    "Production-grade RAG pipeline with dense vector search, BM25 sparse retrieval, reciprocal rank fusion, cross-encoder reranking, and grounded generation with verified inline citations.",
  openGraph: {
    title: "RAG Pipeline | Hybrid Search Over Internal Docs",
    description:
      "Production-grade RAG pipeline with dense vector search, BM25 sparse retrieval, reciprocal rank fusion, cross-encoder reranking, and grounded generation with verified inline citations.",
    images: ["/og-image.svg"],
  },
};

export default function HomePage() {
  return (
    <>
      <Navigation />
      <main id="main-content" className="min-h-screen">
        <Hero />
        <Features />
        <BenchmarkBand />
        <Architecture />
        <Demo />
        <VectorSpaceExplorer />
        <CalloutCoral />
        <Docs />
      </main>
      <Footer />
    </>
  );
}