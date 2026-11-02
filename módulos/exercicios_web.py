"""Geração da página web do quiz.

Fluxo: lê os JSONs em dados/ -> formata os textos -> injeta tudo
no template HTML -> salva o quiz.html final.
"""

import html
import json
import os
import re
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote

PASTA_MODULOS = os.path.dirname(os.path.abspath(__file__))
AQUI = os.path.dirname(PASTA_MODULOS)
if PASTA_MODULOS not in sys.path:
    sys.path.insert(0, PASTA_MODULOS)

import quiz_dados
import pdf_para_json

ROMANOS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]


def _ler(*partes):
    """Lê um arquivo texto dentro da pasta do projeto."""
    with open(os.path.join(AQUI, *partes), encoding="utf-8") as f:
        return f.read()


def _formatar_enunciado(texto):
    """Deixa o enunciado pronto para HTML.

    - escapa caracteres especiais (<, >, &) por segurança;
    - converte tabulações em recuo HTML (&nbsp;&nbsp;&nbsp;&nbsp;);
    - quebra a linha antes de itens romanos e conclusões;
    - converte quebras de linha reais em <br>.
    """
    texto = html.escape(texto)
    texto = texto.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
    # Adiciona quebras antes de itens (I., II., I-, etc.) se ainda não houver quebra
    texto = re.sub(
        r"(?<!^)(?<![\n>])\s+((?:[IVXLCDM]+|[0-9]+)\s*[\.\-\)]|\([IVXLCDM]+\))\s+",
        r"<br>&nbsp;&nbsp;&nbsp;&nbsp;\1 ",
        texto,
        flags=re.IGNORECASE,
    )
    # Adiciona quebras antes de conclusões da questão
    texto = re.sub(
        r"(?<!^)(?<![\n>])\s+(Estão corretas|São corretas|Assinale a|Agora,|É correto o que)\b",
        r"<br>\1",
        texto,
        flags=re.IGNORECASE,
    )
    return texto.replace("\n", "<br>")


def _formatar_alternativa(texto):
    """Escapa a alternativa e transforma ' | ' em quebra de linha."""
    return html.escape(texto).replace(" | ", "<br>")


def _preparar(perguntas, nome_disciplina):
    """Aplica a formatação acima em todas as questões de um quiz."""
    return [
        {
            "enunciado": _formatar_enunciado(q["enunciado"]),
            "alternativas": {k: _formatar_alternativa(v) for k, v in q["alternativas"].items()},
            "gabarito": q["gabarito"],
            "explicacao": q["explicacao"],
            "imagens": [
                quote(f"dados/{nome_disciplina}/{imagem}".replace("\\", "/"), safe="/")
                for imagem in q.get("imagens", [])
            ],
            "imagens_explicacao": [
                quote(f"dados/{nome_disciplina}/{imagem}".replace("\\", "/"), safe="/")
                for imagem in q.get("imagens_explicacao", [])
            ],
        }
        for q in perguntas
    ]


def gerar(converter_arquivos=True):
    """Monta e salva o quiz.html. Retorna o caminho do arquivo criado."""
    if converter_arquivos:
        pdf_para_json.converter_pdfs()
    disciplinas = quiz_dados.carregar_tudo()

    for d in disciplinas:
        for quiz in d["quizzes"]:
            quiz["perguntas"] = _preparar(quiz["perguntas"], quiz.get("origem", d["nome"]))

    js = json.dumps(disciplinas, ensure_ascii=False).replace("</", "<\\/")

    pagina = _ler("templates", "quiz.html").replace(
        "const DADOS = __DATA__;", f"const DADOS = {js};"
    )
    if "const DADOS = __DATA__" in pagina:
        raise RuntimeError("Marcador de dados não encontrado no template!")

    saida = os.path.join(AQUI, "quiz.html")
    with open(saida, "w", encoding="utf-8") as f:
        f.write(pagina)
    return saida


if __name__ == "__main__":
    pdf_para_json.converter_pdfs()
    if not quiz_dados.carregar_tudo():
        print(f"Nenhuma disciplina encontrada em: {quiz_dados.PASTA_DADOS}")
        print("Crie uma pasta por disciplina e coloque um JSON por APOL dentro dela.")
    else:
        caminho = gerar(converter_arquivos=False)
        webbrowser.open(Path(caminho).as_uri())
        print(f"Quiz gerado e aberto no navegador: {caminho}")
