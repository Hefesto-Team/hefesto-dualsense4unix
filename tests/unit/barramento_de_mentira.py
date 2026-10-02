"""Um BlueZ de mentira, para medir a ponte privilegiada sem tocar no rádio dela.

PONTE-SEM-CHAMADOR-01 (20/09/2026). A única forma honesta de medir a lista de
candidatos do verbo `descobrir` é abrindo uma varredura — e abrir varredura na
máquina dela custa de 32% a 43% dos pacotes do adaptador que a hospeda, com
quatro DualSense de pé. Por isso `scripts/bt_ponte_privilegiada.sh` ganhou o
quarto gancho de teste, `HEFESTO_BT_BIN`: uma pasta posta NA FRENTE do `PATH`,
de onde saem o `busctl` e o `bluetoothctl` que ele chama.

Com ela, o barramento que responde é o desta pasta — respostas lidas de
arquivo, nenhuma chamada de D-Bus, nenhum adaptador tocado. O gancho é inerte
sob sudo, como os outros três (contenção 3 do cabeçalho do script).

**Este módulo não é um arquivo de teste** — é a bancada que dois arquivos de
teste usam: o da ponte (`test_a_ponte_devolve_os_candidatos.py`) e o do módulo
Python que a chama (`test_o_gesto_de_pareamento.py`). Escrevê-la duas vezes
deixaria duas verdades sobre o mesmo barramento, e o segundo arquivo passaria a
medir a cópia dele em vez da ponte.
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
PONTE = RAIZ_DO_REPO / "scripts" / "bt_ponte_privilegiada.sh"

ADAPTADOR = "aa:bb:cc:00:00:11"
CONTROLE = "aa:bb:cc:00:00:22"
VIZINHO = "aa:bb:cc:00:00:44"

#: O que os seis objetos de DualSense do BlueZ responderam na mesa dela em
CLASSE_DO_DUALSENSE = 9480
ICONE_DO_DUALSENSE = "input-gaming"

HCI = "hci9"

_BUSCTL = """#!/usr/bin/env bash
# `busctl` de mentira: responde do disco, nunca do barramento.
set -u
raiz="${BUSCTL_FALSO_RAIZ}"
case "${1:-}" in
    tree)
        cat "${raiz}/tree"
        [[ -e "${raiz}/marcador" && -f "${raiz}/tree-tarde" ]] && cat "${raiz}/tree-tarde"
        exit 0
        ;;
    get-property)
        arquivo="${raiz}/props/${3//\\//__}.${5:-}"
        [[ -f "${arquivo}" ]] || exit 1
        cat "${arquivo}"
        exit 0
        ;;
    call|set-property)
        # Anotar é o ponto: é por aqui que a régua confere QUAL caminho D-Bus
        # recebeu o `Pair`, e que ele é o do adaptador escolhido.
        printf '%s\\n' "$*" >>"${raiz}/chamadas"
        [[ -e "${raiz}/pair-recusa" ]] && exit 1
        exit 0
        ;;
esac
exit 1
"""

_BLUETOOTHCTL = """#!/usr/bin/env bash
set -u
raiz="${BUSCTL_FALSO_RAIZ}"
seg=5
#: `varrendo` nasce com o PID desta janela, e é pelo PID que a régua do sinal
#: mede se a varredura caiu junto com a ponte — ver `ainda_varrendo`. O `trap`
#: só arruma a saída pelo `--timeout`.
printf '%s\\n' "$$" >"${raiz}/varrendo"
trap 'rm -f -- "${raiz}/varrendo"' EXIT
printf '%s\\n' "$*" >>"${raiz}/argv"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --timeout) seg="${2:-5}"; shift 2 ;;
        --init-script) [[ -f "${2:-}" ]] && cat "$2" >>"${raiz}/roteiro"; shift 2 ;;
        *) shift ;;
    esac
done
( sleep 1; : >"${raiz}/marcador" ) &
sleep "${seg}"
"""


def ainda_varrendo(raiz: Path) -> bool:
    """A janela de mentira ainda está de pé AGORA? Pergunta ao processo dela."""
    marcador = raiz / "varrendo"
    try:
        texto = marcador.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return False
    if not texto:
        return True
    try:
        linha = Path(f"/proc/{int(texto)}/cmdline").read_bytes()
        estado = Path(f"/proc/{int(texto)}/stat").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    vivo = estado.rsplit(")", 1)[-1].split()[0] != "Z"
    return vivo and str(raiz / "bin" / "bluetoothctl").encode() in linha


def caminho_do(mac: str) -> str:
    """O caminho D-Bus deste endereço sob :data:`HCI`."""
    return f"/org/bluez/{HCI}/dev_{mac.upper().replace(':', '_')}"


def _prop(raiz: Path, caminho: str, nome: str, valor: str) -> None:
    (raiz / "props" / f"{caminho.replace('/', '__')}.{nome}").write_text(
        valor + "\n", encoding="utf-8"
    )


def montar(tmp_path: Path) -> Path:
    """Um BlueZ de mentira: um adaptador, um controle e um vizinho atrasado."""
    raiz = tmp_path / "barramento"
    (raiz / "bin").mkdir(parents=True)
    (raiz / "props").mkdir(parents=True)
    for nome, corpo in (("busctl", _BUSCTL), ("bluetoothctl", _BLUETOOTHCTL)):
        alvo = raiz / "bin" / nome
        alvo.write_text(corpo, encoding="utf-8")
        alvo.chmod(0o755)

    adaptador = f"/org/bluez/{HCI}"
    controle = caminho_do(CONTROLE)
    vizinho = caminho_do(VIZINHO)
    (raiz / "tree").write_text(f"{adaptador}\n{controle}\n", encoding="utf-8")
    (raiz / "tree-tarde").write_text(f"{vizinho}\n", encoding="utf-8")

    _prop(raiz, adaptador, "Address", f's "{ADAPTADOR.upper()}"')
    _prop(raiz, controle, "Address", f's "{CONTROLE.upper()}"')
    _prop(raiz, controle, "Alias", 's "DualSense Wireless Controller"')
    _prop(raiz, controle, "Paired", "b false")
    _prop(raiz, controle, "Class", f"u {CLASSE_DO_DUALSENSE}")
    _prop(raiz, vizinho, "Address", f's "{VIZINHO.upper()}"')
    _prop(raiz, vizinho, "Alias", 's "fone\tda\nvizinha"')
    _prop(raiz, vizinho, "Paired", "b true")
    return raiz


ADAPTADOR_QUE_VARRE = "aa:bb:cc:00:00:a1"
ADAPTADOR_PARADO = "aa:bb:cc:00:00:a2"
ADAPTADOR_FOLGADO = "aa:bb:cc:00:00:a3"


def montar_adaptadores(
    tmp_path: Path,
    adaptadores: dict[str, tuple[str | None, str | None]],
) -> Path:
    """Um BlueZ de mentira feito só de ADAPTADORES, para a leitura de varredura."""
    raiz = tmp_path / "barramento-de-adaptadores"
    (raiz / "bin").mkdir(parents=True)
    (raiz / "props").mkdir(parents=True)
    alvo = raiz / "bin" / "busctl"
    alvo.write_text(_BUSCTL, encoding="utf-8")
    alvo.chmod(0o755)

    caminhos = [f"/org/bluez/{hci}" for hci in adaptadores]
    linhas = ["/org/bluez", *caminhos, caminho_do(CONTROLE)]
    (raiz / "tree").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    for hci, (endereco, varrendo) in adaptadores.items():
        caminho = f"/org/bluez/{hci}"
        if varrendo is not None:
            _prop(raiz, caminho, "Discovering", f"b {varrendo}")
        if endereco is not None:
            _prop(raiz, caminho, "Address", f's "{endereco.upper()}"')
    return raiz


def ambiente_de_leitura(raiz: Path) -> dict[str, str]:
    """As variáveis que fazem um `busctl` chamado por NOME cair nesta pasta."""
    return {
        "PATH": f"{raiz / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
        "BUSCTL_FALSO_RAIZ": str(raiz),
    }


def ambiente(raiz: Path) -> dict[str, str]:
    """O ambiente que faz a ponte falar com este barramento, e só com ele."""
    env = dict(os.environ)
    env["HEFESTO_BT_BIN"] = str(raiz / "bin")
    env["BUSCTL_FALSO_RAIZ"] = str(raiz)
    env["HEFESTO_BT_LOG_DEST"] = "none"
    env["HEFESTO_BT_LIB"] = str(raiz / "lib-de-mentira")
    env.pop("SUDO_UID", None)
    env.pop("SUDO_USER", None)
    return env
