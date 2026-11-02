# Sistema de Exercícios — Faculdade

Aplicação local para treinar APOLs e avaliações no navegador. O sistema lê
PDFs corrigidos, transforma as questões em JSON, extrai imagens e monta um
quiz interativo com correção, gabarito e explicações.

## Antes de começar: o que instalar

O sistema foi preparado para Windows. Instale os itens abaixo **antes de executar o quiz**:

1. **Python 3.10 ou superior**, disponível no site oficial:
   [python.org/downloads](https://www.python.org/downloads/).
   Durante a instalação, marque **Add Python to PATH**.
2. Um navegador moderno, como Microsoft Edge, Google Chrome ou Firefox.
3. O projeto completo, mantendo a estrutura de pastas original.

Não é necessário instalar Node.js, banco de dados ou um servidor web externo.
As bibliotecas Python usadas pelo projeto são instaladas no passo seguinte.

## Instalação automática

O arquivo `scripts\Iniciar Quiz.bat` prepara o ambiente automaticamente antes
de abrir o sistema. Na primeira execução, ele mostra o progresso enquanto:

1. verifica ou instala o Python pelo Windows Package Manager (`winget`);
2. cria o ambiente virtual `.venv`;
3. instala as dependências de `requirements.txt`;
4. inicia o servidor e abre o quiz no navegador.

Essa preparação pode demorar na primeira execução, principalmente por causa do
download do Python, das dependências e do modelo de IA. Nas próximas execuções,
os itens já instalados serão reutilizados.

A geração por apostila usa uma chave do Google Gemini informada no formulário.
Essa chave não é gravada no projeto.

## Instalação manual (alternativa)

Abra o PowerShell ou o Prompt de Comando na pasta raiz do projeto
(`quiz_v2.0`) e execute:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O ambiente `.venv` é opcional, mas recomendado. O arquivo
`scripts/Iniciar Quiz.bat` detecta esse ambiente automaticamente. Se o
comando `python` não for reconhecido, reinstale o Python marcando **Add Python
to PATH** ou use o caminho completo do executável.

## Como usar

### Iniciar o quiz

1. Abra a pasta do projeto no Explorador de Arquivos.
2. Entre em `scripts`.
3. Dê dois cliques em **Iniciar Quiz.bat**.
4. Aguarde o navegador abrir em `http://127.0.0.1:5000`.
5. Escolha a disciplina e a APOL desejada.
6. Responda todas as questões e clique em **Finalizar**.

Na inicialização, o sistema procura PDFs ainda não convertidos, gera os JSONs,
extrai as imagens e atualiza a página. O terminal pode aparecer por alguns
instantes e será ocultado pelo próprio programa.

Para atualizar o conteúdo enquanto o quiz já está aberto, coloque os novos
arquivos na pasta `dados` e clique no botão **Atualizar** no topo da página.

### Encerrar o sistema

Ao fechar a aba ou o navegador, o servidor normalmente encerra sozinho após
alguns segundos.
Para encerrar manualmente, dê dois cliques em **scripts/Encerrar Quiz.bat**.

## Como criar um atalho com ícone

O ícone deve ser configurado no **atalho do Windows**, não no arquivo `.bat`
diretamente:

1. Abra a pasta `scripts`.
2. Clique com o botão direito em **Iniciar Quiz.bat**.
3. Selecione **Mostrar mais opções > Enviar para > Área de trabalho (criar
   atalho)**.
4. Na Área de Trabalho, clique com o botão direito no atalho criado e escolha
   **Propriedades**.
5. Na aba **Atalho**, clique em **Alterar ícone...**.
6. Clique em **Procurar...** e selecione
   `icone\quiz.ico` dentro da pasta do projeto.
7. Confirme com **OK > Aplicar > OK**.

Depois disso, basta usar o atalho da Área de Trabalho para iniciar o quiz.
O ícone exibido na aba do navegador também é definido pelo arquivo
`icone\quiz.ico`.

## Como adicionar uma disciplina ou APOL

1. Crie uma pasta em `dados` com o nome da disciplina. Exemplo:
   `dados\Banco de Dados Relacional`.
2. Salve nela o PDF da avaliação corrigida. Exemplo:
   `dados\Banco de Dados Relacional\Apol 1.pdf`.
3. Salve o PDF a partir da tela de revisão do AVA/Univirtus, usando
   **Ctrl+P > Salvar como PDF**. O PDF deve conter texto selecionável, as
   alternativas, a alternativa selecionada e o resultado da correção.
4. Inicie o sistema ou clique em **Atualizar** no quiz aberto.

O conversor criará automaticamente:

- o JSON com as questões, alternativas, gabarito e explicações;
- a pasta `<nome da APOL>_imagens`, com as figuras extraídas;
- a página `quiz.html`, com os dados prontos para o navegador.

Não edite os JSONs gerados enquanto o PDF original estiver disponível: ao
regenerar, eles serão substituídos pelo conteúdo extraído do PDF.

## Como gerar perguntas de uma apostila

O sistema também pode criar um conjunto de 10 perguntas de múltipla escolha
usando uma apostila em PDF e uma API de IA. Estão disponíveis
[Google Gemini](https://ai.google.dev/) e [OpenAI](https://platform.openai.com/).
O texto extraído da apostila é enviado ao provedor escolhido e está sujeito às
cotas e regras da conta do usuário.

### Geração

1. Crie uma chave no Google AI Studio ou na plataforma OpenAI.
2. Inicie o quiz pelo `scripts\Iniciar Quiz.bat`.
3. No menu inicial, localize **Gerar perguntas por apostila**.
4. Organize as apostilas em `apostilas\<disciplina>`, por exemplo
   `apostilas\Banco de Dados\Capitulo 1.pdf`.
5. No formulário, selecione a disciplina e uma das apostilas disponíveis.
   Disciplinas com o mesmo nome, mesmo que tenham acentos ou separadores
   diferentes, aparecem agrupadas em um único grupo. Por exemplo, `Pré-Cálculo`
   e `Pre Calculo` serão exibidas juntas.
   Variações como `Banco de Dados` também são agrupadas em
   `Banco de Dados Relacional`.
6. Informe o nome do conjunto, escolha o provedor e informe a chave da API.
   A chave usada fica salva localmente para as próximas gerações.
   Para usar outra conta ou outro provedor, escolha-o e informe a nova chave.
7. Clique em **Gerar perguntas** e acompanhe a barra de progresso. Durante a
   geração, clique em **Menu** no rodapé para abrir qualquer questionário já
   pronto; o processamento continuará em segundo plano.

O novo conjunto aparece no grupo da disciplina selecionada como um quiz comum.
A apostila original fica em `apostilas`, e as perguntas geradas ficam em
`dados/<disciplina>`. Quando a
barra chegar a 100%, clique em **Menu** e depois em **Atualizar** para carregar
o novo conjunto. Se a página for recarregada durante a geração, o progresso é
retomado automaticamente.
Como o conteúdo é gerado por inteligência artificial, revise as perguntas antes
de usá-las.

As chaves ficam em `configuracao_ia.json`, somente no computador local. Esse
arquivo é ignorado pelo Git e não deve ser compartilhado. O servidor cria um
token temporário a cada execução e protege as operações de atualização e
geração contra requisições externas à página local.

## Estrutura principal

```text
quiz_v2.0/
├── dados/              PDFs, JSONs e imagens das disciplinas
├── apostilas/           fontes das apostilas usadas na geração por IA
├── docs/               documentação técnica
├── módulos/            conversão, leitura e geração dos dados
├── scripts/             inicialização e encerramento no Windows
├── static/              CSS e JavaScript da interface
├── templates/           modelo HTML
├── icone/               ícone do sistema
├── configuracao_ia.json configurações locais das APIs (não compartilhar)
├── main.py              servidor Flask local
├── requirements.txt     dependências Python
└── quiz.html            página gerada automaticamente
```

## Documentação técnica

Detalhes sobre arquitetura, fluxo de conversão, formato dos dados, rotas
locais e manutenção estão em
[docs/ARQUITETURA-E-FLUXO.md](docs/ARQUITETURA-E-FLUXO.md).

## Solução rápida de problemas

- **O navegador não abriu:** acesse manualmente
  `http://127.0.0.1:5000` após iniciar o `.bat`.
- **`python` não foi encontrado:** reinstale o Python com **Add Python to
  PATH** habilitado.
- **Erro de biblioteca:** execute novamente
  `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- **Uma APOL não apareceu:** confirme que o PDF está dentro de uma subpasta de
  `dados` e clique em **Atualizar**.
- **Uma imagem está incorreta:** confira se o PDF foi salvo pela tela de
  revisão/correção do AVA e gere novamente pelo botão **Atualizar**.
- **Erro HTTP 503 ao gerar perguntas:** o modelo Gemini está temporariamente
  sobrecarregado. O sistema tenta novamente automaticamente e tenta modelos
  alternativos; se o erro persistir, aguarde alguns minutos e repita a geração.
- **Não foi possível conectar à API:** verifique a internet, proxy, firewall e
  se o endereço `generativelanguage.googleapis.com` está acessível. A mensagem
  exibida agora informa a causa técnica da conexão quando o Windows fornecê-la.
