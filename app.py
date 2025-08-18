from flask import Flask, request, render_template, redirect, url_for, session
from datetime import datetime
import openpyxl, os, calendar, pandas as pd

app = Flask(__name__)
app.secret_key = "geheim123"
UPLOAD_FOLDER = 'uploads'

USERS = {
    "admin_sebastiano": {"password": "admin!2025", "role": "super", "restaurant": None},
    "La_Vita":          {"password": "1234",       "role": "input","restaurant": "Restaurant La Vita"},
    "La_Gioia":         {"password": "1234",       "role": "input","restaurant": "Restaurant La Gioia"},
    "Celina":           {"password": "1234",       "role": "input","restaurant": "Restaurant Celina"},
    "Lido":             {"password": "1234",       "role": "input","restaurant": "Restaurant Lido"},
    "Da_Vito":          {"password": "1234",       "role": "input","restaurant": "Restaurant da Vito"}
}

EXCEL_MAP = {
    "Restaurant La Vita": "umsatz_restaurant_la_vita.xlsx",
    "Restaurant La Gioia": "umsatz_restaurant_la_gioia.xlsx",
    "Restaurant Celina": "umsatz_restaurant_celina.xlsx",
    "Restaurant Lido": "umsatz_restaurant_lido.xlsx",
    "Restaurant da Vito": "umsatz_restaurant_da_vito.xlsx"
}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# LOGIN ------------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get("username")
        p = request.form.get("password")
        if u in USERS and USERS[u]["password"] == p:
            session['logged_in'] = True
            session['user'] = u
            session['role'] = USERS[u]["role"]
            session['restaurant'] = USERS[u]["restaurant"]
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Falscher Login")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# FORM ------------------------------------------------------------------------
@app.route('/form', methods=['GET','POST'])
def form():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user  = session.get("user")
    role  = session.get("role")
    rfix  = session.get("restaurant")

    restaurants = [rfix] if role=="input" else list(EXCEL_MAP.keys())

    if request.method == 'POST':
        rest = request.form["restaurant"]
        excel_file = EXCEL_MAP[rest]
        now = datetime.now()
        datum = now.strftime("%d.%m.%Y")
        zeit  = now.strftime("%H:%M")
        username = session.get("user")

        uf=['küche','wein','bier','mineral','heissgetränke','spirituosen','patisserie','anderes']
        pf=['bar','kartenterminal','twint','amex','debitoren','eatch','reka','sonstige']

        uv=[float(request.form.get(f) or 0) for f in uf]
        total=sum(uv)
        zv=[float(request.form.get(f) or 0) for f in pf]

        if round(sum(zv),2)!=round(total,2):
            return "Zahlungsarten stimmen nicht! <a href='/form'>Zurück</a>"

        files = request.files.getlist("fotos")
        c=1
        for f in files:
            if f and f.filename:
                name=f"{datum}_{zeit.replace(':','-')}_{c}_{rest.replace(' ','_')}.jpg"
                f.save(os.path.join(UPLOAD_FOLDER,name)); c+=1

        row=[datum,zeit]+uv+[total]+zv+[username]
        wb=openpyxl.load_workbook(excel_file); ws=wb.active
        ws.append(row); wb.save(excel_file)
        return redirect(url_for('dashboard'))

    return render_template('form.html',restaurants=restaurants,user=user)

# DASHBOARD -------------------------------------------------------------------
@app.route('/dashboard')
def dashboard():
    import pandas as pd
    import calendar

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user = session.get("user")
    role = session.get("role")

    filter = request.args.get("filter") or "monat"
    jahr   = request.args.get("jahr")   or datetime.now().strftime("%Y")

    # Standardmonat nur für Filter "monat"
    if filter == "monat":
        monat  = datetime.now().strftime("%m")
        start = f"01.{monat}.{jahr}"
        end   = f"31.{monat}.{jahr}"
    elif filter == "quartal1":
        start, end = f"01.01.{jahr}", f"31.03.{jahr}"
    elif filter == "quartal2":
        start, end = f"01.04.{jahr}", f"30.06.{jahr}"
    elif filter == "quartal3":
        start, end = f"01.07.{jahr}", f"30.09.{jahr}"
    elif filter == "quartal4":
        start, end = f"01.10.{jahr}", f"31.12.{jahr}"
    elif filter == "jahres":
        start, end = f"01.01.{jahr}", f"31.12.{jahr}"
    elif filter == "custom":
        start = request.args.get("start") or datetime.now().strftime("%d.%m.%Y")
        end   = request.args.get("end")   or datetime.now().strftime("%d.%m.%Y")

    stats = []
    last_entries = []
    monthly = {r: [0]*12 for r in EXCEL_MAP.keys()}

    for r, f in EXCEL_MAP.items():
        if role == "input" and session.get("restaurant") != r:
            continue
        if not os.path.exists(f):
            continue

        df = pd.read_excel(f)
        df['Datum'] = pd.to_datetime(df['Datum'], format="%d.%m.%Y")

        # Zeitraum-Summe
        mask = (df['Datum'] >= pd.to_datetime(start, dayfirst=True)) & (df['Datum'] <= pd.to_datetime(end, dayfirst=True))
        dfF  = df[mask]
        stats.append([r, round(dfF["Total-Umsatz"].sum(), 2) if not dfF.empty else 0])

        # Letzte Zeile
        if not df.empty:
            ls = df.sort_values("Datum", ascending=False).iloc[0]
            last_entries.append((r, ls["Datum"].strftime("%d.%m.%Y"), ls["Total-Umsatz"]))
        else:
            last_entries.append((r, "-", 0))

        # Monatswerte für Linienchart (immer bezogen auf ausgewähltes Jahr!)
        for m in range(1,13):
            start_m = f"01.{m:02d}.{jahr}"
            last_day = calendar.monthrange(int(jahr), m)[1]
            end_m = f"{last_day:02d}.{m:02d}.{jahr}"
            sub = df[(df['Datum']>=pd.to_datetime(start_m,dayfirst=True)) & (df['Datum']<=pd.to_datetime(end_m,dayfirst=True))]
            monthly[r][m-1] = round(sub["Total-Umsatz"].sum(),2) if not sub.empty else 0

    gesamt = sum([row[1] for row in stats])
    jahresliste = [str(y) for y in range(2023, 2031)]

    return render_template("dashboard.html",
                           user=user,
                           stats=stats,
                           gesamt=gesamt,
                           filter=filter,
                           jahr_selected=jahr,
                           start=start,
                           end=end,
                           jahre=jahresliste,
                           last_entries=last_entries,
                           monthly=monthly)

# -----------------------------------------------------------------------------
import os
port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
