"""Toda escrita de extensão passa pelo teto do tato vivo.

Sprint TODA-ESCRITA-DE-EXTENSAO-PASSA-PELO-TETO-DO-TATO-VIVO-01. A porta não escreve direto: cada
pedido vai à fonte de fora do tato vivo, que divide o mesmo ``Teto`` e deixa sair, em cada canal, o
pedido mais forte, do jogo ou de uma extensão. Tudo por dublê: relógio de mentira, jogo de
mentira e um escritor que só anota.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.core.trigger_effects import bloco_do_efeito, build_from_name
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from hefesto_dualsense4unix.mods.manifesto import permissao_valida
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.mods.porta import (
    CODE_O_JOGO_ESCREVE,
    CODE_SEM_PERMISSAO,
    CODE_SEM_PONTE,
    CODE_TETO_CHEIO,
    EscritorDoServico,
    Porta,
)

P1 = "aa:bb:cc:00:00:71"
EXT_A = tv.PREFIXO_DA_EXTENSAO + "a"
EXT_B = tv.PREFIXO_DA_EXTENSAO + "b"
TODAS = [
    "escrever:luz", "escrever:vibracao", "escrever:gatilho",
    "escrever:haptica", "escrever:som", "escrever:leds",
]
PULSO = {"golpes": [[0, 80, 60, 1.0], [180, 80, 60, 0.7]], "repete": True}


class _Relogio:
    def __init__(self, passo: float = 0.0) -> None:
        self.agora = 0.0
        self.passo = passo

    def __call__(self) -> float:
        valor = self.agora
        self.agora += self.passo
        return valor


class _Jogo:
    def __init__(self) -> None:
        self.forcas: dict[tuple[str, str, str], float] = {}

    def __call__(self, uniq: str, canal: str, vaga: str) -> float:
        return self.forcas.get((uniq, canal, vaga), 0.0)


def _anotar(lista: list[Any], valor: Any) -> bool:
    lista.append(valor)
    return True


def _fonte(
    *,
    modo: str | None = tv.MODO_DUALSENSE,
    jogo: _Jogo | None = None,
    relogio: Callable[[], float] | None = None,
    radio_cede: bool = False,
) -> tuple[tv.FonteDeFora, dict[str, list[Any]]]:
    anotado: dict[str, list[Any]] = {"haptica": [], "motores": [], "som": []}
    fonte = tv.FonteDeFora(
        tv.Teto(),
        modo_de=lambda _u: modo,
        do_jogo=jogo or _Jogo(),
        radio_cede=lambda _u: radio_cede,
        tocar_haptica=lambda u, a, lado: _anotar(anotado["haptica"], (u, len(a), lado)),
        motores=lambda u, fraco, forte: _anotar(anotado["motores"], (u, fraco, forte)),
        tocar_som=lambda u, r: _anotar(anotado["som"], (u, r)),
        relogio=relogio or _Relogio(),
    )
    return fonte, anotado


class _Cliente:
    def __init__(self, caminho: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


Roteiro = Callable[[Callable[..., Any], Porta], Any]


def _pela_porta(
    fonte: tv.FonteDeFora | None, roteiro: Roteiro, *, quem: str = "ext",
    permissoes: list[str] | None = None,
) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    escritas: list[tuple[str, dict[str, Any]]] = []

    async def corrida() -> Any:
        with tempfile.TemporaryDirectory(prefix="pt") as pasta:
            caminho = Path(pasta) / "mods.sock"

            async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
                escritas.append((metodo, pedido))
                return {"status": "ok"}

            porta = Porta(
                caminho, EventBus(), escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                uniq_do_posto=lambda: P1,
                arbitro=(lambda: fonte) if fonte is not None else None,
            )
            await porta.iniciar()
            porta.registrar("ficha", quem, os.getpid(), permissoes or TODAS)
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})

                async def pedir(metodo: str, params: dict[str, Any]) -> dict[str, Any]:
                    return await asyncio.to_thread(cliente.pedir, metodo, params)

                return await roteiro(pedir, porta)
            finally:
                cliente.fechar()
                await porta.parar()

    return asyncio.run(corrida()), escritas


def test_cem_vibracoes_num_segundo_escrevem_no_maximo_o_teto_e_o_resto_e_recusado() -> None:
    fonte, _ = _fonte(relogio=_Relogio(passo=0.0099))

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> list[dict[str, Any]]:
        return [await pedir("vibracao.set", {"uniq": P1, "fraco": 10 + i, "forte": 20 + i})
                for i in range(100)]

    respostas, escritas = _pela_porta(fonte, roteiro)
    vibrando = [e for e in escritas if e[1]["weak"] or e[1]["strong"]]
    assert len(vibrando) == tv.TETO_POR_CONTROLE
    assert escritas[-1] == ("rumble.set", {"uniq": P1, "weak": 0, "strong": 0})
    recusas = [r["error"]["code"] for r in respostas if "error" in r]
    assert recusas == [CODE_TETO_CHEIO] * (100 - tv.TETO_POR_CONTROLE)
    assert all("result" in r for r in respostas[: tv.TETO_POR_CONTROLE])


def test_a_extensao_e_o_tato_vivo_dividem_o_mesmo_teto() -> None:
    motor = tv.TatoVivo()
    for _ in range(tv.TETO_POR_CONTROLE - 1):
        motor.teto.gastar(P1, 0.0)
    assert motor.de_fora.teto is motor.teto
    assert motor.de_fora.pedir(EXT_A, "luz", P1, {"centro": 0.5}, 0.1).vale
    assert motor.de_fora.pedir(EXT_A, "luz", P1, {"centro": 0.6}, 0.2).motivo == "teto"


def test_o_mais_forte_vence_no_motor_e_o_lado_que_a_extensao_nao_venceu_fica_com_o_jogo() -> None:
    jogo = _Jogo()
    jogo.forcas[(P1, "vibracao", "esquerdo")] = 200 / 255
    jogo.forcas[(P1, "vibracao", "direito")] = 50 / 255
    fonte, _ = _fonte(jogo=jogo)

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> list[dict[str, Any]]:
        return [
            await pedir("vibracao.set", {"uniq": P1, "fraco": 0, "forte": 120}),
            await pedir("vibracao.set", {"uniq": P1, "fraco": 0, "forte": 230}),
        ]

    (fraca, forte), escritas = _pela_porta(fonte, roteiro)
    assert fraca["error"]["code"] == CODE_O_JOGO_ESCREVE
    assert fraca["error"]["data"]["vence"] == "jogo"
    assert forte["result"] == {"status": "ok"}
    assert escritas == [("rumble.set", {"uniq": P1, "weak": 50, "strong": 230})]


def test_o_gatilho_de_forca_6_vence_o_de_forca_3_e_o_empate_fica_com_o_que_vale() -> None:
    jogo = _Jogo()
    jogo.forcas[(P1, "gatilho", "direito")] = 3 / 8
    fonte, _ = _fonte(jogo=jogo)

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> list[dict[str, Any]]:
        def gatilho(forca: int) -> dict[str, Any]:
            return {"uniq": P1, "lado": "direito", "modo": "Feedback", "params": [0, forca]}

        return [await pedir("gatilho.set", gatilho(3)), await pedir("gatilho.set", gatilho(6)),
                await pedir("gatilho.set", {**gatilho(6), "modo": "NaoExiste"})]

    (empate, vence, fora), escritas = _pela_porta(fonte, roteiro)
    assert empate["error"]["code"] == CODE_O_JOGO_ESCREVE
    assert vence["result"] == {"status": "ok"}
    assert fora["error"]["code"] == CODE_INVALID_PARAMS
    assert [m for m, _ in escritas] == ["trigger.set"]


@pytest.mark.parametrize(("nome", "params", "forca"), [
    ("Feedback", [0, 6], 6),
    ("Vibration", [0, 6, 30], 6),
    ("Vibration", [0, 6, 0], 0),
    ("Off", [], 0),
])
def test_a_forca_do_bloco_le_o_modo_oficial(nome: str, params: list[int], forca: int) -> None:
    assert tv.forca_do_bloco(bloco_do_efeito(build_from_name(nome, params))) == forca


def test_na_luz_o_brilho_igual_vai_ao_pedido_mais_recente_e_o_mais_fraco_ouve_quem_vence() -> None:
    fonte, _ = _fonte()
    a = fonte.pedir(EXT_A, "luz", P1, {"centro": tv.brilho_da_luz([200, 0, 0])}, 0.0)
    b = fonte.pedir(EXT_B, "luz", P1, {"centro": tv.brilho_da_luz([0, 0, 190])}, 0.1)
    c = fonte.pedir(EXT_B, "luz", P1, {"centro": tv.brilho_da_luz([0, 0, 90])}, 0.2)
    assert a.vale and b.vale
    assert not c.vale and c.vence == EXT_A


def test_sem_jogo_a_luz_e_a_haptica_saem_e_no_modo_nativo_recusam() -> None:
    fonte, anotado = _fonte(modo=tv.MODO_DUALSENSE)
    fonte.registrar(EXT_A, "pulso", tv.padrao_de(PULSO))
    assert fonte.pedir(EXT_A, "luz", P1, {"centro": 0.4}, 0.0).vale
    assert fonte.tocar(EXT_A, P1, "esquerdo", "pulso", 0.8, 120.0, 0.0, 1.0).vale
    assert anotado["haptica"]
    nativo, _ = _fonte(modo=tv.MODO_NATIVO)

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> list[dict[str, Any]]:
        return [await pedir("luz.set", {"uniq": P1, "rgb": [255, 0, 0]}),
                await pedir("vibracao.set", {"uniq": P1, "fraco": 10, "forte": 10})]

    respostas, escritas = _pela_porta(nativo, roteiro)
    assert [r["error"]["code"] for r in respostas] == [CODE_O_JOGO_ESCREVE] * 2
    assert respostas[0]["error"]["data"]["modo"] == "nativo"
    assert escritas == []


def test_o_padrao_com_bpm_gasta_uma_vaga_do_teto_e_toca_ate_o_prazo() -> None:
    fonte, anotado = _fonte()
    fonte.registrar(EXT_A, "pulso", tv.padrao_de(PULSO))
    assert fonte.tocar(EXT_A, P1, "esquerdo", "pulso", 1.0, 140.0, 0.0, 2.0).vale
    for quadro in range(1, 150):
        fonte.andar(quadro / 60)
    assert fonte.contadores["escritas"] == 1
    assert len(fonte.teto._por_uniq[P1]) == 1
    quadros = sum(n for _u, n, _l in anotado["haptica"])
    assert abs(quadros - 2.0 * tv.TAXA_DE_FORA) <= tv.TAXA_DE_FORA * tv.ADIANTE_S
    assert P1 not in {u for u, _l in fonte.toques}


def test_no_radio_sem_ponte_o_padrao_vai_ao_motor_e_o_som_recusa() -> None:
    fonte, anotado = _fonte(radio_cede=True)

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> list[dict[str, Any]]:
        await pedir("haptica.registrar", {"id": "pulso", **PULSO})
        await pedir("som.registrar", {"id": "batida", "golpes": [[0, 120, 90, 0.9]]})
        return [
            await pedir("haptica.tocar", {"uniq": P1, "id": "pulso", "forca": 1.0, "bpm": 100,
                                          "lado": "esquerdo", "ate_ms": 1000}),
            await pedir("som.tocar", {"uniq": P1, "som": "batida", "volume": 0.8}),
        ]

    (haptica, som), _ = _pela_porta(fonte, roteiro)
    assert haptica["result"] == {"status": "ok", "pelo_motor": True}
    assert som["error"]["code"] == CODE_SEM_PONTE
    assert anotado["haptica"] == []
    assert any(forte > 0 for _u, _fraco, forte in anotado["motores"])


def test_o_pedido_com_prazo_que_perde_fica_vivo_e_sai_quando_volta_a_ser_o_mais_forte() -> None:
    jogo = _Jogo()
    jogo.forcas[(P1, "vibracao", "esquerdo")] = 200 / 255
    fonte, _ = _fonte(jogo=jogo)

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> dict[str, Any]:
        coberto = await pedir("vibracao.set", {"uniq": P1, "fraco": 0, "forte": 120,
                                               "ate_ms": 1000})
        jogo.forcas.clear()
        fonte.andar(0.5)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        resposta: dict[str, Any] = coberto
        return resposta

    coberto, escritas = _pela_porta(fonte, roteiro)
    assert coberto["result"] == {"status": "coberto", "vence": "jogo"}
    assert escritas == [("rumble.set", {"uniq": P1, "weak": 0, "strong": 120}),
                        ("rumble.set", {"uniq": P1, "weak": 0, "strong": 0})]


def test_as_luzes_de_jogador_acendem_pela_mascara_e_o_numero_volta_no_fim_do_prazo() -> None:
    fonte, _ = _fonte()

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> dict[str, Any]:
        resposta: dict[str, Any] = await pedir(
            "leds.set", {"uniq": P1, "mascara": 0b00011, "ate_ms": 600, "inicio_ms": 5})
        fonte.andar(0.3)
        fonte.andar(0.7)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return resposta

    resposta, escritas = _pela_porta(fonte, roteiro)
    assert resposta["result"] == {"status": "ok"}
    assert escritas == [
        ("led.player_set", {"uniq": P1, "bits": [True, True, False, False, False]}),
        ("led.player_set", {"uniq": P1, "bits": [False] * 5}),
    ]


def test_o_recorte_do_estalo_do_jogo_volta_ao_alto_falante_pelo_t() -> None:
    fonte, anotado = _fonte()
    recorte = tj.recorte_pronto(b"\x01\x00" * 960, 4.0)
    fonte.guardar_o_estalo(tj.Transiente(4.0, tj.LADO_CENTRO, 0.5, recorte=recorte))
    assert fonte.som(EXT_A, P1, tv.SOM_DO_RECORTE, 0.7, 4.01, t=4.0).vale
    assert anotado["som"] == [(P1, recorte)]
    with pytest.raises(ValueError, match="estalo"):
        fonte.som(EXT_A, P1, tv.SOM_DO_RECORTE, 0.7, 5.0, t=9.0)


def test_os_canais_novos_pedem_permissao_propria() -> None:
    for permissao in ("escrever:haptica", "escrever:som", "escrever:leds"):
        assert permissao_valida(permissao)

    async def roteiro(pedir: Callable[..., Any], _porta: Porta) -> list[dict[str, Any]]:
        return [await pedir("haptica.registrar", {"id": "pulso", **PULSO}),
                await pedir("leds.set", {"uniq": P1, "mascara": 1, "ate_ms": 100})]

    respostas, _ = _pela_porta(_fonte()[0], roteiro, permissoes=["escrever:luz"])
    assert [r["error"]["code"] for r in respostas] == [CODE_SEM_PERMISSAO] * 2


def test_o_escritor_do_servico_entrega_a_fonte_de_fora_do_motor_vivo() -> None:
    class _Daemon:
        pass

    daemon = _Daemon()
    escritor = EscritorDoServico(daemon)
    assert escritor.arbitro() is None
    motor = tv.TatoVivo()
    daemon._tato_vivo = motor  # type: ignore[attr-defined]
    assert escritor.arbitro() is motor.de_fora


@pytest.mark.parametrize("tocando", [True, False])
def test_no_cabo_com_a_haptica_tocando_o_motor_da_extensao_vira_pcm(tocando: bool) -> None:
    levados: list[Any] = []
    motores: list[Any] = []

    class _Falante:
        def a_vibracao_vai_pelo_audio_em(self, uniq: str) -> bool:
            return tocando

        def levar_o_rumble(self, uniq: str, fraco: int, forte: int) -> bool:
            levados.append((uniq, fraco, forte))
            return tocando

    class _Controle:
        def set_rumble_for(self, uniq: str, fraco: int, forte: int) -> bool:
            motores.append((uniq, fraco, forte))
            return True

    class _Daemon:
        _alto_falante_subsystem = _Falante()
        controller = _Controle()

    fonte = tv.ligar_a_fonte_de_fora(_Daemon(), _fonte()[0])
    assert fonte.motores is not None
    assert fonte.motores("aa:bb:cc:00:00:01", 50, 230) is True
    if tocando:
        assert levados == [("aa:bb:cc:00:00:01", 50, 230)]
        assert motores == []
    else:
        assert levados == [("aa:bb:cc:00:00:01", 0, 0)]
        assert motores == [("aa:bb:cc:00:00:01", 50, 230)]
