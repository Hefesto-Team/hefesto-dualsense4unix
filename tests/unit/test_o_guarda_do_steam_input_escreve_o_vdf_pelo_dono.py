"""O-GUARDA-DO-STEAM-INPUT-ESCREVE-O-VDF-PELO-DONO-01: o ``--apply-quiet`` troca o vdf pelo dono.

O ``scripts/disable_steam_input.sh`` transforma o ``localconfig.vdf`` e entrega o texto ao dono dos
arquivos de terceiro (``steam_input_ponte.py --gravar-vdf``): cópia de antes com carimbo que não
repete, troca por inteiro e poda por família exata. O script roda DE VERDADE num lar de mentira
(``HOME`` e XDG desviados, ``pgrep``/``steam``/``pkill``/``sleep`` dublês); o vdf é sempre o de
mentira, nunca o da Steam.

O roteiro também viaja nos pacotes (``/usr/share/hefesto-dualsense4unix/scripts``), sem o ``src``
do checkout ao lado: ali o dono se acha pelo Python do produto.

A MORDIDA da sprint: com o script de antes (``cp`` com ``date +%s`` e ``cat`` por cima do vdf), a
rodada de vinte edições deixa uma ou duas cópias em vez de seis, a queda no meio da escrita deixa o
vdf pela metade, a falha no dono não chega ao guarda, e a restauração pega a cópia da família
vizinha; sem o ``_ponte_instalada``, o roteiro instalado recusa escrever.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "disable_steam_input.sh"
PONTE = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "steam_input_ponte.py"
BASH = shutil.which("bash") or "/bin/bash"

_MODELO = (
    '"UserLocalConfigStore"\n'
    "{\n"
    '\t"system"\n'
    "\t{\n"
    '\t\t"SteamController_PSSupport"\t\t"2"\n'
    '\t\t"SteamController_SwitchSupport"\t\t"2"\n'
    '\t\t"Rodada"\t\t"{rodada}"\n'
    "\t}\n"
    "}\n"
)


def _vdf(rodada: int | str) -> str:
    return _MODELO.replace("{rodada}", str(rodada))


@pytest.fixture()
def lar(tmp_path: Path) -> dict[str, Any]:
    casa = tmp_path / "lar"
    vdf = casa / ".steam" / "steam" / "userdata" / "1234" / "config" / "localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(_vdf(0), encoding="utf-8")
    (tmp_path / "estado").mkdir()
    (tmp_path / "run").mkdir()
    stubs = tmp_path / "stubs"
    stubs.mkdir()

    def dubla(nome: str, corpo: str) -> None:
        caminho = stubs / nome
        caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
        caminho.chmod(0o755)

    dubla("pgrep", "exit 1")
    dubla("steam", "exit 0")
    dubla("pkill", "exit 0")
    dubla("sleep", "exit 0")
    return {"casa": casa, "vdf": vdf, "stubs": stubs, "tmp": tmp_path}


def _roda(
    lar: dict[str, Any], *args: str, roteiro: Path = SCRIPT, **extra: str,
) -> subprocess.CompletedProcess[str]:
    casa = lar["casa"]
    assert casa.resolve() != Path(os.path.expanduser("~")).resolve()
    env = {
        "HOME": str(casa),
        "XDG_CONFIG_HOME": str(casa / ".config"),
        "XDG_RUNTIME_DIR": str(lar["tmp"] / "run"),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={lar['tmp'] / 'run' / 'bus'}",
        "PATH": f"{lar['stubs']}:/usr/bin:/bin",
        "LC_ALL": "C.UTF-8",
        **extra,
    }
    return subprocess.run(
        [BASH, str(roteiro), *args], env=env, capture_output=True, text=True,
        check=False, timeout=60)


def _copias(vdf: Path, familia: str = "steam-input") -> list[Path]:
    return sorted(
        (p for p in vdf.parent.iterdir()
         if p.name.startswith(f"{vdf.name}.bak.{familia}-")
         and p.name.removeprefix(f"{vdf.name}.bak.{familia}-").isdigit()),
        key=lambda p: int(p.name.rsplit("-", 1)[1]))


def test_vinte_edicoes_deixam_a_primeira_copia_e_as_cinco_mais_novas(lar: dict[str, Any]) -> None:
    vdf = lar["vdf"]
    for rodada in range(20):
        vdf.write_text(_vdf(rodada), encoding="utf-8")
        resultado = _roda(lar, "--apply-quiet")
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr
        assert '"SteamController_PSSupport"\t\t"0"' in vdf.read_text(encoding="utf-8")

    guardadas = [c.read_text(encoding="utf-8") for c in _copias(vdf)]
    assert guardadas == [_vdf(r) for r in (0, 15, 16, 17, 18, 19)]
    assert not list(vdf.parent.glob("*.hefesto-tmp")) and not list(vdf.parent.glob(".*hefesto*"))


def test_a_queda_no_meio_da_escrita_nunca_deixa_o_vdf_pela_metade(lar: dict[str, Any]) -> None:
    vdf = lar["vdf"]
    antes = vdf.read_text(encoding="utf-8")
    cat = lar["stubs"] / "cat"
    cat.write_text(
        "#!/bin/sh\n"
        f'case "$(tr "\\0" " " < /proc/$PPID/cmdline)" in *"{SCRIPT}"*) ;; *) exit 99 ;; esac\n'
        'head -c 40 -- "$2"\n'
        'kill -KILL "$PPID"\n',
        encoding="utf-8")
    cat.chmod(0o755)

    _roda(lar, "--apply-quiet")

    depois = vdf.read_text(encoding="utf-8")
    assert depois in (antes, antes.replace('"2"', '"0"', 2)), (
        f"o vdf ficou pela metade: {depois!r}")


_PONTE_QUE_FALHA_NA_TROCA = '''import sys
from pathlib import Path

sys.path.insert(0, {pasta!r})

import steam_input_ponte as ponte

_troca = Path.replace


def _disco_cheio(self, alvo):
    if Path(alvo).name == "localconfig.vdf":
        raise OSError(28, "sem espaço no disco")
    return _troca(self, alvo)


Path.replace = _disco_cheio
raise SystemExit(ponte.main(sys.argv[1:]))
'''


def test_a_escrita_que_falha_no_dono_deixa_o_vdf_de_antes_sem_copia_nem_temporario(
    lar: dict[str, Any],
) -> None:
    vdf = lar["vdf"]
    antes = vdf.read_bytes()
    ponte = lar["tmp"] / "ponte_que_falha_na_troca.py"
    ponte.write_text(_PONTE_QUE_FALHA_NA_TROCA.format(pasta=str(PONTE.parent)), encoding="utf-8")

    resultado = _roda(lar, "--apply-quiet", PONTE_PY=str(ponte))

    assert resultado.returncode != 0, resultado.stdout + resultado.stderr
    assert "sem espaço no disco" in resultado.stdout, resultado.stdout
    assert vdf.read_bytes() == antes
    assert sorted(p.name for p in vdf.parent.iterdir()) == ["localconfig.vdf"]


def test_o_roteiro_instalado_sem_o_checkout_ao_lado_acha_o_dono_no_python(
    lar: dict[str, Any],
) -> None:
    instalado = lar["tmp"] / "usr" / "share" / "hefesto-dualsense4unix" / "scripts"
    instalado.mkdir(parents=True)
    roteiro = instalado / SCRIPT.name
    shutil.copy2(SCRIPT, roteiro)
    assert not (instalado.parent / "src").exists()
    vdf = lar["vdf"]
    antes = vdf.read_text(encoding="utf-8")

    resultado = _roda(lar, "--apply-quiet", roteiro=roteiro, PYTHONPATH=str(RAIZ / "src"))

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert '"SteamController_PSSupport"\t\t"0"' in vdf.read_text(encoding="utf-8")
    assert [c.read_text(encoding="utf-8") for c in _copias(vdf)] == [antes]


def test_o_byte_que_nao_e_utf8_passa_sem_traducao(lar: dict[str, Any]) -> None:
    vdf = lar["vdf"]
    bruto = _vdf(0).replace("Rodada", "Rodada\xe9").encode("latin-1")
    vdf.write_bytes(bruto)
    resultado = _roda(lar, "--apply-quiet")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert vdf.read_bytes() == bruto.replace(b'"2"', b'"0"', 2)
    assert _copias(vdf)[0].read_bytes() == bruto


def test_a_restauracao_pega_a_copia_mais_nova_da_familia_exata(lar: dict[str, Any]) -> None:
    vdf = lar["vdf"]
    familia = {100: "velha", 205: "nova"}
    for carimbo, nome in familia.items():
        vdf.with_name(f"{vdf.name}.bak.steam-input-{carimbo}").write_text(
            _vdf(nome), encoding="utf-8")
    vizinha = vdf.with_name(f"{vdf.name}.bak.steam-input-ponte-999")
    vizinha.write_text(_vdf("da-ponte"), encoding="utf-8")
    os.utime(vizinha, (4_000_000_000, 4_000_000_000))

    resultado = _roda(lar, "--restore")

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert vdf.read_text(encoding="utf-8") == _vdf("nova")
