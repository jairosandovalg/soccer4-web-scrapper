import streamlit as st
import pandas as pd
import time
import cloudscraper
import re

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore (Ultra-Light)")
st.subheader("Análisis de métricas en tiempo real con actualización automática cada 60 segundos")

def extraer_datos_api_flashscore():
    """Obtiene los partidos en directo y sus métricas directamente simulando las peticiones del navegador."""
    lista_registros_finales = []
    
    # Creamos un scraper que evade las protecciones básicas de Cloudflare de forma ligera
    scraper = cloudscraper.create_scraper()
    
    try:
        # 1. Obtenemos el feed principal en vivo de la versión móvil (más ligera y rápida de procesar)
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "X-Fsn": "f"
        }
        
        # URL del feed interno de partidos en vivo de Flashscore Perú
        url_feed = "https://m.flashscore.pe/x/feed/d_live_1_pe_1"
        respuesta = scraper.get(url_feed, headers=headers, timeout=8)
        
        if respuesta.status_code != 200:
            return None, f"Error de conexión con el servidor deportivo (Status {respuesta.status_code})"
            
        texto_feed = respuesta.text
        
        # Separamos el texto por bloques de partidos usando los delimitadores nativos de su API (~AA)
        bloques_partidos = texto_feed.split("~AA÷")
        
        partidos_activos = []
        for bloque in bloques_partidos[1:]:  # Ignoramos la cabecera
            lineas = bloque.split("~")
            datos = {}
            for linea in lineas:
                if "÷" in linea:
                    clave, valor = linea.split("÷", 1)
                    datos[clave] = valor
            partidos_activos.append(datos)
            
        if not partidos_activos:
            return [], None

        # Procesamos un máximo de 15 partidos concurrentes para no saturar y mantener la velocidad top
        partidos_a_procesar = partidos_activos[:15]
        
        for idx, part in enumerate(partidos_a_procesar):
            id_partido = part.get("ID", "")
            if not id_partido:
                continue
                
            nom_local = part.get("AE", "Local")
            nom_visitante = part.get("AF", "Visitante")
            marcador_local = part.get("AG", "0")
            marcador_visitante = part.get("AH", "0")
            estado_tiempo = part.get("AC", "-") # Ej: "1er Tiempo", "Descanso"
            minuto_actual = part.get("AD", "-") # Ej: "35"
            
            # Limpieza de strings
            if estado_tiempo == "45": estado_tiempo = "Descanso"
            if estado_tiempo == "1": estado_tiempo = "1er Tiempo"
            if estado_tiempo == "2": estado_tiempo = "2do Tiempo"
            
            # Inicializamos el registro base del encuentro
            registro = {
                "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                "Marcador": f"{marcador_local} - {marcador_visitante}",
                "Tiempo/Estado": estado_tiempo,
                "Minuto": f"{minuto_actual}'" if minuto_actual.isdigit() else minuto_actual
            }
            
            # 2. Consultamos de forma asíncrona y directa las estadísticas numéricas de este ID
            url_stats = f"https://local-pe.flashscore.ninja/x/feed/d_su_{id_partido}_es_1"
            res_stats = scraper.get(url_stats, headers=headers, timeout=4)
            
            if res_stats.status_code == 200 and "wcl-statistics" in res_stats.text:
                # Expresión regular veloz para capturar categorías y valores numéricos del feed crudo
                # Evita usar costosos parsers visuales
                matches = re.findall(r'wcl-statistics-category.*?>(.*?)<.*?wcl-homeValue.*?>(.*?)<.*?wcl-awayValue.*?>(.*?)</', res_stats.text)
                for cat, home_val, away_val in matches:
                    registro[f"{cat} (L)"] = home_val.strip()
                    registro[f"{cat} (V)"] = away_val.strip()
            
            lista_registros_finales.append(registro)
            
        return lista_registros_finales, None
        
    except Exception as e:
        return None, str(e)

# --- COMPONENTE DE ACTUALIZACIÓN AUTOMÁTICA (FRAGMENT) ---
@st.fragment
def contenedor_monitoreo_vivo():
    """Bloque aislado que se refresca de forma automática cada 60 segundos por peticiones HTTP."""
    st.caption(f"🔄 Última actualización del sistema: **{time.strftime('%H:%M:%S')}** (Próximo escaneo automático en 1 min)")
    
    estado_placeholder = st.empty()
    tabla_placeholder = st.empty()

    estado_placeholder.info("Extrayendo métricas en tiempo real directamente desde el Feed...")
    
    # Ejecutamos la consulta directa a los servidores de datos
    datos, error = extraer_datos_api_flashscore()
    
    if error:
        estado_placeholder.error(f"Error en la iteración actual: {error}")
    elif not datos:
        estado_placeholder.warning("No se detectaron partidos en directo activos en este momento.")
    else:
        estado_placeholder.empty() # Limpiamos el aviso de carga inmediatamente
        
        # Estructuración final de la tabla en Pandas
        df_final = pd.DataFrame(datos).fillna("-")
        columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto"]
        
        # Ordenamos dejando las estadísticas hacia la derecha
        columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
        df_final = df_final[columnas_fijas + columnas_stats]
        
        tabla_placeholder.dataframe(df_final, use_container_width=True)

    # Pausa de un minuto y recarga automática del fragmento
    time.sleep(60)
    st.rerun()

# --- RENDERIZADO PRINCIPAL ---
st.write("### 📈 Cuadro de Control General (Actualización Automática)")
contenedor_monitoreo_vivo()
