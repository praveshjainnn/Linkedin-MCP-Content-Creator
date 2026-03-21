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
async def fetch_trending_news(feed_url: str = "https://techcrunch.com/feed/") -> Dict[str, Any]:
    """Fetches real-time trending news headlines to inject into posts."""
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
async def fast_generate(
    brand_desc: str,
    pillar_text: str,
    n_posts: int = 3,
    trending_context: str = "",
    sample_posts: str = "",
) -> Dict[str, Any]:
    """Single-call tool: analyses brand, summarises pillar, and writes posts in ONE LLM pass."""
    news_section = f"\nToday's Trending News (weave at least one headline into a post hook):\n{trending_context}" if trending_context else ""
    samples_section = f"\nSample posts for style reference:\n{sample_posts}" if sample_posts else ""

    prompt = f"""You are an expert LinkedIn ghostwriter. Complete all three tasks below in a single JSON response.

BRAND: {brand_desc}{samples_section}
CONTENT: {pillar_text}{news_section}

Tasks:
1. Derive a brief brand profile.
2. Extract 3-5 key points from the content.
3. Write {n_posts} distinct LinkedIn posts using the brand voice and key points.

Return ONLY this JSON (no extra text):
{{
  "brand_profile": {{
    "audience": "...",
    "tone": "...",
    "style_notes": "...",
    "do": "...",
    "dont": "..."
  }},
  "pillar_summary": {{
    "summary": "...",
    "key_points": ["...", "..."]
  }},
  "posts": [
    {{
      "title": "...",
      "hook": "...",
      "body": "...",
      "CTA": "...",
      "format_hint": "story|how-to|myth-busting|lessons-learned"
    }}
  ]
}}"""
    return _safe_chat_json(prompt)

@mcp.tool()
async def analyze_brand_voice(brand_desc: str, samples: str = "") -> Dict[str, Any]:
    prompt = f"""LinkedIn content strategist. Brand: {brand_desc}. Samples: {samples}.
Return JSON: audience, tone, style_notes, do, dont."""
    return _safe_chat_json(prompt)

@mcp.tool()
async def summarise_pillar(
    pillar_text: str,
    brand_profile: Dict[str, Any],
) -> Dict[str, Any]:
    prompt = f"""Repurpose for LinkedIn. Brand: {json.dumps(brand_profile)}.
Content: {pillar_text}
Return JSON: summary (2-3 sentences), key_points (list of 5 strings)."""
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

@mcp.tool()
async def generate_image_prompts(
    posts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """For each LinkedIn post, generate 3 distinct Midjourney/DALL-E prompt variations."""
    posts_text = "\n\n".join(
        f"Post #{i+1}\nTitle: {p.get('title', 'Untitled')}\nHook: {p.get('hook', '')}\nTheme: {p.get('body', '')[:300]}"
        for i, p in enumerate(posts)
    )
    prompt = f"""You are a world-class creative director specializing in LinkedIn social media visuals.

For EACH LinkedIn post below, produce EXACTLY 3 image prompt variations.
Each variation must use a DIFFERENT visual style and must directly reflect the POST'S SPECIFIC MESSAGE and theme — not generic business imagery.

The 3 styles must be:
1. "3D Render" — surreal, geometric, dramatic lighting, depth of field
2. "Cinematic Photo" — photo-realistic, moody, story-driven, specific scene
3. "Flat Illustration" — clean vector style, bold palette, modern editorial

Rules for every prompt:
- 2-3 sentences, rich and specific
- Mention exact colors, mood, lighting, and composition
- Tie the SUBJECT directly to the post's core idea
- Ready to paste into Midjourney (v6) or DALL-E 3

Posts:
{posts_text}

Return ONLY this exact JSON structure, no extra text:
{{
  "image_prompts": [
    {{
      "post_number": 1,
      "title": "exact post title here",
      "variations": [
        {{
          "style": "3D Render",
          "prompt": "..."
        }},
        {{
          "style": "Cinematic Photo",
          "prompt": "..."
        }},
        {{
          "style": "Flat Illustration",
          "prompt": "..."
        }}
      ]
    }}
  ]
}}"""
    return _safe_chat_json(prompt)

if __name__ == "__main__":
    mcp.run(transport="stdio")
