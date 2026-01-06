# Job Intelligence Engine (JIE)

An AI-powered job intelligence system that monitors frontier AI company careers pages, classifies roles, matches them to a candidate profile, and generates insights and alerts.

## Status

Early development. Architecture and project plan in progress.

## Goals

- Continuously scrape OpenAI careers (later: Anthropic, Google, etc.)
- Classify roles by function (Solutions Architecture, AI Deployment, CS, etc.)
- Compute a fit score and gap analysis against a structured candidate profile
- Generate weekly hiring trend summaries and real-time alerts for high-fit roles
- Demonstrate practical use of LLMs, embeddings, and workflow automation

## Architecture

High level:

- Provider-agnostic scraper layer  
- Embedding + classification pipeline (OpenAI API)  
- Matching engine (fit + gaps)  
- Insight generator (weekly / monthly pulse)  
- Notification & dashboard layer  

## AI-Assisted Development

This project is intentionally built using AI pair programming:

GPT-5 is used for design, code generation, and refactoring.

A second model (e.g. Gemini) is used as a cross-model reviewer for critical modules (scraper, matching engine, etc.).

The goal is to demonstrate practical, safe use of multi-model workflows for software engineering.

## Local setup (editable install)

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
# Example run (no Discord post):
python scripts/run_daily.py --profiles cs --us_only --no_post
```

## Roadmap

Sprint 0: Repo setup, models, and basic scraper skeleton

Sprint 1: Raw scraping of OpenAI careers → JSON

Sprint 2: Embeddings + basic classification

Sprint 3: Matching engine + Discord alerts

Sprint 4: Insights + Streamlit dashboard

Sprint 5: Add additional providers (Anthropic, etc.)