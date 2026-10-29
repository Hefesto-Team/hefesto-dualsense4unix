"""O-AVISO-DO-MODO-FALA-OS-NOMES-DA-TELA-01 — os avisos do modo na aba Sistema.

Medido em 20/10/2026: com a «Função do teclado» em Desativado e o controle na Navegação, a coluna
de atenção da aba Sistema dizia «Você está em "Controlar o PC" (…) Ligue "Emular teclado" na aba
Navegação.», e o perfil que liga o modo dizia «Quem ligou Conexão Nativa (Sony)» ou «Quem ligou
Jogar pelo Hefesto». Nenhum desses nomes existe numa tela de hoje. A régua mede cada nome entre
aspas angulares contra as páginas publicadas: o nome que o aviso manda procurar tem de estar lá.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest import mock

import pytest


from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel

INTERFACE = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "interface"
PUBLICADAS = INTERFACE / "paginas"  # (noqa-acento)

NOMES_QUE_SAIRAM = ("Controlar o PC", "Jogar pelo Hefesto", "Conexão Nativa", "Emular mouse",
                    "Emular teclado")


def _texto_das_paginas() -> str:
    """O texto visível da Jogar e da Navegação publicadas, sem as marcas."""
    bruto = "".join((PUBLICADAS / nome).read_text(encoding="utf-8")
                    for nome in ("01-jogar.html", "06-navegacao.html"))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", bruto))


def _nomes(frase: str) -> list[str]:
    return re.findall(r"«([^»]+)»", frase)


def _avisos_do_desktop() -> list[str]:
    return [home_actions.TEXTO_DESKTOP_SEM_MOUSE, home_actions.TEXTO_DESKTOP_SEM_TECLADO,
            home_actions.TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO]


def _origem(**state: Any) -> str:
    frase = painel.aviso_da_origem_do_modo(state)
    assert frase, f"o perfil ligou o modo e o aviso calou: {state}"
    return frase


def _avisos_da_origem() -> list[str]:
    return [
        _origem(native_mode=True, native_mode_origin="profile"),
        _origem(mode_from_profile="gamepad", gamepad_emulation={"caminho": "xbox"}),
        _origem(mode_from_profile="gamepad", gamepad_emulation={"caminho": "dualsense"}),
    ]


def _lembrancas_e_ponte() -> list[str]:
    """As três frases do disco e a ponte sem jogo."""
    from hefesto_dualsense4unix.utils import session

    frases: list[str] = []
    for resposta in ((True, "dualsense"), (False, None), (None, None)):
        with mock.patch.object(session, "load_gamepad_preference", lambda r=resposta: r):
            frases.append(painel.modo_lembrado().frase)
    frases.append(home_actions.texto_da_ponte(
        {"gamepad_emulation": {"enabled": False}, "native_mode": False,
         "controllers": [{"connected": True, "uniq": "aa:bb:cc:00:00:01"}]}))
    return frases


@pytest.mark.parametrize("fonte", [_avisos_do_desktop, _avisos_da_origem])
def test_cada_nome_do_aviso_esta_na_tela(fonte: Any) -> None:
    """O nome que o aviso cita existe na Jogar ou na Navegação publicadas."""
    _cada_nome_esta_na_tela(fonte())


def test_a_lembranca_do_disco_e_a_ponte_dizem_os_nomes_da_tela() -> None:
    """A lembrança do disco e a ponte sem jogo dizem «Status», «Ligado» e «Desligado».

    D-2910-OS-MODOS-SE-CHAMAM-PELO-NOME-DA-TELA.
    """
    _cada_nome_esta_na_tela(_lembrancas_e_ponte())


def _cada_nome_esta_na_tela(frases: list[str]) -> None:
    tela = _texto_das_paginas()
    for frase in frases:
        nomes = _nomes(frase)
        assert nomes, f"o aviso não diz o nome de tela nenhum: {frase!r}"
        faltam = [n for n in nomes if n not in tela]
        assert not faltam, f"o aviso cita {faltam} e a tela não tem esse nome: {frase!r}"
        velhos = [n for n in NOMES_QUE_SAIRAM if n in frase]
        assert not velhos, f"o aviso fala o nome da janela que saiu {velhos}: {frase!r}"


def test_o_gamepad_diz_o_caminho_de_pe() -> None:
    """Pelo perfil no Xbox o aviso diz «Xbox»; no DualSense, o chip do DualSense."""
    xbox, dualsense = _avisos_da_origem()[1:]
    assert "«Xbox»" in xbox
    assert "«Sony DualSense»" in dualsense


def test_o_rotulo_de_cada_modo_esta_na_tela() -> None:
    """O nome de cada modo é o do elemento `data-modo` da Jogar publicada.

    D-2910-OS-MODOS-SE-CHAMAM-PELO-NOME-DA-TELA.
    """
    pagina = (PUBLICADAS / "01-jogar.html").read_text(encoding="utf-8")
    for chave, rotulo in home_actions._MODE_ITEMS:
        m = re.search(rf'data-modo="{chave}"[^>]*>(.*?)</(label|span></span)>', pagina, re.S)
        assert m, f"a Jogar publicada não tem o elemento do modo {chave!r}"
        na_tela = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()
        assert na_tela == rotulo, f"o modo {chave!r} diz {rotulo!r} e a tela diz {na_tela!r}"
        assert home_actions._mode_label(chave) == rotulo
