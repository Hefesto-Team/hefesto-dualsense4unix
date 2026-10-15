"""Sem perfil ativo, a aba Iluminação mostra o modo e o brilho que ficaram guardados.

Medido em 15/10/2026: `perfil.ativo_que_vale` devolvia `{}` sem perfil, e a aba 04 lia o vazio:
o brilho virava travessão e o modo voltava a Personalizado, mesmo com o computador guardando
outro. O que fica guardado sem perfil mora no padrão do computador (`maquina.json`), onde o gesto
grava quando não há perfil; quem PINTA tem de ler de lá, pela mesma vista que o daemon aplica.

O lar é de mentira (o `conftest` desvia `HOME` e os `XDG_*`).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIQ = "aa:bb:cc:00:00:01"


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


def _guardar_sem_perfil(muda, uniq=UNIQ) -> None:
    """Grava como o gesto grava sem perfil: o brilho vai por controle, o modo é global."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    gravar_pelo_gesto("luz", "", muda, uniq=uniq)


def test_sem_nada_guardado_a_vista_segue_vazia(a04):
    """Sem perfil e sem computador declarado, `{}`: o travessão é o estado, não um erro."""
    from pacotes import perfil

    assert perfil.ativo_que_vale(None) == {}
    assert perfil.ativo_que_vale("") == {}


def test_sem_perfil_o_brilho_guardado_aparece(a04):
    from pacotes import perfil

    _guardar_sem_perfil(lambda prof: a04._com_o_brilho_gravado(prof, UNIQ, 40))
    vista = perfil.ativo_que_vale(None)
    assert vista, "o brilho guardado no computador não chegou à leitura da aba"
    assert a04.brilho_do_controle(vista, UNIQ) == pytest.approx(0.4)


def test_sem_perfil_o_modo_guardado_aparece(a04):
    from pacotes import perfil

    def _automatico(prof):
        leds = prof.leds.model_copy(update={
            "modo": a04.MODO_AUTOMATICO, "auto_player_colors": True})
        return prof.model_copy(update={"leds": leds})

    _guardar_sem_perfil(_automatico, uniq=None)
    assert a04.modo_da_luz_do_perfil(perfil.ativo_que_vale(None)) == a04.MODO_AUTOMATICO


def test_a_aba_pinta_o_brilho_guardado_sem_perfil(a04):
    """A tela inteira: a coluna do controle mostra os 40% que o computador guardou."""
    from pacotes import Contexto

    _guardar_sem_perfil(lambda prof: a04._com_o_brilho_gravado(prof, UNIQ, 40))
    corpo = {"uniq": UNIQ, "index": 0, "transport": "usb", "connected": True, "player": 1,
             "player_slot": 1, "is_primary": True, "lightbar_rgb": [0, 0, 255],
             "lightbar_on": True, "lightbar_source": "sysfs"}
    mesa = [{"pref": "p1", "uniq": UNIQ, "jogador": 1, "cor": "white", "nome": "White",
             "via": "USB", "transporte": "usb"}]
    ctx = Contexto(state={"active_profile": None}, mesa=mesa, conectados=[corpo], estados={})
    achados = repr(a04.pacote(ctx))
    assert "40%" in achados, "a aba sem perfil não mostrou o brilho guardado"


def test_um_perfil_ativo_continua_mandando_sobre_o_computador(a04):
    """Com perfil, nada muda: a vista de antes (o computador por baixo do perfil)."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile
    from pacotes import perfil

    save_profile(Profile(name="regua", match=MatchAny(),
                         leds=LedsConfig(lightbar=(40, 80, 180))), origem="regua")
    assert perfil.ativo_que_vale("regua").get("name") == "regua"
