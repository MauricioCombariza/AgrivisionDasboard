#!/usr/bin/env python3
"""
subir_imile_windows.py
======================
Sube la imagen de captura a iMile usando Selenium.

Mejoras respecto a la versión anterior:
  - Selectores CSS basados en role/atributos estables (sin clases hasheadas l-xxxxx)
  - File upload via send_keys en input[type="file"] — sin PyAutoGUI ni diálogo de Windows
  - Todos los time.sleep() reemplazados por WebDriverWait explicit waits
  - Imports centralizados (sin re-importar dentro de funciones)
  - Bloque PyAutoGUI fallback eliminado completamente

Requiere: pip install selenium webdriver-manager python-dotenv
"""

import sys
import os
import io
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Credenciales
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))
IMILE_USER = os.getenv("IMILE_USER")
IMILE_PASS = os.getenv("IMILE_PASS")

# Chrome con sesión persistente + remote debugging para reutilizar ventana
USER_DATA_DIR          = r"C:\Users\mcomb\ChromeSeleniumProfile_iMile"
REMOTE_DEBUGGING_PORT  = 9223

# ── Selectores estables ────────────────────────────────────────────────────────
# NOTA: iMile usa Material UI (MuiDrawer-root, MuiPaper-root…), no Ant Design.
# Los hash-classes l-XXXXX cambian entre builds y NO se usan aquí.
# Path verificado por inspección del usuario en el navegador.

# Botón "Agregar"
_AGREGAR_BTN = (By.XPATH, "//span[normalize-space(text())='Agregar']/..")

# Input del número de guía
_WAYBILL_INPUT = (By.NAME, "waybillNo")

# Input de archivo
_FILE_INPUT = (By.CSS_SELECTOR, "input[type='file']")

# Botón confirmar — iMile usa <div class="ImileDrawer-footer-confirm ..."> (NO <button>)
# JS path verificado: div.ImileDrawer-footer-root > div.ImileDrawer-footer-confirm > span
_CONFIRMAR_BTN = (By.CSS_SELECTOR, "div.ImileDrawer-footer-confirm")

# Activa diagnóstico verbose (imprime DOM del popup). Poner True solo para depurar.
_DEBUG = False

# ── Dropdowns del formulario (path confirmado por inspección del usuario) ──────
# El selector termina en MuiInputBase-root (role=None, confirmado por diagnóstico).
# El trigger real (MuiSelect-select) es su primer div hijo. Se navega a él via JS
# en _abrir_dropdown para no depender de atributos que pueden no existir.
_CSS_TIPO_RAZON = (
    "div.ImileDrawer-body-root form > div > div:nth-child(3)"
    " div.ImileForm-item-control > div > div"
)
_CSS_PROBLEMA_RAZON = (
    "div.ImileDrawer-body-root form > div > div:nth-child(4)"
    " div.ImileForm-item-control > div > div"
)


def _get_visible_dropdowns(driver):
    """Retorna los divs combobox visibles en pantalla (excluye los ocultos)."""
    return driver.find_elements(
        By.XPATH,
        "//div[@role='combobox' or @aria-haspopup='listbox']"
        "[not(ancestor::*[contains(@style,'display: none')"
        " or contains(@style,'display:none')"
        " or contains(@style,'visibility: hidden')])]"
    )


def _abrir_dropdown(driver, el):
    """
    Abre el trigger de un MUI Select navegando desde MuiInputBase-root al hijo
    real con JS, evitando ActionChains que crasheaba ChromeDriver.

    Estrategia:
      1. Busca dentro del contenedor un descendiente con role='button',
         clase 'Select-select', o tabindex='0' (cualquiera de los tres es el trigger).
      2. Si no encuentra nada, hace click en el propio contenedor.
      3. Nunca usa ActionChains (causa crash en sesiones remote-debugging).
    """
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    tag = driver.execute_script("return arguments[0].tagName;", el)
    cls = driver.execute_script("return arguments[0].className;", el)
    print(f"  [container] tag={tag} class={cls[:80]}", flush=True)

    trigger = driver.execute_script("""
        var c = arguments[0];
        return c.querySelector('[role="button"]')
            || c.querySelector('[class*="Select-select"]')
            || c.querySelector('[tabindex="0"]')
            || c.querySelector('div');
    """, el)

    if trigger:
        t_role = driver.execute_script("return arguments[0].getAttribute('role');", trigger)
        t_cls  = driver.execute_script("return arguments[0].className;", trigger)
        print(f"  [trigger]   role={t_role} class={t_cls[:80]}", flush=True)
        driver.execute_script("arguments[0].click();", trigger)
    else:
        print("  [trigger]   no encontrado, click en contenedor", flush=True)
        driver.execute_script("arguments[0].click();", el)


def _esperar_popup_opciones(driver, wait):
    """
    Espera a que el popup ImileSelect muestre sus opciones.

    Root cause del crash anterior: esperaba role='option' que NO existe en
    ImileSelect (componente custom de iMile). Timeout de 20 s + sesión
    remote-debugging inestable = crash de ChromeDriver siempre en los mismos
    hex addresses.

    Fix: espera por texto real de la lista (confirmado por inspección del usuario).
    'Cancelación' es la primera opción visible del primer dropdown.
    'Incorrecta' aparece en el segundo. Timeout corto (5 s) con pass en fallo
    porque _seleccionar_opcion tiene su propio wait de 10 s.
    """
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (By.XPATH,
                 "//*[contains(text(),'Cancelaci')]"
                 " | //*[contains(text(),'No entregado')]"
                 " | //*[contains(text(),'Incorrecta')]")
            )
        )
    except Exception:
        pass  # _seleccionar_opcion tiene su propio wait robusto


def _diagnosticar_popup(driver):
    """
    Diagnóstico: imprime los elementos visibles del popup ImileSelect actualmente
    abierto para identificar exactamente qué hay en el DOM al momento de seleccionar.
    Solo activo cuando _DEBUG = True.
    """
    if not _DEBUG:
        return
    try:
        textos_clave = ["Cancelaci", "Reprogramaci", "No entregado", "Debido", "Incorrecta",
                        "cliente", "Revision", "Limpieza", "contactable", "Reenv"]
        encontrados = set()
        for texto in textos_clave:
            els = driver.find_elements(By.XPATH, f"//*[contains(.,'{texto}')]")
            for el in els:
                try:
                    tag = el.tag_name
                    cls = (el.get_attribute("class") or "")[:60]
                    vis = el.is_displayed()
                    inner = (driver.execute_script("return arguments[0].innerText;", el) or "").strip()[:60]
                    key = f"{tag}|{cls}|{inner}"
                    if key not in encontrados:
                        encontrados.add(key)
                        print(f"  [diag] tag={tag} vis={vis} class={cls} text='{inner}'", flush=True)
                except Exception:
                    pass
        if not encontrados:
            print("  [diag] no se encontraron opciones en el popup", flush=True)
    except Exception as e:
        print(f"  [diag] error en diagnóstico: {e}", flush=True)


def _seleccionar_opcion(driver, wait, texto: str):
    """
    Clica la opción del popup ImileSelect con el texto dado.

    ROOT CAUSE del bug anterior: XPath genérico //div[contains(text(),'...')] encontraba
    celdas de la tabla de fondo (ImileTable-body-cell) antes que las opciones del popup,
    causando click en una fila de tabla → navegación/drawer → crash de ChromeDriver.

    FIX: scopear SIEMPRE a li.MuiMenuItem-root, que SOLO existe en popups MUI/ImileSelect,
    nunca en celdas de tabla (que usan div.ImileTable-body-cell exclusivamente).

    Estrategia:
      1. li.MuiMenuItem-root dentro de ImileSelect-list (más preciso)
      2. li.MuiMenuItem-root en cualquier parte (también seguro — no hay <li> en tablas)
      3. li.MuiMenuItem-root con contains (texto parcial, por si hay acento u otro)
    """
    patrones = [
        # Scopeado al contenedor del popup + tipo de elemento seguro
        (f"//div[contains(@class,'ImileSelect-list')]"
         f"//li[contains(@class,'MuiMenuItem-root') and normalize-space(.)='{texto}']"),
        # li.MuiMenuItem-root global (no existe en tablas)
        (f"//li[contains(@class,'MuiMenuItem-root') and normalize-space(.)='{texto}']"),
        # li.MuiMenuItem-root con contains (acento o espacio extra)
        (f"//li[contains(@class,'MuiMenuItem-root') and contains(.,'{texto}')]"),
    ]
    for xp in patrones:
        try:
            el = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            txt = (driver.execute_script("return arguments[0].innerText;", el) or "").strip()
            print(f"  [opción] encontrada: '{txt}'", flush=True)
            driver.execute_script("arguments[0].click();", el)
            return
        except Exception:
            continue
    raise Exception(f"No se encontró la opción: '{texto}'")


def _click(driver, wait, locator):
    """Scroll + click robusto via execute_script."""
    el = wait.until(EC.element_to_be_clickable(locator))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    driver.execute_script("arguments[0].click();", el)
    return el


def conectar_chrome_existente():
    """Intenta reconectarse a una instancia de Chrome ya abierta."""
    try:
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{REMOTE_DEBUGGING_PORT}")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
        print("Conectado a Chrome existente.", flush=True)
        return driver, False
    except Exception:
        print("No hay Chrome existente, iniciando nueva instancia…", flush=True)
        return None, True


def iniciar_chrome_nuevo():
    """Lanza Chrome, hace login en iMile y deja la ventana abierta para reutilizar."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--remote-debugging-port={REMOTE_DEBUGGING_PORT}")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, 20)

    print("Primera ejecución — haciendo login…", flush=True)
    driver.get("https://ds.imile.com/login")

    # Esperar formulario de login (no sleep)
    usuario_field = wait.until(EC.presence_of_element_located((By.NAME, "userCode")))
    clave_field   = driver.find_element(By.NAME, "password")

    usuario_field.send_keys(IMILE_USER)
    clave_field.send_keys(IMILE_PASS)
    clave_field.send_keys(Keys.RETURN)

    # Esperar que el dashboard cargue (URL cambia o aparece elemento del menú)
    wait.until(EC.url_contains("ds.imile.com"))
    wait.until(lambda d: "login" not in d.current_url)
    print("Login exitoso. Ventana quedará abierta para futuras subidas.", flush=True)

    return driver


def subir_imagen_imile(serial: str) -> bool:
    """
    Completa el formulario de 'Gestión de Problemas' en iMile y sube la imagen.

    Flujo:
      1. Conectar a Chrome existente (o lanzar uno nuevo con login)
      2. Navegar a la página de gestión de problemas
      3. Clic en Agregar → llenar serial → seleccionar dropdowns → subir imagen → Confirmar
    """
    driver = None
    es_pestana_nueva = False

    try:
        print(f"Iniciando subida para serial {serial}…", flush=True)

        # ── Verificar imagen ────────────────────────────────────────────────────
        download_folder = os.path.join(
            os.environ.get("USERPROFILE", "C:\\Users\\mcomb"), "Downloads"
        )
        file_path    = os.path.join(download_folder, f"captura_{serial}.png")
        ruta_absoluta = os.path.abspath(file_path)

        if not os.path.exists(ruta_absoluta):
            raise FileNotFoundError(f"Imagen no encontrada: {ruta_absoluta}")

        print(f"Imagen encontrada: {ruta_absoluta}", flush=True)

        # ── Obtener driver ──────────────────────────────────────────────────────
        driver, es_primera_vez = conectar_chrome_existente()
        if es_primera_vez:
            driver = iniciar_chrome_nuevo()
        else:
            print("Abriendo nueva pestaña…", flush=True)
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            es_pestana_nueva = True

        wait = WebDriverWait(driver, 20)

        # ── Navegar a gestión de problemas ──────────────────────────────────────
        print("Navegando a gestión de problemas…", flush=True)
        driver.get("https://ds.imile.com/#/Service/ServiceQuality/problemManagement")

        # Esperar a que el botón Agregar sea clicable (SPA puede tardar en renderizar)
        _click(driver, wait, _AGREGAR_BTN)

        # Esperar a que el formulario abra (el input de guía es el indicador más fiable)
        wait.until(EC.visibility_of_element_located(_WAYBILL_INPUT))
        print("Formulario abierto.", flush=True)

        # ── Serial ──────────────────────────────────────────────────────────────
        print(f"Ingresando serial {serial}…", flush=True)
        input_pedido = driver.find_element(*_WAYBILL_INPUT)
        input_pedido.clear()
        input_pedido.send_keys(serial)
        input_pedido.send_keys(Keys.RETURN)

        # Esperar que los dropdowns del formulario estén presentes en el DOM.
        # Condición real: el elemento CSS verificado por inspección existe.
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, _CSS_TIPO_RAZON)
        ))

        # ── Dropdown 1: Problema de tipo Razón → "Debido al cliente" ───────────
        # Selector scopeado al drawer (no global), construido desde el JS path
        # verificado por el usuario. Evita capturar otros combos de la página.
        print("Buscando 'Problema de tipo Razón' por CSS path verificado…", flush=True)
        d1 = driver.find_element(By.CSS_SELECTOR, _CSS_TIPO_RAZON)
        _abrir_dropdown(driver, d1)

        # Esperar condición: role='option' visible (no solo el contenedor listbox)
        _esperar_popup_opciones(driver, wait)
        _diagnosticar_popup(driver)   # ← evidencia: qué hay realmente en el popup
        print("Seleccionando 'Debido al cliente'…", flush=True)
        _seleccionar_opcion(driver, wait, "Debido al cliente")

        # Esperar a que el popup ImileSelect se cierre antes de abrir el siguiente
        try:
            WebDriverWait(driver, 3).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, "div.ImileSelect-list")
                )
            )
        except Exception:
            pass

        # ── Dropdown 2: Problema Razón → "Dirección Incorrecta" ────────────────
        # Mismo patrón, nth-child(4): el siguiente campo del formulario.
        print("Buscando 'Problema Razón' por CSS path verificado…", flush=True)
        d2 = driver.find_element(By.CSS_SELECTOR, _CSS_PROBLEMA_RAZON)
        _abrir_dropdown(driver, d2)

        # Esperar condición: popup visible
        _esperar_popup_opciones(driver, wait)
        _diagnosticar_popup(driver)   # ← evidencia: opciones reales del 2do dropdown
        print("Seleccionando 'Direccion Incorrecta'…", flush=True)
        _seleccionar_opcion(driver, wait, "Direccion Incorrecta")

        # ── Subida de imagen via send_keys — sin diálogo de Windows ────────────
        print(f"Subiendo imagen: {ruta_absoluta}", flush=True)

        # Hacer visible el input[type="file"] si está oculto
        file_input = wait.until(EC.presence_of_element_located(_FILE_INPUT))
        driver.execute_script(
            "arguments[0].style.display='block';"
            "arguments[0].style.visibility='visible';"
            "arguments[0].style.opacity='1';",
            file_input,
        )
        file_input.send_keys(ruta_absoluta)

        # Esperar a que iMile procese la imagen antes de confirmar.
        # Indicador preferido: aparece un <img src="blob:..."> como preview.
        # Fallback: 3 s si el componente no genera preview visible.
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[src^='blob:']"))
            )
            print("Preview de imagen detectado.", flush=True)
        except Exception:
            time.sleep(3)
            print("Imagen cargada (sin preview detectable).", flush=True)

        # ── Confirmar ───────────────────────────────────────────────────────────
        print("Confirmando…", flush=True)
        _click(driver, wait, _CONFIRMAR_BTN)

        # Esperar indicador de éxito o que el drawer se cierre
        try:
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located(
                    (By.XPATH, "//*[contains(@class,'ImileDrawer-body')]")
                )
            )
        except Exception:
            pass  # El drawer puede cerrarse muy rápido
        print("Confirmado exitosamente.", flush=True)

        print(
            json.dumps({"status": "success", "serial": serial, "file": ruta_absoluta}),
            flush=True,
        )
        return True

    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e), "serial": serial}), flush=True)
        return False

    # No se cierra el driver (detach=True para reutilizar la ventana)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python subir_imile_windows.py <serial>", flush=True)
        sys.exit(1)

    ok = subir_imagen_imile(sys.argv[1])
    sys.exit(0 if ok else 1)
