@app.route("/dashboard")
def dashboard():
    import pandas as pd
    import calendar

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user = session.get("user")
    role = session.get("role")

    # -------- Filter einlesen --------
    filter_typ = request.args.get("filter") or "monat"
    jahr_str   = request.args.get("jahr")   or datetime.now().strftime("%Y")
    monat_str  = request.args.get("monat")  or datetime.now().strftime("%m")  # optionaler Query-Param

    try:
        jahr_int  = int(jahr_str)
    except Exception:
        jahr_int  = datetime.now().year
        jahr_str  = str(jahr_int)

    try:
        monat_int = int(monat_str)
    except Exception:
        monat_int = datetime.now().month
        monat_str = f"{monat_int:02d}"

    # -------- Start/End als Timestamp bestimmen --------
    def month_range(y: int, m: int):
        last_day = calendar.monthrange(y, m)[1]
        return (pd.Timestamp(year=y, month=m, day=1),
                pd.Timestamp(year=y, month=m, day=last_day))

    if filter_typ == "monat":
        start_dt, end_dt = month_range(jahr_int, monat_int)
    elif filter_typ == "jahres":
        start_dt = pd.Timestamp(year=jahr_int, month=1,  day=1)
        end_dt   = pd.Timestamp(year=jahr_int, month=12, day=31)
    elif filter_typ == "quartal1":
        start_dt = pd.Timestamp(jahr_int, 1, 1);  end_dt = pd.Timestamp(jahr_int, 3, 31)
    elif filter_typ == "quartal2":
        start_dt = pd.Timestamp(jahr_int, 4, 1);  end_dt = pd.Timestamp(jahr_int, 6, 30)
    elif filter_typ == "quartal3":
        start_dt = pd.Timestamp(jahr_int, 7, 1);  end_dt = pd.Timestamp(jahr_int, 9, 30)
    elif filter_typ == "quartal4":
        start_dt = pd.Timestamp(jahr_int,10, 1);  end_dt = pd.Timestamp(jahr_int,12,31)
    elif filter_typ == "custom":
        # erlaubt dd.mm.yyyy und yyyy-mm-dd
        def parse_user_date(s):
            if not s:
                return pd.NaT
            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
                try: return pd.to_datetime(s, format=fmt)
                except Exception: pass
            return pd.to_datetime(s, dayfirst=True, errors="coerce")
        start_dt = parse_user_date(request.args.get("start"))
        end_dt   = parse_user_date(request.args.get("end"))
        # Fallback, falls ungültig oder vertauscht
        if pd.isna(start_dt) or pd.isna(end_dt) or end_dt < start_dt:
            start_dt, end_dt = month_range(jahr_int, monat_int)
            filter_typ = "monat"
    else:
        start_dt, end_dt = month_range(jahr_int, monat_int)
        filter_typ = "monat"

    # -------- Daten laden & Datum robust parsen --------
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM umsatz", conn)
    conn.close()

    df["Datum"] = pd.to_datetime(df["datum"], format="%d.%m.%Y", errors="coerce")
    df = df.dropna(subset=["Datum"])

    # Strings nur für die Anzeige im Template
    start_str = start_dt.strftime("%d.%m.%Y")
    end_str   = end_dt.strftime("%d.%m.%Y")

    # -------- Auswertungen --------
    stats = []
    last_entries = []
    monthly = {r: [0.0]*12 for r in RESTAURANTS}

    restaurants_to_show = RESTAURANTS if role == "super" else [session.get("restaurant")]

    for r in restaurants_to_show:
        df_r = df[df["restaurant"] == r]

        # Zeitraum-Summe mit vorgeparsten Grenzen
        dfF = df_r[df_r["Datum"].between(start_dt, end_dt, inclusive="both")]
        total_summe = round(float(dfF["total"].sum()), 2) if not dfF.empty else 0.0
        stats.append([r, total_summe])

        # letzter Eintrag
        if not df_r.empty:
            l = df_r.sort_values("Datum", ascending=False).iloc[0]
            last_entries.append((r, l["datum"], float(l["total"])))
        else:
            last_entries.append((r, "-", 0.0))

        # Monatsentwicklung über das gewählte Jahr
        for m in range(1, 13):
            st_m, en_m = month_range(jahr_int, m)
            sub = df_r[df_r["Datum"].between(st_m, en_m, inclusive="both")]
            monthly[r][m-1] = round(float(sub["total"].sum()), 2) if not sub.empty else 0.0

    gesamt = round(sum(row[1] for row in stats), 2)
    jahresliste = [str(y) for y in range(2023, 2031)]

    return render_template(
        "dashboard.html",
        stats=stats,
        gesamt=gesamt,
        year=jahr_str,
        filter=filter_typ,
        jahre=jahresliste,
        jahr_selected=jahr_str,
        start=start_str,
        end=end_str,
        user=user,
        last_entries=last_entries,
        monthly=monthly
    )
