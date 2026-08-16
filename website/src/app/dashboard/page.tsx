export const dynamic = "force-dynamic";

import { Metadata } from "next";
import { Navigation } from "@/components/navigation";
import { DashboardClient } from "./dashboard-client";
import { DocumentUploader } from "@/components/DocumentUploader";
import { DocumentList } from "@/components/DocumentList";
import { Footer } from "@/components/footer";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Interactive RAG Pipeline query dashboard with live vector space visualization",
};

export default function DashboardPage() {
  return (
    <>
      <Navigation />
      <main id="main-content" className="min-h-screen">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 space-y-8">
          <DocumentUploader />
          <DocumentList />
        </div>
        <DashboardClient />
      </main>
      <Footer />
    </>
  );
}