"""A TRAVA MANUAL SAIU — o perfil aplica tudo, para qualquer jogo."""
from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

MORTOS = ("mark_manual_trigger_active", "clear_manual_trigger_active",
          "manual_override_categories", "manual_trigger_active")

VIVO = "manual_profile_lock_active"


class _ControleQueAnota(FakeController):
    """O `FakeController` da casa, com o `OutputSpec` guardado."""

    def __init__(self, *a: object, **k: object) -> None:
        super().__init__(*a, **k)  # type: ignore[arg-type]
        self.specs: list[object] = []

    def apply_output_defaults(self, spec: object) -> None:
        self.specs.append(spec)


def _perfil_com_gatilho_e_luz() -> Profile:
    """Um perfil de jogo, com as duas seções que a trava silenciava."""
    return Profile(
        name="jogo-de-prova",
        match=MatchCriteria(window_class=["steam_app_1599660"]),
        priority=80,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Rigid", params=[5, 200]),
            right=TriggerConfig(mode="Rigid", params=[5, 200]),
        ),
        leds=LedsConfig(lightbar=(255, 0, 128)),
    )


def _codigo_de_producao() -> list[tuple[pathlib.Path, str]]:
    return [(p, p.read_text(encoding="utf-8")) for p in sorted(SRC.rglob("*.py"))]


def _linhas_de_codigo(texto: str) -> list[tuple[int, str]]:
    """As linhas que são CÓDIGO: fora de comentário e fora de docstring."""
    dentro = False
    fora: list[tuple[int, str]] = []
    for n, linha in enumerate(texto.splitlines(), 1):
        aspas = linha.count('"""') + linha.count("'''")
        if dentro:
            if aspas:
                dentro = False
            continue
        if aspas % 2:
            dentro = True
            continue
        if linha.lstrip().startswith("#"):
            continue
        fora.append((n, linha))
    return fora


@pytest.mark.parametrize("origem", ["launch", "autoswitch", "manual", "boot"])
def test_o_perfil_aplica_gatilho_e_luz_em_toda_origem(origem: str) -> None:
    """A queixa dela era com `origin="launch"`; a decisão é para todas.
    (D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO)
    """
    fc = _ControleQueAnota()
    manager = ProfileManager(controller=fc, store=StateStore())
    relatorio: dict[str, str] = {}

    manager.apply(_perfil_com_gatilho_e_luz(), origin=origem, relatorio=relatorio)

    assert fc.specs, (
        "a ativação não chamou `apply_output_defaults` — o perfil não escreveu nada"
    )
    spec = fc.specs[-1]
    assert spec.trigger_left is not None and spec.trigger_right is not None, (
        f"a seção `triggers` do perfil não chegou ao controle na origem {origem!r}: "
        f"é o `ignorado_trava_manual` de volta, e é a queixa dela de 14/09 — "
        f"*«os gatilhos tambem nao tao aplicando»*"  # (noqa-acento): dela
    )
    assert spec.led is not None, (
        f"a seção `leds` do perfil não chegou ao controle na origem {origem!r}"
    )
    assert "ignorado_trava_manual" not in relatorio.values(), (
        f"o relatório da ativação voltou a dizer `ignorado_trava_manual`: "
        f"{relatorio!r}. Nenhuma seção é silenciada por trava desde 14/09/2026"
    )
    for secao in ("trigger", "led"):
        assert relatorio.get(secao) not in (None, "ignorado_trava_manual"), (
            f"a seção {secao!r} sumiu do relatório da ativação — a ausência de "
            f"notícia lida como 'não entrou' é o ELO-MUDO-01, e ela custou uma sprint"
        )


def test_o_store_nao_sabe_mais_travar() -> None:
    """O dono da trava não a tem, e o irmão de 30 s continua lá."""
    store = StateStore()
    for morto in MORTOS:
        assert not hasattr(store, morto), (
            f"`StateStore.{morto}` voltou. A trava manual saiu inteira em "
            f"14/09/2026 por decisão dela — ver o topo deste arquivo"
        )
    assert hasattr(store, VIVO), (
        f"`StateStore.{VIVO}` sumiu. Ele NÃO é a trava manual: é o lock de 30 s "
        f"da escolha manual de perfil, e a decisão dela não o alcança"
    )


def test_nenhuma_linha_de_producao_arma_a_trava() -> None:
    """A régua que impede a volta em pedaços."""
    achados: list[str] = []
    for caminho, texto in _codigo_de_producao():
        for numero, linha in _linhas_de_codigo(texto):
            for morto in MORTOS:
                if f"{morto}(" in linha or f".{morto}" in linha:
                    rel = caminho.relative_to(RAIZ).as_posix()
                    achados.append(f"  {rel}:{numero}  {linha.strip()[:90]}")
    assert not achados, (
        "a trava manual voltou ao código de produção:\n"
        + "\n".join(achados)
        + "\n\nEla saiu inteira em 14/09/2026 por decisão dela — *«e pra qualquer "
          "outro jogo»*, *«isso nao faz sentido mais»*. "  # (noqa-acento): dela
          "Se um caminho novo precisa "
          "proteger um ajuste dela contra o perfil, a pergunta a fazer é outra: "
          "por que o ajuste não está NO perfil?"
    )


def test_as_constantes_da_trava_nao_voltaram() -> None:
    """As duas constantes que descreviam o mecanismo, e o teto que o prorrogava."""
    texto = (SRC / "daemon" / "state_store.py").read_text(encoding="utf-8")
    for numero, linha in _linhas_de_codigo(texto):
        for constante in ("MANUAL_OVERRIDE_CATEGORIES", "MANUAL_OVERRIDE_STALE_AFTER_SEC"):
            assert not re.match(rf"\s*{constante}\s*[:=]", linha), (
                f"`{constante}` voltou a `state_store.py:{numero}`. Ela declarava "
                f"as categorias da trava e o teto de seis horas que era a única "
                f"porta de saída de `led` e `audio` — as duas saíram com o "
                f"mecanismo em 14/09/2026"
            )
    assert "MANUAL_PROFILE_LOCK_SEC" in texto, (
        "`MANUAL_PROFILE_LOCK_SEC` sumiu do `state_store.py`. Ele é o lock de 30 s "
        "da escolha manual de perfil, e fica"
    )
