import os
import json
from typing import List, Dict, Any

from mcp.server.fastmcp import FastMCP
from openai import OpenAI

# ---- API setup via environment ----
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in environment")
client = OpenAI(api_key=OPENAI_API_KEY)

mcp = FastMCP("linkedin_creator_tools")


def _safe_chat_json(prompt: str) -> Dict[str, Any]:
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        if isinstance(content, str):
            try:
                return json.loads(content)
            except Exception:
                return {"message": content}
        return {"message": str(content)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@mcp.tool()
async def analyze_brand_voice(brand_desc: str, samples: str = "") -> Dict[str, Any]:
    prompt = f"""
You are a content strategist who specializes in LinkedIn.

Brand description:
{brand_desc}

Sample posts (if any):
{samples}

Analyze this and return a JSON object with:
- audience
- tone
- style_notes
- do
- dont
"""
    return _safe_chat_json(prompt)


@mcp.tool()
async def summarise_pillar(
    pillar_text: str,
    brand_profile: Dict[str, Any],
) -> Dict[str, Any]:
    prompt = f"""
You are helping a creator repurpose content for LinkedIn.

Brand profile (JSON):
{json.dumps(brand_profile, indent=2)}

Pillar content:
{pillar_text}

1) Write a 2–3 sentence summary in the brand's voice.
2) Extract 5–7 bullet key points that LinkedIn posts could be built around.

Return JSON with:
- summary
- key_points (list of strings)
"""
    return _safe_chat_json(prompt)


@mcp.tool()
async def generate_linkedin_posts(
    pillar_text: str,
    brand_profile: Dict[str, Any],
    n_posts: int = 3,
) -> List[Dict[str, Any]]:
    prompt = f"""
You are a LinkedIn ghostwriter.

Brand profile (JSON):
{json.dumps(brand_profile, indent=2)}

Pillar content:
{pillar_text}

Create {n_posts} LinkedIn posts that feel distinct but consistent with the brand.

For each post:
- Use a strong scroll-stopping first line (the hook).
- Keep paragraphs short.
- Add a clear CTA at the end (comment, save, DM, etc.).
- Vary the format across posts (story, how-to, myth-busting, lessons learned, etc.).

Return a JSON list. Each item must have:
- title
- hook
- body
- CTA
- format_hint
"""
    data = _safe_chat_json(prompt)

    if isinstance(data, dict) and "error" in data:
        return [{
            "title": "Error generating posts",
            "hook": data["error"],
            "body": data["error"],
            "CTA": "",
            "format_hint": "error",
        }]

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "posts" in data and isinstance(data["posts"], list):
        return data["posts"]
    if isinstance(data, dict):
        return [data]

    return [{
        "title": "Unexpected response from model",
        "hook": str(data),
        "body": str(data),
        "CTA": "",
        "format_hint": "unknown",
    }]


if __name__ == "__main__":
    mcp.run(transport="stdio")
