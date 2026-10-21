"""A-ABA-JOGAR-DO-TODO-01 (opção A do BRIEF-T2, 15/10/2026): «Point and click» é do Ligado e
«Navegação» é o terceiro chip do Desligado.

Os dois são o MESMO modo `desktop` do daemon (o controle vira mouse e teclado e o Hefesto segue
lendo; sem gamepad virtual), com tabelas de botões diferentes. Desde 21/10/2026
(O-POINT-AND-CLICK-APLICA-O-PERFIL-QUE-A-NAVEGACAO-ESCOLHE-01) o lado é o ARRANJO que o serviço
guarda e publica no `state_full` (``desktop_arranjo``), e cada chip o leva no plano.

Esta régua mede cinco coisas, cada uma com a sua mordida:

1. os rótulos de cada fileira, nos dois lados, no gerador e na página;
2. o modo de cada chip (`o_que_o_chip_faz`) e o `data-modo` que a página emite;
3. o lado da tela por `_estado_da_tela` com o daemon em `desktop`, nos dois arranjos;
4. as cores do Desligado, que são as da barra de luz (`hotkey.CORES_DO_MODO`), e o alvo de 24 px;
5. a aba sem «?» e sem `title`: toda frase é `data-dica` curta.

A MORDIDA: ponha «Navegação» de volta no Ligado em `aba01.MODOS` (no lugar do Point and click)
e os casos 1 e 2 reprovam; ignore o `desktop_arranjo` em `_estado_da_tela` e o caso 3 reprova.
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

LIGADO = ["Sony DualSense", "Xbox", "Point and click"]
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
    return onde.pagina("01-jogar.html", publicado=False).read_text(encoding="utf-8")


def _fileira(corpo: str, lado: str) -> list[tuple[str, str]]:
    """(rótulo, atributos) dos chips de um lado da fileira, na ordem da página."""
    secao = corpo.split(f'class="hef-modo {lado}"', 1)[-1].split("</div>\n        </div>", 1)[0]
    return [(m.group(2).strip(), m.group(1))
            for m in re.finditer(r'<span class="degrau[^"]*"([^>]*)>([^<]+)</span>', secao)]


# 1. OS RÓTULOS ---------------------------------------------------------------------------------

def test_os_rotulos_do_gerador_sao_os_do_desenho() -> None:
    assert [m["rot"] for m in aba01.MODOS] == LIGADO
    assert [m["rot"] for m in aba01.DO_DESLIGADO] == DESLIGADO


def test_a_pagina_poe_cada_rotulo_no_seu_lado() -> None:
    corpo = _pagina()
    assert [r for r, _ in _fileira(corpo, "so-ligado")] == LIGADO
    assert [r for r, _ in _fileira(corpo, "so-desligado")] == DESLIGADO


def test_a_navegacao_nao_mora_no_ligado_nem_o_point_and_click_no_desligado() -> None:
    corpo = _pagina()
    assert "Navegação" not in [r for r, _ in _fileira(corpo, "so-ligado")]
    assert "Point and click" not in [r for r, _ in _fileira(corpo, "so-desligado")]


# 2. O MODO DE CADA CHIP ------------------------------------------------------------------------

@pytest.mark.parametrize(("chip", "modo", "steam"), [
    ("dualsense", "gamepad", False),
    ("xbox", "gamepad", False),
    (aba.CHIP_DO_POINT_AND_CLICK, "desktop", False),
    (aba.CHIP_DO_NATIVO, "native", False),
    ("steam", "native", True),
    (aba.CHIP_DA_NAVEGACAO, "desktop", False),
])
def test_o_modo_de_cada_chip(chip: str, modo: str, steam: bool) -> None:
    linha = aba.o_que_o_chip_faz(chip)
    assert (linha.modo, linha.steam_input) == (modo, steam)


def test_os_dois_do_desktop_so_diferem_no_arranjo() -> None:
    assert aba.o_que_o_chip_faz(aba.CHIP_DO_POINT_AND_CLICK) == aba.o_que_o_chip_faz(
        aba.CHIP_DA_NAVEGACAO)
    ponto = aba._plano_do_chip(aba.CHIP_DO_POINT_AND_CLICK)
    nav = aba._plano_do_chip(aba.CHIP_DA_NAVEGACAO)
    assert ponto[:-1] == nav[:-1]
    metodo = "desktop.arranjo.apply"
    assert ponto[-1] == (metodo, {"origin": "manual", "arranjo": "point_and_click"})
    assert nav[-1] == ("desktop.arranjo.apply", {"origin": "manual", "arranjo": "navegacao"})


def test_a_pagina_emite_o_gesto_e_o_modo_de_cada_chip() -> None:
    corpo = _pagina()
    ligado = dict(_fileira(corpo, "so-ligado"))
    desligado = dict(_fileira(corpo, "so-desligado"))
    assert 'data-gesto="modo-point-and-click"' in ligado["Point and click"]
    assert 'data-modo="desktop"' in ligado["Point and click"]
    assert 'data-gesto="modo-navegacao"' in desligado["Navegação"]
    assert 'data-modo="desktop"' in desligado["Navegação"]
    assert 'data-gesto="modo-navegacao"' not in "".join(ligado.values())


def test_o_gesto_do_point_and_click_existe_e_tem_prova() -> None:
    assert callable(aba.modo_point_and_click)
    assert any(p["gesto"] == "modo-point-and-click" for p in aba.PROVAS)


# 3. O LADO DA TELA -----------------------------------------------------------------------------

def _tela(state: dict[str, Any]) -> dict[str, str]:
    return aba._estado_da_tela(state)


def test_sem_o_arranjo_o_desktop_acende_o_point_and_click_no_ligado() -> None:
    tela = _tela(VIVO_DESKTOP)
    assert (tela["hef-posicao"], tela["modo-aceso"]) == ("ligado", "pointclick")


def test_no_arranjo_point_and_click_o_desktop_acende_o_point_and_click() -> None:
    tela = _tela({**VIVO_DESKTOP, "desktop_arranjo": "point_and_click"})
    assert (tela["hef-posicao"], tela["modo-aceso"]) == ("ligado", "pointclick")


def test_no_arranjo_da_navegacao_o_desktop_acende_a_navegacao_no_desligado() -> None:
    tela = _tela({**VIVO_DESKTOP, "desktop_arranjo": "navegacao"})
    assert (tela["hef-posicao"], tela["modo-aceso"]) == ("desligado", "navegacao")
    assert tela["steam-input-aceso"] == ""


def test_o_clique_em_cada_chip_leva_o_arranjo_dele(monkeypatch) -> None:
    planos: list[Any] = []
    monkeypatch.setattr(aba, "_aplicar", lambda p, plano: planos.append(plano) or True)
    monkeypatch.setattr(aba, "_lembrar_do_chip", lambda *a, **k: None)
    ctx = Contexto(state=VIVO_DESKTOP, mesa=[], conectados=[], estados={})
    aba.modo_navegacao(ctx, {}, object())
    aba.modo_point_and_click(ctx, {}, object())
    assert [plano[-1][1].get("arranjo") for plano in planos] == ["navegacao", "point_and_click"]


# 3b. A NAVEGAÇÃO SE ESCOLHE COM O HEFESTO DESLIGADO ---------------------------------------------
# (conferência de 15/10/2026). O chip mora no lado Desligado, e é com o Nativo ligado que ela o
# clica: o despachante guardado (`pacotes.GESTOS`, com a recusa da camada) e a folha do Nativo
# (`monta.CSS_DO_NATIVO`) recusavam o clique com «Em modo nativo o jogo lê este controle direto».
# MORDIDA: tire `("01-jogar.html", "modo-navegacao")` de `camada.VIVOS_NO_NATIVO` e o caso reprova.

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


# 4. AS CORES E O ALVO --------------------------------------------------------------------------

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


# 5. SEM «?» E SEM title ------------------------------------------------------------------------

def _miolo_da_pagina() -> str:
    """O miolo da aba, sem comentário e sem SVG: a fita e o rodapé são do esqueleto."""
    corpo = _pagina().split('<div class="miolo">', 1)[-1].split('<div class="rodape"', 1)[0]
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
