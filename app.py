#!/usr/bin/env python3
from flask import Flask, request, jsonify
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

app = Flask(__name__)

# =======================
# CREDENCIALES DEL SITIO
# =======================
USERNAME = "acecargonic@gmail.com"
PASSWORD = "123456"

# =======================
# FUNCIONES DE SCRAPING
# =======================

def login_to_site(username, password):
    print("Paso SCRAP-1: Iniciando sesión en el sitio...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Modo headless para producción
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)
    
    try:
        driver.get("https://onboard.multitrack.trackingpremium.us/login")
        time.sleep(2)
        print("  -> Página de login cargada.")
        
        user_field = wait.until(EC.presence_of_element_located((By.NAME, "_username")))
        pass_field = wait.until(EC.presence_of_element_located((By.NAME, "_password")))
        user_field.send_keys(username)
        pass_field.send_keys(password)
        
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
        login_button.click()
        
        print("  -> Clic en 'Iniciar sesión'. Esperando 5 segundos...")
        time.sleep(5)
        
        driver.get("https://onboard.multitrack.trackingpremium.us/pobox/tracking")
        print("  -> Navegando a /pobox/tracking. Esperando 3 segundos...")
        time.sleep(3)
        
        return driver

    except Exception as e:
        print("Error durante el login:", e)
        driver.quit()
        return None

def select_warehouse(driver):
    print("Paso SCRAP-1.1: Seleccionando 'Warehouse' en el buscador...")
    wait = WebDriverWait(driver, 10)
    try:
        warehouse_radio = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@id='warehouse']/ancestor::label")))
        warehouse_radio.click()
        time.sleep(1)
        print("  -> Opción 'Warehouse' seleccionada correctamente.")
        return True
    except Exception as e:
        print(f"Error al seleccionar Warehouse: {e}")
        return False

def search_tracking(driver, code):
    print(f"Paso SCRAP-1.2: Ingresando número de tracking {code} y buscando...")
    wait = WebDriverWait(driver, 10)
    try:
        if not select_warehouse(driver):
            return False
        search_input = wait.until(EC.presence_of_element_located((By.ID, "numero")))
        search_input.clear()
        search_input.send_keys(code)
        time.sleep(1)
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "buscar")))
        search_button.click()
        print("  -> Clic en botón de búsqueda. Esperando resultado...")
        time.sleep(5)  
        return True
    except Exception as e:
        print(f"Error al buscar el tracking {code}: {e}")
        return False

def get_tracking_url(driver, code):
    print(f"Paso SCRAP-2: Buscando enlace de detalles para {code}...")
    wait = WebDriverWait(driver, 10)
    try:
        results_div = wait.until(EC.visibility_of_element_located((By.ID, "results")))
        time.sleep(2)
        xpath_query = f".//h3[@id='Cabecera']/a[contains(text(), '{code}')]"
        link_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_query)))
        tracking_url = link_element.get_attribute("href")
        print(f"  -> Enlace obtenido: {tracking_url}")
        return tracking_url
    except TimeoutException:
        print(f"ERROR: No se encontró un enlace con el código {code} en #results.")
        return None
    except NoSuchElementException:
        print(f"ERROR: No se encontró ningún enlace en #results.")
        return None
    except Exception as e:
        print(f"Error obteniendo el enlace de tracking: {e}")
        return None

def parse_tracking_details(driver, tracking_url):
    print(f"Paso SCRAP-3: Abriendo página de detalles {tracking_url}...")
    try:
        driver.get(tracking_url)
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        def get_info(icon_class):
            element = soup.find("i", class_=icon_class)
            if element:
                texto = element.find_next(string=True)
                return texto.strip().replace(":", "").strip() if texto else "No encontrado"
            return "No encontrado"
        details = {
            "agencia_actual": get_info("fa fa-building").replace("Agencia Actual", "").strip(),
            "recibido_por": get_info("fa fa-user").replace("Recibido por", "").strip(),
            "fecha": get_info("fa fa-calendar").replace("Fecha", "").strip(),
            "servicio": get_info("fa fa-plane").replace("Instrucciones", "").strip(),
            "pais_destino": get_info("fa fa-flag").replace("País Destino", "").strip(),
        }
        print("=== 📦 DETALLES EXTRAÍDOS ===")
        for key, value in details.items():
            print(f"{key.replace('_', ' ').capitalize()}: {value}")
        return details
    except Exception as e:
        print(f"Error al extraer detalles: {e}")
        return None

# =======================
# ENDPOINT DE LA API (método POST)
# =======================
@app.route('/tracking', methods=['POST'])
def tracking_endpoint():
    data = request.get_json()
    code = data.get('tracking')
    if not code:
        return jsonify({'error': 'Falta el parámetro "tracking"'}), 400

    driver = login_to_site(USERNAME, PASSWORD)
    if not driver:
        return jsonify({'error': 'Error al iniciar sesión'}), 500

    if not search_tracking(driver, code):
        driver.quit()
        return jsonify({'error': 'Error al buscar el tracking'}), 500

    tracking_url = get_tracking_url(driver, code)
    if not tracking_url:
        driver.quit()
        return jsonify({'error': 'No se encontró el enlace de detalles'}), 404

    details = parse_tracking_details(driver, tracking_url)
    driver.quit()
    if not details:
        return jsonify({'error': 'Error al extraer detalles'}), 500

    return jsonify({'tracking': code, 'details': details})

if __name__ == '__main__':
    app.run(debug=True)

