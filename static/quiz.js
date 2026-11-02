/* ============================================================
   COMPORTAMENTO da página (o "cérebro" do quiz).
   Depende da variável DADOS, criada no quiz.html:
   DADOS = [ { nome: <disciplina>, quizzes: [ { titulo, perguntas }, ... ] }, ... ]
   Fluxo: monta menu -> cria os cartões das questões (escondidos)
   -> ao escolher um quiz, mostra só ele -> finalizar corrige tudo.
   ============================================================ */

/* ---------- Estado atual ---------- */
let discAtual = null;      // índice da disciplina em DADOS
let quizAtual = null;      // índice do quiz dentro da disciplina
const cartoes = {};        // mapa "disc-quiz" -> índices dos cartões dessa prova

/** Escapa texto antes de inseri-lo em HTML para evitar interpretação de marcação. */
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

/** Cria a chave usada para localizar os cartões do quiz selecionado. */
function chaveAtual() { return discAtual + '-' + quizAtual; }

/** Retorna os índices das questões pertencentes ao quiz selecionado. */
function questoesAtuais() {
  return cartoes[chaveAtual()] || [];
}

/* ---------- Criação dos cartões de questão ----------
   Percorre todas as disciplinas/quizzes e cria um .questao para
   cada pergunta. Todos nascem escondidos; iniciar() revela os
   do quiz escolhido. Cada input radio usa name=q<índice global>. */
/** Cria no DOM os cartões de todas as questões e os mantém agrupados por quiz. */
function montarCartoes() {
  let i = 0;
  DADOS.forEach(function(d, di) {
    d.quizzes.forEach(function(qz, zi) {
      const indices = [];
      qz.perguntas.forEach(function(q) {
        const card = document.createElement('div');
        card.className = 'questao';
        card.id = 'card-' + i;
        card.style.display = 'none';
        card.dataset.disc = di;
        card.dataset.quiz = zi;

        let opcoes = '';
        Object.keys(q.alternativas).forEach(function(k) {
          opcoes += '<label class="opcao"><input type="radio" name="q' + i + '" value="' + k + '">' +
                    '<span><b>' + k + ')</b> ' + q.alternativas[k] + '</span></label>';
        });

        card.innerHTML = '<p class="enunciado"><span class="rotulo">Quest\u00e3o ' + (indices.length + 1) + '</span>' + q.enunciado + '</p>' +
                         opcoes + '<div class="feedback"></div>';
        (q.imagens || []).forEach(function(src) {
          const imagem = document.createElement('img');
          imagem.className = 'imagem-questao';
          imagem.src = src;
          imagem.alt = 'Imagem da questão';
          imagem.loading = 'lazy';
          card.insertBefore(imagem, card.querySelector('.opcao'));
        });
        document.getElementById('lista').appendChild(card);
        indices.push(i);
        i++;
      });
      cartoes[di + '-' + zi] = indices;
    });
  });
}

/* ---------- Menu inicial ----------
   Gera um bloco (.grupo-menu) por disciplina com um botão por quiz,
   mostrando a quantidade de questões de cada um. */
/** Monta o menu inicial com um botão para cada avaliação disponível. */
function montarMenu() {
  const host = document.getElementById('opcoes-menu');
  DADOS.forEach(function(d, di) {
    const grupo = document.createElement('div');
    grupo.className = 'grupo-menu';
    const h3 = document.createElement('h3');
    h3.textContent = d.nome;
    grupo.appendChild(h3);

    d.quizzes.forEach(function(qz, zi) {
      const btn = document.createElement('button');
      btn.className = 'btn-apol';
      btn.innerHTML = esc(qz.titulo) + '<span>' + qz.perguntas.length + ' quest\u00f5es</span>';
      btn.addEventListener('click', function() { iniciar(di, zi); });
      grupo.appendChild(btn);
    });

    host.appendChild(grupo);
  });
}

/* ---------- Iniciar um quiz ----------
   Esconde o menu, mostra a barra de ações e apenas as questões
   da prova escolhida. Rola para o topo. */
/** Prepara e exibe a avaliação escolhida pelo usuário. */
function iniciar(di, zi) {
  discAtual = di;
  quizAtual = zi;
  document.getElementById('menu').style.display = 'none';
  document.getElementById('barra').style.display = 'flex';
  document.getElementById('titulo-atual').textContent = ' — ' + DADOS[di].nome + ' — ' + DADOS[di].quizzes[zi].titulo;

  questoesAtuais().forEach(function(i) {
    document.getElementById('card-' + i).style.display = 'block';
  });

  atualizarProgresso();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ---------- Progresso: "X de Y respondidas" ---------- */
/** Recalcula a quantidade de respostas marcadas e atualiza o indicador no topo. */
function atualizarProgresso() {
  const qs = questoesAtuais();
  let marcadas = 0;
  qs.forEach(function(i) {
    if (document.querySelector('input[name=q' + i + ']:checked')) marcadas++;
  });
  document.getElementById('progresso').textContent = marcadas + ' de ' + qs.length + ' respondidas';
}

/* ---------- Marcação das alternativas ----------
   Aplica .selecionada na label clicada e remove das outras da mesma questão. */
document.addEventListener('change', function(e) {
  if (e.target && e.target.type === 'radio' && e.target.name.startsWith('q')) {
    const card = e.target.closest('.questao');
    card.querySelectorAll('.opcao').forEach(function(o) { o.classList.remove('selecionada'); });
    e.target.closest('.opcao').classList.add('selecionada');
    atualizarProgresso();
  }
});

/* ---------- Finalizar: confere respostas e dá a nota ---------- */
document.getElementById('btn-finalizar').addEventListener('click', function() {
  const qs = questoesAtuais();
  const perguntas = DADOS[discAtual].quizzes[quizAtual].perguntas;

  // exige que tudo esteja respondido antes de corrigir
  const faltando = qs.filter(function(i) {
    return !document.querySelector('input[name=q' + i + ']:checked');
  });
  if (faltando.length) {
    alert('Ainda existem ' + faltando.length + ' quest\u00e3o(\u00f5es) sem resposta. Responda todas antes de finalizar.');
    document.getElementById('card-' + faltando[0]).scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }

  let pontos = 0;
  qs.forEach(function(i, n) {
    const q = perguntas[n];
    const escolha = document.querySelector('input[name=q' + i + ']:checked').value;
    const card = document.getElementById('card-' + i);
    card.querySelectorAll('input').forEach(function(inp) { inp.disabled = true; });
    const fb = card.querySelector('.feedback');

    const imgsExp = q.imagens_explicacao || [];
    let htmlImgsExp = '';
    if (imgsExp.length) {
      htmlImgsExp = '<div class="bloco-imagens-feedback">' +
        imgsExp.map(function(src) {
          return '<img class="imagem-questao imagem-feedback" src="' + src + '" alt="Resolução da questão" loading="lazy">';
        }).join('') +
        '</div>';
    }

    if (escolha === q.gabarito) {
      pontos++;
      card.classList.add('correto');
      fb.className = 'feedback ok';
      let msg = '<b>Correto!</b>';
      if (q.explicacao) {
        msg += '<div class="detalhe-explicacao"><b>Justificativa:</b><br>' + esc(q.explicacao) + '</div>';
      }
      fb.innerHTML = msg + htmlImgsExp;
    } else {
      card.classList.add('incorreto');
      fb.className = 'feedback dica';
      let msg = '<b>Incorreta.</b>';
      if (q.explicacao) {
        msg += '<br>Dica: ' + esc(q.explicacao);
      }
      fb.innerHTML = msg + htmlImgsExp;
    }
  });

  const pct = Math.round((pontos / qs.length) * 100);
  const banner = document.getElementById('resultado');
  banner.textContent = 'Voc\u00ea acertou ' + pontos + ' de ' + qs.length +
                       ' quest\u00f5es (' + pct + '%).' +
                       (pct === 100 ? ' Perfeito!' : ' As quest\u00f5es incorretas receberam uma dica.');
  banner.style.display = 'block';

  document.getElementById('btn-finalizar').disabled = true;
  document.getElementById('btn-refazer').style.display = 'inline-block';

  banner.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

/* ---------- Limpeza: restaura o estado dos cartões da avaliação atual ---------- */
/** Limpa marcações, feedback e controles da avaliação atual; se esconder=true, oculta os cartões. */
function limparQuizAtual(esconder) {
  questoesAtuais().forEach(function(i) {
    const card = document.getElementById('card-' + i);
    if (esconder) card.style.display = 'none';
    card.classList.remove('correto', 'incorreto');
    const fb = card.querySelector('.feedback');
    fb.className = 'feedback';
    fb.textContent = '';
    card.querySelectorAll('.opcao').forEach(function(o) { o.classList.remove('selecionada'); });
    card.querySelectorAll('input').forEach(function(inp) { inp.disabled = false; inp.checked = false; });
  });
  document.getElementById('resultado').style.display = 'none';
  document.getElementById('btn-finalizar').disabled = false;
  document.getElementById('btn-refazer').style.display = 'none';
}

/* ---------- Menu: volta à tela inicial sem recarregar a página ---------- */
document.getElementById('btn-menu').addEventListener('click', function() {
  limparQuizAtual(true);
  discAtual = null;
  quizAtual = null;
  document.getElementById('barra').style.display = 'none';
  document.getElementById('titulo-atual').textContent = '';
  document.getElementById('progresso').textContent = '';
  document.getElementById('menu').style.display = 'flex';
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

/* ---------- Refazer: limpa as respostas deste quiz ---------- */
document.getElementById('btn-refazer').addEventListener('click', function() {
  limparQuizAtual(false);
  atualizarProgresso();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

/* ---------- Atualizar: converte PDFs novos e recarrega os dados ---------- */
let recarregandoPagina = false;

document.getElementById('btn-atualizar').addEventListener('click', function() {
  const botao = this;
  const carregamento = document.getElementById('carregamento-atualizacao');
  const mensagem = document.getElementById('mensagem-atualizacao');

  if (window.location.protocol === 'file:') {
    carregamento.classList.add('visivel', 'erro');
    mensagem.textContent = 'Aviso: Para atualizar PDFs novos, inicie pelo scripts/Iniciar Quiz.bat ou acesse http://127.0.0.1:5000';
    return;
  }

  botao.disabled = true;
  carregamento.classList.add('visivel');
  mensagem.textContent = 'Convertendo PDFs novos...';

  fetch('/atualizar', { method: 'POST' })
    .then(function(resposta) {
      return resposta.json().then(function(dados) {
        if (!resposta.ok || !dados.sucesso) {
          throw new Error(dados.erro || 'Não foi possível atualizar os dados.');
        }
        return dados;
      });
    })
    .then(function() {
      mensagem.textContent = 'Atualização concluída. Carregando perguntas...';
      recarregandoPagina = true;
      window.location.reload();
    })
    .catch(function(erro) {
      botao.disabled = false;
      mensagem.textContent = 'Erro: ' + erro.message;
      carregamento.classList.add('erro');
    });
});

function acompanharGeracao(id) {
  const form = document.getElementById('form-apostila');
  const mensagem = document.getElementById('mensagem-apostila');
  const progresso = document.getElementById('progresso-apostila');
  const barra = progresso.querySelector('span span');
  const percentual = document.getElementById('percentual-apostila');
  const botao = form.querySelector('button[type=submit]');
  botao.disabled = true;
  progresso.classList.add('visivel');
  function consultar() {
    fetch('/gerar-apostila/' + encodeURIComponent(id))
          .then(function(resposta) {
            return resposta.json().then(function(status) {
              if (!resposta.ok || !status.sucesso) {
                throw new Error(status.erro || 'Não foi possível consultar a geração.');
              }
              return status;
            });
          })
          .then(function(status) {
            barra.style.width = status.percentual + '%';
            percentual.textContent = status.percentual + '%';
            mensagem.textContent = status.mensagem;
            if (status.estado === 'processando') {
              window.setTimeout(consultar, 1500);
              return;
            }
            if (status.estado === 'erro') {
              window.localStorage.removeItem('geracaoApostilaId');
              throw new Error(status.mensagem);
            }
            window.localStorage.removeItem('geracaoApostilaId');
            botao.disabled = false;
            mensagem.textContent = status.mensagem + ' Clique em Menu e depois em Atualizar.';
          })
          .catch(function(erro) {
            botao.disabled = false;
            mensagem.textContent = 'Erro: ' + erro.message;
          });
  }
  consultar();
}

document.getElementById('form-apostila').addEventListener('submit', function(e) {
  e.preventDefault();
  const form = e.target;
  const mensagem = document.getElementById('mensagem-apostila');
  const botao = form.querySelector('button[type=submit]');
  botao.disabled = true;
  mensagem.textContent = 'Enviando a apostila... Você pode abrir outro questionário pelo Menu.';
  fetch('/gerar-apostila', { method: 'POST', body: new FormData(form) })
    .then(function(resposta) {
      return resposta.json().then(function(dados) {
        if (!resposta.ok || !dados.sucesso) {
          throw new Error(dados.erro || 'Não foi possível gerar as perguntas.');
        }
        return dados;
      });
    })
    .then(function(dados) {
      window.localStorage.setItem('geracaoApostilaId', dados.id);
      acompanharGeracao(dados.id);
    })
    .catch(function(erro) {
      botao.disabled = false;
      mensagem.textContent = 'Erro: ' + erro.message;
    });
});

/* ---------- Inicialização ---------- */
montarMenu();
montarCartoes();

const disciplinaApostila = document.getElementById('disciplina-apostila');
const apostilaDisponivel = document.getElementById('apostila-disponivel');
const tituloApostila = document.getElementById('titulo-apostila');
let apostilasPorDisciplina = {};

fetch('/apostilas-disponiveis')
  .then(function(resposta) {
    if (!resposta.ok) throw new Error('Não foi possível carregar as apostilas.');
    return resposta.json();
  })
  .then(function(dados) {
    disciplinaApostila.innerHTML = '<option value="">Selecione a disciplina</option>';
    dados.disciplinas.forEach(function(item) {
      apostilasPorDisciplina[item.nome] = item.apostilas;
      disciplinaApostila.appendChild(new Option(item.nome, item.nome));
    });
  })
  .catch(function(erro) {
    disciplinaApostila.innerHTML = '<option value="">Erro ao carregar apostilas</option>';
    document.getElementById('mensagem-apostila').textContent = erro.message;
  });

disciplinaApostila.addEventListener('change', function() {
  const arquivos = apostilasPorDisciplina[this.value] || [];
  apostilaDisponivel.innerHTML = '<option value="">Selecione a apostila</option>';
  apostilaDisponivel.disabled = !arquivos.length;
  arquivos.forEach(function(item) {
    apostilaDisponivel.appendChild(new Option(item.nome, item.arquivo));
  });
  tituloApostila.value = '';
});

apostilaDisponivel.addEventListener('change', function() {
  if (!tituloApostila.value && this.selectedOptions[0]) {
    tituloApostila.value = 'Quiz - ' + this.selectedOptions[0].textContent;
  }
});

fetch('/configuracao-ia')
  .then(function(resposta) { return resposta.ok ? resposta.json() : null; })
  .then(function(configuracao) {
    if (!configuracao || !configuracao.sucesso) return;
    const provedor = document.getElementById('provedor-ia');
    const chave = document.getElementById('chave-api');
    provedor.value = configuracao.provedor;
    chave.value = configuracao.chave_api || '';
    provedor.addEventListener('change', function() {
      chave.value = (configuracao.chaves || {})[provedor.value] || '';
    });
  })
  .catch(function() {});

const geracaoSalva = window.localStorage.getItem('geracaoApostilaId');
if (geracaoSalva) {
  acompanharGeracao(geracaoSalva);
}


/* ---------- Batimento cardíaco: mantém o servidor ativo enquanto a página estiver aberta ---------- */
if (window.location.protocol !== 'file:') {
  function enviarPing() {
    fetch('/ping', { method: 'POST' }).catch(function() {});
  }
  setInterval(enviarPing, 3000);
  enviarPing();

  window.addEventListener('pagehide', function() {
    if (!recarregandoPagina && navigator.sendBeacon) {
      navigator.sendBeacon('/sair');
    }
  });
}
