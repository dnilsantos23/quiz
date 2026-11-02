"""Leitor dos dados do quiz.

Convenção de pastas (nenhuma configuração no código):
    dados/<Nome da Disciplina>/<Título do Quiz>.json

Cada pasta dentro de dados/ vira uma disciplina e cada arquivo
JSON dentro dela vira um quiz, na ordem natural dos nomes
(APOL 1 antes de APOL 2, APOL 2 antes de APOL 10).
"""

import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DADOS = os.path.join(RAIZ, "dados")


def _chave_natural(texto):
    """Chave de ordenação que trata números como números ('APOL 2' < 'APOL 10')."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", texto)]


def _chave_disciplina(nome):
    """Compara disciplinas ignorando acentos, caixa e separadores."""
    sem_acentos = unicodedata.normalize("NFKD", nome)
    sem_acentos = "".join(c for c in sem_acentos if not unicodedata.combining(c))
    chave = re.sub(r"[^a-z0-9]+", "", sem_acentos.lower())
    if chave in ("bancodedados", "bandodedados"):
        return "bancodedadosrelacional"
    return chave


def _nome_exibicao_disciplina(nome):
    """Aplica o nome oficial de disciplinas com variações históricas."""
    if _chave_disciplina(nome).startswith("precalculo"):
        return "PRÉ-CÁLCULO"
    return nome


def _ler_json(caminho):
    """Abre um arquivo JSON de questões e devolve seu conteúdo estruturado."""
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def carregar_tudo():
    """Varre dados/ e retorna a estrutura completa:

    [
        {
            "nome": "Lógica de Programação",
            "quizzes": [
                {"titulo": "APOL 1", "perguntas": [...]},
                ...
            ],
        },
        ...
    ]
    """
    disciplinas = {}
    if not os.path.isdir(PASTA_DADOS):
        return disciplinas

    for nome_pasta in sorted(os.listdir(PASTA_DADOS), key=_chave_natural):
        pasta = os.path.join(PASTA_DADOS, nome_pasta)
        if not os.path.isdir(pasta):
            continue

        quizzes = []
        for nome_arquivo in sorted(os.listdir(pasta), key=_chave_natural):
            if not nome_arquivo.lower().endswith(".json"):
                continue
            quizzes.append({
                "titulo": os.path.splitext(nome_arquivo)[0],
                "perguntas": _ler_json(os.path.join(pasta, nome_arquivo)),
                "origem": nome_pasta,
            })

        if quizzes:
            chave = _chave_disciplina(nome_pasta)
            if chave not in disciplinas:
                disciplinas[chave] = {
                    "nome": _nome_exibicao_disciplina(nome_pasta),
                    "quizzes": [],
                }
            disciplinas[chave]["quizzes"].extend(quizzes)

    resultado = list(disciplinas.values())
    for disciplina in resultado:
        disciplina["quizzes"].sort(key=lambda quiz: _chave_natural(quiz["titulo"]))
    resultado.sort(key=lambda disciplina: _chave_natural(disciplina["nome"]))
    return resultado
