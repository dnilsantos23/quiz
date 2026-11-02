# Documentação técnica

## Visão geral

O sistema é uma aplicação Python/Flask executada localmente. Os PDFs são a
fonte de dados. Durante a inicialização, o conversor extrai texto, alternativas,
gabarito, explicações e imagens; depois o gerador embute os dados no
`quiz.html`, que é servido pelo Flask.

Não existe banco de dados. Os arquivos em `dados/` funcionam como persistência
do sistema.

## Componentes

| Componente | Responsabilidade |
|---|---|
| `main.py` | Inicia o Flask, serve a página e imagens, atualiza os dados e monitora o navegador. |
| `módulos/pdf_para_json.py` | Lê PDFs, identifica questões, extrai imagens e cria JSONs. |
| `módulos/quiz_dados.py` | Varre `dados/` e carrega disciplinas, APOLs e perguntas. |
| `módulos/exercicios_web.py` | Formata textos, codifica URLs de imagens e gera `quiz.html`. |
| `templates/quiz.html` | Modelo HTML que recebe a variável `DADOS`. |
| `static/quiz.js` | Monta o menu e cartões, corrige respostas e exibe explicações. |
| `static/estilo.css` | Estilos da interface. |
| `scripts/*.bat` | Atalhos de inicialização e encerramento no Windows. |
| `módulos/apostila_ia.py` | Extrai texto de apostilas e solicita perguntas à API Gemini. |

## Preparação automática do ambiente

O `scripts/Iniciar Quiz.bat` é idempotente: verifica o Python, cria `.venv` e
instala `requirements.txt` antes de iniciar o servidor. A geração por apostila
usa Gemini sob demanda e não exige processo local adicional.

## Fluxo de execução

1. `scripts/Iniciar Quiz.bat` muda para a raiz do projeto e executa
   `main.py`, preferindo `.venv\Scripts\python.exe` quando ele existe.
2. `main.py` verifica se a porta `5000` está livre.
3. `exercicios_web.gerar(converter_arquivos=True)` chama
   `pdf_para_json.converter_pdfs()`.
4. O conversor percorre cada PDF em `dados/<disciplina>/`.
5. Para cada PDF, cria `<arquivo>.json` e `<arquivo>_imagens/`.
6. `quiz_dados.carregar_tudo()` lê os JSONs e monta a estrutura de disciplinas.
7. `exercicios_web` escapa o texto, codifica os caminhos e substitui
   `__DATA__` no template.
8. O Flask serve `quiz.html` em `/` e imagens em `/dados/<arquivo>`.

## Geração por apostila

O formulário da tela inicial seleciona um PDF em `apostilas/<disciplina>/` e
envia seu caminho relativo e uma chave temporária para `POST /gerar-apostila`.
O servidor valida o caminho dentro de `apostilas/`, cria uma tarefa em segundo
plano e responde imediatamente com um identificador. A interface consulta
`GET /gerar-apostila/<id>` para atualizar a barra de progresso, sem bloquear a
navegação para questionários já existentes. A tarefa extrai até 40.000
caracteres de texto, envia um prompt estruturado ao Gemini e valida exatamente 10 questões com
alternativas A-E e um único gabarito. Respostas HTTP 429 e 503 são repetidas
automaticamente até três vezes, com espera progressiva e respeito ao cabeçalho
`Retry-After`. Se o modelo principal continuar indisponível, são tentados
modelos Gemini de reserva. O provedor também pode ser OpenAI, usando o endpoint
de chat completions e o modelo `gpt-4o-mini`.

Falhas de rede são repetidas e, quando persistem, retornam a causa fornecida
pelo sistema operacional, facilitando identificar DNS, timeout, proxy ou firewall.

As chaves são armazenadas por provedor em `configuracao_ia.json`, que é ignorado
pelo Git. O endpoint `GET /configuracao-ia` preenche o formulário localmente,
permitindo alternar entre provedores sem expor as chaves ao navegador. A cada
execução, o servidor cria um token efêmero; as rotas que alteram dados exigem
esse token e uma origem local válida.

A chave Gemini é enviada no cabeçalho `x-goog-api-key`, e a chave OpenAI no
cabeçalho `Authorization`; nenhuma delas é colocada na URL.

O identificador da tarefa é mantido no navegador durante a geração. Assim, um
recarregamento causado pelo botão **Atualizar** não perde o acompanhamento. O
monitor de inatividade mantém o processo Flask ativo enquanto houver uma
geração em andamento, e a regeneração do `quiz.html` usa um bloqueio para não
concorrer com o salvamento do questionário.

As fontes são armazenadas em `apostilas/`, fora da pasta varrida pelo conversor
de APOLs. O JSON gerado é salvo em `dados/<disciplina>/` e a página é
regenerada. É necessária uma chave do provedor escolhido somente para gerar
perguntas por apostila.

As pastas de dados são agrupadas ignorando acentos, caixa e separadores. Assim,
pastas como `Pré-Cálculo` e `Pre Calculo` formam uma única disciplina na
interface. Cada quiz conserva sua pasta física de origem para que as imagens
continuem apontando para o local correto.
Variações de `Banco de Dados` também são direcionadas para
`Banco de Dados Relacional`.

## Mapeamento de imagens

O conversor calcula a posição vertical dos cabeçalhos, dos resultados
(`Você acertou!`/`Você errou!`) e das imagens incorporadas no PDF. Esses eventos
são processados em ordem de leitura, mantendo a questão ativa entre páginas.

- Antes do resultado: a imagem vai para `imagens`.
- Depois do resultado: a imagem vai para `imagens_explicacao`.
- O cabeçalho da próxima questão encerra a associação com a questão anterior.

Esse estado entre páginas é importante porque uma questão pode começar em uma
página e terminar em outra.

## Formato dos dados

Cada JSON contém uma lista de objetos:

```json
[
  {
    "numero": 1,
    "enunciado": "Texto da questão",
    "alternativas": {
      "A": "Primeira alternativa",
      "B": "Segunda alternativa"
    },
    "gabarito": "B",
    "explicacao": "Justificativa",
    "imagens": ["Apol 1_imagens/pagina-002-imagem-01.png"],
    "imagens_explicacao": []
  }
]
```

Os caminhos são relativos à pasta da disciplina. Na geração do HTML, eles são
convertidos para URLs `/dados/...` e codificados para suportar espaços e
acentos.

## Rotas Flask

| Método e rota | Função |
|---|---|
| `GET /` | Entrega o `quiz.html` sem cache. |
| `GET /dados/<arquivo>` | Serve imagens e arquivos estáticos da pasta `dados`. |
| `GET /icone/<arquivo>` | Serve arquivos da pasta `icone`. |
| `GET /favicon.ico` | Serve `icone/quiz.ico`. |
| `POST /atualizar` | Converte PDFs pendentes e regenera o HTML. |
| `GET /apostilas-disponiveis` | Lista PDFs organizados por disciplina para o formulário. |
| `GET /configuracao-ia` | Carrega as configurações locais dos provedores de IA. |
| `GET /gerar-apostila/<id>` | Consulta o estado e o progresso da geração em segundo plano. |
| `POST /ping` | Mantém o servidor informado de que a página está aberta. |
| `POST /sair` | Agenda a verificação de encerramento após o fechamento da página. |

## Manutenção e validação

Após alterar o conversor ou o gerador:

```powershell
python -m py_compile .\módulos\pdf_para_json.py .\módulos\exercicios_web.py .\main.py
```

Para regenerar todos os JSONs existentes a partir dos PDFs, use explicitamente
o conversor com sobrescrita:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'módulos'); import pdf_para_json; pdf_para_json.converter_pdfs(sobrescrever=True)"
```

Depois, regenere a página:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'módulos'); import exercicios_web; exercicios_web.gerar(converter_arquivos=False)"
```

O botão **Atualizar** usa o modo padrão, que não sobrescreve JSONs já
existentes. Isso evita perda acidental de edições manuais, mas significa que
um PDF alterado precisa ter seu JSON removido ou ser regenerado explicitamente.
