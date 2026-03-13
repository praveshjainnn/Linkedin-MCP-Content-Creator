import json
import urllib.request
from typing import List, Dict, Any

from mcp.server.fastmcp import FastMCP  # type: ignore

mcp = FastMCP("linkedin_creator_tools")

def _safe_chat_json(prompt: str) -> Dict[str, Any]:
    url = "http://localhost:11434/api/chat"
    data = {
        "model": "llama3.2",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json"
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req) as response:
            result_str = response.read().decode('utf-8')
            result_json = json.loads(result_str)
            content = result_json.get("message", {}).get("content", "")
            
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except Exception:
                    return {"message": content}
            return {"message": str(content)}
    except Exception as e:
        return {"error": f"Ollama Connection Error ({type(e).__name__}): {e}. Make sure Ollama is running and you have pulled the llama3.2 model."}

import xml.etree.ElementTree as ET

@mcp.tool()
async def fetch_trending_news(source: str = "techcrunch") -> Dict[str, Any]:
    """Fetches real-time trending news headlines to inject into posts."""
    feed_url = "https://techcrunch.com/feed/"
    try:
        req = urllib.request.Request(feed_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        headlines = []
        for item in root.findall('./channel/item')[:3]:  # type: ignore
            title = item.find('title')
            title_text = title.text if title is not None else "No title"
            
            # We skip description parsing here to keep it simple and clean, TechCrunch descriptions often have a lot of HTML structure in them.
            headlines.append(f"- {title_text}")
            
        return {
            "status": "success",
            "trending_news": "\n".join(headlines)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def analyze_brand_voice(brand_desc: str, samples: str = "") -> Dict[str, Any]:
    prompt = f"""
You are a content strategist who specializes in LinkedIn.

Brand description:
{brand_desc}

Sample posts (if any):
{samples}

Analyze this and return a JSON object with:
- audience (string)
- tone (string)
- style_notes (string)
- do (string)
- dont (string)
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

Return JSON with exactly these keys:
- summary (string)
- key_points (list of strings)
"""
    return _safe_chat_json(prompt)


@mcp.tool()
async def generate_linkedin_posts(
    pillar_text: str,
    brand_profile: Dict[str, Any],
    trending_context: str = "",
    n_posts: int = 3,
) -> List[Dict[str, Any]]:
    if trending_context and trending_context != "No news available.":
        prompt = f"""
You are an expert LinkedIn ghostwriter. Your goal is to write highly engaging posts that bridge timeless concepts with today's breaking news.

Brand profile (JSON):
{json.dumps(brand_profile, indent=2)}

Timeless Pillar Content:
{pillar_text}

Today's Trending News:
{trending_context}

Create {n_posts} LinkedIn posts.
CRITICAL REQUIREMENT: For at least 2 of these posts, you MUST use one of the "Today's Trending News" headlines as the "Hook" or introductory context, and then seamlessly transition into teaching a lesson from the "Timeless Pillar Content".

Make them feel timely, urgent, and highly relevant to today's news cycle.

For each post:
- Use a strong scroll-stopping first line (the hook) referencing the news.
- Keep paragraphs short.
- Add a clear CTA at the end (comment, save, DM, etc.).
- Vary the format across posts (story, how-to, myth-busting, lessons learned, etc.).
"""
    else:
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
"""

    prompt += """

Return a JSON object with a single key "posts" which contains a list of objects. Each object must have:
- title (string)
- hook (string)
- body (string)
- CTA (string)
- format_hint (string)
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
