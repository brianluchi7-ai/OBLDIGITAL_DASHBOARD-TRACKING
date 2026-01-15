import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — DEPOSITS (FIX FINAL) ===
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
    return pd.read_csv("CMN_MASTER_MEX_preview.csv", dtype=str)

# ========================
# DATA LOAD
# ========================
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# ========================
# MISMA LIMPIEZA QUE COMISIONES
# ========================
def limpiar_usd(valor):
    if pd.isna(valor):
        return 0.0
    s = str(valor).strip()
    if s == "":
        return 0.0
    s = re.sub(r"[^\d,.\-]", "", s)
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        partes = s.split(",")
        s = s.replace(",", ".") if len(partes[-1]) == 2 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except:
        return 0.0

# === USD REAL ===
if "usd" in df.columns:
    df["usd"] = df["usd"].apply(limpiar_usd)
elif "usd_total" in df.columns:
    df["usd"] = df["usd_total"].apply(limpiar_usd)
else:
    df["usd"] = 0.0

# === FECHAS ===
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df[df["date"].notna()]

# === TEXTO LIMPIO ===
for col in ["country", "affiliate", "team", "agent", "id"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.title()

df["type"] = df.get("type", "").astype(str).str.upper()

# ========================
# FECHAS UI
# ========================
fecha_min = pd.Timestamp("2025-09-01")
fecha_max = df["date"].max()

# ========================
# DASH APP
# ========================
app = dash.Dash(__name__)
server = app.server
app.title = "OBL Digital — Deposits Dashboard"

def card(title, value, money=True):
    v = f"${value:,.2f}" if money else f"{int(value):,}"
    return html.Div(
        [
            html.H4(title, style={"color": "#D4AF37"}),
            html.H2(v, style={"color": "#FFF"})
        ],
        style={
            "backgroundColor": "#1a1a1a",
            "padding": "20px",
            "borderRadius": "10px",
            "textAlign": "center"
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
            "marginBottom": "30px"
        }),

        dcc.DatePickerRange(
            id="filtro-fecha",
            start_date=fecha_min,
            end_date=fecha_max,
            display_format="YYYY-MM-DD"
        ),

        html.Br(), html.Br(),

        html.Div(style={"display": "flex", "justifyContent": "space-around"}, children=[
            html.Div(id="card-total-deposits", style={"width": "22%"}),
            html.Div(id="card-ftd", style={"width": "22%"}),
            html.Div(id="card-std", style={"width": "22%"}),
            html.Div(id="card-total-amount", style={"width": "22%"}),
        ]),

        html.Br(),

        html.Div(style={"display": "flex", "flexWrap": "wrap"}, children=[
            dcc.Graph(id="pie-deposits-country", style={"width": "48%"}),
            dcc.Graph(id="pie-amount-country", style={"width": "48%"}),
            dcc.Graph(id="pie-deposits-affiliate", style={"width": "48%"}),
            dcc.Graph(id="pie-amount-affiliate", style={"width": "48%"}),
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
    ]
)

# ========================
# CALLBACK
# ========================
@app.callback(
    [
        Output("card-total-deposits", "children"),
        Output("card-ftd", "children"),
        Output("card-std", "children"),
        Output("card-total-amount", "children"),
        Output("pie-deposits-country", "figure"),
        Output("pie-amount-country", "figure"),
        Output("pie-deposits-affiliate", "figure"),
        Output("pie-amount-affiliate", "figure"),
        Output("tabla-detalle", "data"),
        Output("tabla-detalle", "columns"),
    ],
    [
        Input("filtro-fecha", "start_date"),
        Input("filtro-fecha", "end_date"),
    ]
)
def actualizar_dashboard(start, end):

    start = pd.to_datetime(start)
    end = pd.to_datetime(end) + pd.Timedelta(days=1)

    # 🔥 DATASET REAL
    df_calc = df[
        (df["date"] >= start) &
        (df["date"] < end) &
        (df["usd"] > 0)
    ].copy()

    # ========================
    # MÉTRICAS CORRECTAS
    # ========================
    total_amount = df_calc["usd"].sum()
    total_deposits = len(df_calc)

    # ========================
    # GRÁFICAS
    # ========================
    pie_dep_country = px.pie(
        df_calc.groupby("country").size().reset_index(name="count"),
        names="country", values="count"
    )
    pie_amt_country = px.pie(df_calc, names="country", values="usd")

    pie_dep_aff = px.pie(
        df_calc.groupby("affiliate").size().reset_index(name="count"),
        names="affiliate", values="count"
    )
    pie_amt_aff = px.pie(df_calc, names="affiliate", values="usd")

    for fig in [pie_dep_country, pie_amt_country, pie_dep_aff, pie_amt_aff]:
        fig.update_layout(paper_bgcolor="#0d0d0d", font_color="#f2f2f2")

    # ========================
    # TABLA
    # ========================
    df_table = df_calc.copy()
    df_table["date"] = df_table["date"].dt.strftime("%Y-%m-%d")
    df_table["total_amount"] = df_table["usd"]
    df_table["total_deposits"] = 1

    df_table = df_table[
        ["date", "id", "agent", "team", "country",
         "affiliate", "total_amount", "total_deposits"]
    ]

    columns = [{"name": c.upper(), "id": c} for c in df_table.columns]

    return (
        card("TOTAL DEPOSITS", total_deposits, False),
        card("FTD", 0, False),
        card("STD", 0, False),
        card("TOTAL AMOUNT", total_amount),
        pie_dep_country,
        pie_amt_country,
        pie_dep_aff,
        pie_amt_aff,
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




























