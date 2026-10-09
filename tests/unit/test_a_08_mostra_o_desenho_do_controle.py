"""A-08-MOSTRA-O-DESENHO-DO-CONTROLE-E-O-HUB-PERGUNTA-A-ENTRADA-01, item 1: o desenho no quadrado.

Ela, 08/10/2026: *«temos os svgs deles no repo já (…) colocamos eles nos quadrados de cada controle.»*
A linha do controle de fora ganha o desenho do modelo (o do repositório, ou o Xbox, que é desenho
nosso) e o nome do modelo vai para a dica do quadrado, não para o corpo da linha.

O que se mede, com cabo e com rádio e com quatro externos na mesma lista:

* cada marca que tem desenho (Nintendo, Xbox, 8BitDo) leva UM quadrado `<svg><use>` apontando para
  um símbolo que EXISTE no sprite da página, e o nome do modelo mora só no `title` do quadrado;
* a marca sem desenho não ganha quadrado (a tela não afirma um modelo que ninguém desenhou);
* o Xbox é desenho nosso: o arquivo existe, é só traçado e não referencia nada de fora.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from pacotes import Contexto
from pacotes import a08_conexoes as conexoes

from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

# Faixas forjadas (`aa:bb:cc`), nunca endereço real mascarado.
PRO = {"name": "Pro Controller", "vid": "057e", "pid": "2009", "driver": "hid-nintendo"}
XBOX = {"name": "Xbox 360 Controller", "vid": "045e", "pid": "028e", "driver": "xpad"}
SN30 = {"name": "8BitDo SN30 Pro", "vid": "2dc8", "pid": "6003", "driver": "hid-generic"}
HORI = {"name": "Controle da HORI", "vid": "0f0d", "pid": "0092", "driver": "hid-generic"}

MODELO = {"057e:2009": "Pro Controller (modo Switch)", "045e:028e": "Xbox 360"}
SIMBOLO = {"057e:2009": "ext-nintendo", "045e:028e": "ext-xbox", "2dc8:6003": "ext-8bitdo"}


@pytest.fixture(autouse=True)
def _sem_o_maquina_json_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import mesa_viva

    monkeypatch.setattr(mesa_viva, "_declaracao_do_disco",
                        lambda: MaquinaConfig.model_validate({}))


def _externo(base: dict[str, Any], bus: str, ordem: int) -> dict[str, Any]:
    return {**base, "bus": bus, "uniq": f"aa:bb:cc:00:00:{ordem:02x}",
            "player_slot": ordem + 2}


def _linhas(*externos: dict[str, Any]) -> list[str]:
    ctx = Contexto(state={"connected": True}, mesa=[], conectados=[], externos=list(externos))
    html = conexoes._html_dos_externos(ctx)
    return re.findall(r'<div class="ext-linha".*?</div>', html, re.S)


def _a_pagina() -> str:
    return (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
@pytest.mark.parametrize("base", [PRO, XBOX, SN30], ids=["pro", "xbox", "sn30"])
def test_cada_modelo_tem_o_seu_desenho_no_quadrado_no_cabo_e_no_radio(
        base: dict[str, Any], bus: str) -> None:
    (linha,) = _linhas(_externo(base, bus, 1))
    quadrados = re.findall(r'<span class="ext-desenho"[^>]*>(.*?)</span>', linha, re.S)
    assert len(quadrados) == 1, linha
    simbolo = SIMBOLO[f"{base['vid']}:{base['pid']}"]
    assert f'<svg aria-hidden="true"><use href="#{simbolo}"/></svg>' in quadrados[0]
    # o quadrado é o PRIMEIRO filho da linha: o desenho abre a linha, o nome vem depois
    assert re.match(r'<div class="ext-linha"[^>]*><span class="ext-desenho"', linha), linha


def test_o_simbolo_de_cada_quadrado_existe_no_sprite_da_pagina() -> None:
    pagina = _a_pagina()
    assert pagina.count('<svg class="ext-sprite"') == 1
    for marca, simbolo in conexoes.SIMBOLO_DO_EXTERNO.items():
        achados = re.findall(rf'<symbol id="{simbolo}" viewBox="[^"]+">(.+?)</symbol>', pagina, re.S)
        assert len(achados) == 1, f"{marca}: o símbolo {simbolo} não está no sprite da página"
        assert "<path" in achados[0] or "<circle" in achados[0], marca
        assert "currentColor" in achados[0], f"{marca}: o desenho não segue a cor do texto"
    assert set(conexoes.SIMBOLO_DO_EXTERNO.values()) == set(SIMBOLO.values())


@pytest.mark.parametrize("vp", ["057e:2009", "045e:028e"])
def test_o_nome_do_modelo_mora_na_dica_do_quadrado_e_nao_no_corpo_da_linha(vp: str) -> None:
    base = PRO if vp == "057e:2009" else XBOX
    (linha,) = _linhas(_externo(base, "usb", 1))
    assert f'title="{MODELO[vp]}"' in linha and f'aria-label="{MODELO[vp]}"' in linha
    sem_atributos = re.sub(r"<[^>]+>", "|", linha)
    assert MODELO[vp] not in sem_atributos, "o modelo voltou a ser texto da linha"


def test_marca_sem_desenho_nao_ganha_quadrado_e_quatro_externos_cabem_em_quatro_linhas() -> None:
    linhas = _linhas(_externo(PRO, "bluetooth", 1), _externo(XBOX, "usb", 2),
                     _externo(SN30, "bluetooth", 3), _externo(HORI, "usb", 4))
    assert len(linhas) == 4
    com = ["ext-desenho" in x for x in linhas]
    assert com == [True, True, True, False], com


def test_o_xbox_e_desenho_nosso_sem_nada_de_fora() -> None:
    arquivo = RAIZ / "assets" / "control-svg" / "xbox.svg"
    texto = arquivo.read_text(encoding="utf-8")
    assert texto.lstrip().startswith("<svg") and "viewBox=" in texto
    for fora in ("<image", "http://", "https://", "<metadata", "xlink:href", "<script"):
        if fora == "http://":
            assert texto.count("http://") == texto.count("http://www.w3.org/2000/svg"), texto
        else:
            assert fora not in texto, f"o desenho nosso referencia `{fora}`"
