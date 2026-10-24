"""O-LED-DE-QUEM-VOLTA-ACENDE-E-O-DISCOVER-NAO-REPETE-NA-ESPERA-01 (24/10/2026).

Os restos do LED de quem espera no lugar guardado, no caminho do sysfs (o controle sem a
camada do co-op): o aviso do `discover` que falha sai uma vez por borda, e não por tique
de espera; quem volta e cujo nó de LED aparece depois do primeiro ciclo acende o número
quando o nó aparece, uma vez; o `disable()` e a camada do co-op esvaziam os avisos ditos,
e religado o co-op o nó que falta se avisa de novo. E o gesto do mapa não manda devolver
a cor clicando na do número: a cor de antes pode ser a do plástico; nem a réplica da luz
parte dela (O-GESTO-DA-REPLICA-DA-LUZ-DIZ-A-COR-DO-PLASTICO-01).

MORDIDAS: cada cura arrancada reprova o caso dela (o relato do conjunto as lista).
"""
from __future__ import annotations

import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.led_control import player_led_pattern
from tests.unit.test_o_led_de_quem_espera_nao_enche_o_diario import (
    MATRIZ,
    P1,
    P2,
    P3,
    P4,
    QUATRO,
    TIQUES,
    _Mesa,
    _No,
)

DISCOVER = "coop_player_led_discover_falhou"
AVISO = "coop_player_led_indisponivel"
DISCOVER_DO_SYSFS = "hefesto_dualsense4unix.core.sysfs_leds.discover"
RAIZ = Path(__file__).resolve().parents[2]
GESTO = RAIZ / "docs/method/2026-09-07-O-COMO-DO-MAPA-o-gesto-das-178-celulas.md"

#: A matriz do vizinho e a mesa de um só (o P1 sem secundário: não há lâmpada do co-op).
MATRIZ_COM_UM = [*MATRIZ, ("um-so", {P1: QUATRO[P1]}, ())]


def _eventos(registros: list[MutableMapping[str, Any]], nome: str) -> list[str]:
    return [str(r.get("identity")) for r in registros if r.get("event") == nome]


def _o_discover_falha(monkeypatch: pytest.MonkeyPatch, m: _Mesa) -> list[bool]:
    """O `discover` do sysfs que levanta enquanto a chave estiver ligada."""
    falha = [True]

    def discover() -> dict[str, _No]:
        if falha[0]:
            raise OSError("leds ilegível")
        return {mac: _No(m.escritas, mac) for mac in m.leds}

    monkeypatch.setattr(DISCOVER_DO_SYSFS, discover)
    return falha


@pytest.mark.parametrize(
    ("mesa", "nos", "esperam"), MATRIZ_COM_UM, ids=[m[0] for m in MATRIZ_COM_UM]
)
def test_o_discover_que_falha_na_espera_avisa_uma_vez(
    monkeypatch: pytest.MonkeyPatch, mesa: str, nos: dict[str, str], esperam: tuple[str, ...]
) -> None:
    m = _Mesa(monkeypatch, nos)
    falha = _o_discover_falha(monkeypatch, m)
    with structlog.testing.capture_logs() as registros:
        if esperam:
            m.sai(*esperam)
        m.tiques(TIQUES)
    assert all(m.mgr._players[mac].a_espera for mac in esperam), mesa
    avisos = _eventos(registros, DISCOVER)
    assert len(avisos) == (1 if esperam else 0), (
        f"{mesa}: {len(avisos)} avisos do discover em {TIQUES} tiques de espera")
    if not esperam:
        return
    with structlog.testing.capture_logs() as registros:
        falha[0] = False
        m.tiques(3)
        falha[0] = True
        m.tiques(TIQUES)
    assert len(_eventos(registros, DISCOVER)) == 1, (
        f"{mesa}: o discover que voltou a funcionar e caiu de novo é outra borda")


@pytest.mark.parametrize(("mesa", "nos", "esperam"), MATRIZ, ids=[m[0] for m in MATRIZ])
def test_o_no_que_aparece_depois_da_volta_acende_o_numero_uma_vez(
    monkeypatch: pytest.MonkeyPatch, mesa: str, nos: dict[str, str], esperam: tuple[str, ...]
) -> None:
    # D-2410-O-LED-PENDENTE-ACENDE-QUANDO-O-NO-APARECE
    m = _Mesa(monkeypatch, nos)
    m.sai(*esperam)
    m.tiques(10)
    for i, mac in enumerate(esperam):
        m.nos[mac] = f"/dev/input/event{60 + i}"
        m.registro.ligados.add(mac)
        m.registro.saiu_em.pop(mac, None)
    m.mudou[0] = True
    m.escritas.clear()
    m.mgr.sync()
    assert not any(m.mgr._players[mac].a_espera for mac in esperam), mesa
    m.tiques(4)
    assert not [mac for mac, _ in m.escritas if mac in esperam], "sem nó, nada se escreve"
    m.leds.update(esperam)
    m.tiques(1)
    numeros = m.mgr.numeros_de_jogador()
    for mac in esperam:
        esperado = (mac, tuple(player_led_pattern(numeros[mac])))
        assert m.escritas.count(esperado) == 1, (
            f"{mesa}: o nó de {mac} apareceu no quinto tique e o número dele não acendeu "
            f"({m.escritas})")
    m.escritas.clear()
    m.tiques(TIQUES)
    assert not [mac for mac, _ in m.escritas if mac in esperam], (
        f"{mesa}: o número aceso se reescreveu a cada tique ({m.escritas})")


def _desligar_e_religar(m: _Mesa) -> None:
    m.daemon.config.coop_enabled = False
    m.mgr.sync()
    assert not m.mgr._players
    m.daemon.config.coop_enabled = True
    m.mudou[0] = True
    m.mgr.sync()


@pytest.mark.parametrize(("mesa", "nos", "esperam"), MATRIZ, ids=[m[0] for m in MATRIZ])
def test_religado_o_coop_o_no_que_falta_se_avisa_de_novo(
    monkeypatch: pytest.MonkeyPatch, mesa: str, nos: dict[str, str], esperam: tuple[str, ...]
) -> None:
    m = _Mesa(monkeypatch, nos)
    falta = esperam[0]
    with structlog.testing.capture_logs() as registros:
        m.leds.discard(falta)
        m.mudou[0] = True
        m.mgr.sync()
        m.tiques(5)
    assert _eventos(registros, AVISO).count(falta) == 1, _eventos(registros, AVISO)
    with structlog.testing.capture_logs() as registros:
        _desligar_e_religar(m)
    assert _eventos(registros, AVISO).count(falta) == 1, (
        f"{mesa}: religado o co-op, o nó de {falta} que segue faltando não se avisou")


@pytest.mark.parametrize(("mesa", "nos", "esperam"), MATRIZ, ids=[m[0] for m in MATRIZ])
def test_religado_o_coop_o_discover_que_segue_falhando_se_avisa_de_novo(
    monkeypatch: pytest.MonkeyPatch, mesa: str, nos: dict[str, str], esperam: tuple[str, ...]
) -> None:
    m = _Mesa(monkeypatch, nos)
    _o_discover_falha(monkeypatch, m)
    with structlog.testing.capture_logs() as registros:
        m.mudou[0] = True
        m.mgr.sync()
        m.tiques(5)
    assert len(_eventos(registros, DISCOVER)) == 1, mesa
    with structlog.testing.capture_logs() as registros:
        _desligar_e_religar(m)
    assert len(_eventos(registros, DISCOVER)) == 1, (
        f"{mesa}: religado o co-op, o discover que segue falhando não se avisou")


def test_a_camada_do_coop_esvazia_os_avisos_do_sysfs(monkeypatch: pytest.MonkeyPatch) -> None:
    """O controle que passa a publicar a camada não guarda o aviso do caminho do sysfs."""
    m = _Mesa(monkeypatch, QUATRO)
    m.leds.discard(P4)
    m.mudou[0] = True
    m.mgr.sync()
    assert P4 in m.mgr._led_indisponivel
    camadas: list[Any] = []
    m.daemon.controller.set_coop_outputs = lambda saidas, **_kw: camadas.append(saidas)
    m.mudou[0] = True
    m.mgr.sync()
    assert camadas, "a camada do co-op não se publicou"
    assert m.mgr._led_indisponivel == frozenset(), m.mgr._led_indisponivel
    del m.daemon.controller.set_coop_outputs
    with structlog.testing.capture_logs() as registros:
        m.mudou[0] = True
        m.mgr.sync()
    assert _eventos(registros, AVISO).count(P4) == 1, _eventos(registros, AVISO)


def test_o_gesto_do_mapa_nao_devolve_a_cor_pela_do_numero() -> None:
    """A cor de antes de um controle com o plástico lido é a do plástico (3de549aa6)."""
    passos = [
        linha for linha in GESTO.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\d+\. ", linha)
        and re.search(r"devolver|desfazer", linha)
        and re.search(r"quadradinho (da cor do número|azul \(o primeiro\)|verde \(o terceiro\))"
                      r"|a cor do número de cada um", linha)
    ]
    assert not passos, "\n".join(passos)


_ORDINAIS = {
    "primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4, "quinto": 5, "sexto": 6,
    "sétimo": 7, "oitavo": 8, "nono": 9, "décimo": 10,
}


def test_a_cor_que_se_devolve_foi_anotada_antes() -> None:
    # D-2410-O-GESTO-DEVOLVE-A-COR-ANOTADA
    """Quem devolve a «Cor» devolve à que anotou num passo da mesma célula."""
    erros: list[str] = []
    passos: dict[int, str] = {}
    for linha in GESTO.read_text(encoding="utf-8").splitlines():
        if linha.startswith("## "):
            passos = {}
        achou = re.match(r"^(\d+)\. (.*)$", linha)
        if not achou:
            continue
        passos[int(achou[1])] = achou[2]
        if not re.search(r"[Dd]evolva a «Cor»", linha):
            continue
        ref = re.search(r"à que você anotou no (\w+) passo\.$", linha)
        alvo = passos.get(_ORDINAIS.get(ref[1], 0), "") if ref else ""
        if not re.search(r"[Aa]note\b.*(«Cor»|\bcor\b)", alvo):
            erros.append(linha)
    assert not erros, "\n".join(erros)


#: A cor de partida dita como a do número, sem o plástico: «começa azul», «ficou verde e
#: a do P4 rosa», «deixou o azul», «a cor do número continua»…
_PARTIDA_PELO_NUMERO = re.compile(
    r"[Cc]omeça (azul|vermelho|verde|rosa)|deixou o (azul|vermelho|verde|rosa)"
    r"|ficou (azul|vermelha|verde|rosa) e a do P\d|cor automática do número"
    r"|cor do número")


def test_a_replica_da_luz_comeca_na_cor_do_plastico() -> None:
    """Na réplica da luz a cor de partida é a automática: a do plástico, e sem ele a do número."""
    erros: list[str] = []
    celulas = 0
    secao = ""
    passos: dict[int, str] = {}
    texto: dict[str, str] = {}
    for linha in GESTO.read_text(encoding="utf-8").splitlines():
        if linha.startswith("## "):
            secao, passos = linha, {}
            celulas += secao.startswith("## mapa-luz.replica_output_jogo-")
            continue
        if not secao.startswith("## mapa-luz.replica_output_jogo-"):
            continue
        texto[secao] = texto.get(secao, "") + linha + "\n"
        for frase in re.split(r"(?<=[.;—])\s", linha):
            if _PARTIDA_PELO_NUMERO.search(frase) and "sem o plástico" not in frase:
                erros.append(f"{secao[3:].split(' — ')[0]}: {frase}")
        achou = re.match(r"^(\d+)\. (.*)$", linha)
        if not achou:
            continue
        passos[int(achou[1])] = achou[2]
        if not re.search(r"\bdeixou\b", linha):
            continue
        ref = re.search(r"cor que você anotou no (\w+) passo", linha)
        alvo = passos.get(_ORDINAIS.get(ref[1], 0), "") if ref else ""
        if not re.search(r"[Aa]note\b.*\bcor\b", alvo):
            erros.append(f"{secao[3:].split(' — ')[0]}: {linha}")
    for nome, corpo in texto.items():
        if not re.search(r"cor automática de cada controle é a do plástico dele.*"
                         r"sem o plástico lido, é a do número", corpo):
            erros.append(f"{nome[3:].split(' — ')[0]}: não diz que a automática é a do plástico")
    assert celulas == 2, f"as duas células da réplica sumiram: {celulas}"
    assert not erros, "\n".join(erros)


def test_os_quatro_jogadores_estao_na_matriz() -> None:
    assert {P2, P3, P4} <= {mac for _m, _n, esperam in MATRIZ for mac in esperam}
