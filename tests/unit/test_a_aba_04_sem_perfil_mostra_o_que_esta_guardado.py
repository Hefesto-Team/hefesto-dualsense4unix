"""Sem perfil ativo, a aba Iluminação mostra o modo e o brilho que ficaram guardados.

Medido em 15/10/2026: `perfil.ativo_que_vale` devolvia `{}` sem perfil, e a aba 04 lia o vazio:
o brilho virava travessão e o modo voltava a Personalizado, mesmo com o computador guardando
outro. O que fica guardado sem perfil mora no padrão do computador (`maquina.json`), onde o gesto
grava quando não há perfil; quem PINTA tem de ler de lá, pela mesma vista que o daemon aplica.

O lar é de mentira (o `conftest` desvia `HOME` e os `XDG_*`).

MORDIDAS (15/10/2026): `ativo_que_vale` devolvendo o vazio sem perfil reprova quatro; a guarda dos
gestos lendo `{}` sem perfil (`_nao_no_automatico`) reprova a recusa no Automático guardado; tirar
de `modo_da_luz_do_perfil` a regra da vista sem `name` reprova o efeito que virava a aba.
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


#: Dois controles, um no cabo e outro no rádio: a vista sem perfil vale para as duas conexões.
DOIS = (("aa:bb:cc:00:00:01", "usb", "White", 40), ("aa:bb:cc:00:00:02", "bt", "Cosmic Red", 70))


def _ctx_dos_dois():
    from pacotes import Contexto

    corpos, mesa = [], []
    for n, (uniq, via, plastico, _pct) in enumerate(DOIS, start=1):
        corpos.append({"uniq": uniq, "index": n - 1, "transport": via, "connected": True,
                       "player": n, "player_slot": n, "is_primary": n == 1,
                       "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
                       "lightbar_source": "sysfs" if via == "usb" else "hidraw"})
        mesa.append({"pref": f"p{n}", "uniq": uniq, "jogador": n,
                     "cor": plastico.lower().replace(" ", "-"), "nome": plastico,
                     "via": via.upper(), "transporte": via})
    return Contexto(state={"active_profile": None}, mesa=mesa, conectados=corpos, estados={})


def test_a_aba_pinta_o_brilho_de_cada_controle_sem_perfil_no_cabo_e_no_radio(a04):
    """A tela inteira: cada coluna mostra o brilho que o computador guardou PARA ELA."""
    for uniq, _via, _plastico, pct in DOIS:
        _guardar_sem_perfil(lambda prof, u=uniq, v=pct: a04._com_o_brilho_gravado(prof, u, v),
                            uniq=uniq)
    colunas = a04.pacote(_ctx_dos_dois())["colunas"]
    for uniq, via, _plastico, pct in DOIS:
        assert colunas[uniq]["brilho"] == f"{pct}%", (via, colunas[uniq]["brilho"])


def test_a_aba_pinta_o_automatico_guardado_sem_perfil_e_a_guarda_recusa(a04):
    """O modo que a tela pinta é o que a guarda dos gestos lê: as duas leem o computador."""

    def _automatico(prof):
        leds = prof.leds.model_copy(update={
            "modo": a04.MODO_AUTOMATICO, "auto_player_colors": True})
        return prof.model_copy(update={"leds": leds})

    _guardar_sem_perfil(_automatico, uniq=None)
    ctx = _ctx_dos_dois()
    pac = a04.pacote(ctx)
    assert pac[a04.GESTO_DO_MODO] == a04.MODO_AUTOMATICO
    assert pac[f"{a04.GESTO_DO_MODO}-{a04.MODO_AUTOMATICO}"] == "sim"
    for uniq, via, _plastico, _pct in DOIS:
        with pytest.raises(RuntimeError, match="modo automático"):
            a04.efeito_da_luz(ctx, {"uniq": uniq, "valor": "base:respirar"}, None)
        with pytest.raises(RuntimeError, match="modo automático"):
            a04.cor(ctx, {"uniq": uniq, "hex": "FF8000"}, None), via


def test_sem_perfil_o_efeito_e_o_brilho_nao_viram_a_aba_para_o_automatico(a04):
    """«Não há perfil» não é um modo: o computador sem `leds.modo` não deduz Automático.

    Medido no lar de mentira (15/10/2026): escolher Respirar sem perfil acendia «Modo automático» e
    apagava a grade, porque a vista do computador caía na dedução do esquema (cores automáticas
    ligadas por padrão, nenhuma cor própria).
    """
    ctx = _ctx_dos_dois()
    assert a04.pacote(ctx)[a04.GESTO_DO_MODO] == a04.MODO_PERSONALIZADO
    for uniq, via, _plastico, pct in DOIS:
        _guardar_sem_perfil(lambda prof, u=uniq, v=pct: a04._com_o_brilho_gravado(prof, u, v),
                            uniq=uniq)
        a04.efeito_da_luz(_ctx_dos_dois(), {"uniq": uniq, "valor": "base:respirar"}, None)
        pac = a04.pacote(_ctx_dos_dois())
        assert pac[a04.GESTO_DO_MODO] == a04.MODO_PERSONALIZADO, via
        assert pac["colunas"][uniq][a04.CAMPO_DO_EFEITO] == "base:respirar", via


def test_um_perfil_ativo_continua_mandando_sobre_o_computador(a04):
    """Com perfil, nada muda: a vista de antes (o computador por baixo do perfil)."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile
    from pacotes import perfil

    save_profile(Profile(name="regua", match=MatchAny(),
                         leds=LedsConfig(lightbar=(40, 80, 180))), origem="regua")
    assert perfil.ativo_que_vale("regua").get("name") == "regua"
