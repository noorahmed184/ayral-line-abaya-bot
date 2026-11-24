# AERAL LINE – Abaya Sales Assistant 🌸

A Gulf-Arabic chatbot for an abaya shop. It answers customer questions (prices, colors, sizes, delivery, exchange), **finds abayas from a photo**, and **hands the conversation to a staff member by email** when needed.

🔗 **Live demo:** 
🎥 **Video walkthrough:**

## Features
- Text Q&A grounded only in the shop catalog and store info (no invented prices).
- **Image search:** the customer uploads a photo → CLIP finds the closest catalog items → a Gemini model compares them visually and answers.
- Automatic fallback between several Gemini models, with retries.
- **Staff handoff** (complaints, custom tailoring, order/payment problems) with an email notification.
- Separate conversation history for each visitor.

## How it works
```
Customer (web UI)
      │  text + optional photo
      ▼
 AbayaBot.reply()
 ├─ CLIP (clip-ViT-B-32) + index.npy → top-3 similar abayas
 ├─ Gemini (OpenAI-compatible API) with catalog + store info as context
 └─ tool call handoff_to_staff → email to staff
```

## Project files
| File | Purpose |
|---|---|
| `app.py` | Gradio web interface |
| `bot_core.py` | Bot logic: retrieval, LLM calls, handoff tool |
| `notifications.py` | Email notification to staff |
| `catalog.json` | Abaya catalog (code, name, price, colors, sizes, ...) |
| `store_info.md` | Shop policies and information |
| `index.npy` | Pre-computed CLIP embeddings of the catalog images |
| `images/` | Catalog images |
| `requirements.txt` | Dependencies |

## Setup
```bash
git clone https://github.com/noorahmed184/ayral-line-abaya-bot.git
cd ayral-line-abaya-bot
pip install -r requirements.txt
```

Set these environment variables (never commit them):

| Variable | Used for |
|---|---|
| `GEMINI_API_KEY` | Gemini API key |
| `STAFF_EMAIL` | Email that receives handoff notifications |
| `SENDER_EMAIL` | Gmail address that sends them |
| `GMAIL_APP_PASSWORD` | Gmail app password |
| `APP_USER`, `APP_PASS` | Optional login for the web app |

Run:
```bash
python app.py
```

## Deployment
The app is deployed on Hugging Face Spaces (Gradio). Secrets are configured in the Space settings, not in the code.

## Tech stack
Python, Gradio, Sentence-Transformers (CLIP), Google Gemini API (via the OpenAI SDK), SMTP (Gmail).

## Known limitations and next steps
- Very similar abayas can be confused in image search. Planned: several photos per item and a stricter visual-comparison prompt.
- Running on an always-on server.

## Author
Noor Ahmed
