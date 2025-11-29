---
title: Linkedin MCP Creator
emoji: 📊
colorFrom: purple
colorTo: pink
sdk: gradio
sdk_version: 6.0.1
app_file: app.py
pinned: false
license: mit
short_description: MCP-powered app to turn pillar content into LinkedIn posts
tags:
  - mcp-in-action-track-creative
  - building-mcp-track-creative
---

# LinkedIn MCP Creator

**Tags:** `mcp-in-action-track-creative` · `building-mcp-track-creative`.`mcp` · `gradio` · `agents` · `openai` · `linkedin` · `content-creation`

A Gradio + MCP app that turns your **long-form “pillar” content** into a **pack of LinkedIn posts** – using an internal MCP server powered by OpenAI.

You paste:

1. A short **brand / creator description**  
2. (Optional) A few **sample posts** in your own voice  
3. A **pillar** (article, transcript, long post)

…and the app:

- Analyzes your **brand voice** via an MCP tool  
- Summarizes the **pillar** and extracts key talking points  
- Generates **multiple LinkedIn posts** with hooks, bodies, CTAs & format hints  

All of this is orchestrated as an **agentic workflow** inside the Gradio app using MCP.

## 🎯 Hackathon Info

- **Track:** MCP in Action (Track 2 – Creative)  
- **Organization:** MCP 1st Birthday  

**Demo video:**  
`https://YOUR_DEMO_VIDEO_URL_HERE`

**Social media post:**  
`https://YOUR_LINKEDIN_POST_URL_HERE`

## 🖥️ How to Use

1. Wait for:  
   `✅ Connected to MCP server. Tools available: analyze_brand_voice, summarise_pillar, generate_linkedin_posts`
2. Fill in:
   - **Brand / Creator Description**
   - **Sample LinkedIn Posts (optional)**
   - **Pillar Content**
   - Choose number of posts
3. Click **“Generate LinkedIn Content Pack 🚀”**
4. Copy the posts from the right-hand panel, lightly edit, and publish.

## 🧱 Under the Hood

- **MCP server** (`creator_mcp_server.py`) built with `FastMCP`, exposing:
  - `analyze_brand_voice`
  - `summarise_pillar`
  - `generate_linkedin_posts`
- **Gradio app** (`app.py`) is an MCP client that:
  - Spawns the MCP server over stdio
  - Calls tools in sequence
  - Normalises and renders the outputs as a single content pack

OpenAI is used behind the scenes (via `OPENAI_API_KEY` set as a Space secret) to power all generations.

## 🔐 API Key

On Hugging Face Spaces, the app reads `OPENAI_API_KEY` from the Space’s **Secrets**.  
Users of the Space don’t need a key – if they fork or duplicate it, they’ll add their own.

## 📜 License

Released under the **MIT License**.


Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
