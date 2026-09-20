"""MIC-PADRAO-NO-CABO-01 — o install dizia «monitor» e terminava com o DualSense eleito.

O QUE SE MEDIU no `install.sh --yes` de 13/09/2026, 22:58, com o P1 no CABO (a
sprint `2026-09-13-MIC-PADRAO-NO-CABO-01-…`, §E). O passo [10/11] se chama
«impedir o DualSense de virar o microfone padrão» e imprimiu, nesta ordem:

    [wp-fix] persistido: default.configured.audio.source=hefesto_mic_000003
    [wp-fix] FALHA: a fonte padrão é um MONITOR (hefesto_som_000003.monitor)
          drop-in do WirePlumber instalado (a fonte padrão ainda não é um microfone)
          microfone: camadas 1 e 2 conferidas (doctor.sh --fix-mic)
          microfone padrão do sistema: alsa_input.usb-Sony_…DualSense…iec958-stereo
          (entrada de verdade)

AS TRÊS CAUSAS, reproduzidas com dublês pelo estudo da sprint (§2):

1. o laço de `verify_active_not_dualsense` só esperava o `auto_null` e o DualSense
   passarem. Logo depois do restart, o WirePlumber elege de passagem o sink virtual
   da própria casa (`hefesto_som_…`), e o laço aceitava o `.monitor` dele;
2. o `fix_default_source_monitor` do doctor lia o mesmo monitor logo depois e
   GRAVAVA o DualSense por fallback. A gravação entra na pilha do WirePlumber e
   vence a webcam plugada depois;
3. a linha `persistido:` lia a pilha que o rádio tinha deixado horas antes.

OS DUBLÊS CONTAM CHAMADAS, NUNCA O RELÓGIO. O estudo usou relógio de parede, que
serve para estudar e não para portão: uma máquina lenta vira vermelho
intermitente. Aqui cada chamada do `pactl` é um tique. Os nós ALSA voltam à lista
`A` tiques depois do restart e entram na eleição `B` tiques depois. O `sleep`
também é dublê, então o laço de ~5 s custa zero.

A GUARDA vem antes de qualquer script. O Python confere que cada nome resolve
para o dublê, e o shell confere de novo com `type -P`, com o HOME e o
`XDG_RUNTIME_DIR` no lar de mentira e sem `PULSE_SERVER` nem
`DBUS_SESSION_BUS_ADDRESS`. Se um nome escapar, o shell sai com 97 antes de
rodar qualquer coisa.

AS RÉGUAS, E A MORDIDA DE CADA UMA (arranque a cura e veja reprovar):

    R1  o laço atravessa o monitor de passagem     tirar `! is_monitor_source` do laço
    R2  monitor que não passa continua reprovando  é o contraste da R1
    R3  o passo no cabo diz uma coisa só           devolver o laço; devolver o `case 3)`
    R4  no rádio o passo elege o mic virtual       `hefesto_mic` na exclusão de `fontes_elegiveis`
    R5  nenhum nó ausente é gravado                `pick_target_source_name` lendo o topo da pilha
    R6  «entrada de verdade» só com porta usável   devolver o `*)` da conferência final
    R7  a pilha sai do passo como entrou           devolver o laço e tirar a guarda do §D.7

Nenhum teste deste arquivo toca o áudio da máquina.
"""

# ruff: noqa: E501 — os dublês imprimem linhas de `pactl list` inteiras, e
# quebrá-las inventaria uma saída que o parser do doctor nunca recebe.

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
WP_FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"
INSTALL = RAIZ / "install.sh"
DROPINS = RAIZ / "assets" / "wireplumber"

DS_CARTAO = "alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00"
DS_ENTRADA = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00"
    ".iec958-stereo"
)
DS_SAIDA = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00"
    ".analog-surround-40"
)
WEBCAM = "alsa_input.usb-046d_HD_Pro_Webcam_C920-02.analog-stereo"
ONBOARD = "alsa_input.pci-0000_0c_00.4.analog-stereo"

#: MIC-CABO-SPDIF-01, 20/09/2026 — A PORTA DO CENÁRIO «desconhecida» SAI DA
#: MÁQUINA, e não da memória de quem escreveu o dublê.
#:
#: Aqui estava digitada à mão a linha
#: `iec958-stereo-input: Digital Input (S/PDIF) (type: SPDIF, priority: 0,
#: availability unknown)`. Ela já divergia do vivo quando foi conferida, e
#: divergia CALADA — que é o defeito de toda fixture digitada. Em 20/09 ela
#: divergia duas vezes: com o UCM desta casa instalado (HAPTICA-NATIVA-01), a
#: porta de captura do DualSense no cabo nem se chama mais assim.
#:
#: O cenário continua sendo o mesmo — uma porta cuja disponibilidade o ALSA não
#: declara —, e é isso que `test_a_fixture_da_porta_desconhecida_e_gravada`
#: trava: se a gravação deixar de dizer `availability unknown`, o teste acusa,
#: em vez de o dublê passar a medir outro cenário em silêncio.
_FIXTURES_MIC_CABO = RAIZ / "tests" / "fixtures" / "mic-cabo"
_SOURCES_GRAVADA = _FIXTURES_MIC_CABO / "sources-cabo-2026-09-20.txt"


def _primeira_porta_e_ativa(texto: str) -> tuple[str, str]:
    """`(linha da porta, nome da porta ativa)` da PRIMEIRA source do texto.

    Para na primeira `Active Port:`, e desiste se uma segunda source começar
    antes dela. A leitura anterior varria o texto inteiro e guardava a PRIMEIRA
    porta listada com a ÚLTIMA porta ativa — que num texto de mais de uma
    source são de blocos diferentes, e o dublê passaria a descrever uma máquina
    que não existe. Hoje a gravação tem uma source só; a régua não pode
    depender disso.
    """
    porta = ""
    dentro = False
    cabecalhos = nomes = 0
    for linha in texto.splitlines():
        nua = linha.strip()
        # Uma source começa com `Source #N` (saída completa) ou, num recorte de
        # um bloco só como o desta gravação, com a própria linha `Name:`. As
        # duas contam separado: no formato completo, as duas aparecem na MESMA
        # source, e somá-las faria a leitura parar na primeira delas.
        if nua.startswith("Source #"):
            cabecalhos += 1
            if cabecalhos > 1:
                break  # a primeira source acabou sem porta ativa
            continue
        if nua.startswith("Name:"):
            nomes += 1
            if nomes > 1:
                break
            continue
        if nua == "Ports:":
            dentro = True
            continue
        if nua.startswith("Active Port:"):
            return (porta, nua.split(":", 1)[1].strip())
        if dentro and nua:
            porta = porta or nua
    return (porta, "")


def _porta_desconhecida_gravada() -> tuple[str, str]:
    """A dupla lida da gravação de 20/09/2026, ou dois vazios se ela sumiu."""
    if not _SOURCES_GRAVADA.is_file():
        return ("", "")
    return _primeira_porta_e_ativa(
        _SOURCES_GRAVADA.read_text(encoding="utf-8")
    )


PORTA_DESCONHECIDA, ATIVA_DESCONHECIDA = _porta_desconhecida_gravada()
#: Os nós virtuais da casa, na máscara (octetos 4 e 5 zerados).
SOM = "hefesto_som_000003"
MIC = "hefesto_mic_000003"
MIC_ANTIGO = "hefesto_mic_0000ab"
MONITOR_DO_SOM = f"{SOM}.monitor"

#: Todo nome que um dos três programas pode chamar e que falaria com a sessão de
#: som de quem roda a suíte. O `sleep` entra porque o laço dorme 20 vezes.
NOMES_DUBLADOS = ("pactl", "wpctl", "systemctl", "pw-metadata", "pw-dump", "pw-cli", "sleep")

# ---------------------------------------------------------------------------
# O WirePlumber de mentira
# ---------------------------------------------------------------------------

_SIM = r"""# _sim.sh — o WirePlumber de mentira da MIC-PADRAO-NO-CABO-01, por CONTAGEM
# DE CHAMADAS. Lê e escreve só em $HEFESTO_SIM e no HOME desviado.
#
# O modelo é o do estudo da sprint, lido no Lua do WirePlumber 0.5.12:
#   * o configured presente vale 30000+prio (find-selected-default-node.lua);
#   * o i-ésimo da pilha vale 20001-i+prio (state-default-nodes.lua);
#   * senão, vence a maior prioridade (find-best-default-node.lua);
#   * sink é candidato a audio.source, e o pulse publica o `.monitor` (rescan.lua);
#   * nó ALSA sem rota disponível fica fora da eleição (rescan.lua);
#   * só o set-default-source empilha; o restart recarrega o topo da pilha.
# Prioridades: o 51 põe a entrada do DualSense em 1500; hefesto_som em 10;
# hefesto_mic em 1500; os sinks em 1109/736/696; a webcam em 2009.
export LC_ALL=C
SIM="${HEFESTO_SIM:?HEFESTO_SIM não definido}"
ESTADO="${HOME}/.local/state/wireplumber/default-nodes"
DS_ENTRADA="@DS_ENTRADA@"
DS_SAIDA="@DS_SAIDA@"
DS_CARTAO="@DS_CARTAO@"
WEBCAM="@WEBCAM@"
ONBOARD="@ONBOARD@"
SOM="@SOM@"
MIC="@MIC@"
# A porta do cenário «desconhecida», GRAVADA da máquina — ver o cabeçalho do
# módulo de teste. O dublê imprime o que leu, nunca o que alguém lembrou.
PORTA_DESCONHECIDA="@PORTA_DESCONHECIDA@"
ATIVA_DESCONHECIDA="@ATIVA_DESCONHECIDA@"

_le() {
    local v=""
    [[ -f "$1" ]] && v="$(< "$1")"
    printf '%s' "${v:-$2}"
}

registra() { printf '%s\n' "$*" >> "${SIM}/argv.log"; }

tique() { printf '%s\n' "$(( $(_le "${SIM}/tiques" 0) + 1 ))" > "${SIM}/tiques"; }

desde_o_restart() {
    if [[ -f "${SIM}/restart_no_tique" ]]; then
        printf '%s' "$(( $(_le "${SIM}/tiques" 0) - $(_le "${SIM}/restart_no_tique" 0) ))"
    else
        printf '999999'
    fi
}

nos_vivos() {   # nome|classe|prioridade|portas|tipo
    local t a
    t="$(desde_o_restart)"
    a="$(_le "${SIM}/A" 0)"
    echo "${SOM}|Sink|10|nenhuma|virtual"
    if [[ -f "${SIM}/radio" ]]; then echo "${MIC}|Source|1500|nenhuma|virtual"; fi
    if (( t >= a )); then
        echo "alsa_output.pci-0000_0c_00.4.iec958-stereo|Sink|736|nenhuma|alsa"
        echo "alsa_output.pci-0000_0a_00.1.hdmi-stereo|Sink|696|nenhuma|alsa"
        echo "${ONBOARD}|Source|1109|indisponivel|alsa"
        if [[ -f "${SIM}/cabo" ]]; then
            echo "${DS_SAIDA}|Sink|1109|nenhuma|alsa"
            echo "${DS_ENTRADA}|Source|1500|desconhecida|alsa"
        fi
        if [[ -f "${SIM}/webcam" ]]; then echo "${WEBCAM}|Source|2009|disponivel|alsa"; fi
    fi
    return 0
}

ler_pilha() {
    [[ -f "${ESTADO}" ]] || return 0
    awk '
        BEGIN { base = "default.configured.audio.source" }
        { p = index($0, "="); if (p < 2) next; v[substr($0, 1, p - 1)] = substr($0, p + 1) }
        END { k = base; i = 0; while (k in v) { print v[k]; k = base "." i; i++ } }
    ' "${ESTADO}"
}

eleito() {
    local t b cfg pilha melhor="" classe_m="" mscore=-1 score i
    local nome classe prio portas tipo
    t="$(desde_o_restart)"
    b="$(_le "${SIM}/B" 0)"
    cfg="$(_le "${SIM}/configured" "")"
    pilha="$(ler_pilha)"
    while IFS='|' read -r nome classe prio portas tipo; do
        [[ -n "${nome}" ]] || continue
        if [[ "${classe}" == Source && "${portas}" == indisponivel ]]; then continue; fi
        # Um set-default-source dispara nova eleição: o nó ALSA já listado e
        # nomeado no configured entra sem esperar B.
        if [[ "${tipo}" == alsa ]] && (( t < b )) && [[ "${nome}" != "${cfg}" ]]; then
            continue
        fi
        score="${prio}"
        if [[ -n "${cfg}" && "${nome}" == "${cfg}" ]]; then
            score=$((30000 + prio))
        else
            i="$(printf '%s\n' "${pilha}" | awk -v n="${nome}" '$0 == n { print NR; exit }')"
            if [[ -n "${i}" ]]; then score=$((20001 - i + prio)); fi
        fi
        if (( score > mscore )); then mscore="${score}"; melhor="${nome}"; classe_m="${classe}"; fi
    done < <(nos_vivos)
    if [[ -z "${melhor}" ]]; then printf 'auto_null.monitor\n'; return 0; fi
    if [[ "${classe_m}" == Sink ]]; then printf '%s.monitor\n' "${melhor}"; else printf '%s\n' "${melhor}"; fi
}

empilhar() {   # o store hook do WirePlumber: o novo no topo, sem duplicata
    local novo="$1" pilha resto
    pilha="$(ler_pilha)"
    resto="$(grep -v '^default\.configured\.audio\.source\(\.[0-9]\+\)\?=' "${ESTADO}" 2>/dev/null || printf '[default-nodes]')"
    {
        printf '%s\n' "${resto}"
        printf '%s\n%s\n' "${novo}" "${pilha}" | awk -v novo="${novo}" '
            BEGIN { base = "default.configured.audio.source"; n = 0 }
            $0 == "" { next }
            NR > 1 && $0 == novo { next }
            { if (n == 0) print base "=" $0; else print base "." (n - 1) "=" $0; n++ }
        '
    } > "${ESTADO}.novo"
    mv -f "${ESTADO}.novo" "${ESTADO}"
}
"""

_PACTL = r"""#!/bin/bash
# DUBLÊ do pactl: responde o cenário de $HEFESTO_SIM e nunca fala com servidor.
source "$(dirname "$0")/_sim.sh"
tique
registra "pactl $*"

_curta() {
    local id=100 nome classe prio portas tipo
    while IFS='|' read -r nome classe prio portas tipo; do
        [[ -n "${nome}" ]] || continue
        if [[ "${classe}" == Sink ]]; then nome="${nome}.monitor"; fi
        printf '%s\t%s\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n' "${id}" "${nome}"
        id=$((id + 1))
    done < <(nos_vivos)
}

_longa() {
    local id=100 nome classe prio portas tipo
    while IFS='|' read -r nome classe prio portas tipo; do
        [[ -n "${nome}" ]] || continue
        if [[ "${classe}" == Sink ]]; then nome="${nome}.monitor"; fi
        printf 'Source #%s\n\tState: SUSPENDED\n\tName: %s\n\tMute: no\n' "${id}" "${nome}"
        case "${classe}:${portas}" in
            Source:indisponivel)
                printf '\tPorts:\n'
                printf '\t\tanalog-input-front-mic: Front Microphone (type: Mic, priority: 8500, not available)\n'
                printf '\t\tanalog-input-rear-mic: Rear Microphone (type: Mic, priority: 8200, not available)\n'
                printf '\t\tanalog-input-linein: Line In (type: Line, priority: 8100, not available)\n'
                printf '\tActive Port: analog-input-front-mic\n' ;;
            Source:desconhecida)
                printf '\tPorts:\n'
                printf '\t\t%s\n' "${PORTA_DESCONHECIDA}"
                printf '\tActive Port: %s\n' "${ATIVA_DESCONHECIDA}" ;;
            Source:disponivel)
                printf '\tPorts:\n'
                printf '\t\tanalog-input-mic: Microphone (type: Mic, priority: 8700, available)\n'
                printf '\tActive Port: analog-input-mic\n' ;;
        esac
        printf '\n'
        id=$((id + 1))
    done < <(nos_vivos)
}

_cartoes() {
    (( $(desde_o_restart) >= $(_le "${SIM}/A" 0) )) || return 0
    [[ -f "${SIM}/cabo" ]] || return 0
    printf 'Card #91\n\tName: %s\n\tProfiles:\n' "${DS_CARTAO}"
    printf '\t\toff: Off (sinks: 0, sources: 0, priority: 0, available: yes)\n'
    printf '\t\toutput:analog-surround-40+input:analog-stereo: Surround 4.0 + Input (sinks: 1, sources: 1, priority: 1265, available: no)\n'
    printf '\t\toutput:analog-surround-40+input:iec958-stereo: Surround 4.0 + IEC958 (sinks: 1, sources: 1, priority: 1255, available: yes)\n'
    printf '\tActive Profile: output:analog-surround-40+input:iec958-stereo\n\n'
}

_roteiro() {   # R1, R2 e R6: a fonte padrão sai de uma lista, uma linha por leitura
    local n total
    n="$(( $(_le "${SIM}/leituras" 0) + 1 ))"
    printf '%s\n' "${n}" > "${SIM}/leituras"
    total="$(wc -l < "${SIM}/roteiro")"
    if (( n > total )); then n="${total}"; fi
    sed -n "${n}p" "${SIM}/roteiro"
}

case "$*" in
    "get-default-source")
        if [[ -f "${SIM}/roteiro" ]]; then _roteiro; else eleito; fi ;;
    "list sources short"|"list short sources") _curta ;;
    "list sources") _longa ;;
    "list cards") _cartoes ;;
    "get-source-mute "*) printf 'Mute: no\n' ;;
    "set-default-source "*)
        # Como o pactl de verdade: nome fora da lista é recusado. A R5 exige
        # que nenhuma recusa apareça no argv.
        if nos_vivos | awk -F'|' -v a="${2:-}" '$1 == a { achou = 1 } END { exit !achou }'; then
            printf '%s\n' "${2}" > "${SIM}/configured"
            empilhar "${2}"
        else
            registra "RECUSADO: ${2:-}"
            echo "Failure: No such entity" >&2
            exit 1
        fi ;;
    *) : ;;
esac
exit 0
"""

_SYSTEMCTL = r"""#!/bin/bash
# DUBLÊ do systemctl: o restart do WirePlumber marca o tique e recarrega o topo
# da pilha como configured.
source "$(dirname "$0")/_sim.sh"
registra "systemctl $*"
case "$*" in
    *"restart wireplumber"*)
        _le "${SIM}/tiques" 0 > "${SIM}/restart_no_tique"
        ler_pilha | head -n1 > "${SIM}/configured" ;;
esac
exit 0
"""

_WPCTL = r"""#!/bin/bash
# DUBLÊ do wpctl: registra e responde o mínimo que os scripts leem.
source "$(dirname "$0")/_sim.sh"
registra "wpctl $*"
case "${1:-}" in
    status) printf 'Audio\n ├─ Sources:\n │\nSettings\n └─ Default Configured Devices:\n' ;;
    get-volume) printf 'Volume: 0.40\n' ;;
esac
exit 0
"""

_SO_REGISTRA = r"""#!/bin/bash
# DUBLÊ: só registra.
source "$(dirname "$0")/_sim.sh"
registra "$(basename "$0") $*"
exit 0
"""

_SLEEP = r"""#!/bin/bash
# DUBLÊ do sleep: conta a volta e não dorme.
source "$(dirname "$0")/_sim.sh"
printf '%s\n' "$*" >> "${SIM}/sonos"
exit 0
"""

#: Roda ANTES de qualquer script. Sai com 97 se um nome escapar do dublê ou se
#: o ambiente não for o lar de mentira.
GUARDA = r"""set -euo pipefail
for _nome in pactl wpctl systemctl pw-metadata pw-dump pw-cli sleep; do
    if [[ "$(type -P "${_nome}" || true)" != "${HEFESTO_DUBLES}/${_nome}" ]]; then
        printf 'GUARDA: %s não resolve para o dublê\n' "${_nome}" >&2
        exit 97
    fi
done
if [[ "${HOME}" != "${HEFESTO_LAR}" || "${XDG_RUNTIME_DIR}" != "${HEFESTO_LAR}/run" \
      || -n "${PULSE_SERVER:-}" || -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
    printf 'GUARDA: o ambiente não é o lar de mentira\n' >&2
    exit 97
fi
unset _nome
"""

#: As funções do `install.sh` que o bloco do passo usa, com as mesmas saídas.
_PREAMBULO_DO_PASSO = r"""step()  { printf '\n[%s] %s\n' "$1" "$2"; }
warn()  { printf '      aviso: %s\n' "$*"; }
_faria() { :; }
_nao_faria() { :; }
_ensaio_wireplumber() { :; }
DRY_RUN=0
WITH_WIREPLUMBER_FIX=1
WITH_WIREPLUMBER_DISABLE_MIC=0
ROOT_DIR="${HEFESTO_RAIZ}"
"""


@dataclass
class Bancada:
    """Um lar de mentira, a pasta de dublês e o diretório do cenário."""

    dubles: Path
    lar: Path
    sim: Path

    @property
    def env(self) -> dict[str, str]:
        """O ambiente inteiro, montado do zero: nada da sessão de quem roda."""
        return {
            "PATH": f"{self.dubles}:/usr/bin:/bin",
            "HOME": str(self.lar),
            "XDG_CONFIG_HOME": str(self.lar / ".config"),
            "XDG_DATA_HOME": str(self.lar / ".local" / "share"),
            "XDG_STATE_HOME": str(self.lar / ".local" / "state"),
            "XDG_CACHE_HOME": str(self.lar / ".cache"),
            "XDG_RUNTIME_DIR": str(self.lar / "run"),
            "LANG": "C.UTF-8",
            "HEFESTO_SIM": str(self.sim),
            "HEFESTO_DUBLES": str(self.dubles),
            "HEFESTO_LAR": str(self.lar),
            "HEFESTO_RAIZ": str(RAIZ),
            "HEFESTO_WP_FIX": str(WP_FIX),
        }

    def argv(self) -> list[str]:
        log = self.sim / "argv.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def pilha(self) -> list[str]:
        estado = self.lar / ".local" / "state" / "wireplumber" / "default-nodes"
        return [
            linha
            for linha in estado.read_text(encoding="utf-8").splitlines()
            if linha.startswith("default.configured.audio.source")
        ]

    def contagem(self, arquivo: str) -> int:
        caminho = self.sim / arquivo
        if arquivo == "sonos":
            return len(caminho.read_text(encoding="utf-8").splitlines()) if caminho.exists() else 0
        return int(caminho.read_text(encoding="utf-8").strip()) if caminho.exists() else 0


#: A pilha do WirePlumber antes do install das 22:58, na máscara: o topo é o
#: canal do rádio (eleito às 05:30) e o histórico traz o outro canal.
PILHA_DE_ANTES = [
    f"default.configured.audio.source={MIC}",
    f"default.configured.audio.source.0={MIC_ANTIGO}",
]


def montar_bancada(
    base: Path,
    *,
    aparelhos: tuple[str, ...],
    a: int = 0,
    b: int = 0,
    roteiro: list[str] | None = None,
) -> Bancada:
    """Monta dublês, lar e cenário. `a` e `b` são tiques do `pactl` depois do restart."""
    dubles = base / "dubles"
    lar = base / "lar"
    sim = base / "sim"
    for pasta in (dubles, sim, lar / ".local" / "share", lar / ".cache", lar / "run"):
        pasta.mkdir(parents=True, exist_ok=True)

    sim_sh = _SIM
    for chave, valor in {
        "@DS_ENTRADA@": DS_ENTRADA,
        "@DS_SAIDA@": DS_SAIDA,
        "@DS_CARTAO@": DS_CARTAO,
        "@WEBCAM@": WEBCAM,
        "@ONBOARD@": ONBOARD,
        "@SOM@": SOM,
        "@MIC@": MIC,
        "@PORTA_DESCONHECIDA@": PORTA_DESCONHECIDA,
        "@ATIVA_DESCONHECIDA@": ATIVA_DESCONHECIDA,
    }.items():
        sim_sh = sim_sh.replace(chave, valor)
    (dubles / "_sim.sh").write_text(sim_sh, encoding="utf-8")
    for nome, corpo in {
        "pactl": _PACTL,
        "systemctl": _SYSTEMCTL,
        "wpctl": _WPCTL,
        "pw-metadata": _SO_REGISTRA,
        "pw-dump": _SO_REGISTRA,
        "pw-cli": _SO_REGISTRA,
        "sleep": _SLEEP,
    }.items():
        (dubles / nome).write_text(corpo, encoding="utf-8")
        (dubles / nome).chmod(0o755)

    # §E.3 da sprint: os drop-ins 51 e 54 já estavam no lugar.
    conf_d = lar / ".config" / "wireplumber" / "wireplumber.conf.d"
    conf_d.mkdir(parents=True)
    for dropin in (
        "51-hefesto-dualsense-no-default-source.conf",
        "54-hefesto-dualsense-alto-falante-nunca-dorme.conf",
    ):
        shutil.copy(DROPINS / dropin, conf_d / dropin)
    estado = lar / ".local" / "state" / "wireplumber"
    estado.mkdir(parents=True)
    (estado / "default-nodes").write_text(
        "[default-nodes]\n"
        "default.configured.audio.sink=alsa_output.pci-0000_0c_00.4.iec958-stereo\n"
        + "\n".join(PILHA_DE_ANTES)
        + "\n",
        encoding="utf-8",
    )
    (estado / "default-routes").write_text(
        "[default-routes]\n"
        f'{DS_CARTAO}:input:iec958-stereo-input={{"channelVolumes":[1.0, 1.0], "mute":false}}\n',
        encoding="utf-8",
    )

    (sim / "A").write_text(f"{a}\n", encoding="utf-8")
    (sim / "B").write_text(f"{b}\n", encoding="utf-8")
    (sim / "configured").write_text(f"{MIC}\n", encoding="utf-8")
    (sim / "argv.log").write_text("", encoding="utf-8")
    for aparelho in aparelhos:
        (sim / aparelho).write_text("", encoding="utf-8")
    if roteiro is not None:
        (sim / "roteiro").write_text("\n".join(roteiro) + "\n", encoding="utf-8")
    return Bancada(dubles=dubles, lar=lar, sim=sim)


def _rodar(bancada: Bancada, corpo: str) -> subprocess.CompletedProcess[str]:
    """Confere os dublês pelo Python, e o shell confere de novo antes do corpo."""
    for nome in NOMES_DUBLADOS:
        achado = shutil.which(nome, path=bancada.env["PATH"])
        assert achado == str(bancada.dubles / nome), f"GUARDA: {nome} resolve para {achado}"
    res = subprocess.run(
        ["bash", "-c", GUARDA + corpo],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
        env=bancada.env,
    )
    assert res.returncode != 97, f"a guarda recusou rodar: {res.stderr}"
    return res


def bloco_do_passo_10() -> str:
    """Do `step "10/11"` até a régua (`# ---…`) que abre o passo seguinte."""
    texto = INSTALL.read_text(encoding="utf-8")
    inicio = texto.index('step "10/11"')
    fim = re.search(r"^# -{10,}", texto[inicio:], re.MULTILINE)
    assert fim is not None, "fim do bloco do passo 10 não encontrado"
    return texto[inicio : inicio + fim.start()]


def rodar_o_passo(bancada: Bancada) -> subprocess.CompletedProcess[str]:
    """O bloco REAL do passo [10/11], com o wp-fix e o doctor desta árvore."""
    return _rodar(bancada, _PREAMBULO_DO_PASSO + bloco_do_passo_10())


def rodar_o_veredito(bancada: Bancada) -> subprocess.CompletedProcess[str]:
    """Só a `verify_active_not_dualsense` do wp-fix, carregada por `source`."""
    return _rodar(bancada, 'set --\nsource "${HEFESTO_WP_FIX}"\nverify_active_not_dualsense\n')


#: Os cenários do passo inteiro, com `a` e `b` em tiques do `pactl`.
CENARIOS = {
    # No rádio o microfone virtual já está no ar antes do restart.
    "radio": {"aparelhos": ("radio",), "a": 1, "b": 8},
    # O relógio do log das 22:58: o doctor lia o monitor e gravava o DualSense.
    "cabo": {"aparelhos": ("cabo",), "a": 1, "b": 8},
    # O monitor não passa dentro do orçamento do laço.
    "cabo-lento": {"aparelhos": ("cabo",), "a": 1, "b": 1_000_000},
    # A webcam volta à lista três leituras depois do restart.
    "cabo-webcam": {"aparelhos": ("cabo", "webcam"), "a": 4, "b": 8},
}


def _passo(tmp_path: Path, cenario: str) -> tuple[Bancada, subprocess.CompletedProcess[str]]:
    bancada = montar_bancada(tmp_path / cenario, **CENARIOS[cenario])
    res = rodar_o_passo(bancada)
    assert res.returncode == 0, f"o passo abortou:\n{res.stdout}\n{res.stderr}"
    return bancada, res


# ---------------------------------------------------------------------------
# A guarda
# ---------------------------------------------------------------------------


def test_a_guarda_nao_deixa_rodar_sem_o_duble(tmp_path: Path) -> None:
    """A mordida da guarda: sem um dublê, nada roda.

    O `sleep` sai da pasta de dublês e passa a resolver para o do sistema. A
    guarda do shell tem de sair com 97 antes do corpo, que só escreveria no argv.
    """
    bancada = montar_bancada(tmp_path, aparelhos=("cabo",))
    (bancada.dubles / "sleep").unlink()
    res = subprocess.run(
        ["bash", "-c", GUARDA + 'echo rodou >> "${HEFESTO_SIM}/argv.log"\n'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
        env=bancada.env,
    )
    assert res.returncode == 97, res.stderr
    assert "sleep" in res.stderr
    assert bancada.argv() == [], "o corpo rodou com um nome fora do dublê"


# ---------------------------------------------------------------------------
# R1 e R2 — o veredito do wp-fix não depende do relógio
# ---------------------------------------------------------------------------


def test_r1_o_laco_atravessa_o_monitor_de_passagem_ate_a_webcam(tmp_path: Path) -> None:
    """Três leituras do monitor do sink virtual e depois a webcam: OK.

    MORDIDA: tirar `! is_monitor_source` do laço faz a primeira leitura
    encerrar tudo com exit 3 e «FALHA: … MONITOR».
    """
    bancada = montar_bancada(
        tmp_path, aparelhos=("webcam",), roteiro=[MONITOR_DO_SOM] * 3 + [WEBCAM]
    )
    res = rodar_o_veredito(bancada)
    assert res.returncode == 0, f"esperava 0, veio {res.returncode}:\n{res.stdout}"
    assert f"OK: microfone padrão ativo = {WEBCAM}" in res.stdout, res.stdout
    assert "MONITOR" not in res.stdout, res.stdout
    assert bancada.contagem("leituras") == 4, "o laço não esperou o monitor passar"


def test_r1_o_laco_atravessa_o_monitor_de_passagem_ate_o_dualsense(tmp_path: Path) -> None:
    """Três leituras do monitor e depois o DualSense sem outra elegível: o aviso (2).

    MORDIDA: a mesma da régua acima — sem a espera, sai 3 com «FALHA».
    """
    bancada = montar_bancada(
        tmp_path, aparelhos=("cabo",), roteiro=[MONITOR_DO_SOM] * 3 + [DS_ENTRADA]
    )
    res = rodar_o_veredito(bancada)
    assert res.returncode == 2, f"esperava 2, veio {res.returncode}:\n{res.stdout}"
    assert "FALHA" not in res.stdout, res.stdout
    assert "única fonte de captura" in res.stdout, res.stdout


def test_r2_monitor_que_nao_passa_continua_reprovando(tmp_path: Path) -> None:
    """O contraste: sem isto a R1 passaria com um laço que devolve sempre 0 ou 2."""
    bancada = montar_bancada(tmp_path, aparelhos=("cabo",), roteiro=[MONITOR_DO_SOM])
    res = rodar_o_veredito(bancada)
    assert res.returncode == 3, f"esperava 3, veio {res.returncode}:\n{res.stdout}"
    assert f"MONITOR ({MONITOR_DO_SOM})" in res.stdout, res.stdout
    assert bancada.contagem("leituras") == 20, "o monitor foi julgado antes do fim do orçamento"
    assert bancada.contagem("sonos") == 20


# ---------------------------------------------------------------------------
# R3 — o passo inteiro, no cabo, diz uma coisa só
# ---------------------------------------------------------------------------


def test_r3_o_passo_no_cabo_so_com_o_dualsense_diz_uma_coisa_so(tmp_path: Path) -> None:
    """O cenário das 22:58, com o bloco real do install, o wp-fix e o doctor.

    MORDIDA: devolver o laço traz a «FALHA: … MONITOR» de volta. Devolver a
    linha `persistido:` do `show_status` também reprova aqui.
    """
    bancada, res = _passo(tmp_path, "cabo")
    saida = res.stdout
    assert "FALHA" not in saida, saida
    assert "ainda não é um microfone" not in saida, saida
    assert "(entrada de verdade)" not in saida, saida
    assert "ÚNICA fonte de" in saida, saida
    assert "(o DualSense, porque é a ÚNICA entrada com porta usável agora)" in saida, saida
    assert "persistido:" not in saida, saida
    assert f"preferência de fonte guardada no WirePlumber (lida do estado dele): {MIC}" in saida
    assert f"pactl set-default-source {DS_ENTRADA}" not in bancada.argv(), bancada.argv()


def test_r3_quando_o_monitor_nao_passa_o_passo_nao_da_dois_vereditos(tmp_path: Path) -> None:
    """O WirePlumber não assenta dentro do orçamento: o veredito é o do fim.

    MORDIDA: devolver o `case 3)` traz «a fonte padrão ainda não é um microfone»;
    devolver a receita do fim traz o `--fix-mic` que acabou de rodar.
    """
    bancada, res = _passo(tmp_path, "cabo-lento")
    saida = res.stdout
    assert "ainda não é um microfone" not in saida, saida
    assert "(o veredito do microfone sai no fim deste passo)" in saida, saida
    assert "rode: bash scripts/doctor.sh --fix-mic" not in saida, saida
    assert f"o microfone padrão do sistema é um MONITOR ({MONITOR_DO_SOM})" in saida, saida
    assert "(entrada de verdade)" not in saida, saida
    assert f"pactl set-default-source {DS_ENTRADA}" not in bancada.argv(), bancada.argv()
    # A VALIDAÇÃO (14/09): o fim mandava «conecte o DualSense (no cabo)» com a
    # entrada dele no ar e o doctor dizendo isso uma linha acima. MORDIDA: trocar
    # o `if [[ -n "${_no_ar}" ]]` do ramo do monitor por `if false`.
    assert "DualSense (no cabo)" not in saida, saida
    assert f"Há uma entrada com porta usável no ar ({DS_ENTRADA})" in saida, saida


def test_r3_sem_entrada_no_ar_o_monitor_ainda_pede_uma_entrada_de_verdade(tmp_path: Path) -> None:
    """O contraste da régua acima: sem entrada com porta usável, pedir hardware é a receita certa.

    MORDIDA: trocar o `if [[ -n "${_no_ar}" ]]` do ramo do monitor por `if true`.
    """
    bancada = montar_bancada(tmp_path, aparelhos=(), roteiro=[MONITOR_DO_SOM])
    res = rodar_o_passo(bancada)
    assert res.returncode == 0, res.stderr
    assert "Há uma entrada com porta usável no ar" not in res.stdout, res.stdout
    assert "Não há comando que resolva sem uma entrada de verdade" in res.stdout, res.stdout


# ---------------------------------------------------------------------------
# R4 — no rádio, o microfone virtual continua sendo o eleito
# ---------------------------------------------------------------------------


def test_r4_no_radio_o_passo_elege_o_microfone_virtual(tmp_path: Path) -> None:
    """§D.2: pelo rádio o eleito é o `hefesto_mic_…`.

    MORDIDA: pôr `hefesto_mic` na exclusão de `fontes_elegiveis` tira a eleição
    do argv (o restart ainda devolve o topo da pilha, e por isso a régua olha o
    argv, não só o OK).
    """
    bancada, res = _passo(tmp_path, "radio")
    assert f"pactl set-default-source {MIC}" in bancada.argv(), bancada.argv()
    assert f"OK: microfone padrão ativo = {MIC}" in res.stdout, res.stdout
    assert f"microfone padrão do sistema: {MIC} (entrada de verdade)" in res.stdout, res.stdout


# ---------------------------------------------------------------------------
# R5 — nada de gravar como padrão um nó que não existe
# ---------------------------------------------------------------------------


def test_r5_o_duble_recusa_no_ausente(tmp_path: Path) -> None:
    """O contraste da R5: o detector de recusa funciona, então o zero dela vale."""
    bancada = montar_bancada(tmp_path, aparelhos=("cabo",))
    res = _rodar(bancada, f'pactl set-default-source "{MIC}" || true\n')
    assert f"RECUSADO: {MIC}" in bancada.argv(), (res.stdout, res.stderr)


@pytest.mark.parametrize("cenario", sorted(CENARIOS))
def test_r5_nenhum_no_ausente_e_gravado(tmp_path: Path, cenario: str) -> None:
    """§D.4. MORDIDA: `pick_target_source_name` lendo o topo da pilha grava o
    `hefesto_mic_…` no cabo, e o dublê recusa como o pactl de verdade."""
    bancada, _res = _passo(tmp_path, cenario)
    recusas = [linha for linha in bancada.argv() if linha.startswith("RECUSADO")]
    assert recusas == [], recusas


# ---------------------------------------------------------------------------
# R6 — «entrada de verdade» só para quem tem porta de captura usável
# ---------------------------------------------------------------------------


def test_r6_a_conferencia_final_nao_chama_de_entrada_de_verdade_quem_grava_silencio(
    tmp_path: Path,
) -> None:
    """§D.5: a onboard com as três portas `not available` grava silêncio.

    MORDIDA: devolver o `*)` de hoje imprime «(entrada de verdade)» para ela.
    """
    bancada = montar_bancada(tmp_path, aparelhos=(), roteiro=[ONBOARD])
    res = rodar_o_passo(bancada)
    assert res.returncode == 0, res.stderr
    assert "(entrada de verdade)" not in res.stdout, res.stdout
    assert (
        f"o microfone padrão do sistema ({ONBOARD}) não tem porta de captura usável"
        in res.stdout
    ), res.stdout


def test_r6_a_webcam_continua_sendo_entrada_de_verdade(tmp_path: Path) -> None:
    """O contraste da R6: sem ele, apagar a frase deixaria a régua verde para sempre."""
    bancada = montar_bancada(tmp_path, aparelhos=("webcam",), roteiro=[WEBCAM])
    res = rodar_o_passo(bancada)
    assert res.returncode == 0, res.stderr
    assert f"microfone padrão do sistema: {WEBCAM} (entrada de verdade)" in res.stdout


def test_r6_o_dualsense_com_outra_entrada_usavel_e_aviso(tmp_path: Path) -> None:
    """§D.2: o DualSense eleito com a webcam ao lado é o caso proibido, não «ÚNICA»."""
    bancada = montar_bancada(tmp_path, aparelhos=("cabo", "webcam"), roteiro=[DS_ENTRADA])
    res = rodar_o_passo(bancada)
    assert res.returncode == 0, res.stderr
    assert "ÚNICA entrada" not in res.stdout, res.stdout
    assert f"mas há outra entrada com porta usável: {WEBCAM}" in res.stdout, res.stdout


# ---------------------------------------------------------------------------
# R7 — a pilha do WirePlumber sai do passo como entrou
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cenario", ["cabo", "cabo-lento"])
def test_r7_a_pilha_sai_do_passo_como_entrou(tmp_path: Path, cenario: str) -> None:
    """No cabo sem outra fonte, nenhum dos três programas grava a preferência.

    MORDIDA: no `cabo`, devolver o laço E tirar a guarda do §D.7 (uma só não
    basta: são duas travas); no `cabo-lento`, tirar só a guarda do §D.7.
    """
    bancada, _res = _passo(tmp_path, cenario)
    assert bancada.pilha() == PILHA_DE_ANTES, bancada.argv()


# ---------------------------------------------------------------------------
# MIC-CABO-SPDIF-01 — a guarda da fixture GRAVADA
# ---------------------------------------------------------------------------


def test_a_fixture_da_porta_desconhecida_e_gravada() -> None:
    """A porta do cenário «desconhecida» tem de vir do disco e valer o cenário.

    Duas coisas, e as duas já falharam nesta casa de jeitos diferentes:

    1. **Ela existe.** Se a gravação sumir, o dublê imprimiria uma linha vazia e
       o cenário viraria «source sem porta» — que é OUTRO cenário, e daria verde
       ou vermelho pelo motivo errado, calado.
    2. **Ela ainda significa «disponibilidade desconhecida».** É o que o nome do
       cenário promete. Se um `pactl` novo passar a declarar a porta, esta linha
       acusa, em vez de sete réguas medirem outra coisa sem ninguém notar.
    """
    assert _SOURCES_GRAVADA.is_file(), (
        f"a gravação de 20/09/2026 sumiu de {_SOURCES_GRAVADA} — sem ela o "
        "dublê imprime porta vazia e o cenário troca de significado"
    )
    assert PORTA_DESCONHECIDA, "a gravação não tem linha de porta"
    assert ATIVA_DESCONHECIDA, "a gravação não tem `Active Port:`"
    assert "availability unknown" in PORTA_DESCONHECIDA, (
        "o cenário se chama «desconhecida»: a porta gravada precisa dizer "
        f"`availability unknown`. Ela diz: {PORTA_DESCONHECIDA!r}"
    )
    assert ATIVA_DESCONHECIDA in PORTA_DESCONHECIDA, (
        "a porta ATIVA tem de ser a porta listada — se divergirem, o dublê "
        "descreve uma máquina que não existe"
    )


def test_a_leitura_da_porta_para_na_primeira_source() -> None:
    """A dupla tem de sair do MESMO bloco, e a gravação de hoje não prova isso.

    Ela tem uma source só, então uma leitura que varresse o arquivo inteiro
    daria o mesmo resultado — e passaria verde guardando a primeira porta de um
    bloco com a última `Active Port:` de outro. Aqui vão duas sources nas duas
    formas que o `pactl` emite (com e sem o cabeçalho `Source #`), e o que se
    cobra é que a segunda não contamine a primeira.
    """
    com_cabecalho = (
        "Source #1\n"
        "\tName: alsa_input.primeira\n"
        "\tPorts:\n"
        "\t\tporta-da-primeira: Primeira (availability unknown)\n"
        "\tActive Port: porta-da-primeira\n"
        "Source #2\n"
        "\tName: alsa_input.segunda\n"
        "\tPorts:\n"
        "\t\tporta-da-segunda: Segunda (available)\n"
        "\tActive Port: porta-da-segunda\n"
    )
    porta, ativa = _primeira_porta_e_ativa(com_cabecalho)
    assert ativa == "porta-da-primeira", f"veio {ativa!r}"
    assert porta.startswith("porta-da-primeira:"), f"veio {porta!r}"

    sem_cabecalho = com_cabecalho.replace("Source #1\n", "").replace(
        "Source #2\n", ""
    )
    porta, ativa = _primeira_porta_e_ativa(sem_cabecalho)
    assert (ativa, porta.startswith("porta-da-primeira:")) == (
        "porta-da-primeira",
        True,
    ), f"veio porta={porta!r} ativa={ativa!r}"
