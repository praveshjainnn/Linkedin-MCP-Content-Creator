# LinkedIn Content Creator Pro

An agentic AI application that genuinely automates content repurposing. Turn long-form "pillar" content—like articles, transcripts, and blog posts—into a ready-to-publish pack of LinkedIn posts, completely locally.

## 🚀 The Stack
- **AI Engine:** Local Llama 3.2 via Ollama (100% free and private—no API keys required!)
- **Agent Framework:** Model Context Protocol (MCP) orchestrating multi-step generation tasks. 
- **Backend/API:** FastAPI (Python) with APScheduler for automated CRON tasks.
- **Frontend:** Custom HTML/CSS/JS (Glassmorphic dark UI)

## 🎯 Architecture: Manual vs Factory

This project features two distinct modes of operation to demonstrate the difference between a simple "chat wrapper" and a true "agentic workflow".

### 1. Manual Studio 📝
Users paste their brand description and their long-form article into the UI. The application runs a local `llama3.2` model via MCP to:
1. Analyze and extract the exact Brand Voice parameters.
2. Summarize the Pillar Content into actionable bullet points.
3. Generate multiple LinkedIn drafts applying the exact Brand Voice to the extracted points.

### 2. Automated Factory 🏭
A background simulation of a true Productivity Engine. When triggered (either via API or its daily APScheduler CRON job), the application:
1. Reaches out to the web and scrapes the newest article from its target RSS feed.
2. Runs a **RAG (Retrieval-Augmented Generation)** step, reaching out to global tech news feeds to fetch live breaking news.
3. Automatically synthesizes the daily breaking news with the RSS article, tying timeless content to today's news cycle. 
4. Drafts a beautifully formatted HTML email containing the final generated LinkedIn posts and securely dispatches it to the marketing manager via SMTP.

## 🖥️ How to Run Locally

### Prerequisites
1. Install [Ollama](https://ollama.com/) on your machine.
2. Open your terminal and run `ollama pull llama3.2` to download the free LLM model to your local machine.

### Start the Server
1. Clone the repository.
2. Install requirements (e.g., `pip install fastapi uvicorn mcp sse_starlette apscheduler`).
3. Run the FastAPI server:
   ```bash
   python server.py
   ```
4. Open your browser and navigate to `http://localhost:1337` to view the UI.

## 🧱 The MCP Tools under the hood
The `creator_mcp_server.py` defines the core Agent tasks via FastMCP:
  - `analyze_brand_voice`
  - `summarise_pillar`
  - `fetch_trending_news`
  - `generate_linkedin_posts`

## 📜 License

Released under the **MIT License**.
