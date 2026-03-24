import json
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP  # type: ignore

mcp = FastMCP("linkedin_creator_tools")

# ── Speed knobs ──────────────────────────────────────────────
# Truncate pillar text before it reaches the LLM.
PILLAR_CHAR_LIMIT = 3000

# Ollama generation options — the single biggest latency lever.
# num_predict caps output tokens; num_ctx caps the context window.
OLLAMA_OPTIONS = {
    "num_predict": 800,   # max tokens to generate  (~600 words)
    "num_ctx":     3072,  # context window (reduce from default 4096)
    "temperature": 0.7,
}

# Hard timeout for every Ollama HTTP call (seconds).
OLLAMA_TIMEOUT = 120

# Larger limits for image-prompt generation (9 detailed prompts = lots of tokens).
OLLAMA_OPTIONS_LARGE = {
    "num_predict": 2048,  # image prompts are verbose; 800 was truncating mid-JSON
    "num_ctx":     4096,
    "temperature": 0.7,
}
OLLAMA_TIMEOUT_LARGE = 180
# ─────────────────────────────────────────────────────────────

def _safe_chat_json(
    prompt: str,
    options: Optional[Dict] = None,
    timeout: int = OLLAMA_TIMEOUT,
) -> Dict[str, Any]:  # type: ignore[return]
    """Send a chat request to Ollama and return parsed JSON."""
    url = "http://localhost:11434/api/chat"
    data = {
        "model": "llama3.2",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": options or OLLAMA_OPTIONS,
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result_str = response.read().decode('utf-8')
            result_json = json.loads(result_str)
            content = result_json.get("message", {}).get("content", "")
            
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except Exception:
                    return {"error": f"LLM returned invalid JSON. Raw content: {content[:500]}"}
            return {"message": str(content)}
    except Exception as e:
        return {"error": f"Ollama Connection Error ({type(e).__name__}): {e}. Make sure Ollama is running and you have pulled the llama3.2 model."}

# xml import moved to top of file

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
    # Truncate inputs to keep the prompt lean and generation fast.
    pillar_text      = pillar_text.strip()[:int(PILLAR_CHAR_LIMIT)]  # type: ignore[misc]
    brand_desc       = brand_desc.strip()[:500]        # type: ignore[misc]
    sample_posts     = sample_posts.strip()[:800]      # type: ignore[misc]
    trending_context = trending_context.strip()[:400]  # type: ignore[misc]

    news_section = f"\nTrending News (weave into at least one hook):\n{trending_context}" if trending_context else ""
    samples_section = f"\nStyle reference posts:\n{sample_posts}" if sample_posts else ""

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
    # Limit to first 5 posts to keep output manageable for the LLM.
    posts = posts[:5]
    posts_text = "\n\n".join(
        f"Post #{i+1}\nTitle: {p.get('title', 'Untitled')}\nHook: {p.get('hook', '')}\nTheme: {p.get('body', '')[:200]}"
        for i, p in enumerate(posts)
    )
    prompt = f"""You are a creative director for LinkedIn visuals.

For EACH post below, produce EXACTLY 3 image-prompt variations in 3 styles:
1. "3D Render" - surreal, geometric, dramatic lighting
2. "Cinematic Photo" - photo-realistic, moody scene
3. "Flat Illustration" - clean vector, bold palette

Each prompt: 1-2 sentences, mention colors/mood/lighting. Tie it to the post's core idea.

Posts:
{posts_text}

Return ONLY valid JSON in this exact shape:
{{
  "image_prompts": [
    {{
      "post_number": 1,
      "title": "post title",
      "variations": [
        {{"style": "3D Render", "prompt": "..."}},
        {{"style": "Cinematic Photo", "prompt": "..."}},
        {{"style": "Flat Illustration", "prompt": "..."}}
      ]
    }}
  ]
}}"""
    # Use LARGE options so the LLM has enough tokens to write all 9+ prompts.
    return _safe_chat_json(prompt, options=OLLAMA_OPTIONS_LARGE, timeout=OLLAMA_TIMEOUT_LARGE)

if __name__ == "__main__":
    mcp.run(transport="stdio")
