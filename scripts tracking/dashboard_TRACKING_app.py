import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — DEPOSITS (FINAL STD LOGIC)
# ======================================================

def cargar_datos():
    try:
        conexion = crear_conexion()
        if conexion:
            query = "SELECT * FROM CMN_MASTER_MEX_CLEAN"
            df = pd.read_sql(query, conexion)
            conexion.close()
            return df
    except Exception as e:
        print(f"⚠️ SQL error, usando CSV: {e}")
    return pd.read_csv("CMN_MASTER_MEX_CLEAN_preview.csv", dtype=str)

# ========================
# DATA LOAD
# ========================
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# ========================
# NORMALIZACIONES
# ========================
if "deposit_type" not in df.columns:
    df.rename(columns={"type": "deposit_type"}, inplace=True)

if "usd_total" not in df.columns:
    df.rename(columns={"usd": "usd_total"}, inplace=True)

# ========================
# FECHAS
# ========================
def convertir_fecha(valor):
    try:
        s = str(valor).strip()
        if "/" in s:
            return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
        return pd.to_datetime(s.split(" ")[0], errors="coerce")
    except:
        return pd.NaT

df["date"] = df["date"].astype(str).apply(convertir_fecha)
df = df[df["date"].notna()]
df["date"] = df["date"].dt.tz_localize(None)

# ========================
# LIMPIEZA USD
# ========================
def limpiar_usd(valor):
    if pd.isna(valor):
        return 0.0
    s = re.sub(r"[^\d,.\-]", "", str(valor))
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

df["usd_total"] = df["usd_total"].apply(limpiar_usd)

# ========================
# TEXTO LIMPIO
# ========================
for col in ["team", "agent", "country", "affiliate", "deposit_type", "id"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.title()
        df[col].replace({"Nan": None, "None": None, "": None}, inplace=True)

# ========================
# MONTH DATA
# ========================
df["month"] = df["date"].dt.to_period("M")
month_options = sorted(df["month"].astype(str).unique())

month_labels = {
    m: pd.Period(m).to_timestamp().strftime("%B %Y")
    for m in month_options
}

# ========================
# APP
# ========================
app = dash.Dash(__name__)
server = app.server
app.title = "OBL Digital — Deposits Dashboard"

def card(title, value, money=False):
    val = f"${value:,.2f}" if money else f"{int(value):,}"
    return html.Div(
        [
            html.H4(title, style={"color": "#D4AF37", "marginBottom": "10px"}),
            html.H2(val, style={"color": "#FFF"})
        ],
        style={
            "backgroundColor": "#1a1a1a",
            "padding": "20px",
            "borderRadius": "12px",
            "textAlign": "center",
            "boxShadow": "0 0 10px rgba(212,175,55,0.35)",
            "width": "220px",
            "minWidth": "220px"
        }
    )

# ========================
# LAYOUT
# ========================
app.layout = html.Div(
    style={"backgroundColor": "#0d0d0d", "padding": "20px"},
    children=[

        html.H1("📊 DASHBOARD DEPOSITS", style={
            "textAlign": "center",
            "color": "#D4AF37",
            "marginBottom": "30px",
            "fontWeight": "bold"
        }),

        html.Div(style={"display": "flex"}, children=[

            html.Div(style={
                "width": "25%",
                "backgroundColor": "#1a1a1a",
                "padding": "20px",
                "borderRadius": "12px",
                "boxShadow": "0 0 15px rgba(212,175,55,0.3)"
            }, children=[

                html.H4("Month (FTD Base)", style={"color": "#D4AF37"}),
                dcc.Dropdown(
                    options=[{"label": month_labels[m], "value": m} for m in month_options],
                    id="filtro-month",
                    placeholder="Select month"
                ),

                html.H4("Date", style={"color": "#D4AF37"}),
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    display_format="YYYY-MM-DD"
                ),

                html.H4("Team", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["team"].dropna().unique()), multi=True, id="filtro-team"),

                html.H4("Agent", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["agent"].dropna().unique()), multi=True, id="filtro-agent"),

                html.H4("ID", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["id"].dropna().unique()), id="filtro-id"),
            ]),

            html.Div(style={"width": "72%"}, children=[

                html.Div(style={"display": "flex", "gap": "20px"}, children=[
                    html.Div(id="card-ftd"),
                    html.Div(id="card-total-deposits"),
                    html.Div(id="card-std"),
                    html.Div(id="card-total-amount"),
                ]),

                html.Br(),

                dash_table.DataTable(
                    id="tabla-detalle",
                    page_size=15,
                    style_table={"overflowX": "auto"},
                    style_cell={
                        "backgroundColor": "#1a1a1a",
                        "color": "#f2f2f2",
                        "textAlign": "center"
                    },
                    style_header={
                        "backgroundColor": "#D4AF37",
                        "color": "#000",
                        "fontWeight": "bold"
                    },
                )
            ])
        ])
    ]
)

# ========================
# CALLBACK
# ========================
@app.callback(
    [
        Output("filtro-fecha", "start_date"),
        Output("filtro-fecha", "end_date"),
        Output("card-ftd", "children"),
        Output("card-total-deposits", "children"),
        Output("card-std", "children"),
        Output("card-total-amount", "children"),
        Output("tabla-detalle", "data"),
        Output("tabla-detalle", "columns"),
    ],
    [
        Input("filtro-month", "value"),
        Input("filtro-fecha", "end_date"),
        Input("filtro-team", "value"),
        Input("filtro-agent", "value"),
        Input("filtro-id", "value"),
    ]
)
def actualizar_dashboard(month_sel, end_date, teams, agents, id_sel):

    df_base = df.copy()

    if teams:
        df_base = df_base[df_base["team"].isin(teams)]
    if agents:
        df_base = df_base[df_base["agent"].isin(agents)]
    if id_sel:
        df_base = df_base[df_base["id"] == id_sel]

    std_count = 0
    df_table = pd.DataFrame()

    if month_sel:
        month_period = pd.Period(month_sel)
        start_date = month_period.start_time
        end_date = pd.to_datetime(end_date or month_period.end_time)

        ftd_ids = df_base[
            (df_base["deposit_type"].str.upper() == "FTD") &
            (df_base["month"] == month_period)
        ][["id", "date"]].rename(columns={"date": "ftd_date"})

        rtn = df_base[
            (df_base["deposit_type"].str.upper() == "RTN") &
            (df_base["date"] > ftd_ids["ftd_date"].min()) &
            (df_base["date"] <= end_date)
        ]

        std = ftd_ids.merge(rtn, on="id", how="inner")
        std = std[std["date"] > std["ftd_date"]]

        std = std.sort_values("date").drop_duplicates("id")
        std_count = len(std)

        df_table = std[["date", "id", "agent", "team", "country", "affiliate", "usd_total"]]
        total_deposits = len(std)
        total_amount = std["usd_total"].sum()
        ftds = len(ftd_ids)

    else:
        start_date = None
        end_date = None
        ftds = (df_base["deposit_type"].str.upper() == "FTD").sum()
        total_deposits = len(df_base)
        total_amount = df_base["usd_total"].sum()

    if not df_table.empty:
        df_table["date"] = df_table["date"].dt.strftime("%Y-%m-%d")
        df_table["total_deposits"] = 1
        columns = [{"name": c.upper(), "id": c} for c in df_table.columns]
        data = df_table.to_dict("records")
    else:
        columns = []
        data = []

    return (
        start_date,
        end_date,
        card("FTD'S", ftds),
        card("TOTAL DEPOSITS", total_deposits),
        card("STD", std_count),
        card("TOTAL AMOUNT", total_amount, True),
        data,
        columns
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
