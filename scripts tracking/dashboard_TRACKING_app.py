import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — DEPOSITS VIEW
# ======================================================

def cargar_datos():
    try:
        conexion = crear_conexion()
        if conexion:
            df = pd.read_sql("SELECT * FROM TRACKING_MEX_CLEAN", conexion)
            conexion.close()
            return df
    except Exception as e:
        print(f"SQL error, usando CSV: {e}")
    return pd.read_csv("TRACKING_MEX_preview.csv", dtype=str)

# ========================
# === DATA LOAD ==========
# ========================
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# ========================
# === NORMALIZATION ======
# ========================
if "usd_total" not in df.columns:
    for alt in ["usd", "amount", "total_amount", "deposit_amount"]:
        if alt in df.columns:
            df.rename(columns={alt: "usd_total"}, inplace=True)

df["usd_total"] = df["usd_total"].apply(
    lambda x: float(re.sub(r"[^\d.-]", "", str(x))) if pd.notna(x) else 0
)

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df[df["date"].notna()]

df["id"] = df["id"].astype(str)
df["type"] = df["type"].astype(str).str.upper()

for col in ["team", "agent", "country", "affiliate"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.title().str.strip()

# === DATE FTD ===
df_ftd = (
    df[df["type"] == "FTD"]
    .sort_values("date")
    .groupby("id", as_index=False)
    .first()[["id", "date"]]
    .rename(columns={"date": "date_ftd"})
)

df = df.merge(df_ftd, on="id", how="left")

fecha_min = pd.Timestamp("2025-09-01")
fecha_max = df["date"].max()

# ========================
# === APP INIT ===========
# ========================
app = dash.Dash(__name__)
server = app.server

# ========================
# === HELPERS ============
# ========================
def card(title, value, money=True):
    txt = f"${value:,.2f}" if money else f"{int(value):,}"
    return html.Div([
        html.H4(title, style={"color": "#D4AF37"}),
        html.H2(txt, style={"color": "#FFF"})
    ], style={
        "backgroundColor": "#1a1a1a",
        "padding": "20px",
        "borderRadius": "10px",
        "textAlign": "center"
    })

# ========================
# === LAYOUT =============
# ========================
app.layout = html.Div(style={"backgroundColor": "#0d0d0d", "padding": "20px"}, children=[

    html.H1("📊 DASHBOARD DEPOSITS", style={"color": "#D4AF37", "textAlign": "center"}),

    html.Div(style={"display": "flex"}, children=[

        # === FILTERS ===
        html.Div(style={
            "width": "25%", "backgroundColor": "#1a1a1a", "padding": "20px",
            "borderRadius": "12px", "textAlign": "center"
        }, children=[

            dcc.DatePickerRange(
                id="filtro-fecha",
                start_date=fecha_min,
                end_date=fecha_max,
                display_format="YYYY-MM-DD"
            ),

            dcc.Dropdown(sorted(df[df["type"]=="RTN"]["team"].dropna().unique()), multi=True, id="filtro-team"),
            dcc.Dropdown(sorted(df[df["type"]=="RTN"]["agent"].dropna().unique()), multi=True, id="filtro-agent"),
            dcc.Dropdown(sorted(df["id"].unique()), id="filtro-id"),
            dcc.Dropdown(sorted(df["affiliate"].unique()), multi=True, id="filtro-affiliate"),
            dcc.Dropdown(sorted(df["country"].unique()), multi=True, id="filtro-country"),
        ]),

        # === MAIN ===
        html.Div(style={"width": "72%"}, children=[

            html.Div(style={"display": "flex", "justifyContent": "space-around"}, children=[
                html.Div(id="card-total-deposits", style={"width": "22%"}),
                html.Div(id="card-ftd", style={"width": "22%"}),
                html.Div(id="card-std", style={"width": "22%"}),
                html.Div(id="card-total-amount", style={"width": "22%"}),
            ]),

            html.Br(),

            html.Div(style={"display": "flex", "flexWrap": "wrap"}, children=[
                dcc.Graph(id="pie-dep-country", style={"width": "48%"}),
                dcc.Graph(id="pie-amt-country", style={"width": "48%"}),
                dcc.Graph(id="pie-dep-aff", style={"width": "48%"}),
                dcc.Graph(id="pie-amt-aff", style={"width": "48%"}),
            ]),

            html.Br(),

            dash_table.DataTable(
                id="tabla",
                page_size=15,
                style_table={"overflowX": "auto"},
                style_cell={"backgroundColor": "#1a1a1a", "color": "#fff", "textAlign": "center"},
                style_header={"backgroundColor": "#D4AF37", "color": "#000"}
            )
        ])
    ])
])

# ========================
# === CALLBACK ===========
# ========================
@app.callback(
    [
        Output("card-total-deposits","children"),
        Output("card-ftd","children"),
        Output("card-std","children"),
        Output("card-total-amount","children"),
        Output("pie-dep-country","figure"),
        Output("pie-amt-country","figure"),
        Output("pie-dep-aff","figure"),
        Output("pie-amt-aff","figure"),
        Output("tabla","data"),
        Output("tabla","columns"),
    ],
    [
        Input("filtro-fecha","start_date"),
        Input("filtro-fecha","end_date"),
        Input("filtro-team","value"),
        Input("filtro-agent","value"),
        Input("filtro-id","value"),
        Input("filtro-affiliate","value"),
        Input("filtro-country","value"),
    ]
)
def update(start, end, teams, agents, id_sel, affiliates, countries):

    start = pd.to_datetime(start)
    end = pd.to_datetime(end) + pd.Timedelta(days=1)

    df_filtrado = df[(df["date"] >= start) & (df["date"] < end)]

    if affiliates:
        df_filtrado = df_filtrado[df_filtrado["affiliate"].isin(affiliates)]
    if countries:
        df_filtrado = df_filtrado[df_filtrado["country"].isin(countries)]
    if id_sel:
        df_filtrado = df_filtrado[df_filtrado["id"] == str(id_sel)]

    df_metrics = df_filtrado.copy()
    if teams:
        df_metrics = df_metrics[(df_metrics["team"].isin(teams)) & (df_metrics["type"]=="RTN")]
    if agents:
        df_metrics = df_metrics[(df_metrics["agent"].isin(agents)) & (df_metrics["type"]=="RTN")]

    total_dep = len(df_metrics)
    total_amt = df_metrics["usd_total"].sum()

    ftd = std = 0
    if id_sel:
        base = df[df["id"] == str(id_sel)]
        f = base[base["type"]=="FTD"].sort_values("date").head(1)
        if not f.empty:
            ftd = f["usd_total"].iloc[0]
            s = base[(base["type"]=="RTN") & (base["date"]>f["date"].iloc[0])].head(1)
            if not s.empty:
                std = s["usd_total"].iloc[0]

    def dark(fig):
        fig.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d", font_color="#fff")
        return fig

    fig1 = dark(px.pie(df_metrics.groupby("country").size().reset_index(name="count"), names="country", values="count"))
    fig2 = dark(px.pie(df_metrics, names="country", values="usd_total"))
    fig3 = dark(px.pie(df_metrics.groupby("affiliate").size().reset_index(name="count"), names="affiliate", values="count"))
    fig4 = dark(px.pie(df_metrics, names="affiliate", values="usd_total"))

    df_table = df_filtrado.groupby(
        ["date","id","agent","team","country","affiliate","date_ftd"],
        as_index=False
    ).agg(
        total_amount=("usd_total","sum"),
        total_deposits=("usd_total","count")
    )

    df_table["date"] = df_table["date"].dt.strftime("%Y-%m-%d")
    df_table["date_ftd"] = df_table["date_ftd"].dt.strftime("%Y-%m-%d")

    cols = [{"name": c.upper(), "id": c} for c in df_table.columns]

    return (
        card("TOTAL DEPOSITS", total_dep, False),
        card("FTD", ftd),
        card("STD", std),
        card("TOTAL AMOUNT", total_amt),
        fig1, fig2, fig3, fig4,
        df_table.to_dict("records"),
        cols
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







