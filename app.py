# app.py
import os
import sys
import json
import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import gradio as gr
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Path to the MCP server file
SERVER_PATH = "creator_mcp_server.py"

# Create a dedicated asyncio loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


class MCPClient:
    def __init__(self):
        self.exit_stack: Optional[AsyncExitStack] = None
        self.session: Optional[ClientSession] = None
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
                # Pass through OPENAI_API_KEY, used by creator_mcp_server.py
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
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
        Synchronously call an MCP tool and parse JSON if possible.
        """
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        result = loop.run_until_complete(self.session.call_tool(name, args))
        content = result.content

        # FastMCP tools typically return a list of Text contents
        texts: List[str] = []
        if isinstance(content, list):
            for c in content:
                # c likely has a .text attribute if it's text content
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

        # Try to parse JSON; if it fails, just return the raw text
        try:
            return json.loads(text)
        except Exception:
            return text


mcp_client = MCPClient()


def run_linkedin_agent(
    brand_desc: str,
    sample_posts: str,
    pillar_text: str,
    n_posts: int,
) -> str:
    """
    Orchestrate calls to MCP tools to produce a LinkedIn content pack.
    """
    if not brand_desc.strip():
        return "⚠️ Please provide a brand / creator description."
    if not pillar_text.strip():
        return "⚠️ Please paste your pillar content."

    # 1) Brand voice
    brand_profile = mcp_client.call_tool(
        "analyze_brand_voice",
        {"brand_desc": brand_desc, "samples": sample_posts or ""},
    )

    # Normalise brand_profile: expect a dict
    if isinstance(brand_profile, str):
        try:
            brand_profile = json.loads(brand_profile)
        except Exception:
            brand_profile = {}
    elif not isinstance(brand_profile, dict):
        brand_profile = {}

    # If tool reported an error, surface it clearly
    if isinstance(brand_profile, dict) and "error" in brand_profile:
        return f"❌ Error from analyze_brand_voice tool:\n\n{brand_profile['error']}"

    # 2) Pillar summary
    pillar_summary = mcp_client.call_tool(
        "summarise_pillar",
        {"pillar_text": pillar_text, "brand_profile": brand_profile},
    )

    # Normalise pillar_summary: handle both string JSON and dict
    if isinstance(pillar_summary, str):
        try:
            pillar_summary = json.loads(pillar_summary)
        except Exception:
            pillar_summary = {"summary": pillar_summary, "key_points": []}
    elif not isinstance(pillar_summary, dict):
        pillar_summary = {"summary": str(pillar_summary), "key_points": []}

    if "error" in pillar_summary:
        return f"❌ Error from summarise_pillar tool:\n\n{pillar_summary['error']}"

    # 3) LinkedIn posts
    posts = mcp_client.call_tool(
        "generate_linkedin_posts",
        {
            "pillar_text": pillar_text,
            "brand_profile": brand_profile,
            "n_posts": int(n_posts),
        },
    )

    # Normalise posts: always end up with a list[dict]
    if isinstance(posts, str):
        try:
            posts = json.loads(posts)
        except Exception:
            posts = [{
                "title": "Post",
                "hook": posts,
                "body": posts,
                "CTA": "",
                "format_hint": ""
            }]

    if isinstance(posts, dict):
        # Maybe {"posts": [...]}
        if "posts" in posts and isinstance(posts["posts"], list):
            posts = posts["posts"]
        else:
            posts = [posts]
    elif isinstance(posts, list):
        normalised: List[Dict[str, Any]] = []
        for item in posts:
            if isinstance(item, dict):
                normalised.append(item)
            else:
                normalised.append({
                    "title": "Post",
                    "hook": str(item),
                    "body": str(item),
                    "CTA": "",
                    "format_hint": ""
                })
        posts = normalised
    else:
        posts = []

    # Build a Markdown-style output
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

    if not posts:
        sections.append("_No posts generated – check for earlier errors or try again._\n")
    else:
        for i, post in enumerate(posts, start=1):
            sections.append(f"---\n\n### Post #{i}: {post.get('title', 'Untitled')}\n")
            sections.append(f"**Format:** {post.get('format_hint', 'general')}\n\n")
            sections.append(f"**Hook:** {post.get('hook', '')}\n\n")
            sections.append(post.get("body", ""))
            sections.append("\n\n**CTA:** " + post.get("CTA", "") + "\n")

    return "\n".join(sections)


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
            n_posts = gr.Slider(
                1, 10, value=3, step=1, label="Number of LinkedIn posts to generate"
            )
            run_btn = gr.Button("Generate LinkedIn Content Pack 🚀")

        with gr.Column(scale=1):
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
    def ui_wrapper(brand_desc, sample_posts, pillar_text, n_posts):
        return run_linkedin_agent(brand_desc, sample_posts, pillar_text, n_posts)

    run_btn.click(
        ui_wrapper,
        inputs=[brand_desc, sample_posts, pillar_text, n_posts],
        outputs=output_md,
    )

if __name__ == "__main__":
    # Works both locally and on Hugging Face Spaces
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
    )
