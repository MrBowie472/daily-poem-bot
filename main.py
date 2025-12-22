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

# --- קבלת המפתחות מהכספת של GitHub ---
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
BENYEHUDA_KEY = os.environ["BENYEHUDA_KEY"].strip()
SENDER_EMAIL = os.environ["SENDER_EMAIL"].strip()
APP_PASSWORD = os.environ["APP_PASSWORD"].strip()
RECEIVER_EMAIL = SENDER_EMAIL 

# הגדרות קבועות
BASE_URL = "https://benyehuda.org/api/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_WORDS = 450 
MAX_ID_GUESS = 33000 

def get_ai_analysis(title, author, text_sample, missing_date=False):
    models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-lite"]
    
    date_instruction = ""
    if missing_date:
        date_instruction = """
        ⚠️ שים לב: שנת הפרסום והמקור חסרים.
        אנא התחל את התשובה בשורה: <b>שנת פרסום: [שנה] | מקור: [שם הספר]</b> (רק אם ידוע ומהימן).
        אם לא ידוע, כתוב: <b>תאריך ומקור לא ידועים</b>.
        """

    prompt = f"""
    אתה עורך ספרותי ומבקר תרבות בעל תודעה היסטורית ופוליטית חריפה.
    קהל היעד: גבר בן 31 מהגליל, משכיל (מדיניות ציבורית), חובב פילוסופיה, סולד מקיטש.

    השיר: "{title}" מאת "{author}".
    טקסט: "{text_sample[:1500]}..."

    {date_instruction}

    כתוב ניתוח (עד 130 מילים) בשני חלקים:
    1. <h3>הקשר היסטורי-פוליטי</h3>
    הסבר את הרגע ההיסטורי/תרבותי שבו נכתב השיר. (בלי סיכומי ויקיפדיה).
    
    2. <h3>קריאה עכשווית (2025)</h3>
    מה השיר אומר לנו היום? איזה שבר הוא מציף? חבר למציאות הישראלית.
    סיים במשפט אחד חד ונוקב.

    * החזר HTML נקי בלבד (ללא ```html).
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    print(f"🤖 מנתח את: {title}...")

    for model in models:
        clean_model = model.strip()
        # בניית הכתובת בצורה בטוחה
        url = f"{GEMINI_BASE_URL}{clean_model}:generateContent?key={GEMINI_API_KEY}"
        if '[' in url: url = url.replace('[', '').split(']')[0]

        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    return result['candidates'][0]['content']['parts'][0]['text'].replace('```html', '').replace('```', '')
            elif response.status_code == 429:
                time.sleep(2); continue
        except: pass
    return "<p>לא ניתן היה לייצר ניתוח עומק הפעם.</p>"

def get_author_image(author_name):
    clean_name = author_name.split('/')[0].strip()
    clean_name = re.sub(r'(רבי|הרב|ד\"ר|ד ר|מר)\s+', '', clean_name).strip()
    search_terms = [clean_name]
    if len(clean_name.split()) > 2: search_terms.append(" ".join(clean_name.split()[:2]))

    for term in search_terms:
        try:
            r = requests.get("[https://he.wikipedia.org/w/api.php](https://he.wikipedia.org/w/api.php)", params={"action": "opensearch", "search": term, "limit": 1, "format": "json"}).json()
            if not r[1]: continue
            r_sum = requests.get(f"[https://he.wikipedia.org/api/rest_v1/page/summary/](https://he.wikipedia.org/api/rest_v1/page/summary/){urllib.parse.quote(r[1][0])}").json()
            if 'thumbnail' in r_sum: return r_sum['thumbnail'].get('source')
            if 'originalimage' in r_sum: return r_sum['originalimage'].get('source')
        except: pass
    return None

def clean_html(raw_html, max_words):
    soup = BeautifulSoup(raw_html, 'html.parser')
    for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']): h.decompose()
    keywords = ["פרויקט בן-יהודה", "הפיקו מתנדבי", "זמין תמיד בכתובת", "להמשך קריאה"]
    for t in soup.find_all(['p', 'div', 'small']):
        if any(k in t.get_text() for k in keywords): t.decompose()
            
    text = soup.get_text(separator=' ')
    for k in keywords: text = text.replace(k, '')
    
    if len(text.split()) <= max_words: return str(soup), False, text
    
    short, count = "", 0
    for el in soup.recursiveChildGenerator():
        if isinstance(el, str):
            t = el.strip()
            if not t or any(k in t for k in keywords): continue
            w = len(t.split())
            if count + w > max_words: short += "..."; break
            short += t + "<br>"; count += w
    return f"<div>{short}</div>", True, text

def format_date(meta):
    d = meta.get('orig_publication_date')
    if d and len(d.split('-')) == 3: return f"{d.split('-')[2]}/{d.split('-')[1]}/{d.split('-')[0]}"
    return meta.get('raw_publication_date') or str(meta.get('year') or "")

def main():
    print("🎲 מתחיל ריצה יומית בענן...")
    for _ in range(50):
        try:
            rid = random.randint(1, MAX_ID_GUESS)
            r = requests.get(f"{BASE_URL}/texts/{rid}", params={'key': BENYEHUDA_KEY})
            if r.status_code != 200: continue
            data = r.json()
            meta = data.get('metadata', {})
            if meta.get('genre') != 'poetry': continue
            
            title = meta.get('title')
            author = meta.get('author_string')
            print(f"✅ מועמד: {title} / {author}")
            
            dl_url = data.get('download_url')
            if not dl_url: continue
            
            raw = requests.get(dl_url).text
            final_html, is_trunc, clean_text = clean_html(raw, MAX_WORDS)
            
            if len(clean_text) < 40: continue
            
            ai = get_ai_analysis(title, author, clean_text, missing_date=(format_date(meta)==""))
            
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = f"{title} | {author}"
            
            img_src = get_author_image(author)
            img_html = f"<img src='{img_src}' style='width:80px; height:80px; border-radius:50%; float:left; margin-right:15px; border:2px solid #333; object-fit:cover;'>" if img_src else "<div style='width:80px; height:80px; border-radius:50%; float:left; margin-right:15px; border:2px solid #ddd; background:#f0f0f0; display:flex; align-items:center; justify-content:center; font-size:40px;'>✍️</div>"
            date_display = f" | {format_date(meta)}" if format_date(meta) else ""
            
            html_body = f"""
            <div dir='rtl' style='font-family:serif; color:#222; max-width:650px; margin:auto; line-height:1.6;'>
                <div style='border-bottom:1px solid #ddd; padding-bottom:15px; margin-bottom:25px; overflow:hidden;'>
                    {img_html}
                    <h1 style='margin:0; font-size:28px;'>{title}</h1>
                    <div style='font-size:18px; color:#555;'>{author}{date_display}</div>
                </div>
                <div style='font-size:19px; margin-bottom:40px;'>{final_html}</div>
                <a href='{data.get('url')}' style='color:#444; text-decoration:none; border-bottom:1px solid #ccc;'>לקריאה באתר בן-יהודה ➜</a>
                <hr style='margin:30px 0; border:0; border-top:1px solid #eee;'>
                <div style='background:#f9f9f9; padding:25px; border-radius:8px; font-family:sans-serif;'>{ai}</div>
                <div style='text-align:center; font-size:11px; color:#aaa; margin-top:40px;'>בוט בן-יהודה</div>
            </div>
            """
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            s = smtplib.SMTP('smtp.gmail.com', 587); s.starttls(); s.login(SENDER_EMAIL, APP_PASSWORD); s.send_message(msg); s.quit()
            print(">>> ✅ נשלח בהצלחה!")
            return 
        except Exception as e:
            print(f"Error: {e}")
            pass

if __name__ == "__main__":
    main()
