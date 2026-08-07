export const dynamic = "force-dynamic";

import { Metadata } from "next";
import { Navigation } from "@/components/navigation";
import { DashboardClient } from "./dashboard-client";
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
        <DashboardClient />
      </main>
      <Footer />
    </>
  );
}