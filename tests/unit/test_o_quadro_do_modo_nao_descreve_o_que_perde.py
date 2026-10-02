"""O quadro "Modo" não mora mais na aba Perfis — e as duas frases têm dono."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_o_quadro_do_modo_nao_descreve_o_que_perde: importa código da janela GTK")

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_CUSTO_MASCARA_XBOX,
    texto_do_radio_fragil,
)
from hefesto_dualsense4unix.interface import onde

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

_ESTADO_DO_RADIO_FRAGIL = {
    "controllers": [{"uniq": "aabbcc000001", "connected": True, "transport": "bt"}],
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "native_bt_fragil": True,
    "native_mode": {"enabled": True},
}

_MARCAS_DO_QUADRO = (
    ('<div class="campo modo">', "o bloco da fileira no editor"),
    ('data-modo="', "o atributo que dizia qual dos quatro"),
    ('data-hef="editor.modo"', "o endereço que o produto pintava"),
    (".campo.modo", "a regra de CSS da fileira"),
)


def _pagina(publicado: bool) -> str:
    return onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")


def _frases_proibidas() -> list[tuple[str, str]]:
    """`(nome da constante, texto)` — perguntados ao DONO, nunca digitados."""
    frases = [("home_actions.TEXTO_CUSTO_MASCARA_XBOX", TEXTO_CUSTO_MASCARA_XBOX)]
    do_radio = texto_do_radio_fragil(_ESTADO_DO_RADIO_FRAGIL)
    if do_radio:
        frases.append(("home_actions.texto_do_radio_fragil", do_radio))
    return frases


def test_as_duas_frases_do_dono_existem_de_verdade() -> None:
    """A régua abaixo só morde se as constantes ainda produzem texto."""
    frases = _frases_proibidas()
    assert len(frases) == 2, (
        f"esperava as DUAS frases do dono e vi {[n for n, _ in frases]} — "
        "a varredura de baixo ficaria verde sem varrer nada")
    for nome, texto in frases:
        assert len(texto) > 20, f"{nome} encolheu para {texto!r}"


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
@pytest.mark.parametrize("marca,o_que_e", _MARCAS_DO_QUADRO,
                         ids=[m for m, _ in _MARCAS_DO_QUADRO])
def test_o_quadro_do_modo_nao_esta_na_aba_perfis(
    publicado: bool, marca: str, o_que_e: str
) -> None:
    """Ordem dela, 11/09/2026 — e as duas páginas respondem igual."""
    assert marca not in _pagina(publicado), (
        f"{o_que_e} voltou à aba Perfis ({'publicada' if publicado else 'bancada'}) "
        f"— {marca!r}. O quadro «Modo» saiu do editor por ordem dela em "
        f"11/09/2026: *\"em perfis ainda aparece modo. Isso deve aparecer só na "
        f"aba jogar.\"* Se a decisão mudou, ela muda aqui primeiro."
    )


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
def test_as_duas_frases_do_dono_nao_chegam_a_esta_pagina(publicado: bool) -> None:
    """Decisão 10-Q6 dela, e ela sobrevive à saída do quadro."""
    html = _pagina(publicado)
    for nome, texto in _frases_proibidas():
        assert texto not in html, (
            f"a aba Perfis carrega `{nome}` — a decisão 10-Q6 dela tirou as "
            f"DUAS frases, e o aviso pertence ao canal de recado. A frase "
            f"continua certa onde ela mora; errada é a tela.")
