"""O medidor de ar — AR-MEDIDO-01 (23/09/2026).

O contrato é o do ``varredura_do_radio.py``: «não sei» é diferente de «zero».
Todo ioctl aqui é um DUBLÊ que empacota nos deslocamentos do kernel escritos à
mão (nunca pelo formato do módulo, que seria a régua medida contra ela mesma).
Nada nesta suíte abre socket de Bluetooth.

A MORDIDA, feita em 23/09/2026: arrancar de ``ar_do_adaptador.conferir`` a
guarda do contador parado com enlace vivo faz
``test_contador_congelado_com_conexao_viva_responde_nao_sei`` reprovar com
``entrada_por_s == 0.0`` — o medidor dizendo «ninguém no rádio» sobre um
controle conectado. Devolvida a guarda, md5 conferido.

E DUAS DA CONFERÊNCIA, no mesmo dia: medir o contador de BYTES com o teto de
pacotes faz ``test_o_contador_de_bytes_que_da_a_volta_…`` reprovar com «o
contador recomeçou»; tirar a guarda da lista de conexões ilegível faz
``test_sem_a_lista_de_conexoes_…`` reprovar com ``0.0``.
"""

from __future__ import annotations

import socket
import struct

import pytest

from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar

ADAPTADOR_A = "aa:bb:cc:00:00:01"
ADAPTADOR_B = "aa:bb:cc:00:00:02"
CONTROLE_1 = "aa:bb:cc:00:00:11"
CONTROLE_2 = "aa:bb:cc:00:00:12"


def _bdaddr(endereco: str) -> bytes:
    return bytes(int(p, 16) for p in endereco.split(":"))[::-1]


class KernelDeMentira:
    """Os três ioctls de leitura, com o layout do kernel escrito à mão."""

    def __init__(self) -> None:
        self.adaptadores: dict[int, dict] = {}
        self.falhar: set[int] = set()
        self.pedidos: list[int] = []

    def por(self, hci: int, endereco: str, *, ligado: bool = True) -> dict:
        self.adaptadores[hci] = {
            "endereco": endereco,
            "ligado": ligado,
            "c": dict.fromkeys(
                ("err_rx", "err_tx", "cmd_tx", "evt_rx", "acl_tx", "acl_rx",
                 "sco_tx", "sco_rx", "byte_rx", "byte_tx"), 0),
            "enlaces": [],
        }
        return self.adaptadores[hci]

    def ioctl(self, pedido: int, buf: bytearray) -> None:
        self.pedidos.append(pedido)
        if pedido in self.falhar:
            raise OSError(19, "No such device")
        if pedido == ar.HCIGETDEVLIST:
            hcis = sorted(self.adaptadores)
            struct.pack_into("<H", buf, 0, len(hcis))
            for i, hci in enumerate(hcis):
                struct.pack_into("<HxxI", buf, 4 + 8 * i, hci, 0)
            return
        hci = struct.unpack_from("<H", buf, 0)[0]
        dado = self.adaptadores.get(hci)
        if dado is None:
            raise OSError(19, "No such device")
        if pedido == ar.HCIGETDEVINFO:
            buf[2:10] = f"hci{hci}".encode().ljust(8, b"\0")
            buf[10:16] = _bdaddr(dado["endereco"])
            struct.pack_into("<I", buf, 16, 0x0D if dado["ligado"] else 0x0C)
            struct.pack_into("<HH", buf, 44, 1021, 6)
            c = dado["c"]
            ordem = ("err_rx", "err_tx", "cmd_tx", "evt_rx", "acl_tx", "acl_rx",
                     "sco_tx", "sco_rx", "byte_rx", "byte_tx")
            for i, nome in enumerate(ordem):
                struct.pack_into("<I", buf, 52 + 4 * i, c[nome] % (1 << 32))
            return
        if pedido == ar.HCIGETCONNLIST:
            conexoes = dado["enlaces"]
            struct.pack_into("<H", buf, 2, len(conexoes))
            for i, (handle, endereco, tipo) in enumerate(conexoes):
                base = 4 + 16 * i
                struct.pack_into("<H", buf, base, handle)
                buf[base + 2 : base + 8] = _bdaddr(endereco)
                struct.pack_into("<BBHI", buf, base + 8, tipo, 1, 1, 0x7)
            return
        raise AssertionError(f"pedido de ioctl que um medidor não faz: {pedido:#x}")


class Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


def _medidor(kernel: KernelDeMentira, relogio: Relogio, **kw: float) -> ar.MedidorDeAr:
    return ar.MedidorDeAr(ar.LeitorDoKernel(ioctl=kernel.ioctl, relogio=relogio), **kw)


# ---------------------------------------------------------------- o layout


def test_o_layout_do_kernel_tem_92_bytes_e_cada_campo_no_lugar() -> None:
    assert struct.calcsize(ar.FORMATO_DEV_INFO) == 92
    kernel = KernelDeMentira()
    dado = kernel.por(3, ADAPTADOR_A)
    dado["c"].update(acl_rx=7, acl_tx=11, byte_rx=13, byte_tx=17, err_rx=19, err_tx=23)
    leitura = ar.LeitorDoKernel(ioctl=kernel.ioctl, relogio=Relogio()).ler(3)
    assert leitura is not None
    assert (leitura.hci, leitura.endereco, leitura.ligado) == (3, ADAPTADOR_A, True)
    assert (leitura.acl_mtu, leitura.acl_pkts) == (1021, 6)
    c = leitura.contadores
    assert (c.acl_rx, c.acl_tx, c.byte_rx, c.byte_tx, c.err_rx, c.err_tx) == (
        7, 11, 13, 17, 19, 23)


def test_a_lista_de_conexoes_traz_handle_endereco_papel_e_saida() -> None:
    kernel = KernelDeMentira()
    kernel.por(0, ADAPTADOR_A)["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL)]
    conexoes = ar.LeitorDoKernel(ioctl=kernel.ioctl).conexoes(0)
    assert conexoes is not None and len(conexoes) == 1
    (c,) = conexoes
    assert (c.handle, c.endereco, c.tipo, c.saida, c.mestre) == (
        12, CONTROLE_1, ar.TIPO_ACL, True, True)


def test_o_endereco_sai_na_forma_do_hid_phys() -> None:
    """Minúsculo com dois-pontos — senão não casa com ``adaptador_por_uniq``."""
    assert ar.endereco_do_kernel(_bdaddr("AA:BB:CC:00:00:0F")) == "aa:bb:cc:00:00:0f"


# ---------------------------------------------------------------- as taxas


def test_a_taxa_e_o_delta_do_contador_na_janela() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    dado["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL)]
    medidor = _medidor(kernel, relogio)
    primeira = medidor.amostrar()[ADAPTADOR_A]
    assert not primeira.sei and primeira.motivo == ar.PRIMEIRA_LEITURA
    relogio.agora += 1.0
    dado["c"].update(acl_rx=753, byte_rx=753 * 87, acl_tx=2)
    agora = medidor.amostrar()[ADAPTADOR_A]
    assert agora.sei and agora.motivo == ""
    assert agora.entrada_por_s == 753.0
    assert agora.bytes_entrada_por_s == 753.0 * 87
    assert agora.saida_por_s == 2.0
    assert agora.janela_s == 1.0


def test_o_contador_de_32_bits_que_da_a_volta_continua_sendo_taxa() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    dado["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL)]
    dado["c"]["acl_rx"] = (1 << 32) - 100
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    dado["c"]["acl_rx"] = 650
    assert medidor.amostrar()[ADAPTADOR_A].entrada_por_s == 750.0


def test_o_contador_de_bytes_que_da_a_volta_nao_vira_adaptador_reiniciado() -> None:
    """O de BYTES dá a volta a cada ~17 h com um controle no rádio (~70 kB/s).

    Medido contra o teto de PACOTES, a volta dele virava «o adaptador
    reiniciou» e apagava a janela inteira — conferência de 23/09/2026.
    """
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    dado["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL)]
    dado["c"].update(acl_rx=1_000, byte_rx=(1 << 32) - 30_000)
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    dado["c"].update(acl_rx=1_753, byte_rx=(1 << 32) - 30_000 + 753 * 87)
    resposta = medidor.amostrar()[ADAPTADOR_A]
    assert resposta.motivo == "", resposta.motivo
    assert resposta.entrada_por_s == 753.0
    assert resposta.bytes_entrada_por_s == 753.0 * 87


def test_sem_a_lista_de_conexoes_o_contador_parado_e_nao_sei() -> None:
    """Sem o ``HCIGETCONNLIST`` o parado não separa «ninguém» de «instrumento parado»."""
    kernel, relogio = KernelDeMentira(), Relogio()
    kernel.por(0, ADAPTADOR_A)["c"]["acl_rx"] = 40_000
    kernel.falhar.add(ar.HCIGETCONNLIST)
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    resposta = medidor.amostrar()[ADAPTADOR_A]
    assert resposta.entrada_por_s is None, (
        f"contador parado sem saber das conexões virou número: {resposta.entrada_por_s!r}")
    assert resposta.motivo == ar.CONEXOES_ILEGIVEIS


def test_o_contador_que_zerou_e_nao_sei_e_nunca_uma_volta_inventada() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    dado["c"]["acl_rx"] = 5_000_000
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    dado["c"]["acl_rx"] = 10
    resposta = medidor.amostrar()[ADAPTADOR_A]
    assert not resposta.sei
    assert resposta.motivo == ar.CONTADOR_RECOMECOU
    assert resposta.entrada_por_s is None


def test_contador_congelado_com_conexao_viva_responde_nao_sei() -> None:
    """A MORDIDA da sprint: congelado com enlace de pé NUNCA é «0 Hz»."""
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    dado["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL)]
    dado["c"]["acl_rx"] = 40_000
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    resposta = medidor.amostrar()[ADAPTADOR_A]
    assert resposta.entrada_por_s is None, (
        "contador parado com um controle conectado virou número: "
        f"{resposta.entrada_por_s!r}"
    )
    assert not resposta.sei
    assert resposta.motivo == ar.CONTADOR_PARADO


def test_adaptador_sem_conexao_e_zero_conexoes_e_nao_erro() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    kernel.por(0, ADAPTADOR_A)
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    resposta = medidor.amostrar()[ADAPTADOR_A]
    assert resposta.conexoes == ()
    assert resposta.sei
    assert resposta.entrada_por_s == 0.0


def test_o_ioctl_que_falha_e_nao_sei() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    kernel.por(0, ADAPTADOR_A)
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    kernel.falhar.add(ar.HCIGETDEVINFO)
    relogio.agora += 1.0
    (resposta,) = medidor.amostrar().values()
    assert not resposta.sei and resposta.motivo == ar.IOCTL_FALHOU


def test_o_adaptador_que_some_sai_uma_vez_como_nao_sei() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    kernel.por(0, ADAPTADOR_A)
    kernel.por(1, ADAPTADOR_B)
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    del kernel.adaptadores[1]
    relogio.agora += 1.0
    resposta = medidor.amostrar()
    assert resposta[ADAPTADOR_B].motivo == ar.ADAPTADOR_SUMIU
    assert not resposta[ADAPTADOR_B].sei
    relogio.agora += 1.0
    assert ADAPTADOR_B not in medidor.amostrar()


def test_sem_socket_de_bluetooth_a_resposta_inteira_e_nao_sei() -> None:
    kernel = KernelDeMentira()
    kernel.falhar.add(ar.HCIGETDEVLIST)
    resposta = _medidor(kernel, Relogio()).amostrar()
    assert list(resposta) == [""]
    assert resposta[""].motivo == ar.SEM_BLUETOOTH


def test_o_adaptador_desligado_e_nao_sei() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    kernel.por(0, ADAPTADOR_A, ligado=False)
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    assert medidor.amostrar()[ADAPTADOR_A].motivo == ar.ADAPTADOR_DESLIGADO


def test_entre_duas_janelas_o_medidor_repete_a_ultima_resposta() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    dado["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL)]
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += 1.0
    dado["c"]["acl_rx"] = 800
    fechada = medidor.amostrar()[ADAPTADOR_A]
    relogio.agora += 0.3
    dado["c"]["acl_rx"] = 1_000
    assert medidor.amostrar()[ADAPTADOR_A] == fechada


def test_referencia_velha_recomeca_em_vez_de_publicar_media_velha() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    medidor = _medidor(kernel, relogio)
    medidor.amostrar()
    relogio.agora += ar.JANELA_MAXIMA_S + 1.0
    dado["c"]["acl_rx"] = 999
    assert medidor.amostrar()[ADAPTADOR_A].motivo == ar.PRIMEIRA_LEITURA


def test_a_janela_do_governador_e_um_parametro() -> None:
    kernel, relogio = KernelDeMentira(), Relogio()
    dado = kernel.por(0, ADAPTADOR_A)
    dado["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL)]
    medidor = _medidor(kernel, relogio, janela_s=0.25)
    medidor.amostrar()
    relogio.agora += 0.25
    dado["c"]["acl_rx"] = 200
    assert medidor.amostrar()[ADAPTADOR_A].entrada_por_s == 800.0


# ---------------------------------------------------------------- o AFH

#: O que o rádio da máquina dela respondeu em 23/09/2026 a um handle que não
#: existe (0x0EFE): ``Command Complete`` com status 0x02, conexão desconhecida.
RESPOSTA_MEDIDA_DE_HANDLE_INEXISTENTE = bytes.fromhex("040e0602061402fe0e")


def _resposta_afh(handle: int, evitados: set[int], *, modo: int = 1) -> bytes:
    mapa = bytearray(10)
    for canal in range(ar.CANAIS_DO_BT):
        if canal not in evitados:
            mapa[canal // 8] |= 1 << (canal % 8)
    params = bytes([0x00]) + struct.pack("<H", handle) + bytes([modo]) + bytes(mapa)
    corpo = bytes([0x01]) + struct.pack("<H", 0x1406) + params
    return bytes([0x04, 0x0E, len(corpo)]) + corpo


def test_o_comando_do_afh_e_o_que_o_filtro_do_kernel_deixa_sem_root() -> None:
    """``hci_sec_filter``: ``OGF_STATUS_PARAM`` = ``0x000000ea``, bit do OCF."""
    ogf, ocf = ar.OPCODE_LER_MAPA_AFH >> 10, ar.OPCODE_LER_MAPA_AFH & 0x3FF
    assert (ogf, ocf) == (0x05, 0x0006)
    assert (0x000000EA >> ocf) & 1 == 1


def test_o_mapa_afh_le_os_79_canais_e_os_evitados() -> None:
    evitados = {0, 20, 21, 32, 78}
    mapa = ar.mapa_afh_da_resposta(_resposta_afh(12, evitados), 12)
    assert mapa is not None
    assert len(mapa.canais) == ar.CANAIS_DO_BT
    assert set(mapa.evitados) == evitados
    assert mapa.usados == ar.CANAIS_DO_BT - len(evitados)
    assert mapa.modo == 1


def test_resposta_de_outro_handle_nao_e_a_nossa() -> None:
    assert ar.mapa_afh_da_resposta(_resposta_afh(13, set()), 12) is None


def test_a_resposta_de_erro_medida_na_maquina_dela_e_nao_sei() -> None:
    evento = RESPOSTA_MEDIDA_DE_HANDLE_INEXISTENTE
    assert ar.mapa_afh_da_resposta(evento, 0x0EFE) is None
    assert ar.resposta_de_erro_do_afh(evento) == 0x02


class _SocketDeMentira:
    """Uma ponta de ``socketpair`` vestida de socket HCI."""

    def __init__(self, resposta: bytes | None) -> None:
        self._nosso, self._deles = socket.socketpair()
        self._resposta = resposta
        self.opcoes: list[tuple[int, int, bytes]] = []
        self.enviados: list[bytes] = []

    def fileno(self) -> int:
        return self._nosso.fileno()

    def setsockopt(self, nivel: int, nome: int, valor: bytes) -> None:
        self.opcoes.append((nivel, nome, valor))

    def send(self, dados: bytes) -> int:
        self.enviados.append(bytes(dados))
        if self._resposta is not None:
            self._deles.send(self._resposta)
        return len(dados)

    def recv(self, tamanho: int) -> bytes:
        return self._nosso.recv(tamanho)

    def close(self) -> None:
        self._nosso.close()
        self._deles.close()


def test_ler_mapa_afh_manda_so_o_comando_de_leitura_e_filtra_a_resposta() -> None:
    falso = _SocketDeMentira(_resposta_afh(12, {5}))
    mapa = ar.ler_mapa_afh(0, 12, abrir=lambda _hci: falso)  # type: ignore[arg-type,return-value]
    assert mapa is not None and mapa.evitados == (5,)
    assert falso.enviados == [bytes.fromhex("01061402") + struct.pack("<H", 12)]
    ((nivel, nome, filtro),) = falso.opcoes
    assert (nivel, nome) == (0, 2)
    tipos, eventos, _, opcode = struct.unpack("<IIIH2x", filtro)
    assert tipos == 1 << 4
    assert eventos == (1 << 0x0E) | (1 << 0x0F)
    assert opcode == 0x1406


def test_ler_mapa_afh_sem_resposta_no_prazo_e_nao_sei() -> None:
    falso = _SocketDeMentira(None)
    assert ar.ler_mapa_afh(0, 12, prazo_s=0.05, abrir=lambda _hci: falso) is None  # type: ignore[arg-type,return-value]


def test_ler_mapa_afh_que_nao_abre_o_socket_e_nao_sei() -> None:
    def recusa(_hci: int) -> socket.socket:
        raise PermissionError(1, "Operation not permitted")

    assert ar.ler_mapa_afh(0, 12, abrir=recusa) is None


def test_no_modo_falso_o_afh_nunca_pergunta_ao_radio_de_verdade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O único comando ao controlador tem a trava NELE, não só em quem chama."""
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")

    def recusa(*_a: object, **_k: object) -> None:
        raise AssertionError("a suíte abriu um socket HCI para perguntar ao rádio")

    monkeypatch.setattr(socket, "socket", recusa)
    assert ar.ler_mapa_afh(0, 12) is None


def test_os_canais_que_o_adaptador_evita_sao_os_evitados_em_todos_os_enlaces() -> None:
    um = ar.mapa_afh_da_resposta(_resposta_afh(1, {20, 21, 22}), 1)
    outro = ar.mapa_afh_da_resposta(_resposta_afh(2, {21, 22, 40}), 2)
    assert ar.canais_evitados_pelo_adaptador({CONTROLE_1: um, CONTROLE_2: outro}) == (
        21, 22)
    assert ar.canais_evitados_pelo_adaptador({CONTROLE_1: um, CONTROLE_2: None}) == (
        20, 21, 22)


def test_sem_enlace_o_afh_e_nao_sei() -> None:
    """AFH só existe com conexão: adaptador vazio não «evita zero canais»."""
    assert ar.canais_evitados_pelo_adaptador({}) is None
    assert ar.canais_evitados_pelo_adaptador({CONTROLE_1: None}) is None


def test_os_mapas_do_adaptador_so_perguntam_pelos_enlaces_acl() -> None:
    conexoes = (
        ar.Enlace(12, CONTROLE_1, ar.TIPO_ACL, True, 1, 7),
        ar.Enlace(40, CONTROLE_2, 0x02, True, 1, 7),
    )
    perguntados: list[tuple[int, int]] = []

    def ler(hci: int, handle: int) -> ar.MapaAFH | None:
        perguntados.append((hci, handle))
        return None

    ar_a = ar.ArDoAdaptador(hci=3, endereco=ADAPTADOR_A, conexoes=conexoes)
    assert ar.mapas_afh_do_adaptador(ar_a, ler=ler) == {CONTROLE_1: None}
    assert perguntados == [(3, 12)]


def test_a_suite_nunca_abre_o_socket_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    """O leitor padrão só abre socket na PRIMEIRA chamada — nunca ao nascer."""
    abertos: list[tuple] = []
    monkeypatch.setattr(socket, "socket", lambda *a, **k: abertos.append(a))
    ar.LeitorDoKernel()
    ar.MedidorDeAr()
    assert abertos == []
