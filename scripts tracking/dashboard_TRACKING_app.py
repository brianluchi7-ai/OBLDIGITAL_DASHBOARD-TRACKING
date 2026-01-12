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
            query = "SELECT * FROM TRACKING_MEX_CLEAN"
            df = pd.read_sql(query, conexion)
            conexion.close()
            return df
    except Exception as e:
        print(f"SQL error, usando CSV: {e}")

    return pd.read_csv("TRACKING_MEX_preview.csv", dtype=str)


# === DATA LOAD ===
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# === NORMALIZATION ===
df["usd_total"] = df["usd_total"].apply(lambda x: float(re.sub(r"[^\d.-]", "", str(x))) if pd.notna(x) else 0)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df[df["date"].notna()]

for col in ["country", "affiliate", "team", "agent", "type"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.title()

fecha_min, fecha_max = df["date"].min(), df["date"].max()

# === APP INIT ===
app = dash.Dash(__name__)
server = app.server
app.title = "OBL Digital — Deposits Dashboard"

# === LAYOUT ===
app.layout = html.Div(
    style={"backgroundColor": "#0d0d0d", "padding": "20px"},
    children=[

        html.H1("📊 DASHBOARD DEPOSITS", style={
            "textAlign": "center", "color": "#D4AF37", "marginBottom": "30px"
        }),

        html.Div(style={"display": "flex"}, children=[

            # ===== FILTERS =====
            html.Div(style={
                "width": "25%", "backgroundColor": "#1a1a1a", "padding": "20px",
                "borderRadius": "12px", "boxShadow": "0 0 15px rgba(212,175,55,0.3)"
            }, children=[

                html.H4("Date", style={"color": "#D4AF37"}),
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    start_date=fecha_min,
                    end_date=fecha_max,
                    display_format="YYYY-MM-DD"
                ),

                html.H4("Team Leader", style={"color": "#D4AF37"}),
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

# === CALLBACK ===
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

    df_f = df.copy()

    if start and end:
        df_f = df_f[(df_f["date"] >= start) & (df_f["date"] <= end)]
    if teams:
        df_f = df_f[df_f["team"].isin(teams)]
    if agents:
        df_f = df_f[df_f["agent"].isin(agents)]
    if affiliates:
        df_f = df_f[df_f["affiliate"].isin(affiliates)]
    if countries:
        df_f = df_f[df_f["country"].isin(countries)]
    if id_sel:
        df_f = df_f[df_f["id"] == id_sel]

    total_deposits = len(df_f)
    total_amount = df_f["usd_total"].sum()

    ftd_amount = 0
    std_amount = 0

    if id_sel:
        df_ftd = df_f[df_f["type"] == "Ftd"].sort_values("date").head(1)
        if not df_ftd.empty:
            ftd_amount = df_ftd["usd_total"].iloc[0]
            ftd_date = df_ftd["date"].iloc[0]
            df_std = df_f[(df_f["type"] == "Rtn") & (df_f["date"] > ftd_date)].sort_values("date").head(1)
            if not df_std.empty:
                std_amount = df_std["usd_total"].iloc[0]

    def card(title, value):
        return html.Div([
            html.H4(title, style={"color": "#D4AF37"}),
            html.H2(f"${value:,.2f}", style={"color": "#FFF"})
        ], style={
            "backgroundColor": "#1a1a1a",
            "padding": "20px",
            "borderRadius": "10px",
            "textAlign": "center"
        })

    pie1 = px.pie(df_f, names="country", values="usd_total", title="Total Amount by Country")
    pie2 = px.pie(df_f.groupby("country").size().reset_index(name="count"),
                  names="country", values="count", title="Total Deposits by Country")
    pie3 = px.pie(df_f, names="affiliate", values="usd_total", title="Total Amount by Affiliate")
    pie4 = px.pie(df_f.groupby("affiliate").size().reset_index(name="count"),
                  names="affiliate", values="count", title="Total Deposits by Affiliate")

    for fig in [pie1, pie2, pie3, pie4]:
        fig.update_layout(paper_bgcolor="#0d0d0d", font_color="#f2f2f2")

    # === TABLE ===
    if id_sel:
        df_table = df_f.copy()
        df_table["total_deposits"] = 1
        df_table = df_table.groupby("date", as_index=False).agg({
            "country": "first",
            "affiliate": "first",
            "usd_total": "sum",
            "total_deposits": "sum"
        })
    else:
        df_table = df_f.groupby("date", as_index=False).agg({
            "country": "first",
            "affiliate": "first",
            "usd_total": "sum"
        })
        df_table["total_deposits"] = df_f.groupby("date").size().values

    columns = [
        {"name": "DATE", "id": "date"},
        {"name": "COUNTRY", "id": "country"},
        {"name": "AFFILIATE", "id": "affiliate"},
        {"name": "TOTAL AMOUNT", "id": "usd_total"},
        {"name": "TOTAL DEPOSITS", "id": "total_deposits"},
    ]

    df_table["date"] = df_table["date"].dt.strftime("%Y-%m-%d")

    return (
        card("TOTAL DEPOSITS", total_deposits),
        card("FTD", ftd_amount),
        card("STD", std_amount),
        card("TOTAL AMOUNT", total_amount),
        pie2, pie1, pie4, pie3,
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
