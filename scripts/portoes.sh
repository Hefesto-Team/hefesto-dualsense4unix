#!/usr/bin/env bash
set -uo pipefail
_ajuda() {
  cat <<'AJUDA'
portoes.sh — A LISTA DE PORTÕES DESTA CASA, e ela é UMA SÓ.

Uso:
  scripts/portoes.sh              a leva inteira (rápidos + completos)
  scripts/portoes.sh --rapido     só a camada rápida (quantos: `scripts/portoes.sh --listar | grep -c '^PORTAO|rapido|'`)
  scripts/portoes.sh --suite      acrescenta a suíte de testes
  scripts/portoes.sh --listar     a tabela crua, que é o que o portão do portão lê
  scripts/portoes.sh --interpretador  só o cabeçalho: qual python, e o que falta nele
  scripts/portoes.sh --em-serie   um portão de cada vez, na ordem da lista (a mesma corrida, sem a pressa)
  scripts/portoes.sh --sem-memoria  roda todos, sem pular o que já passou sobre os mesmos bytes
  scripts/portoes.sh --so ID…     só os portões nomeados, de qualquer camada, com o mesmo motor (id fora da
                                  tabela: rc 2, nomeando-o); é assim que o `ci.yml` chama cada portão
AJUDA
}

RAIZ="$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(dirname "$(readlink -f "$0")")")"

_LISTA() {
  cat <<'TABELA'
rapido|contrato-ipc|py|scripts/gerar-contrato-ipc.py --check
rapido|citacoes-de-linha|py|scripts/validar-citacoes-de-linha.py --all
rapido|citacoes-novas|py|scripts/validar-citacoes-de-linha.py --novas|@sempre
completo|citacoes-no-codigo|pytest|tests/unit/test_portao_o_par_com_metade_ligada.py
rapido|nada-mockado|pytest|tests/unit/test_portao_nada_e_afirmado_sem_prova.py
rapido|quatro-respostas|py|scripts/check_cabo_bt_perfil_controle.py
rapido|quatro-respostas-morde|pytest|tests/unit/test_portao_a_regua_das_quatro_respostas.py|src/** docs/data/** tests/** scripts/check_cabo_bt_perfil_controle.py scripts/check_faixa_sintetica.py pyproject.toml
rapido|ate-onde-a-prova-chegou|py|scripts/check_ate_onde_a_prova_chegou.py
rapido|ate-onde-a-prova-chegou-morde|pytest|tests/unit/test_portao_a_quinta_pergunta_morde.py
rapido|mapa-de-canais|py|scripts/gerar-mapa.py --check
rapido|fatos-de-tela|py|scripts/gerar-fatos-de-tela.py --check
rapido|fala-de-tela|py|scripts/validar-fala-de-tela.py --all|@dia
rapido|caducos|py|scripts/validar-caducos.py --all
rapido|texto-publico|py|scripts/check_texto_publico.py
rapido|palavra-de-tela|py|scripts/validar-palavra-de-tela.py --all
rapido|version-consistency|py|scripts/check_version_consistency.py
rapido|curvas|py|scripts/gerar-tabela-de-curvas.py --check
rapido|paridade-transporte|py|scripts/check_paridade_transporte.py|@dia tests/** src/** docs/data/** docs/specs.html scripts/eliminacao.py
rapido|paridade-gtk-html|py|scripts/check_paridade_gtk_html.py|src/** mockup/** docs/data/** docs/method/** assets/** tests/** install.sh scripts/prosa_do_codigo.py
rapido|contratos-de-fora|py|scripts/check_os_contratos_de_fora.py
rapido|donos-de-comportamento|py|scripts/check_donos_de_comportamento.py
rapido|a-origem|py|scripts/check_a_origem.py|@sempre
rapido|decisao-tem-prova|py|scripts/check_a_decisao_tem_prova.py|docs/data/decisoes-de-produto.csv docs/data/decisoes-sem-prova.txt tests/**
rapido|broadcast-proibido|py|scripts/check_broadcast_proibido.py|src/**
completo|nada-aponta-para-a-janela|py|scripts/check_nada_aponta_para_a_janela.py
rapido|o-gtk-fica-na-moldura|py|scripts/check_o_gtk_fica_na_moldura.py|src/** scripts/check_o_gtk_fica_na_moldura.py
rapido|test-data|bash|scripts/check_test_data.sh
rapido|endereco-de-radio|py|scripts/check_endereco_de_radio.py
rapido|endereco-dela-em-toda-forma|py|scripts/check_o_endereco_em_toda_forma.py|@sempre
rapido|serial-de-aparelho|py|scripts/check_numero_de_serie.py
rapido|faixa-sintetica|py|scripts/check_faixa_sintetica.py
rapido|comentario-cortado|py|scripts/check_comentario_cortado.py|@sempre
completo|mac-por-oui|pytest|tests/unit/test_docs_mac_anonimato.py
completo|mac-de-fixture|pytest|tests/unit/test_anonimato_de_fixtures.py
rapido|autoria-historia|py|scripts/check_autoria.py historia|@sempre
completo|casa-sabe|pytest|tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py
completo|portao-tem-chamador|pytest|tests/unit/test_portao_todo_portao_tem_chamador.py
completo|interpretador-do-portao|pytest|tests/unit/test_o_portao_declara_o_interpretador.py|@sempre
completo|a-tela-dela|pytest|tests/unit/test_a_tela_nao_recebe_janela_de_teste.py
completo|o-instrumento-e-a-tela|pytest|tests/unit/test_o_instrumento_nao_abre_na_tela_do_usuario.py
completo|a-frase-banida|pytest|tests/unit/test_a_frase_que_ela_baniu_nao_chega_a_tela.py
completo|src-desta-arvore|pytest|tests/unit/test_a_suite_mede_esta_arvore.py|@sempre
completo|o-piloto-e-a-arvore|pytest|tests/unit/test_o_piloto_aponta_para_a_propria_arvore.py
rapido|desenho-aprovado|py|scripts/check_o_desenho_aprovado.py
rapido|os-quatro-lugares|py|scripts/check_os_quatro_lugares.py
rapido|gesto-em-lugar-vazio|pytest|tests/unit/test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio.py|src/** scripts/** tests/** mockup/** docs/data/** assets/glyphs/** pyproject.toml
rapido|gesto-onde-deve-04|pytest|tests/unit/test_a_04_iluminacao_o_gesto_esta_onde_deve.py|src/** scripts/** tests/** mockup/** docs/data/** pyproject.toml
rapido|identidade-de-cima|py|scripts/check_identidade_vem_de_cima.py
rapido|cor-vem-do-aparelho|py|scripts/check_a_cor_vem_do_aparelho.py
rapido|icones|bash|scripts/gerar_icones.sh --check
rapido|packaging-parity|bash|scripts/check_packaging_parity.sh
rapido|glifos|py|scripts/validar-glifos.py --all
rapido|pecas-do-dualsense|py|scripts/check_pecas_do_dualsense.py|src/** docs/data/**
rapido|cores-do-dualsense|py|scripts/check_cores_do_dualsense.py|src/** docs/data/** assets/control-svg/** scripts/gerar_cores_do_dualsense.py
rapido|altura-do-cartao|py|scripts/check_a_altura_do_cartao.py
rapido|regua-de-tela|py|scripts/check_regua_de_tela.py|@sempre
rapido|tela-nao-confessa|py|scripts/check_a_tela_nao_confessa.py|src/** mockup/**
rapido|janela-nao-confessa|py|scripts/check_a_janela_nao_confessa.py
rapido|maiuscula-decorativa|py|scripts/check_a_maiuscula_decorativa.py
rapido|maiuscula-decorativa-morde|pytest|tests/unit/test_portao_a_maiuscula_decorativa_morde.py
rapido|so-a-primeira-letra|py|scripts/check_so_a_primeira_letra.py|src/** docs/data/** scripts/check_a_maiuscula_decorativa.py
rapido|grafia-do-nome|py|scripts/check_a_grafia_do_nome.py
rapido|grafia-do-nome-morde|pytest|tests/unit/test_portao_a_grafia_do_nome_morde.py
rapido|projeto-traduzivel|py|scripts/check_o_projeto_e_traduzivel.py
rapido|projeto-traduzivel-morde|pytest|tests/unit/test_o_projeto_e_traduzivel_morde.py
rapido|portoes-lentos-rapidos|pytest|tests/unit/test_os_portoes_lentos_ficam_rapidos.py|src/** scripts/** tests/** mockup/** docs/data/** assets/glyphs/** install.sh uninstall.sh pyproject.toml
rapido|o-ignorado-fica-fora-do-indice|py|scripts/check_o_ignorado_fica_fora_do_indice.py|@head
rapido|numeros-da-sony|py|scripts/check_numeros_da_sony.py|src/** scripts/check_numeros_da_sony.py
rapido|numeros-da-sony-morde|pytest|tests/unit/test_os_numeros_da_sony_tem_um_dono.py|src/** scripts/** tests/unit/test_os_numeros_da_sony_tem_um_dono.py
rapido|docstring-longa|py|scripts/check_docstring_longa.py|src/** scripts/check_docstring_longa.py docs/data/a-catraca-da-docstring-longa.json
rapido|docstring-longa-morde|pytest|tests/unit/test_a_docstring_longa_so_desce.py|src/** scripts/** docs/data/a-catraca-da-docstring-longa.json tests/unit/test_a_docstring_longa_so_desce.py
rapido|texto-enxuto|py|scripts/o-texto-enxuto.py --conferir --mudados|@sempre
rapido|texto-enxuto-catraca|py|scripts/o-texto-enxuto.py --catraca|src/** scripts/o-texto-enxuto.py docs/data/o-texto-enxuto.json
rapido|texto-enxuto-morde|pytest|tests/unit/test_o_texto_enxuto_se_corrige_no_ato.py|scripts/** src/** .pre-commit-config.yaml tests/unit/test_o_texto_enxuto_se_corrige_no_ato.py
rapido|ruff|bin|ruff check src/ tests/|src/** tests/** pyproject.toml .gitignore
completo|shellcheck|bin|shellcheck -S error scripts/*.sh scripts/ci/*.sh scripts/banco_de_prova/*.sh install.sh uninstall.sh|scripts/*.sh scripts/ci/*.sh scripts/banco_de_prova/*.sh install.sh uninstall.sh
completo|referencias-docs|py|scripts/validar-referencias-docs.py --all
completo|anonimato|bash|scripts/check_anonymity.sh
completo|autoria-arvore|py|scripts/check_autoria.py arvore|@sempre
completo|acentuacao|py|scripts/validar-acentuacao.py --all
completo|mypy|bin|mypy --cache-dir .mypy_cache/src src/hefesto_dualsense4unix|src/** pyproject.toml
completo|mypy-testes|bin|mypy --cache-dir .mypy_cache/testes --follow-imports=silent @tests/mypy-limpos.txt|tests/** src/** pyproject.toml
completo|coleta-sem-gtk|py|scripts/check_a_coleta_sem_gtk.py
suite|suite|bin|pytest -q
TABELA
}

_DIVERGENCIAS() {
  cat <<'DIV'
FORA-DO-LOCAL|scripts/ci/instalar_como_usuaria.sh|ensaio de instalação em máquina descartável; rodar na máquina dela mexeria no sistema vivo.
FORA-DO-LOCAL|scripts/banco_de_prova/sonda.sh|06/10/2026, O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01 (parte 0): é a sonda do kernel do runner (carrega uhid e hid_playstation, cria um gadget USB e roda o install.sh com sudo), só em workflow_dispatch. Cria aparelho no kernel: na máquina dela mexeria no que ela usa.
FORA-DO-LOCAL|scripts/i18n_compile.sh|regenera os .mo, que são artefato compartilhado, e não tem forma --check. Portão que reescreve artefato não roda na árvore de agente.
FORA-DO-CI|scripts/check_o_endereco_em_toda_forma.py|27/09/2026, O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01: pergunta à máquina dela os endereços reais (maquina.json do HOME de verdade, bluetoothctl e sysfs) e procura os octetos 4 e 5 em toda forma; no runner não há endereço nenhum a perguntar, e o portão só diria NÃO MEDIDO (O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01, 27/09).
FORA-DO-LOCAL|pre-commit|13/10/2026, O-TEXTO-ENXUTO-SE-CORRIGE-NO-ATO-01: o .pre-commit-config.yaml roda em casa pelo gancho do git (scripts/hooks/pre-commit, item 6), com o mesmo framework do job «pre-commit» do CI, quando ele está na máquina; esta tabela não o repete. Medido no mesmo dia: o framework não está nesta máquina, e o gancho global do git só encadeia o .git/hooks/pre-commit de árvore com .git pasta, o que nenhuma worktree tem.
ARGUMENTO-DO-EVENTO|scripts/check_paridade_transporte.py|10/10/2026: além do censo pelo nome, o `mapa-de-canais` o chama com `--exigir-id-estavel --contra <ref>`, e o ref é o do evento (o `before` do push, a base do PR), que só o passo anterior do job calcula.
ARGUMENTO-DO-EVENTO|scripts/check_a_origem.py|10/10/2026: no CI ele recebe `--base` com a faixa do evento (o `BASE_DA_FAIXA` do passo), e em casa mede contra o `dev`.
ARGUMENTO-DO-EVENTO|scripts/check_autoria.py|10/10/2026: o `autoria.yml` o chama com as refs do evento (`historia origin/dev origin/main <tags>`, `arvore "$REV"`, o texto do PR), que só o runner tem.
ARGUMENTO-DO-EVENTO|scripts/check_a_coleta_sem_gtk.py|10/10/2026: no CI ele julga (`--julgar`) a coleta que o próprio passo acabou de gravar sem o `gi`; em casa ele coleta sozinho, com o `gi` e o `cairo` bloqueados.
FORA-DO-LOCAL|scripts/rodar-a-suite.sh|27/09/2026: é a suíte inteira, e em casa ela roda no fecho, com a máquina livre, depois dos portões (a lista «Antes de fechar qualquer leva»): toca nós uinput de verdade e leva quarenta minutos. No CI é o job gtk-real, com o GTK real.
DIV
}

_uso() { _ajuda; }

CAMADAS="rapido completo"
MODO=""
EM_SERIE=0
SEM_MEMORIA=0
SO_IDS=()
_LENDO_IDS=0
for _opcao in "$@"; do
  if [ "$_LENDO_IDS" -eq 1 ]; then
    case "$_opcao" in
      -*) _LENDO_IDS=0 ;;
      *) SO_IDS+=("$_opcao"); continue ;;
    esac
  fi
  case "$_opcao" in
    --so) _LENDO_IDS=1 ;;
    --listar)
      _LISTA | sed 's/^/PORTAO|/'
      _DIVERGENCIAS
      exit 0 ;;
    --rapido)  CAMADAS="rapido" ;;
    --interpretador) CAMADAS=""; MODO="interpretador" ;;
    --suite)   CAMADAS="rapido completo suite" ;;
    --aceite)  CAMADAS="rapido completo suite" ;;
    --em-serie) EM_SERIE=1 ;;
    --sem-memoria) SEM_MEMORIA=1 ;;
    -h|--help) _uso; exit 0 ;;
    *) echo "ERRO: opção desconhecida '${_opcao}'. Veja $0 --help" >&2; exit 2 ;;
  esac
done
declare -A SO_DE=()
if [ "$_LENDO_IDS" -eq 1 ] || [ ${#SO_IDS[@]} -gt 0 ]; then
  [ ${#SO_IDS[@]} -gt 0 ] || { echo "ERRO: --so sem nenhum id. Veja $0 --listar" >&2; exit 2; }
  declare -A _NA_TABELA=()
  while IFS='|' read -r _camada _id _resto; do
    case "${_camada:-}" in ""|"#"*) continue ;; esac
    _NA_TABELA["$_id"]=1
  done < <(_LISTA)
  _desconhecidos=()
  for _id in "${SO_IDS[@]}"; do
    [ -n "${_NA_TABELA[$_id]:-}" ] || _desconhecidos+=("$_id")
    SO_DE["$_id"]=1
  done
  if [ ${#_desconhecidos[@]} -gt 0 ]; then
    echo "ERRO: portão fora da tabela: ${_desconhecidos[*]}. Veja $0 --listar" >&2
    exit 2
  fi
  CAMADAS="rapido completo suite"
fi

_VENV_FALTA=""

_venv_completa() {
  local d="$1" falta=""
  "$d/python" -c 'import structlog, playwright' >/dev/null 2>&1 || falta="python:structlog/playwright"
  [ -x "$d/ruff" ] || falta="${falta:+$falta }bin:ruff"
  [ -x "$d/mypy" ] || falta="${falta:+$falta }bin:mypy"
  _VENV_FALTA="$falta"
  [ -z "$falta" ]
}

_venv_bin() {
  local d cand=() primeira="" w
  cand+=("$RAIZ/.venv/bin" "$RAIZ/venv/bin")
  while read -r w; do
    [ -n "$w" ] && cand+=("$w/.venv/bin" "$w/venv/bin")
  done < <(git -C "$RAIZ" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')

  for d in "${cand[@]}"; do
    [ -x "$d/python" ] || continue
    [ -n "$primeira" ] || primeira="$d"
    if _venv_completa "$d"; then echo "$d"; return 0; fi
  done
  if [ -n "$primeira" ]; then
    _venv_completa "$primeira" || true
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

VENV_INCOMPLETA=""
if ! _venv_completa "$(dirname "$PY")"; then
  VENV_INCOMPLETA="$_VENV_FALTA"
fi

_bin() {
  local nome="$1"
  if [ -n "$VENV_BIN" ] && [ -x "$VENV_BIN/$nome" ]; then echo "$VENV_BIN/$nome"
  else command -v "$nome" || echo "$nome"; fi
}

echo "portões — árvore ${RAIZ}"
echo "         python  ${PY}"
if [ ${#SO_IDS[@]} -gt 0 ]; then echo "         só      ${SO_IDS[*]}"; else echo "         camadas ${CAMADAS}"; fi
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
if [ "$MODO" = "interpretador" ]; then
  [ -z "${VENV_INCOMPLETA:-}" ]; exit $?
fi
echo

LAR_DE_MENTIRA="$(mktemp -d "${TMPDIR:-/tmp}/portoes-lar-XXXXXX")"
mkdir -p "$LAR_DE_MENTIRA"/{config,data,cache,state,runtime}
chmod 700 "$LAR_DE_MENTIRA/runtime"
trap 'rm -rf "$LAR_DE_MENTIRA"' EXIT
_AMBIENTE_DE_MENTIRA=(
  "HOME=$LAR_DE_MENTIRA"
  "XDG_CONFIG_HOME=$LAR_DE_MENTIRA/config"
  "XDG_DATA_HOME=$LAR_DE_MENTIRA/data"
  "XDG_CACHE_HOME=$LAR_DE_MENTIRA/cache"
  "XDG_STATE_HOME=$LAR_DE_MENTIRA/state"
  "XDG_RUNTIME_DIR=$LAR_DE_MENTIRA/runtime"
  "XDG_CURRENT_DESKTOP="
  "WAYLAND_DISPLAY="
  "GIO_USE_VFS=local"
)
_lar_sem_portal() {
  local servicos="$1/dbus-1/services" nome
  mkdir -p "$servicos"
  for nome in org.freedesktop.portal.Desktop org.freedesktop.portal.Documents; do
    printf '[D-BUS Service]\nName=%s\nExec=/bin/false\n' "$nome" > "$servicos/$nome.service"
  done
}

RECIBO_DA_CORRIDA=""
case " $CAMADAS " in
  *" completo "*)
    if [ ${#SO_IDS[@]} -eq 0 ]; then
      RECIBO_DA_CORRIDA="$(mktemp "${TMPDIR:-/tmp}/portoes-recibo-XXXXXX")"
      trap 'rm -rf "$LAR_DE_MENTIRA" "$RECIBO_DA_CORRIDA"' EXIT
      "$PY" "$RAIZ/scripts/recibo_da_medida.py" abrir portoes-completo \
        --raiz "$RAIZ" --corrida "$RECIBO_DA_CORRIDA" || true
      echo
    fi ;;
esac

_sair() {
  local rc="$1" id bandeiras=()
  if [ -n "$RECIBO_DA_CORRIDA" ]; then
    for id in ${NAO_MEDIDOS[@]+"${NAO_MEDIDOS[@]}"} ${PULADOS[@]+"${PULADOS[@]}"}; do
      bandeiras+=(--nao-medido "$id")
    done
    for id in ${LEMBRADOS[@]+"${LEMBRADOS[@]}"}; do
      bandeiras+=(--lembrado "$id")
    done
    echo
    "$PY" "$RAIZ/scripts/recibo_da_medida.py" fechar portoes-completo "$rc" \
      --raiz "$RAIZ" --corrida "$RECIBO_DA_CORRIDA" \
      --contagem "$((TOTAL - ${#NAO_MEDIDOS[@]})) de ${TOTAL} portões verdes" \
      ${bandeiras[@]+"${bandeiras[@]}"} || true
  fi
  exit "$rc"
}

VERMELHOS=()
AUSENTES=()
NAO_MEDIDOS=()
PULADOS=()
LEMBRADOS=()
VERDES_TSV=""
TOTAL=0
G_ID=(); G_RUN=(); G_ARGV=(); G_ENT=(); G_ESTADO=(); G_CHAVE=(); G_DICA=()

while IFS='|' read -r camada id runner argv entradas; do
  [ -z "${camada:-}" ] && continue
  case "$camada" in "#"*) continue ;; esac
  case " $CAMADAS " in *" $camada "*) ;; *) continue ;; esac
  [ ${#SO_IDS[@]} -gt 0 ] && [ -z "${SO_DE[$id]:-}" ] && continue
  estado="rodar"

  primeiro="${argv%% *}"
  case "$primeiro" in
    scripts/*)
      case "$primeiro" in
        *'*'*) ;;
        *) if [ ! -e "$RAIZ/$primeiro" ]; then
             AUSENTES+=("$id -> $primeiro")
             estado="ausente"
           fi ;;
      esac ;;
  esac
  case "$runner" in
    py|bash|bin|pytest) ;;
    *) echo "ERRO: runner desconhecido '$runner' no portão '$id'" >&2; exit 2 ;;
  esac
  G_ID+=("$id"); G_RUN+=("$runner"); G_ARGV+=("$argv"); G_ENT+=("${entradas:-}")
  G_ESTADO+=("$estado"); G_CHAVE+=(""); G_DICA+=(0)
  [ "$camada" = suite ] && G_ENT[${#G_ID[@]}-1]="@sempre"
done < <(_LISTA)
N=${#G_ID[@]}

_NUCLEOS="$(nproc 2>/dev/null || echo 4)"
VAGAS_GERAIS="${PORTOES_VAGAS:-$(( _NUCLEOS > 3 ? _NUCLEOS - 2 : 1 ))}"
SEMAFORO=""
_vez="${HEFESTO_VEZ_DO_PYTEST:-$RAIZ/docs/process/ferramentas-da-leva/vez-do-pytest.sh}"
_dentro_da_vaga=0
case "$(readlink /proc/$$/fd/9 2>/dev/null || true)" in */vagas/vaga-*) _dentro_da_vaga=1 ;; esac
if [ "$_dentro_da_vaga" -eq 1 ]; then
  VAGAS_PYTEST=1
elif [ -f "$_vez" ]; then
  SEMAFORO="bash $_vez"
  VAGAS_PYTEST=3
else
  VAGAS_PYTEST=$(( _NUCLEOS >= 8 ? 3 : 1 ))
fi
VAGAS_PYTEST="${PORTOES_VAGAS_PYTEST:-$VAGAS_PYTEST}"
[ "$EM_SERIE" -eq 1 ] && { VAGAS_GERAIS=1; VAGAS_PYTEST=1; }
PREFIXO_DE_TELA=""
command -v dbus-run-session >/dev/null 2>&1 && PREFIXO_DE_TELA="dbus-run-session --"
command -v xvfb-run >/dev/null 2>&1 && PREFIXO_DE_TELA="${PREFIXO_DE_TELA:+$PREFIXO_DE_TELA }xvfb-run -a"

_tres_campos() {
  local resto
  _a="${1%%$'\t'*}"; resto="${1#*$'\t'}"
  if [ "$resto" = "$1" ]; then _b=""; _c=""; return; fi
  _b="${resto%%$'\t'*}"; _c="${resto#*$'\t'}"
  [ "$_c" = "$resto" ] && _c=""
  return 0
}
[ -n "${CI:-}" ] && SEM_MEMORIA=1
OUT="$LAR_DE_MENTIRA/saidas"
mkdir -p "$OUT"
MEM_PASTA=""
declare -A G_LINHA_DE=()
if [ "$SEM_MEMORIA" -eq 0 ] && [ "$N" -gt 0 ]; then
  _linhas=""
  for ((n = 0; n < N; n++)); do
    [ "${G_ESTADO[n]}" = rodar ] || continue
    _resolvido="${G_ARGV[n]}"
    [ "${G_RUN[n]}" = bin ] && _resolvido="$(_bin "${_resolvido%% *}") ${_resolvido#* }"
    G_LINHA_DE["${G_ID[n]}"]="${G_ID[n]}|${G_RUN[n]}|${_resolvido}|${G_ENT[n]}"
    _linhas+="${G_LINHA_DE[${G_ID[n]}]}"$'\n'
  done
  _chaves="$("$PY" "$RAIZ/scripts/recibo_da_medida.py" chaves --raiz "$RAIZ" \
             <<<"$_linhas" 2>"$OUT/memoria.err")" || _chaves=""
  [ -s "$OUT/memoria.err" ] && sed 's/^/  /' "$OUT/memoria.err"
  declare -A _CHAVE_DE=() _DICA_DE=()
  while IFS= read -r _l; do
    _tres_campos "$_l"
    case "$_a" in
      "#pasta") MEM_PASTA="$_b" ;;
      "") ;;
      *) _CHAVE_DE["$_a"]="$_b"; _DICA_DE["$_a"]="${_c:-0}" ;;
    esac
  done <<<"$_chaves"
  for ((n = 0; n < N; n++)); do
    [ "${G_ESTADO[n]}" = rodar ] || continue
    G_DICA[n]="${_DICA_DE[${G_ID[n]}]:-0}"
    _k="${_CHAVE_DE[${G_ID[n]}]:-}"
    [ -n "$MEM_PASTA" ] && [ -n "$_k" ] || continue
    G_CHAVE[n]="$_k"
    [ -e "$MEM_PASTA/${G_ID[n]}.$_k" ] && G_ESTADO[n]="lembrado"
  done
fi

_comando_do_portao() {
  local i="$1" runner="${G_RUN[$1]}" argv="${G_ARGV[$1]}" cmd
  if [ "$runner" = pytest ]; then
    mkdir -p "$LAR_DE_MENTIRA/$i"/{config,data,cache,state,runtime,tmp}
    chmod 700 "$LAR_DE_MENTIRA/$i/runtime"
    _lar_sem_portal "$LAR_DE_MENTIRA/$i/data"
  fi
  case "$runner" in
    py)   cmd="$PY $argv" ;;
    bash) cmd="bash $argv" ;;
    bin)  cmd="$(_bin "${argv%% *}") ${argv#* }" ;;
    pytest) cmd="env ${_AMBIENTE_DE_MENTIRA[*]//$LAR_DE_MENTIRA/$LAR_DE_MENTIRA/$i} TMPDIR=$LAR_DE_MENTIRA/$i/tmp $PREFIXO_DE_TELA $PY -m pytest -q -p no:cacheprovider $argv"
            [ -n "$SEMAFORO" ] && cmd="$SEMAFORO $cmd" ;;
  esac
  echo "$cmd"
}

_roda_um() {
  local n="$1" cmd inicio fim rc
  cmd="$(_comando_do_portao "$n")"
  inicio=$(date +%s%N)
  ( cd "$RAIZ" && eval "$cmd" ) > "$OUT/$n.out" 2>&1
  rc=$?
  fim=$(date +%s%N)
  printf '%d' $(( (fim - inicio) / 1000000 )) > "$OUT/$n.ms"
  printf '%d' "$rc" > "$OUT/$n.rc.tmp" && mv -f "$OUT/$n.rc.tmp" "$OUT/$n.rc"
}

_escalona() {
  local vagas="$1" rodando=0 n; shift
  for n in "$@"; do
    while [ "$rodando" -ge "$vagas" ]; do wait -n 2>/dev/null; rodando=$((rodando - 1)); done
    _roda_um "$n" &
    rodando=$((rodando + 1))
  done
  wait
}

_mais_lentos_primeiro() {
  local n
  for n in "$@"; do printf '%s %s\n' "${G_DICA[n]:-0}" "$n"; done | sort -s -k1,1nr | awk '{print $2}'
}

_mata_arvore() { local f; for f in $(pgrep -P "$1" 2>/dev/null); do _mata_arvore "$f"; done; kill "$1" 2>/dev/null || true; }
_interrompe() { local f; for f in $(jobs -p); do _mata_arvore "$f"; done; exit 130; }
trap _interrompe INT TERM

GERAL=(); DO_PYTEST=(); TODOS=()
for ((n = 0; n < N; n++)); do
  [ "${G_ESTADO[n]}" = rodar ] || continue
  TODOS+=("$n")
  if [ "${G_RUN[n]}" = pytest ]; then DO_PYTEST+=("$n"); else GERAL+=("$n"); fi
done

_nota_da_vaga=""
[ -n "$SEMAFORO" ] && _nota_da_vaga=" (pela vez-do-pytest)"
[ "$_dentro_da_vaga" -eq 1 ] && _nota_da_vaga=" (dentro de uma vaga que já é sua)"
echo "         vagas   ${VAGAS_GERAIS} gerais, ${VAGAS_PYTEST} de pytest${_nota_da_vaga}"
if [ "$SEM_MEMORIA" -eq 1 ]; then echo "         memória desligada"; else echo "         memória ${MEM_PASTA:-(indisponível)}"; fi
echo

INICIO_DA_CORRIDA=$(date +%s)
ESCALONADORES=()
if [ "$EM_SERIE" -eq 1 ]; then
  _escalona 1 ${TODOS[@]+"${TODOS[@]}"} & ESCALONADORES+=("$!")
else
  if [ ${#GERAL[@]} -gt 0 ]; then
    mapfile -t _ordem < <(_mais_lentos_primeiro "${GERAL[@]}")
    _escalona "$VAGAS_GERAIS" "${_ordem[@]}" & ESCALONADORES+=("$!")
  fi
  if [ ${#DO_PYTEST[@]} -gt 0 ]; then
    mapfile -t _ordem < <(_mais_lentos_primeiro "${DO_PYTEST[@]}")
    _escalona "$VAGAS_PYTEST" "${_ordem[@]}" & ESCALONADORES+=("$!")
  fi
fi

_escalonadores_vivos() {
  local p
  for p in ${ESCALONADORES[@]+"${ESCALONADORES[@]}"}; do kill -0 "$p" 2>/dev/null && return 0; done
  return 1
}

SOMA_MS=0
for ((n = 0; n < N; n++)); do
  id="${G_ID[n]}"; runner="${G_RUN[n]}"
  case "${G_ESTADO[n]}" in
    ausente)
      printf '  %-22s AUSENTE DA ÁRVORE  %s\n' "$id" "${G_ARGV[n]%% *}"
      continue ;;
    lembrado)
      TOTAL=$((TOTAL + 1))
      LEMBRADOS+=("$id")
      _idade=$(( $(date +%s) - $(stat -c %Y "$MEM_PASTA/$id.${G_CHAVE[n]}" 2>/dev/null || date +%s) ))
      printf '  %-22s lembrado  (verde sobre os mesmos bytes, há %s)\n' "$id" \
        "$([ "$_idade" -ge 3600 ] && echo "$((_idade / 3600)) h" || echo "$((_idade / 60 + 1)) min")"
      continue ;;
  esac

  TOTAL=$((TOTAL + 1))
  while [ ! -e "$OUT/$n.rc" ]; do
    _escalonadores_vivos || { [ -e "$OUT/$n.rc" ] || break; }
    sleep 0.1
  done
  if [ -e "$OUT/$n.rc" ]; then
    rc="$(cat "$OUT/$n.rc")"; ms="$(cat "$OUT/$n.ms")"
    saida="$(cat "$OUT/$n.out")"
  else
    rc=125; ms=0; saida="o portão não terminou: a corrida foi interrompida antes dele"
  fi
  SOMA_MS=$((SOMA_MS + ms))

  nao_mediu=0
  case "$saida" in "NÃO MEDIDO"*) nao_mediu=1 ;; esac
  if [ "$rc" -eq 0 ] && [ "$nao_mediu" -eq 1 ]; then
    printf '  %-22s NÃO MEDIDO %5d ms\n' "$id" "$ms"
    printf '%s\n' "$saida" | sed 's/^/      /'
    NAO_MEDIDOS+=("$id")
  elif [ "$rc" -eq 0 ]; then
    printf '  %-22s ok      %6d ms\n' "$id" "$ms"
    pulos=""
    if [ "$runner" = pytest ]; then
      pulos="$(printf '%s\n' "$saida" \
        | grep -E '^[= ]*[0-9]+ (passed|failed|skipped|xfailed|xpassed|errors?|deselected)' \
        | tail -1 | grep -o '[0-9]\+ skipped' | grep -o '[0-9]\+' || true)"
      if [ -n "$pulos" ]; then
        printf '      %s teste(s) pulado(s)\n' "$pulos"
        PULADOS+=("$id: $pulos teste(s) pulado(s)")
      fi
    fi
    [ -z "$pulos" ] && [ -n "${G_CHAVE[n]}" ] && VERDES_TSV+="$id"$'\t'"${G_CHAVE[n]}"$'\t'"$ms"$'\n'
  else
    printf '  %-22s VERMELHO rc=%s %5d ms\n' "$id" "$rc" "$ms"
    printf '%s\n' "$saida" | sed 's/^/      /'
    VERMELHOS+=("$id")
  fi
done
wait 2>/dev/null
trap - INT TERM

if [ -n "$VERDES_TSV" ] && [ -n "$MEM_PASTA" ]; then
  _depois=""
  while IFS=$'\t' read -r _a _b _c; do
    [ -n "$_a" ] && _depois+="${G_LINHA_DE[$_a]:-}"$'\n'
  done <<<"$VERDES_TSV"
  _chaves_depois="$(printf '%s' "$_depois" \
    | "$PY" "$RAIZ/scripts/recibo_da_medida.py" chaves --raiz "$RAIZ" 2>/dev/null)" || _chaves_depois=""
  declare -A _CHAVE_DEPOIS=()
  while IFS= read -r _l; do
    _tres_campos "$_l"
    case "$_a" in "#"*|"") ;; *) _CHAVE_DEPOIS["$_a"]="$_b" ;; esac
  done <<<"$_chaves_depois"
  _confirmados=""; _mudaram=()
  while IFS=$'\t' read -r _a _b _c; do
    [ -n "$_a" ] || continue
    if [ "${_CHAVE_DEPOIS[$_a]:-}" = "$_b" ]; then
      _confirmados+="$_a"$'\t'"$_b"$'\t'"$_c"$'\n'
    else
      _mudaram+=("$_a")
    fi
  done <<<"$VERDES_TSV"
  [ ${#_mudaram[@]} -gt 0 ] \
    && echo "memória: a árvore mudou durante a corrida, e estes verdes não ficam lembrados: ${_mudaram[*]}"
  [ -n "$_confirmados" ] \
    && { printf '%s' "$_confirmados" | "$PY" "$RAIZ/scripts/recibo_da_medida.py" anotar --raiz "$RAIZ" || true; }
fi

PAREDE=$(( $(date +%s) - INICIO_DA_CORRIDA ))
echo
echo "tempo: ${PAREDE} s de parede; $((SOMA_MS / 1000)) s de portão somados; ${#LEMBRADOS[@]} lembrado(s) sem rodar."
if [ ${#AUSENTES[@]} -gt 0 ]; then
  echo "PORTÕES DECLARADOS E AUSENTES DA ÁRVORE (${#AUSENTES[@]}):"
  printf '  %s\n' "${AUSENTES[@]}"
fi
if [ ${#NAO_MEDIDOS[@]} -gt 0 ]; then
  echo "NÃO MEDIDOS (${#NAO_MEDIDOS[@]}): ${NAO_MEDIDOS[*]}"
  echo "  Faltou o DADO, não o conserto — eles não reprovam. Mas também não"
  echo "  entram na conta dos verdes: ninguém pode dizer que estão certos."
fi
_dos_lembrados=""
[ ${#LEMBRADOS[@]} -gt 0 ] && _dos_lembrados=" (${#LEMBRADOS[@]} lembrados de uma corrida anterior sobre os mesmos bytes)"
if [ ${#VERMELHOS[@]} -eq 0 ] && [ ${#AUSENTES[@]} -eq 0 ]; then
  if [ ${#NAO_MEDIDOS[@]} -gt 0 ]; then
    echo "VERDES — $((TOTAL - ${#NAO_MEDIDOS[@]})) de ${TOTAL} portões; ${#NAO_MEDIDOS[@]} NÃO MEDIDO(S)."
  else
    echo "TODOS VERDES — ${TOTAL} portões.${_dos_lembrados}"
  fi
  _sair 0
fi
echo "REPROVOU: ${#VERMELHOS[@]} vermelho(s) de ${TOTAL}${VERMELHOS[0]+ -> }${VERMELHOS[*]:-}"
_sair 1
