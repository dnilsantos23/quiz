"""Geração de perguntas a partir de apostilas usando provedores de IA."""

import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pypdf import PdfReader
from pypdf.errors import PdfReadError

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MODELO_PADRAO = "gemini-3.8-flash"
MODELOS_RESERVA = ("gemini-3.7-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash")
MAX_TEXTO = 40000
TENTATIVAS_GEMINI = 3
ARQUIVO_CONFIGURACAO = Path(__file__).resolve().parent.parent / "configuracao_ia.json"
PROVEDORES = {
    "gemini": {"nome": "Google Gemini"},
    "openai": {"nome": "OpenAI"},
}


class GeracaoApostilaError(RuntimeError):
    """Erro esperado durante leitura, geração ou validação da apostila."""


def _url_modelo(modelo):
    return f"{GEMINI_API_URL}/{modelo}:generateContent"


def _listar_modelos_gemini(chave_api):
    """Obtém os modelos autorizados pela chave e compatíveis com texto."""
    requisicao = Request(
        GEMINI_API_URL,
        headers={"x-goog-api-key": chave_api.strip()},
    )
    try:
        with urlopen(requisicao, timeout=30) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except HTTPError as erro:
        detalhe = erro.read().decode("utf-8", errors="replace")[:300]
        raise GeracaoApostilaError(
            f"Não foi possível consultar os modelos Gemini (HTTP {erro.code}): {detalhe}"
        ) from erro
    except (URLError, TimeoutError, OSError) as erro:
        detalhe = getattr(erro, "reason", None) or str(erro)
        raise GeracaoApostilaError(
            f"Não foi possível consultar os modelos Gemini: {detalhe}."
        ) from erro
    except json.JSONDecodeError as erro:
        raise GeracaoApostilaError(
            "A API Gemini retornou uma lista de modelos inválida."
        ) from erro

    modelos = []
    for item in dados.get("models", []):
        nome = str(item.get("name", ""))
        metodos = item.get("supportedGenerationMethods", [])
        if nome.startswith("models/"):
            nome = nome[7:]
        if nome and "generateContent" in metodos:
            modelos.append(nome)
    if not modelos:
        raise GeracaoApostilaError(
            "A chave Gemini foi aceita, mas não há modelos disponíveis para "
            "generateContent neste projeto."
        )
    return modelos


def _ordenar_modelos_gemini(modelos, preferidos):
    disponiveis = set(modelos)
    ordenados = [modelo for modelo in preferidos if modelo in disponiveis]
    restantes = sorted(
        (modelo for modelo in modelos if modelo not in ordenados),
        key=lambda modelo: (
            "flash" not in modelo.lower(),
            "lite" not in modelo.lower(),
            modelo,
        ),
    )
    return tuple(ordenados + restantes)


def carregar_configuracao(provedor=None):
    """Carrega a configuração local sem falhar quando ela ainda não existe."""
    try:
        with ARQUIVO_CONFIGURACAO.open(encoding="utf-8") as arquivo:
            configuracao = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {"provedor": "gemini", "chave_api": "", "chaves": {}}
    provedor_configurado = configuracao.get("provedor", "gemini")
    if provedor_configurado not in PROVEDORES:
        provedor_configurado = "gemini"
    chaves = configuracao.get("chaves", {})
    if not isinstance(chaves, dict):
        chaves = {}
    chave_antiga = str(configuracao.get("chave_api", ""))
    if chave_antiga and "gemini" not in chaves:
        chaves["gemini"] = chave_antiga
    provedor_selecionado = (
        provedor if provedor in PROVEDORES else provedor_configurado
    )
    return {
        "provedor": provedor_selecionado,
        "chave_api": str(chaves.get(provedor_selecionado, "")),
        "chaves": {nome: str(chave) for nome, chave in chaves.items() if nome in PROVEDORES},
    }


def salvar_configuracao(provedor, chave_api):
    """Salva a chave somente no arquivo local ignorado pelo controle de versão."""
    if provedor not in PROVEDORES:
        raise GeracaoApostilaError("Provedor de IA inválido.")
    if not chave_api or len(chave_api.strip()) < 20:
        raise GeracaoApostilaError("Informe uma chave válida da API.")
    configuracao = carregar_configuracao()
    chaves = configuracao["chaves"]
    chaves[provedor] = chave_api.strip()
    with ARQUIVO_CONFIGURACAO.open("w", encoding="utf-8") as arquivo:
        json.dump({"provedor": provedor, "chaves": chaves}, arquivo, indent=2)
        arquivo.write("\n")


def _nome_seguro(nome, padrao):
    base = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", " ", base).strip()
    return base or padrao


def _extrair_texto(caminho):
    try:
        paginas = PdfReader(str(caminho)).pages
        texto = "\n".join((pagina.extract_text() or "") for pagina in paginas)
    except (OSError, PdfReadError, ValueError) as erro:
        raise GeracaoApostilaError(f"Não foi possível ler a apostila PDF: {erro}") from erro
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if len(texto) < 200:
        raise GeracaoApostilaError(
            "A apostila não possui texto suficiente. Use um PDF com texto selecionável."
        )
    return texto[:MAX_TEXTO]


def _extrair_json(resposta, provedor="gemini"):
    resposta = resposta.strip()
    if resposta.startswith("```"):
        resposta = re.sub(r"^```(?:json)?\s*", "", resposta, flags=re.IGNORECASE)
        resposta = re.sub(r"\s*```$", "", resposta)
    try:
        dados = json.loads(resposta)
    except json.JSONDecodeError as erro:
        inicio = next(
            (indice for indice, caractere in enumerate(resposta) if caractere in "[{"),
            -1,
        )
        if inicio < 0:
            raise GeracaoApostilaError(f"JSON retornado pela IA é inválido: {erro}") from erro
        fim = _fim_json(resposta, inicio)
        if fim <= inicio:
            raise GeracaoApostilaError(f"JSON retornado pela IA é inválido: {erro}") from erro
        try:
            dados = json.loads(resposta[inicio:fim])
        except json.JSONDecodeError as erro_lista:
            raise GeracaoApostilaError(f"JSON retornado pela IA é inválido: {erro_lista}") from erro_lista

    if isinstance(dados, str):
        return _extrair_json(dados)
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for chave in ("perguntas", "questions", "questoes", "items"):
            if isinstance(dados.get(chave), list):
                return dados[chave]
    raise GeracaoApostilaError("O provedor de IA não retornou uma lista de perguntas.")


def _fim_json(texto, inicio):
    """Encontra o fim do primeiro objeto/array JSON sem confundir texto interno."""
    fechamentos = {"[": "]", "{": "}"}
    pilha = []
    dentro_string = False
    escapado = False
    for indice in range(inicio, len(texto)):
        caractere = texto[indice]
        if dentro_string:
            if escapado:
                escapado = False
            elif caractere == "\\":
                escapado = True
            elif caractere == '"':
                dentro_string = False
            continue
        if caractere == '"':
            dentro_string = True
        elif caractere in fechamentos:
            pilha.append(fechamentos[caractere])
        elif caractere in ("]", "}"):
            if not pilha or pilha.pop() != caractere:
                return -1
            if not pilha:
                return indice + 1
    return -1


def _validar(perguntas, quantidade):
    if not isinstance(perguntas, list) or len(perguntas) != quantidade:
        raise GeracaoApostilaError(
            f"O Gemini retornou {len(perguntas) if isinstance(perguntas, list) else 0} "
            f"perguntas; eram esperadas {quantidade}."
        )
    resultado = []
    for indice, pergunta in enumerate(perguntas, 1):
        if not isinstance(pergunta, dict):
            raise GeracaoApostilaError(f"Pergunta {indice} possui formato inválido.")
        alternativas = pergunta.get("alternativas")
        if isinstance(alternativas, list) and len(alternativas) == 5:
            alternativas = dict(zip("ABCDE", alternativas))
        elif isinstance(alternativas, dict):
            alternativas = {str(chave).upper(): valor for chave, valor in alternativas.items()}
        gabarito_bruto = str(pergunta.get("gabarito", "")).strip()
        gabarito = gabarito_bruto.upper()
        if gabarito not in "ABCDE" and isinstance(alternativas, dict):
            for letra, alternativa in alternativas.items():
                if str(alternativa).strip().casefold() == gabarito_bruto.casefold():
                    gabarito = letra
                    break
        if (
            not isinstance(pergunta.get("enunciado"), str)
            or not pergunta["enunciado"].strip()
            or not isinstance(alternativas, dict)
            or set(alternativas) != set("ABCDE")
            or any(not isinstance(valor, str) or not valor.strip() for valor in alternativas.values())
            or gabarito not in "ABCDE"
        ):
            raise GeracaoApostilaError(f"Pergunta {indice} não passou na validação.")
        resultado.append(
            {
                "numero": indice,
                "enunciado": pergunta["enunciado"].strip(),
                "alternativas": {letra: alternativas[letra].strip() for letra in "ABCDE"},
                "gabarito": gabarito,
                "explicacao": str(pergunta.get("explicacao", "")).strip(),
                "imagens": [],
                "imagens_explicacao": [],
            }
        )
    return resultado


def _corpo_gemini(prompt):
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "perguntas": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "enunciado": {"type": "STRING"},
                                "alternativas": {
                                    "type": "ARRAY",
                                    "items": {"type": "STRING"},
                                },
                                "gabarito": {"type": "STRING"},
                                "explicacao": {"type": "STRING"},
                            },
                            "required": [
                                "enunciado",
                                "alternativas",
                                "gabarito",
                                "explicacao",
                            ],
                        },
                    }
                },
                "required": ["perguntas"],
            },
        },
    }


def _corpo_openai(prompt):
    return {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Responda somente com JSON válido."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }


def _extrair_resposta(dados, provedor):
    try:
        if provedor == "openai":
            return dados["choices"][0]["message"]["content"]
        return dados["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as erro:
        raise GeracaoApostilaError("O provedor de IA não retornou perguntas.") from erro


def gerar(caminho_pdf, chave_api, provedor="gemini", quantidade=10, modelo=MODELO_PADRAO, progresso=None):
    """Gera perguntas usando o provedor escolhido e devolve uma lista validada."""
    def informar(percentual, mensagem):
        if progresso:
            progresso(percentual, mensagem)

    if not chave_api or len(chave_api.strip()) < 20:
        raise GeracaoApostilaError("Informe uma chave válida da API.")
    if provedor not in PROVEDORES:
        raise GeracaoApostilaError("Provedor de IA inválido.")
    informar(10, "Lendo o texto da apostila...")
    texto = _extrair_texto(caminho_pdf)
    prompt = f"""
Crie exatamente {quantidade} perguntas de múltipla escolha usando somente a apostila.
Retorne somente JSON válido, sem markdown, com esta estrutura:
{{"perguntas":[{{"enunciado":"pergunta","alternativas":["A","B","C","D","E"],
"gabarito":"A","explicacao":"explicação"}}]}}
O array perguntas deve ter exatamente {quantidade} itens. Cada alternativas deve
ter exatamente cinco textos. O gabarito deve ser uma letra entre A e E.

APOSTILA:
{texto}
"""
    if provedor == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        corpo = json.dumps(_corpo_openai(prompt)).encode()
        modelos = ("openai",)
    else:
        url = None
        corpo = json.dumps(_corpo_gemini(prompt)).encode()
        modelos_disponiveis = _listar_modelos_gemini(chave_api)
        modelos = _ordenar_modelos_gemini(
            modelos_disponiveis, (modelo,) + MODELOS_RESERVA
        )
    ultimo_erro = None
    dados = None
    for modelo_atual in modelos:
        informar(25, f"Aguardando resposta da {PROVEDORES[provedor]['nome']}...")
        destino = url if provedor == "openai" else _url_modelo(modelo_atual)
        cabecalhos = {"Content-Type": "application/json"}
        if provedor == "openai":
            cabecalhos["Authorization"] = "Bearer " + chave_api.strip()
        else:
            cabecalhos["x-goog-api-key"] = chave_api.strip()
        requisicao = Request(destino, data=corpo, headers=cabecalhos)
        sucesso = False
        for tentativa in range(TENTATIVAS_GEMINI):
            try:
                with urlopen(requisicao, timeout=120) as resposta:
                    dados = json.loads(resposta.read().decode("utf-8"))
                sucesso = True
                informar(80, "Resposta recebida. Validando perguntas...")
                break
            except HTTPError as erro:
                detalhe = erro.read().decode("utf-8", errors="replace")[:300]
                ultimo_erro = erro
                if erro.code in (429, 503) and tentativa < TENTATIVAS_GEMINI - 1:
                    espera = min(2 ** (tentativa + 1), 30)
                    cabecalho = erro.headers.get("Retry-After")
                    if cabecalho and cabecalho.isdigit():
                        espera = min(int(cabecalho), 30)
                    time.sleep(espera)
                    continue
                if provedor == "gemini" and erro.code in (404, 429, 503):
                    break
                raise GeracaoApostilaError(
                    f"{PROVEDORES[provedor]['nome']} recusou a solicitação "
                    f"(HTTP {erro.code}): {detalhe}"
                ) from erro
            except (URLError, TimeoutError, OSError) as erro:
                ultimo_erro = erro
                if tentativa < TENTATIVAS_GEMINI - 1:
                    time.sleep(min(2 ** (tentativa + 1), 30))
                    continue
                if provedor == "gemini":
                    break
                detalhe = getattr(erro, "reason", None) or str(erro)
                raise GeracaoApostilaError(
                    f"Não foi possível conectar à API da {PROVEDORES[provedor]['nome']}: "
                    f"{detalhe}. Verifique sua internet, proxy ou firewall."
                ) from erro
            except json.JSONDecodeError as erro:
                raise GeracaoApostilaError("A API do Gemini retornou uma resposta inválida.") from erro
        if sucesso:
            break
    else:
        if provedor == "gemini" and isinstance(ultimo_erro, HTTPError) and ultimo_erro.code == 404:
            raise GeracaoApostilaError(
                "Nenhum modelo Gemini configurado está disponível para esta chave."
            ) from ultimo_erro
        if isinstance(ultimo_erro, (URLError, TimeoutError, OSError)):
            detalhe = getattr(ultimo_erro, "reason", None) or str(ultimo_erro)
            raise GeracaoApostilaError(
                f"Não foi possível conectar à API da {PROVEDORES[provedor]['nome']}: "
                f"{detalhe}. Verifique sua internet, proxy ou firewall."
            ) from ultimo_erro
        raise GeracaoApostilaError(
            "Os modelos Gemini estão temporariamente indisponíveis. "
            "Tente novamente em alguns minutos."
        ) from ultimo_erro

    texto_resposta = _extrair_resposta(dados, provedor)
    resultado = _validar(_extrair_json(texto_resposta), quantidade)
    informar(95, "Perguntas validadas. Salvando o questionário...")
    return resultado


def nomes_seguros(nome_disciplina, nome_quiz):
    return _nome_seguro(nome_disciplina, "Apostilas"), _nome_seguro(nome_quiz, "Quiz da apostila")
