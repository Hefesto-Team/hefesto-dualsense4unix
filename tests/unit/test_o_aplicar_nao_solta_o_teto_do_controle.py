"""O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 — o «Aplicar» e o «Salvar» respeitam a economia.

Achado pela O-BRILHO-DAS-LUZES-SOBREVIVE-AO-APLICAR-01 (26/09/2026). O rascunho
do rodapé não sabia da economia de bateria, e o `DraftApplier` troca o mapa de
overrides do daemon inteiro (`reset_output_overrides`).

**MEDIDO ANTES DA CURA**, na mesa de quatro da A-MARCA (o `IpcServer` real, o
merge do `PyDualSenseController`, o `SysfsLedNode` sobre arquivos), a economia
ligada só no P2 (laranja, perfil a 82%, as luzes dele no Forte, o global no
Médio), cabo e rádio iguais::

                    luz            luzes    gatilhos (força)   vibração
    ativação        (76, 38, 0)    Fraco    73, 18             0,3
    «Aplicar»       (209, 104, 0)  Médio    182, 45            —

e o «Salvar» com a economia ligada gravava os 30% do teto como o brilho DELA:
desligada a economia, o P2 seguia a `(76, 38, 0)` para sempre. Na «Bateria
longa», o mesmo em todos os controles.

A CURA, e cada régua abaixo mede uma parte:

* o rascunho leva o Fraco, o Médio e o Forte (global e de cada controle), e a
  segunda viagem do rodapé saiu (`DraftConfig._controllers_to_ipc`);
* o `DraftApplier` põe o teto pelo MESMO dono da ativação
  (`_com_o_teto_da_economia` → `manager._perfil_na_economia`, com a declaração
  que o gesto `economia-do-controle` grava), e o controle em economia vai na
  camada do PERFIL (`_publicar_a_economia`): na camada dela o teto ficaria
  preso depois de a economia desligar;
* o «Todos» das luzes só vai cru a todos quando ninguém termina noutro
  degrau (`DraftApplier._o_todos_das_luzes`): nenhum quadro intermediário;
* o «Salvar» grava o brilho do disco, e não o aceso, no controle em economia
  (`rodape._quem_esta_em_economia`);
* a procedência da cor mora no `DraftConfig` (`_com_a_procedencia_da_mesma_cor`).

**AS MORDIDAS**, arrancadas e devolvidas (o relato da sprint diz o que caiu):

* tire o `_com_o_teto_da_economia` do `DraftApplier.apply` → a seção 1 e a 2
  reprovam no «Aplicar»;
* troque o `reset_profile_overrides` de `_publicar_a_economia` pelo
  `apply_output_for` (a camada dela) → a seção 1 reprova ao desligar a economia;
* tire o `na_economia(uniq)` do `rodape._draft_do_ativo` → a seção 1 e a 2
  reprovam no disco depois do «Salvar»;
* faça o `_o_todos_das_luzes` devolver sempre o degrau → a seção 1 acusa o
  quadro intermediário;
* tire o `player_led_brightness` de `_controllers_to_ipc` → a seção 3 reprova,
  e a seção 1 da O-BRILHO junto;
* tire o `_com_a_procedencia_da_mesma_cor` do `with_controller_leds` → a seção 4.

A régua dela, a de toda decisão: *«nunca é pensada só em um modo, rota, forma
de conexão se cabo ou se bt, ou só pro player 1.»* <!-- noqa-acento: citação literal dela -->
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

from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES
from tests.unit import test_a_04_pergunta_ao_daemon_vivo as viva
from tests.unit import test_a_marca_da_cor_nao_some as marca
from tests.unit import test_o_brilho_das_luzes_sobrevive_ao_aplicar_e_ao_salvar as regua_do_brilho
from tests.unit.test_a_marca_da_cor_nao_some import MACS, NOME, UNIQS

# O caminho de `pacotes` é posto pela mesa da A-MARCA, importada acima.
import pacotes
from pacotes import a04_iluminacao, rodape

#: UM BRILHO DIFERENTE EM CADA: a palavra das luzes e o trilho da barra. Tudo
#: acima do teto da economia (Fraco e 30%), senão o teto passaria sem a cura.
PALAVRAS = {1: "forte", 2: "medio", 3: "forte", 4: "medio"}  # (noqa-acento) chaves ASCII
TRILHOS = {1: 90, 2: 70, 3: 60, 4: 50}
#: O «Todos» das luzes: diferente de todas, para o global cru aparecer se vier.
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
def mesa_de(tmp_path, monkeypatch):
    """A mesa de quatro da O-BRILHO, com os handles que guardam os quadros."""
    feitas: list[Any] = []

    def montar(via: str) -> Any:
        monkeypatch.setattr(marca, "_handle_falso", lambda: _handle_que_grava(via))
        m = viva.MesaViva(tmp_path / f"mesa-{len(feitas)}", pacotes, a04_iluminacao)
        m.ponte = regua_do_brilho._PonteDaAba(m)
        feitas.append(m)
        vias = {m.ctl._detect_transport(h) for h in m.ctl._handles.values()}
        assert vias == {via}, f"a mesa pediu {via} e o backend leu {vias}"
        return m

    yield montar
    for m in feitas:
        m.fechar()


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


def _cada_um_no_seu(mesa: Any) -> None:
    """A palavra e o trilho de cada controle, pelos gestos da aba 04, e o perfil reaplicado."""
    regua_do_brilho._o_global_das_luzes(mesa, GLOBAL_DAS_LUZES)
    trilho = pacotes.gesto_da_pagina(a04_iluminacao.PAGINA, "brilho")
    for n in (1, 2, 3, 4):
        trilho(mesa.ctx(), {"uniq": UNIQS[n - 1], "valor": str(TRILHOS[n]),
                            "tipo": "input", "evento": "change"}, mesa.ponte)
        mesa.clicar_na_pilula(n, PALAVRAS[n])
    mesa.trocar(NOME, "manual")


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


def _o_aplicar_nao_mexe_e_nao_pisca(mesa: Any, esperado: dict[int, dict[str, Any]],
                                   onde: str) -> None:
    """O «Aplicar» deixa cada controle como a ativação o deixou, sem quadro no meio."""
    _zerar_os_quadros(mesa)
    regua_do_brilho._aplicar(mesa)
    depois = _mesa_inteira(mesa)
    for n in (1, 2, 3, 4):
        assert depois[n] == esperado[n], (
            f"{onde}: o «Aplicar» mudou o P{n} de {esperado[n]} para {depois[n]}")
        final = depois[n]["luzes"][1]
        assert set(_quadros(mesa, n)) <= {final}, (
            f"{onde}: as luzes do P{n} passaram por {_quadros(mesa, n)} antes do "
            f"degrau {final} — um quadro intermediário")


# ---------------------------------------------------------------------------
# 1. A economia de UM controle — P1 a P4, cabo e rádio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("k", [1, 2, 3, 4], ids=["P1", "P2", "P3", "P4"])
def test_a_economia_de_um_controle_atravessa_o_aplicar_o_salvar_e_sai_quando_desliga(
        mesa_de, economia, k: int, via: str) -> None:
    """A economia no P<k>, e os outros três com a palavra e o trilho deles.

    Ativação → «Aplicar» → «Salvar» → economia desligada: o aparelho de cada
    um é o que a ativação decidiu, o disco guarda o que ELA escolheu, e o P<k>
    volta inteiro quando a economia sai — pela ativação `system`, que é a que
    o daemon faz no clique (`lifecycle.reaplicar_se_a_economia_mudou`).
    """
    from hefesto_dualsense4unix.profiles.schema import declaracao_da_economia

    mesa = mesa_de(via)
    _cada_um_no_seu(mesa)
    livre = _mesa_inteira(mesa)
    disco = {n: _o_disco(n) for n in (1, 2, 3, 4)}
    assert disco[k] == {"barra": TRILHOS[k] / 100, "luzes": PALAVRAS[k]}, disco[k]

    economia(declaracao_da_economia(UNIQS[k - 1], True))
    mesa.trocar(NOME, "manual")
    esperado = _mesa_inteira(mesa)
    # A régua precisa do teto no P<k>, e só nele.
    assert esperado[k]["luzes"] == (FRACO, FRACO), esperado[k]
    assert esperado[k]["barra"] is not None and esperado[k]["barra"] <= 0.3, esperado[k]
    assert esperado[k]["gatilhos"] != livre[k]["gatilhos"], "a economia não pôs teto no gatilho"
    for n in {1, 2, 3, 4} - {k}:
        assert esperado[n] == livre[n], f"a economia do P{k} mexeu no P{n}"

    _o_aplicar_nao_mexe_e_nao_pisca(mesa, esperado, f"P{k}/{via}")

    regua_do_brilho._salvar(mesa)
    assert _mesa_inteira(mesa) == esperado, "o «Salvar» mexeu no aparelho"
    for n in (1, 2, 3, 4):
        assert _o_disco(n) == disco[n], (
            f"P{k}/{via}: o «Salvar» gravou no P{n} {_o_disco(n)}, e ela escolheu "
            f"{disco[n]} — o teto da economia não é escolha dela")

    economia(declaracao_da_economia(UNIQS[k - 1], False))
    mesa.trocar(NOME, "system")
    solto = _estado(mesa, k)
    for campo in ("luzes", "gatilhos", "vibracao", "barra"):
        assert solto[campo] == livre[k][campo], (
            f"P{k}/{via}: com a economia desligada o {campo} ficou {solto[campo]}, "
            f"e sem ela era {livre[k][campo]} — o teto ficou preso")


# ---------------------------------------------------------------------------
# 2. A «Bateria longa» da mesa inteira
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("via", ["usb", "bt"])
def test_a_bateria_longa_atravessa_o_aplicar_e_o_salvar(mesa_de, economia, via: str) -> None:
    """O Perfil Global de Bateria em «Bateria longa»: os quatro no teto, e o disco no dela."""
    mesa = mesa_de(via)
    _cada_um_no_seu(mesa)
    livre = _mesa_inteira(mesa)
    disco = {n: _o_disco(n) for n in (1, 2, 3, 4)}

    economia({"orcamento": {"teto": "economia"}})
    mesa.trocar(NOME, "manual")
    esperado = _mesa_inteira(mesa)
    for n in (1, 2, 3, 4):
        assert esperado[n]["luzes"] == (FRACO, FRACO), (n, esperado[n])
        assert esperado[n]["barra"] is not None and esperado[n]["barra"] <= 0.3, esperado[n]

    _o_aplicar_nao_mexe_e_nao_pisca(mesa, esperado, f"mesa/{via}")

    regua_do_brilho._salvar(mesa)
    for n in (1, 2, 3, 4):
        assert _o_disco(n) == disco[n], (
            f"mesa/{via}: o «Salvar» gravou no P{n} {_o_disco(n)}, e ela escolheu {disco[n]}")

    economia({"orcamento": {"teto": None}})
    mesa.trocar(NOME, "system")
    for n in (1, 2, 3, 4):
        solto = _estado(mesa, n)
        assert (solto["luzes"], solto["barra"]) == (livre[n]["luzes"], livre[n]["barra"]), (
            f"mesa/{via}: o P{n} ficou em {solto} depois da «Bateria longa»")


# ---------------------------------------------------------------------------
# 3. O rascunho leva o Fraco, o Médio e o Forte — o global e o de cada um
# ---------------------------------------------------------------------------
def test_o_rascunho_leva_as_luzes_de_numero_de_quem_as_escreveu() -> None:
    """`to_ipc_dict` com o «Todos» em `leds`, e a palavra só de quem a escreveu."""
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        MatchAny,
        Profile,
    )

    forte = LedsConfig(player_led_brightness="forte")
    prof = Profile(name="regua", match=MatchAny(),
                   leds=LedsConfig(player_led_brightness="medio"),  # (noqa-acento) chave ASCII
                   controllers={
                       UNIQS[1]: ControllerOverrides(leds=forte),
                       UNIQS[2]: ControllerOverrides(leds=LedsConfig(lightbar=(0, 255, 255))),
                   })
    ipc = DraftConfig.from_profile(prof).to_ipc_dict()
    assert ipc["leds"]["player_led_brightness"] == "medio"  # (noqa-acento) chave ASCII
    assert ipc["controllers"][UNIQS[1]]["leds"] == {"player_led_brightness": "forte"}
    assert "player_led_brightness" not in ipc["controllers"][UNIQS[2]]["leds"], (
        "o P3 não escreveu a palavra, e o rascunho a inventou")


def test_sem_economia_o_aplicar_e_o_de_antes() -> None:
    """Nenhuma economia declarada: a vista é o MESMO rascunho, byte a byte."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
    from hefesto_dualsense4unix.profiles.schema import registrar_declaracao_da_mesa

    registrar_declaracao_da_mesa(None)
    applier = DraftApplier(controller=object(), store=object(), daemon=None)  # type: ignore[arg-type]
    rascunho: dict[str, Any] = {"leds": {"lightbar_brightness": 1.0}, "controllers": None}
    assert applier._com_o_teto_da_economia(rascunho) is rascunho
    assert applier._em_economia == frozenset()


# ---------------------------------------------------------------------------
# 4. A procedência da cor mora no `DraftConfig`, e o rodapé não usa o privado
# ---------------------------------------------------------------------------
def test_a_mesma_cor_regravada_guarda_o_numero_e_a_outra_nao() -> None:
    """`with_controller_leds` leva o `lightbar_para_o_numero` só da MESMA cor."""
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        MatchAny,
        Profile,
    )

    tom = (255, 128, 0)
    prof = Profile(name="regua", match=MatchAny(), controllers={UNIQS[3]: ControllerOverrides(
        leds=LedsConfig(lightbar=tom, lightbar_para_o_numero=2))})
    draft = DraftConfig.from_profile(prof)
    base = draft.effective_leds_for(UNIQS[3])
    igual = draft.with_controller_leds(UNIQS[3], base.model_copy(update={"lightbar_rgb": tom}))
    assert igual.controller_override(UNIQS[3]).leds.lightbar_para_o_numero == 2
    outra = draft.with_controller_leds(
        UNIQS[3], base.model_copy(update={"lightbar_rgb": (0, 255, 255)}))
    leds = outra.controller_override(UNIQS[3]).leds
    assert "lightbar_para_o_numero" not in leds.model_fields_set, (
        f"a cor nova saiu com o número da antiga: {leds}")


def test_o_rodape_nao_escreve_no_rascunho_pela_porta_privada() -> None:
    """Nenhum `_with_*` no rodapé: a regra da cor é do `DraftConfig`."""
    fonte = pathlib.Path(rodape.__file__).read_text(encoding="utf-8")
    privados = sorted({
        no.attr for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.Attribute) and no.attr.startswith("_with_")})
    assert privados == [], f"o rodapé escreve no rascunho por {privados}"
