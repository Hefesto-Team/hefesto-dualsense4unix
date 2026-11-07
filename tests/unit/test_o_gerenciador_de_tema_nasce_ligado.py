"""A extensão de fábrica com ``ligar: true`` nasce ligada, mesmo quando substitui uma desligada.

A sprint é a O-GERENCIADOR-DE-TEMA-NASCE-LIGADO-E-VESTE-OS-BOTOES-DA-JANELA-01. Medido em
01/11/2026: o gerenciador de tema substitui o tema claro, que fica desligado no tema Escuro, e a
regra do substituto desligado o deixava desligado justamente no tema normal. A regra agora só olha
o registro DESTA extensão: a que quem usa desligou fica desligada; a que nasceu desligada pela
regra velha se liga uma vez, no install seguinte.

MORDIDAS (01/11/2026, executadas sobre a cura e devolvidas):

- a regra velha (``desligadas`` do substituto) devolvida ao ``_trazer_uma`` reprova
  ``test_a_que_substitui_uma_desligada_nasce_ligada``;
- a revisão da que nasceu desligada arrancada reprova
  ``test_a_que_nasceu_desligada_pela_regra_velha_se_liga_uma_vez``;
- a revisão sem a anotação das revistas reprova
  ``test_a_que_nasceu_desligada_pela_regra_velha_se_liga_uma_vez`` (a atualização zera o
  ``ligada_em``, e a desligada depois da atualização voltaria ligada);
- a revisão sem conferir o ``ligada_em`` reprova
  ``test_a_que_quem_usa_desligou_antes_da_cura_fica_desligada``;
- o ``Gtk.Image`` do tema de ícones devolvido ao ``montar_a_barra`` reprova
  ``test_o_glifo_nao_depende_do_tema_de_icones`` (o quadrado de traço sai cheio);
- o ``css_da_cor_da_barra`` vazio sem tema reprova ``test_os_botoes_vestem_a_casa_sem_tema``;
- a regra ``:backdrop`` arrancada reprova ``test_fora_de_foco_os_botoes_vestem_o_texto_mudo``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import de_fabrica_por_endereco as fabrica
from hefesto_dualsense4unix.mods import tema
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import Lugares, gravar_registro, ler_registro
from tests.unit.test_a_extensao_de_fabrica_por_endereco_chega_pelo_install import (
    ANTIGA,
    NOVA,
    _lista,
    _repo,
    lg,
)

__all__ = ["lg"]


def _a_substituta(tmp_path: Path, **item: object) -> Path:
    endereco = _repo(tmp_path, NOVA, substitui=[ANTIGA])
    return _lista(tmp_path, {"id": NOVA, "endereco": endereco, **item})


def _como_a_regra_velha_deixou(lg: Lugares, tmp_path: Path, *, ligada_em: str = "") -> Path:
    """O registro de quem fez o install antes da cura: instalada, desligada, já anotada."""
    endereco = _repo(tmp_path, NOVA)
    lista = _lista(tmp_path, {"id": NOVA, "endereco": endereco})
    instalador.instalar(endereco, lugares=lg)
    registro = ler_registro(lg.registro)
    registro[NOVA].ligada_em = ligada_em
    gravar_registro(lg.registro, registro)
    lg.registro.with_name(fabrica.TRAZIDAS).write_text(json.dumps({"trazidas": [NOVA]}))
    return lista


def test_a_que_substitui_uma_desligada_nasce_ligada(lg: Lugares, tmp_path: Path) -> None:
    instalador.instalar(_repo(tmp_path, ANTIGA), lugares=lg)
    feitos = fabrica.trazer(lugares=lg, arquivo=_a_substituta(tmp_path))
    registro = ler_registro(lg.registro)
    assert ANTIGA not in registro and registro[NOVA].ligada
    assert [f.o_que for f in feitos] == ["ligada"]


def test_a_que_a_lista_nao_manda_ligar_fica_desligada(lg: Lugares, tmp_path: Path) -> None:
    instalador.instalar(_repo(tmp_path, ANTIGA), lugares=lg)
    feitos = fabrica.trazer(lugares=lg, arquivo=_a_substituta(tmp_path, ligar=False))
    assert [f.o_que for f in feitos] == ["instalada"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_quem_usa_desligou_depois_fica_desligada(lg: Lugares, tmp_path: Path) -> None:
    instalador.instalar(_repo(tmp_path, ANTIGA), lugares=lg)
    lista = _a_substituta(tmp_path)
    fabrica.trazer(lugares=lg, arquivo=lista)
    instalador.desligar(NOVA, lugares=lg)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_nasceu_desligada_pela_regra_velha_se_liga_uma_vez(
        lg: Lugares, tmp_path: Path) -> None:
    lista = _como_a_regra_velha_deixou(lg, tmp_path)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ligada"]
    assert ler_registro(lg.registro)[NOVA].ligada
    instalador.atualizar(NOVA, lugares=lg)
    assert ler_registro(lg.registro)[NOVA].ligada_em == ""
    instalador.desligar(NOVA, lugares=lg)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_quem_usa_desligou_antes_da_cura_fica_desligada(
        lg: Lugares, tmp_path: Path) -> None:
    lista = _como_a_regra_velha_deixou(lg, tmp_path, ligada_em="2026-10-31T10:00:00+00:00")
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_quem_usa_instalou_sem_a_lista_fica_como_esta(lg: Lugares, tmp_path: Path) -> None:
    endereco = _repo(tmp_path, NOVA)
    lista = _lista(tmp_path, {"id": NOVA, "endereco": endereco})
    instalador.instalar(endereco, lugares=lg)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_lista_do_pacote_manda_ligar_cada_extensao() -> None:
    assert all(item.ligar for item in fabrica.ler())


_SONDA_DOS_BOTOES = r"""
import json, sys
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface import janela

folha, icones = sys.argv[1], sys.argv[2]
Gtk.Settings.get_default().set_property("gtk-icon-theme-name", icones)

def girar():
    GLib.timeout_add(400, Gtk.main_quit)
    Gtk.main()

def cor(pix, i, j):
    k = j * pix.get_rowstride() + i * pix.get_n_channels()
    return "#%02x%02x%02x" % tuple(pix.get_pixels()[k:k + 3])

provedor = Gtk.CssProvider()
provedor.load_from_data(janela.css_da_cor_da_barra(folha).encode("utf-8"))
cliques = []
barra, botoes = janela.montar_a_barra("H", "a", lambda _b, g: cliques.append(g), cor=provedor,
                                      lado="direita")
oculta = Gtk.OffscreenWindow()
oculta.add(barra)
oculta.show_all()
saida = {}
for maximizada in (False, True):
    janela.vestir_a_cara_do_maximizar(botoes, maximizada)
    for fora in (False, True):
        if fora:
            barra.set_state_flags(Gtk.StateFlags.BACKDROP, False)
        else:
            barra.unset_state_flags(Gtk.StateFlags.BACKDROP)
        girar()
        pix = oculta.get_pixbuf()
        for gesto, botao in botoes.items():
            x, y = botao.translate_coordinates(oculta, 0, 0)
            caixa = botao.get_allocation()
            fundo = cor(pix, x + 1, y + 1)
            linhas = [[cor(pix, i, j) for i in range(x, x + caixa.width)]
                      for j in range(y, y + caixa.height)]
            saida[f"{maximizada}|{fora}|{gesto}"] = {
                "fundo": fundo,
                "tinta": sorted({c for linha in linhas for c in linha} - {fundo}),
                "mapa": ["".join("." if c == fundo else "#" for c in linha) for linha in linhas],
                "meio": linhas[caixa.height // 2][caixa.width // 2],
            }
for botao in botoes.values():
    botao.clicked()
print(json.dumps({"botoes": saida, "cliques": cliques}))
"""

TRACO = {
    "window-maximize-symbolic": '<rect stroke-width="2.5" width="26" height="26" x="11" y="11" '
                                'fill="none" stroke="currentColor"/>',
    "window-restore-symbolic": '<rect stroke-width="2.5" width="21" height="21" x="9" y="18" '
                               'fill="none" stroke="currentColor"/>',
    "window-minimize-symbolic": '<path stroke-width="2.5" fill="none" stroke="currentColor" '
                                'd="M12 33h24"/>',
    "window-close-symbolic": '<path stroke-width="2.5" fill="none" stroke="currentColor" '
                             'd="M13 13l22 22M35 13L13 35"/>',
}
CLARO = ":root{--app-bg:#eef0f5 !important;--panel:#ffffff !important;--fg:#1c1e29 !important;}"


def _tema_de_icones_de_traco(raiz: Path) -> None:
    pasta = raiz / "icons" / "TemaDeTraco"
    (pasta / "scalable" / "actions").mkdir(parents=True)
    (pasta / "index.theme").write_text(
        "[Icon Theme]\nName=TemaDeTraco\nInherits=hicolor\nDirectories=scalable/actions\n\n"
        "[scalable/actions]\nSize=16\nMinSize=8\nMaxSize=512\nType=Scalable\n",
        encoding="utf-8")
    for nome, corpo in TRACO.items():
        (pasta / "scalable" / "actions" / f"{nome}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
            f'viewBox="0 0 48 48">{corpo}</svg>', encoding="utf-8")


def _sondar(raiz: Path, folha: str, icones: str) -> dict[str, Any]:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a sonda abre os botões da janela no GTK real")
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", XDG_DATA_HOME=str(raiz),
                    XDG_CONFIG_HOME=str(raiz / "config"))
    filho = subprocess.run([sys.executable, "-c", _SONDA_DOS_BOTOES, folha, icones],
                           env=ambiente, capture_output=True, text=True, timeout=120)
    assert filho.returncode == 0, filho.stderr[-800:]
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


@pytest.fixture(scope="module")
def sondas(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], dict[str, Any]]:
    raiz = tmp_path_factory.mktemp("icones")
    _tema_de_icones_de_traco(raiz)
    return {(nome, icones): _sondar(raiz, folha, icones)
            for nome, folha in (("sem", ""), ("claro", CLARO))
            for icones in ("TemaDeTraco", "hicolor")}


def test_o_glifo_nao_depende_do_tema_de_icones(
        sondas: dict[tuple[str, str], dict[str, Any]]) -> None:
    for tema_de_cor in ("sem", "claro"):
        traco = sondas[(tema_de_cor, "TemaDeTraco")]["botoes"]
        outro = sondas[(tema_de_cor, "hicolor")]["botoes"]
        for chave, lido in traco.items():
            assert lido["mapa"] == outro[chave]["mapa"], chave
            assert lido["tinta"], f"{chave}: o botão saiu sem glifo"
        normal = traco["False|False|maximizar"]
        assert normal["meio"] == normal["fundo"], "o maximizar saiu quadrado cheio"
        assert normal["mapa"] != traco["True|False|maximizar"]["mapa"], "restaurar = maximizar"


def test_os_botoes_vestem_a_casa_sem_tema(sondas: dict[tuple[str, str], dict[str, Any]]) -> None:
    casa = tema.tokens_da_casa()
    for chave, lido in sondas[("sem", "TemaDeTraco")]["botoes"].items():
        assert lido["fundo"] == casa["--panel"], chave
        if chave.split("|")[1] == "False":
            assert casa["--fg"] in lido["tinta"], chave


def test_fora_de_foco_os_botoes_vestem_o_texto_mudo(
        sondas: dict[tuple[str, str], dict[str, Any]]) -> None:
    casa = tema.tokens_da_casa()
    for chave, lido in sondas[("sem", "TemaDeTraco")]["botoes"].items():
        if chave.split("|")[1] == "True":
            assert casa["--texto-mudo"] in lido["tinta"] and casa["--fg"] not in lido["tinta"], (
                chave, lido["tinta"])
    claro = sondas[("claro", "TemaDeTraco")]["botoes"]
    assert claro["False|False|fechar"]["fundo"] == "#ffffff"
    assert "#1c1e29" in claro["False|False|fechar"]["tinta"]
    assert "#1c1e29" not in claro["False|True|fechar"]["tinta"]


def test_cada_botao_responde_ao_clique(sondas: dict[tuple[str, str], dict[str, Any]]) -> None:
    for lido in sondas.values():
        assert lido["cliques"] == ["fechar", "maximizar", "minimizar"]
