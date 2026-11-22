"""A-SAIDA-PELO-RADIO-DIZ-QUEM-SAIU-E-SE-O-PS-ESTAVA-SEGURADO-01 — a linha da saída se explica.

Medido em 21/11/2026: seis controles saíram do rádio com `bluez_controle_saiu
saida=o_controle_encerrou`, e o porquê só saía juntando quatro diários à mão: a linha não
dizia qual controle nem qual adaptador, o `ps_solo_ignorado_hold_longo` não levava o `de`, e
a mão vazia por falta de leitor era o mesmo `frozenset()` da mão sem botão.

O `DonoVivo` sobre o barramento de mentira, o `VigiaDaVaga` com relógio de mentira, e os
endereços da faixa forjada `aa:bb:cc` (octetos 4 e 5 zerados). Nenhum teste fala com o BlueZ
de verdade.

Morde:

* tirar o controle e o adaptador do `_como_saiu`: o primeiro caso reprova pela falta deles;
* tratar o tique sem leitura como PS solto: o primeiro sai com `ps_segurado_s=0`;
* tirar o `nao_lido`: o terceiro diz «0».
"""

from __future__ import annotations

from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import poll
from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyConfig, HotkeyManager
from tests.unit import bluez_de_mentira as bm

NO = bm.no_de(bm.CONTROLE)
NO_OUTRO = bm.no_de(bm.OUTRO)
TIQUE_S = 0.25
ANTES_DO_SINAL_S = 0.11
ENTRE_AS_SAIDAS_S = 0.6
PS_SEGURADO_S = 5.0


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Mesa:
    """O dono vivo com dois controles pareados e ligados, no mesmo adaptador."""

    def __init__(self) -> None:
        self.relogio = _Relogio()
        self.vaga = bd.VigiaDaVaga(self.relogio)
        self.barramento = bm.BarramentoDeMentira()
        for no in (NO, NO_OUTRO):
            self.barramento.mesa[no][bd.APARELHO].update(Paired=True, Connected=True)
        self.vivo = bd.DonoVivo(self.barramento, vaga=self.vaga)
        assert self.vivo.ligar()

    def tique(
        self, maos: dict[str | None, Iterable[str]], lidos: Iterable[str | None] | None,
    ) -> None:
        entrada = {quem: frozenset(botoes) for quem, botoes in maos.items()}
        self.vaga.observar(entrada, None if lidos is None else frozenset(lidos))

    def segurar_o_ps(self, segundos: float, *, quem: str = bm.CONTROLE) -> None:
        """Um tique lido a cada 0,25 s com o PS apertado, por `segundos`, e o outro sem botão."""
        outro = bm.OUTRO if quem == bm.CONTROLE else bm.CONTROLE
        fim = self.relogio.agora + segundos
        while True:
            self.tique({quem: {"ps"}, outro: set()}, [quem, outro])
            if self.relogio.agora >= fim:
                return
            self.relogio.agora = min(fim, self.relogio.agora + TIQUE_S)

    def sair(self, no: str = NO, razao: str = bd.RAZAO_DO_CONTROLE) -> dict[str, Any]:
        """A linha `bluez_controle_saiu` que a saída escreveu."""
        with structlog.testing.capture_logs() as registros:
            self.barramento.emitir(bd.Sinal("desconectou", caminho=no, razao=razao))
            self.barramento.emitir(
                bd.Sinal("mudou", caminho=no, interface=bd.APARELHO,
                         mudadas={"Connected": False}))
        linhas = [r for r in registros if r.get("event") == "bluez_controle_saiu"]
        assert len(linhas) == 1, [r.get("event") for r in registros]
        return dict(linhas[0])


def test_duas_saidas_no_mesmo_adaptador_dizem_cada_uma_o_seu_controle() -> None:
    """O PS do primeiro, 5,0 s; a mão dele chega vazia, sem leitor, 0,11 s antes do sinal."""
    mesa = _Mesa()
    mesa.segurar_o_ps(PS_SEGURADO_S)
    mesa.relogio.agora += ANTES_DO_SINAL_S
    mesa.tique({bm.CONTROLE: set(), bm.OUTRO: set()}, [bm.OUTRO])
    primeira = mesa.sair(NO)
    mesa.relogio.agora += ENTRE_AS_SAIDAS_S
    mesa.tique({bm.OUTRO: set()}, [bm.OUTRO])
    segunda = mesa.sair(NO_OUTRO)

    assert primeira["uniq"] == bm.CONTROLE and segunda["uniq"] == bm.OUTRO
    assert primeira["adaptador"] == segunda["adaptador"] == bm.ADAPTADOR
    assert primeira["saida"] == segunda["saida"] == bd.SAIDA_O_CONTROLE_ENCERROU
    assert primeira["ps_segurado_s"] == PS_SEGURADO_S, primeira
    assert segunda["ps_segurado_s"] == 0, segunda
    assert "ps_segurado" not in primeira and "ps_segurado" not in segunda


def test_o_controle_fora_do_mapa_de_maos_ainda_diz_o_ps_segurado() -> None:
    mesa = _Mesa()
    mesa.segurar_o_ps(PS_SEGURADO_S)
    mesa.relogio.agora += ANTES_DO_SINAL_S
    mesa.tique({bm.OUTRO: set()}, [bm.OUTRO])

    linha = mesa.sair(NO)

    assert linha["uniq"] == bm.CONTROLE
    assert linha["ps_segurado_s"] == PS_SEGURADO_S, linha


def test_o_controle_que_soltou_o_ps_antes_de_sair_diz_zero() -> None:
    mesa = _Mesa()
    mesa.segurar_o_ps(PS_SEGURADO_S)
    mesa.relogio.agora += TIQUE_S
    mesa.tique({bm.CONTROLE: set(), bm.OUTRO: set()}, [bm.CONTROLE, bm.OUTRO])

    assert mesa.sair(NO)["ps_segurado_s"] == 0


def test_sem_tique_lido_recente_a_linha_diz_nao_lido() -> None:
    """O modo nativo: o laço não roda os atalhos, e «0» seria mentira."""
    mesa = _Mesa()
    mesa.segurar_o_ps(PS_SEGURADO_S)
    mesa.relogio.agora += 2.0

    linha = mesa.sair(NO)

    assert linha["ps_segurado"] == "nao_lido", linha
    assert "ps_segurado_s" not in linha


def test_o_controle_que_nunca_foi_lido_diz_nao_lido() -> None:
    mesa = _Mesa()

    assert mesa.sair(NO)["ps_segurado"] == "nao_lido"


def test_a_troca_de_vaga_segue_dando_outro_aparelho() -> None:
    mesa = _Mesa()
    fim = mesa.relogio.agora + 3.0
    while mesa.relogio.agora < fim:
        mesa.tique({bm.CONTROLE: {"ps", "triangle"}}, [bm.CONTROLE])
        mesa.relogio.agora += TIQUE_S
    mesa.tique({bm.CONTROLE: {"ps", "triangle"}}, [bm.CONTROLE])

    assert mesa.sair(NO)["saida"] == bd.SAIDA_OUTRO_APARELHO


def test_o_ps_segurado_se_gasta_na_saida() -> None:
    mesa = _Mesa()
    mesa.segurar_o_ps(PS_SEGURADO_S)
    mesa.sair(NO)
    mesa.barramento.emitir(
        bd.Sinal("mudou", caminho=NO, interface=bd.APARELHO, mudadas={"Connected": True}))

    assert mesa.sair(NO)["ps_segurado"] == "nao_lido"


class _Gerente:
    def observe(self, *_a: Any, **_k: Any) -> None:
        return None


def test_o_laco_entrega_ao_vigia_quem_foi_lido_de_verdade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mão vazia por falta de leitor (sentado com o grab pendente) não conta como lida."""
    chamadas: list[tuple[dict[str | None, Any], Any]] = []
    monkeypatch.setattr(
        poll, "observar_o_gesto_da_vaga",
        lambda maos, lidos=None: chamadas.append((dict(maos), lidos)))
    controle = SimpleNamespace(
        primary_uniq=bm.CONTROLE, alvos_conectados=lambda: {"a": bm.CONTROLE, "b": bm.OUTRO},
        _evdev=SimpleNamespace(is_available=lambda: True))
    coop = SimpleNamespace(
        live_snapshots=lambda: {}, numeros_de_jogador=lambda: {bm.OUTRO: 2})
    daemon = SimpleNamespace(
        _hotkey_manager=_Gerente(), controller=controle, _coop_manager=coop)

    poll.observar_os_atalhos(daemon, frozenset({"ps"}), now=0.0)

    assert len(chamadas) == 1
    maos, lidos = chamadas[0]
    assert maos == {bm.CONTROLE: frozenset({"ps"}), bm.OUTRO: frozenset()}
    assert lidos is not None and bm.CONTROLE in lidos, lidos
    assert bm.OUTRO not in lidos, "a mão do sentado sem leitor contou como lida"


def test_o_ps_solo_ignorado_por_hold_longo_leva_o_controle() -> None:
    mgr = HotkeyManager(on_ps_solo=lambda: None, config=HotkeyConfig())
    with structlog.testing.capture_logs() as registros:
        mgr.observe(["ps"], now=0.0, de=bm.CONTROLE)
        mgr.observe([], now=5.0, de=bm.CONTROLE)

    recusas = [r for r in registros if r.get("event") == "ps_solo_ignorado_hold_longo"]
    assert len(recusas) == 1, [r.get("event") for r in registros]
    assert recusas[0]["de"] == bm.CONTROLE, recusas[0]
