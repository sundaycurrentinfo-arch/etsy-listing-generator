import { get } from "@vercel/blob";

const BLOB_PATH = "emails.csv";

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
  if (request.method !== "GET") {
    return Response.json({ error: "Method not allowed" }, { status: 405 });
  }

  const secret = new URL(request.url).searchParams.get("secret");
  const exportSecret = process.env.EXPORT_SECRET;

  if (!exportSecret) {
    return Response.json(
      { error: "Export is not configured. Add EXPORT_SECRET to your environment." },
      { status: 500 }
    );
  }

  if (secret !== exportSecret) {
    return Response.json({ error: "Invalid export secret." }, { status: 403 });
  }

  try {
    const content = await readCsv();

    return new Response(content, {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": 'attachment; filename="subscribers.csv"',
      },
    });
  } catch (error) {
    console.error("export error:", error);
    return Response.json(
      { error: error.message || "Something went wrong. Please try again." },
      { status: 500 }
    );
  }
}
