"""CalibraUV — interfaz gráfica (Streamlit).

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from calibrauv import __version__
from calibrauv import graficos as G
from calibrauv.interpretacion import advertencias_muestras, evaluar
from calibrauv.motor import UNIDADES, absortividad_molar, calcular, motores_disponibles
from calibrauv.reporte import (AVISO_IA, reporte_html, tabla_anova, tabla_coeficientes,
                               tabla_muestras, tabla_puntos, tabla_resumen)

RAIZ = Path(__file__).resolve().parent
st.set_page_config(page_title="CalibraUV", page_icon="🧪", layout="wide")


@st.cache_data
def ejemplo():
    return (pd.read_csv(RAIZ / "datos" / "ejemplo_calibracion_hierro.csv"),
            pd.read_csv(RAIZ / "datos" / "ejemplo_muestras.csv"))


def leer_archivo(f) -> pd.DataFrame:
    if f.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    contenido = f.getvalue().decode("utf-8-sig", errors="replace")
    sep = ";" if contenido.count(";") > contenido.count(",") else ","
    from io import StringIO
    df = pd.read_csv(StringIO(contenido), sep=sep)
    if sep == ";":  # formato regional con coma decimal (Excel en español)
        for col in df.columns:
            conv = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")
            if conv.notna().all():
                df[col] = conv
    return df


# --------------------------------------------------------------- barra lateral
disp = motores_disponibles()
with st.sidebar:
    st.title("🧪 CalibraUV")
    st.caption(f"v{__version__} · Curva de calibración UV-Vis · Ley de Lambert-Beer")

    st.subheader("Método")
    analito = st.text_input("Analito", "Fe(II)–o-fenantrolina")
    lam = st.number_input("Longitud de onda λ (nm)", 190.0, 1100.0, 510.0, 1.0)
    unidad = st.selectbox("Unidad de concentración", list(UNIDADES), index=3)
    masa_molar = None
    if UNIDADES[unidad] is None:
        masa_molar = st.number_input("Masa molar (g/mol) para ε", 0.0, 1e6, 55.845, 0.001,
                                     format="%.3f", help="0 = no calcular ε molar")
    paso = st.number_input("Paso óptico l (cm)", 0.01, 10.0, 1.0, 0.1)

    st.subheader("Estadística")
    conf = st.select_slider("Nivel de confianza", [0.90, 0.95, 0.99], 0.95,
                            format_func=lambda v: f"{v:.0%}")
    origen = st.checkbox("Forzar por el origen (A = b·C)", False,
                         help="Solo si el intercepto no es significativo y el blanco está corregido.")
    opciones_motor = ["auto", "R", "Python"] if disp["R"] else ["Python"]
    motor = st.selectbox("Motor de cálculo", opciones_motor,
                         help="R (stats::lm) es el motor de referencia; Python es el respaldo.")
    if not disp["R"]:
        st.warning("R no encontrado: se usará Python. Instale R para usar stats::lm.")

    st.subheader("Gráficos")
    lib = st.radio("Biblioteca", ["Plotly (interactivo)", "Matplotlib + Seaborn", "Matplotlib",
                                  "Altair"], index=0)
    estilo = st.selectbox("Estilo Seaborn", ["whitegrid", "darkgrid", "ticks", "white"],
                          disabled=lib != "Matplotlib + Seaborn")
    st.divider()
    st.caption("🤖 " + AVISO_IA)

xlab = f"Concentración ({unidad})"

# ----------------------------------------------------------------- datos
st.header("Curva de calibración UV-Vis")
st.markdown(r"Ley de Lambert-Beer: $A = \varepsilon \, l \, c$ → regresión lineal "
            r"$A = a + b\,C$, donde $b = \varepsilon l$ es la sensibilidad.")

tab_datos, tab_res, tab_graf, tab_muest, tab_rep, tab_ia = st.tabs(
    ["📋 Datos", "📊 Estadísticos", "📈 Gráficos", "🧫 Muestras", "📄 Reporte", "🤖 IA y licencia"])

std_ej, unk_ej = ejemplo()
with tab_datos:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Estándares")
        f = st.file_uploader("CSV o Excel (columna 1: concentración, columna 2: absorbancia)",
                             type=["csv", "xlsx", "xls"], key="f_std")
        base = leer_archivo(f) if f else std_ej
        base = base.iloc[:, :2].copy()
        base.columns = ["Concentración", "Absorbancia"]
        estandares = st.data_editor(base, num_rows="dynamic", width="stretch", key="ed_std")
    with c2:
        st.subheader("Muestras problema (opcional)")
        f2 = st.file_uploader("CSV o Excel con columnas: muestra, absorbancia (réplicas en filas)",
                              type=["csv", "xlsx", "xls"], key="f_unk")
        base_u = leer_archivo(f2) if f2 else unk_ej
        base_u.columns = [c.lower().strip() for c in base_u.columns]
        muestras = st.data_editor(base_u[["muestra", "absorbancia"]], num_rows="dynamic",
                                  width="stretch", key="ed_unk")
    st.info("Consejo: mida cada estándar por triplicado para poder evaluar la falta de ajuste, "
            "y mantenga las absorbancias entre ~0.1 y 1.0.")

# -------------------------------------------------------------- cálculo
try:
    res = calcular(estandares.dropna(), muestras.dropna(), motor=motor, conf=conf,
                   origen=origen, paso_optico=paso)
except Exception as exc:  # noqa: BLE001
    st.error(f"No se pudo calcular la regresión: {exc}")
    st.stop()

if res.get("engine_note"):
    st.warning(res["engine_note"])
eps = absortividad_molar(res, unidad, masa_molar)

with tab_res:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("R²", f"{res['r_squared']:.5f}")
    m2.metric("Pendiente b", f"{res['coefficients']['slope']['estimate']:.5g}")
    m3.metric("s(y/x)", f"{res['s_yx']:.3g}")
    m4.metric(f"LOD ({unidad})", f"{res['lod']:.3g}")
    m5.metric(f"LOQ ({unidad})", f"{res['loq']:.3g}")
    st.markdown(f"**Ecuación:** `{G.ecuacion(res, 6)}`  ·  **Motor:** {res['engine']}")
    if eps is not None:
        st.markdown(f"**Absortividad molar ε** = {eps:,.0f} L·mol⁻¹·cm⁻¹ (a {lam:.0f} nm, l = {paso} cm)")

    a, b = st.columns([1, 1])
    with a:
        st.subheader("Resumen")
        st.dataframe(tabla_resumen(res, unidad, eps), hide_index=True, width="stretch")
    with b:
        st.subheader("Coeficientes")
        st.dataframe(tabla_coeficientes(res).style.format(precision=6), hide_index=True,
                     width="stretch")
        st.subheader("ANOVA")
        st.dataframe(tabla_anova(res).style.format(precision=6, na_rep=""), hide_index=True,
                     width="stretch")

    st.subheader("Evaluación de supuestos")
    icono = {"ok": "✅", "aviso": "⚠️", "mal": "❌", "info": "ℹ️"}
    for e in evaluar(res):
        st.markdown(f"{icono[e['estado']]} **{e['prueba']}** — {e['valor']}  \n{e['mensaje']}")

    with st.expander("Datos, residuales e influencia"):
        st.dataframe(tabla_puntos(res).style.format(precision=5), hide_index=True,
                     width="stretch")

fig_p = G.plotly_calibracion(res, xlab, titulo=f"{analito} · λ = {lam:.0f} nm")
fig_d = G.plotly_diagnostico(res, xlab)

with tab_graf:
    if lib.startswith("Plotly"):
        st.plotly_chart(fig_p, width="stretch")
        st.plotly_chart(fig_d, width="stretch")
    elif lib.startswith("Matplotlib"):
        usar_sns = "Seaborn" in lib
        f1 = G.mpl_calibracion(res, xlab, titulo=f"{analito} · λ = {lam:.0f} nm",
                               estilo_seaborn=estilo, usar_seaborn=usar_sns)
        f2 = G.mpl_diagnostico(res, xlab, estilo_seaborn=estilo, usar_seaborn=usar_sns)
        st.pyplot(f1)
        st.download_button("⬇️ Curva PNG (300 dpi)", G.fig_a_png(f1), "curva_calibracion.png",
                           "image/png")
        st.pyplot(f2)
        st.download_button("⬇️ Diagnóstico PNG (300 dpi)", G.fig_a_png(f2), "diagnostico.png",
                           "image/png")
    else:
        st.altair_chart(G.altair_calibracion(res, xlab), width="stretch")
        st.altair_chart(G.altair_residuales(res, xlab), width="stretch")

with tab_muest:
    tm = tabla_muestras(res, unidad)
    if tm.empty:
        st.info("Agregue absorbancias de muestras en la pestaña Datos.")
    else:
        st.markdown(r"Concentración por regresión inversa: $\hat C_0 = (\bar A_0 - a)/b$, con "
                    r"$s_{C_0} = \frac{s_{y/x}}{b}\sqrt{\frac1m + \frac1n + "
                    r"\frac{(\bar A_0-\bar A)^2}{b^2 S_{xx}}}$")
        st.dataframe(tm.style.format(precision=5, na_rep=""), hide_index=True,
                     width="stretch")
        for msg in advertencias_muestras(res):
            st.warning(msg)
        st.caption("Si diluyó la muestra, multiplique la concentración y su intervalo por el "
                   "factor de dilución.")

with tab_rep:
    meta = {"Analito": analito, "Longitud de onda (nm)": lam, "Paso óptico (cm)": paso,
            "unidad": unidad, "Nivel de confianza": f"{conf:.0%}",
            "Modelo": "A = b·C (por el origen)" if origen else "A = a + b·C"}
    html = reporte_html(res, meta, fig_p, fig_d, eps)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Reporte HTML", html, "reporte_calibracion.html", "text/html")
    c2.download_button("⬇️ Resultados JSON", json.dumps(res, indent=2, ensure_ascii=False),
                       "resultados.json", "application/json")
    c3.download_button("⬇️ Residuales CSV", tabla_puntos(res).to_csv(index=False),
                       "residuales.csv", "text/csv")
    st.caption("El reporte HTML incluye tablas, interpretación y gráficos interactivos; "
               "se puede imprimir a PDF desde el navegador.")

with tab_ia:
    st.subheader("Software libre")
    st.markdown("CalibraUV se distribuye bajo **licencia MIT**: puede usarla, estudiarla, "
                "modificarla y redistribuirla libremente.")
    st.subheader("Diseñada con apoyo de IA")
    st.markdown(AVISO_IA)
    pol = RAIZ / "POLITICA_USO_RESPONSABLE_IA.md"
    if pol.exists():
        with st.expander("Política de uso responsable de la IA", expanded=False):
            st.markdown(pol.read_text(encoding="utf-8"))
