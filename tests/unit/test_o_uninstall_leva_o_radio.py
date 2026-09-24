"""O `uninstall.sh` leva o que a leva do rádio instalou — e só o que é dela.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026). A leva do rádio pôs na máquina
coisas que o uninstall de antes não conhecia:

- o NOME DO LUGAR no Alias de cada adaptador (ENTRADA-A-ENTRADA-02). O bloco de
  reversão olhava só o PRIMEIRO adaptador e só tirava o prefixo «Nintendo »; o
  rádio dela ficava chamado «Sofá» para sempre (P-11);
- o registro dos lugares dos adaptadores (BLUEZ-UM-DONO-01), que é ESTADO e
  sai sempre (P-6);
- o diário do rádio da sessão e a marca do boot do kernel-watch
  (O-DIARIO-DO-RADIO-01), que são HISTÓRICO e seguem a doutrina dos dados
  dela: ficam por padrão, saem com --purge-config (P-2).

Os blocos são recortados do `uninstall.sh` REAL e rodados num lar de mentira,
com `sudo` e `busctl` de mentira que só anotam — nada escala privilégio e nada
fala com o BlueZ de ninguém.

A MORDIDA, medida: tirar o ramo `_e_do_hefesto` do bloco dos nomes reprova os
três casos de lugar; tirar o `rm -f` do `lugares-dos-adaptadores.json`, o
teste dele; trocar o `KEEP_CONFIG` da marca do boot por um `rm` incondicional,
o teste da marca.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")


def _recorte(inicio: str, fim: str) -> str:
    a = UNINSTALL.index(inicio)
    b = UNINSTALL.index(fim, a)
    return UNINSTALL[a:b]


def _fake(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# 1. Os nomes dos adaptadores (P-11)
# ---------------------------------------------------------------------------

BLOCO_DOS_NOMES = _recorte(
    "# BT-NINTENDO-ACTIVE-01: reverter a link policy",
    "    # O carimbo da desinstalação, um só:",
)


#: O `busctl` de mentira imprime como o de verdade. O dublê de antes devolvia o
#: texto CRU, e o `busctl` do systemd escapa em C todo byte fora do ASCII
#: (`cescape`): «Sofá» sai `s "Sof\303\241"` — medido num barramento privado
#: com o systemd 255 dela (23/09/2026). Com o dublê cru, o uninstall que
#: comparava o texto escapado com o nome do `maquina.json` passava aqui e, na
#: máquina de verdade, deixava o lugar com acento no rádio e ainda gravava de
#: volta o texto escapado. Este dá as duas formas do real: a escapada e a do
#: `--json=short`. Propriedade ausente é erro, como no real.
_BUSCTL_DE_MENTIRA = """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

args = sys.argv[1:]
json_curto = "--json=short" in args
args = [a for a in args if not a.startswith("--json")]
if args[:1] != ["get-property"]:
    sys.exit(0)
arquivo = Path(PROPS) / (args[2].rsplit("/", 1)[-1] + "." + args[4])
if not arquivo.is_file():
    sys.exit(1)
texto = arquivo.read_text(encoding="utf-8")
if json_curto:
    print(json.dumps({"type": "s", "data": texto}, ensure_ascii=False, separators=(",", ":")))
    sys.exit(0)
ESPECIAIS = {7: "a", 8: "b", 12: "f", 10: "n", 13: "r", 9: "t", 11: "v", 92: "\\\\", 34: '"', 39: "'"}
saida = []
for byte in texto.encode("utf-8"):
    if byte in ESPECIAIS:
        saida.append("\\\\" + ESPECIAIS[byte])
    elif byte < 32 or byte >= 127:
        saida.append("\\\\%03o" % byte)
    else:
        saida.append(chr(byte))
print('s "' + "".join(saida) + '"')
"""


def _busctl_como_o_de_verdade(alvo: Path, props: Path) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(
        _BUSCTL_DE_MENTIRA.replace("Path(PROPS)", f"Path({str(props)!r})"), encoding="utf-8"
    )
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _mesa(tmp_path: Path, adaptadores: dict[str, tuple[str, str]], lugares: list[str]):
    fakes = tmp_path / "fakes"
    sysfs = tmp_path / "sysfs"
    props = tmp_path / "props"
    casa = tmp_path / "casa"
    for pasta in (sysfs, props, casa):
        pasta.mkdir()
    for hci, (alias, nome) in adaptadores.items():
        (sysfs / hci).mkdir()
        (props / f"{hci}.Alias").write_text(alias, encoding="utf-8")
        (props / f"{hci}.Name").write_text(nome, encoding="utf-8")
    config = casa / ".config" / "hefesto-dualsense4unix"
    config.mkdir(parents=True)
    (config / "maquina.json").write_text(
        json.dumps(
            {
                "version": 1,
                "lugares": {
                    f"pci-0000:00:14.0-usb-0:{i}:1.0": {"nome": n}
                    for i, n in enumerate(lugares)
                },
            }
        ),
        encoding="utf-8",
    )
    _fake(fakes, "sudo", 'printf "SUDO:%s\\n" "$(printf "[%s]" "$@")"\nexit 0\n')
    _busctl_como_o_de_verdade(fakes / "busctl", props)
    # Sem `hciconfig`: a metade da link policy não é o que esta régua mede.
    _fake(fakes, "hciconfig", "exit 1\n")
    script = "set -uo pipefail\n" 'log() { printf "[uninstall] %s\\n" "$*"; }\n' + BLOCO_DOS_NOMES
    ambiente = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(casa),
        "HEFESTO_SYSFS_BLUETOOTH": str(sysfs),
        "LC_ALL": "C.UTF-8",
    }
    return subprocess.run(
        [BASH, "-c", script], env=ambiente, capture_output=True, text=True, timeout=60, check=False
    )


def _escritas(saida: str) -> dict[str, str]:
    """`{hciN: alias escrito}` das chamadas `sudo busctl set-property`."""
    escritas: dict[str, str] = {}
    for linha in saida.splitlines():
        if not linha.startswith("SUDO:[busctl][set-property]"):
            continue
        partes = linha.removeprefix("SUDO:")[1:-1].split("][")
        escritas[partes[3].rsplit("/", 1)[-1]] = partes[-1]
    return escritas


def test_o_nome_do_lugar_volta_ao_padrao_em_todo_adaptador(tmp_path: Path) -> None:
    r = _mesa(
        tmp_path,
        {
            "hci0": ("Nintendo Sofá", "meu-pc"),
            "hci1": ("Mesa da TV", "meu-pc"),
            "hci2": ("Nintendo meu-pc", "meu-pc"),
            "hci3": ("Nintendo Nome Dela", "meu-pc"),
            "hci4": ("Outro Nome", "meu-pc"),
        },
        ["Sofá", "Mesa da TV"],
    )
    assert r.returncode == 0, r.stderr
    escritas = _escritas(r.stdout)
    assert escritas.get("hci0") == "", (
        "o nome do lugar com o prefixo ficou no adaptador depois do uninstall:\n" + r.stdout
    )
    assert escritas.get("hci1") == "", (
        "o nome do lugar SEM o prefixo ficou no adaptador (o bloco só olhava o «Nintendo »):\n"
        + r.stdout
    )
    assert escritas.get("hci2") == "", "«Nintendo » + o nome do sistema é inteiro do Hefesto"
    assert escritas.get("hci3") == "Nome Dela", (
        "um nome que não é do Hefesto tem de ficar — só o prefixo sai:\n" + r.stdout
    )
    assert "hci4" not in escritas, "um nome de terceiro, sem o prefixo, não é tocado"
    assert "devolvido ao padrão do sistema" in r.stdout


def test_o_nome_de_fabrica_do_bluez_com_numero_volta_ao_padrao(tmp_path: Path) -> None:
    """O « #N» que o BlueZ põe em cada adaptador não faz do nome uma escolha dela.

    Medido no ensaio do uninstall na máquina dela (23/09): o hci0 tinha o Alias
    «Nintendo MeowSystem #1» e o Name «MeowSystem»; o hci1, «Nintendo
    MeowSystem» e «MeowSystem #2». O plugin `hostname` do BlueZ dá ao adaptador
    padrão o nome da máquina e aos outros «<nome> #<índice+1>» — o número muda
    quando a ordem dos adaptadores muda, e o prefixo guardou o de antes. Tirar
    só o prefixo deixava os dois com um Alias fixo e trocado. A MORDIDA: voltar
    a comparar o nome inteiro reprova os dois.
    """
    r = _mesa(
        tmp_path,
        {
            "hci0": ("Nintendo MeowSystem #1", "MeowSystem"),
            "hci1": ("Nintendo MeowSystem", "MeowSystem #2"),
            "hci2": ("Nintendo Sala", "MeowSystem #3"),
        },
        [],
    )
    escritas = _escritas(r.stdout)
    assert escritas.get("hci0") == "" and escritas.get("hci1") == "", r.stdout
    assert escritas.get("hci2") == "Sala", r.stdout


def test_o_lugar_com_acento_volta_ao_padrao_e_nada_sai_escapado(tmp_path: Path) -> None:
    """O nome dela tem acento, e o `busctl` de verdade o devolve escapado.

    Conferência da INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09): lido sem
    `--json`, «Nintendo Sofá» chegava ao uninstall como «Nintendo
    Sof\\303\\241». O lugar não casava com o `maquina.json` (ficava no rádio),
    e o ramo do prefixo gravava de volta «Sof\\303\\241» — o nome dela trocado
    por barras e números. A MORDIDA: voltar a ler sem o `--json=short` reprova
    as três linhas de baixo.
    """
    r = _mesa(
        tmp_path,
        {
            "hci0": ("Nintendo Sofá", "Máquina da Tetê"),
            "hci1": ("Escritório", "Máquina da Tetê #2"),
            "hci2": ("Nintendo Canto da Tetê", "Máquina da Tetê #3"),
            "hci3": ("Nintendo Máquina da Tetê #1", "Máquina da Tetê"),
        },
        ["Sofá", "Escritório"],
    )
    assert r.returncode == 0, r.stderr
    escritas = _escritas(r.stdout)
    assert escritas.get("hci0") == "", "o lugar com acento ficou no rádio:\n" + r.stdout
    assert escritas.get("hci1") == "", "o lugar com acento, sem prefixo, ficou:\n" + r.stdout
    assert escritas.get("hci2") == "Canto da Tetê", (
        "o nome que não é do Hefesto tem de voltar como ela o escreveu:\n" + r.stdout
    )
    assert escritas.get("hci3") == "", r.stdout
    assert not any("\\" in valor for valor in escritas.values()), (
        "o uninstall gravou texto ESCAPADO no nome de um adaptador:\n" + r.stdout
    )


def test_sem_maquina_json_o_prefixo_ainda_sai(tmp_path: Path) -> None:
    """A casa sem nenhum lugar declarado: o comportamento de antes, intacto."""
    r = _mesa(tmp_path, {"hci0": ("Nintendo meowsystem", "outra")}, [])
    assert _escritas(r.stdout).get("hci0") == "meowsystem", r.stdout


# ---------------------------------------------------------------------------
# 2. O estado do rádio na sessão (P-2, P-6)
# ---------------------------------------------------------------------------

BLOCO_DA_SESSAO = _recorte(
    "# O RÁDIO DA SESSÃO (a leva do rádio, 23/09/2026)",
    'rmdir "${ESTADO_DO_RADIO}" 2>/dev/null || true\n',
)


def _estado(tmp_path: Path, *, purge: bool) -> tuple[Path, subprocess.CompletedProcess[str]]:
    estado = tmp_path / "estado" / "hefesto-dualsense4unix"
    estado.mkdir(parents=True)
    for nome in (
        "lugares-dos-adaptadores.json",
        "radio-diario.jsonl",
        "radio-diario.jsonl.1",
        "kernel.log",
        "kernel-watch.boot",
    ):
        (estado / nome).write_text("x\n", encoding="utf-8")
    script = (
        "set -uo pipefail\n"
        'log() { printf "[uninstall] %s\\n" "$*"; }\n'
        f"KEEP_CONFIG={0 if purge else 1}\n" + BLOCO_DA_SESSAO
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp_path / "casa"),
            "XDG_STATE_HOME": str(tmp_path / "estado"),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return estado, r


def test_por_padrao_o_estado_sai_e_o_historico_fica_com_carimbo(tmp_path: Path) -> None:
    estado, r = _estado(tmp_path, purge=False)
    assert r.returncode == 0, r.stderr
    sobra = sorted(p.name for p in estado.iterdir())
    assert "lugares-dos-adaptadores.json" not in sobra, (
        "o registro dos lugares é ESTADO e sai sempre — ficou: " + ", ".join(sobra)
    )
    assert "radio-diario.jsonl" not in sobra and "radio-diario.jsonl.1" not in sobra, (
        "o diário ficou com o nome de antes: a próxima instalação o releria no "
        "arranque como se fosse desta vida — " + ", ".join(sobra)
    )
    guardados = [n for n in sobra if n.startswith("radio-diario.pre-uninstall-")]
    assert len(guardados) == 2, f"o diário tem de ficar guardado com carimbo: {sobra}"
    assert "kernel.log" in sobra and "kernel-watch.boot" in sobra, (
        "o kernel.log e a marca do boot andam juntos e ficam por padrão: " + ", ".join(sobra)
    )


def test_com_purge_config_o_historico_sai_inteiro(tmp_path: Path) -> None:
    estado, r = _estado(tmp_path, purge=True)
    assert r.returncode == 0, r.stderr
    assert not estado.exists() or not any(estado.iterdir()), (
        "com --purge-config o histórico do rádio tinha de sair: "
        + ", ".join(sorted(p.name for p in estado.iterdir()))
    )


# ---------------------------------------------------------------------------
# 3. As peças de root, no texto que EXECUTA (a paridade confere o par inteiro)
# ---------------------------------------------------------------------------


def _codigo(texto: str) -> str:
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith(("#", "log "))
    )


def test_a_trava_os_carimbos_e_o_diario_do_root_saem() -> None:
    codigo = _codigo(UNINSTALL)
    assert "rm -rf /run/hefesto-bt-ponte" in codigo, "os carimbos do reinício da ponte ficam"
    assert "/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf" in codigo
    assert "sudo rmdir /run/hefesto-dualsense4unix" in codigo
    assert "/var/lib/hefesto-dualsense4unix/radio-diario.jsonl" in codigo


# ---------------------------------------------------------------------------
# 4. O diário do root vai JUNTO do acervo de bonds guardado (P-2.2)
# ---------------------------------------------------------------------------
#
# Decisão de quem coordena: o diário do rádio do root é o histórico que explica
# a mesa que os bonds descrevem — vai para a MESMA pasta carimbada e não se
# apaga por padrão. O bloco é recortado do uninstall REAL e roda com o
# /var/lib trocado por uma pasta de mentira; o `sudo` de mentira executa o
# comando e RECUSA qualquer argumento que ainda aponte para o /var/lib de
# verdade (a troca tem de ter pegado tudo).
#
# A MORDIDA, medida: tirar o `sudo mv -f "${_diarios_root[@]}"` deixa o diário
# no caminho de antes, e o primeiro teste reprova.

VAR_LIB = "/var/lib/hefesto-dualsense4unix"
BLOCO_DOS_BONDS = _recorte(
    "    # O carimbo da desinstalação, um só:",
    "    sudo systemctl daemon-reload >/dev/null 2>&1 || true\n",
)


def _acervo(tmp_path: Path, *, purge: bool, com_bonds: bool = True) -> Path:
    raiz = tmp_path / "var-lib"
    raiz.mkdir()
    if com_bonds:
        (raiz / "bt-bonds").mkdir()
        (raiz / "bt-bonds" / "snapshot-1.tar").write_text("bonds\n", encoding="utf-8")
    for nome in ("radio-diario.jsonl", "radio-diario.jsonl.1"):
        (raiz / nome).write_text('{"o_que": "x"}\n', encoding="utf-8")
    fakes = tmp_path / "fakes-acervo"
    _fake(
        fakes,
        "sudo",
        'for a in "$@"; do\n'
        '  [[ "$a" == *' + VAR_LIB + '* ]] && { echo "RECUSEI $a" >&2; exit 97; }\n'
        "done\n"
        'exec "$@"\n',
    )
    bloco = BLOCO_DOS_BONDS.replace(VAR_LIB, str(raiz))
    assert VAR_LIB not in bloco
    script = (
        "set -uo pipefail\n"
        'log() { printf "[uninstall] %s\\n" "$*"; }\n'
        f"KEEP_CONFIG={0 if purge else 1}\nREMOVE_UDEV=0\n" + bloco
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "RECUSEI" not in r.stderr, r.stderr
    return raiz


def test_o_diario_do_root_vai_junto_dos_bonds_guardados(tmp_path: Path) -> None:
    raiz = _acervo(tmp_path, purge=False)
    guardados = sorted(raiz.glob("bt-bonds.pre-uninstall-*"))
    assert len(guardados) == 1, sorted(p.name for p in raiz.iterdir())
    dentro = sorted(p.name for p in guardados[0].iterdir())
    assert dentro == ["radio-diario.jsonl", "radio-diario.jsonl.1", "snapshot-1.tar"], dentro
    assert not list(raiz.glob("radio-diario*")), (
        "o diário ficou no caminho de antes: a próxima instalação o releria como desta vida"
    )


def test_sem_bonds_o_diario_ainda_e_guardado(tmp_path: Path) -> None:
    raiz = _acervo(tmp_path, purge=False, com_bonds=False)
    guardados = sorted(raiz.glob("bt-bonds.pre-uninstall-*"))
    assert len(guardados) == 1
    assert sorted(p.name for p in guardados[0].iterdir()) == [
        "radio-diario.jsonl",
        "radio-diario.jsonl.1",
    ]


def test_com_purge_config_bonds_e_diario_saem_juntos(tmp_path: Path) -> None:
    raiz = _acervo(tmp_path, purge=True)
    assert sorted(p.name for p in raiz.iterdir()) == []
