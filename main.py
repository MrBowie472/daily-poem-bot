import os
import requests
import smtplib
import random
import time
import urllib.parse
import re
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- קבלת המפתחות בצורה מאובטחת מ-GitHub Secrets ---
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
    BENYEHUDA_KEY = os.environ["BENYEHUDA_KEY"].strip()
    SENDER_EMAIL = os.environ["SENDER_EMAIL"].strip()
    APP_PASSWORD = os.environ["APP_PASSWORD"].strip()
except KeyError:
    print("❌ שגיאה: המפתחות לא נמצאו ב-Secrets של גיטהאב.")
    exit(1)

RECEIVER_EMAIL = SENDER_EMAIL 

# הגדרות
BASE_URL = "https://benyehuda.org/api/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_ID_GUESS = 59083 
MAX_WORDS = 450 

def get_ai_analysis(title, author, text_sample, missing_date=False):
    # --- הנבחרת המנצחת (Gemini 3 בראש) ---
    working_models = [
        "models/gemini-3-flash-preview",           # הכוכב החדש שעבד לך
        "models/gemini-flash-latest",              # יציב מאוד
        "models/gemini-2.5-flash-preview-09-2025",
        "models/gemini-2.5-flash-lite",
        "models/gemini-flash-lite-latest",
        "models/gemma-3-27b-it"
    ]
    
    date_instruction = ""
    if missing_date:
        date_instruction = """
        (הערה לבוט: שנת הפרסום חסרה. אם ידועה לך ומהימנה, ציין אותה בראש הניתוח: שנת פרסום: [שנה]. אם לא - אל תמציא).
        """

    # הפרומפט ההומניסטי המדויק
    prompt = f"""
    כתוב ניתוח פרשני לשיר עברי, עד 250 מילים סך הכול, מחולק לשני חלקים עם תגיות HTML כפי שמוגדר להלן.

    השיר: "{title}" מאת "{author}".
    טקסט השיר: "{text_sample[:1500]}..."

    {date_instruction}

    נקודת המוצא (מחייב):
    אתה כותב לקורא קבוע:
    אדם בוגר, משכיל, הומניסט, רגיש למורכבות מוסרית.
    הוא חי בישראל, מכיר מלחמה, שירות, שבר אזרחי ועייפות אידאולוגית.
    הוא מחפש בספרות לא נחמה ולא הטפה — אלא הבנה חדה, שקטה, מפוכחת.
    אל תסביר לו מושגים בסיסיים ואל תנסה “לרגש בכוח”.

    הנחיות סגנון:
    - עברית מדויקת, אינטליגנטית, לא אקדמית-כבדה.
    - כתיבה ישירה, מאופקת, בלי קלישאות ובלי פאתוס.
    - יצירתיות פרשנית עדיפה על בטיחות ניסוחית.
    - רוח הומניסטית: האדם קודם לסיסמה, השאלה קודמת לתשובה.

    מבנה הפלט (חובה):
    <h3>הקשר היסטורי-פוליטי</h3>
    הצג את הרגע ההיסטורי/תרבותי שבו נכתב השיר דרך:
    - מתח בין יחיד לחברה, או בין אידאה למציאות.
    - תחושת סדק, עייפות, או חשבון נפש של התקופה.
    - האופן שבו ההקשר מחלחל לשיר — גם בלי אזכור מפורש.
    - רוח התקופה ששרה בזמן כתיבת היצירה

    <h3>קריאה עכשווית (2025)</h3>
    פרשנות שמכבדת את הקורא:
    - מה בשיר מדבר אל מציאות של חוסר ודאות, עומס מוסרי ושאלת שייכות.
    - חיבור עדין אך ברור לישראל של 2025, ברוח הומניסטית ליברלית.
    - העדף שאלה חדה או תובנה לא-נוחה על פני מסר מרגיע.
    סיים במשפט אחד קצר, נקי, חותך — כזה שלא מבקש הסכמה אלא מחשבה.

    * החזר HTML נקי בלבד (ללא ```html).
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    print(f"   🤖 שולח לניתוח AI...")

    for model_raw in working_models:
        clean_model = model_raw.replace("models/", "").strip()
        url = f"{GEMINI_BASE_URL}{clean_model}:generateContent?key={GEMINI_API_KEY}"
        
        try:
            print(f"      ⏳ מנסה מודל: {clean_model}...")
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    print(f"      ✅ הצלחה עם {clean_model}!")
                    return result['candidates'][0]['content']['parts'][0]['text'].replace('```html', '').replace('```', '')
            
            elif response.status_code == 429:
                 print(f"      ⚠️ עומס (429), עובר לבא...")
                 time.sleep(0.5)
            else:
                 print(f"      ❌ נכשל ({response.status_code})")

        except Exception: continue
            
    return "<p>לא ניתן היה לייצר ניתוח עומק הפעם.</p>"

def get_author_image(author_name):
    try:
        clean = author_name.split('/')[0].replace('רבי','').replace('הרב','').strip()
        r = requests.get("[https://he.wikipedia.org/w/api.php](https://he.wikipedia.org/w/api.php)", params={"action": "opensearch", "search": clean, "limit": 1, "format": "json"}).json()
        if r[1]:
            r_sum = requests.get(f"[https://he.wikipedia.org/api/rest_v1/page/summary/](https://he.wikipedia.org/api/rest_v1/page/summary/){urllib.parse.quote(r[1][0])}").json()
            if 'thumbnail' in r_sum: return r_sum['thumbnail'].get('source')
    except: pass
    return None

def clean_html(raw_html, max_words):
    soup = BeautifulSoup(raw_html, 'html.parser')
    for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']): h.decompose()
    text = soup.get_text(separator='\n').strip()
    clean_lines = [line for line in text.splitlines() if line.strip() and "פרויקט בן-יהודה" not in line and "הפיקו מתנדבי" not in line]
    final_text = "\n".join(clean_lines)
    final_html = final_text.replace('\n', '<br>')
    
    if len(final_text.split()) <= max_words:
        return f"<div style='direction:rtl; text-align:right;'>{final_html}</div>", False, final_text
    
    short_html = "<br>".join(clean_lines[:50]) + "..." 
    return f"<div style='direction:rtl; text-align:right;'>{short_html}</div>", True, final_text

def format_date(meta):
    d = meta.get('orig_publication_date')
    if d and len(d.split('-')) == 3: return f"{d.split('-')[2]}/{d.split('-')[1]}/{d.split('-')[0]}"
    return meta.get('raw_publication_date') or str(meta.get('year') or "")

def main():
    print("🎲 מתחיל ריצה יומית בגיטהאב (הנבחרת המנצחת)...")
    
    for i in range(1, 101):
        rid = random.randint(1, MAX_ID_GUESS)
        print(f"\n🔄 בדיקה {i}: מנסה ID {rid}...")
        
        try:
            r = requests.get(f"{BASE_URL}/texts/{rid}", params={'key': BENYEHUDA_KEY}, timeout=5)
            
            if r.status_code != 200: 
                print(f"   ❌ דילוג (סטטוס {r.status_code})")
                continue
            
            data = r.json()
            meta = data.get('metadata', {})
            
            if meta.get('genre') != 'poetry':
                print(f"   ⚠️ לא שירה ({meta.get('genre')})")
                continue
            
            title = meta.get('title')
            author = meta.get('author_string')
            print(f"   ✅ נמצא שיר! {title} / {author}")
            
            dl_url = data.get('download_url')
            if not dl_url: continue
            
            raw = requests.get(dl_url, timeout=10).text
            final_html, is_trunc, clean_text = clean_html(raw, MAX_WORDS)
            
            if len(clean_text) < 20: 
                print("   ❌ טקסט קצר מדי")
                continue
            
            # הפעלת AI
            ai = get_ai_analysis(title, author, clean_text, missing_date=(format_date(meta)==""))
            
            # שליחה
            print("   📧 שולח...")
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = f"{title} | {author}"
            
            img_src = get_author_image(author)
            img_html = f"<img src='{img_src}' style='width:80px; height:80px; border-radius:50%; float:left; margin-right:15px; border:2px solid #333; object-fit:cover;'>" if img_src else ""
            
            date_display = f" | {format_date(meta)}" if format_date(meta) else ""

            html_body = f"""
            <div dir='rtl' style='font-family:serif; color:#222; max-width:650px; margin:auto; line-height:1.6;'>
                <div style='border-bottom:1px solid #ddd; padding-bottom:15px; margin-bottom:25px; overflow:hidden;'>
                    {img_html}
                    <h1 style='margin:0; font-size:28px;'>{title}</h1>
                    <div style='font-size:18px; color:#555;'>{author}{date_display}</div>
                </div>
                <div style='font-size:19px; margin-bottom:40px; white-space: pre-wrap;'>{final_html}</div>
                <a href='{data.get('url')}' style='color:#444; text-decoration:none; border-bottom:1px solid #ccc;'>לקריאה באתר בן-יהודה ➜</a>
                <hr style='margin:30px 0; border:0; border-top:1px solid #eee;'>
                <div style='background:#f9f9f9; padding:25px; border-radius:8px; font-family:sans-serif;'>{ai}</div>
                <div style='text-align:center; font-size:11px; color:#aaa; margin-top:40px;'>בוט בן-יהודה</div>
            </div>
            """
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            s = smtplib.SMTP('smtp.gmail.com', 587); s.starttls(); s.login(SENDER_EMAIL, APP_PASSWORD); s.send_message(msg); s.quit()
            print(">>> ✅ נשלח! בדוק את המייל.")
            break 
            
        except Exception as e:
            print(f"   💥 שגיאה: {e}")

if __name__ == "__main__":
    main()
