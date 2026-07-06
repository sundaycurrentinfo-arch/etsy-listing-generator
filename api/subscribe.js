import { get, put } from "@vercel/blob";

const BLOB_PATH = "emails.csv";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function parseCsv(content) {
  const lines = content.trim().split("\n");
  const rows = [];

  for (let i = 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) continue;

    const commaIndex = line.indexOf(",");
    const email = line.slice(0, commaIndex).trim().toLowerCase();
    const subscribedAt = line.slice(commaIndex + 1).trim();

    if (email) {
      rows.push({ email, subscribed_at: subscribedAt });
    }
  }

  return rows;
}

function rowsToCsv(rows) {
  const lines = ["email,subscribed_at"];
  for (const row of rows) {
    lines.push(`${row.email},${row.subscribed_at}`);
  }
  return `${lines.join("\n")}\n`;
}

async function readCsv() {
  try {
    const result = await get(BLOB_PATH, { access: "private" });

    if (!result || result.statusCode !== 200) {
      return "email,subscribed_at\n";
    }

    return await new Response(result.stream).text();
  } catch {
    return "email,subscribed_at\n";
  }
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return Response.json({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const body = await request.json();
    const email = (body.email || "").trim().toLowerCase();

    if (!email || !EMAIL_PATTERN.test(email)) {
      return Response.json(
        { error: "Please enter a valid email address." },
        { status: 400 }
      );
    }

    const rows = parseCsv(await readCsv());

    if (!rows.some((row) => row.email === email)) {
      rows.push({ email, subscribed_at: new Date().toISOString() });
      await put(BLOB_PATH, rowsToCsv(rows), {
        access: "private",
        allowOverwrite: true,
      });
    }

    return Response.json({ ok: true });
  } catch (error) {
    console.error("subscribe error:", error);
    return Response.json(
      { error: error.message || "Something went wrong. Please try again." },
      { status: 500 }
    );
  }
}
