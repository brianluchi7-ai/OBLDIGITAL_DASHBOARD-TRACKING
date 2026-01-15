import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — DEPOSITS (NEW BASE) ===
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
# LIMPIEZA USD (MISMA LÓGICA BUENA)
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
# FECHAS UI
# ========================
fecha_min, fecha_max = df["date"].min(), df["date"].max()

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
            html.H4(title, style={"color": "#D4AF37"}),
            html.H2(val, style={"color": "#FFF"})
        ],
        style={
            "backgroundColor": "#1a1a1a",
            "padding": "20px",
            "borderRadius": "10px",
            "textAlign": "center",
            "boxShadow": "0 0 10px rgba(212,175,55,0.3)",
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

            # === FILTROS ===
            html.Div(style={
                "width": "25%",
                "backgroundColor": "#1a1a1a",
                "padding": "20px",
                "borderRadius": "12px",
                "boxShadow": "0 0 15px rgba(212,175,55,0.3)",
                "textAlign": "center"
            }, children=[

                html.H4("Date", style={"color": "#D4AF37"}),
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    start_date=fecha_min,
                    end_date=fecha_max,
                    display_format="YYYY-MM-DD"
                ),

                html.H4("Team", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["team"].dropna().unique()), multi=True, id="filtro-team"),

                html.H4("Agent", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["agent"].dropna().unique()), multi=True, id="filtro-agent"),

                html.H4("ID", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["id"].dropna().unique()), multi=False, id="filtro-id"),

                html.H4("Affiliate", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["affiliate"].dropna().unique()), multi=True, id="filtro-affiliate"),

                html.H4("Country", style={"color": "#D4AF37"}),
                dcc.Dropdown(sorted(df["country"].dropna().unique()), multi=True, id="filtro-country"),
            ]),

            # === MAIN ===
            html.Div(style={"width": "72%"}, children=[

                html.Div(style={"display": "flex", "justifyContent": "space-around"}, children=[
                    html.Div(id="card-ftd"),
                    html.Div(id="card-total-deposits"),
                    html.Div(id="card-std"),
                    html.Div(id="card-total-amount"),
                ]),

                html.Br(),

                html.Div(style={"display": "flex", "flexWrap": "wrap"}, children=[
                    dcc.Graph(id="pie-country-deposits", style={"width": "48%"}),
                    dcc.Graph(id="pie-country-amount", style={"width": "48%"}),
                    dcc.Graph(id="pie-affiliate-deposits", style={"width": "48%"}),
                    dcc.Graph(id="pie-affiliate-amount", style={"width": "48%"}),
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
        Output("card-ftd", "children"),
        Output("card-total-deposits", "children"),
        Output("card-std", "children"),
        Output("card-total-amount", "children"),
        Output("pie-country-deposits", "figure"),
        Output("pie-country-amount", "figure"),
        Output("pie-affiliate-deposits", "figure"),
        Output("pie-affiliate-amount", "figure"),
        Output("tabla-detalle", "data"),
        Output("tabla-detalle", "columns"),
    ],
    [
        Input("filtro-fecha", "start_date"),
        Input("filtro-fecha", "end_date"),
        Input("filtro-team", "value"),
        Input("filtro-agent", "value"),
        Input("filtro-id", "value"),
        Input("filtro-affiliate", "value"),
        Input("filtro-country", "value"),
    ]
)
def actualizar_dashboard(start, end, teams, agents, id_sel, affiliates, countries):

    df_f = df.copy()

    if start and end:
        df_f = df_f[(df_f["date"] >= start) & (df_f["date"] <= end)]
    if teams:
        df_f = df_f[df_f["team"].isin(teams)]
    if agents:
        df_f = df_f[df_f["agent"].isin(agents)]
    if id_sel:
        df_f = df_f[df_f["id"] == id_sel]
    if affiliates:
        df_f = df_f[df_f["affiliate"].isin(affiliates)]
    if countries:
        df_f = df_f[df_f["country"].isin(countries)]

    df_f = df_f[df_f["usd_total"] > 0]

    ftds = (df_f["deposit_type"].str.upper() == "Ftd".upper()).sum()
    total_deposits = len(df_f)
    total_amount = df_f["usd_total"].sum()

    pie_country_dep = px.pie(df_f.groupby("country").size().reset_index(name="count"),
                             names="country", values="count")
    pie_country_amt = px.pie(df_f, names="country", values="usd_total")

    pie_aff_dep = px.pie(df_f.groupby("affiliate").size().reset_index(name="count"),
                         names="affiliate", values="count")
    pie_aff_amt = px.pie(df_f, names="affiliate", values="usd_total")

    for fig in [pie_country_dep, pie_country_amt, pie_aff_dep, pie_aff_amt]:
        fig.update_layout(paper_bgcolor="#0d0d0d", font_color="#f2f2f2")

    df_table = df_f.copy()
    df_table["date"] = df_table["date"].dt.strftime("%Y-%m-%d")
    df_table["total_deposits"] = 1

    df_table = df_table[
        ["date", "id", "agent", "team", "country", "affiliate", "usd_total", "total_deposits"]
    ]

    columns = [{"name": c.upper(), "id": c} for c in df_table.columns]

    return (
        card("FTD'S", ftds),
        card("TOTAL DEPOSITS", total_deposits),
        card("STD", 0),
        card("TOTAL AMOUNT", total_amount, True),
        pie_country_dep,
        pie_country_amt,
        pie_aff_dep,
        pie_aff_amt,
        df_table.to_dict("records"),
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





























