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

# --- קבלת המפתחות ---
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
    BENYEHUDA_KEY = os.environ["BENYEHUDA_KEY"].strip()
    SENDER_EMAIL = os.environ["SENDER_EMAIL"].strip()
    APP_PASSWORD = os.environ["APP_PASSWORD"].strip()
except KeyError:
    print("❌ שגיאה: המפתחות לא נמצאו ב-Secrets.")
    exit(1)

RECEIVER_EMAIL = SENDER_EMAIL 

# הגדרות
BASE_URL = "https://benyehuda.org/api/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_ID_GUESS = 59083 
MAX_WORDS = 450 

# --- פונקציות עזר ---

def get_benyehuda_author_image(author_id):
    try:
        url = f"{BASE_URL}/authors/{author_id}"
        r = requests.get(url, params={'key': BENYEHUDA_KEY}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if 'image_url' in data and data['image_url']: return data['image_url']
            if 'portrait_url' in data and data['portrait_url']: return data['portrait_url']
    except: pass
    return None

def get_wiki_author_image(author_name):
    try:
        clean = author_name.split('/')[0].replace('רבי','').replace('הרב','').strip()
        r = requests.get("https://he.wikipedia.org/w/api.php", params={"action": "opensearch", "search": clean, "limit": 1, "format": "json"}).json()
        if r[1]:
            r_sum = requests.get(f"https://he.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(r[1][0])}").json()
            if 'thumbnail' in r_sum: return r_sum['thumbnail'].get('source')
    except: pass
    return None

def get_best_author_image(author_id, author_name):
    img = get_benyehuda_author_image(author_id)
    if img: return img
    return get_wiki_author_image(author_name)

def get_ai_analysis(title, author, text_sample, biblio_info, missing_date=False):
    working_models = [
        "models/gemini-3-flash-preview",
        "models/gemini-flash-latest",
        "models/gemini-2.5-flash-preview-09-2025",
        "models/gemini-2.5-flash-lite",
        "models/gemma-3-27b-it"
    ]
    
    source_context = f"מידע ביבליוגרפי (מקור): {biblio_info}" if biblio_info else ""
    date_instruction = "(שנת הפרסום חסרה. נסה לחלץ אותה אם ניתן)." if missing_date else ""

    prompt = f"""
    כתוב ניתוח פרשני לשיר עברי (עד 250 מילים).
    היצירה: "{title}" מאת "{author}".
    {source_context}
    טקסט השיר (חלקי): "{text_sample[:1500]}..."
    {date_instruction}

    הנחיה: כתיבה לקורא הומניסט, ישראלי (2025), רגיש, סולד מקיטש.
    
    מבנה HTML חובה (הקפד על התגיות):
    <div class="analysis-section">
        <h3>הקשר היסטורי-פוליטי</h3>
        <p>(רוח התקופה, המתח שבין היחיד לכלל).</p>
        
        <h3>קריאה עכשווית (2025)</h3>
        <p>(מה השיר אומר להיום? שאלות מוסר ושייכות. סיום נוקב).</p>
    </div>

    * החזר HTML נקי בלבד.
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
            elif response.status_code == 429: time.sleep(0.5)
        except: continue
    return "<p>לא ניתן היה לייצר ניתוח עומק הפעם.</p>"

def clean_html(raw_html, max_words):
    soup = BeautifulSoup(raw_html, 'html.parser')
    for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']): h.decompose()
    text = soup.get_text(separator='\n').strip()
    clean_lines = [line for line in text.splitlines() if line.strip() and "פרויקט בן-יהודה" not in line and "הפיקו מתנדבי" not in line]
    final_text = "\n".join(clean_lines)
    final_html = final_text.replace('\n', '<br>')
    if len(final_text.split()) <= max_words: return f"<div style='direction:rtl; text-align:right;'>{final_html}</div>", False, final_text
    short_html = "<br>".join(clean_lines[:50]) + "..." 
    return f"<div style='direction:rtl; text-align:right;'>{short_html}</div>", True, final_text

def format_date(meta):
    d = meta.get('orig_publication_date')
    if d and len(d.split('-')) == 3: return f"{d.split('-')[2]}/{d.split('-')[1]}/{d.split('-')[0]}"
    return meta.get('raw_publication_date') or str(meta.get('year') or "")

def main():
    print("🎲 מתחיל ריצה יומית בגיטהאב (עיצוב Tahoma)...")
    for i in range(1, 101):
        rid = random.randint(1, MAX_ID_GUESS)
        print(f"\n🔄 בדיקה {i}: ID {rid}...")
        try:
            r = requests.get(f"{BASE_URL}/texts/{rid}", params={'key': BENYEHUDA_KEY}, timeout=5)
            if r.status_code != 200: continue
            
            data = r.json()
            meta = data.get('metadata', {})
            if meta.get('genre') != 'poetry':
                print(f"   ⚠️ לא שירה ({meta.get('genre')})")
                continue
            
            title = meta.get('title')
            author = meta.get('author_string')
            author_id = meta.get('author_id')
            biblio_info = meta.get('bibliographic_info') or meta.get('source', '')
            
            print(f"   ✅ נמצא שיר! {title} / {author}")
            
            dl_url = data.get('download_url')
            if not dl_url: continue
            
            raw = requests.get(dl_url, timeout=10).text
            final_html, is_trunc, clean_text = clean_html(raw, MAX_WORDS)
            
            if len(clean_text) < 20: continue
            
            ai = get_ai_analysis(title, author, clean_text, biblio_info, missing_date=(format_date(meta)==""))
            
            print("   📧 שולח...")
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = f"{title} | {author}"
            
            img_src = get_best_author_image(author_id, author)
            img_html = f"<img src='{img_src}' style='width:80px; height:80px; border-radius:50%; float:left; margin-right:15px; border:2px solid #333; object-fit:cover;'>" if img_src else ""
            date_display = f" | {format_date(meta)}" if format_date(meta) else ""
            source_display = f"<br><span style='font-size:14px; color:#777;'>מקור: {biblio_info}</span>" if biblio_info else ""

            # --- עיצוב: Tahoma הוא המלך ---
            html_body = f"""
            <!DOCTYPE html>
            <html lang="he" dir="rtl">
            <head>
                <meta charset="utf-8">
                <style>
                    /* הגדרות בסיס - Tahoma לכל העמוד */
                    body, h1, h2, h3, p, div {{ font-family: Tahoma, Verdana, Segoe, sans-serif !important; }}
                    
                    /* עיצוב אזור הניתוח */
                    .ai-box {{ background:#f8f9fa; padding:25px; border-radius:8px; border-right:4px solid #333; font-size:16px; line-height: 1.6; }}
                    .ai-box h3 {{ color: #000; margin-top: 20px; margin-bottom: 10px; font-weight: bold; }}
                    
                    /* יישור לשני הצדדים - עובד מצוין עם Tahoma */
                    .ai-box p, .ai-box div {{ 
                        text-align: justify !important; 
                        text-justify: inter-word;
                    }}
                </style>
            </head>
            <body style="margin:0; padding:0; background-color:#f4f4f4;">
                <div style="background-color:#ffffff; color:#222; max-width:650px; margin:20px auto; padding:30px; border-radius:8px; box-shadow:0 0 10px rgba(0,0,0,0.05); line-height:1.6; direction:rtl; text-align:right;">
                    
                    <div style='border-bottom:1px solid #eee; padding-bottom:20px; margin-bottom:25px; overflow:hidden;'>
                        {img_html}
                        <h1 style="margin:0; font-size:26px; font-weight:bold; color:#111;">{title}</h1>
                        <div style='font-size:16px; color:#666; margin-top:5px;'>
                            {author}{date_display}
                            {source_display}
                        </div>
                    </div>
                    
                    <div style='font-size:20px; margin-bottom:40px; white-space: pre-wrap; line-height: 1.8; color:#000; font-weight:normal;'>{final_html}</div>
                    
                    <a href='{data.get('url')}' style='color:#666; text-decoration:none; border-bottom:1px solid #ccc; font-size:14px; display:inline-block; margin-bottom:30px;'>לקריאה באתר בן-יהודה ➜</a>
                    
                    <div class="ai-box">
                        {ai}
                    </div>
                    
                    <div style='text-align:center; font-size:11px; color:#aaa; margin-top:40px;'>בוט בן-יהודה</div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            s = smtplib.SMTP('smtp.gmail.com', 587); s.starttls(); s.login(SENDER_EMAIL, APP_PASSWORD); s.send_message(msg); s.quit()
            print(">>> ✅ נשלח! בדוק את המייל.")
            break 
            
        except Exception as e:
            print(f"   💥 שגיאה: {e}")

if __name__ == "__main__":
    main()
