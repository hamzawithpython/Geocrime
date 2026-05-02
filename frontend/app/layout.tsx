import type { Metadata } from "next";
import "./globals.css";
import NavTabs from "./components/NavTabs";

export const metadata: Metadata = {
  title: "GeoCrime",
  description: "AI-powered Chicago crime analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white">
        <div className="flex flex-col h-screen">
          <div className="border-b border-gray-800 px-6 py-3">
            <h1 className="text-lg font-semibold">GeoCrime</h1>
          </div>
          <NavTabs />
          <div className="flex-1 overflow-hidden">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}