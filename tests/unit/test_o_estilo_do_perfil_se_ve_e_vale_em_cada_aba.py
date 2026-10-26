"""O estilo do perfil se vê e vale em cada aba, de P1 a P4.

O-ESTILO-DO-PERFIL-SE-VE-E-VALE-EM-CADA-ABA-01 (26/10/2026).
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.led_control import LedSettings, cor_automatica
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04
from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10
from hefesto_dualsense4unix.profiles import estilos_de_jogo as estilos
from hefesto_dualsense4unix.profiles.manager import ProfileManager, _controllers_to_specs
from hefesto_dualsense4unix.profiles.schema import (
    MODO_AUTOMATICO,
    MODO_PERSONALIZADO,
    MatchCriteria,
    Profile,
    perfil_no_modo,
)
from tests.unit.test_a_luz_do_controle_nunca_sai_preta import (  # noqa: F401
    BRANCO_ID,
    _esperar_o_plastico,
    registro,
)

QUATRO = (BRANCO_ID, "aabbcc0000d2", "aabbcc0000d3", "aabbcc0000d4")
PINTAM = tuple(e for e in estilos.DE_FABRICA if e.chave not in estilos.SEM_COR)
MODOS_DA_LUZ = (None, MODO_AUTOMATICO)


def _mesa(registro: Any, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, dict[str, int]]:  # noqa: F811
    from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod

    monkeypatch.setattr(id_mod, "get_identity_registry", lambda: registro)
    provider = id_mod.make_auto_output_provider(registro)
    registro.sync_connected(list(QUATRO))
    registro.liberar_as_lampadas()
    _esperar_o_plastico(registro, *QUATRO)
    numeros = {u: provider.numero_do_slot(u) for u in QUATRO}  # type: ignore[attr-defined]
    assert sorted(numeros.values()) == [1, 2, 3, 4], numeros
    return provider, numeros


def _do_jogo() -> Profile:
    return Profile(name="ButtKnight", match=MatchCriteria(window_class=["steam_app_1"]),
                   priority=80)


def _com_o_estilo_so_no_p1(estilo: Any, numeros: dict[str, int]) -> Profile:
    p1 = next(u for u, n in numeros.items() if n == 1)
    prof, pintados = a10._com_o_estilo(_do_jogo(), estilo, [{"uniq": p1, "jogador": 1}])
    assert pintados == 1
    assert isinstance(prof, Profile)
    return prof


def _no_modo(prof: Profile, modo: str | None) -> Profile:
    if modo is None:
        return prof
    return prof.model_copy(update={"leds": prof.leds.model_copy(
        update={"modo": modo, "auto_player_colors": True})})


def _acesa(provider: Any, vista: Profile, uniq: str) -> tuple[int, int, int] | None:
    ProfileManager._configure_auto_player_colors(vista)
    specs = _controllers_to_specs(vista.controllers, vista.leds)
    if uniq in specs and specs[uniq].led is not None:
        return specs[uniq].led
    saida = provider(uniq)
    return None if saida is None else saida.led


def _mostrada(prof: Profile, numeros: dict[str, int], uniq: str) -> tuple[int, int, int]:
    cru = prof.model_dump(mode="json", exclude_unset=True)
    mesa = [{"uniq": u, "jogador": n} for u, n in numeros.items()]
    conectados = [{"uniq": u} for u in numeros]
    ctx = pacotes.Contexto(state={"active_profile": prof.name}, mesa=mesa,
                           conectados=conectados, estados={})
    return a04._a_cor_de_agora(ctx, cru, {"uniq": uniq})


def _no_brilho(cor: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    return LedSettings(lightbar=cor, brightness_level=brilho).apply_brightness(brilho).lightbar


def test_a_luz_de_cada_estilo_acende_e_se_mostra_de_p1_a_p4_nos_dois_modos(
        registro: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    provider, numeros = _mesa(registro, monkeypatch)
    falhas = []
    for estilo in PINTAM:
        prof = _com_o_estilo_so_no_p1(estilo, numeros)
        for modo in MODOS_DA_LUZ:
            dele = _no_modo(prof, modo)
            vista = perfil_no_modo(dele)
            for uniq, n in sorted(numeros.items(), key=lambda kv: kv[1]):
                quer = estilos.cor_da_unidade(estilo, n)
                acesa = _acesa(provider, vista, uniq)
                if acesa != _no_brilho(quer, estilo.brilho):
                    falhas.append(f"{estilo.rotulo} · 04 · {modo or 'sem modo'} · P{n}: "
                                  f"acende {acesa}, a família do estilo é {quer}")
                mostrada = _mostrada(dele, numeros, uniq)
                if mostrada != quer:
                    falhas.append(f"{estilo.rotulo} · 04 na tela · {modo or 'sem modo'} · P{n}: "
                                  f"mostra {mostrada}, a família do estilo é {quer}")
    assert not falhas, "\n".join(falhas)


def test_o_gatilho_e_a_vibracao_de_cada_estilo_valem_de_p1_a_p4(
        registro: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    _, numeros = _mesa(registro, monkeypatch)
    falhas = []
    for estilo in estilos.DE_FABRICA:
        if estilo.chave == "nativo":
            continue
        vista = perfil_no_modo(_com_o_estilo_so_no_p1(estilo, numeros))
        for uniq, n in numeros.items():
            dele = (vista.controllers or {}).get(uniq)
            if dele is not None and dele.triggers is not None:
                falhas.append(f"{estilo.rotulo} · 03 · P{n}: gatilho próprio por cima do estilo")
            if dele is not None and dele.rumble is not None and dele.rumble.policy is not None:
                falhas.append(f"{estilo.rotulo} · 05 · P{n}: degrau próprio por cima do estilo")
        assert estilo.l2 is not None and estilo.r2 is not None, estilo.chave
        lados = (vista.triggers.left.mode, vista.triggers.right.mode)
        pede = (estilo.l2.modo, estilo.r2.modo)
        if lados != pede:
            falhas.append(f"{estilo.rotulo} · 03: {lados}, o estilo pede {pede}")
        if vista.rumble.policy != estilo.vibracao:
            falhas.append(f"{estilo.rotulo} · 05: {vista.rumble.policy}, o estilo pede "
                          f"{estilo.vibracao}")
    assert not falhas, "\n".join(falhas)


def test_a_cor_a_mao_vence_o_estilo_e_o_estilo_preenche_o_resto(
        registro: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    provider, numeros = _mesa(registro, monkeypatch)
    adulto = estilos.POR_CHAVE["adulto"]
    prof = _com_o_estilo_so_no_p1(adulto, numeros)
    p2 = next(u for u, n in numeros.items() if n == 2)
    a_mao = (10, 200, 30)
    prof = a04._com_a_cor_gravada(prof, p2, a_mao, 2)
    vista = perfil_no_modo(prof)
    assert _acesa(provider, vista, p2) == a_mao
    for uniq, n in numeros.items():
        if uniq != p2:
            assert _acesa(provider, vista, uniq) == _no_brilho(
                estilos.cor_da_unidade(adulto, n), adulto.brilho), f"P{n}"


def test_sem_estilo_que_pinta_a_luz_automatica_segue_o_plastico(
        registro: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    provider, numeros = _mesa(registro, monkeypatch)
    for chave in (None, "nativo", "personalizado", "estilo-que-nao-existe"):
        prof = _do_jogo().model_copy(update={"estilo": chave})
        vista = perfil_no_modo(prof)
        for uniq, n in numeros.items():
            assert _acesa(provider, vista, uniq) == cor_automatica(
                n, registro.tom_do_plastico(uniq)), f"{chave} P{n}"


NA_TELA = tuple(f"aa:bb:cc:00:00:e{n}" for n in (1, 2, 3, 4))


def _tique_com_o_perfil(prof: Profile) -> Any:
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(prof)
    vista = perfil_no_modo(prof)
    conectados = [
        {"uniq": u, "player": n, "connected": True, "index": n - 1, "is_primary": n == 1,
         "transport": "usb" if n % 2 else "bt", "battery_pct": 90, "inputs": {}}
        for n, u in enumerate(NA_TELA, start=1)]
    mesa = [{"pref": f"p{n}", "jogador": n, "uniq": u, "nome": "Régua",
             "via": "USB" if n % 2 else "BT", "cor": "starlight-blue",
             "plastico": "#123456", "conectado": True}
            for n, u in enumerate(NA_TELA, start=1)]
    state = {"active_profile": prof.name, "rumble_policy": vista.rumble.policy or "",
             "rumble_mult_applied": 0.7, "controllers": conectados}
    return pacotes.Contexto(state=state, mesa=mesa, conectados=conectados, estados={})


def test_o_gatilho_e_a_vibracao_de_cada_estilo_se_mostram_na_03_e_na_05_de_p1_a_p4() -> None:
    from hefesto_dualsense4unix.app.telas import vibracao as tela_da_vibracao

    escada = tela_da_vibracao._escada()
    falhas = []
    for estilo in estilos.DE_FABRICA:
        if estilo.chave == "nativo":
            continue
        assert estilo.l2 is not None and estilo.r2 is not None, estilo.chave
        prof, _ = a10._com_o_estilo(_do_jogo(), estilo, [{"uniq": NA_TELA[0], "jogador": 1}])
        ctx = _tique_com_o_perfil(prof)
        g = pacotes.pacote_da_pagina("03-gatilhos.html", ctx) or {}
        if g.get("estilo-do-perfil") != estilo.rotulo:
            falhas.append(f"{estilo.rotulo} · 03 na tela: o estilo diz "
                          f"{g.get('estilo-do-perfil')!r}")
        automatico = (estilo.l2.modo, estilo.r2.modo) == ("Off", "Off")
        if g.get("modo-dos-gatilhos") != (MODO_AUTOMATICO if automatico else MODO_PERSONALIZADO):
            falhas.append(f"{estilo.rotulo} · 03 na tela: modo {g.get('modo-dos-gatilhos')!r}")
        v = pacotes.pacote_da_pagina("05-vibracao.html", ctx) or {}
        quer = str(round(escada[estilo.vibracao] * 100))
        for n, uniq in enumerate(NA_TELA, start=1):
            col = (g.get("colunas") or {}).get(uniq) or {}
            for sig, lado in (("e", estilo.l2), ("d", estilo.r2)):
                mudo = col.get(f"modo-{sig}") == "Desligado"
                if not automatico and mudo != (lado.modo == "Off"):
                    falhas.append(f"{estilo.rotulo} · 03 na tela · P{n}: o lado {sig} mostra "
                                  f"{col.get(f'modo-{sig}')!r}, o estilo pede {lado.modo}")
            dela = (v.get("colunas") or {}).get(uniq) or {}
            if dela.get("mult") != quer:
                falhas.append(f"{estilo.rotulo} · 05 na tela · P{n}: força {dela.get('mult')!r}, "
                              f"o degrau {estilo.vibracao} é {quer}")
    assert not falhas, "\n".join(falhas)
