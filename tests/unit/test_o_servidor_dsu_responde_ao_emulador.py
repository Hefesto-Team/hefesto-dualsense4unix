"""O servidor DSU responde ao emulador do jeito que o Azahar espera (E4).

Socket UDP de verdade na porta 0 (efêmera): NUNCA a 26760, que é do daemon
dela. O hub e a tabela de slots são dublês, e os dublês RECUSAM: o servidor só
pode chamar ``amostra_do_dsu`` e ``segurar_o_dedo``. Os pedidos são montados
aqui com ``struct`` e ``zlib``, sem o codec do produto: duas pontas
independentes.

O hub de carimbo que anda, com 1 g de aceleração, é o mesmo contra o qual o
ensaio ``o_dsu_chega_ao_emulador.py`` roda.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import socket
import struct
import subprocess
import sys
import threading
import time
import zlib
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.evdev_reader import PontoDeToque
from hefesto_dualsense4unix.core.virtual_motion import RegistroDeSensores
from hefesto_dualsense4unix.daemon.servidor_dsu import ServidorDsu, SlotDsu
from hefesto_dualsense4unix.daemon.sensor_hub import AmostraDoDsu
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

UNIQ_1 = "aa:bb:cc:00:00:01"
UNIQ_3 = "aa:bb:cc:00:00:03"
ID_DO_AZAHAR = 24872


# -- os pedidos, montados sem o codec do produto -------------------------------


def _pedido(
    tipo: int, corpo: bytes, *, client_id: int = ID_DO_AZAHAR, crc_ruim: bool = False
) -> bytes:
    pacote = bytearray(b"DSUC")
    pacote += struct.pack("<HHII", 1001, 4 + len(corpo), 0, client_id)
    pacote += struct.pack("<I", tipo) + corpo
    crc = zlib.crc32(bytes(pacote)) & 0xFFFFFFFF
    struct.pack_into("<I", pacote, 8, crc ^ 1 if crc_ruim else crc)
    return bytes(pacote)


def _pede_versao() -> bytes:
    return _pedido(0x100000, b"")


def _pede_portas(*slots: int) -> bytes:
    return _pedido(0x100001, struct.pack("<i", len(slots)) + bytes(slots))


def _pede_dados(slot: int | None = None, mac: bytes | None = None, **kw: Any) -> bytes:
    flags = (1 if slot is not None else 0) | (2 if mac is not None else 0)
    corpo = bytes([flags, slot or 0]) + (mac or bytes(6))
    return _pedido(0x100002, corpo, **kw)


# -- as respostas ------------------------------------------------------------------


def _dados(pacote: bytes) -> SimpleNamespace:
    assert len(pacote) == 100, len(pacote)
    assert pacote[:4] == b"DSUS"
    assert struct.unpack_from("<I", pacote, 16)[0] == 0x100002
    zerado = bytearray(pacote)
    zerado[8:12] = bytes(4)
    assert zlib.crc32(bytes(zerado)) & 0xFFFFFFFF == struct.unpack_from("<I", pacote, 8)[0]

    def toque(base: int) -> tuple[int, int, int, int]:
        return (pacote[base], pacote[base + 1], *struct.unpack_from("<HH", pacote, base + 2))

    return SimpleNamespace(
        slot=pacote[20],
        estado=pacote[21],
        modelo=pacote[22],
        conexao=pacote[23],
        mac=":".join(f"{b:02x}" for b in pacote[24:30]),
        conectado=pacote[31],
        contador=struct.unpack_from("<I", pacote, 32)[0],
        toque1=toque(56),
        toque2=toque(62),
        timestamp=struct.unpack_from("<Q", pacote, 68)[0],
        aceleracao=struct.unpack_from("<fff", pacote, 76),
        giro=struct.unpack_from("<fff", pacote, 88),
    )


def _cliente() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(0.05)
    return sock


def _juntar(sock: socket.socket, segundos: float) -> list[bytes]:
    """Tudo o que chega ao socket durante a janela."""
    fim = time.monotonic() + segundos
    achados: list[bytes] = []
    while time.monotonic() < fim:
        with contextlib.suppress(TimeoutError):
            achados.append(sock.recvfrom(2048)[0])
    return achados


def _ate(
    sock: socket.socket,
    pronto: Callable[[SimpleNamespace], bool],
    *,
    limite: float = 4.0,
    ao_ler: Callable[[SimpleNamespace], None] | None = None,
) -> SimpleNamespace:
    """Lê pacotes de dados até um satisfazer a condição; reprova no limite."""
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        try:
            pacote = sock.recvfrom(2048)[0]
        except TimeoutError:
            continue
        lido = _dados(pacote)
        if ao_ler is not None:
            ao_ler(lido)
        if pronto(lido):
            return lido
    raise AssertionError("o pacote esperado não chegou no prazo")


# -- os dublês que recusam -----------------------------------------------------------


class _Hub:
    """Só atende ``amostra_do_dsu`` e ``segurar_o_dedo``; qualquer outra coisa é anotada."""

    def __init__(self) -> None:
        self.fontes: dict[str, Callable[[], AmostraDoDsu | None]] = {}
        self.segurados: list[str] = []
        self.recusadas: list[str] = []

    def amostra_do_dsu(self, uniq: str) -> AmostraDoDsu | None:
        fonte = self.fontes.get(uniq)
        return fonte() if fonte is not None else None

    def segurar_o_dedo(self, uniq: str) -> None:
        self.segurados.append(uniq)

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith("__"):
            raise AttributeError(nome)
        self.recusadas.append(nome)
        raise AttributeError(f"o servidor DSU não pode chamar hub.{nome}")


def _andando(
    *,
    toques: tuple[PontoDeToque, ...] = (),
    epoca: int = 1,
    base_us: int = 1_000_000,
    passo_us: int = 4000,
    aceleracao: tuple[float, float, float] = (0.0, 0.0, 1.0),
    giro: tuple[float, float, float] = (10.0, 20.0, 30.0),
) -> Callable[[], AmostraDoDsu]:
    """Uma fonte cujo carimbo anda a cada pergunta, com 1 g parado."""
    n = itertools.count()

    def fonte() -> AmostraDoDsu:
        return AmostraDoDsu(
            giro=giro,
            aceleracao=aceleracao,
            carimbo_us=base_us + next(n) * passo_us,
            epoca=epoca,
            toques=toques,
            com_movimento=True,
            com_toque=True,
        )

    return fonte


def _dedo(slot: int, identidade: int, x: int = 700, y: int = 500) -> PontoDeToque:
    return PontoDeToque(slot=slot, x=x, y=y, identidade=identidade)


class _Relogio:
    """O relógio monotônico mais um deslocamento que o teste pode empurrar."""

    def __init__(self, deslocamento: float = 0.0) -> None:
        self.deslocamento = deslocamento

    def __call__(self) -> float:
        return time.monotonic() + self.deslocamento


def _slot(uniq: str, jogador: int) -> SlotDsu:
    return SlotDsu(uniq=uniq, mac=vpad_mac(uniq, jogador))


@pytest.fixture
def montar() -> Iterator[Callable[..., SimpleNamespace]]:
    """Fábrica de servidores na porta 0, todos parados no fim."""
    servidores: list[ServidorDsu] = []
    clientes: list[socket.socket] = []

    def fazer(
        tabela: dict[int, SlotDsu] | None = None,
        *,
        fontes: dict[str, Callable[[], AmostraDoDsu | None]] | None = None,
        **kw: Any,
    ) -> SimpleNamespace:
        store = StateStore()
        registro = kw.pop("registro", RegistroDeSensores())
        servidor = ServidorDsu(porta=0, store=store, registro=registro, **kw)
        hub = _Hub()
        hub.fontes.update(fontes or {})
        servidor.publicar(tabela if tabela is not None else {0: _slot(UNIQ_1, 1)}, hub)
        servidor.iniciar()
        servidores.append(servidor)

        def novo_cliente() -> socket.socket:
            sock = _cliente()
            clientes.append(sock)
            return sock

        def envia(sock: socket.socket, pacote: bytes) -> None:
            sock.sendto(pacote, ("127.0.0.1", servidor.porta))

        return SimpleNamespace(
            servidor=servidor,
            hub=hub,
            store=store,
            registro=registro,
            cliente=novo_cliente,
            envia=envia,
        )

    yield fazer
    for servidor in servidores:
        servidor.parar()
    for sock in clientes:
        sock.close()


# -- 1 · a versão -------------------------------------------------------------------


def test_1_a_versao_responde_1001(montar: Callable[..., SimpleNamespace]) -> None:
    mundo = montar()
    sock = mundo.cliente()
    mundo.envia(sock, _pede_versao())
    resposta = _juntar(sock, 0.5)[0]
    assert len(resposta) == 22 and resposta[:4] == b"DSUS"
    assert struct.unpack_from("<H", resposta, 4)[0] == 1001
    assert struct.unpack_from("<I", resposta, 16)[0] == 0x100000
    assert struct.unpack_from("<H", resposta, 20)[0] == 1001
    assert mundo.hub.recusadas == []


# -- 2 · as portas ------------------------------------------------------------------


def test_2_portas_zero_e_tres_com_um_controle_no_primeiro(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar()
    sock = mundo.cliente()
    mundo.envia(sock, _pede_portas(0, 3))
    respostas = _juntar(sock, 0.5)
    assert [len(r) for r in respostas] == [32, 32]
    ocupada, vazia = respostas
    assert struct.unpack_from("<I", ocupada, 16)[0] == 0x100001
    assert tuple(ocupada[20:24]) == (0, 2, 2, 1)  # slot, conectado, modelo 2, conexão 1
    assert ocupada[24:26] == bytes([0x02, 0xFE])
    assert tuple(vazia[20:24]) == (3, 0, 0, 0)
    assert vazia[24:31] == bytes(7)


# -- 3 · o cliente só recebe o slot que pediu -----------------------------------------


def test_3_a_inscricao_no_slot_zero_nao_recebe_o_slot_dois(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(
        {0: _slot(UNIQ_1, 1), 2: _slot(UNIQ_3, 3)},
        fontes={UNIQ_1: _andando(), UNIQ_3: _andando()},
    )
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    pacotes = [_dados(p) for p in _juntar(sock, 0.6)]
    assert len(pacotes) >= 5
    assert {p.slot for p in pacotes} == {0}
    contadores = [p.contador for p in pacotes]
    assert all(b > a for a, b in itertools.pairwise(contadores))
    assert set(mundo.hub.segurados) == {UNIQ_1}
    assert mundo.hub.recusadas == []


def test_3b_a_inscricao_pelo_mac_so_recebe_o_slot_daquele_mac(
    montar: Callable[..., SimpleNamespace],
) -> None:
    tabela = {0: _slot(UNIQ_1, 1), 2: _slot(UNIQ_3, 3)}
    mundo = montar(tabela, fontes={UNIQ_1: _andando(), UNIQ_3: _andando()})
    sock = mundo.cliente()
    mac_do_dois = bytes(int(b, 16) for b in tabela[2].mac.split(":"))
    mundo.envia(sock, _pede_dados(mac=mac_do_dois))
    assert {_dados(p).slot for p in _juntar(sock, 0.4)} == {2}


# -- 4 · o cliente é o endereço, não o id --------------------------------------------


def test_4_dois_clientes_com_o_mesmo_id_recebem_os_dois(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando()})
    um, outro = mundo.cliente(), mundo.cliente()
    assert um.getsockname()[1] != outro.getsockname()[1]
    mundo.envia(um, _pede_dados(slot=0, client_id=ID_DO_AZAHAR))
    mundo.envia(outro, _pede_dados(slot=0, client_id=ID_DO_AZAHAR))
    time.sleep(0.2)
    assert len(_juntar(um, 0.4)) >= 3
    assert len(_juntar(outro, 0.4)) >= 3


# -- 5 · cinco segundos sem renovar ----------------------------------------------------


def test_5_sem_renovar_o_envio_para_e_o_ultimo_pacote_e_o_neutro(
    montar: Callable[..., SimpleNamespace],
) -> None:
    relogio = _Relogio()
    mundo = montar(
        fontes={UNIQ_1: _andando(toques=(_dedo(0, 5),), aceleracao=(0.0, 0.0, 1.0))},
        relogio=relogio,
    )
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    vivos = _juntar(sock, 0.4)
    assert len(vivos) >= 3 and _dados(vivos[-1]).aceleracao[2] != 0
    relogio.deslocamento += 6.0
    depois = [_dados(p) for p in _juntar(sock, 0.6)]
    assert depois, "o pacote neutro de despedida não chegou"
    ultimo = depois[-1]
    assert ultimo.aceleracao == (0.0, 0.0, 0.0) and ultimo.giro == (0.0, 0.0, 0.0)
    assert ultimo.toque1[0] == 0 and ultimo.toque2[0] == 0
    assert _juntar(sock, 0.5) == [], "parou de renovar e o servidor continuou mandando"


def test_5b_parar_o_servidor_manda_o_pacote_neutro_antes_de_fechar(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando(toques=(_dedo(0, 5),))})
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    assert len(_juntar(sock, 0.3)) >= 3
    mundo.servidor.parar()
    ultimo = _dados(_juntar(sock, 0.3)[-1])
    assert ultimo.aceleracao == (0.0, 0.0, 0.0)
    assert ultimo.toque1[0] == 0


# -- 6 · os slots seguem os números, sem compactar ----------------------------------------


def test_6_primeiro_e_terceiro_dao_os_slots_zero_e_dois_e_o_um_responde_desconectado(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(
        {0: _slot(UNIQ_1, 1), 2: _slot(UNIQ_3, 3)},
        fontes={UNIQ_1: _andando(), UNIQ_3: _andando()},
    )
    sock = mundo.cliente()
    mundo.envia(sock, _pede_portas(0, 1, 2, 3))
    portas = _juntar(sock, 0.4)
    assert [(p[20], p[21]) for p in portas] == [(0, 2), (1, 0), (2, 2), (3, 0)]
    mundo.envia(sock, _pede_dados())
    assert {_dados(p).slot for p in _juntar(sock, 0.4)} == {0, 2}


# -- 7 · o interruptor dela vale -----------------------------------------------------------


def test_7_giroscopio_desligado_zera_o_giro_e_o_toque_segue(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando(toques=(_dedo(0, 5),))})
    mundo.registro.definir(UNIQ_1, giroscopio=False)
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    pacotes = [_dados(p) for p in _juntar(sock, 0.4)]
    assert pacotes
    assert all(p.giro == (0.0, 0.0, 0.0) for p in pacotes)
    assert all(p.toque1[0] == 1 for p in pacotes)
    assert all(p.aceleracao[2] != 0 for p in pacotes)


def test_7b_a_mira_acesa_zera_o_giro_e_o_toque_segue(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando(toques=(_dedo(0, 5),))})
    mundo.registro.definir_roteados(sem_chip=False, por_peca={UNIQ_1: True})
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    pacotes = [_dados(p) for p in _juntar(sock, 0.4)]
    assert pacotes
    assert all(p.giro == (0.0, 0.0, 0.0) for p in pacotes)
    assert all(p.toque1[0] == 1 for p in pacotes)


def test_7c_acelerometro_desligado_zera_a_aceleracao(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando()})
    mundo.registro.definir(UNIQ_1, acelerometro=False)
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    pacotes = [_dados(p) for p in _juntar(sock, 0.4)]
    assert pacotes and all(p.aceleracao == (0.0, 0.0, 0.0) for p in pacotes)
    assert all(p.giro[0] != 0 for p in pacotes)


def test_7d_os_sinais_do_protocolo(montar: Callable[..., SimpleNamespace]) -> None:
    """Aceleração (-x, -y, -z); giro (x, -y, -z): o que o Azahar espera deste aparelho."""
    mundo = montar(fontes={UNIQ_1: _andando(aceleracao=(0.25, 0.5, 1.0), giro=(10.0, 20.0, 30.0))})
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    lido = _dados(_juntar(sock, 0.3)[-1])
    assert lido.aceleracao == pytest.approx((-0.25, -0.5, -1.0))
    assert lido.giro == pytest.approx((10.0, -20.0, -30.0))


# -- 8 · o toque 1 é o contato mais antigo --------------------------------------------------


def test_8_quando_o_primeiro_dedo_sai_o_toque_um_passa_a_ser_o_segundo(
    montar: Callable[..., SimpleNamespace],
) -> None:
    amostras: dict[str, tuple[PontoDeToque, ...]] = {"toques": (_dedo(1, 5, 100, 100),)}

    def fonte() -> AmostraDoDsu:
        return _andando(toques=amostras["toques"])()

    mundo = montar(fontes={UNIQ_1: fonte})
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    _ate(sock, lambda p: p.toque1[:2] == (1, 5) and p.toque2[0] == 0)
    # O dedo novo cai no slot 0 do kernel e vem primeiro na tupla, mas é o mais NOVO.
    amostras["toques"] = (_dedo(0, 6, 200, 200), _dedo(1, 5, 100, 100))
    dois = _ate(sock, lambda p: p.toque2[0] == 1)
    assert dois.toque1[:2] == (1, 5) and dois.toque2[:2] == (1, 6)
    assert dois.toque1[2:] == (100, 100) and dois.toque2[2:] == (200, 200)
    amostras["toques"] = (_dedo(0, 6, 200, 200),)
    um = _ate(sock, lambda p: p.toque2[0] == 0)
    assert um.toque1[:2] == (1, 6) and um.toque1[2:] == (200, 200)


# -- 9 · o contador ---------------------------------------------------------------------------


def test_9_o_contador_nao_recua_quando_o_servidor_reinicia(
    montar: Callable[..., SimpleNamespace],
) -> None:
    primeiro = montar(fontes={UNIQ_1: _andando()})
    sock = primeiro.cliente()
    primeiro.envia(sock, _pede_dados(slot=0))
    antes = _dados(_juntar(sock, 0.4)[-1]).contador
    primeiro.servidor.parar()
    segundo = montar(fontes={UNIQ_1: _andando()})
    segundo.envia(sock, _pede_dados(slot=0))
    depois = _dados(_juntar(sock, 0.4)[-1]).contador
    assert depois > antes


def test_9b_na_virada_dos_32_bits_nao_ha_struct_error_e_o_cliente_novo_cresce(
    montar: Callable[..., SimpleNamespace],
) -> None:
    virada = 2**32
    relogio = _Relogio(deslocamento=(virada - 50) / 1000.0 - time.monotonic())
    mundo = montar(fontes={UNIQ_1: _andando()}, relogio=relogio)
    velho = mundo.cliente()
    mundo.envia(velho, _pede_dados(slot=0))
    assert len(_juntar(velho, 0.3)) >= 3, "sem pacote na virada dos 32 bits"
    assert relogio() * 1000 > virada + 10
    novo = mundo.cliente()
    mundo.envia(novo, _pede_dados(slot=0))
    contadores = [_dados(p).contador for p in _juntar(novo, 0.4)]
    assert len(contadores) >= 3
    assert all(c < virada for c in contadores)
    assert all(b > a for a, b in itertools.pairwise(contadores))


# -- 10 · o pedido ruim ------------------------------------------------------------------------


def test_10_vinte_e_oito_bytes_com_crc_errado_ficam_sem_resposta(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando()})
    sock = mundo.cliente()
    ruim = _pede_dados(slot=0, crc_ruim=True)
    assert len(ruim) == 28
    mundo.envia(sock, ruim)
    assert _juntar(sock, 0.4) == []
    assert mundo.store.counter("dsu.recusado") == 1
    assert mundo.store.counter("dsu.pacotes") == 0


# -- 11 · o carimbo ----------------------------------------------------------------------------


def test_11_o_carimbo_nao_recua_quando_o_no_reabre_com_carimbo_menor(
    montar: Callable[..., SimpleNamespace],
) -> None:
    corrente: dict[str, Callable[[], AmostraDoDsu]] = {
        "fonte": _andando(epoca=1, base_us=5_000_000_000)
    }
    mundo = montar(fontes={UNIQ_1: lambda: corrente["fonte"]()})
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    carimbos = [_dados(p).timestamp for p in _juntar(sock, 0.3)]
    assert len(carimbos) >= 3
    # O nó reabriu: época nova, carimbo recomeçando perto de zero.
    corrente["fonte"] = _andando(epoca=2, base_us=1_000)
    carimbos += [_dados(p).timestamp for p in _juntar(sock, 0.4)]
    assert len(carimbos) >= 6
    assert all(b > a for a, b in itertools.pairwise(carimbos)), carimbos


# -- 12 · o hub que não responde ---------------------------------------------------------------


def test_12_o_hub_sem_amostra_rende_conectado_e_o_pacote_neutro(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={})
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    pacotes = [_dados(p) for p in _juntar(sock, 0.5)]
    assert len(pacotes) >= 3
    for p in pacotes:
        assert (p.estado, p.conectado) == (2, 1)
        assert p.toque1[0] == 0 and p.toque2[0] == 0
        assert p.aceleracao == (0.0, 0.0, 0.0) and p.giro == (0.0, 0.0, 0.0)
    assert all(b.timestamp > a.timestamp for a, b in itertools.pairwise(pacotes))
    assert mundo.servidor._thread is not None and mundo.servidor._thread.is_alive()


def test_12b_o_hub_que_levanta_excecao_tambem_rende_o_neutro(
    montar: Callable[..., SimpleNamespace],
) -> None:
    def quebra() -> AmostraDoDsu:
        raise RuntimeError("o hub caiu")

    mundo = montar(fontes={UNIQ_1: quebra})
    sock = mundo.cliente()
    mundo.envia(sock, _pede_dados(slot=0))
    pacotes = [_dados(p) for p in _juntar(sock, 0.4)]
    assert len(pacotes) >= 3 and all(p.aceleracao == (0.0, 0.0, 0.0) for p in pacotes)


# -- a porta e o ritmo --------------------------------------------------------------------------


def test_porta_ocupada_levanta_e_conta(montar: Callable[..., SimpleNamespace]) -> None:
    mundo = montar()
    store = StateStore()
    outro = ServidorDsu(porta=mundo.servidor.porta, store=store)
    with pytest.raises(OSError):
        outro.iniciar()
    assert store.counter("dsu.porta_ocupada") == 1


def test_o_ritmo_nunca_passa_de_250_por_segundo_nem_cai_de_10(
    montar: Callable[..., SimpleNamespace],
) -> None:
    rapido = montar(fontes={UNIQ_1: _andando()})
    sock = rapido.cliente()
    rapido.envia(sock, _pede_dados(slot=0))
    assert len(_juntar(sock, 1.0)) <= 270

    parado = montar(fontes={})
    outro = parado.cliente()
    parado.envia(outro, _pede_dados(slot=0))
    assert len(_juntar(outro, 1.0)) >= 8


def test_a_thread_nao_morre_com_lixo_na_porta(montar: Callable[..., SimpleNamespace]) -> None:
    mundo = montar(fontes={UNIQ_1: _andando()})
    sock = mundo.cliente()
    for lixo in (b"", b"x", b"DSUC" + bytes(40), bytes(range(256)) * 4):
        mundo.envia(sock, lixo)
    mundo.envia(sock, _pede_versao())
    assert len(_juntar(sock, 0.4)) == 1
    assert threading.active_count() >= 1


# -- 13 · o ensaio que o confere vivo --------------------------------------------------------


def _ensaio(porta: int, *extra: str) -> subprocess.CompletedProcess[str]:
    raiz = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [
            sys.executable,
            str(raiz / "scripts/ensaios/o_dsu_chega_ao_emulador.py"),
            "--porta",
            str(porta),
            "--segundos",
            "1.5",
            "--json",
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_13_o_ensaio_aprova_o_servidor_do_e4_com_um_g_parado(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando()})
    feito = _ensaio(mundo.servidor.porta, "--sem-dono")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    relato = json.loads(feito.stdout)
    assert relato["ok"] is True and relato["versao"] == 1001
    assert relato["por_segundo"] >= 8 and relato["crc_ruim"] == 0


def test_13b_o_ensaio_reprova_sem_servidor_e_diz_o_degrau(
    montar: Callable[..., SimpleNamespace],
) -> None:
    sem_dono = montar()
    porta = sem_dono.servidor.porta
    sem_dono.servidor.parar()
    feito = _ensaio(porta, "--sem-dono")
    assert feito.returncode == 1
    assert "sem resposta de versão em 2 s" in json.loads(feito.stdout)["falha"]


def test_13c_o_ensaio_reprova_a_porta_que_nao_e_do_daemon(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando()})
    feito = _ensaio(mundo.servidor.porta)
    assert feito.returncode == 1
    assert "de outro processo" in json.loads(feito.stdout)["falha"]


def test_13d_o_ensaio_reprova_a_aceleracao_fora_de_um_g(
    montar: Callable[..., SimpleNamespace],
) -> None:
    mundo = montar(fontes={UNIQ_1: _andando(aceleracao=(0.0, 0.0, 3.0))})
    feito = _ensaio(mundo.servidor.porta, "--sem-dono")
    assert feito.returncode == 1
    assert "aceleração média" in json.loads(feito.stdout)["falha"]
