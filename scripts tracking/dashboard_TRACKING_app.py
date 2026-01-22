import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# DATA LOAD
# ======================================================
def cargar_datos():
    try:
        conexion = crear_conexion()
        df = pd.read_sql("SELECT * FROM CMN_MASTER_MEX_CLEAN", conexion)
        conexion.close()
        return df
    except:
        return pd.read_csv("CMN_MASTER_MEX_CLEAN_preview.csv", dtype=str)

df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# ======================================================
# NORMALIZATION
# ======================================================
df.rename(columns={"type": "deposit_type", "usd": "usd_total"}, inplace=True, errors="ignore")

def convertir_fecha(v):
    try:
        s = str(v)
        return pd.to_datetime(s.split(" ")[0], errors="coerce")
    except:
        return pd.NaT

df["date"] = df["date"].apply(convertir_fecha)
df = df[df["date"].notna()]
df["date"] = df["date"].dt.tz_localize(None)

def limpiar_usd(v):
    if pd.isna(v): return 0.0
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

df["usd_total"] = df["usd_total"].apply(limpiar_usd)

for c in ["team", "agent", "country", "affiliate", "deposit_type", "id"]:
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip().str.title()

# ======================================================
# MONTH OPTIONS (FTD BASE)
# ======================================================
month_options = (
    df[df["deposit_type"].str.upper() == "FTD"]["date"]
    .dt.to_period("M")
    .astype(str)
    .unique()
)
month_options = sorted(month_options)

# ======================================================
# APP
# ======================================================
app = dash.Dash(__name__)
server = app.server

def card(title, value, money=False):
    val = f"${value:,.2f}" if money else f"{int(value):,}"
    return html.Div(
        [html.H4(title), html.H2(val)],
        style={
            "backgroundColor": "#1a1a1a",
            "padding": "20px",
            "borderRadius": "12px",
            "textAlign": "center",
            "boxShadow": "0 0 12px rgba(212,175,55,0.35)",
            "width": "220px",
        },
    )

# ======================================================
# LAYOUT
# ======================================================
app.layout = html.Div(
    style={"backgroundColor": "#0d0d0d", "padding": "20px"},
    children=[

        html.H1("📊 DASHBOARD DEPOSITS", style={"textAlign": "center", "color": "#D4AF37"}),

        html.Div(style={"display": "flex"}, children=[

            # FILTERS
            html.Div(style={"width": "25%", "padding": "20px"}, children=[

                html.H4("Month (FTD Base)"),
                dcc.Dropdown(
                    options=[{"label": pd.Period(m).strftime("%B %Y"), "value": m} for m in month_options],
                    id="filtro-month",
                    clearable=True
                ),

                html.H4("Date"),
                dcc.DatePickerRange(id="filtro-fecha"),

                html.H4("Team"),
                dcc.Dropdown(df["team"].dropna().unique(), multi=True, id="filtro-team"),

                html.H4("Agent"),
                dcc.Dropdown(df["agent"].dropna().unique(), multi=True, id="filtro-agent"),

                html.H4("ID"),
                dcc.Dropdown(df["id"].dropna().unique(), id="filtro-id"),

                html.H4("Affiliate"),
                dcc.Dropdown(df["affiliate"].dropna().unique(), multi=True, id="filtro-affiliate"),

                html.H4("Country"),
                dcc.Dropdown(df["country"].dropna().unique(), multi=True, id="filtro-country"),
            ]),

            # MAIN
            html.Div(style={"width": "72%"}, children=[

                html.Div(style={"display": "flex", "gap": "20px"}, children=[
                    html.Div(id="card-ftd"),
                    html.Div(id="card-total"),
                    html.Div(id="card-std"),
                    html.Div(id="card-amount"),
                ]),

                dash_table.DataTable(
                    id="tabla",
                    page_size=15,
                    style_cell={"backgroundColor": "#1a1a1a", "color": "white", "textAlign": "center"},
                    style_header={"backgroundColor": "#D4AF37", "color": "black"},
                ),
            ]),
        ]),
    ],
)

# ======================================================
# CALLBACK
# ======================================================
@app.callback(
    [
        Output("card-ftd", "children"),
        Output("card-total", "children"),
        Output("card-std", "children"),
        Output("card-amount", "children"),
        Output("tabla", "data"),
        Output("tabla", "columns"),
        Output("filtro-fecha", "start_date"),
        Output("filtro-fecha", "end_date"),
    ],
    [
        Input("filtro-month", "value"),
        Input("filtro-fecha", "end_date"),
        Input("filtro-team", "value"),
        Input("filtro-agent", "value"),
        Input("filtro-id", "value"),
        Input("filtro-affiliate", "value"),
        Input("filtro-country", "value"),
    ],
)
def update(month_sel, end_date, teams, agents, id_sel, affiliates, countries):

    dff = df.copy()

    # -------------------------------
    # MONTH LOGIC
    # -------------------------------
    if month_sel:
        period = pd.Period(month_sel)
        start = period.to_timestamp("M") - pd.offsets.MonthEnd(1) + pd.Timedelta(days=1)
        end = pd.to_datetime(end_date) if end_date else period.to_timestamp("M")

        # === FTD REAL POR ID (PRIMER FTD HISTÓRICO)
        ftd_real = (
            dff[dff["deposit_type"].str.upper() == "FTD"]
            .sort_values("date")
            .groupby("id", as_index=False)
            .first()
            .rename(columns={"date": "ftd_date"})
        )

        # === COHORTE DEL MES
        ftd_base = ftd_real[ftd_real["ftd_date"].dt.to_period("M") == period]
        base_ids = ftd_base[["id", "ftd_date"]]

        # === RTN POSTERIOR AL FTD (STD REAL)
        std_df = (
            dff[dff["deposit_type"].str.upper() == "RTN"]
            .merge(base_ids, on="id", how="inner")
            .query("date > ftd_date and date <= @end")
            .sort_values("date")
            .groupby("id", as_index=False)
            .first()
        )

        std_count = std_df.shape[0]
        total_deposits = std_count
        total_amount = std_df["usd_total"].sum()
        table = std_df

        ftds = ftd_base.shape[0]

    else:
        start = dff["date"].min()
        end = dff["date"].max()
        std_count = 0
        ftds = (dff["deposit_type"].str.upper() == "FTD").sum()
        total_deposits = len(dff)
        total_amount = dff["usd_total"].sum()
        table = dff

    # -------------------------------
    # EXTRA FILTERS
    # -------------------------------
    for col, val in [
        ("team", teams),
        ("agent", agents),
        ("affiliate", affiliates),
        ("country", countries),
    ]:
        if val:
            table = table[table[col].isin(val)]

    if id_sel:
        table = table[table["id"] == id_sel]

    table = table.copy()
    table["date"] = table["date"].dt.strftime("%Y-%m-%d")
    table["total_deposits"] = 1

    columns = [{"name": c.upper(), "id": c} for c in table.columns]

    return (
        card("FTD'S", ftds),
        card("TOTAL DEPOSITS", total_deposits),
        card("STD", std_count),
        card("TOTAL AMOUNT", total_amount, True),
        table.to_dict("records"),
        columns,
        start,
        end,
    )

    # === 9️⃣ Captura PDF/PPT desde iframe ===
app.index_string = '''
<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>OBL Digital — Dashboard FTD</title>
  {%favicon%}
  {%css%}
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
</head>
<body>
  {%app_entry%}
  <footer>
    {%config%}
    {%scripts%}
    {%renderer%}
  </footer>

  <script>
    window.addEventListener("message", async (event) => {
      if (!event.data || event.data.action !== "capture_dashboard") return;

      try {
        const canvas = await html2canvas(document.body, { useCORS: true, scale: 2, backgroundColor: "#0d0d0d" });
        const imgData = canvas.toDataURL("image/png");

        window.parent.postMessage({
          action: "capture_image",
          img: imgData,
          filetype: event.data.type
        }, "*");
      } catch (err) {
        console.error("Error al capturar dashboard:", err);
        window.parent.postMessage({ action: "capture_done" }, "*");
      }
    });
  </script>
</body>
</html>
'''

if __name__ == "__main__":
    app.run_server(debug=True, port=8053)


