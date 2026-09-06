#!/usr/bin/env bash
# portoes.sh — A LISTA DE PORTÕES DESTA CASA, e ela é UMA SÓ.
#
# POR QUE ELE EXISTE, e o defeito é medido: até 25/08/2026 a lista de portões
# vivia em DOIS lugares — o bloco "Antes de fechar qualquer leva" do `CLAUDE.md`
# e os jobs do `.github/workflows/ci.yml`. Duas listas para a mesma coisa é o
# defeito que a regra do fato-errado existe para matar, e ele COBROU: o
# `validar-caducos.py` roda no CI e NÃO estava no bloco local, e foi assim que
# um literal caduco atravessou uma leva inteira e só apareceu no vermelho do CI.
#
# A partir daqui a lista mora AQUI, em `_LISTA`, versionada e viajando junto com
# toda árvore de agente. O `CLAUDE.md` não é versionado (`.gitignore:90`), então
# ele não pode ser a fonte: um worktree de agente nasce sem ele.
#
# E A LISTA TEM PORTÃO PRÓPRIO: `tests/unit/test_portao_a_lista_de_portoes_e_uma_so.py`
# compara esta tabela com o que o `ci.yml` roda e REPROVA na divergência. Quem
# acrescentar um job ao CI sem acrescentar a linha aqui é barrado nomeando o
# script que ficou de fora — que é exatamente o caso do `validar-caducos.py`,
# agora impossível de repetir.
#
# PORTÃO DECLARADO E AUSENTE DA ÁRVORE SAI rc=1 NOMEANDO, nunca em silêncio.
# É a cicatriz do `validar-acentuacao.py --check-file`, que devolvia rc=0 contra
# arquivo que não existe: portão cego é pior que portão nenhum.
#
# Uso:
#   scripts/portoes.sh              a leva inteira (rápidos + completos)
#   scripts/portoes.sh --rapido     só a camada rápida (~6 s)
#   scripts/portoes.sh --suite      acrescenta a suíte de testes
#   scripts/portoes.sh --listar     a tabela crua, que é o que o portão do portão lê
#   scripts/portoes.sh --interpretador  só o cabeçalho: qual python, e o que falta nele
#
# O INTERPRETADOR SE DECLARA. A casa já pagou por medir contra a biblioteca
# errada — "todo instrumento tem de declarar qual biblioteca está usando" — e
# `gerar-tabela-de-curvas.py --check` quebra com `ModuleNotFoundError: pydantic`
# no `python3` pelado e passa no `.venv`. Aqui há UM python para todo portão de
# python, e ele sai impresso no cabeçalho da execução.
set -uo pipefail

RAIZ="$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(dirname "$(readlink -f "$0")")")"

# ---------------------------------------------------------------------------
# A TABELA. Colunas: camada|id|runner|argumentos
#
#   camada   rapido   | completo  | suite
#   runner   py (o python resolvido) | bash | bin (binário do venv, senão PATH)
#
# Tempos medidos nesta árvore em 25/08/2026, `dev` em f475b2a, e é por eles que
# a camada rápida existe: `validar-acentuacao.py --all` sozinho custa 38 s e o
# `shellcheck` sobre o `install.sh` de 219 KB custa 11,4 s -- os dois juntos são
# oito vezes a camada rápida inteira, que fechava em 5,3 s com QUINZE portões.
# CONTAGEM CORRIGIDA em 29/08/2026 — o tempo é de 25/08 e fica com a data dele;
# a contagem envelheceu e virava número errado: hoje a tabela tem 21 `rapido` e
# 7 `completo` (28 no `portoes.sh` sem argumento), mais 1 `suite`. Quem mexer
# aqui conta de novo: `grep -cE '^rapido\|' scripts/portoes.sh`.
# ---------------------------------------------------------------------------
_LISTA() {
  cat <<'TABELA'
rapido|contrato-ipc|py|scripts/gerar-contrato-ipc.py --check
# 31/08/2026, decisão dela: este portão passou a cobrir também as planilhas de
# `docs/data/` — o mapa carregava 762 citações `arquivo:linha` e NENHUMA tinha
# portão. Nasce em zero (nenhuma aponta além do fim hoje), e continua na camada
# rápida porque o preço foi medido: 33 ms só `docs/protocol/`, 101 ms com o
# mapa, o caderno e as decisões dela juntos -- 903 citações conferidas.
rapido|citacoes-de-linha|py|scripts/validar-citacoes-de-linha.py --all
rapido|mapa-de-canais|py|scripts/gerar-mapa.py --check
rapido|fatos-de-tela|py|scripts/gerar-fatos-de-tela.py --check
rapido|fala-de-tela|py|scripts/validar-fala-de-tela.py --all
rapido|caducos|py|scripts/validar-caducos.py --all
rapido|palavra-de-tela|py|scripts/validar-palavra-de-tela.py --all
rapido|version-consistency|py|scripts/check_version_consistency.py
rapido|curvas|py|scripts/gerar-tabela-de-curvas.py --check
# 25/08/2026: a página das frases de tela é gerada de um JSON versionado.
# Sem este portão, o HTML publicado e o dado divergiriam em silêncio — e o que
# ela abre para decidir passaria a mostrar uma lista que já não é a do disco.
rapido|frases-de-tela|py|scripts/gerar-frases-de-tela.py --check
rapido|paridade-transporte|py|scripts/check_paridade_transporte.py
# 03/09/2026: O TERCEIRO NÚMERO. Os dois outros medem a interface nova contra
# ela mesma (campos escritos; publicado × mockup) e nenhum responde "o que a GTK
# faz e o HTML não faz" -- que é de onde sai a fila. Este confere as 396
# features de `docs/data/paridade-gtk-html.csv` contra o CÓDIGO, e a metade que
# importa é a regra `divida-fechada`: quando alguém FECHAR uma dívida, ele
# reprova para o dado ser atualizado. Sem isso o número vira propaganda no dia
# seguinte à primeira cura. Camada rápida porque custa 0,4 s.
rapido|paridade-gtk-html|py|scripts/check_paridade_gtk_html.py
# O DONO DE CADA COMPORTAMENTO — 05/09/2026, e a queixa é dela: *"estamos
# recriando um produto que estava praticamente pronto pro gtk"*. Cinco laudos
# mediram 410 comportamentos das dez abas; os 50 que decidem estão em
# `docs/data/donos-de-comportamento.csv` com o endereço do dono. O portão não
# julga se um código recria — ele impede o LAUDO de envelhecer: endereço morto,
# cura descosturada, SO-GTK que já migrou, e a dívida declarada, que só desce.
rapido|donos-de-comportamento|py|scripts/check_donos_de_comportamento.py
# NADA NOVO APONTA PARA A JANELA — 06/09/2026, sprint GTK-1. Decisão dela
# (D-0609-GTK-LEVA-INTEIRA): *"a ideia sempre foi reaproveitar o que fiz no gtk e
# não apontar nada mais pra lá mas pro html"*. A janela GTK sai em três sprints
# (GTK-1 inventário, GTK-2 os leitores do glade, GTK-3 a remoção); enquanto ela
# sai, a lista de quem ainda aponta para lá SÓ DIMINUI — senão a GTK-3 persegue
# um alvo que cresce.
# O inventário é `docs/data/o-que-ainda-aponta-para-a-janela.csv`: 255 pares
# (arquivo, alvo) e 522 citações, cada uma com veredito. O portão tem DUAS
# metades: citação nova reprova nomeando arquivo e linha; linha nova no CSV sem
# veredito reprova. Ele NÃO é um `grep`: a natureza de cada citação sai do
# `tokenize`, porque 111 das 255 são PROSA e um grep as contaria como dependência.
# CAMADA `completo`, e o número é a razão: 3,7 s medidos em 06/09/2026, contra
# ~5 s da camada rápida INTEIRA. Ele lê 1.694 arquivos. O `bash scripts/portoes.sh`
# sem argumento — que é o que esta casa manda rodar antes de fechar leva — o
# alcança; o `--rapido`, que roda a cada salvamento, não paga por ele.
completo|nada-aponta-para-a-janela|py|scripts/check_nada_aponta_para_a_janela.py
rapido|test-data|bash|scripts/check_test_data.sh
rapido|endereco-de-radio|py|scripts/check_endereco_de_radio.py
# O IRMÃO DO DE CIMA, PARA O SERIAL — 03/09/2026, e o pedido é dela: *"sim, faz
# o portão pro número de série"*. O serial de fábrica identifica a unidade dela
# tão bem quanto o MAC, e a regra desta casa é sobre ARQUIVO VERSIONADO, não
# sobre a palavra "MAC".
# NÃO É A PRIMEIRA RÉGUA DE SERIAL, e isso foi medido escrevendo esta: o
# `test_nenhum_serial_de_fabrica_real_no_repo`, dentro do `mac-por-oui`, existe
# desde 15/08 e acusou o forjado que este portão acabara de criar. Ele é o
# AUTORITATIVO — pega a forma exata de um DualSense em texto, em hexdump e em
# corrida hexadecimal colada.
# O QUE ESTA ACRESCENTA são duas coisas: a CAMADA (1,2 s contra 12 s, logo roda
# antes do commit em vez de no fim da suíte) e a LARGURA (15 a 20 caracteres,
# que alcança serial de 8BitDo e de Pro Controller, não só de DualSense).
# A camada é a lição de HOJE: o `mac-por-oui` acusava os 37 endereços crus da
# manhã, mas era teste da SUÍTE, e a suíte roda no FIM.
rapido|serial-de-aparelho|py|scripts/check_numero_de_serie.py
rapido|faixa-sintetica|py|scripts/check_faixa_sintetica.py
# 03/09/2026 — O PORTÃO AUTORITATIVO DE MAC ENTRA AQUI, e a razão é medida: os
# documentos da leva de cliques trouxeram 37 endereços CRUS da bancada, e este
# teste os acusou — a lista dele já trazia os quatro OUIs. Ele não estava cego;
# ele só não era rodado. Era teste da SUÍTE, e a suíte roda no FIM: entre o
# commit que vazou e a reprovação havia um dia inteiro de trabalho.
# Camada `completo` porque custa ~12 s — varre toda a árvore versionada, e
# dentro dos `.gz` também.
completo|mac-por-oui|pytest|tests/unit/test_docs_mac_anonimato.py
# A TERCEIRA RÉGUA, e ela mede o que as outras duas não podem: fixture de teste
# tem de usar faixa FORJADA (`aa:bb:cc`), não endereço real podado — a máscara
# da casa preserva o OUI, e o OUI é identidade de fabricante do aparelho dela.
completo|mac-de-fixture|pytest|tests/unit/test_anonimato_de_fixtures.py
completo|casa-sabe|pytest|tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py
# 25/08/2026: o portão que exige que TODO portão tenha quem o rode não era
# rodado por esta lista — só pela camada `suite`, que é de quem coordena e
# roda no fim. Achado pela conferência da frente C2, e a ironia é o ponto.
completo|portao-tem-chamador|pytest|tests/unit/test_portao_todo_portao_tem_chamador.py
# 04/09/2026 — O PORTÃO QUE MEDE O PRÓPRIO INSTRUMENTO. Numa árvore de voo o
# cabeçalho deste script imprimia a venv da `-estavel`, outra cópia do
# repositório, sem structlog/playwright/ruff/mypy: QUATRO vermelhos falsos sobre
# código são. A causa era a regra da POSIÇÃO (`worktree list | awk NR==1`), e a
# regra passou a ser a de CAPACIDADE. Ele entra na camada `completo` e não na
# suíte pela lição que este arquivo já carrega no `mac-por-oui`: era teste da
# SUÍTE, e a suíte roda no FIM -- entre o vazamento e a reprovação havia um dia
# inteiro de trabalho. Custa ~1 s.
completo|interpretador-do-portao|pytest|tests/unit/test_o_portao_declara_o_interpretador.py
completo|a-tela-dela|pytest|tests/unit/test_a_tela_dela_nao_recebe_janela_de_teste.py
completo|o-instrumento-e-a-tela|pytest|tests/unit/test_o_instrumento_nao_abre_na_tela_dela.py
completo|a-frase-banida|pytest|tests/unit/test_a_frase_que_ela_baniu_nao_chega_a_tela.py
completo|src-desta-arvore|pytest|tests/unit/test_a_suite_mede_esta_arvore.py
completo|o-piloto-e-a-arvore|pytest|tests/unit/test_o_piloto_aponta_para_a_propria_arvore.py
rapido|desenho-aprovado|py|scripts/check_o_desenho_aprovado.py
rapido|identidade-de-cima|py|scripts/check_identidade_vem_de_cima.py
# 03/09/2026, a lei dela: *"cada pessoa tem um dualsense diferente (…) nada
# hardcoded, trazer tudo que eu já mapeei"*. O irmão acima acha cor congelada
# em elemento SEM endereço; este acha cor de aparelho cravada mesmo ONDE o
# endereço existe -- porque um endereço com o alvo errado não alcança a cor.
# NASCE VERMELHO, e é o ponto: 360 cravados em sete das dez abas, o número de
# onde as ondas partem. Ele distingue a TABELA dela (a folha com os 28 modelos,
# que é o mecanismo certo) da ESCOLHA cravada (a folha podada para um só).
# VERMELHO POR DECISÃO DELA, e não por descuido — 03/09/2026. Ele mede a página
# PUBLICADA, e a bancada já está em ZERO: `--bancada` devolve 0 plástico, 0
# colorway, 0 zona nas dez abas (era 503 na manhã deste dia). Os 358 que sobram
# vivem só no publicado, e publicar é ATO DELA.
#
# ELA ESCOLHEU PUBLICAR POR ÚLTIMO, depois do install e dos cliques: *"deixa
# para o fim, depois do install"*. Até lá este portão fica vermelho, e ficar
# vermelho é o comportamento CERTO — ele está dizendo a verdade sobre a tela
# que ela vê hoje.
#
# NÃO O CALE, e não publique para o silenciar. `--publicar` é a palavra dela, e
# antecipá-lo entregaria dez abas que ela ainda não olhou.
rapido|cor-vem-do-aparelho|py|scripts/check_a_cor_vem_do_aparelho.py
rapido|colisao-de-sprints|py|scripts/check_colisao_de_sprints.py
rapido|icones|bash|scripts/gerar_icones.sh --check
rapido|packaging-parity|bash|scripts/check_packaging_parity.sh
rapido|glifos|py|scripts/validar-glifos.py --all
rapido|pecas-do-dualsense|py|scripts/check_pecas_do_dualsense.py
# 27/08/2026: o irmão acima confere que o NOME da peça bate com o LUGAR dela;
# este confere que a COR bate com o dado. Antes dele, nenhuma régua sabia dizer
# se o hex do desenho estava certo, porque não havia com o que comparar — o
# Cosmic Red era #b11f54 e a amostragem devolveu #A51C48. 3,5 s.
rapido|cores-do-dualsense|py|scripts/check_cores_do_dualsense.py
rapido|regua-de-tela|py|scripts/check_regua_de_tela.py
rapido|ruff|bin|ruff check src/ tests/
completo|shellcheck|bin|shellcheck -S error scripts/*.sh scripts/ci/*.sh install.sh uninstall.sh
completo|referencias-docs|py|scripts/validar-referencias-docs.py --all
completo|anonimato|bash|scripts/check_anonymity.sh
completo|acentuacao|py|scripts/validar-acentuacao.py --all
completo|mypy|bin|mypy src/hefesto_dualsense4unix
suite|suite|bin|pytest -q
TABELA
}

# ---------------------------------------------------------------------------
# AS DIVERGÊNCIAS DECLARADAS. O portão do portão exige que toda diferença entre
# esta tabela e o `ci.yml` esteja escrita aqui, com o motivo. Diferença
# declarada é decisão; diferença calada é a M9 de novo.
# ---------------------------------------------------------------------------
_DIVERGENCIAS() {
  cat <<'DIV'
FORA-DO-LOCAL|scripts/ci/instalar_como_usuaria.sh|ensaio de instalação em máquina descartável; rodar na máquina dela mexeria no sistema vivo.
FORA-DO-LOCAL|scripts/i18n_compile.sh|regenera os .mo, que são artefato compartilhado, e não tem forma --check. Portão que reescreve artefato não roda na árvore de agente.
FORA-DO-LOCAL|scripts/portao_alvo_tem_dono.py|precisa de Xvfb. Fica na camada de tela, não no bloco de fechar leva.
FORA-DO-LOCAL|pre-commit|DECISÃO EM ABERTO, e não é minha: ou o framework entra no install.sh sem flag, ou os dez portões do .pre-commit-config.yaml migram para o gancho e o .yaml some (INFRA-DE-EXECUCAO-01, I14 e §9.4). Enquanto não decidido, o CI é o único que o roda -- e esta linha declara isso em vez de fingir que não existe. Medido: `which pre-commit` -> not found nesta máquina.
DIV
}

_uso() { sed -n '2,32p' "$0" | sed 's/^# \?//'; }

CAMADAS="rapido completo"
case "${1:-}" in
  --listar)
    _LISTA | sed 's/^/PORTAO|/'
    _DIVERGENCIAS
    exit 0 ;;
  --rapido)  CAMADAS="rapido" ;;
  --interpretador) CAMADAS="" ;;   # só o cabeçalho; ver o bloco do interpretador
  --suite)   CAMADAS="rapido completo suite" ;;
  --aceite)  CAMADAS="rapido completo suite" ;;
  -h|--help) _uso; exit 0 ;;
  "")        ;;
  *) echo "ERRO: opção desconhecida '${1}'. Veja $0 --help" >&2; exit 2 ;;
esac

# --- o interpretador, resolvido e DECLARADO -------------------------------
#
# O DEFEITO QUE ESTE BLOCO CUROU, medido em 04/09/2026 dentro de uma árvore de
# voo: o cabeçalho imprimia
#
#     python  /mnt/.../hefesto-dualsense4unix-estavel/venv/bin/python
#
# — a venv de OUTRA CÓPIA do repositório, sem playwright, sem structlog e sem
# ruff, e por isso com QUATRO vermelhos falsos. A causa era uma suposição
# escrita aqui: `worktree list | awk NR==1` devolve a árvore PRINCIPAL do
# `.git`, e esta casa tem TRÊS árvores — a principal do git é a `-estavel`, que
# não é a de trabalho. "A primeira da lista" nunca foi "a que tem as
# dependências".
#
# É a família de defeito que esta casa persegue acima de todas: **o instrumento
# apontando para outra coisa.** Um portão que roda com o interpretador errado
# não é um portão vermelho — é um portão que não mede.
#
# A REGRA NOVA: não se adivinha a venv pela POSIÇÃO na lista. PERGUNTA-SE a ela
# se tem o que os portões precisam, e a que responder sim ganha. Se nenhuma
# responder, o cabeçalho DIZ, em vez de deixar o vermelho falso explicar-se
# sozinho.
_VENV_FALTA=""

_venv_completa() {  # rc=0 se esta venv tem o que os portões precisam
  local d="$1" falta=""
  "$d/python" -c 'import structlog, playwright' >/dev/null 2>&1 || falta="python:structlog/playwright"
  [ -x "$d/ruff" ] || falta="${falta:+$falta }bin:ruff"
  [ -x "$d/mypy" ] || falta="${falta:+$falta }bin:mypy"
  _VENV_FALTA="$falta"
  [ -z "$falta" ]
}

_venv_bin() {
  local d cand=() primeira="" w
  # 1. a venv DESTA árvore, se houver.
  cand+=("$RAIZ/.venv/bin" "$RAIZ/venv/bin")
  # 2. as das outras árvores do mesmo `.git` — TODAS, não só a primeira. Numa
  #    árvore de agente não há venv (o worktree copia só o que o git rastreia,
  #    e `.venv/` é ignorado), então é aqui que ela é achada.
  while read -r w; do
    [ -n "$w" ] && cand+=("$w/.venv/bin" "$w/venv/bin")
  done < <(git -C "$RAIZ" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')

  for d in "${cand[@]}"; do
    [ -x "$d/python" ] || continue
    [ -n "$primeira" ] || primeira="$d"
    if _venv_completa "$d"; then echo "$d"; return 0; fi
  done
  # Nenhuma completa: devolve a primeira que existe, e o chamador AVISA.
  if [ -n "$primeira" ]; then
    _venv_completa "$primeira" || true   # repovoa _VENV_FALTA com a escolhida
    echo "$primeira"; return 0
  fi
  return 1
}

VENV_BIN="$(_venv_bin || true)"
if [ -n "${HEFESTO_PY:-}" ]; then
  PY="$HEFESTO_PY"
elif [ -n "$VENV_BIN" ]; then
  PY="$VENV_BIN/python"
else
  PY="$(command -v python3)"
fi

# A CONFERÊNCIA É SOBRE O INTERPRETADOR QUE VAI RODAR, não sobre o que foi
# escolhido — senão um `HEFESTO_PY` apontado para uma venv capenga passa em
# silêncio, que é o mesmo defeito com outra porta. Medido ao morder o próprio
# conserto, em 04/09/2026.
VENV_INCOMPLETA=""
if ! _venv_completa "$(dirname "$PY")"; then
  VENV_INCOMPLETA="$_VENV_FALTA"
fi

_bin() {  # resolve um binário: venv primeiro, PATH depois
  local nome="$1"
  if [ -n "$VENV_BIN" ] && [ -x "$VENV_BIN/$nome" ]; then echo "$VENV_BIN/$nome"
  else command -v "$nome" || echo "$nome"; fi
}

echo "portões — árvore ${RAIZ}"
echo "         python  ${PY}"
echo "         camadas ${CAMADAS}"
# O `src/` DESTA árvore vai na frente do PYTHONPATH, sempre.
#
# Aqui havia só um AVISO ("PYTHONPATH (vazio) -- armadilha"), e aviso não é
# cura: ninguém lê o cabeçalho de um comando que termina verde. Medido em
# 04/09/2026 numa árvore de integração — doze lotes de suíte e uma leva de
# portões mediram o `src/` de OUTRA cópia do repositório, porque a venv tem o
# pacote em modo editável apontando para a árvore onde ela nasceu. Não dá erro:
# dá `ImportError` de símbolo novo, que se lê como "o agente não terminou".
#
# É a mesma família do defeito do interpretador, e a mesma resposta: o script
# RESOLVE em vez de pedir que alguém lembre.
if [ -d "${RAIZ}/src" ]; then
  case ":${PYTHONPATH:-}:" in
    *":${RAIZ}/src:"*) : ;;
    *) PYTHONPATH="${RAIZ}/src${PYTHONPATH:+:${PYTHONPATH}}" ;;
  esac
  export PYTHONPATH
fi
echo "         PYTHONPATH ${PYTHONPATH:-(vazio)}"
if [ -n "${VENV_INCOMPLETA:-}" ]; then
  echo "         INTERPRETADOR INCOMPLETO -- falta: ${VENV_INCOMPLETA}"
  echo "         O VERMELHO QUE VIER PODE SER DO INSTRUMENTO, NÃO DO CÓDIGO."
  echo "         Aponte o certo: HEFESTO_PY=<árvore>/.venv/bin/python bash scripts/portoes.sh"
fi
# `--interpretador` para AQUI, e é ele que torna a resolução OBSERVÁVEL — que é
# a metade que faltava quando o defeito de 04/09 viveu meses: o python errado
# saía impresso e ninguém tinha como afirmar, numa régua, que ele estava certo.
if [ "${1:-}" = "--interpretador" ]; then
  [ -z "${VENV_INCOMPLETA:-}" ]; exit $?
fi
echo

# --- a corrida -------------------------------------------------------------
VERMELHOS=()
AUSENTES=()
TOTAL=0

while IFS='|' read -r camada id runner argv; do
  [ -z "${camada:-}" ] && continue
  case " $CAMADAS " in *" $camada "*) ;; *) continue ;; esac

  # PORTÃO DECLARADO E AUSENTE SAI VERMELHO NOMEANDO. Um script que sumiu da
  # árvore e some da corrida em silêncio é o portão cego da cicatriz acima.
  primeiro="${argv%% *}"
  case "$primeiro" in
    scripts/*)
      case "$primeiro" in
        *'*'*) ;;  # glob: quem expande é o shell, não dá para conferir aqui
        *) if [ ! -e "$RAIZ/$primeiro" ]; then
             AUSENTES+=("$id -> $primeiro")
             printf '  %-22s AUSENTE DA ÁRVORE  %s\n' "$id" "$primeiro"
             continue
           fi ;;
      esac ;;
  esac

  case "$runner" in
    py)   cmd="$PY $argv" ;;
    bash) cmd="bash $argv" ;;
    bin)  cmd="$(_bin "${argv%% *}") ${argv#* }" ;;
    # `pytest` como runner nasceu em 25/08/2026, e por um defeito medido: o
    # `portao_a_casa_sabe_e_o_produto_nao_faz.py` RODA NO CI, ficou VERMELHO no
    # `dev` por horas, e ninguém viu — porque a lista local não o continha e o
    # portão da lista só compara `scripts/*`. Portão do CI que não cabe em
    # `scripts/` precisa caber aqui, ou o buraco continua aberto.
    pytest) cmd="$PY -m pytest -q $argv" ;;
    *)    echo "ERRO: runner desconhecido '$runner' no portão '$id'" >&2; exit 2 ;;
  esac

  TOTAL=$((TOTAL + 1))
  inicio=$(date +%s%N)
  saida="$(cd "$RAIZ" && eval "$cmd" 2>&1)"
  rc=$?
  fim=$(date +%s%N)
  ms=$(( (fim - inicio) / 1000000 ))

  if [ "$rc" -eq 0 ]; then
    printf '  %-22s ok      %6d ms\n' "$id" "$ms"
  else
    printf '  %-22s VERMELHO rc=%s %5d ms\n' "$id" "$rc" "$ms"
    printf '%s\n' "$saida" | sed 's/^/      /'
    VERMELHOS+=("$id")
  fi
done < <(_LISTA)

echo
if [ ${#AUSENTES[@]} -gt 0 ]; then
  echo "PORTÕES DECLARADOS E AUSENTES DA ÁRVORE (${#AUSENTES[@]}):"
  printf '  %s\n' "${AUSENTES[@]}"
fi
if [ ${#VERMELHOS[@]} -eq 0 ] && [ ${#AUSENTES[@]} -eq 0 ]; then
  echo "TODOS VERDES — ${TOTAL} portões."
  exit 0
fi
echo "REPROVOU: ${#VERMELHOS[@]} vermelho(s) de ${TOTAL}${VERMELHOS[0]+ -> }${VERMELHOS[*]:-}"
exit 1
