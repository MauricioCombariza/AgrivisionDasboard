#!/usr/bin/env python3
"""
wa_captura_windows.py
=====================
Envía un mensaje por WhatsApp Web y captura la pantalla usando Selenium.
Reemplaza enviar_mensaje_windows.py + captura_imile_windows.py.

Ventajas sobre la versión anterior:
  - Sin coordenadas hardcodeadas: localiza el botón Enviar por selector
  - Sin time.sleep() fijos: usa WebDriverWait (explicit waits)
  - Screenshot via driver.save_screenshot() — solo la ventana del browser
  - Perfil Chrome persistente: la sesión de WA no expira entre ejecuciones

Uso:
    python wa_captura_windows.py <numero> <mensaje> <serial>

Requiere:
    pip install selenium webdriver-manager Pillow
"""

import sys
import os
import io
import json
import time
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image

# UTF-8 en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Configuración ─────────────────────────────────────────────────────────────
# Perfil Chrome separado para WhatsApp (persiste la sesión de WA Web)
WA_PROFILE = r"C:\Users\mcomb\ChromeSeleniumProfile_WhatsApp"

# Selectores de WhatsApp Web (con fallbacks por si cambia el DOM)
# Se intentan en orden dentro del mismo CSS selector (coma = OR)
_CHAT_INPUT = (
    By.CSS_SELECTOR,
    '[data-testid="conversation-compose-box-input"], '
    '[data-testid="msg-input"], '
    'div[contenteditable="true"][data-tab="10"]',
)
_SEND_BTN = (
    By.CSS_SELECTOR,
    '[data-testid="compose-btn-send"], '
    'button[aria-label="Enviar"], '
    'span[data-icon="send"]',
)
_MSG_SENT = (
    By.CSS_SELECTOR,
    'span[data-testid="msg-dblcheck"], '
    'span[data-icon="msg-check"], '
    'span[data-icon="msg-dblcheck"]',
)


def _build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={WA_PROFILE}")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option("detach", False)
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )


def enviar_y_capturar(numero: str, mensaje: str, serial: str,
                      output_dir: str | None = None) -> bool:
    """
    Abre WhatsApp Web, envía el mensaje y guarda un screenshot.

    Parámetros
    ----------
    numero     : teléfono destino (con o sin +)
    mensaje    : texto completo a enviar
    serial     : identificador del paquete (usado en el nombre del archivo)
    output_dir : carpeta donde guardar la captura (default: Descargas del usuario)

    Retorna True si todo fue exitoso, False en caso de error.
    """
    numero = str(numero).strip()
    if not numero.startswith("+"):
        numero = f"+{numero}"

    if output_dir is None:
        output_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\mcomb"), "Downloads")

    screenshot_path = os.path.join(output_dir, f"captura_{serial}.png")
    url = f"https://web.whatsapp.com/send?phone={numero}&text={quote(mensaje)}"

    driver = _build_driver()
    try:
        print(f"Abriendo WhatsApp para {numero}…", flush=True)
        driver.get(url)

        wait = WebDriverWait(driver, 60)  # hasta 60 s para que cargue WA Web

        # ── 1. Esperar que el campo de texto esté listo ───────────────────────
        print("Esperando carga de WhatsApp Web…", flush=True)
        wait.until(EC.presence_of_element_located(_CHAT_INPUT))
        print("WhatsApp listo.", flush=True)

        # ── 2. Localizar y hacer clic en el botón Enviar ─────────────────────
        send_btn = wait.until(EC.element_to_be_clickable(_SEND_BTN))
        driver.execute_script("arguments[0].click();", send_btn)
        print("Mensaje enviado.", flush=True)

        # ── 3. Esperar indicador de entrega al servidor ───────────────────────
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(_MSG_SENT)
            )
            print("Confirmación de entrega recibida.", flush=True)
        except Exception:
            # El check puede tardar si hay mala conexión; continuamos igual
            print("Aviso: no se detectó check de confirmación, capturando igual.", flush=True)

        # ── 4. Captura de pantalla via Selenium ───────────────────────────────
        driver.save_screenshot(screenshot_path)

        # ── 5. Recorte opcional: elimina la barra lateral de WA ───────────────
        try:
            img = Image.open(screenshot_path)
            w, h = img.size
            img.crop((700, 150, w, h - 70)).save(screenshot_path)
        except Exception as e:
            print(f"Aviso: no se pudo recortar la imagen: {e}", flush=True)

        print(
            json.dumps({"status": "success", "file": screenshot_path, "serial": serial}),
            flush=True,
        )
        return True

    except Exception as e:
        print(
            json.dumps({"status": "error", "error": str(e), "serial": serial}),
            flush=True,
        )
        return False

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Uso: python wa_captura_windows.py <numero> <mensaje> <serial>",
            flush=True,
        )
        sys.exit(1)

    ok = enviar_y_capturar(
        numero=sys.argv[1],
        mensaje=sys.argv[2],
        serial=sys.argv[3],
    )
    sys.exit(0 if ok else 1)
