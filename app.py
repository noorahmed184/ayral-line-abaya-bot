# -*- coding: utf-8 -*-
"""app

Gradio
"""
import os, inspect
from bot_core import AbayaBot
from notifications import notify_staff

# Brand palette
CSS = """
:root {
    --beige: #F4EEE5;
    --beige-deep: #E8DCCB;
    --cream: #FBF8F3;
    --maroon: #6B263D;
    --maroon-dark: #4D192B;
    --text: #493A35;
}
body, .gradio-container {
    background: var(--beige) !important;
    color: var(--text) !important;
}
.gradio-container {
    max-width: 1050px !important;
    margin: auto !important;
}
#brand-header {
    text-align: center;
    padding: 28px 18px 20px;
    margin: 14px auto 20px;
    background: linear-gradient(135deg, #FBF8F3, #EFE4D7);
    border: 1px solid #E4D5C5;
    border-radius: 22px;
    box-shadow: 0 8px 28px rgba(77, 25, 43, .06);
}
#brand-name {
    color: var(--maroon);
    font-family: Georgia, serif;
    font-size: clamp(28px, 5vw, 43px);
    font-weight: 700;
    letter-spacing: 3px;
    margin: 0 0 8px;
}
#brand-title {
    color: var(--maroon-dark);
    font-size: clamp(20px, 3vw, 27px);
    font-weight: 700;
    margin: 0 0 8px;
}
#brand-subtitle {
    color: #806D62;
    font-size: 14px;
    margin: 0;
}
#chat-panel {
    position: relative;
    overflow: hidden;
    background: rgba(251, 248, 243, .92);
    border: 1px solid #E3D4C4;
    border-radius: 20px;
    padding: 12px;
    box-shadow: 0 10px 30px rgba(77, 25, 43, .06);
}
#chat-panel::before {
    content: "AERAL LINE";
    position: absolute;
    inset: 42% 0 auto 0;
    text-align: center;
    color: #6B263D;
    opacity: .055;
    font-family: Georgia, serif;
    font-size: clamp(34px, 8vw, 76px);
    font-weight: 700;
    letter-spacing: 8px;
    transform: rotate(-12deg);
    pointer-events: none;
    z-index: 0;
}
#brand-chatbot, #brand-chatbot > div {
    background: transparent !important;
    position: relative;
    z-index: 1;
}
#brand-chatbot { border: none !important; }
.message { border-radius: 16px !important; }
textarea, input { border-radius: 14px !important; }
button.primary {
    background: var(--maroon) !important;
    border-color: var(--maroon) !important;
    color: white !important;
}
button.primary:hover { background: var(--maroon-dark) !important; }
#footer-note {
    text-align: center;
    color: #927F73;
    font-size: 12px;
    padding: 14px 0 22px;
}
@media (max-width: 640px) {
    #brand-header { padding: 22px 12px 16px; margin: 8px auto 14px; }
    #chat-panel { padding: 6px; border-radius: 15px; }
    #brand-chatbot { min-height: 430px !important; }
}
"""

import gradio as gr

ERROR_MSG = "صار عندنا خلل بسيط، جربي مرة ثانية بعد شوي 🌸"

def get_bot(bot_state):
    # Each visitor/session gets its own conversation history.
    return bot_state if bot_state is not None else AbayaBot()

def read_image(files):
    if not files:
        return None
    first = files[0]
    path = first if isinstance(first, str) else first.get("path")
    if not path:
        return None
    with open(path, "rb") as f:
        return f.read()

def chat(message, history, bot_state):
    history = history or []
    message = message or {}
    text = (message.get("text") or "").strip()
    image_bytes = read_image(message.get("files") or [])

    if not text and not image_bytes:
        return None, history, bot_state

    user_display = text if text else "أرسلت صورة"
    if image_bytes:
        user_display += "\n📷 صورة مرفقة"

    bot_state = get_bot(bot_state)
    try:
        answer, handoff = bot_state.reply(text, image_bytes)
    except Exception as e:
        print("خطأ:", e)
        history = history + [
            {"role": "user", "content": user_display},
            {"role": "assistant", "content": ERROR_MSG},
        ]
        return None, history, bot_state

    history = history + [
        {"role": "user", "content": user_display},
        {"role": "assistant", "content": answer or "ما قدرت أجهز رد، جربي مرة ثانية."},
    ]

    if handoff:
        notify_staff("واجهة الويب", handoff, text or "(صورة)")
        history.append({
            "role": "assistant",
            "content": f"🔔 تم تحويل المحادثة للموظفة: {handoff}",
        })

    return None, history, bot_state

def clear_chat():
    return [], None

css_in_launch = "css" in inspect.signature(gr.Blocks.launch).parameters
blocks_kwargs = {"title": "أيرال لاين | مساعدتج الخاصة للعبايات"}
if not css_in_launch:
    blocks_kwargs["css"] = CSS

chatbot_kwargs = {"height": 510, "elem_id": "brand-chatbot"}
if "type" in inspect.signature(gr.Chatbot.__init__).parameters:
    chatbot_kwargs["type"] = "messages"

with gr.Blocks(**blocks_kwargs) as demo:
    gr.HTML("""
    <header id="brand-header" dir="rtl">
        <p id="brand-name" dir="ltr">AERAL LINE</p>
        <h1 id="brand-title">مساعدتج الخاصة للعبايات</h1>
        <p id="brand-subtitle">اختاري إطلالتج بثقة — اسألينا عن العبايات أو أرسلي صورة القطعة</p>
    </header>
    """)
    bot_state = gr.State(value=None)

    with gr.Column(elem_id="chat-panel"):
        chatbot = gr.Chatbot(**chatbot_kwargs)
        message = gr.MultimodalTextbox(
            file_types=["image"],
            file_count="single",
            placeholder="اكتبي رسالتج أو أرفقي صورة عباية...",
            show_label=False,
            submit_btn="إرسال",
            stop_btn=False,
        )

    with gr.Row():
        clear = gr.Button("محادثة جديدة", variant="secondary")

    gr.HTML('<div id="footer-note">AERAL LINE · عناية بالتفاصيل، وأناقة بكل اختيار</div>')

    message.submit(chat, inputs=[message, chatbot, bot_state],
                   outputs=[message, chatbot, bot_state])
    clear.click(clear_chat, inputs=None, outputs=[chatbot, bot_state])

launch_kwargs = {}
if css_in_launch:
    launch_kwargs["css"] = CSS
if os.environ.get("APP_USER") and os.environ.get("APP_PASS"):
    launch_kwargs["auth"] = (os.environ["APP_USER"], os.environ["APP_PASS"])

demo.launch(**launch_kwargs)
