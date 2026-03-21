# app.py
import os
import sys
import json
import re
import asyncio
import csv
import tempfile
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Union, Tuple

import gradio as gr  # type: ignore
from mcp import ClientSession, StdioServerParameters  # type: ignore
from mcp.client.stdio import stdio_client  # type: ignore

# Path to the MCP server file
SERVER_PATH = "creator_mcp_server.py"

# Create a dedicated asyncio loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


# --------- Helper functions for parsing tool output ---------


def _safe_json_loads(text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """
    Try json.loads; return None if it fails.
    """
    try:
        return json.loads(text)
    except Exception:
        return None


def _parse_multi_json_objects(text: str) -> List[Any]:
    """
    Handle the case where the model returns multiple JSON objects
    one after another, e.g.:

        { ... } { ... } { ... }

    This is not valid JSON as a whole, but each {...} is.
    We extract all object substrings and parse them individually.
    """
    objs: List[Any] = []
    # Find { ... } blocks (non-greedy, across newlines)
    matches = re.findall(r"\{.*?\}", text, flags=re.DOTALL)
    for m in matches:
        parsed = _safe_json_loads(m)
        if parsed is not None:
            objs.append(parsed)
        else:
            # Fallback: keep raw chunk
            objs.append({"raw": m})
    return objs


def _normalise_posts(raw: Any) -> List[Dict[str, Any]]:
    """
    Take whatever the tool returned for posts (string/dict/list)
    and normalise it to a list[dict] with at least:
    - title
    - hook
    - body
    - CTA
    - format_hint
    """
    # Case 1: raw is already a Python list/dict (from JSON)
    if isinstance(raw, dict):
        # Maybe {"posts": [...]}
        if "posts" in raw and isinstance(raw["posts"], list):
            items = raw["posts"]
        else:
            items = [raw]
    elif isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        text = raw.strip()

        # Try simple json.loads first
        parsed = _safe_json_loads(text)
        if parsed is not None:
            return _normalise_posts(parsed)

        # Try extracting multiple JSON objects
        multi = _parse_multi_json_objects(text)
        if multi:
            items = multi
        else:
            # As a last resort: treat the entire string as one "post"
            return [{
                "title": "Post",
                "hook": text,
                "body": text,
                "CTA": "",
                "format_hint": "raw-text",
            }]
    else:
        # Unknown type: just wrap as one generic post
        return [{
            "title": "Post",
            "hook": str(raw),
            "body": str(raw),
            "CTA": "",
            "format_hint": "raw",
        }]

    # Now ensure everything in items is a dict with the expected keys
    normalised: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            item = {
                "title": "Post",
                "hook": str(item),
                "body": str(item),
                "CTA": "",
                "format_hint": "raw",
            }
        normalised.append({
            "title": item.get("title", "Post"),
            "hook": item.get("hook", ""),
            "body": item.get("body", ""),
            "CTA": item.get("CTA", ""),
            "format_hint": item.get("format_hint", "general"),
        })
    return normalised


def _normalise_brand_profile(raw: Any) -> Dict[str, Any]:
    """
    Ensure brand_profile is a dict. Try to parse JSON if it's a string.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = _safe_json_loads(raw.strip())
        if isinstance(parsed, dict):
            return parsed
        return {"raw": raw}
    # fallback
    return {"raw": str(raw)}


def _normalise_pillar_summary(raw: Any) -> Dict[str, Any]:
    """
    Ensure pillar_summary is a dict with:
    - summary: str
    - key_points: list[str]
    """
    summary = ""
    key_points: List[str] = []

    if isinstance(raw, dict):
        summary = str(raw.get("summary", ""))
        kps = raw.get("key_points", [])
        if isinstance(kps, list):
            key_points = [str(k) for k in kps]
    elif isinstance(raw, str):
        parsed = _safe_json_loads(raw.strip())
        if isinstance(parsed, dict):
            return _normalise_pillar_summary(parsed)
        # If it's just plain text, treat as summary
        summary = raw
    else:
        summary = str(raw)

    return {
        "summary": summary,
        "key_points": key_points,
        **({k: v for k, v in raw.items() if k not in ["summary", "key_points"]} if isinstance(raw, dict) else {}),
    }


# --------- MCP Client wrapper ---------


class MCPClient:
    def __init__(self):
        self.exit_stack: Any = None
        self.session: Any = None
        self.stdio = None
        self.write = None

    def connect(self) -> str:
        """
        Sync wrapper to initialize MCP connection (called on Gradio load).
        """
        return loop.run_until_complete(self._connect())

    async def _connect(self) -> str:
        if self.exit_stack:
            await self.exit_stack.aclose()

        self.exit_stack = AsyncExitStack()

        server_params = StdioServerParameters(
            command=sys.executable,   # use the current Python interpreter
            args=[SERVER_PATH],
            env={
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                # Pass through GEMINI_API_KEY, used by creator_mcp_server.py
                "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
            },
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        await self.session.initialize()

        tools_resp = await self.session.list_tools()
        tool_names = [t.name for t in tools_resp.tools]
        return f"✅ Connected to MCP server. Tools available: {', '.join(tool_names)}"

    def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """
        Synchronously call an MCP tool and return its content as:
        - parsed JSON (dict/list) if possible
        - otherwise, raw text
        """
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        result = loop.run_until_complete(self.session.call_tool(name, args))
        content = result.content

        texts: List[str] = []
        if isinstance(content, list):
            for c in content:
                # For MCP TextContent, we expect a .text attribute
                if hasattr(c, "text"):
                    texts.append(c.text)
                else:
                    texts.append(str(c))
            text = "\n".join(texts)
        else:
            if hasattr(content, "text"):
                text = content.text  # type: ignore
            else:
                text = str(content)

        parsed = _safe_json_loads(text)
        if parsed is not None:
            return parsed
        return text


mcp_client = MCPClient()


# --------- Orchestration function ---------


def run_linkedin_agent(
    brand_desc: str,
    sample_posts: str,
    pillar_text: str,
    n_posts: int,
    use_trending_news: bool = False,
    feed_url: str = "https://techcrunch.com/feed/",
) -> Tuple[str, Optional[str]]:
    """
    Orchestrate calls to MCP tools to produce a LinkedIn content pack.
    Returns (markdown_text, csv_file_path).
    """
    if not brand_desc.strip():
        return "⚠️ Please provide a brand / creator description.", None
    if not pillar_text.strip():
        return "⚠️ Please paste your pillar content.", None

    # 1) Brand voice
    brand_profile_raw = mcp_client.call_tool(
        "analyze_brand_voice",
        {"brand_desc": brand_desc, "samples": sample_posts or ""},
    )
    brand_profile = _normalise_brand_profile(brand_profile_raw)

    # If tool reported an error, surface it clearly
    if isinstance(brand_profile, dict) and "error" in brand_profile:
        return f"❌ Error from analyze_brand_voice tool:\n\n{brand_profile['error']}", None

    # 2) Pillar summary
    pillar_summary_raw = mcp_client.call_tool(
        "summarise_pillar",
        {"pillar_text": pillar_text, "brand_profile": brand_profile},
    )
    pillar_summary = _normalise_pillar_summary(pillar_summary_raw)

    if isinstance(pillar_summary, dict) and "error" in pillar_summary:
        return f"❌ Error from summarise_pillar tool:\n\n{pillar_summary['error']}", None

    # 2.5) Trending News
    trending_context = ""
    if use_trending_news:
        news_raw = mcp_client.call_tool("fetch_trending_news", {"feed_url": feed_url})
        if isinstance(news_raw, dict) and "trending_news" in news_raw:
            trending_context = news_raw["trending_news"]
        elif isinstance(news_raw, str):
            trending_context = news_raw

    # 3) LinkedIn posts
    posts_raw = mcp_client.call_tool(
        "generate_linkedin_posts",
        {
            "pillar_text": pillar_text,
            "brand_profile": brand_profile,
            "trending_context": trending_context,
            "n_posts": int(n_posts),
        },
    )
    posts = _normalise_posts(posts_raw)

    # --------- Build a Markdown-style output ---------
    sections: List[str] = []

    sections.append("## Brand Profile\n")
    sections.append("```json\n" + json.dumps(brand_profile, indent=2) + "\n```")

    sections.append("\n\n## Pillar Summary\n")
    sections.append("**Summary:**\n")
    sections.append(pillar_summary.get("summary", ""))
    sections.append("\n\n**Key Points:**\n")
    for point in pillar_summary.get("key_points", []):
        sections.append(f"- {point}")
    sections.append("\n")

    sections.append("\n\n## LinkedIn Posts\n")

    csv_path = None
    if not posts:
        sections.append("_No posts generated – check for earlier errors or try again._\n")
    else:
        # Create CSV for Content Calendar Export
        tmp_dir = tempfile.gettempdir()
        csv_path = os.path.join(tmp_dir, "linkedin_content_calendar.csv")
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Schedule Day", "Post Format", "Title", "Hook", "Body", "CTA"])
            
            for i, post in enumerate(posts, start=1):
                day = days[(i - 1) % len(days)]
                
                writer.writerow([
                    day,
                    post.get("format_hint", "general"),
                    post.get("title", ""),
                    post.get("hook", ""),
                    post.get("body", ""),
                    post.get("CTA", "")
                ])
                
                sections.append(f"---\n\n### Post #{i}: {post.get('title', 'Untitled')} ({day} 📅)\n")
                sections.append(f"**Format:** {post.get('format_hint', 'general')}\n\n")
                sections.append(f"**Hook:** {post.get('hook', '')}\n\n")
                sections.append(post.get("body", ""))
                sections.append("\n\n**CTA:** " + post.get("CTA", "") + "\n")

    return "\n".join(sections), csv_path


# ---------------- Gradio UI ----------------


with gr.Blocks(title="LinkedIn MCP Creator") as demo:
    gr.Markdown(
        """
# 💼 LinkedIn MCP Creator

This app is a **Gradio MCP client** that talks to a custom MCP server:

1. Analyzes your brand voice  
2. Summarizes your pillar content  
3. Generates multiple LinkedIn posts in your style  

All generation is done via MCP tools backed by OpenAI.
"""
    )

    status = gr.Markdown("Connecting to MCP server...")

    with gr.Row():
        with gr.Column(scale=1):
            brand_desc = gr.Textbox(
                label="Brand / Creator Description",
                lines=4,
                placeholder="Who are you? What do you talk about? Who is your audience?",
            )
            sample_posts = gr.Textbox(
                label="Sample LinkedIn Posts (optional)",
                lines=4,
                placeholder="Paste 1–3 of your LinkedIn posts so we can match your style.",
            )
            pillar_text = gr.Textbox(
                label="Pillar Content",
                lines=12,
                placeholder="Paste a long-form article, transcript, or detailed post you want to repurpose.",
            )
            use_trending_news = gr.Checkbox(
                label="Tie posts into today's Trending News (via RSS)",
                value=False,
            )
            feed_url = gr.Textbox(
                label="Custom RSS Feed URL",
                lines=1,
                value="https://techcrunch.com/feed/",
                visible=False,
            )

            use_trending_news.change(
                fn=lambda x: gr.update(visible=x),
                inputs=use_trending_news,
                outputs=feed_url,
            )

            n_posts = gr.Slider(
                1, 10, value=3, step=1, label="Number of LinkedIn posts to generate"
            )
            run_btn = gr.Button("Generate LinkedIn Content Pack 🚀")

        with gr.Column(scale=1):
            download_btn = gr.DownloadButton(label="📥 Download CSV Calendar", visible=False)
            output_md = gr.Markdown(label="Generated LinkedIn Content Pack")

    # Connect to MCP server on app load
    def on_startup():
        try:
            msg = mcp_client.connect()
        except Exception as e:
            msg = f"❌ Failed to connect to MCP server: {e}"
        return msg

    demo.load(on_startup, inputs=None, outputs=status)

    # Button click -> run agent
    def ui_wrapper(brand_desc, sample_posts, pillar_text, use_trending_news, feed_url, n_posts):
        md_text, csv_path = run_linkedin_agent(brand_desc, sample_posts, pillar_text, n_posts, use_trending_news, feed_url)
        if csv_path:
            return md_text, gr.update(value=csv_path, visible=True)
        return md_text, gr.update(value=None, visible=False)

    run_btn.click(
        ui_wrapper,
        inputs=[brand_desc, sample_posts, pillar_text, use_trending_news, feed_url, n_posts],
        outputs=[output_md, download_btn],
    )

if __name__ == "__main__":
    # Works both locally and on Hugging Face Spaces
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
    )

