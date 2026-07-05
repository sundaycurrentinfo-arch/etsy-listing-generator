import json
import os
import re
from urllib import error, request

SYSTEM_PROMPT = """You are an Etsy SEO expert specializing in digital products. A seller will give you details about their product. Generate a complete Etsy listing optimized for 2026 Etsy search.

OUTPUT FORMAT — return exactly this:

TITLE (max 140 characters):
[Natural, readable title. Lead with primary buyer search phrase in first 40 characters. Include product type and 1-2 key details. No keyword stuffing.]

DESCRIPTION (150-180 words):
[One-sentence hook about the problem it solves. What's Included section in bullet points listing files and formats. Brief usage instructions. State: 'This is an INSTANT DOWNLOAD — no physical product will be shipped.' Close with who it's perfect for.]

TAGS (exactly 13, each under 20 characters, comma-separated):
[Never repeat title words. Cover: file type, occasion, recipient, use case, style, synonyms. Always include instant download and relevant format terms.]"""


def parse_listing(text):
    title_match = re.search(
        r"TITLE[^:]*:\s*\n([\s\S]*?)(?=\n\s*DESCRIPTION|$)", text, re.IGNORECASE
    )
    description_match = re.search(
        r"DESCRIPTION[^:]*:\s*\n([\s\S]*?)(?=\n\s*TAGS|$)", text, re.IGNORECASE
    )
    tags_match = re.search(r"TAGS[^:]*:\s*\n([\s\S]*?)$", text, re.IGNORECASE)

    def clean(value):
        if not value:
            return ""
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1].strip()
        return value

    title = clean(title_match.group(1) if title_match else "")
    description = clean(description_match.group(1) if description_match else "")
    tags = clean(tags_match.group(1) if tags_match else "")

    if not title or not description or not tags:
        raise ValueError("Could not parse listing from API response.")

    return {"title": title, "description": description, "tags": tags}


def call_anthropic(api_key, product_name, product_description, file_type):
    user_message = (
        f"Product Name: {product_name}\n"
        f"Product Description: {product_description}\n"
        f"File Type: {file_type}"
    )

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }

    req = request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            message = json.loads(body).get("error", {}).get("message")
        except json.JSONDecodeError:
            message = None
        raise RuntimeError(message or "Failed to generate listing. Please try again.") from exc

    text = "\n".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )

    if not text:
        raise RuntimeError("Empty response from API.")

    return parse_listing(text)


def generate_listing(body):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return 500, {
            "error": "Server is missing ANTHROPIC_API_KEY. Add it to your environment."
        }

    product_name = (body.get("productName") or "").strip()
    product_description = (body.get("productDescription") or "").strip()
    file_type = (body.get("fileType") or "").strip()

    if not product_name or not product_description or not file_type:
        return 400, {"error": "All fields are required."}

    try:
        listing = call_anthropic(api_key, product_name, product_description, file_type)
        return 200, listing
    except RuntimeError as exc:
        return 500, {"error": str(exc)}
    except Exception:
        return 500, {"error": "Something went wrong. Please try again."}
