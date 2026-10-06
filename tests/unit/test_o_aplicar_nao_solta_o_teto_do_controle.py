"""O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 — o «Aplicar» e o «Salvar» respeitam a economia.

Achado pela O-BRILHO-DAS-LUZES-SOBREVIVE-AO-APLICAR-01 (26/09/2026). O rascunho
do rodapé não sabia da economia de bateria, e o «Aplicar» de então trocava o mapa
de overrides do daemon inteiro (`reset_output_overrides`).

**MEDIDO ANTES DA CURA**, na mesa de quatro da A-MARCA (o `IpcServer` real, o
merge do `PyDualSenseController`, o `SysfsLedNode` sobre arquivos), a economia
ligada só no P2 (laranja, perfil a 82%, as luzes dele no Forte, o global no
Médio), cabo e rádio iguais::

                    luz            luzes    gatilhos (força)   vibração
    ativação        (76, 38, 0)    Fraco    73, 18             0,3
    «Aplicar»       (209, 104, 0)  Médio    182, 45            —

e o «Salvar» com a economia ligada gravava os 30% do teto como o brilho DO USUÁRIO:
desligada a economia, o P2 seguia a `(76, 38, 0)` para sempre. Na «Bateria
longa», o mesmo em todos os controles.

A CURA, e cada régua abaixo mede uma parte:

* o rascunho leva o Fraco, o Médio e o Forte (global e de cada controle), e a
  segunda viagem do rodapé saiu (`DraftConfig._controllers_to_ipc`);
* o «Aplicar» põe o teto pelo MESMO dono da ativação
  (`manager._perfil_na_economia`, com a declaração que o gesto
  `economia-do-controle` grava), e o controle em economia vai na camada do
  PERFIL: na camada do usuário o teto ficaria preso depois de a economia
  desligar;
* o «Todos» das luzes só vai cru a todos quando ninguém termina noutro
  degrau (`manager._o_todos_das_luzes_vai_cru`): nenhum quadro intermediário;
* o «Salvar» grava o brilho do disco, e não o aceso, no controle em economia:
  desde 27/09 ele não lê o aparelho em controle nenhum
  (`D-2709-O-SALVAR-LE-O-PERFIL`);
* a procedência da cor mora no `DraftConfig` (`_com_a_procedencia_da_mesma_cor`).

**AS MORDIDAS**, arrancadas e devolvidas (o relato da sprint diz o que caiu):

* tire o `_perfil_na_economia` do `ProfileManager.apply` → a seção 1 reprova
  no «Aplicar»;
* devolva ao `rodape.salvar` a luz acesa (a cor e o brilho do aparelho no
  override) → a seção 1 e a 2 reprovam no disco depois do «Salvar»;
* faça o `_o_todos_das_luzes_vai_cru` devolver sempre `True` → a seção 1 acusa
  o quadro intermediário;
* tire o `player_led_brightness` de `_controllers_to_ipc` → a seção 3 reprova,
  e a seção 1 da O-BRILHO junto;
* tire o `_com_a_procedencia_da_mesma_cor` do `with_controller_leds` → a seção 4;

NOTA DATADA — 01/10/2026 (O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01). O «Aplicar»
do rodapé manda `profile.reaplicar`, e o daemon roda a cadeia da ativação; o
`profile.apply_draft` e o `DraftApplier` saíram do código em 06/10/2026, com as
seções que os chamavam direto.

A régua dela, a de toda decisão: *«nunca é pensada só em um modo, rota, forma
de conexão se cabo ou se bt, ou só pro player 1.»* <!-- noqa-acento: citação literal -->
— P1 a P4, cabo e rádio.

O LAR É DE MENTIRA: o `conftest` desvia o `HOME` e os `XDG_*`; o perfil e o
`maquina.json` gravados aqui moram dentro dele.
"""
from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa as réguas da aba 04, que carregam o GTK")

from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES
from tests.unit.test_a_marca_da_cor_nao_some import MACS, NOME, UNIQS

from pacotes import a04_iluminacao, rodape

PALAVRAS = {1: "forte", 2: "medio", 3: "forte", 4: "medio"}  # (noqa-acento) chaves ASCII
TRILHOS = {1: 90, 2: 70, 3: 60, 4: 50}
GLOBAL_DAS_LUZES = "fraco"
FRACO = BRILHOS_DAS_LUZES["fraco"]


class _HandleQueGrava(SimpleNamespace):
    """O handle falso da A-MARCA, que guarda cada degrau das luzes que o Hefesto lhe leva.

    `_brilho_das_luzes` é onde os dois transportes deixam o degrau
    (`PyDualSenseController._levar_o_brilho_das_luzes` e o quadro do rádio): a
    lista é a sequência de quadros que o aparelho recebeu.
    """

    def __setattr__(self, nome: str, valor: Any) -> None:
        if nome == "_brilho_das_luzes":
            self.__dict__.setdefault("quadros", []).append(int(valor))
        super().__setattr__(nome, valor)


def _handle_que_grava(via: str) -> Any:
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    h = _HandleQueGrava(
        connected=True, triggerL=DSTrigger(), triggerR=DSTrigger(),
        light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None)
    if via == "bt":
        h.conType = SimpleNamespace(name="BT")
    return h


@pytest.fixture
def economia() -> Iterator[Any]:
    """Liga e desliga a economia pelo `maquina.json` do lar de mentira."""
    from hefesto_dualsense4unix.profiles.schema import registrar_declaracao_da_mesa
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, gravar_maquina

    registrar_declaracao_da_mesa(carregar_maquina)

    def declarar(declaracao: dict[str, Any]) -> None:
        assert gravar_maquina(declaracao), f"o lar de mentira recusou {declaracao}"

    yield declarar
    registrar_declaracao_da_mesa(None)


def _estado(mesa: Any, n: int) -> dict[str, Any]:
    """O aparelho do P<n>: a luz, as luzes de número, os gatilhos, a vibração e o brilho aceso."""
    ctl = mesa.ctl
    with ctl._io_lock:
        d = ctl._merged_desired_for_key(MACS[n - 1])
    return {"luz": mesa.luz(n), "luzes": mesa.degrau(n),
            "gatilhos": (d.trigger_left, d.trigger_right),
            "vibracao": ctl._rumble_scale_by_uniq.get(UNIQS[n - 1]),
            "barra": mesa.server._brilhos_acesos(UNIQS[n - 1])["brilho_da_barra"]}


def _mesa_inteira(mesa: Any) -> dict[int, dict[str, Any]]:
    return {n: _estado(mesa, n) for n in (1, 2, 3, 4)}


def _zerar_os_quadros(mesa: Any) -> None:
    for h in mesa.ctl._handles.values():
        h.__dict__["quadros"] = []


def _quadros(mesa: Any, n: int) -> list[int]:
    return list(mesa.ctl._handles[MACS[n - 1]].__dict__.get("quadros") or [])


def _o_disco(n: int) -> dict[str, Any]:
    """O brilho da barra e a palavra das luzes que o disco guarda para o P<n>."""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    prof = load_profile(NOME)
    dele = prof.controllers.get(a04_iluminacao.chave_do_override(UNIQS[n - 1]))
    leds = getattr(dele, "leds", None)
    escritos = leds.model_fields_set if leds is not None else set()
    return {
        "barra": (round(leds.lightbar_brightness, 2) if "lightbar_brightness" in escritos
                  else round(prof.leds.lightbar_brightness, 2)),
        "luzes": (leds.player_led_brightness if "player_led_brightness" in escritos
                  else prof.leds.player_led_brightness),
    }


def test_o_rodape_nao_escreve_no_rascunho_pela_porta_privada() -> None:
    """Nenhum `_with_*` no rodapé: a regra da cor é do `DraftConfig`."""
    fonte = pathlib.Path(rodape.__file__).read_text(encoding="utf-8")
    privados = sorted({
        no.attr for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.Attribute) and no.attr.startswith("_with_")})
    assert privados == [], f"o rodapé escreve no rascunho por {privados}"
