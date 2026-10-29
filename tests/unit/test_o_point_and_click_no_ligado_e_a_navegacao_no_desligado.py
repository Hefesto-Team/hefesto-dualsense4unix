"""A fileira da Jogar: três chips no Ligado, três no Desligado, e o Point and click fora dela.

A-ABA-JOGAR-DO-TODO-01 (15/10/2026) pôs o «Point and click» no Ligado e a «Navegação» no
Desligado, os dois no MESMO modo `desktop` do daemon com tabelas de botões diferentes. Desde
O-POINT-AND-CLICK-E-ESTILO-DE-JOGO-E-NAO-MODO-01 o Point and click é estilo de jogo, e o desenho
de 27/10/2026 (publicado em 28/10) põe o «Nintendo Pro» no terceiro lugar do Ligado. O `desktop`
vivo, em qualquer arranjo, acende a «Navegação» no Desligado (decisão de 28/10/2026, a
validar pelo usuário): o arranjo é do estilo de jogo, e o chip diz o modo.

Esta régua mede cinco coisas, cada uma com a sua mordida:

1. os rótulos de cada fileira, nos dois lados, no gerador e na página;
2. o modo de cada chip (`o_que_o_chip_faz`) e o `data-modo` que a página emite;
3. o lado da tela por `_estado_da_tela` com o daemon em `desktop`, nos dois arranjos;
4. as cores do Desligado, que são as da barra de luz (`hotkey.CORES_DO_MODO`), e o alvo de 24 px;
5. o quadro Status sem «?» e sem `title`: toda frase é `data-dica` curta.

A MORDIDA: devolva o ramo que acendia o Point and click no `desktop` sem o arranjo da
Navegação em `_estado_da_tela` e o caso 3 reprova; ponha o Point and click de volta em
`aba01.MODOS` e o caso 1 reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.interface import aba01, onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

LIGADO = ["Sony DualSense", "Xbox", "Nintendo Pro"]
DESLIGADO = ["Nativo", "Steam Input", "Navegação"]

VIVO_DESKTOP: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense",
                          "wrapper_used": None, "mascara_divergente": None},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True, "player_slot": 1}],
}


@pytest.fixture()
def lar_novo(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    """Um `config_dir()` só deste teste."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def _pagina() -> str:
    return onde.pagina("01-jogar.html", publicado=True).read_text(encoding="utf-8")


def _fileira(corpo: str, lado: str) -> list[tuple[str, str]]:
    """(rótulo, atributos) dos chips de um lado da fileira, na ordem da página."""
    secao = corpo.split(f'class="hef-modo {lado}"', 1)[-1].split("</div>\n        </div>", 1)[0]
    secao = re.sub(r"<svg.*?</svg>", "", secao, flags=re.S)
    return [(m.group(2).strip(), m.group(1))
            for m in re.finditer(rf'<span class="degrau[^"]*"([^>]*)>'
                                 rf'<span class="{aba01.ROTULO_DO_MODO}">([^<]+)</span></span>',
                                 secao)]


def test_os_rotulos_do_gerador_sao_os_do_desenho() -> None:
    assert [m["rot"] for m in aba01.MODOS] == LIGADO
    assert [m["rot"] for m in aba01.DO_DESLIGADO] == DESLIGADO


def test_a_pagina_poe_cada_rotulo_no_seu_lado() -> None:
    corpo = _pagina()
    assert [r for r, _ in _fileira(corpo, "so-ligado")] == LIGADO
    assert [r for r, _ in _fileira(corpo, "so-desligado")] == DESLIGADO


def test_a_navegacao_nao_mora_no_ligado_e_o_point_and_click_nao_e_chip() -> None:
    corpo = _pagina()
    assert "Navegação" not in [r for r, _ in _fileira(corpo, "so-ligado")]
    chips = [r for lado in ("so-ligado", "so-desligado") for r, _ in _fileira(corpo, lado)]
    assert "Point and click" not in chips


@pytest.mark.parametrize(("chip", "modo", "steam"), [
    ("dualsense", "gamepad", False),
    ("xbox", "gamepad", False),
    ("nintendo", "gamepad", False),
    (aba.CHIP_DO_NATIVO, "native", False),
    ("steam", "native", True),
    (aba.CHIP_DA_NAVEGACAO, "desktop", False),
])
def test_o_modo_de_cada_chip(chip: str, modo: str, steam: bool) -> None:
    linha = aba.o_que_o_chip_faz(chip)
    assert (linha.modo, linha.steam_input) == (modo, steam)


def test_a_navegacao_leva_o_arranjo_dela() -> None:
    nav = aba._plano_do_chip(aba.CHIP_DA_NAVEGACAO)
    assert nav[-1] == ("desktop.arranjo.apply", {"origin": "manual", "arranjo": "navegacao"})


def test_a_pagina_emite_o_gesto_e_o_modo_de_cada_chip() -> None:
    corpo = _pagina()
    ligado = dict(_fileira(corpo, "so-ligado"))
    desligado = dict(_fileira(corpo, "so-desligado"))
    assert 'data-gesto="modo-navegacao"' in desligado["Navegação"]
    assert 'data-modo="desktop"' in desligado["Navegação"]
    assert 'data-gesto="modo-navegacao"' not in "".join(ligado.values())
    assert 'data-gesto="modo-point-and-click"' not in corpo


def test_o_gesto_do_point_and_click_saiu_da_jogar() -> None:
    import pacotes

    assert not hasattr(aba, "modo_point_and_click")
    assert ("01-jogar.html", "modo-point-and-click") not in pacotes.GESTOS
    assert not any(p["gesto"] == "modo-point-and-click" for p in aba.PROVAS)


def _tela(state: dict[str, Any]) -> dict[str, str]:
    return aba._estado_da_tela(state)


def test_sem_o_arranjo_o_desktop_acende_a_navegacao_no_desligado() -> None:
    tela = _tela(VIVO_DESKTOP)
    assert (tela["hef-posicao"], tela["modo-aceso"]) == ("desligado", "navegacao")


def test_no_arranjo_point_and_click_o_desktop_acende_a_navegacao_no_desligado() -> None:
    """O estilo de jogo Point and click abre no arranjo dele; a fileira diz o modo."""
    tela = _tela({**VIVO_DESKTOP, "desktop_arranjo": "point_and_click"})
    assert (tela["hef-posicao"], tela["modo-aceso"]) == ("desligado", "navegacao")


def test_no_arranjo_da_navegacao_o_desktop_acende_a_navegacao_no_desligado() -> None:
    tela = _tela({**VIVO_DESKTOP, "desktop_arranjo": "navegacao"})
    assert (tela["hef-posicao"], tela["modo-aceso"]) == ("desligado", "navegacao")
    assert tela["steam-input-aceso"] == ""


def test_o_clique_na_navegacao_leva_o_arranjo_dela(monkeypatch) -> None:
    planos: list[Any] = []
    monkeypatch.setattr(aba, "_aplicar", lambda p, plano: planos.append(plano) or True)
    monkeypatch.setattr(aba, "_lembrar_do_chip", lambda *a, **k: None)
    ctx = Contexto(state=VIVO_DESKTOP, mesa=[], conectados=[], estados={})
    aba.modo_navegacao(ctx, {}, object())
    assert [plano[-1][1].get("arranjo") for plano in planos] == ["navegacao"]


VIVO_NATIVO: dict[str, Any] = {**VIVO_DESKTOP, "native_mode": True}


def test_com_o_hefesto_desligado_o_clique_na_navegacao_chega_ao_daemon(lar_novo,
                                                                       monkeypatch) -> None:
    import pacotes
    from pacotes import camada

    planos: list[Any] = []
    monkeypatch.setattr(aba, "_aplicar", lambda p, plano: planos.append(plano) or True)
    monkeypatch.setattr(aba, "_lembrar_do_chip", lambda *a, **k: None)
    ctx = Contexto(state=VIVO_NATIVO, mesa=[], conectados=[], estados={})
    assert camada.recusa_no_nativo("01-jogar.html", "modo-navegacao", VIVO_NATIVO) is None
    pacotes.GESTOS[("01-jogar.html", "modo-navegacao")](ctx, {}, object())
    assert planos == [aba._plano_do_chip(aba.CHIP_DA_NAVEGACAO)]
    assert planos[0][-1][1]["arranjo"] == "navegacao"


def test_a_folha_do_nativo_deixa_a_navegacao_clicavel() -> None:
    from hefesto_dualsense4unix.interface import monta

    vivos = re.findall(r":not\(:is\(([^)]*)\)", monta.CSS_DO_NATIVO)
    assert vivos and "[data-gesto=modo-navegacao]" in vivos[0]
    assert monta.CSS_DO_NATIVO.strip() in _pagina(), "a página não leva a folha do Nativo de agora"


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


@pytest.mark.parametrize(("chip", "modo"), [
    ("nativo", "nativo"), ("steam", "steam_input"), ("navegacao", "mouse_teclado"),
])
def test_a_cor_do_chip_do_desligado_e_a_da_barra(chip: str, modo: str) -> None:
    cor = _hex(hotkey.CORES_DO_MODO[modo])
    regra = re.search(
        rf'\.so-desligado \.degrau\.on\[data-hef-quando="{chip}"\]\{{\s*'
        r"border-color:(#[0-9a-f]{6})",
        aba01.CSS)
    assert regra, f"o chip {chip!r} perdeu a cor própria no Desligado"
    assert regra.group(1) == cor, f"{chip}: a tela pinta {regra.group(1)} e a barra {cor}"


def test_todo_alvo_clicavel_tem_24_px() -> None:
    assert "[data-gesto]{min-height:24px}" in aba01.CSS.replace(" ", "")


def _miolo_da_pagina() -> str:
    """O quadro Status, sem comentário e sem SVG.

    A seção Controles (`<div class="quadro estica">`) veio da aba 02 com os `title` dela, e a
    régua dela é a da seção; esta mede o que é só da Jogar.
    """
    corpo = _pagina().split('<div class="miolo">', 1)[-1].split('<div class="quadro estica">', 1)[0]
    corpo = re.sub(r"<svg.*?</svg>", "", corpo, flags=re.S)
    return re.sub(r"<!--.*?-->", "", corpo, flags=re.S)


def test_a_aba_nao_tem_ajuda_com_interrogacao_nem_title() -> None:
    corpo = _miolo_da_pagina()
    assert 'class="ajuda"' not in corpo
    assert ' title="' not in corpo


def test_cada_chip_do_desligado_tem_uma_dica_curta() -> None:
    for rotulo, atributos in _fileira(_pagina(), "so-desligado"):
        dica = re.search(r'data-dica="([^"]+)"', atributos)
        assert dica, f"o chip {rotulo!r} ficou sem dica"
        assert len(dica.group(1).split()) <= 12, dica.group(1)


def test_o_reconectar_mora_no_canto_do_quadro_das_mascaras() -> None:
    corpo = _miolo_da_pagina()
    assert corpo.count('data-gesto="reconectar"') == 1
    antes = corpo.split('data-gesto="reconectar"', 1)[0]
    assert antes.rfind('class="quadro-topo"') > antes.rfind('class="faixa-final"')
    assert "Reconectar controles" not in corpo
