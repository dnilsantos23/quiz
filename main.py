"""Servidor local do quiz com auto-encerramento e atualização de PDFs.

Responsabilidades deste módulo:
- Fornecer as rotas do Flask para servir a página do quiz, imagens e ícone;
- Permitir atualização dinâmica dos PDFs novos via endpoint POST /atualizar;
- Monitorar a presença do navegador através de um batimento cardíaco (/ping);
- Encerrar o processo automaticamente quando o usuário fechar a aba do navegador;
- Iniciar a página web e ocultar a janela de console do terminal no Windows (SW_HIDE);
- Garantir que apenas uma instância do servidor rode por vez na porta 5000.
"""

import ctypes
import json
import os
import socket
import sys
import threading
import time
import unicodedata
import urllib.request
import webbrowser
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_MODULOS = os.path.join(AQUI, "módulos")
if PASTA_MODULOS not in sys.path:
    sys.path.insert(0, PASTA_MODULOS)

import exercicios_web
import apostila_ia
import quiz_dados

app = Flask(__name__)
geracoes = {}
geracoes_lock = threading.Lock()
geracao_html_lock = threading.Lock()


def _chave_disciplina(nome):
    sem_acentos = unicodedata.normalize("NFKD", nome)
    sem_acentos = "".join(c for c in sem_acentos if not unicodedata.combining(c))
    chave = "".join(c for c in sem_acentos.lower() if c.isalnum())
    if chave in ("bancodedados", "bandodedados"):
        return "bancodedadosrelacional"
    return chave


def _pasta_disciplina_existente(nome):
    chave = _chave_disciplina(nome)
    if os.path.isdir(os.path.join(AQUI, "dados")):
        for pasta in os.listdir(os.path.join(AQUI, "dados")):
            caminho = os.path.join(AQUI, "dados", pasta)
            if os.path.isdir(caminho) and _chave_disciplina(pasta) == chave:
                return pasta
    return apostila_ia.nomes_seguros(nome, "Apostilas")[0]

# Registra o timestamp do último ping recebido da página web
ultimo_ping = time.time()
@app.get("/")
def pagina_quiz():
    """Entrega a página gerada do quiz (quiz.html)."""
    global ultimo_ping
    ultimo_ping = time.time()
    resposta = send_from_directory(AQUI, "quiz.html")
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


@app.post("/ping")
def ping():
    """Recebe o batimento cardíaco enviado a cada 3 segundos pela página aberta.
    
    Atualiza o timestamp para sinalizar que o usuário ainda está ativo no quiz.
    """
    global ultimo_ping
    ultimo_ping = time.time()
    return ("", 204)


def _confirmar_encerramento(momento_saida):
    """Finaliza o servidor apenas se nenhum novo acesso ou ping ocorreu após o sinal de saída.
    
    Isso impede que recarregamentos de página (F5 ou botão Atualizar) matem o servidor.
    """
    if ultimo_ping <= momento_saida:
        os._exit(0)


@app.post("/sair")
def sair():
    """Recebe o sinal de fechamento da página via navigator.sendBeacon.
    
    Aguarda 4 segundos e confirma se a aba foi realmente fechada (sem novos pings)
    antes de encerrar o processo Flask.
    """
    momento_saida = time.time()
    threading.Timer(4.0, _confirmar_encerramento, args=(momento_saida,)).start()
    return ("", 204)


@app.get("/dados/<path:arquivo>")
def arquivo_dados(arquivo):
    """Entrega imagens extraídas dos PDFs e demais arquivos estáticos da pasta dados/."""
    return send_from_directory(os.path.join(AQUI, "dados"), arquivo)


@app.get("/icone/<path:arquivo>")
def arquivo_icone(arquivo):
    """Entrega o arquivo de ícone da pasta icone/."""
    return send_from_directory(os.path.join(AQUI, "icone"), arquivo)


@app.get("/favicon.ico")
def favicon():
    """Atende a requisição automática de favicon feita pelos navegadores."""
    return send_from_directory(
        os.path.join(AQUI, "icone"), "quiz.ico", mimetype="image/x-icon"
    )


@app.post("/atualizar")
def atualizar_quiz():
    """Converte PDFs novos, regenera o quiz.html e informa o resultado ao cliente."""
    global ultimo_ping
    ultimo_ping = time.time()
    try:
        with geracao_html_lock:
            exercicios_web.gerar(converter_arquivos=True)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as erro:
        return jsonify({"sucesso": False, "erro": str(erro)}), 500

    return jsonify({"sucesso": True})


@app.post("/gerar-apostila")
def gerar_apostila():
    """Recebe uma apostila e inicia a geração em segundo plano."""
    global ultimo_ping
    ultimo_ping = time.time()
    disciplina = request.form.get("disciplina", "").strip()
    titulo = request.form.get("titulo", "").strip()
    apostila_relativa = request.form.get("apostila", "").strip()
    provedor = request.form.get("provedor", "gemini").strip().lower()
    chave_api = request.form.get("chave_api", "").strip()
    if not chave_api:
        chave_api = apostila_ia.carregar_configuracao(provedor)["chave_api"]
    pasta_fontes = os.path.join(AQUI, "apostilas")
    caminho_pdf = os.path.abspath(os.path.join(pasta_fontes, apostila_relativa))
    raiz_fontes = os.path.abspath(pasta_fontes)
    if (
        not apostila_relativa
        or not apostila_relativa.lower().endswith(".pdf")
        or os.path.commonpath([raiz_fontes, caminho_pdf]) != raiz_fontes
        or not os.path.isfile(caminho_pdf)
    ):
        return jsonify({"sucesso": False, "erro": "Selecione uma apostila disponível."}), 400
    if not disciplina or not titulo:
        return jsonify({"sucesso": False, "erro": "Informe a disciplina e o nome do conjunto."}), 400
    if not chave_api:
        return jsonify({"sucesso": False, "erro": "Informe a chave da API do provedor selecionado."}), 400
    try:
        apostila_ia.salvar_configuracao(provedor, chave_api)
    except apostila_ia.GeracaoApostilaError as erro:
        return jsonify({"sucesso": False, "erro": str(erro)}), 400

    pasta_disciplina = _pasta_disciplina_existente(disciplina)
    _, nome_quiz = apostila_ia.nomes_seguros(disciplina, titulo)
    pasta = os.path.join(AQUI, "dados", pasta_disciplina)
    os.makedirs(pasta, exist_ok=True)
    caminho_json = os.path.join(pasta, f"{nome_quiz}.json")

    identificador = uuid.uuid4().hex
    with geracoes_lock:
        geracoes[identificador] = {
            "estado": "processando",
            "percentual": 5,
            "mensagem": "Apostila recebida. Preparando geração...",
            "titulo": nome_quiz,
            "disciplina": pasta_disciplina,
        }

    def atualizar_progresso(percentual, mensagem):
        with geracoes_lock:
            if identificador in geracoes:
                geracoes[identificador].update(
                    percentual=percentual, mensagem=mensagem
                )

    def executar_geracao():
        try:
            perguntas = apostila_ia.gerar(
                caminho_pdf, chave_api, provedor=provedor, progresso=atualizar_progresso
            )
            with open(caminho_json, "w", encoding="utf-8") as destino:
                json.dump(perguntas, destino, ensure_ascii=False, indent=2)
                destino.write("\n")
            with geracao_html_lock:
                exercicios_web.gerar(converter_arquivos=False)
            with geracoes_lock:
                geracoes[identificador].update(
                    estado="concluido",
                    percentual=100,
                    mensagem="Questionário criado. Atualize o menu para acessá-lo.",
                )
        except (OSError, ValueError, json.JSONDecodeError, apostila_ia.GeracaoApostilaError) as erro:
            with geracoes_lock:
                geracoes[identificador].update(
                    estado="erro", percentual=100, mensagem=str(erro)
                )

    threading.Thread(target=executar_geracao, daemon=True).start()
    return jsonify({"sucesso": True, "id": identificador}), 202


@app.get("/apostilas-disponiveis")
def apostilas_disponiveis():
    """Lista as apostilas PDF organizadas por disciplina."""
    pasta_fontes = os.path.join(AQUI, "apostilas")
    os.makedirs(pasta_fontes, exist_ok=True)
    disciplinas = {}
    nomes_existentes = {
        _chave_disciplina(disciplina["nome"]): disciplina["nome"]
        for disciplina in quiz_dados.carregar_tudo()
    }
    for raiz, _, arquivos in os.walk(pasta_fontes):
        for nome in sorted(arquivos):
            if not nome.lower().endswith(".pdf"):
                continue
            caminho = os.path.join(raiz, nome)
            relativo = os.path.relpath(caminho, pasta_fontes).replace(os.sep, "/")
            partes = relativo.split("/")
            nome_disciplina = partes[0] if len(partes) > 1 else "Outras apostilas"
            nome_disciplina = nomes_existentes.get(
                _chave_disciplina(nome_disciplina), nome_disciplina
            )
            disciplinas.setdefault(nome_disciplina, []).append(
                {"nome": Path(nome).stem, "arquivo": relativo}
            )
    return jsonify(
        {
            "sucesso": True,
            "disciplinas": [
                {"nome": nome, "apostilas": arquivos}
                for nome, arquivos in sorted(disciplinas.items())
            ],
        }
    )


@app.get("/configuracao-ia")
def configuracao_ia():
    """Entrega ao formulário a última configuração local do provedor."""
    configuracao = apostila_ia.carregar_configuracao()
    return jsonify({"sucesso": True, **configuracao})


@app.get("/gerar-apostila/<identificador>")
def status_geracao_apostila(identificador):
    """Consulta o progresso de uma geração iniciada em segundo plano."""
    with geracoes_lock:
        status = geracoes.get(identificador)
        if status is None:
            return jsonify({"sucesso": False, "erro": "Geração não encontrada."}), 404
        return jsonify({"sucesso": True, **status})


def _porta_em_uso(porta=5000):
    """Verifica se a porta 5000 já está ocupada por outra instância ativa do servidor."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def _vigiar_inatividade():
    """Thread sentinela que encerra o processo se o navegador for fechado.
    
    Aguarda 15 segundos iniciais para tolerar o tempo de inicialização do navegador.
    Se decorrerem mais de 8 segundos sem nenhum ping (ou seja, todas as abas
    do quiz foram fechadas), finaliza o processo Python liberando a memória do SO.
    """
    time.sleep(15)
    while True:
        time.sleep(2)
        with geracoes_lock:
            geracao_em_andamento = any(
                item["estado"] == "processando" for item in geracoes.values()
            )
        if not geracao_em_andamento and time.time() - ultimo_ping > 8:
            os._exit(0)


def _abrir_navegador_e_ocultar():
    """Abre a página do quiz no navegador padrão e oculta a janela do console no Windows."""
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")
    time.sleep(1.5)
    try:
        # Obtém o identificador da janela do console (HWND) e a oculta (SW_HIDE = 0)
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


if __name__ == "__main__":
    # Se o servidor já estiver em execução em segundo plano:
    # 1. Pede para atualizar os dados caso novos PDFs tenham sido inseridos
    # 2. Abre uma nova aba no navegador
    # 3. Finaliza esta instância duplicada
    if _porta_em_uso(5000):
        try:
            req = urllib.request.Request("http://127.0.0.1:5000/atualizar", method="POST")
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass
        webbrowser.open("http://127.0.0.1:5000")
        os._exit(0)

    # Converte PDFs novos e regenera a página estática antes de subir o servidor
    try:
        exercicios_web.gerar(converter_arquivos=True)
    except Exception as erro:
        print(f"Aviso ao inicializar dados: {erro}")

    print("Iniciando página no navegador...")
    # Dispara a abertura do navegador e ocultação da janela em thread separada
    threading.Thread(target=_abrir_navegador_e_ocultar, daemon=True).start()
    # Dispara o sentinela de encerramento automático em thread separada
    threading.Thread(target=_vigiar_inatividade, daemon=True).start()
    # Inicia o servidor Flask na porta local 5000
    app.run(host="127.0.0.1", port=5000, debug=False)
