"""A identidade do pad virtual é uma regra só (A-IDENTIDADE-DO-PAD-VIRTUAL-E-UMA-REGRA-SO-01).

A regra (docs/protocol/a-identidade-do-pad-virtual.md): o pad veste o `0ce6` só quando o
jogo nomeia o DualSense comum, não nomeia o Edge e nada no caminho dele pede o Edge (a
biblioteca Sony, o Modo Xbox, o Steam Input, a Launch Option que esconde o `0ce6`). Em todo
outro caso, o Edge. A régua confere a regra em todas as combinações de sinais, nos três jogos
da bancada de 22/10/2026, e que a decisão mora num lugar só.
"""
from __future__ import annotations

import ast
import itertools
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import a_roupa_do_jogo as rj
from hefesto_dualsense4unix.integrations.steam_launch_options import IGNORE_SIGNATURE

_METADATA = "Jogo_Data/il2cpp_data/Metadata/global-metadata.dat"
_PERFIL_DO_COMUM = b"PlayStation5USBWindowsNativeProfile"
_PERFIL_DO_EDGE = b"PlayStation5EdgeUSBWindowsNativeProfile"
_PID_DO_COMUM = b"\x4c\x05\xe6\x0c"
_PID_DO_EDGE = b"\x4c\x05\xf2\x0d"
_SEPARA = b"\0" * 12


@pytest.fixture(autouse=True)
def _cache_limpo() -> Any:
    rj._CACHE.clear()
    yield
    rj._CACHE.clear()


def _jogo(raiz: Path, arquivos: dict[str, bytes]) -> Path:
    raiz.mkdir(parents=True)
    for relativo, conteudo in arquivos.items():
        caminho = raiz / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"\0" + conteudo + b"\0")
    return raiz


#: Onde o jogo pode nomear cada modelo: nada, um arquivo do leitor (o InControl), o executável.
_EDGE = {"nada": {}, "arquivo": {"edge": _PERFIL_DO_EDGE}, "exe": {"exe": _PID_DO_EDGE}}
_COMUM = {"nada": {}, "arquivo": {"comum": _PERFIL_DO_COMUM}, "exe": {"exe": _PID_DO_COMUM}}
_SONY = {"nada": b"", "libScePad": b"", "WinDualShock": "WinDualShock".encode("utf-16-le")}
_CAMINHO: dict[str, dict[str, Any]] = {
    "direto": {},
    "modo-xbox": {"modo_xbox": True},
    "steam-input": {"no_steam_input": True},
    "launch-option": {"opcoes_de_lancamento": f"{IGNORE_SIGNATURE} %command%"},
}
_COMBINACOES = list(itertools.product(_EDGE, _COMUM, _SONY, _CAMINHO))


def _arquivos(edge: str, comum: str, sony: str) -> dict[str, bytes]:
    exe = b"MZ" + _SEPARA.join(
        v for v in (_EDGE[edge].get("exe"), _COMUM[comum].get("exe"), _SONY[sony]) if v)
    perfis = [v for v in (_EDGE[edge].get("edge"), _COMUM[comum].get("comum")) if v]
    arquivos = {"Jogo.exe": exe}
    if perfis:
        arquivos[_METADATA] = b"\0".join(perfis)
    if sony == "libScePad":
        arquivos["Jogo_Data/Plugins/libScePad.dll"] = b"x"
    return arquivos


@pytest.mark.parametrize(("edge", "comum", "sony", "caminho"), _COMBINACOES,
                         ids=["-".join(c) for c in _COMBINACOES])
def test_a_regra_em_toda_combinacao(
    tmp_path: Path, edge: str, comum: str, sony: str, caminho: str
) -> None:
    raiz = _jogo(tmp_path / "Jogo", _arquivos(edge, comum, sony))

    roupa, fonte = rj.roupa_do_jogo(raiz, **_CAMINHO[caminho])

    so_o_comum = comum != "nada" and edge == "nada"
    nada_pede_o_edge = sony == "nada" and caminho == "direto"
    assert roupa == ("0ce6" if so_o_comum and nada_pede_o_edge else "0df2"), fonte
    assert fonte, "toda roupa diz de onde veio"


#: Os três jogos da bancada de 22/10/2026, com os sinais que a `ficha_declarada` mediu.
_OS_TRES = {
    "sackboy": (
        {"Jogo.exe": b"MZ" + "WinDualSense".encode("utf-16-le") + _SEPARA + _PID_DO_COMUM
         + _SEPARA + _PID_DO_EDGE},
        ("0df2", "o executável conhece o modelo 0DF2 do Edge"),
    ),
    "dungeons-ii": (
        {"Jogo.exe": b"MZ" + "WinDualShock".encode("utf-16-le") + _SEPARA + _PID_DO_COMUM},
        ("0df2", "a biblioteca Sony (WinDualShock) pede o Edge de hoje"),
    ),
    "mullet-mad-jack": (
        {_METADATA: _PERFIL_DO_COMUM, "Jogo.exe": b"MZ"},
        ("0ce6", f"{_METADATA} declara só o DualSense comum"),
    ),
}


@pytest.mark.parametrize("jogo", sorted(_OS_TRES))
def test_os_tres_jogos_da_bancada(tmp_path: Path, jogo: str) -> None:
    arquivos, esperada = _OS_TRES[jogo]

    assert rj.roupa_do_jogo(_jogo(tmp_path / "Jogo", arquivos)) == esperada


def test_a_decisao_mora_num_lugar_so() -> None:
    """Só a `_a_regra` devolve uma roupa; a leitura do disco devolve o que o jogo nomeia."""
    arvore = ast.parse(Path(rj.__file__).read_text(encoding="utf-8"))
    roupas = {"ROUPA_DO_EDGE", "ROUPA_DO_COMUM"}
    fora: list[str] = []
    for funcao in (n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)):
        for no in ast.walk(funcao):
            if not isinstance(no, ast.Return) or not isinstance(no.value, ast.Tuple):
                continue
            primeiro = no.value.elts[0] if no.value.elts else None
            if isinstance(primeiro, ast.Tuple):
                primeiro = primeiro.elts[0] if primeiro.elts else None
            if isinstance(primeiro, ast.Name) and primeiro.id in roupas and (
                funcao.name != "_a_regra"
            ):
                fora.append(f"{funcao.name}:{no.lineno}")
    assert fora == [], f"roupa decidida fora da regra: {fora}"


def test_a_roupa_nao_depende_de_onde_o_jogo_mora(tmp_path: Path) -> None:
    """A mesma pasta, em dois lugares e com dois nomes, veste a mesma roupa: nada por nome."""
    arquivos = {_METADATA: _PERFIL_DO_COMUM, "Jogo.exe": b"MZ"}
    um = _jogo(tmp_path / "steamapps" / "common" / "Mullet Mad Jack", arquivos)
    outro = _jogo(tmp_path / "Heroic" / "QualquerNome", arquivos)

    assert rj.roupa_do_jogo(um)[0] == rj.roupa_do_jogo(outro)[0] == "0ce6"
