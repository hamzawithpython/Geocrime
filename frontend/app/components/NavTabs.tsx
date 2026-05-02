"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function NavTabs() {
  const pathname = usePathname();

  return (
    <div className="flex border-b border-gray-800 bg-gray-950">
      <Link
        href="/map"
        className={`px-6 py-3 text-sm font-medium transition-colors ${
          pathname === "/map"
            ? "border-b-2 border-blue-500 text-white"
            : "text-gray-400 hover:text-white"
        }`}
      >
        Map
      </Link>
      <Link
        href="/chat"
        className={`px-6 py-3 text-sm font-medium transition-colors ${
          pathname === "/chat"
            ? "border-b-2 border-blue-500 text-white"
            : "text-gray-400 hover:text-white"
        }`}
      >
        AI Agent
      </Link>
    </div>
  );
}