import os
import sys
import json
import re
import csv
import io
import urllib.request
import xml.etree.ElementTree as ET
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

from fastapi import FastAPI, HTTPException  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore
from fastapi.staticfiles import StaticFiles  # type: ignore
from pydantic import BaseModel  # type: ignore

from mcp import ClientSession, StdioServerParameters  # type: ignore
from mcp.client.stdio import stdio_client  # type: ignore

SERVER_PATH = "creator_mcp_server.py"

def _safe_json_loads(text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    try:
        return json.loads(text)
    except Exception:
        return None

def _parse_multi_json_objects(text: str) -> List[Any]:
    objs = []
    matches = re.findall(r"\{.*?\}", text, flags=re.DOTALL)
    for m in matches:
        parsed = _safe_json_loads(m)
        if parsed is not None:
            objs.append(parsed)
        else:
            objs.append({"raw": m})
    return objs

def _normalise_posts(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, dict):
        if "posts" in raw and isinstance(raw["posts"], list):
            items = raw["posts"]
        else:
            items = [raw]
    elif isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        text = raw.strip()
        parsed = _safe_json_loads(text)
        if parsed is not None:
            return _normalise_posts(parsed)
        multi = _parse_multi_json_objects(text)
        if multi:
            items = multi
        else:
            return [{"title": "Post", "hook": text, "body": text, "CTA": "", "format_hint": "raw-text"}]
    else:
        return [{"title": "Post", "hook": str(raw), "body": str(raw), "CTA": "", "format_hint": "raw"}]
    
    normalised = []
    for item in items:
        if not isinstance(item, dict):
            item = {"title": "Post", "hook": str(item), "body": str(item), "CTA": "", "format_hint": "raw"}
        normalised.append({
            "title": item.get("title", "Post"),
            "hook": item.get("hook", ""),
            "body": item.get("body", ""),
            "CTA": item.get("CTA", ""),
            "format_hint": item.get("format_hint", "general"),
        })
    return normalised

def _normalise_brand_profile(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict): return raw
    if isinstance(raw, str):
        parsed = _safe_json_loads(raw.strip())
        if isinstance(parsed, dict): return parsed
        return {"raw": raw}
    return {"raw": str(raw)}

def _normalise_pillar_summary(raw: Any) -> Dict[str, Any]:
    summary = ""
    key_points = []
    if isinstance(raw, dict):
        summary = str(raw.get("summary", ""))
        kps = raw.get("key_points", [])
        if isinstance(kps, list):
            key_points = [str(k) for k in kps]
    elif isinstance(raw, str):
        parsed = _safe_json_loads(raw.strip())
        if isinstance(parsed, dict):
            return _normalise_pillar_summary(parsed)
        summary = raw
    else:
        summary = str(raw)
    
    res = {
        "summary": summary,
        "key_points": key_points,
    }
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k not in ["summary", "key_points"]:
                res[k] = v
    return res

class MCPClientHelper:
    def __init__(self):
        self.session: Any = None
        self.exit_stack: Any = None

    async def connect(self):
        from contextlib import AsyncExitStack
        self.exit_stack = AsyncExitStack()
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[SERVER_PATH],
            env={
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
            },
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        
        self.session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await self.session.initialize()

    async def close(self):
        if self.exit_stack:
            await self.exit_stack.aclose()

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        if not self.session:
            raise RuntimeError("MCP session not initialized")
        result = await self.session.call_tool(name, args)
        content = result.content
        texts = []
        if isinstance(content, list):
            for c in content:
                if hasattr(c, "text"):
                    texts.append(c.text)
                else:
                    texts.append(str(c))
            text = "\n".join(texts)
        else:
            if hasattr(content, "text"):
                text = content.text
            else:
                text = str(content)
                
        parsed = _safe_json_loads(text)
        if parsed is not None:
            return parsed
        return text

mcp_client = MCPClientHelper()

def get_latest_blog_post(rss_url: str) -> str:
    print(f"[SCANNING] RSS Feed: {rss_url}")
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        
    root = ET.fromstring(xml_data)
    # Get the newest post
    latest_item = root.find('./channel/item')
    
    if latest_item is None:
        return "No posts found."
        
    title = latest_item.find('title')
    link = latest_item.find('link')
    
    title_text = title.text if title is not None else "Untitled"
    link_text = link.text if link is not None else "No link"
    
    return f"Title: {title_text}\nLink: {link_text}"

def send_approval_email(generated_posts: List[Dict[str, Any]], target_email: str) -> str:
    print("[EMAIL] Simulating Email Sending Process...")
    # In a real scenario, you'd pull credentials from environment variables:
    # SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
    # SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    
    body = f"To: {target_email}\nSubject: [NEW] LinkedIn Posts Ready for Approval!\n"
    body += "-" * 50 + "\n"
    body += "Good morning! Here are today's generated posts based on the new blog article:\n\n"
    for idx, post in enumerate(generated_posts):
        body += f"--- DRAFT POST {idx+1} ---\n"
        body += f"Hook: {post.get('hook', '')}\n"
        body += f"{post.get('body', '')}\n"
        body += f"CTA: {post.get('CTA', '')}\n\n"
        
    # We will just print the email to the terminal for now so we don't accidentally spam anyone!
    print("\n" + "="*50)
    print("[OUTBOX]")
    print("="*50)
    print(body)
    print("="*50 + "\n")
    return body


async def run_automated_pipeline(user_feed: str = "https://techcrunch.com/feed/", target_email: str = "marketing_manager@company.com") -> str:
    print("[PIPELINE WAKING UP]...")
    
    # 1. RSS Scanning Phase
    pillar_content = get_latest_blog_post(user_feed)
    print(f"[FOUND ARTICLE] {pillar_content.splitlines()[0]}")
    
    # 2. Preparation Phase
    brand_profile = {
        "audience": "Tech enthusiasts and founders",
        "tone": "Sharp, insightful, and slightly informal",
        "style_notes": "Use short sentences. Avoid corporate jargon.",
        "do": "Be opinionated. Start with a strong hook.",
        "dont": "Don't use hashtags or emojis in the middle of sentences."
    }
    
    # Get Trending News RAG
    print("[FETCHING] World news context for RAG injection...")
    news_raw = await mcp_client.call_tool("fetch_trending_news", {"feed_url": "https://techcrunch.com/feed/"})
    trending_context = news_raw.get("trending_news", "No news available.") if isinstance(news_raw, dict) else str(news_raw)
    
    # 3. AI Engine Phase
    print("[AI ENGINE] Processing Content through Local Llama 3.2 Model... (This may take a minute)")
    posts_raw = await mcp_client.call_tool(
        "generate_linkedin_posts",
        {
            "pillar_text": pillar_content,
            "brand_profile": brand_profile,
            "trending_context": trending_context,
            "n_posts": 3,
        }
    )
    posts = _normalise_posts(posts_raw)
    print("[SUCCESS] Generated 3 LinkedIn drafts!")
    
    # 4. Email Courier Phase
    email_draft = send_approval_email(posts, target_email)
    return email_draft


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_client.connect()
    
    # 🕒 Step 1: Start the Background Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_automated_pipeline, 'cron', hour=8, minute=0)
    scheduler.start()
    print("[SYSTEM] Background Scheduler Started (Runs every day at 8:00 AM)")
    
    yield
    await mcp_client.close()

app = FastAPI(lifespan=lifespan)

class PipelineRequest(BaseModel):
    user_feed: str
    target_email: str

@app.post("/api/test-pipeline")
async def trigger_pipeline_test(req: PipelineRequest):
    """Manually trigger the pipeline and return the email draft."""
    try:
        email_draft = await run_automated_pipeline(req.user_feed, req.target_email)
        return {"message": email_draft}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SendEmailRequest(BaseModel):
    target_email: str
    body: str

@app.post("/api/send-email")
async def send_actual_email(req: SendEmailRequest):
    """Sends the generated draft email to the target email via SMTP."""
    
    # ⚠️ IMPORTANT: To make this work, you must change these to your actual credentials!
    # If using Gmail, you need to generate an "App Password" in your Google Account Settings.
    SENDER_EMAIL = "jainrolex70@gmail.com"
    SENDER_PASSWORD = "wjuq xlxa bmxt zhtn"
    
    if "your_actual_email" in SENDER_EMAIL:
        raise HTTPException(
            status_code=400, 
            detail="To send a real email, you must add your Sender Email and App Password around line 285 in server.py!"
        )
        
    try:
        msg = EmailMessage()
        msg['Subject'] = '🚀 New LinkedIn Posts Ready for Approval!'
        msg['From'] = SENDER_EMAIL
        msg['To'] = req.target_email
        msg.set_content(req.body)
        
        # Connect to Gmail and send it
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
            
        return {"message": "Email dispatched successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


class GenerateRequest(BaseModel):
    brand_desc: str
    sample_posts: str = ""
    pillar_text: str
    n_posts: int = 3
    use_trending_news: bool = False
    feed_url: str = "https://techcrunch.com/feed/"

@app.post("/api/generate")
async def generate_posts(req: GenerateRequest):
    if not req.brand_desc.strip():
        raise HTTPException(status_code=400, detail="Missing brand description")
    if not req.pillar_text.strip():
        raise HTTPException(status_code=400, detail="Missing pillar text")

    try:
        # Fetch trending news first (fast, just RSS scraping - not an LLM call)
        trending_context = ""
        if req.use_trending_news:
            news_raw = await mcp_client.call_tool(
                "fetch_trending_news",
                {"feed_url": req.feed_url},
            )
            if isinstance(news_raw, dict) and "trending_news" in news_raw:
                trending_context = news_raw["trending_news"]
            elif isinstance(news_raw, str):
                trending_context = news_raw

        # Single LLM call for EVERYTHING (brand profile + summary + posts)
        result_raw = await mcp_client.call_tool(
            "fast_generate",
            {
                "brand_desc": req.brand_desc,
                "pillar_text": req.pillar_text,
                "n_posts": int(req.n_posts),
                "trending_context": trending_context,
                "sample_posts": req.sample_posts,
            },
        )

        if isinstance(result_raw, dict) and "error" in result_raw:
            raise HTTPException(status_code=500, detail=result_raw["error"])

        # Extract the three parts from the combined response
        brand_profile = _normalise_brand_profile(
            result_raw.get("brand_profile", result_raw) if isinstance(result_raw, dict) else result_raw
        )
        pillar_summary = _normalise_pillar_summary(
            result_raw.get("pillar_summary", {}) if isinstance(result_raw, dict) else {}
        )
        posts_raw = result_raw.get("posts", []) if isinstance(result_raw, dict) else []
        posts = _normalise_posts(posts_raw)

        return {
            "brand_profile": brand_profile,
            "pillar_summary": pillar_summary,
            "posts": posts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExportCSVRequest(BaseModel):
    posts: List[Dict[str, Any]]

@app.post("/api/export-csv")
async def export_txt(req: ExportCSVRequest):
    """Converts generated posts into a plain .txt file that opens in Notepad."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    lines = []
    lines.append("LINKEDIN CONTENT CALENDAR")
    lines.append("=" * 50)
    lines.append("")
    for i, post in enumerate(req.posts):
        day = days[i % len(days)]
        lines.append(f"--- POST #{i+1} | {day} | {post.get('format_hint', 'general').upper()} ---")
        lines.append(f"Title   : {post.get('title', '')}")
        lines.append(f"Hook    : {post.get('hook', '')}")
        lines.append("")
        lines.append(post.get("body", ""))
        lines.append("")
        lines.append(f"CTA     : {post.get('CTA', '')}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("")
    content = "\r\n".join(lines)  # Windows line endings for Notepad
    return StreamingResponse(
        iter([content]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=linkedin_content_calendar.txt"},
    )

class ImagePromptsRequest(BaseModel):
    posts: List[Dict[str, Any]]

@app.post("/api/image-prompts")
async def get_image_prompts(req: ImagePromptsRequest):
    """Generate Midjourney/DALL-E image prompts for a list of LinkedIn posts."""
    if not req.posts:
        raise HTTPException(status_code=400, detail="No posts provided")
    try:
        result = await mcp_client.call_tool(
            "generate_image_prompts",
            {"posts": req.posts},
        )
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        # Normalise: result may be {"image_prompts": [...]} or a list
        if isinstance(result, dict) and "image_prompts" in result:
            return {"image_prompts": result["image_prompts"]}
        if isinstance(result, list):
            return {"image_prompts": result}
        return {"image_prompts": [result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

static_path = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path, exist_ok=True)
app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run("server:app", host="0.0.0.0", port=1337, reload=True)
