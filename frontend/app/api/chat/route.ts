import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { question } = await req.json();

  if (!question) {
    return NextResponse.json({ error: "Question is required" }, { status: 400 });
  }

  const response = await fetch(`${FASTAPI_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  const data = await response.json();

  if (!response.ok) {
    return NextResponse.json({ error: data.detail }, { status: response.status });
  }

  return NextResponse.json({ answer: data.answer });
}