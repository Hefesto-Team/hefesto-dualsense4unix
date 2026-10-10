"""O «Personalizado» desliga a receita do estilo anterior — 09/10/2026.

O perfil guarda a chave do estilo (`Profile.estilo`), e o motor do tato toca a receita
invisível por ela. Escolher «Personalizado» respondia sem gravar: o `estilo: "fps"`
seguia no disco, e o motor seguia tocando o FPS depois que ela disse «eu ajusto na
mão». Agora o gesto grava `estilo = "personalizado"` (sem receita) e deixa as abas e o
desvio `receita_do_tato` como estão.

MORDIDA: volte o `return _dizer(...)` antes da gravação e a receita segue a do FPS.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)

NOME = "Tiro"


class Ponte:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(metodo)
        return True

    def profile_reaplicar(self, nome: str, *a: Any, **kw: Any) -> bool:
        self.chamadas.append(f"profile_reaplicar:{nome}")
        return True


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)


def _no_disco(**extra: Any) -> Profile:
    lado = TriggerConfig(mode="Rigid", params=[5, 200])
    prof = Profile(name=NOME, match=MatchCriteria(window_class=["tiro"]),
                   triggers=TriggersConfig(left=lado, right=lado),
                   rumble=RumbleConfig(policy="max"),
                   leds=LedsConfig(lightbar=(1, 2, 3)),
                   estilo="fps", **extra)
    loader.save_profile(prof, origem="régua")
    return loader.load_profile(NOME)


def _personalizado(ativo: str | None = None) -> tuple[dict[str, Any] | None, Ponte]:
    ponte = Ponte()
    ctx = Contexto(state={"active_profile": ativo}, mesa=[], conectados=[], estados={})
    a10_perfis.selecionar(ctx, {"hefPerfil": NOME}, ponte)
    return a10_perfis.editor_estilo(ctx, {"valor": "Personalizado"}, ponte), ponte


def test_o_personalizado_desliga_a_receita_e_deixa_as_abas() -> None:
    """Relido do disco: a chave é a do Personalizado, e as abas ficam iguais."""
    antes = _no_disco()
    assert tato_vivo.receita_do_perfil(antes) != tato_vivo.DESLIGADA, (
        "o FPS deixou de ter receita: a régua não mede mais nada")

    resposta, _ = _personalizado()

    depois = loader.load_profile(NOME)
    assert depois.estilo == "personalizado"
    for campo in ("triggers", "rumble", "leds", "controllers"):
        assert getattr(depois, campo) == getattr(antes, campo), f"mudou `{campo}`"
    assert tato_vivo.receita_do_perfil(depois) == tato_vivo.DESLIGADA, (
        "o motor do tato segue tocando a receita do FPS")
    assert resposta is not None and "FPS" in resposta["relato"]
    assert "desligada" in resposta["relato"]


def test_o_canal_a_canal_continua_valendo() -> None:
    """O desvio `receita_do_tato` fica: só o campo que ele liga, liga."""
    _no_disco(receita_do_tato={"lado_do_som": True})

    _personalizado()

    receita = tato_vivo.receita_do_perfil(loader.load_profile(NOME))
    esperada = tato_vivo.Receita.de({**asdict(tato_vivo.DESLIGADA), "lado_do_som": True})
    assert receita == esperada, f"o canal a canal virou {receita!r}"


def test_o_perfil_ativo_e_reaplicado() -> None:
    """Grava pelo funil da aba: o perfil que vale chega ao daemon na hora."""
    _no_disco()
    _, ponte = _personalizado(ativo=NOME)
    assert f"profile_reaplicar:{NOME}" in ponte.chamadas, ponte.chamadas


def test_nenhum_texto_diz_que_o_perfil_nao_guarda_o_estilo() -> None:
    """Os textos de `perfis_web` dizem o que o perfil guarda hoje."""
    textos = [perfis_web.DONOS_DOS_GESTOS["editor.estilo"], perfis_web.ESTILO_APLICA_E_SAI]
    for texto in textos:
        assert "NÃO há campo" not in texto and "não é um valor a guardar" not in texto, texto
        assert "não o nome do estilo" not in texto, texto
    assert "Profile.estilo" in perfis_web.DONOS_DOS_GESTOS["editor.estilo"]
