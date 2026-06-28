import os
import streamlit as st
import pandas as pd
import time
from playwright.sync_api import sync_playwright

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore (Auto-Update)")
st.subheader("Análisis de métricas en tiempo real con actualización automática cada 60 segundos")

def extraer_estadisticas_partido(context, url_partido):
    """Abre una pestaña nueva, extrae la info de forma ultra rápida y la cierra para liberar RAM."""
    datos_partido = {
        "Marcador": "- - -",
        "Tiempo/Estado": "-",
        "Minuto": "-",
        "Stats": {}
    }
    page = None
    try:
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "font", "stylesheet"] else route.continue_())
        
        page.goto(url_partido, timeout=7000, wait_until="domcontentloaded")
        page.wait_for_selector("div.detailScore__wrapper", timeout=4000)
        
        marcador_el = page.locator("div.detailScore__wrapper").first
        if marcador_el.count() > 0:
            datos_partido["Marcador"] = marcador_el.text_content(timeout=500).strip()
            
        estado_el = page.locator("span.fixedHeaderDuel__detailStatus").first
        if estado_el.count() > 0:
            datos_partido["Tiempo/Estado"] = estado_el.text_content(timeout=500).strip()
            
        minuto_el = page.locator("span.eventTime").first
        if minuto_el.count() > 0:
            datos_partido["Minuto"] = minuto_el.text_content(timeout=500).strip()
            
        boton_stats = page.locator("//button[@role='tab' and contains(., 'Estadísticas')]").first
        if boton_stats.count() > 0:
            boton_stats.click(timeout=1000)
            page.wait_for_selector("div[data-testid='wcl-statistics']", timeout=2000)
            
            filas = page.locator("div[data-testid='wcl-statistics']").all()
            for fila in filas:
                cat_el = fila.locator("div[data-testid='wcl-statistics-category']").first
                if cat_el.count() > 0:
                    categoria = cat_el.text_content().strip()
                    
                    home_el = fila.locator("div[class*='wcl-homeValue']").first
                    away_el = fila.locator("div[class*='wcl-awayValue']").first
                    
                    val_home = home_el.text_content().strip() if home_el.count() > 0 else "0"
                    val_away = away_el.text_content().strip() if away_el.count() > 0 else "0"
                    
                    datos_partido["Stats"][f"{categoria} (L)"] = val_home
                    datos_partido["Stats"][f"{categoria} (V)"] = val_away
    except Exception:
        pass
    finally:
        if page:
            page.close()
            
    return datos_partido

# --- COMPONENTE DE ACTUALIZACIÓN AUTOMÁTICA (FRAGMENT) ---

@st.fragment
def contenedor_monitoreo_vivo():
    """Este bloque se ejecuta de forma independiente y se auto-refresca cada 60 segundos."""
    
    # Marcador de tiempo de la última actualización
    st.caption(f"🔄 Última actualización del sistema: **{time.strftime('%H:%M:%S')}** (Se actualiza solo cada 1 min)")
    
    # Contenedor dinámico para mostrar el estado actual del escaneo
    estado_placeholder = st.empty()
    barra_placeholder = st.empty()
    tabla_placeholder = st.empty()

    estado_placeholder.info("Iniciando escaneo de partidos en directo...")
    
    with sync_playwright() as p:
        browser = None
        context = None
        try:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            
            main_page = context.new_page()
            main_page.goto("https://www.flashscore.pe/", wait_until="domcontentloaded")
            
            boton_directo = main_page.locator("//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
            boton_directo.wait_for(state="visible", timeout=10000)
            boton_directo.click()
            
            time.sleep(2.5)
            
            partidos_elementos = main_page.locator("div[id^='g_1_']").all()
            
            if not partidos_elementos:
                estado_placeholder.warning("No se encontraron partidos en directo activos en este momento.")
            else:
                estado_placeholder.success(f"Analizando {len(partidos_elementos)} partidos activos...")
                
                barra_progreso = barra_placeholder.progress(0)
                lista_registros_finales = []
                
                for idx, fila in enumerate(partidos_elementos):
                    id_completo = fila.get_attribute("id")
                    id_partido = id_completo.split('_')[-1]
                    url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                    
                    local_el = fila.locator("div[class*='home'][class*='participant']").first
                    away_el = fila.locator("div[class*='away'][class*='participant']").first
                    
                    nom_local = local_el.text_content().strip() if local_el.count() > 0 else "Local"
                    nom_visitante = away_el.text_content().strip() if away_el.count() > 0 else "Visitante"
                    
                    resultado_profundo = extraer_estadisticas_partido(context, url_match_stats)
                    
                    registro = {
                        "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                        "Marcador": resultado_profundo["Marcador"],
                        "Tiempo/Estado": resultado_profundo["Tiempo/Estado"],
                        "Minuto": resultado_profundo["Minuto"]
                    }
                    registro.update(resultado_profundo["Stats"])
                    lista_registros_finales.append(registro)
                    
                    barra_progreso.progress((idx + 1) / len(partidos_elementos))
                
                # Limpiar los elementos visuales de carga una vez finalizado
                barra_placeholder.empty()
                estado_placeholder.empty()
                
                # Renderizar tabla finalizada
                df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto"]
                columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
                df_final = df_final[columnas_fijas + columnas_stats]
                
                tabla_placeholder.dataframe(df_final, use_container_width=True)
                
        except Exception as e:
            estado_placeholder.error(f"Error en la iteración actual: {str(e)}")
        finally:
            if context:
                context.close()
            if browser:
                browser.close()

    # Este comando fuerza a este fragmento específico a volver a ejecutarse tras 60 segundos
    time.sleep(60)
    st.rerun()

# --- FLUJO PRINCIPAL ---

# Garantizar la instalación de dependencias una sola vez al arrancar la app globalmente
if 'navegador_listo' not in st.session_state:
    with st.spinner("Preparando entorno de Playwright en la nube (Solo la primera vez)..."):
        os.system("playwright install chromium --with-deps")
    st.session_state['navegador_listo'] = True

st.write("### 📈 Cuadro de Control General (Actualización Automática)")

# Inicializamos el fragmento automatizado
contenedor_monitoreo_vivo()
