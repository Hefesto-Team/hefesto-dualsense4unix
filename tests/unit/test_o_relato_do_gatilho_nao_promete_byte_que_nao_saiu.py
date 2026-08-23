"""ELO-MUDO-02 — `aplicado` só sai da boca de quem viu o byte sair.

O DEFEITO, MEDIDO EM 23/08/2026
===============================
A ELO-MUDO-01 (22/08) fechou o silêncio: gatilho e luz passaram a aparecer no
relatório de ativação em vez de sumir quando davam certo. O que ela escreveu
foi ``relatorio.setdefault(categoria, "aplicado")`` — a palavra FIXA. Com o
perfil ``Sackboy`` dela e a mesa vazia, o relatório saía assim::

    bytes escritos no aparelho: 0
    relatorio: {'led': 'aplicado', 'trigger': 'aplicado'}

Zero byte, duas seções afirmando que entraram. É a MESMA família que a
ELO-MUDO-01 nomeia, hospedada dentro da própria cura: ausência de notícia virou
notícia inventada.

O preço já foi pago uma vez: essa linha do journal sustentou um dia de caça a um
defeito de gravação de gatilho que não existe. Os 34 perfis dela guardam
``triggers`` — a medição que dizia o contrário perguntava por ``trigger``, no
singular, que não é campo de ``Profile``.

O QUE ESTE ARQUIVO PRENDE
=========================
1. o backend que CONHECE a mesa responde o que fez (``registrado`` sem
   ninguém, ``escreveu`` com alguém, ``nada_a_fazer`` sem pedido);
2. o relatório traduz isso para o dialeto dele e **não diz ``aplicado``** com a
   mesa vazia;
3. quem não sabe dizer (``None``) continua valendo ``aplicado`` — a disciplina
   do ``_estado_da_secao``: dublê e backend simples não podem fabricar veredito;
4. a trava manual continua vencendo os dois.

O DUBLÊ E POR QUE ELE É HONESTO
===============================
Os testes chamam o método REAL do ``PyDualSenseController`` (a função, não uma
cópia) sobre um objeto que carrega só o que ele toca. É o jeito de medir o
código de produção sem hardware: se alguém trocar o corpo do método, este
arquivo sente. Um dublê que reimplementasse a lógica não sentiria nada — seria
a régua medindo a si mesma, que é o defeito que esta casa chama de instrumento
mentiroso.
"""
from __future__ import annotations

import threading
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchManual,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

#: O método de PRODUÇÃO, tomado da classe. É ele que roda nos testes.
APLICAR_PADROES = PyDualSenseController.apply_output_defaults

#: MAC de teste — faixa sintética da casa, não é controle dela.
UNIQ_DE_TESTE = "aabbcc000001"


class _MesaDeControles:
    """O mínimo que `apply_output_defaults` toca, e um contador de escritas.

    `_for_each`/`_for_each_led` reproduzem a ÚNICA decisão do original que
    importa aqui: sem handle não sai byte (`output_offline_noop`).
    """

    def __init__(self, handles: dict[str, Any] | None = None) -> None:
        self._io_lock = threading.RLock()
        self._handles: dict[str, Any] = dict(handles or {})
        self._desired_default = type("_Desejado", (), {})()
        self._output_target_key: str | None = None
        self.escritas: list[str] = []

    def _for_each(
        self,
        op: Any,
        *,
        what: str,
        broadcast: bool = False,
        record: dict[str, Any] | None = None,
    ) -> None:
        if not self._handles:
            return
        self.escritas.extend(what for _ in self._handles)

    def _for_each_led(self, **kwargs: Any) -> None:
        self._for_each(None, what=str(kwargs["what"]), broadcast=True)

    def _apply_trigger(self, handle: Any, side: str, efeito: Any) -> None:
        return None

    def _pode_escrever_player_leds(self) -> bool:
        return True

    # --- o que o ProfileManager.apply chama além do broadcast ---
    def apply_output_defaults(self, spec: OutputSpec) -> Any:
        return APLICAR_PADROES(self, spec)  # type: ignore[arg-type]

    def reset_output_overrides(self, mapa: Any) -> None:
        return None

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> Any:
        return None


class _ControllerQueNaoSabeDizer(_MesaDeControles):
    """Backend simples/dublê: escreve e devolve `None` (não relata)."""

    def apply_output_defaults(self, spec: OutputSpec) -> Any:
        self.escritas.append("apply_output_defaults")
        return None


def _perfil_com_gatilho() -> Profile:
    """Perfil com a MESMA seção de gatilho do `Sackboy` dela."""
    return Profile(
        name="Perfil de teste",
        match=MatchManual(),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Feedback", params=[5, 4]),
            right=TriggerConfig(mode="Feedback", params=[5, 4]),
        ),
    )


def _spec_do_perfil(perfil: Profile) -> OutputSpec:
    return OutputSpec(
        trigger_left=build_from_name(
            perfil.triggers.left.mode, perfil.triggers.left.params
        ),
        trigger_right=build_from_name(
            perfil.triggers.right.mode, perfil.triggers.right.params
        ),
        led=(80, 60, 220),
        player_leds=(False, False, True, False, False),
    )


# ---------------------------------------------------------------------------
# 1. o backend responde o que fez
# ---------------------------------------------------------------------------


def test_mesa_vazia_devolve_registrado_e_nao_escreve_nada() -> None:
    mesa = _MesaDeControles(handles={})
    veredito = APLICAR_PADROES(mesa, _spec_do_perfil(_perfil_com_gatilho()))  # type: ignore[arg-type]
    assert mesa.escritas == [], "mesa vazia não pode escrever byte nenhum"
    assert veredito == "registrado", (
        "sem ninguém na mesa o pedido fica GUARDADO no `_desired_default` para o "
        f"hotplug — a palavra é `registrado`, veio {veredito!r}"
    )


def test_com_controle_na_mesa_devolve_escreveu() -> None:
    mesa = _MesaDeControles(handles={UNIQ_DE_TESTE: object()})
    veredito = APLICAR_PADROES(mesa, _spec_do_perfil(_perfil_com_gatilho()))  # type: ignore[arg-type]
    assert mesa.escritas, "com handle na mesa as escritas têm de sair"
    assert veredito == "escreveu"


def test_spec_sem_pedido_nenhum_devolve_nada_a_fazer() -> None:
    mesa = _MesaDeControles(handles={UNIQ_DE_TESTE: object()})
    veredito = APLICAR_PADROES(mesa, OutputSpec())  # type: ignore[arg-type]
    assert mesa.escritas == []
    assert veredito == "nada_a_fazer"


# ---------------------------------------------------------------------------
# 2. o relatório de ativação não promete o que não saiu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("secao", ["trigger", "led"])
def test_relatorio_com_mesa_vazia_nao_diz_aplicado(secao: str) -> None:
    """O caso medido em 23/08: zero byte e o relatório dizendo `aplicado`."""
    mesa = _MesaDeControles(handles={})
    relatorio: dict[str, str] = {}
    ProfileManager(controller=mesa).apply(  # type: ignore[arg-type]
        _perfil_com_gatilho(), origin="launch", relatorio=relatorio
    )
    assert mesa.escritas == [], "a régua exige zero byte para o caso valer"
    assert relatorio[secao] != "aplicado", (
        f"nenhum byte saiu e o relatório disse {relatorio[secao]!r} para {secao!r} — "
        "é a ELO-MUDO-01 dentro da própria cura"
    )
    assert relatorio[secao] == "adiado_sem_controle"


@pytest.mark.parametrize("secao", ["trigger", "led"])
def test_relatorio_com_controle_na_mesa_diz_aplicado(secao: str) -> None:
    mesa = _MesaDeControles(handles={UNIQ_DE_TESTE: object()})
    relatorio: dict[str, str] = {}
    ProfileManager(controller=mesa).apply(  # type: ignore[arg-type]
        _perfil_com_gatilho(), origin="launch", relatorio=relatorio
    )
    assert mesa.escritas, "a régua exige byte escrito para o caso valer"
    assert relatorio[secao] == "aplicado"


@pytest.mark.parametrize("secao", ["trigger", "led"])
def test_backend_que_nao_relata_continua_valendo_aplicado(secao: str) -> None:
    """`None` é "não sei dizer", nunca "nada aconteceu".

    Sem esta linha, todo dublê da suíte e todo backend de um controle só
    passariam a reportar um adiamento que ninguém mediu — a mentira ao
    contrário.
    """
    mesa = _ControllerQueNaoSabeDizer()
    relatorio: dict[str, str] = {}
    ProfileManager(controller=mesa).apply(  # type: ignore[arg-type]
        _perfil_com_gatilho(), origin="launch", relatorio=relatorio
    )
    assert relatorio[secao] == "aplicado"


# ---------------------------------------------------------------------------
# 3. a trava manual continua vencendo
# ---------------------------------------------------------------------------


class _StoreComTravaDeGatilho:
    """O store lê a trava como ATRIBUTO iterável, não como método."""

    manual_override_categories = frozenset({"trigger"})


def test_trava_manual_vence_o_veredito_do_controller() -> None:
    """Gatilho travado diz `ignorado_trava_manual`; a luz fica com o veredito."""
    mesa = _MesaDeControles(handles={})
    relatorio: dict[str, str] = {}
    gerente = ProfileManager(controller=mesa)  # type: ignore[arg-type]
    gerente.store = _StoreComTravaDeGatilho()  # type: ignore[assignment]
    gerente.apply(_perfil_com_gatilho(), origin="launch", relatorio=relatorio)
    assert relatorio["trigger"] == "ignorado_trava_manual"
    assert relatorio["led"] == "adiado_sem_controle"
