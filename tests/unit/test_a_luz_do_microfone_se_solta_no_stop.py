"""A luz do microfone se solta no stop, o medidor não trava o laço e o grafo não é relido à toa.

A-LUZ-DO-MICROFONE-SE-SOLTA-NO-STOP-E-O-SOM-NAO-ESPERA-A-TOA-01. Três curas, três mordidas:

* a soltura do desligamento não tem ponto de suspensão: cancelar o laço duas vezes durante o
  `finally` deixa a posse de TODO controle solta (mordida: o `asyncio.sleep` da espera de volta);
* o `parar()` do fluxo de um canal roda DEPOIS de soltar a trava do medidor: `captando()` e
  `picos()` de outro fio respondem na hora enquanto um `parec` demora a morrer (mordida: o
  `parar()` de volta dentro da trava);
* o completar do `pactl` lembra, pela identidade de cada nó, o que o grafo devolveu e o que ele
  não tem: duas releituras com os mesmos nulos leem o grafo uma vez (mordida: o completar sem
  memória).

O cenário de quatro controles (dois no mesmo adaptador, um passando do rádio ao cabo no meio e de
volta) está em cada parte onde há estado por controle. Servidor de som, grafo, `parec` e backend de
mentira.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import threading
import time
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as mod
from hefesto_dualsense4unix.integrations import nivel_do_microfone as nivel
from hefesto_dualsense4unix.integrations import porta_do_som as ps

A = "aabbcc0000a1"
B = "aabbcc0000a2"
C = "aabbcc0000a3"
D = "aabbcc0000a4"
OS_QUATRO = (A, B, C, D)
NO_MESMO_ADAPTADOR = (A, B)


class _Controle:
    """Backend de mentira com as portas que o laço toca e o transporte de cada controle."""

    def __init__(self, mudo: dict[str, bool]) -> None:
        self.uniqs = list(mudo)
        self.mudo = dict(mudo)
        self.transportes = dict.fromkeys(mudo, "bt")
        self.escritas: list[tuple[str | None, int | None]] = []
        self.voltas = 0

    def set_microphone_led(self, aceso: bool | int | None, *, uniq: str | None = None) -> bool:
        self.escritas.append((uniq, aceso))
        return True

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        return None

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        valor = self.mudo.get(uniq if uniq is not None else "")
        if valor is None:
            return None
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": valor}

    def describe_controllers(self) -> list[dict[str, object]]:
        self.voltas += 1
        return [
            {
                "index": i,
                "connected": True,
                "transport": self.transportes[u],
                "is_primary": i == 0,
                "uniq": u,
                "battery_pct": 90,
            }
            for i, u in enumerate(self.uniqs)
        ]


class _Daemon:
    def __init__(self, controller: _Controle) -> None:
        self.bus = EventBus()
        self.controller = controller
        self._tasks: list[asyncio.Task[Any]] = []

    def _is_stopping(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


@pytest.fixture
def _ensaio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "INTERVALO_S", 0.001)
    monkeypatch.setattr(mod, "INTERVALO_DE_QUEM_OUVE_S", 0.0)
    monkeypatch.setattr(mod, "SEM_RESPOSTA_ATE_SOLTAR_S", 60.0)
    monkeypatch.setattr(mod, "_fontes_para", lambda _uniqs, _mesa: {})
    for caminho in (mod.MODULO_DE_QUEM_OUVE, mod.MODULO_DO_NIVEL):
        monkeypatch.setitem(sys.modules, caminho, types.ModuleType(caminho))


async def _esperar(condicao: Any, prazo_s: float = 5.0) -> None:
    limite = time.monotonic() + prazo_s
    while not condicao():
        assert time.monotonic() < limite, "a condição do ensaio não veio no prazo"
        await asyncio.sleep(0.002)


def _soltos(controle: _Controle) -> set[str]:
    return {u for u, v in controle.escritas if v is None and u is not None}


@pytest.mark.asyncio
async def test_cancelar_duas_vezes_durante_o_finally_deixa_a_posse_de_todo_controle_solta(
    _ensaio: None,
) -> None:
    """Quatro controles com a posse; o desligamento recancela o laço no meio do `finally`.

    O desligamento cancela a tarefa de novo a cada 0,5 s até a queda: o segundo cancelamento
    chegava durante a espera da soltura e o controle voltava ao kernel com o nosso desenho da luz.
    """
    controle = _Controle({A: True, B: False, C: False, D: True})
    tarefa = asyncio.create_task(mod.luz_do_mic_loop(_Daemon(controle)))
    await _esperar(lambda: {u for u, v in controle.escritas if v is not None} == set(OS_QUATRO))

    tarefa.cancel()
    await asyncio.sleep(0)
    tarefa.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await tarefa

    assert _soltos(controle) == set(OS_QUATRO), (
        f"a posse ficou retida depois do segundo cancelamento: soltos {sorted(_soltos(controle))}"
    )
    assert sorted(controle.escritas[-4:]) == sorted((u, None) for u in OS_QUATRO)


@pytest.mark.asyncio
async def test_a_troca_de_transporte_no_meio_nao_solta_nem_retoma_e_o_stop_solta_os_quatro(
    _ensaio: None,
) -> None:
    """Quatro no rádio (A e B no mesmo adaptador); D passa ao cabo e volta; cada um com a sua luz.

    A troca não é chegada nem saída: nenhuma soltura nem escrita nova de nenhum dos quatro; a luz
    de cada um segue a dele (A e D mudos apagam, B e C acesos), e só o stop devolve a posse.
    """
    controle = _Controle({A: True, B: False, C: False, D: True})
    tarefa = asyncio.create_task(mod.luz_do_mic_loop(_Daemon(controle)))
    await _esperar(lambda: {u for u, v in controle.escritas if v is not None} == set(OS_QUATRO))
    antes = list(controle.escritas)

    for transporte in ("usb", "bt"):
        controle.transportes[D] = transporte
        marca = controle.voltas
        await _esperar(lambda marca=marca: controle.voltas >= marca + 30)
        assert controle.escritas == antes, (
            f"a troca de D para {transporte} mexeu na luz: {controle.escritas[len(antes):]}"
        )
    assert dict(controle.escritas) == {A: mod.APAGADA, B: mod.ACESA, C: mod.ACESA, D: mod.APAGADA}
    assert _soltos(controle) == set()

    tarefa.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await tarefa
    assert _soltos(controle) == set(OS_QUATRO)


class _Fluxo:
    """Um `parec` de mentira: um fio de verdade para o seletor e um `parar()` que demora."""

    def __init__(self, demora_s: float = 0.0) -> None:
        self._leitura, self._escrita = os.pipe()
        self.demora_s = demora_s
        self.parou = 0

    @property
    def fd(self) -> int:
        return self._leitura

    def vivo(self) -> bool:
        return True

    def parar(self) -> None:
        self.parou += 1
        time.sleep(self.demora_s)
        for ponta in (self._leitura, self._escrita):
            with contextlib.suppress(OSError):
                os.close(ponta)


def test_o_medidor_responde_enquanto_um_parec_demora_a_morrer_e_os_outros_seguem_abertos() -> None:
    """D passa do rádio ao cabo (a fonte muda): o `parar()` do fluxo velho dura 1 s, fora da trava.

    O laço do serviço pergunta `captando` e `picos` a 4 Hz: nenhuma das duas espera o `parec`.
    """
    abertos: dict[tuple[str, str], _Fluxo] = {}

    def abrir(fonte: str, uniq: str) -> _Fluxo:
        fluxo = _Fluxo(demora_s=1.0 if (uniq, fonte) == (D, "fonte-do-radio") else 0.0)
        abertos[(uniq, fonte)] = fluxo
        return fluxo

    medidor = nivel.NivelDoMicrofone(abrir=abrir, automatico=False)
    fontes = {A: "fonte-a", B: "fonte-b", C: "fonte-c", D: "fonte-do-radio"}
    medidor.seguir(fontes)
    medidor.bombear(timeout_s=0.0)
    assert set(abertos) == {(u, f) for u, f in fontes.items()}

    medidor.seguir({**fontes, D: "fonte-do-cabo"})
    volta = threading.Thread(target=lambda: medidor.bombear(timeout_s=0.0))
    volta.start()
    try:
        time.sleep(0.15)
        assert volta.is_alive(), "o ensaio não prendeu o `parar()`: nada a medir"
        for pergunta in (medidor.captando, medidor.picos):
            inicio = time.monotonic()
            pergunta()
            espera = time.monotonic() - inicio
            assert espera < 0.05, (
                f"`{pergunta.__name__}` esperou {espera:.3f} s: a trava do medidor segura o "
                "`parar()` do fluxo que está morrendo"
            )
    finally:
        volta.join()

    assert abertos[(D, "fonte-do-radio")].parou == 1
    assert (D, "fonte-do-cabo") in abertos
    for uniq in (A, B, C):
        assert abertos[(uniq, fontes[uniq])].parou == 0, "o vizinho de D foi fechado junto"
    medidor.parar()
    assert all(f.parou == 1 for f in abertos.values())


def _nulo(texto: str) -> str:
    return texto if texto.isascii() else ps.NULO_DO_PACTL


def _fluxo_do_pactl(indice: int, nome: str) -> dict[str, Any]:
    """Um `source-output` na forma do `pactl` 16.1: o nome com acento chega `(null)`."""
    return {
        "index": indice, "source": 40, "client": "718", "corked": False, "mute": False,
        "properties": {
            "application.name": _nulo(nome), "node.name": _nulo(nome),
            "object.id": str(indice + 100), "object.serial": str(indice),
        },
    }


def _no_do_grafo(indice: int, nome: str) -> dict[str, Any]:
    return {"id": indice + 100, "type": "PipeWire:Interface:Node",
            "info": {"props": {"node.name": nome, "application.name": nome,
                               "object.serial": indice}}}


class _Grafo:
    """O `pw-dump` de mentira, que conta quantas vezes foi lido."""

    def __init__(self, nos: list[dict[str, Any]]) -> None:
        self.nos = nos
        self.lidas = 0

    def __call__(self) -> str | None:
        self.lidas += 1
        return json.dumps(self.nos, ensure_ascii=False)


JOGOS = {1: "Sackboy™", 2: "Ratchet & Clank®", 3: "Pokémon", 4: "ゼルダ"}


def _lista(fluxos: dict[int, str]) -> str:
    return json.dumps([_fluxo_do_pactl(i, n) for i, n in fluxos.items()])


def _nome_de_cada(texto: str | None) -> dict[int, str]:
    objetos = ps.lista_do_json(texto) or []
    return {int(o["index"]): o["properties"]["node.name"] for o in objetos}


def test_duas_releituras_com_os_mesmos_nulos_leem_o_grafo_uma_vez() -> None:
    grafo = _Grafo([_no_do_grafo(i, n) for i, n in JOGOS.items()])
    pactl = _lista(JOGOS)

    primeira = ps.completar_o_json(pactl, grafo)
    segunda = ps.completar_o_json(pactl, grafo)
    terceira = ps.completar_o_json(pactl, grafo)

    assert grafo.lidas == 1, f"o grafo foi lido {grafo.lidas} vezes para os mesmos nulos"
    assert _nome_de_cada(primeira) == _nome_de_cada(segunda) == _nome_de_cada(terceira) == JOGOS


def test_o_que_o_grafo_nao_tem_segue_nulo_e_nao_o_pede_de_novo() -> None:
    grafo = _Grafo([_no_do_grafo(1, JOGOS[1])])
    pactl = _lista({1: JOGOS[1], 2: JOGOS[2]})

    primeira = ps.completar_o_json(pactl, grafo)
    ps.completar_o_json(pactl, grafo)

    assert grafo.lidas == 1
    nomes = _nome_de_cada(primeira)
    assert nomes[1] == JOGOS[1]
    assert nomes[2] == ps.NULO_DO_PACTL, "o nó que o grafo não tem não ganha nome inventado"


def test_quatro_controles_o_que_passa_ao_cabo_ganha_um_no_novo_e_so_ele_pede_o_grafo() -> None:
    """Os quatro jogos nomeados; D troca de stream (rádio para cabo e de volta) no meio.

    A troca cria um stream com serial novo: UMA leitura a mais por troca, nunca uma por
    releitura, e os três vizinhos seguem com o nome sem reler.
    """
    grafo = _Grafo([_no_do_grafo(i, n) for i, n in JOGOS.items()])
    mesa = dict(JOGOS)
    ps.completar_o_json(_lista(mesa), grafo)
    assert grafo.lidas == 1

    serial_de_d = 4
    for serial_novo in (14, 24):
        del mesa[serial_de_d]
        mesa[serial_novo] = JOGOS[4]
        serial_de_d = serial_novo
        grafo.nos.append(_no_do_grafo(serial_novo, JOGOS[4]))
        antes = grafo.lidas
        feito = ps.completar_o_json(_lista(mesa), grafo)
        ps.completar_o_json(_lista(mesa), grafo)
        assert grafo.lidas == antes + 1, "a troca de D pediu o grafo mais (ou menos) de uma vez"
        assert _nome_de_cada(feito) == mesa


def test_o_no_que_sai_da_lista_e_esquecido_e_o_que_volta_se_le_de_novo() -> None:
    grafo = _Grafo([_no_do_grafo(1, JOGOS[1]), _no_do_grafo(3, JOGOS[3])])
    ps.completar_o_json(_lista({1: JOGOS[1]}), grafo)
    ps.completar_o_json(_lista({1: JOGOS[1]}), grafo)
    assert grafo.lidas == 1

    ps.completar_o_json(_lista({3: JOGOS[3]}), grafo)
    assert grafo.lidas == 2, "um nó novo com nulo tem de ler o grafo"

    grafo.nos[:] = [_no_do_grafo(1, "outro nome™")]
    refeito = ps.completar_o_json(_lista({1: "outro nome™"}), grafo)
    assert grafo.lidas == 3, "o nó 1 saiu da lista e ficou na memória"
    assert _nome_de_cada(refeito)[1] == "outro nome™"


def test_cada_leitor_do_grafo_tem_a_sua_memoria() -> None:
    um, outro = _Grafo([_no_do_grafo(1, JOGOS[1])]), _Grafo([_no_do_grafo(1, "Outro™")])
    pactl = _lista({1: JOGOS[1]})

    assert _nome_de_cada(ps.completar_o_json(pactl, um)) == {1: JOGOS[1]}
    assert _nome_de_cada(ps.completar_o_json(pactl, outro)) == {1: "Outro™"}
    assert (um.lidas, outro.lidas) == (1, 1)
