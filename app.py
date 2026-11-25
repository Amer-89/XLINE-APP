# -*- coding: utf-8 -*-
"""X-LINE Gaming Lounge Staff Edition | Offline transfer | Developer: Eng.Amer Ameen Alfatwa"""
import os, sqlite3, time, csv, shutil, hashlib, hmac, secrets, json, uuid, socket, io
from pathlib import Path
from datetime import datetime, timedelta
import streamlit as st

APP_NAME='X-LINE Gaming Lounge'
APP_DIR=Path(os.environ.get('XLINE_DATA_DIR', str(Path.home()/'Documents'/'X-LINE'))); APP_DIR.mkdir(parents=True,exist_ok=True)
DB=APP_DIR/'xline_pro.db'
RED='#D71920'; DARK='#17191D'; BG='#F2F4F7'; WHITE='#FFFFFF'; MUTED='#586273'; GREEN='#16834A'; BLUE='#2459A9'; BORDER='#D9DEE6'
UNITS=[('PING PONG 01','PING PONG','Table Tennis'),('PS4 01','PLAYSTATION','PS4'),('PS4 02','PLAYSTATION','PS4'),('PS4 03','PLAYSTATION','PS4'),('PS5 01','PLAYSTATION','PS5'),('BILLIARDS 01','BILLIARDS','Pool Table'),('BILLIARDS 02','BILLIARDS','Pool Table'),('BILLIARDS 03','BILLIARDS','Pool Table')]
DEFAULT_RATES={'BILLIARDS':400,'PING PONG':300,'PS4':150,'PS5':200}

CURRENT_LANG = 'ar'
def money(v, ar=None):
 if ar is None: ar = (CURRENT_LANG == 'ar')
 return f'{float(v):,.0f} {"ل.س" if ar else "SYP"}'
def dur(s):
 s=max(0,int(s)); h,r=divmod(s,3600); m,sec=divmod(r,60); return f'{h:02d}:{m:02d}:{sec:02d}'
def stamp(v):
 try:return datetime.fromtimestamp(float(v)).strftime('%Y-%m-%d %H:%M:%S')
 except:return '—'
def hash_pw(pw, salt=None):
 salt=salt or secrets.token_hex(16); digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),200000).hex(); return salt,digest
def check_pw(pw,salt,digest): return hmac.compare_digest(hash_pw(pw,salt)[1],digest)

class Store:
 def __init__(self):
  self.c=sqlite3.connect(DB); self.c.row_factory=sqlite3.Row; self.c.execute('PRAGMA foreign_keys=ON'); self.setup()
 def setup(self):
  with self.c:
   self.c.executescript('''CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS units(name TEXT PRIMARY KEY,category TEXT NOT NULL,model TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,pwhash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'staff',active INTEGER NOT NULL DEFAULT 1);
   CREATE TABLE IF NOT EXISTS drinks(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,price REAL NOT NULL,active INTEGER NOT NULL DEFAULT 1);
   CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,unit_name TEXT NOT NULL,start REAL NOT NULL,end REAL,status TEXT NOT NULL,elapsed REAL NOT NULL DEFAULT 0,segment REAL,rate REAL NOT NULL,minimum REAL NOT NULL,total REAL,username TEXT NOT NULL,drink_total REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '');
   CREATE TABLE IF NOT EXISTS day_closures(day TEXT PRIMARY KEY,closed_at REAL NOT NULL,username TEXT NOT NULL,total REAL NOT NULL,invoice_count INTEGER NOT NULL); 
   CREATE TABLE IF NOT EXISTS session_drinks(id INTEGER PRIMARY KEY AUTOINCREMENT,session_id INTEGER NOT NULL,drink_id INTEGER,drink_name TEXT NOT NULL,price REAL NOT NULL,qty INTEGER NOT NULL,FOREIGN KEY(session_id) REFERENCES sessions(id));''')
   # Safe migration for databases created by earlier X-LINE versions.
   cols={r['name'] for r in self.c.execute('PRAGMA table_info(sessions)').fetchall()}
   if 'notes' not in cols:self.c.execute("ALTER TABLE sessions ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
   closure_cols={r['name'] for r in self.c.execute('PRAGMA table_info(day_closures)').fetchall()}
   if 'reopened_at' not in closure_cols:self.c.execute('ALTER TABLE day_closures ADD COLUMN reopened_at REAL')
   if 'reopened_by' not in closure_cols:self.c.execute("ALTER TABLE day_closures ADD COLUMN reopened_by TEXT NOT NULL DEFAULT ''")
   for u in UNITS:self.c.execute('INSERT OR IGNORE INTO units VALUES(?,?,?)',u)
   defaults={'language':'ar','minimum':'100','rate_BILLIARDS':'400','rate_PING PONG':'300','rate_PS4':'150','rate_PS5':'200'}
   for k,v in defaults.items():self.c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,v))
   self.c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',('device_id',str(uuid.uuid4())))
   if not self.c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
    salt,d=hash_pw('admin123'); self.c.execute('INSERT INTO users(username,salt,pwhash,role) VALUES(?,?,?,?)',('admin',salt,d,'admin'))
 def setting(self,k,default=''): 
  r=self.c.execute('SELECT v FROM settings WHERE k=?',(k,)).fetchone(); return r['v'] if r else default
 def setsetting(self,k,v):
  with self.c:self.c.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',(k,str(v)))
 def login(self,user,pw):
  r=self.c.execute('SELECT * FROM users WHERE username=? AND active=1',(user.strip(),)).fetchone(); return r if r and check_pw(pw,r['salt'],r['pwhash']) else None
 def users(self):return self.c.execute('SELECT id,username,role,active FROM users ORDER BY username').fetchall()
 def save_user(self,username,password,role='staff',uid=None):
  username=username.strip()
  if not username:raise ValueError('اسم المستخدم مطلوب')
  if uid:
   with self.c:
    if password:
     s,d=hash_pw(password); self.c.execute('UPDATE users SET username=?,salt=?,pwhash=?,role=? WHERE id=?',(username,s,d,role,uid))
    else:self.c.execute('UPDATE users SET username=?,role=? WHERE id=?',(username,role,uid))
  else:
   if not password:raise ValueError('كلمة المرور مطلوبة')
   s,d=hash_pw(password)
   with self.c:self.c.execute('INSERT INTO users(username,salt,pwhash,role) VALUES(?,?,?,?)',(username,s,d,role))
 def set_user_active(self,uid,active):
  with self.c:self.c.execute('UPDATE users SET active=? WHERE id=?',(int(active),uid))
 def reset_password(self,uid,password):
  if not password: raise ValueError('أدخل كلمة مرور جديدة')
  salt,digest=hash_pw(password)
  with self.c:self.c.execute('UPDATE users SET salt=?,pwhash=? WHERE id=?',(salt,digest,uid))
 def units(self):return self.c.execute('SELECT * FROM units ORDER BY name').fetchall()
 def active(self):return self.c.execute("SELECT * FROM sessions WHERE status IN ('active','paused') ORDER BY id DESC").fetchall()
 def active_unit(self,n):return self.c.execute("SELECT * FROM sessions WHERE unit_name=? AND status IN ('active','paused')",(n,)).fetchone()
 def elapsed(self,r):return float(r['elapsed'] or 0)+(max(0,time.time()-r['segment']) if r['status']=='active' and r['segment'] else 0)
 def start(self,name,username):
  if self.active_unit(name):raise ValueError('هذه الوحدة لديها جلسة نشطة بالفعل')
  u=self.c.execute('SELECT * FROM units WHERE name=?',(name,)).fetchone(); model=u['model']; cat=u['category']; rate=float(self.setting('rate_'+(model if model in ('PS4','PS5') else cat),'400')); minimum=float(self.setting('minimum','100')); now=time.time()
  with self.c:self.c.execute('INSERT INTO sessions(unit_name,start,status,elapsed,segment,rate,minimum,username) VALUES(?,?,?,?,?,?,?,?)',(name,now,'active',0,now,rate,minimum,username))
 def pause(self,sid):
  r=self.session(sid)
  if r and r['status']=='active':
   e=self.elapsed(r)
   with self.c:self.c.execute("UPDATE sessions SET status='paused',elapsed=?,segment=NULL WHERE id=?",(e,sid))
 def resume(self,sid):
  with self.c:self.c.execute("UPDATE sessions SET status='active',segment=? WHERE id=? AND status='paused'",(time.time(),sid))
 def session(self,sid):return self.c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
 def drinks(self):return self.c.execute('SELECT * FROM drinks WHERE active=1 ORDER BY name').fetchall()
 def all_drinks(self):return self.c.execute('SELECT * FROM drinks ORDER BY active DESC,name').fetchall()
 def edit_drink(self,did,name,price):
  if not name.strip():raise ValueError('اسم المشروب مطلوب')
  with self.c:self.c.execute('UPDATE drinks SET name=?,price=?,active=1 WHERE id=?',(name.strip(),float(price),did))
 def delete_drink(self,did):
  with self.c:self.c.execute('UPDATE drinks SET active=0 WHERE id=?',(did,))
 def add_drink(self,name,price):
  with self.c:self.c.execute('INSERT INTO drinks(name,price) VALUES(?,?)',(name.strip(),float(price)))
 def attach_drink(self,sid,drink_id,qty):
  d=self.c.execute('SELECT * FROM drinks WHERE id=? AND active=1',(drink_id,)).fetchone()
  if not d:raise ValueError('المشروب غير موجود')
  with self.c:self.c.execute('INSERT INTO session_drinks(session_id,drink_id,drink_name,price,qty) VALUES(?,?,?,?,?)',(sid,d['id'],d['name'],d['price'],qty)); self.c.execute('UPDATE sessions SET drink_total=drink_total+? WHERE id=?',(d['price']*qty,sid))
 def session_drinks(self,sid):return self.c.execute('SELECT * FROM session_drinks WHERE session_id=?',(sid,)).fetchall()
 def finish(self,sid):
  r=self.session(sid)
  if not r:return None
  e=self.elapsed(r); mins=max(1,int((e+59.999999)//60)); play=max(mins*float(r['rate'])/60,float(r['minimum'])); total=play+float(r['drink_total']); end=time.time()
  with self.c:self.c.execute("UPDATE sessions SET status='completed',end=?,elapsed=?,segment=NULL,total=? WHERE id=?",(end,e,total,sid))
  return {'id':sid,'unit':r['unit_name'],'start':r['start'],'end':end,'elapsed':e,'minutes':mins,'rate':r['rate'],'minimum':r['minimum'],'play':play,'drinks':r['drink_total'],'total':total,'user':r['username'],'items':self.session_drinks(sid)}
 def history(self,search=''):
  return self.c.execute("SELECT * FROM sessions WHERE status='completed' AND unit_name LIKE ? ORDER BY end DESC",('%'+search+'%',)).fetchall()
 def revenue(self):
  # Live daily total: completed invoices plus estimated current charges for open sessions.
  today=datetime.now().date()
  completed=sum(float(r['total'] or 0) for r in self.c.execute("SELECT end,total FROM sessions WHERE status='completed'") if r['end'] and datetime.fromtimestamp(r['end']).date()==today)
  live=0.0
  for r in self.active():
   if datetime.fromtimestamp(r['start']).date()==today:
    mins=max(1,int((self.elapsed(r)+59.999999)//60))
    live += max(mins*float(r['rate'])/60,float(r['minimum']))+float(r['drink_total'])
  return completed+live
 def reopen_day(self,username):
  day=datetime.now().date().isoformat()
  with self.c:self.c.execute('UPDATE day_closures SET reopened_at=?,reopened_by=? WHERE day=?',(time.time(),username,day))
  return day
 def reset_test_data(self):
  # Keep users, prices, units and drink catalog; clear only transactional/test data.
  with self.c:
   self.c.execute('DELETE FROM session_drinks')
   self.c.execute('DELETE FROM sessions')
   self.c.execute('DELETE FROM day_closures')
   self.c.execute("DELETE FROM sqlite_sequence WHERE name IN ('sessions','session_drinks')")
 def set_note(self,sid,note):
  with self.c:self.c.execute("UPDATE sessions SET notes=? WHERE id=? AND status IN ('active','paused')",(note.strip(),sid))
 def is_day_closed(self):
  day=datetime.now().date().isoformat()
  return bool(self.c.execute('SELECT 1 FROM day_closures WHERE day=? AND reopened_at IS NULL',(day,)).fetchone())
 def close_day(self,username):
  day=datetime.now().date().isoformat()
  rows=self.c.execute("SELECT end,total FROM sessions WHERE status='completed' AND end IS NOT NULL").fetchall()
  todays=[r for r in rows if datetime.fromtimestamp(r['end']).date().isoformat()==day]
  total=sum(float(r['total'] or 0) for r in todays)
  with self.c:self.c.execute("INSERT INTO day_closures(day,closed_at,username,total,invoice_count,reopened_at,reopened_by) VALUES(?,?,?,?,?,NULL,?) ON CONFLICT(day) DO UPDATE SET closed_at=excluded.closed_at,username=excluded.username,total=excluded.total,invoice_count=excluded.invoice_count,reopened_at=NULL,reopened_by=excluded.reopened_by",(day,time.time(),username,total,len(todays),''))
  return day,total,len(todays)
 def export_transfer_bundle(self,path):
  """Export completed invoices for safe offline transfer to the office/accountant app."""
  device_id=self.setting('device_id','unknown-device')
  sessions=self.c.execute("SELECT * FROM sessions WHERE status='completed' AND end IS NOT NULL ORDER BY end").fetchall()
  payload={'format':'XLINE_TRANSFER','version':1,'device_id':device_id,'device_name':socket.gethostname(),'exported_at':time.time(),'sessions':[],'closures':[]}
  for row in sessions:
   r=dict(row)
   r['source_key']=f"{device_id}:{r['id']}"
   r['items']=[dict(x) for x in self.session_drinks(r['id'])]
   payload['sessions'].append(r)
  for row in self.c.execute('SELECT * FROM day_closures ORDER BY day').fetchall():
   r=dict(row); r['source_key']=f"{device_id}:closure:{r['day']}"; payload['closures'].append(r)
  with open(path,'w',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
  return len(payload['sessions']),len(payload['closures']),device_id
 def period_bounds(self,period):
  now=datetime.now()
  if period=='يومي':start=now.replace(hour=0,minute=0,second=0,microsecond=0)
  elif period=='أسبوعي':start=(now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
  elif period=='شهري':start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
  else:return None,None
  return start.timestamp(),now.timestamp()


st.set_page_config(page_title="X-LINE Gaming Lounge", page_icon="🎮", layout="wide")
st.markdown("""
<style>
.stApp {background:#f3f5f8}
section[data-testid="stSidebar"] {background:#17191d}
section[data-testid="stSidebar"] * {color:#f4f5f7}
.xline-title {font-size:2.2rem;font-weight:900;color:#d71920;letter-spacing:1px}
.metric-card {background:white;border:1px solid #d9dee6;border-radius:12px;padding:16px}
div.stButton>button {border-radius:8px;font-weight:650}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_store():
    return Store()

s = get_store()
if "xline_user" not in st.session_state:
    st.session_state.xline_user = None
if "xline_lang" not in st.session_state:
    st.session_state.xline_lang = s.setting("language", "ar")
def tr(ar, en):
    return ar if st.session_state.xline_lang == "ar" else en
def fmt_money(v):
    return f"{float(v):,.0f} {'ل.س' if st.session_state.xline_lang == 'ar' else 'SYP'}"
def safe_action(fn):
    try:
        fn()
        st.rerun()
    except Exception as e:
        st.error(str(e))

if not st.session_state.xline_user:
    _, center, _ = st.columns([1,1.2,1])
    with center:
        st.markdown('<div class="xline-title">X-LINE</div>', unsafe_allow_html=True)
        st.subheader(tr("إدارة صالة الألعاب","GAMING LOUNGE MANAGEMENT"))
        with st.form("login_form"):
            username = st.text_input(tr("اسم المستخدم","Username"))
            password = st.text_input(tr("كلمة المرور","Password"), type="password")
            submitted = st.form_submit_button(tr("تسجيل الدخول","Sign in"), use_container_width=True)
        if submitted:
            user = s.login(username, password)
            if user:
                st.session_state.xline_user = dict(user)
                st.rerun()
            else:
                st.error(tr("اسم المستخدم أو كلمة المرور غير صحيحين.","Incorrect username or password."))
        st.caption(tr("المستخدم الافتراضي عند أول تشغيل: admin / admin123 — غيّر كلمة المرور فوراً.",
                      "First-run default: admin / admin123 — change the password immediately."))
    st.stop()

user = st.session_state.xline_user
is_admin = user["role"] == "admin"
with st.sidebar:
    st.markdown('<div class="xline-title">X-LINE</div>', unsafe_allow_html=True)
    st.caption("GAMING LOUNGE")
    page = st.radio(tr("القائمة","MENU"),
        [tr("لوحة التحكم","Dashboard"), tr("سجل الجلسات والتقارير","History & Reports"),
         tr("الإعدادات والأسعار والمشروبات","Settings, Rates & Drinks"),
         tr("المستخدمون","Users")], key="xline_page")
    lang = st.selectbox("Language / اللغة", ["العربية","English"],
                        index=0 if st.session_state.xline_lang=="ar" else 1)
    new_lang = "ar" if lang=="العربية" else "en"
    if new_lang != st.session_state.xline_lang:
        st.session_state.xline_lang = new_lang
        s.setsetting("language", new_lang)
        st.rerun()
    st.divider()
    st.write(tr(f"المستخدم: {user['username']}", f"User: {user['username']}"))
    st.caption("Developed by Eng.Amer Ameen Alfatwa")
    if st.button(tr("تسجيل الخروج","Sign out"), use_container_width=True):
        st.session_state.xline_user = None
        st.rerun()

if page == tr("لوحة التحكم","Dashboard"):
    st.title(tr("لوحة التحكم","Dashboard"))
    active = s.active()
    units = s.units()
    available = sum(1 for u in units if not s.active_unit(u["name"]))
    c1,c2,c3,c4 = st.columns(4)
    c1.metric(tr("إجمالي الوحدات","Total units"), len(units))
    c2.metric(tr("الوحدات المتاحة","Available units"), available)
    c3.metric(tr("الجلسات النشطة","Active sessions"), len(active))
    c4.metric(tr("إيرادات اليوم (تقديرية)","Today's revenue (estimate)"), fmt_money(s.revenue()))
    st.subheader(tr("وحدات اللعب","Gaming units"))
    cols = st.columns(4)
    for i, unit in enumerate(units):
        current = s.active_unit(unit["name"])
        with cols[i%4]:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown(f"**{unit['name']}**")
            st.caption(unit["model"])
            if current:
                elapsed = s.elapsed(current)
                mins = max(1, int((elapsed+59.999999)//60))
                charge = max(mins*float(current["rate"])/60, float(current["minimum"])) + float(current["drink_total"])
                st.warning(tr(f"مشغولة — {current['status']}", f"Occupied — {current['status']}"))
                st.write(tr("المدة: ","Duration: ")+dur(elapsed))
                st.write(tr("التكلفة الحالية: ","Current charge: ")+fmt_money(charge))
            else:
                st.success(tr("متاحة","Available"))
                if st.button(tr("بدء جلسة","Start session"), key=f"start_{unit['name']}", use_container_width=True):
                    try:
                        if s.is_day_closed():
                            st.error(tr("اليوم مغلق. افتحه أولاً من سجل الجلسات.","Business day is closed. Reopen it from History."))
                        else:
                            s.start(unit["name"], user["username"]); st.rerun()
                    except Exception as e: st.error(str(e))
            st.markdown('</div>', unsafe_allow_html=True)
    st.subheader(tr("الجلسات الحالية","Current sessions"))
    if not active:
        st.info(tr("لا توجد جلسات نشطة حالياً.","No active sessions."))
    for r in active:
        elapsed=s.elapsed(r); mins=max(1,int((elapsed+59.999999)//60))
        charge=max(mins*float(r["rate"])/60,float(r["minimum"]))+float(r["drink_total"])
        with st.expander(f"#{r['id']} · {r['unit_name']} · {r['username']} · {fmt_money(charge)}", expanded=True):
            a,b,c,d = st.columns([1,1,1,2])
            a.write(tr("الحالة: ","Status: ")+r["status"])
            b.write(tr("المدة: ","Duration: ")+dur(elapsed))
            c.write(tr("المشروبات: ","Drinks: ")+fmt_money(r["drink_total"]))
            with d:
                note=st.text_input(tr("ملاحظة","Note"),value=r["notes"] or "",key=f"note_{r['id']}")
                if st.button(tr("حفظ الملاحظة","Save note"),key=f"save_note_{r['id']}"):
                    s.set_note(r["id"],note); st.success(tr("تم الحفظ","Saved"))
            x,y,z = st.columns(3)
            if r["status"]=="active":
                if x.button(tr("إيقاف مؤقت","Pause"),key=f"pause_{r['id']}"):
                    safe_action(lambda:s.pause(r["id"]))
            else:
                if x.button(tr("استئناف","Resume"),key=f"resume_{r['id']}"):
                    safe_action(lambda:s.resume(r["id"]))
            with y:
                drinks=s.drinks()
                if drinks:
                    with st.popover(tr("إضافة مشروب","Add drink")):
                        drink_map={f"{d['name']} — {fmt_money(d['price'])}":d["id"] for d in drinks}
                        choice=st.selectbox(tr("المشروب","Drink"),list(drink_map),key=f"drink_{r['id']}")
                        qty=st.number_input(tr("الكمية","Quantity"),1,100,1,key=f"qty_{r['id']}")
                        if st.button(tr("إضافة","Add"),key=f"adddrink_{r['id']}"):
                            safe_action(lambda:s.attach_drink(r["id"],drink_map[choice],int(qty)))
                else: st.caption(tr("أضف المشروبات من الإعدادات","Add drinks in Settings"))
            if z.button(tr("إنهاء الجلسة وإصدار الفاتورة","Finish & invoice"),key=f"finish_{r['id']}", type="primary"):
                invoice=s.finish(r["id"])
                if invoice:
                    st.session_state["last_invoice"]=invoice
                    st.rerun()
    if st.session_state.get("last_invoice"):
        inv=st.session_state["last_invoice"]
        st.divider(); st.subheader(tr("آخر فاتورة","Latest invoice"))
        st.write(f"#{inv['id']} | {inv['unit']} | {stamp(inv['start'])} – {stamp(inv['end'])}")
        a,b,c,d=st.columns(4)
        a.metric(tr("اللعب","Play"),fmt_money(inv["play"]))
        b.metric(tr("المشروبات","Drinks"),fmt_money(inv["drinks"]))
        c.metric(tr("الإجمالي","Total"),fmt_money(inv["total"]))
        d.metric(tr("المدة بالدقائق","Minutes"),inv["minutes"])
        if st.button(tr("إخفاء الفاتورة","Dismiss invoice")):
            del st.session_state["last_invoice"]; st.rerun()

elif page == tr("سجل الجلسات والتقارير","History & Reports"):
    st.title(tr("سجل الجلسات والتقارير","History & Reports"))
    c1,c2=st.columns([2,1])
    query=c1.text_input(tr("البحث باسم وحدة اللعب","Search unit"))
    period=c2.selectbox(tr("الفترة","Period"),["يومي","أسبوعي","شهري","كل السجلات"] if st.session_state.xline_lang=="ar" else ["Daily","Weekly","Monthly","All records"])
    pmap={"Daily":"يومي","Weekly":"أسبوعي","Monthly":"شهري","All records":"كل السجلات"}
    period=pmap.get(period,period)
    rows=s.history(query)
    now=datetime.now()
    if period!="كل السجلات":
        if period=="يومي": start=now.replace(hour=0,minute=0,second=0,microsecond=0)
        elif period=="أسبوعي": start=(now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
        else: start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        rows=[r for r in rows if r["end"] and start.timestamp()<=float(r["end"])<=now.timestamp()]
    if rows:
        data=[{"ID":r["id"],tr("الوحدة","Unit"):r["unit_name"],tr("المستخدم","User"):r["username"],
               tr("البدء","Start"):stamp(r["start"]),tr("الانتهاء","End"):stamp(r["end"]),
               tr("المدة","Duration"):dur(r["elapsed"]),tr("المشروبات","Drinks"):float(r["drink_total"]),
               tr("الإجمالي","Total"):float(r["total"] or 0),tr("ملاحظات","Notes"):r["notes"]} for r in rows]
        st.dataframe(data,use_container_width=True,hide_index=True)
        st.metric(tr("عدد الفواتير","Invoice count"),len(rows))
        st.metric(tr("الإيرادات","Revenue"),fmt_money(sum(float(r["total"] or 0) for r in rows)))
        csv_data=io.StringIO()
        writer=csv.writer(csv_data); writer.writerow(list(data[0].keys()))
        for row in data: writer.writerow(list(row.values()))
        st.download_button(tr("تنزيل التقرير CSV","Download CSV report"),csv_data.getvalue().encode("utf-8-sig"),"xline_report.csv","text/csv")
    else: st.info(tr("لا توجد سجلات لهذه الفترة.","No records for this period."))
    st.divider()
    left,right=st.columns(2)
    with left:
        if is_admin:
            if st.button(tr("إغلاق اليوم وحفظ الإجمالي","Close business day"),type="primary"):
                day,total,count=s.close_day(user["username"])
                st.success(f"{day} | {tr('الفواتير','Invoices')}: {count} | {fmt_money(total)}")
            if st.button(tr("إعادة فتح اليوم","Reopen business day")):
                st.success(s.reopen_day(user["username"]))
        st.caption(tr("إغلاق اليوم يحفظ ملخص الفواتير المكتملة فقط.","Closing day stores a summary of completed invoices only."))
    with right:
        if st.button(tr("تصدير ملف نقل للمحاسب (JSON)","Export accountant transfer (JSON)")):
            path=APP_DIR/"xline_transfer.json"
            count,closures,device=s.export_transfer_bundle(path)
            st.download_button(tr("تنزيل ملف النقل","Download transfer file"),path.read_bytes(),"xline_transfer.json","application/json",key="download_transfer")
            st.success(f"{count} invoices · {closures} closures · {device}")
    if is_admin:
        with st.expander(tr("إعادة ضبط بيانات التجربة (تحذف الجلسات والفواتير)","Reset test data (deletes sessions/invoices)")):
            st.warning(tr("هذا الإجراء لا يمكن التراجع عنه.","This cannot be undone."))
            if st.checkbox(tr("أؤكد حذف بيانات المعاملات","I confirm deleting transaction data")):
                if st.button(tr("حذف بيانات التجربة","Delete test data")):
                    s.reset_test_data(); st.success(tr("تمت إعادة الضبط","Reset complete")); st.rerun()

elif page == tr("الإعدادات والأسعار والمشروبات","Settings, Rates & Drinks"):
    st.title(tr("الإعدادات والأسعار والمشروبات","Settings, Rates & Drinks"))
    if not is_admin:
        st.error(tr("هذه الصفحة للمدير فقط.","Admin only.")); st.stop()
    with st.form("rates_form"):
        st.subheader(tr("أسعار الساعة","Hourly rates"))
        rates={}
        labels=[("BILLIARDS","البلياردو / Billiards"),("PING PONG","تنس الطاولة / Ping pong"),("PS4","PlayStation 4"),("PS5","PlayStation 5")]
        cols=st.columns(2)
        for i,(key,label) in enumerate(labels):
            rates[key]=cols[i%2].number_input(label,min_value=0.0,value=float(s.setting("rate_"+key,str(DEFAULT_RATES[key]))),step=50.0,key=f"rate_{key}")
        minimum=st.number_input(tr("الحد الأدنى لكل جلسة","Minimum session charge"),min_value=0.0,value=float(s.setting("minimum","100")),step=10.0)
        if st.form_submit_button(tr("حفظ الأسعار","Save rates")):
            for k,v in rates.items(): s.setsetting("rate_"+k,v)
            s.setsetting("minimum",minimum); st.success(tr("تم حفظ الأسعار. الأسعار الجديدة تطبق على الجلسات الجديدة.","Rates saved; changes apply to new sessions."))
    st.divider(); st.subheader(tr("قائمة المشروبات","Drink catalog"))
    drinks=s.all_drinks()
    if drinks: st.dataframe([{"ID":d["id"],tr("الاسم","Name"):d["name"],tr("السعر","Price"):d["price"],tr("نشط","Active"):bool(d["active"])} for d in drinks],use_container_width=True,hide_index=True)
    with st.form("add_drink_form"):
        name=st.text_input(tr("اسم المشروب","Drink name"))
        price=st.number_input(tr("السعر","Price"),min_value=0.0,step=10.0)
        if st.form_submit_button(tr("إضافة مشروب","Add drink")):
            try: s.add_drink(name,price); st.success(tr("تمت الإضافة","Added")); st.rerun()
            except Exception as e: st.error(str(e))
    if drinks:
        ids={f"{d['id']} · {d['name']} ({'نشط' if d['active'] else 'غير نشط'})":d for d in drinks}
        selected=st.selectbox(tr("تعديل أو تعطيل مشروب","Edit or deactivate drink"),list(ids))
        d=ids[selected]
        with st.form("edit_drink_form"):
            nm=st.text_input(tr("الاسم","Name"),d["name"])
            pr=st.number_input(tr("السعر","Price"),min_value=0.0,value=float(d["price"]),step=10.0)
            a,b=st.columns(2)
            save=a.form_submit_button(tr("حفظ التعديل","Save changes"))
            deactivate=b.form_submit_button(tr("تعطيل المشروب","Deactivate"))
            if save:
                try:s.edit_drink(d["id"],nm,pr);st.success(tr("تم التحديث","Updated"));st.rerun()
                except Exception as e:st.error(str(e))
            if deactivate:
                s.delete_drink(d["id"]);st.success(tr("تم التعطيل","Deactivated"));st.rerun()

else:
    st.title(tr("إدارة المستخدمين","User management"))
    if not is_admin:
        st.error(tr("هذه الصفحة للمدير فقط.","Admin only.")); st.stop()
    users=s.users()
    if users:
        st.dataframe([{"ID":u["id"],tr("اسم المستخدم","Username"):u["username"],tr("الصلاحية","Role"):u["role"],tr("نشط","Active"):bool(u["active"])} for u in users],use_container_width=True,hide_index=True)
    with st.expander(tr("إضافة مستخدم","Add user"),expanded=True):
        with st.form("new_user"):
            uname=st.text_input(tr("اسم المستخدم","Username"),key="new_username")
            pw=st.text_input(tr("كلمة المرور","Password"),type="password",key="new_password")
            role=st.selectbox(tr("الصلاحية","Role"),["staff","admin"],format_func=lambda x:tr("موظف" if x=="staff" else "مدير","Staff" if x=="staff" else "Admin"))
            if st.form_submit_button(tr("إنشاء المستخدم","Create user")):
                try:s.save_user(uname,pw,role);st.success(tr("تم إنشاء المستخدم","User created"));st.rerun()
                except Exception as e:st.error(str(e))
    if users:
        usermap={f"{u['id']} · {u['username']}":u for u in users}
        chosen=st.selectbox(tr("إدارة حساب موجود","Manage existing account"),list(usermap))
        u=usermap[chosen]
        with st.form("manage_user"):
            newpw=st.text_input(tr("كلمة مرور جديدة (اختياري)","New password (optional)"),type="password")
            role2=st.selectbox(tr("الصلاحية","Role"),["staff","admin"],index=0 if u["role"]=="staff" else 1)
            active2=st.checkbox(tr("الحساب نشط","Account active"),value=bool(u["active"]))
            save=st.form_submit_button(tr("حفظ المستخدم","Save user"))
            if save:
                try:
                    s.save_user(u["username"],newpw,role2,u["id"]);s.set_user_active(u["id"],active2)
                    st.success(tr("تم حفظ المستخدم","User saved"));st.rerun()
                except Exception as e:st.error(str(e))
