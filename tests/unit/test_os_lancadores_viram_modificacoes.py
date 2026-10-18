"""Os seis lançadores viram modificações oficiais (OS-SEIS-LANCADORES-VIRAM-MODIFICACOES-01).

O censo, a reposição e a aba Lançadores deixam de ter a lista fixa dos seis e passam a ler os
manifestos de ``mods/de_fabrica/<chave>/hefesto-mod.json``. A régua tem duas pernas:

* os manifestos dão EXATAMENTE as tabelas que o código tinha antes (a lista de antes está
  copiada aqui, de 17/10/2026, e é o oráculo);
* tirar um manifesto tira o lançador do censo, da reposição e do desenho (a mordida: o processo
  de prova lê outra pasta, sem o Heroic).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as reposicao
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.mods.manifesto import ler_manifesto

# --- a lista de antes, copiada do código de 16/10/2026 ----------------------------------------

_ONDE_DE_ANTES = {
    "Heroic": ("com.heroicgameslauncher.hgl", "heroic"),
    "Lutris": ("net.lutris.Lutris", "lutris"),
    "RetroArch": ("org.libretro.RetroArch", "retroarch"),
    "Dolphin": ("org.DolphinEmu.dolphin-emu", "dolphin-emu"),
    "mGBA": ("io.mgba.mGBA", "mgba"),
}
_CARTAO_DE_ANTES = {
    "heroic": ("Heroic",),
    "lutris": ("Lutris",),
    "retroarch": ("RetroArch",),
    "emuladores": ("Dolphin", "mGBA"),
    "flatpak": (),
}
_REPOSICAO_DE_ANTES = (
    ("steam", "Steam", ("steamwebhelper",), None, None),
    ("heroic", "Heroic", ("heroic",), "com.heroicgameslauncher.hgl", "heroic"),
    ("lutris", "Lutris", ("lutris",), "net.lutris.Lutris", "lutris"),
)
#: ``(chave, nome, atalhos, comandos, janelas)`` na ordem dos cartões; a Steam vai na frente.
_EMBUTIDOS_DE_ANTES = (
    ("steam", "Steam", ("steam", "com.valvesoftware.Steam", "steam-native"),
     ("steam", "steam-native"), ()),
    ("heroic", "Heroic (Epic · GOG)", ("com.heroicgameslauncher.hgl", "heroic"), ("heroic",), ()),
    ("lutris", "Lutris", ("net.lutris.Lutris", "lutris"), ("lutris",), ()),
    ("flatpak", "Flatpak", (), ("flatpak",), ()),
    ("retroarch", "RetroArch", ("org.libretro.RetroArch", "retroarch"), ("retroarch",),
     ("com.libretro.RetroArch",)),
    ("emuladores", "Dolphin · mGBA",
     ("org.DolphinEmu.dolphin-emu", "dolphin-emu", "io.mgba.mGBA", "mgba-qt", "mgba"),
     ("dolphin-emu", "mgba-qt", "mgba"), ()),
)
_SEIS = [chave for chave, *_ in _EMBUTIDOS_DE_ANTES]


def _como_tupla(item: desenho.SemCenso) -> tuple[object, ...]:
    return (item.chave, item.nome, item.atalhos, item.comandos, item.janelas)


# --- os manifestos dão a lista de antes --------------------------------------------------------


def test_os_manifestos_dao_as_tabelas_do_censo_de_antes() -> None:
    assert censo._ONDE == _ONDE_DE_ANTES
    assert censo._DO_CARTAO == _CARTAO_DE_ANTES
    assert frozenset({"Lutris"}) == censo._CONFIG_CAI_NOS_DADOS
    assert list(censo._LEITORES) == list(_ONDE_DE_ANTES)
    assert censo._LEITORES["Heroic"] is censo._heroic
    assert censo._LEITORES["mGBA"] is censo._mgba


def test_os_manifestos_dao_a_reposicao_de_antes() -> None:
    visto = tuple((x.chave, x.nome, x.processos, x.flatpak, x.nativo)
                  for x in reposicao.LANCADORES)
    assert visto == _REPOSICAO_DE_ANTES


def test_os_manifestos_dao_os_cartoes_de_antes_na_mesma_ordem() -> None:
    # D-1710-OS-LANCADORES-DE-FABRICA-SAO-MODIFICACOES-OFICIAIS
    assert tuple(_como_tupla(x) for x in desenho.EMBUTIDOS) == _EMBUTIDOS_DE_ANTES
    assert tuple(_como_tupla(x) for x in desenho.SEM_FONTE) == _EMBUTIDOS_DE_ANTES[1:]
    assert _como_tupla(desenho.A_STEAM) == _EMBUTIDOS_DE_ANTES[0]


def test_o_censo_acha_o_nativo_pelo_manifesto() -> None:
    assert censo._agulhas_do_nativo("Dolphin") == (
        ("org.DolphinEmu.dolphin-emu", "dolphin-emu"), ("dolphin-emu",))
    assert censo._agulhas_do_nativo("mGBA") == (("io.mgba.mGBA", "mgba-qt", "mgba"),
                                               ("mgba-qt", "mgba"))
    assert censo._agulhas_do_nativo("Heroic") == (
        ("com.heroicgameslauncher.hgl", "heroic"), ("heroic",))


# --- cada um é uma modificação de verdade ------------------------------------------------------


@pytest.mark.parametrize("chave", _SEIS)
def test_cada_lancador_de_fabrica_e_um_manifesto_que_o_conferidor_aceita(chave: str) -> None:
    manifesto = ler_manifesto(censo.PASTA_DE_FABRICA / chave)
    assert manifesto.id == chave
    assert manifesto.tipos == ["lancador"]
    assert manifesto.permissoes == ["lancador"]
    assert manifesto.lancador is not None


def test_a_pasta_de_fabrica_viaja_dentro_do_pacote() -> None:
    pacote = Path(censo.__file__).resolve().parent.parent
    assert pacote / "mods" / "de_fabrica" == censo.PASTA_DE_FABRICA
    assert sorted(p.name for p in censo.PASTA_DE_FABRICA.iterdir() if p.is_dir()) == sorted(_SEIS)


def test_a_modificacao_de_fora_nao_pede_o_que_e_so_de_fabrica() -> None:
    base = {"rotulo": "X", "comandos": ["x"]}
    for campo, valor in (
        ("reposicao", {"nome": "X", "processos": ["x"]}),
        ("programas", []),
        ("ordem", 0),
        ("interior_lido", True),
    ):
        with pytest.raises(ValueError, match="que não existe"):
            censo.lancador_da_modificacao("x", {**base, campo: valor}, Path("/nao/existe"))


# --- o manifesto de fábrica torto levanta, com o caminho ---------------------------------------


def _fabrica_com(tmp_path: Path, **bloco: object) -> Path:
    """Uma pasta de fábrica de mentira com um lançador só, o bloco ajustado."""
    pasta = tmp_path / "x"
    pasta.mkdir()
    corpo: dict[str, object] = {"rotulo": "X", "ordem": 0, "comandos": ["x"]}
    corpo.update(bloco)
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "x", "nome": "X", "versao": "1", "api": ">=1,<2",  # (noqa-acento): chave do manifesto
        "licenca": "MIT", "tipos": ["lancador"],  # (noqa-acento): chave do manifesto
        "permissoes": ["lancador"], "lancador": corpo}),  # (noqa-acento): chave do manifesto
        encoding="utf-8")
    return tmp_path


def test_o_bloco_certo_de_mentira_le(tmp_path: Path) -> None:
    (item,) = censo.lancadores_de_fabrica(_fabrica_com(tmp_path))
    assert item.bloco.chave == "x" and item.programas == () and item.reposicao is None


@pytest.mark.parametrize("bloco, frase", [
    ({"ordem": -1}, "ordem"),
    ({"ordem": True}, "ordem"),
    ({"interior_lido": "sim"}, "interior_lido"),
    ({"programas": [{"nome": "X", "flatpak": "a.b", "pasta": "x", "leitor": "nenhum"}]},
     "leitor que o censo sabe"),
    ({"programas": [{"nome": "X", "flatpak": "a.b", "pasta": "x"}]}, "programas"),
    ({"reposicao": {"nome": "X", "processos": []}}, "processos"),
    ({"reposicao": {"nome": "X", "processos": ["x"], "mata": True}}, "reposicao"),
])
def test_o_manifesto_de_fabrica_torto_levanta_com_o_caminho(
        tmp_path: Path, bloco: dict[str, object], frase: str) -> None:
    raiz = _fabrica_com(tmp_path, **bloco)
    with pytest.raises(ValueError, match=frase) as erro:
        censo.lancadores_de_fabrica(raiz)
    assert str(raiz / "x" / "hefesto-mod.json") in str(erro.value)


def test_o_id_tem_de_ser_o_nome_da_pasta(tmp_path: Path) -> None:
    raiz = _fabrica_com(tmp_path)
    (raiz / "x").rename(raiz / "outro")
    with pytest.raises(ValueError, match="nome da pasta"):
        censo.lancadores_de_fabrica(raiz)


def test_raiz_que_nao_existe_nao_tem_lancador(tmp_path: Path) -> None:
    assert censo.lancadores_de_fabrica(tmp_path / "nao-existe") == ()


# --- a mordida: sem o manifesto, o lançador some de tudo ---------------------------------------

_PROVA = """
import json
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as c
from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as r
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d
print(json.dumps({
    "onde": sorted(c._ONDE), "cartoes": sorted(c._DO_CARTAO), "leitores": list(c._LEITORES),
    "reposicao": [x.chave for x in r.LANCADORES],
    "embutidos": [x.chave for x in d.EMBUTIDOS], "sem_fonte": [x.chave for x in d.SEM_FONTE],
    "sabe_ler": [n for n in ("Heroic", "Lutris") if c.sabe_ler(n)],
}))
"""


def _ver_com(raiz: Path, tmp_path: Path) -> dict[str, list[str]]:
    ambiente = {**os.environ, "HEFESTO_LANCADORES_DE_FABRICA": str(raiz)}
    saida = subprocess.run(
        [sys.executable, "-c", _PROVA], capture_output=True, text=True, timeout=60,
        env=ambiente, cwd=tmp_path, check=False)
    assert saida.returncode == 0, saida.stderr
    visto: dict[str, list[str]] = json.loads(saida.stdout)
    return visto


def test_com_os_seis_manifestos_o_processo_de_prova_ve_os_seis(tmp_path: Path) -> None:
    copia = tmp_path / "fabrica"
    shutil.copytree(censo.PASTA_DE_FABRICA, copia)
    visto = _ver_com(copia, tmp_path)
    assert visto["embutidos"] == _SEIS
    assert visto["reposicao"] == ["steam", "heroic", "lutris"]
    assert visto["sabe_ler"] == ["Heroic", "Lutris"]


def test_tirar_o_manifesto_do_heroic_o_tira_do_censo_da_reposicao_e_do_desenho(
        tmp_path: Path) -> None:
    copia = tmp_path / "fabrica"
    shutil.copytree(censo.PASTA_DE_FABRICA, copia)
    shutil.rmtree(copia / "heroic")
    visto = _ver_com(copia, tmp_path)
    assert "Heroic" not in visto["onde"] and "Heroic" not in visto["leitores"]
    assert "heroic" not in visto["cartoes"]
    assert "heroic" not in visto["reposicao"] and visto["reposicao"] == ["steam", "lutris"]
    assert "heroic" not in visto["embutidos"] and "heroic" not in visto["sem_fonte"]
    assert visto["sabe_ler"] == ["Lutris"]
    assert [c for c in visto["embutidos"] if c != "heroic"] == visto["embutidos"]


def test_tirar_o_manifesto_dos_emuladores_tira_os_dois_programas(tmp_path: Path) -> None:
    copia = tmp_path / "fabrica"
    shutil.copytree(censo.PASTA_DE_FABRICA, copia)
    shutil.rmtree(copia / "emuladores")
    visto = _ver_com(copia, tmp_path)
    assert "Dolphin" not in visto["onde"] and "mGBA" not in visto["onde"]
    assert "emuladores" not in visto["embutidos"]
