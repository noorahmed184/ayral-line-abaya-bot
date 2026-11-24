import os, base64, io, json, time
import numpy as np
from PIL import Image
from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError
from sentence_transformers import SentenceTransformer
from google.colab import userdata

PROJECT = os.path.dirname(os.path.abspath(__file__))

# if the first besy try the others
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.1-pro-preview"]
TOP_K = 3

SYSTEM = """أنتِ مساعدة مبيعات لمحل عبايات، تردين على الزبونات بلهجة خليجية بسيطة ولبقة ومختصرة.
معلومات المحل:
{store_info}
الكاتلوج (مصدرك الوحيد للأسعار والتوفر):
{catalog_text}
طريقة الشغل:
- ردي مباشرة على السلام والشكر والأسئلة عن الأسعار والألوان والمقاسات والتوصيل والاستبدال. لا تحوّلين هذي للموظفة أبداً.
- إذا الزبونة طرشت صورة، بتوصلك صورتها وبعدها صور أقرب عبايات من الكاتلوج مع كودها ودرجة التشابه.
  قارني بدقة: التطريز، الأكمام، القصّة، الأزرار، القماش، اللون. درجة التشابه مجرد مساعدة، قرارك على المقارنة البصرية.
  * إذا متأكدة: جاوبي باسم العباية وسعرها وألوانها ومقاساتها.
  * إذا عبايتين قريبتين وما تقدرين تفرقين: اعرضي الاثنتين واسألي الزبونة أي وحدة تقصد.
  * إذا ولا وحدة تطابق: قولي إنها ما لقيتها بالكاتلوج، واسألي إذا تبي الموظفة تتأكد لها.
    وإذا وافقت، استخدمي handoff_to_staff.
- لا تخمنين سعر أو معلومة مو موجودة فوق.
- handoff_to_staff فقط: شكوى، تفصيل خاص، مشكلة في طلب أو دفع، أو سؤال ما له جواب بالمعلومات.
- الرد قصير (2 إلى 4 أسطر).
"""

TOOLS = [{
    "type": "function",
    "function": {
        "name": "handoff_to_staff",
        "description": "حوّل المحادثة للموظفة. فقط للشكاوى، التفصيل الخاص، مشاكل الطلبات/الدفع، أو أسئلة ما لها جواب في المعلومات المعطاة.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "سبب التحويل بجملة قصيرة"}},
            "required": ["reason"],
        },
    },
}]

RETRY_CODES = (429, 500, 502, 503, 504)
SKIP_MODEL_CODES = (400, 404)

def get_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        from google.colab import userdata
        return userdata.get("bot2")
    except Exception:
        raise RuntimeError("Place the key GEMINI_API_KEY")


def to_block(img: Image.Image) -> dict:
    img = img.convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}

# the index and cataloge load once
class _Shared:
    loaded = False

    @classmethod
    def load(cls):
        if cls.loaded:
            return
        cls.catalog = json.load(open(f"{PROJECT}/catalog.json", encoding="utf-8-sig"))
        store_info = open(f"{PROJECT}/store_info.md", encoding="utf-8-sig").read()
        cls.emb = np.load(f"{PROJECT}/index.npy")
        assert len(cls.emb) == len(cls.catalog), "Embedding size mismatch with catalog!"
        cls.clip = SentenceTransformer("clip-ViT-B-32")

        catalog_text = "\n".join(
            f"- {c['code']} | {c['name']} | {c['price']} | ألوان: {c['colors']} | "
            f"مقاسات: {c['sizes']} | قماش: {c.get('fabric', '')} | "
            f"نوع الطلب: {c.get('order_type', '')} | مدة التفصيل: {c.get('tailoring_days', '')} | "
            f"التوفر: {c.get('stock', '')} | {c['description']}"
            for c in cls.catalog)

        cls.system = SYSTEM.format(store_info=store_info, catalog_text=catalog_text)
        cls.client = OpenAI(
            api_key=get_api_key(),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_retries=0,
            timeout=60, )
        cls.loaded = True

# for each customer alone
class AbayaBot:
    def __init__(self):
        _Shared.load()
        self.history = []

    def find_similar(self, img, k=TOP_K):
        q = _Shared.clip.encode(img.convert("RGB"), normalize_embeddings=True)
        sims = _Shared.emb @ q
        return [(_Shared.catalog[i], float(sims[i])) for i in np.argsort(-sims)[:k]]
# try each model 3 times
    def _call(self, messages):
        last_error = None
        for model in MODELS:
            for attempt in range(3):
                try:
                    return _Shared.client.chat.completions.create(
                        model=model, max_tokens=800, tools=TOOLS, messages=messages)
                except APIStatusError as e:
                    last_error = e
                    if e.status_code in SKIP_MODEL_CODES:
                        break                      # ينتقل للموديل اللي بعده مباشرة
                    if e.status_code not in RETRY_CODES:
                        raise
                except (APIConnectionError, APITimeoutError) as e:
                    last_error = e
                time.sleep(2 * 2 ** attempt)
            print(f"⚠️ {model} didn't work ttry the others")
        raise last_error

    def reply(self, text="", image_bytes=None):
        content = []
        if image_bytes:
            img = Image.open(io.BytesIO(image_bytes))
            content += [{"type": "text", "text": " customer photos:"}, to_block(img)]
            for c, score in self.find_similar(img):
                with Image.open(f"{PROJECT}/images/{c['image']}") as cand:
                    content += [
                        {"type": "text",
                         "text": f" Recommended from the catalog : {c['code']} ({c['name']}) - similar to  {score:.2f}"},
                        to_block(cand),
                    ]
        content.append({"type": "text", "text": text or "customer sent photo without text"})

        start = len(self.history)
        self.history.append({"role": "user", "content": content})
        handoff = None

        try:
            while True:
                resp = self._call([{"role": "system", "content": _Shared.system}] + self.history)
                msg = resp.choices[0].message
                self.history.append(msg.model_dump(exclude_none=True))
                if not msg.tool_calls:
                    break
                for call in msg.tool_calls:
                    if call.function.name == "handoff_to_staff":
                        try:
                            handoff = json.loads(call.function.arguments).get("reason", "")
                        except Exception:
                            handoff = "غير مححدد"
                    self.history.append({"role": "tool", "tool_call_id": call.id,
                                         "content": "تم إشعار الموظفة."})
        except Exception:
            del self.history[start:]

        self.history[start]["content"] = [b for b in self.history[start]["content"] if b["type"] == "text"]
        return msg.content or "", handoff
