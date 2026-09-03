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
rapido|test-data|bash|scripts/check_test_data.sh
rapido|endereco-de-radio|py|scripts/check_endereco_de_radio.py
rapido|faixa-sintetica|py|scripts/check_faixa_sintetica.py
completo|casa-sabe|pytest|tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py
# 25/08/2026: o portão que exige que TODO portão tenha quem o rode não era
# rodado por esta lista — só pela camada `suite`, que é de quem coordena e
# roda no fim. Achado pela conferência da frente C2, e a ironia é o ponto.
completo|portao-tem-chamador|pytest|tests/unit/test_portao_todo_portao_tem_chamador.py
rapido|desenho-aprovado|py|scripts/check_o_desenho_aprovado.py
rapido|identidade-de-cima|py|scripts/check_identidade_vem_de_cima.py
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
  --suite)   CAMADAS="rapido completo suite" ;;
  --aceite)  CAMADAS="rapido completo suite" ;;
  -h|--help) _uso; exit 0 ;;
  "")        ;;
  *) echo "ERRO: opção desconhecida '${1}'. Veja $0 --help" >&2; exit 2 ;;
esac

# --- o interpretador, resolvido e DECLARADO -------------------------------
_venv_bin() {
  local d
  for d in "$RAIZ/.venv/bin" "$RAIZ/venv/bin"; do
    [ -x "$d/python" ] && { echo "$d"; return 0; }
  done
  # Numa árvore de agente não há venv: o worktree copia só o que o git
  # rastreia, e `.venv/` é ignorado. Cai na venv da árvore PRINCIPAL, que é
  # onde o install editable mora. Isso vale para os BINÁRIOS (ruff, mypy,
  # pytest); o código sob teste continua vindo do PYTHONPATH do `.envrc-voo`.
  local principal
  principal="$(git -C "$RAIZ" worktree list --porcelain 2>/dev/null | awk 'NR==1{print $2}')"
  if [ -n "${principal:-}" ]; then
    for d in "$principal/.venv/bin" "$principal/venv/bin"; do
      [ -x "$d/python" ] && { echo "$d"; return 0; }
    done
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

_bin() {  # resolve um binário: venv primeiro, PATH depois
  local nome="$1"
  if [ -n "$VENV_BIN" ] && [ -x "$VENV_BIN/$nome" ]; then echo "$VENV_BIN/$nome"
  else command -v "$nome" || echo "$nome"; fi
}

echo "portões — árvore ${RAIZ}"
echo "         python  ${PY}"
echo "         camadas ${CAMADAS}"
if [ -n "${PYTHONPATH:-}" ]; then
  echo "         PYTHONPATH ${PYTHONPATH}"
else
  echo "         PYTHONPATH (vazio) -- numa árvore de agente isto é ARMADILHA: rode 'source .envrc-voo' antes."
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
