import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — DEPOSITS VIEW (Dark Gold)
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
# === DATA LOAD ==========
# ========================
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# ========================
# === NORMALIZATION ======
# ========================
if "usd_total" not in df.columns:
    for alt in ["usd", "total_amount", "amount", "deposit_amount"]:
        if alt in df.columns:
            df.rename(columns={alt: "usd_total"}, inplace=True)
            break

df["usd_total"] = df["usd_total"].apply(
    lambda x: float(re.sub(r"[^\d.-]", "", str(x))) if pd.notna(x) else 0
)

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df[df["date"].notna()]

df["id"] = df["id"].astype(str)

for col in ["country", "affiliate", "team", "agent"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.title()

df["type"] = df["type"].astype(str).str.strip().str.upper()

# =====================================================
# ✅ DATE_FTD REAL (primer depósito histórico por ID)
# =====================================================
df_first_deposit = (
    df.sort_values("date")
      .groupby("id", as_index=False)
      .first()[["id", "date"]]
      .rename(columns={"date": "date_ftd"})
)

df = df.merge(df_first_deposit, on="id", how="left")

fecha_min = pd.Timestamp("2025-09-01")
fecha_max = df["date"].max()

# ========================
# === APP INIT ===========
# ========================
app = dash.Dash(__name__)
server = app.server
app.title = "OBL Digital — Deposits Dashboard"

# ========================
# === UI HELPERS =========
# ========================
def filtro_titulo(texto):
    return html.H4(
        texto,
        style={
            "color": "#D4AF37",
            "textAlign": "center",
            "marginTop": "15px",
            "marginBottom": "5px"
        }
    )

def card(title, value, is_money=True):
    display_value = f"${value:,.2f}" if is_money else f"{int(value):,}"
    return html.Div([
        html.H4(title, style={"color": "#D4AF37"}),
        html.H2(display_value, style={"color": "#FFF"})
    ], style={
        "backgroundColor": "#1a1a1a",
        "padding": "20px",
        "borderRadius": "10px",
        "textAlign": "center"
    })

# ========================
# === LAYOUT =============
# ========================
app.layout = html.Div(
    style={
        "backgroundColor": "#0d0d0d",
        "color": "#000000",
        "fontFamily": "Arial",
        "padding": "20px"
    },
    children=[

        html.H1("📊 DASHBOARD DEPOSITS", style={
            "textAlign": "center",
            "color": "#D4AF37",
            "marginBottom": "30px"
        }),

        html.Div(style={"display": "flex"}, children=[

            # ===== FILTERS =====
            html.Div(style={
                "width": "25%",
                "backgroundColor": "#1a1a1a",
                "padding": "20px",
                "borderRadius": "12px",
                "boxShadow": "0 0 15px rgba(212,175,55,0.3)",
                "textAlign": "center"
            }, children=[

                filtro_titulo("Date"),
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    start_date=fecha_min,
                    end_date=fecha_max,
                    display_format="YYYY-MM-DD"
                ),

                filtro_titulo("Team Leader"),
                dcc.Dropdown(
                    sorted(df[df["type"] == "RTN"]["team"].dropna().unique()),
                    multi=True,
                    id="filtro-team"
                ),

                filtro_titulo("Agent"),
                dcc.Dropdown(
                    sorted(df[df["type"] == "RTN"]["agent"].dropna().unique()),
                    multi=True,
                    id="filtro-agent"
                ),

                filtro_titulo("ID"),
                dcc.Dropdown(
                    sorted(df["id"].dropna().unique()),
                    multi=False,
                    id="filtro-id"
                ),

                filtro_titulo("Affiliate"),
                dcc.Dropdown(
                    sorted(df["affiliate"].dropna().unique()),
                    multi=True,
                    id="filtro-affiliate"
                ),

                filtro_titulo("Country"),
                dcc.Dropdown(
                    sorted(df["country"].dropna().unique()),
                    multi=True,
                    id="filtro-country"
                ),
            ]),

            # ===== MAIN =====
            html.Div(style={"width": "72%"}, children=[

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
            ])
        ])
    ]
)

# ========================
# === CALLBACK ===========
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
        Input("filtro-team", "value"),
        Input("filtro-agent", "value"),
        Input("filtro-id", "value"),
        Input("filtro-affiliate", "value"),
        Input("filtro-country", "value"),
    ]
)
def actualizar_dashboard(start, end, teams, agents, id_sel, affiliates, countries):

    # 🔧 FIX CRÍTICO — evita NoneType error
    if start is None or end is None:
        start = fecha_min
        end = fecha_max + pd.Timedelta(days=1)
    else:
        start = pd.to_datetime(start).normalize()
        end = pd.to_datetime(end).normalize() + pd.Timedelta(days=1)

    # ======================
    # DATASET ÚNICO REAL
    # ======================
    df_calc = df.copy()
    df_calc = df_calc[(df_calc["date"] >= start) & (df_calc["date"] < end)]

    if affiliates:
        df_calc = df_calc[df_calc["affiliate"].isin(affiliates)]
    if countries:
        df_calc = df_calc[df_calc["country"].isin(countries)]
    if id_sel:
        df_calc = df_calc[df_calc["id"] == str(id_sel)]

    if teams:
        df_calc = df_calc[(df_calc["team"].isin(teams)) | (df_calc["type"] == "FTD")]
    if agents:
        df_calc = df_calc[(df_calc["agent"].isin(agents)) | (df_calc["type"] == "FTD")]

    # ======================
    # MÉTRICAS
    # ======================
    ftd_df = df_calc[df_calc["type"] == "FTD"]
    rtn_df = df_calc[df_calc["type"] == "RTN"]

    ftd_count = len(ftd_df)
    rtn_count = len(rtn_df)

    std_df = (
        rtn_df[rtn_df["date"] > rtn_df["date_ftd"]]
        .sort_values("date")
        .groupby("id", as_index=False)
        .first()
    )

    std_count = len(std_df)
    total_deposits = ftd_count + rtn_count
    total_amount = df_calc["usd_total"].sum()

    # ======================
    # CHARTS
    # ======================
    pie_deposits_country = px.pie(
        df_calc.groupby("country").size().reset_index(name="count"),
        names="country", values="count"
    )
    pie_amount_country = px.pie(df_calc, names="country", values="usd_total")
    pie_deposits_affiliate = px.pie(
        df_calc.groupby("affiliate").size().reset_index(name="count"),
        names="affiliate", values="count"
    )
    pie_amount_affiliate = px.pie(df_calc, names="affiliate", values="usd_total")

    for fig in [pie_deposits_country, pie_amount_country, pie_deposits_affiliate, pie_amount_affiliate]:
        fig.update_layout(paper_bgcolor="#0d0d0d", font_color="#f2f2f2")

    # ======================
    # TABLE
    # ======================
    df_table = df_calc.copy()
    df_table = df_table[
        (df_table["usd_total"] > 0) &
        (df_table["id"].notna()) &
        (df_table["agent"].notna()) &
        (df_table["team"].notna())
    ]

    df_table["date"] = df_table["date"].dt.strftime("%Y-%m-%d")
    df_table["date_ftd"] = df_table["date_ftd"].dt.strftime("%Y-%m-%d")
    df_table["total_amount"] = df_table["usd_total"]
    df_table["total_deposits"] = 1

    df_table = df_table[
        ["date", "id", "agent", "team", "country", "affiliate",
         "date_ftd", "total_amount", "total_deposits"]
    ]

    columns = [{"name": c.upper(), "id": c} for c in df_table.columns]

    return (
        card("TOTAL DEPOSITS", total_deposits, False),
        card("FTD", ftd_count, False),
        card("STD", std_count, False),
        card("TOTAL AMOUNT", total_amount),
        pie_deposits_country,
        pie_amount_country,
        pie_deposits_affiliate,
        pie_amount_affiliate,
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





















