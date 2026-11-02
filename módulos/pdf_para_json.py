"""Converte PDFs de avaliações corrigidas para o formato JSON do quiz."""

import json
import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"

QUESTAO_RE = re.compile(r"(?im)^[ \t]*Questão\s*(\d+)\s*/\s*(\d+)")
ALTERNATIVA_RE = re.compile(r"(?m)^[ \t]*([A-E])(?:\s*$|\s{2,})")
SELECIONADA_RE = re.compile(
    r"Você\s+assinalou\s+essa\s+alternativa\s*\(([A-E])\)", re.IGNORECASE
)
RESULTADO_RE = re.compile(r"Você\s+(acertou|errou)\s*!", re.IGNORECASE)


def _limpar(texto):
    """Normaliza espaços e quebras de linha extraídos do texto do PDF."""
    return re.sub(r"\s+", " ", texto).strip()


def _formatar_enunciado(texto):
    """Formata o enunciado preservando quebras de linha estruturadas (itens e conclusão)."""
    linhas = [l.strip() for l in texto.splitlines()]
    regex_item = re.compile(
        r"^(?:(?:[IVXLCDM]+|[0-9]+)\s*[\.\-\)]|\([IVXLCDM]+\)|\([0-9]+\)|¦)\s*",
        re.IGNORECASE,
    )
    regex_conclusao = re.compile(
        r"^(?:Estão|São|Assinale|Agora,|É correto|Quais|Considerando|Qual|Com base|A respeito|Quanto)\b",
        re.IGNORECASE,
    )

    blocos = []
    buffer = []
    em_itens = False

    def descarregar(identar=False):
        nonlocal buffer
        if buffer:
            t = " ".join(buffer).strip()
            t = re.sub(r"[ \t]+", " ", t)
            if t:
                blocos.append(f"\t{t}" if identar else t)
            buffer = []

    for linha in linhas:
        if not linha:
            continue
        if regex_item.match(linha):
            descarregar(identar=em_itens)
            em_itens = True
            buffer.append(linha)
        elif em_itens and regex_conclusao.match(linha):
            descarregar(identar=True)
            em_itens = False
            buffer.append(linha)
        else:
            buffer.append(linha)

    descarregar(identar=em_itens)
    return "\n".join(blocos)


def _nome_imagem(numero_pagina, numero_imagem, imagem):
    """Cria um nome estável para uma imagem extraída de uma página do PDF."""
    formato = (imagem.image.format or "png").lower()
    extensao = "jpg" if formato == "jpeg" else formato
    return f"pagina-{numero_pagina:03d}-imagem-{numero_imagem:02d}.{extensao}"


def _matrix_multiply(m1, m2):
    """Multiplicação de matrizes afins 2D no formato do PDF [a, b, c, d, e, f]."""
    a1, b1, c1, d1, e1, f1 = [float(x) for x in m1]
    a2, b2, c2, d2, e2, f2 = [float(x) for x in m2]
    return [
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    ]


def _extrair_elementos_pagina(page):
    """Extrai cabeçalhos de questões e marcadores de resultado com coordenadas Y."""
    buffer = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip():
            buffer.append((text.strip(), tm[5] * cm[3] + cm[5]))

    page.extract_text(visitor_text=visitor)

    headers = []
    resultados = []
    regex_full = re.compile(r"(?i)Questão\s*(\d+)\s*/\s*(\d+)")
    regex_num = re.compile(r"^(\d+)\s*/\s*(\d+)")

    for idx, (t, y) in enumerate(buffer):
        m = regex_full.search(t)
        if m:
            headers.append((int(m.group(1)), y))
            continue
        if "quest" in t.lower():
            for next_idx in range(idx + 1, min(len(buffer), idx + 5)):
                next_t = buffer[next_idx][0]
                m2 = regex_num.search(next_t)
                if m2:
                    headers.append((int(m2.group(1)), y))
                    break
        if "acertou" in t.lower() or "errou" in t.lower():
            resultados.append(y)

    headers.sort(key=lambda h: -h[1])
    return headers, resultados


def _mapear_todas_imagens_espacial(leitor):
    """Mapeia cada imagem à sua respectiva questão usando coordenadas espaciais."""
    questao_ativa = None
    em_explicacao = False

    imagens_enunciado = {}
    imagens_explicacao = {}

    for p_idx, page in enumerate(leitor.pages):
        num_pag = p_idx + 1
        headers, resultados = _extrair_elementos_pagina(page)

        nome_map = {}
        for i, img in enumerate(page.images, start=1):
            nome_completo = _nome_imagem(num_pag, i, img)
            nome_map[img.name] = nome_completo
            nome_map[img.name.rsplit(".", 1)[0]] = nome_completo

        contents = page.get_contents()
        ops = (
            contents.operations
            if contents is not None and hasattr(contents, "operations")
            else []
        )
        ctm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        stack = []
        images_ops = []

        for op in ops:
            code = op[1]
            args = op[0]
            if code == b"q":
                stack.append(list(ctm))
            elif code == b"Q":
                if stack:
                    ctm = stack.pop()
            elif code == b"cm":
                ctm = _matrix_multiply(args, ctm)
            elif code == b"Do":
                img_key = str(args[0]).lstrip("/")
                nome_final = nome_map.get(img_key, img_key)
                corners = [
                    (ctm[4], ctm[5]),
                    (ctm[0] + ctm[4], ctm[1] + ctm[5]),
                    (ctm[2] + ctm[4], ctm[3] + ctm[5]),
                    (ctm[0] + ctm[2] + ctm[4], ctm[1] + ctm[3] + ctm[5]),
                ]
                cy = (min(c[1] for c in corners) + max(c[1] for c in corners)) / 2.0
                images_ops.append((nome_final, cy))

        # Fallback para imagens declaradas que não passaram pelo fluxo de operadores.
        # Elas ficam no fim da página, pois não há posição disponível.
        names_found = {x[0] for x in images_ops}
        for i, img in enumerate(page.images, start=1):
            nome_completo = _nome_imagem(num_pag, i, img)
            if nome_completo not in names_found:
                images_ops.append((nome_completo, 0.0))

        # Processa cabeçalhos, resultados e imagens em uma única ordem de leitura.
        # Assim, uma imagem no topo de uma página de continuação permanece ligada
        # à questão anterior até que o próximo cabeçalho seja encontrado.
        eventos = (
            [(y, 0, numero, None) for numero, y in headers]
            + [(y, 1, None, None) for y in resultados]
            + [(y, 2, None, nome) for nome, y in images_ops]
        )
        for _, tipo, numero, nome in sorted(eventos, key=lambda evento: (-evento[0], evento[1])):
            if tipo == 0:
                questao_ativa = numero
                em_explicacao = False
            elif tipo == 1:
                em_explicacao = True
            elif questao_ativa is not None:
                destino = imagens_explicacao if em_explicacao else imagens_enunciado
                destino.setdefault(questao_ativa, []).append(nome)

    return imagens_enunciado, imagens_explicacao


def _extrair_gabarito(bloco, resultado, selecionada):
    """Obtém o gabarito pela alternativa marcada ou pela resposta explícita."""
    if resultado.group(1).lower() == "acertou":
        return selecionada

    padroes = (
        r"(?:alternativa|resposta)\s+correta\s*(?:(?:é|:)\s*)?"
        r"(?:a\s+)?(?:alternativa\s+)?(?:letra\s+)?\(?([A-E])\)?(?!\w)",
        r"gabarito\s*:\s*\(?([A-E])\)?(?!\w)",
    )
    for padrao in padroes:
        encontrado = re.search(padrao, bloco, re.IGNORECASE)
        if encontrado:
            return encontrado.group(1).upper()

    raise ValueError(
        "A questão foi marcada como incorreta, mas o PDF não informa "
        "explicitamente qual é a alternativa correta."
    )


def _parsear_questao(bloco, numero, imagens, imagens_explicacao):
    """Converte o bloco textual de uma questão em um registro JSON validado."""
    linha_cabecalho = bloco.find("\n")
    if linha_cabecalho < 0:
        raise ValueError(f"Questão {numero}: cabeçalho incompleto.")

    corpo = bloco[linha_cabecalho + 1:]
    corpo = re.sub(r"\bLer em voz alta\b", "", corpo, count=1)
    nota = re.search(r"\bNota\s*:\s*[\d.,]+", corpo, re.IGNORECASE)
    if not nota:
        raise ValueError(f"Questão {numero}: não foi encontrado o início das alternativas.")

    enunciado = _formatar_enunciado(corpo[:nota.start()])
    texto_opcoes = corpo[nota.end():]
    todos_marcadores = list(ALTERNATIVA_RE.finditer(texto_opcoes))
    esperado = list("ABCDE")
    marcadores = []
    idx = 0
    for m in todos_marcadores:
        if idx < len(esperado) and m.group(1) == esperado[idx]:
            marcadores.append(m)
            idx += 1
    if not enunciado or len(marcadores) < 2:
        raise ValueError(f"Questão {numero}: enunciado ou alternativas não reconhecidos.")
    letras = [marcador.group(1) for marcador in marcadores]
    if letras != list("ABCDE")[:len(letras)]:
        raise ValueError(f"Questão {numero}: alternativas duplicadas ou fora da ordem A–E.")

    selecionada = SELECIONADA_RE.search(texto_opcoes)
    resultado = RESULTADO_RE.search(texto_opcoes)
    if not selecionada or not resultado:
        raise ValueError(
            f"Questão {numero}: o PDF precisa indicar a alternativa selecionada "
            "e o resultado da correção."
        )

    indice_selecionada = next(
        (
            i for i, marcador in enumerate(marcadores)
            if marcador.start() < selecionada.start()
            and (i + 1 == len(marcadores) or marcadores[i + 1].start() > selecionada.start())
        ),
        None,
    )
    if indice_selecionada is None:
        raise ValueError(f"Questão {numero}: não foi possível localizar a alternativa selecionada.")

    gabarito = _extrair_gabarito(bloco, resultado, selecionada.group(1).upper())
    alternativas = {}
    for indice, marcador in enumerate(marcadores):
        proximo = marcadores[indice + 1].start() if indice + 1 < len(marcadores) else len(texto_opcoes)
        conteudo = texto_opcoes[marcador.end():proximo]
        if indice == indice_selecionada:
            conteudo = conteudo[:selecionada.start() - marcador.end()]
        alternativa = _limpar(conteudo)
        if not alternativa:
            raise ValueError(
                f"Questão {numero}: a alternativa {marcador.group(1)} está vazia."
            )
        alternativas[marcador.group(1)] = alternativa

    if gabarito not in alternativas:
        raise ValueError(f"Questão {numero}: o gabarito {gabarito} não corresponde a uma alternativa.")
    if selecionada.group(1).upper() not in alternativas:
        raise ValueError(f"Questão {numero}: a alternativa selecionada não foi encontrada.")

    proxima_alternativa = next(
        (marcador.start() for marcador in marcadores if marcador.start() > resultado.end()),
        len(texto_opcoes),
    )
    explicacao = _limpar(texto_opcoes[resultado.end():proxima_alternativa])
    return {
        "numero": numero,
        "enunciado": enunciado,
        "alternativas": alternativas,
        "gabarito": gabarito,
        "explicacao": explicacao,
        "imagens": imagens,
        "imagens_explicacao": imagens_explicacao,
    }


def _ler_questoes(pdf):
    """Lê questões e associa as imagens às seções e questões corretas."""
    leitor = PdfReader(str(pdf))
    imagens_enun, imagens_exp = _mapear_todas_imagens_espacial(leitor)

    textos_paginas = [
        page.extract_text(extraction_mode="layout") or ""
        for page in leitor.pages
    ]
    texto_completo = "\n".join(textos_paginas)
    cabecalhos = list(QUESTAO_RE.finditer(texto_completo))
    if not cabecalhos:
        raise ValueError("Nenhum enunciado de questão foi encontrado no PDF.")
    numeros = [int(cabecalho.group(1)) for cabecalho in cabecalhos]
    total_esperado = int(cabecalhos[0].group(2))
    if any(int(cabecalho.group(2)) != total_esperado for cabecalho in cabecalhos):
        raise ValueError("O PDF informa quantidades diferentes de questões nos cabeçalhos.")
    if numeros != list(range(1, total_esperado + 1)):
        raise ValueError(
            f"O PDF indica {total_esperado} questões, mas foram encontradas "
            f"{len(numeros)} ou a numeração está incompleta."
        )

    questoes = []
    for indice, cabecalho in enumerate(cabecalhos):
        fim = cabecalhos[indice + 1].start() if indice + 1 < len(cabecalhos) else len(texto_completo)
        bloco = texto_completo[cabecalho.start():fim]
        numero = int(cabecalho.group(1))
        imgs_enun = imagens_enun.get(numero, [])
        imgs_exp = imagens_exp.get(numero, [])
        questoes.append(_parsear_questao(bloco, numero, imgs_enun, imgs_exp))

    return questoes, bool(imagens_enun or imagens_exp)


def converter_pdf(pdf, sobrescrever=False):
    """Gera o JSON e extrai as imagens de um PDF."""
    pdf = Path(pdf)
    destino = pdf.with_suffix(".json")
    if destino.exists() and not sobrescrever:
        print(f"JSON já existe; PDF ignorado para evitar sobrescrita: {destino}")
        return False

    questoes, tem_imagens = _ler_questoes(pdf)
    pasta_imagens = pdf.parent / f"{pdf.stem}_imagens"
    leitor = PdfReader(str(pdf))
    arquivos_imagem = []

    for numero_pagina, pagina in enumerate(leitor.pages, start=1):
        for numero_imagem, imagem in enumerate(pagina.images, start=1):
            nome = _nome_imagem(numero_pagina, numero_imagem, imagem)
            arquivos_imagem.append((nome, imagem))

    if arquivos_imagem:
        pasta_imagens.mkdir(exist_ok=True)
        for nome, imagem in arquivos_imagem:
            imagem.image.save(pasta_imagens / nome)

    for questao in questoes:
        if questao.get("imagens"):
            questao["imagens"] = [
                f"{pasta_imagens.name}/{nome}" for nome in questao["imagens"]
            ]
        if questao.get("imagens_explicacao"):
            questao["imagens_explicacao"] = [
                f"{pasta_imagens.name}/{nome}" for nome in questao["imagens_explicacao"]
            ]

    with destino.open("w", encoding="utf-8") as arquivo:
        json.dump(questoes, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")

    print(f"JSON criado a partir do PDF: {destino}")
    if tem_imagens:
        print(f"Imagens extraídas para: {pasta_imagens}")
    return True


def converter_pdfs(sobrescrever=False):
    """Percorre as disciplinas e converte todos os PDFs."""
    if not PASTA_DADOS.is_dir():
        return

    for pasta_disciplina in sorted(PASTA_DADOS.iterdir(), key=lambda p: p.name.casefold()):
        if not pasta_disciplina.is_dir():
            continue
        pdfs = (
            arquivo for arquivo in pasta_disciplina.iterdir()
            if arquivo.is_file() and arquivo.suffix.lower() == ".pdf"
        )
        for pdf in sorted(pdfs, key=lambda p: p.name.casefold()):
            try:
                converter_pdf(pdf, sobrescrever=sobrescrever)
            except (OSError, PdfReadError, ValueError, NotImplementedError) as erro:
                raise RuntimeError(f"Falha ao converter {pdf}: {erro}") from erro


if __name__ == "__main__":
    converter_pdfs()
