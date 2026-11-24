# -*- coding: utf-8 -*-
"""AERAL LINE – brand website (Streamlit) with a side chat assistant.

Run locally:  streamlit run streamlit_app.py
Needs the same files/secrets as the Gradio app (bot_core.py, notifications.py,
catalog.json, store_info.md, index.npy, images/).
"""
import os, io, json
import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="AERAL LINE | أيرال لاين",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────── Brand settings (edit these) ─────────────────────────
BRAND = "AERAL LINE"
TAGLINE = "عناية بالتفاصيل، وأناقة بكل اختيار"
INSTAGRAM_URL = os.environ.get("INSTAGRAM_URL", "https://www.instagram.com/ayral.line/")
INSTAGRAM_HANDLE = os.environ.get("INSTAGRAM_HANDLE", "@aryal.line")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "97339500391") 
# ───────────────────────────────────────────────────────────────────────────────

PROJECT = os.path.dirname(os.path.abspath(__file__))
PAGE_SIZE = 12
GREETING = "هلا وغلا فيج في أيرال لاين 🌸\nاسأليني عن العبايات، أو أرفقي صورة القطعة وأدورلج عليها."

st.markdown("""
<style>
:root { --beige:#F4EEE5; --cream:#FBF8F3; --maroon:#6B263D; --maroon-dark:#4D192B; --text:#493A35; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--beige); color: var(--text); }
.block-container { direction: rtl; text-align: right; max-width: 1150px; padding-top: 1.5rem; }
[data-testid="stSidebar"] { background: var(--cream); border-left: 1px solid #E3D4C4; direction: rtl; }
[data-testid="stSidebar"] * { text-align: right; }
#hero { text-align:center; padding:46px 20px 38px; border-radius:26px; border:1px solid #E4D5C5;
        background: linear-gradient(135deg,#FBF8F3,#EFE4D7); box-shadow:0 8px 28px rgba(77,25,43,.07); }
#hero .brand { color:var(--maroon); font-family:Georgia,serif; font-weight:700; letter-spacing:6px;
               font-size:clamp(34px,6vw,60px); margin:0 0 8px; direction:ltr; }
#hero .title { color:var(--maroon-dark); font-size:clamp(20px,3vw,28px); font-weight:700; margin:0 0 10px; }
#hero .sub { color:#806D62; font-size:16px; margin:0 0 22px; }
.btn { display:inline-block; padding:11px 26px; border-radius:30px; margin:4px 6px; font-weight:700;
       text-decoration:none !important; font-size:15px; }
.btn-primary { background:var(--maroon); color:#fff !important; }
.btn-primary:hover { background:var(--maroon-dark); }
.btn-outline { border:1.5px solid var(--maroon); color:var(--maroon) !important; background:transparent; }
.section-title { color:var(--maroon-dark); font-size:26px; font-weight:700; margin:42px 0 6px; }
.section-sub { color:#806D62; margin:0 0 18px; }
.feature { background:var(--cream); border:1px solid #E3D4C4; border-radius:18px; padding:20px; height:100%;
           box-shadow:0 6px 20px rgba(77,25,43,.05); }
.feature .ico { font-size:30px; }
.feature h4 { color:var(--maroon); margin:8px 0 6px; }
.feature p { color:var(--text); margin:0; font-size:14.5px; line-height:1.7; }
.price { color:var(--maroon); font-weight:700; font-size:17px; }
.code { color:#927F73; font-size:12px; letter-spacing:1px; }
.contact { background:linear-gradient(135deg,#6B263D,#4D192B); color:#fff; border-radius:24px;
           padding:34px 20px; text-align:center; margin-top:40px; }
.contact h3 { color:#fff; margin:0 0 8px; font-size:26px; }
.contact p { color:#F2E6DA; margin:0 0 18px; }
.contact .btn-light { background:#FBF8F3; color:var(--maroon) !important; }
.contact .btn-ghost { border:1.5px solid #FBF8F3; color:#FBF8F3 !important; }
#footer { text-align:center; color:#927F73; font-size:12px; padding:26px 0 8px; }
div[data-testid="stVerticalBlockBorderWrapper"] { background: var(--cream); border-radius:18px; }
button[kind="secondary"] { border-radius:24px; }
</style>
""", unsafe_allow_html=True)


# ───────────────────────────── data helpers ─────────────────────────────
@st.cache_data(show_spinner=False)
def load_catalog():
    try:
        with open(os.path.join(PROJECT, "catalog.json"), encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def load_store_info():
    try:
        with open(os.path.join(PROJECT, "store_info.md"), encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def thumb_bytes(name):
    """Small JPEG thumbnail so the gallery loads fast."""
    try:
        with Image.open(os.path.join(PROJECT, "images", name)) as im:
            im = im.convert("RGB")
            im.thumbnail((600, 800))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return None


@st.cache_resource(show_spinner="جاري تجهيز المساعدة...")
def load_bot_class():
    """Loads the catalog index and CLIP model once for all visitors."""
    from bot_core import AbayaBot
    AbayaBot()
    return AbayaBot


catalog = load_catalog()
wa_link = f"https://wa.me/{WHATSAPP_NUMBER}"

# ───────────────────────────── hero ─────────────────────────────
st.markdown(f"""
<div id="hero">
  <p class="brand">{BRAND}</p>
  <p class="title">مساعدتج الخاصة للعبايات</p>
  <p class="sub">اختاري إطلالتج بثقة — {TAGLINE}</p>
  <a class="btn btn-primary" href="#gallery">تصفحي العبايات</a>
  <a class="btn btn-outline" href="{wa_link}" target="_blank">واتساب</a>
  <a class="btn btn-outline" href="{INSTAGRAM_URL}" target="_blank">انستغرام</a>
</div>
""", unsafe_allow_html=True)


# ───────────────────────────── gallery ─────────────────────────────
st.markdown('<div id="gallery"></div><div class="section-title">معرض العبايات</div>'
            '<p class="section-sub">ابحثي بالاسم أو الكود، وللتفاصيل اضغطي على «التفاصيل».</p>',
            unsafe_allow_html=True)

query = st.text_input("بحث", placeholder="ابحثي باسم العباية أو الكود (مثال: AYL-098)",
                      label_visibility="collapsed")

if "shown" not in st.session_state:
    st.session_state.shown = PAGE_SIZE

q = (query or "").strip().lower()
items = [c for c in catalog
         if not q or q in str(c.get("name", "")).lower() or q in str(c.get("code", "")).lower()
         or q in str(c.get("colors", "")).lower()]

if not catalog:
    st.info("الكاتلوج غير متوفر حالياً.")
elif not items:
    st.warning("ما لقينا نتائج، جربي كلمة ثانية.")
else:
    st.caption(f"{len(items)} عباية")
    visible = items[: st.session_state.shown]
    for row_start in range(0, len(visible), 3):
        cols = st.columns(3)
        for col, c in zip(cols, visible[row_start: row_start + 3]):
            with col.container(border=True):
                img = thumb_bytes(c.get("image", "")) if c.get("image") else None
                if img:
                    st.image(img, width="stretch")
                st.markdown(f"**{c.get('name', '')}**")
                st.markdown(f'<span class="price">{c.get("price", "")}</span>', unsafe_allow_html=True)
                st.markdown(f'<span class="code">{c.get("code", "")}</span>', unsafe_allow_html=True)
                with st.expander("التفاصيل"):
                    st.markdown(f"**الألوان:** {c.get('colors', '-')}")
                    st.markdown(f"**المقاسات:** {c.get('sizes', '-')}")
                    if c.get("fabric"):
                        st.markdown(f"**القماش:** {c['fabric']}")
                    if c.get("stock"):
                        st.markdown(f"**التوفر:** {c['stock']}")
                    if c.get("order_type"):
                        st.markdown(f"**نوع الطلب:** {c['order_type']}")
                    if c.get("tailoring_days"):
                        st.markdown(f"**مدة التفصيل:** {c['tailoring_days']}")
                    if c.get("description"):
                        st.write(c["description"])
    if len(items) > st.session_state.shown:
        if st.button("عرض المزيد", width="stretch"):
            st.session_state.shown += PAGE_SIZE
            st.rerun()

# ───────────────────────────── store info ─────────────────────────────
info = load_store_info()
if info:
    st.markdown('<div class="section-title">معلومات المحل</div>', unsafe_allow_html=True)
    with st.expander("التوصيل والاستبدال والسياسات"):
        st.markdown(info)

# ───────────────────────────── contact ─────────────────────────────
st.markdown(f"""
<div class="contact">
  <h3>تواصلي معنا</h3>
  <p>نسعد بخدمتج ونرد على كل استفساراتج</p>
  <a class="btn btn-light" href="{wa_link}" target="_blank">واتساب: {WHATSAPP_NUMBER}</a>
  <a class="btn btn-ghost" href="{INSTAGRAM_URL}" target="_blank">انستغرام {INSTAGRAM_HANDLE}</a>
</div>
<div id="footer">{BRAND} · {TAGLINE}</div>
""", unsafe_allow_html=True)

# ───────────────────────────── side chat assistant ─────────────────────────────
# (kept last so the page renders before the model is touched)
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]
if "up_key" not in st.session_state:
    st.session_state.up_key = 0

with st.sidebar:
    st.markdown("### 💬 مساعدتج الخاصة")
    st.caption("اسألي عن الأسعار والألوان والمقاسات والتوصيل، أو أرفقي صورة عباية ثم اكتبي رسالتج.")
    chat_box = st.container(height=430)
    uploaded = st.file_uploader("📷 أرفقي صورة عباية", type=["jpg", "jpeg", "png", "webp"],
                                key=f"up_{st.session_state.up_key}")
    prompt = st.chat_input("اكتبي رسالتج...")

with chat_box:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if prompt:
        image_bytes = uploaded.getvalue() if uploaded else None
        shown_text = prompt + ("\n\n📷 صورة مرفقة" if image_bytes else "")
        st.session_state.messages.append({"role": "user", "content": shown_text})
        with st.chat_message("user"):
            st.markdown(shown_text)
            if image_bytes:
                st.image(image_bytes, width=140)

        with st.chat_message("assistant"):
            with st.spinner("لحظة..."):
                try:
                    if "bot" not in st.session_state:
                        st.session_state.bot = load_bot_class()()
                    answer, handoff = st.session_state.bot.reply(prompt.strip(), image_bytes)
                    answer = answer or "ما قدرت أجهز رد، جربي مرة ثانية."
                except Exception as e:
                    print("خطأ:", repr(e))
                    answer, handoff = ERROR_MSG, None
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

            if handoff:
                try:
                    from notifications import notify_staff
                    notify_staff("موقع AERAL LINE", handoff, prompt.strip() or "(صورة)")
                except Exception as e:
                    print("notify error:", repr(e))
                note = f"🔔 تم تحويل المحادثة للموظفة: {handoff}"
                st.markdown(note)
                st.session_state.messages.append({"role": "assistant", "content": note})

        if uploaded:
            st.session_state.up_key += 1   # reset the uploader
            st.rerun()

with st.sidebar:
    if st.button("محادثة جديدة", width="stretch"):
        st.session_state.messages = [{"role": "assistant", "content": GREETING}]
        st.session_state.pop("bot", None)
        st.session_state.up_key += 1
        st.rerun()