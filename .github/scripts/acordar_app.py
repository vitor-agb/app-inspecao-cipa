"""Mantém o app no Streamlit Community Cloud acordado.

Abre o endereço do app em navegador headless, aciona o botão de despertar quando o app está
hibernado e permanece conectado por alguns segundos, gerando o tráfego que reinicia a contagem
de inatividade. O endereço vem da variável de ambiente STREAMLIT_APP_URL.
Não realiza login nem grava dados.
"""
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

LIMITE_CARGA_SEGUNDOS = 240
PERMANENCIA_SEGUNDOS = 20


def app_carregado(pagina):
    # O app renderiza dentro de um iframe na página do Community Cloud; verifica todos os frames.
    return any(frame.locator('[data-testid="stApp"]').count() > 0 for frame in pagina.frames)


def acionar_despertar(pagina):
    botao = pagina.get_by_role("button", name=re.compile(r"back up|wake", re.IGNORECASE))
    if botao.count() > 0:
        botao.first.click()
        return True
    return False


def main():
    url = os.environ.get("STREAMLIT_APP_URL", "").strip()
    if not url:
        print("Variável STREAMLIT_APP_URL não definida.")
        return 2

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch()
        pagina = navegador.new_page()
        pagina.goto(url, wait_until="domcontentloaded", timeout=60_000)

        despertou = False
        inicio = time.time()
        carregado = False
        while time.time() - inicio < LIMITE_CARGA_SEGUNDOS:
            if app_carregado(pagina):
                carregado = True
                break
            if not despertou:
                despertou = acionar_despertar(pagina)
            time.sleep(3)

        if not carregado:
            print("App não carregou dentro do limite de tempo.")
            navegador.close()
            return 1

        print("App carregado" + (" após acionar o despertar." if despertou else " (já estava acordado)."))
        time.sleep(PERMANENCIA_SEGUNDOS)
        navegador.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
