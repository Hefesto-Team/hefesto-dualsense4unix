"""O governador do rádio — GOVERNADOR-DO-RADIO-01 (23/09/2026), R2, R3 e R4 dela.

Em 22/09 a terceira ponte num adaptador derrubou os quatro controles da mesa
dela em 11 a 89 segundos. O governador é quem dá a vaga de cada ponte e quem
manda ceder na fonte quando o adaptador não escoa. Esta régua cobra:

1. **O TEMPO REAL:** com o ``acl_tx`` do adaptador preso (o dublê do ioctl) e a
   bomba escrevendo, a bomba cede na primeira janela — em até 250 ms. **A
   mordida:** sem o ramo da vaga na bomba, ela escreve os quadros todos.
2. **«NÃO SEI» NUNCA É ZERO:** ``saida_por_s`` ``None`` não vira déficit.
3. **O TETO:** o escritor que devolve ``EAGAIN`` para sempre derruba a ponte
   em dois segundos, com o motivo certo e o diário dizendo o adaptador; e o
   adaptador que não escoa pelo governador também cai no mesmo teto.
4. **A ADMISSÃO:** a terceira ponte num adaptador com duas volta «cheio, há
   vaga em X» — uma entrada só no diário —, e «Ligar aqui» a sobe marcada.
   Sem vaga em lugar nenhum (R4), ela sobe marcada sozinha.
5. **O DIÁRIO:** ``PONTE_SUBIU``/``PONTE_DESCEU`` com controle, adaptador e
   tipo — sem eles, ``storm_doctor.o_fato_da_queda`` devolve ``None``.
6. **UM DONO:** o limite é o ``N_MAX_PONTES`` do ``radio_da_mesa`` nos três
   leitores, e o ``state_full`` lê a amostra do governador.

Nada aqui abre socket de Bluetooth, lê o sysfs dela ou escreve no diário dela:
o ioctl é um dublê com o layout do kernel escrito à mão, e o diário mora em
``tmp_path``.
"""

from __future__ import annotations

import contextlib
import fcntl
import functools
import os
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import diario_do_radio as diario
from hefesto_dualsense4unix.integrations import radio_da_mesa, storm_doctor

ADAPTADOR_A = "aa:bb:cc:00:00:a1"
ADAPTADOR_B = "aa:bb:cc:00:00:b2"
CONTROLE_1 = "aa:bb:cc:00:00:01"
CONTROLE_2 = "aa:bb:cc:00:00:02"
CONTROLE_3 = "aa:bb:cc:00:00:03"
#: 512 amostras a 48 kHz: um quadro do 0x35.
QUADRO_S = 512 / 48000


# --- o kernel de mentira (o layout escrito à mão, como em test_o_ar_do_adaptador)


def _bdaddr(endereco: str) -> bytes:
    return bytes(int(p, 16) for p in endereco.split(":"))[::-1]


class _Kernel:
    """Os três ioctls de leitura do medidor, com os contadores na mão da régua."""

    def __init__(self) -> None:
        self.adaptadores: dict[int, dict[str, Any]] = {}

    def por(self, hci: int, endereco: str) -> dict[str, Any]:
        self.adaptadores[hci] = {
            "endereco": endereco,
            "c": dict.fromkeys(
                ("err_rx", "err_tx", "cmd_tx", "evt_rx", "acl_tx", "acl_rx",
                 "sco_tx", "sco_rx", "byte_rx", "byte_tx"), 0),
            "enlaces": [(12, CONTROLE_1, ar.TIPO_ACL)],
        }
        return self.adaptadores[hci]

    def ioctl(self, pedido: int, buf: bytearray) -> None:
        if pedido == ar.HCIGETDEVLIST:
            hcis = sorted(self.adaptadores)
            struct.pack_into("<H", buf, 0, len(hcis))
            for i, hci in enumerate(hcis):
                struct.pack_into("<HxxI", buf, 4 + 8 * i, hci, 0)
            return
        hci = struct.unpack_from("<H", buf, 0)[0]
        dado = self.adaptadores[hci]
        if pedido == ar.HCIGETDEVINFO:
            buf[2:10] = f"hci{hci}".encode().ljust(8, b"\0")
            buf[10:16] = _bdaddr(dado["endereco"])
            struct.pack_into("<I", buf, 16, 0x0D)
            struct.pack_into("<HH", buf, 44, 1021, 6)
            ordem = ("err_rx", "err_tx", "cmd_tx", "evt_rx", "acl_tx", "acl_rx",
                     "sco_tx", "sco_rx", "byte_rx", "byte_tx")
            for i, nome in enumerate(ordem):
                struct.pack_into("<I", buf, 52 + 4 * i, dado["c"][nome] % (1 << 32))
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
        raise AssertionError(f"ioctl que um medidor não faz: {pedido:#x}")


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


@dataclass
class _Diario:
    entradas: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, quem: str, o_que: str, por_que: str, **campos: Any) -> None:
        self.entradas.append({"quem": quem, "o_que": o_que, "por_que": por_que, **campos})

    def de(self, o_que: str) -> list[dict[str, Any]]:
        return [e for e in self.entradas if e["o_que"] == o_que]


def _governador(
    kernel: _Kernel | None,
    relogio: _Relogio,
    registro: _Diario,
    *,
    adaptadores: dict[str, str] | None = None,
) -> gov.GovernadorDoRadio:
    medidor = None
    if kernel is not None:
        medidor = ar.MedidorDeAr(
            ar.LeitorDoKernel(ioctl=kernel.ioctl, relogio=relogio), janela_s=gov.PERIODO_S
        )
    onde = adaptadores or {}
    return gov.GovernadorDoRadio(
        medidor=medidor,
        adaptador_de=lambda uniq: onde.get(uniq, ADAPTADOR_A),
        registrar=registro,
        relogio=relogio,
    )


def _bomba(vaga: Any, relogio: _Relogio, escritor: Any = None) -> af.BombaDeSomPeloRadio:
    return af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_035,
        fonte=lambda n: b"\x00" * n,
        escritor=escritor or (lambda report: len(report)),
        seco=False,
        common=af.common_de_audio(),
        vaga=vaga,
        relogio=relogio,
    )


def _uma_janela(bomba: af.BombaDeSomPeloRadio, relogio: _Relogio, dado: dict[str, Any],
                *, tx_por_quadro: int, rx_por_quadro: int = 8) -> list[bool]:
    """250 ms de ponte: um quadro a cada 10,667 ms, e o kernel contando."""
    saidas: list[bool] = []
    fim = relogio.agora + gov.PERIODO_S
    while relogio.agora < fim:
        saidas.append(bomba.escrever(b"\x35" + b"\x00" * 333))
        dado["c"]["acl_tx"] += tx_por_quadro
        dado["c"]["acl_rx"] += rx_por_quadro
        relogio.agora += QUADRO_S
    return saidas


# ---------------------------------------------------------------------------
# 1. o tempo real — o acl_tx preso faz a bomba ceder em até 250 ms
# ---------------------------------------------------------------------------
def test_o_acl_tx_preso_faz_a_bomba_ceder_em_ate_250_ms() -> None:
    """O crédito do controlador parou: a fila do host cresce, e a bomba cede.

    Sem o patch do bluetoothd, o socket de uma ponte enche em ~1,8 s de
    crédito parado e o primeiro EAGAIN derruba o controle (os críticos de
    23/09) — o governador tem de ceder na PRIMEIRA janela.

    MORDIDA: tire da bomba o ramo `if vaga.cedendo:` e ela escreve todos os
    quadros da janela seguinte; o teste reprova com zero cedidos.
    """
    relogio, registro, kernel = _Relogio(), _Diario(), _Kernel()
    dado = kernel.por(0, ADAPTADOR_A)
    governador = _governador(kernel, relogio, registro)
    vaga = governador.pedir_vaga(CONTROLE_1, "som")
    assert isinstance(vaga, gov.Vaga)
    vaga.subiu("som")
    bomba = _bomba(vaga, relogio)
    governador.tique()  # a primeira foto: «não sei», ainda sem taxa

    # Uma janela sã: o adaptador escoa o que a bomba escreve.
    _uma_janela(bomba, relogio, dado, tx_por_quadro=1)
    governador.tique()
    assert vaga.cedendo is False, "o governador cedeu sobre um adaptador que escoa"

    # O crédito para: a bomba escreve, o acl_tx não anda.
    inicio = relogio.agora
    _uma_janela(bomba, relogio, dado, tx_por_quadro=0)
    governador.tique()
    decidiu_em = relogio.agora - inicio
    assert vaga.cedendo is True, "250 ms de escrita sem acl_tx e o governador não cedeu"
    assert decidiu_em <= gov.PERIODO_S + QUADRO_S, decidiu_em

    escritas_antes = bomba.contagem.escritas_aceitas_pelo_kernel
    _uma_janela(bomba, relogio, dado, tx_por_quadro=0)
    assert bomba.contagem.quadros_cedidos_ao_governador >= 20, bomba.contagem
    assert bomba.contagem.escritas_aceitas_pelo_kernel == escritas_antes, (
        "a bomba escreveu com o governador mandando ceder"
    )
    assert [e["adaptador"] for e in registro.de(gov.CEDEU_NA_FONTE)] == [ADAPTADOR_A]


def test_o_adaptador_que_volta_a_escoar_devolve_a_escrita_e_a_borda_sai_uma_vez() -> None:
    relogio, registro, kernel = _Relogio(), _Diario(), _Kernel()
    dado = kernel.por(0, ADAPTADOR_A)
    governador = _governador(kernel, relogio, registro)
    vaga = governador.pedir_vaga(CONTROLE_1, "som")
    assert isinstance(vaga, gov.Vaga)
    vaga.subiu()
    bomba = _bomba(vaga, relogio)
    governador.tique()
    _uma_janela(bomba, relogio, dado, tx_por_quadro=0)
    governador.tique()
    assert vaga.cedendo is True
    # Cedendo, a bomba não escreve; o adaptador escoa a fila que ficou.
    _uma_janela(bomba, relogio, dado, tx_por_quadro=2)
    governador.tique()
    assert vaga.cedendo is False, "o adaptador escoou e as pontes seguiram cedendo"
    assert len(registro.de(gov.CEDEU_NA_FONTE)) == 1
    assert len(registro.de(gov.VOLTOU_A_ESCREVER)) == 1


# ---------------------------------------------------------------------------
# 2. «não sei» nunca é zero
# ---------------------------------------------------------------------------
@dataclass
class _MedidorQueNaoSabe:
    endereco: str = ADAPTADOR_A

    def amostrar(self) -> dict[str, ar.ArDoAdaptador]:
        # Um objeto NOVO por janela, com a taxa de saída «não sei».
        return {
            self.endereco: ar.ArDoAdaptador(
                hci=0, endereco=self.endereco, entrada_por_s=None,
                saida_por_s=None, janela_s=0.25, motivo=ar.CONTADOR_PARADO,
            )
        }


def test_saida_que_nao_se_sabe_nao_vira_deficit() -> None:
    """O contador parado com enlace de pé é «não sei», e não «zero pacotes».

    MORDIDA: em `_medir`, trate `saida_por_s is None` como `0.0` e as 23
    escritas de cada janela viram fila; o governador cede sobre nada.
    """
    relogio, registro = _Relogio(), _Diario()
    governador = gov.GovernadorDoRadio(
        medidor=_MedidorQueNaoSabe(),
        adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=registro,
        relogio=relogio,
    )
    vaga = governador.pedir_vaga(CONTROLE_1, "som")
    assert isinstance(vaga, gov.Vaga)
    vaga.subiu()
    for _ in range(8):
        for _ in range(24):
            vaga.contar_escrita()
        relogio.agora += gov.PERIODO_S
        governador.tique()
    assert vaga.cedendo is False
    assert registro.de(gov.CEDEU_NA_FONTE) == []
    assert governador.publicar()[ADAPTADOR_A]["fila"] is None, "«não sei» publicado como número"


# ---------------------------------------------------------------------------
# 3. o teto — consumidor parado não é congestão
# ---------------------------------------------------------------------------
def test_o_adaptador_que_nao_escoa_cai_no_teto_e_espera_para_religar() -> None:
    """Ceder mais que o teto sobre um adaptador parado derruba a ponte.

    Depois, o adaptador espera `ESPERA_DA_FILA_PARADA_S` — a ponte sob demanda
    religa sozinha na volta seguinte, que é a prova de que ele voltou a drenar.
    """
    relogio, registro, kernel = _Relogio(), _Diario(), _Kernel()
    dado = kernel.por(0, ADAPTADOR_A)
    governador = _governador(kernel, relogio, registro)
    vaga = governador.pedir_vaga(CONTROLE_1, "som")
    assert isinstance(vaga, gov.Vaga)
    vaga.subiu()
    bomba = _bomba(vaga, relogio)
    governador.tique()
    caiu = False
    for _ in range(20):  # cinco segundos de adaptador parado
        saidas = _uma_janela(bomba, relogio, dado, tx_por_quadro=0)
        governador.tique()
        if False in saidas:
            caiu = True
            break
    assert caiu, "o governador cedeu cinco segundos sem derrubar a ponte"
    assert bomba.fila_parada is True
    [parada] = registro.de(gov.FILA_PARADA)
    assert (parada["adaptador"], parada["familia"]) == (ADAPTADOR_A, "2B")
    assert "não drena o adaptador" in parada["por_que"]
    vaga.soltar(af.MOTIVO_FILA_PARADA)
    recusa = governador.pedir_vaga(CONTROLE_1, "som")
    assert isinstance(recusa, gov.Recusa) and recusa.motivo == gov.MOTIVO_PARADO
    relogio.agora += gov.ESPERA_DA_FILA_PARADA_S + 0.1
    assert isinstance(governador.pedir_vaga(CONTROLE_1, "som"), gov.Vaga)


def _cano_que_enche() -> tuple[int, int]:
    """Um hidraw de mentira cuja fila enche e NUNCA drena: EAGAIN para sempre."""
    leitura, escrita = os.pipe()
    with contextlib.suppress(OSError):  # kernel sem F_SETPIPE_SZ: a fila é maior
        fcntl.fcntl(escrita, 1031, 4096)  # F_SETPIPE_SZ: a fila de 4 KiB
    fcntl.fcntl(escrita, fcntl.F_SETFL, fcntl.fcntl(escrita, fcntl.F_GETFL) | os.O_NONBLOCK)
    return leitura, escrita


class _CodificadorDeMentira:
    """Um quadro Opus de tamanho certo, sem a libopus. O laço é o de verdade."""

    def __init__(self, **_kw: Any) -> None:
        pass

    def codificar(self, _pcm: bytes) -> bytes:
        return b"\x01" * af.BYTES_POR_QUADRO_OPUS


def test_o_escritor_que_so_devolve_eagain_derruba_a_ponte_em_dois_segundos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """De ponta a ponta, com a ponte de verdade: o `bluetoothd` que não drena.

    A fila do hidraw enche em doze quadros e nunca mais anda. A ponte tem de
    cair no teto — nem antes (é congestão até lá), nem nunca (a ponte muda de
    pé para sempre, a ressalva do estudo) — com o motivo certo, a vaga
    devolvida e o diário dizendo qual adaptador.

    MORDIDA: tire o ramo do teto da bomba e a ponte fica de pé, cedendo, pelos
    seis segundos que a régua espera.
    """
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    monkeypatch.setattr(af, "CodificadorOpus", _CodificadorDeMentira)
    caminho = tmp_path / "diario.jsonl"
    relogio = _Relogio()
    governador = gov.GovernadorDoRadio(
        adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=functools.partial(diario.registrar, caminho=caminho),
        relogio=relogio,
    )
    vaga = governador.pedir_vaga(CONTROLE_1, "som")
    assert isinstance(vaga, gov.Vaga)
    leitura, escrita = _cano_que_enche()
    try:
        ponte = af.PonteDeSomPorRadio(
            uniq=CONTROLE_1,
            abrir_hidraw=lambda: escrita,
            fonte_de_pcm=af.fonte_com_ritmo(lambda n: b"\x00" * n, ms_por_report=10),
            vaga=vaga,
        )
        inicio = time.monotonic()
        assert ponte.subir() is True, ponte.motivo
        prazo = inicio + 6.0
        while not ponte.terminou_sozinha() and time.monotonic() < prazo:
            time.sleep(0.02)
        durou = time.monotonic() - inicio
        assert ponte.terminou_sozinha(), "a ponte cedeu seis segundos sem cair"
        assert af.TETO_DE_CEDER_S < durou < af.TETO_DE_CEDER_S + 2.0, durou
        assert ponte.motivo == af.MOTIVO_FILA_PARADA
        assert vaga.solta is True, "a ponte caiu e a vaga ficou ocupando o adaptador"
    finally:
        os.close(leitura)
    o_que = [(e["o_que"], e.get("adaptador")) for e in diario.ler(caminhos=[caminho])]
    assert o_que == [
        (diario.PONTE_SUBIU, ADAPTADOR_A),
        (gov.FILA_PARADA, ADAPTADOR_A),
        (diario.PONTE_DESCEU, ADAPTADOR_A),
    ], o_que


# ---------------------------------------------------------------------------
# 4. a admissão — R3 e R4
# ---------------------------------------------------------------------------
def _dois_adaptadores_de_pe(relogio: _Relogio, registro: _Diario,
                            onde: dict[str, str]) -> gov.GovernadorDoRadio:
    kernel = _Kernel()
    kernel.por(0, ADAPTADOR_A)
    kernel.por(1, ADAPTADOR_B)
    governador = _governador(kernel, relogio, registro, adaptadores=onde)
    governador.tique()  # a amostra que diz quais adaptadores estão de pé
    return governador


def test_a_terceira_ponte_pergunta_e_ligar_aqui_a_sobe_marcada() -> None:
    """R3: sempre pedir mover antes de subir a 3ª ponte. R4: se ela escolher
    «Ligar aqui», a ponte sobe marcada «além do limite» — nada é desligado.

    MORDIDA: troque o `<` da admissão por `<=` e a terceira sobe sem pergunta.
    """
    relogio, registro = _Relogio(), _Diario()
    onde = {CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A}
    governador = _dois_adaptadores_de_pe(relogio, registro, onde)
    for uniq in (CONTROLE_1, CONTROLE_2):
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga) and not vaga.alem_do_limite
        vaga.subiu()

    recusa = governador.pedir_vaga(CONTROLE_3, "haptica")
    assert isinstance(recusa, gov.Recusa), "a terceira ponte subiu sem perguntar"
    assert (recusa.motivo, recusa.vagas) == (gov.MOTIVO_CHEIO, (ADAPTADOR_B,))
    assert recusa.frase == f"Este adaptador está cheio. Há vaga em {ADAPTADOR_B}."
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "haptica"), gov.Recusa)
    assert len(registro.de(gov.ADAPTADOR_CHEIO)) == 1, "a pergunta repetida encheu o diário"
    [pedido] = governador.publicar()[ADAPTADOR_A]["pedidos"]
    assert pedido == {"uniq": CONTROLE_3, "tipo": "vibracao", "vagas": [ADAPTADOR_B]}

    assert governador.ligar_aqui(CONTROLE_3) is True
    vaga = governador.pedir_vaga(CONTROLE_3, "haptica")
    assert isinstance(vaga, gov.Vaga) and vaga.alem_do_limite is True
    vaga.subiu("vibracao")
    publicado = governador.publicar()[ADAPTADOR_A]
    assert publicado["pedidos"] == []
    assert [p["alem_do_limite"] for p in publicado["pontes"]] == [False, False, True]
    [subida] = [e for e in registro.de(diario.PONTE_SUBIU) if e["controle"] == CONTROLE_3]
    assert subida["alem_do_limite"] is True
    assert subida["frase"] == "3 pontes num adaptador (limite 2)."


def test_sem_vaga_em_lugar_nenhum_a_ponte_sobe_marcada_e_o_diario_diz() -> None:
    """R4: os adaptadores cheios — degrada e avisa. Nada é recusado."""
    relogio, registro = _Relogio(), _Diario()
    onde = {
        CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A,
        "aa:bb:cc:00:00:04": ADAPTADOR_B, "aa:bb:cc:00:00:05": ADAPTADOR_B,
    }
    governador = _dois_adaptadores_de_pe(relogio, registro, onde)
    for uniq in (CONTROLE_1, CONTROLE_2, "aa:bb:cc:00:00:04", "aa:bb:cc:00:00:05"):
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga)
        vaga.subiu()
    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga), "sem vaga em lugar nenhum, a ponte foi recusada"
    assert vaga.alem_do_limite is True
    assert registro.de(gov.ADAPTADOR_CHEIO) == [], "perguntou mover sem ter para onde"


def test_a_ponte_que_desce_devolve_a_vaga() -> None:
    relogio, registro = _Relogio(), _Diario()
    onde = {CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A}
    governador = _dois_adaptadores_de_pe(relogio, registro, onde)
    vagas = [governador.pedir_vaga(u, "som") for u in (CONTROLE_1, CONTROLE_2)]
    for vaga in vagas:
        assert isinstance(vaga, gov.Vaga)
        vaga.subiu()
    vagas[0].soltar("sem som")
    vagas[0].soltar("sem som")  # idempotente
    terceira = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(terceira, gov.Vaga) and not terceira.alem_do_limite
    assert len(registro.de(diario.PONTE_DESCEU)) == 1


# ---------------------------------------------------------------------------
# 5. o diário alimenta o fato da queda
# ---------------------------------------------------------------------------
def test_as_pontes_no_diario_dao_o_fato_da_queda(tmp_path: Path) -> None:
    """Sem o `PONTE_SUBIU` com controle, adaptador e tipo, o sino não tem fato.

    MORDIDA: faça `Vaga.subiu` não registrar e `o_fato_da_queda` devolve
    `None` — a queda sem o porquê.
    """
    caminho = tmp_path / "diario.jsonl"
    relogio = _Relogio()
    governador = gov.GovernadorDoRadio(
        adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=functools.partial(diario.registrar, caminho=caminho),
        relogio=relogio,
    )
    for uniq in (CONTROLE_1, CONTROLE_2, CONTROLE_3):
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga)
        vaga.subiu()
    queda = storm_doctor.EventoDoRadio(
        quando="agora", carimbo=time.time() + 1, tag="[BT-SOCKET]", familia="2A",
        ocorrencias=1, borda=True, texto="BT socket write error",
    )
    fato = storm_doctor.o_fato_da_queda(queda, diario.ler(caminhos=[caminho]))
    assert fato == "3 controles com som (limite 2)"


# ---------------------------------------------------------------------------
# 6. um dono: o limite e o amostrador
# ---------------------------------------------------------------------------
def test_o_limite_de_pontes_tem_um_dono_so() -> None:
    """O governador, o orçamento e o sino leem o MESMO número.

    Eram dois — `N_MAX_PONTES` no `radio_da_mesa` e
    `LIMITE_DE_PONTES_POR_ADAPTADOR` no `storm_doctor` —, e dois números
    iguais por coincidência divergem na primeira medição da bancada.
    """
    assert storm_doctor.LIMITE_DE_PONTES_POR_ADAPTADOR is radio_da_mesa.N_MAX_PONTES
    assert gov.GovernadorDoRadio().n_max == radio_da_mesa.N_MAX_PONTES
    fonte = Path(storm_doctor.__file__).read_text(encoding="utf-8")
    assert "LIMITE_DE_PONTES_POR_ADAPTADOR = 2" not in fonte, (
        "o storm_doctor voltou a digitar o limite em vez de lê-lo do dono"
    )


def test_no_modo_falso_o_governador_nao_mede_o_ar() -> None:
    """A suíte nunca pergunta ao rádio de ninguém: sem medidor, sem thread."""
    governador = gov.GovernadorDoRadio.de_producao()
    governador.iniciar()
    try:
        assert governador.ultima_amostra() is None
        assert governador._thread is None
    finally:
        governador.parar()


class _SubsystemComGovernador:
    def __init__(self, amostra: dict[str, Any]) -> None:
        self.governador = type(
            "G", (), {
                "ultima_amostra": lambda _s: dict(amostra),
                "publicar": lambda _s: {ADAPTADOR_A: {"cedendo": True}},
            },
        )()

    def pontes_de_pe(self) -> dict[str, str]:
        return {}


@pytest.mark.asyncio
async def test_o_state_full_le_a_amostra_do_governador() -> None:
    """UM dono do amostrador: o `state_full` não abre um segundo medidor.

    MORDIDA: tire do `_ar_por_adaptador` a leitura de `ultima_amostra()` e o
    `radio_ar` sai sem taxa — a tela sem o ar que o governador mediu.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(transport="bt"))
    daemon.controller.describe_controllers = lambda: []  # type: ignore[attr-defined]
    daemon._alto_falante_subsystem = _SubsystemComGovernador({
        ADAPTADOR_A: ar.ArDoAdaptador(
            hci=0, endereco=ADAPTADOR_A, entrada_por_s=640.0, saida_por_s=190.0,
            janela_s=0.25, conexoes=(),
        ),
    })

    class _Handlers(IpcHandlersMixin):
        def __init__(self, alvo: Any) -> None:
            self.daemon = alvo
            self.store = alvo.store
            self.controller = alvo.controller

    handlers = _Handlers(daemon)
    handlers._afh_lido_em = time.monotonic()  # type: ignore[attr-defined]
    payload = await handlers._handle_daemon_state_full({})  # type: ignore[attr-defined]
    assert handlers._medidor_de_ar is None, "o state_full nasceu com um medidor próprio"
    a = payload["radio_ar"][ADAPTADOR_A]
    assert (a["entrada_por_s"], a["saida_por_s"]) == (640.0, 190.0)
    assert payload["radio_governador"] == {ADAPTADOR_A: {"cedendo": True}}


# ---------------------------------------------------------------------------
# 7. o subsystem: a pergunta não derruba o nó nem acorda a volta à toa
# ---------------------------------------------------------------------------
@dataclass
class _Controle:
    uniq: str
    caminho: str = "/dev/hidraw9"
    transporte: str = "bluetooth"


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.vaga = kw.get("vaga")
        self.motivo = ""
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        if self.vaga is not None:
            self.vaga.subiu("som")
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        if self.vaga is not None:
            self.vaga.soltar("desceu")
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu

    def terminou_sozinha(self) -> bool:
        return False


@pytest.fixture
def som(monkeypatch: pytest.MonkeyPatch) -> Any:
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import filho_de_som as fs

    _PonteDeMentira.criadas = []
    gravadores: list[str] = []

    def _fonte(no: str, **_kw: Any) -> tuple[Any, str, str]:
        gravadores.append(no)
        return (lambda _n: b""), f"gravador:{no}", ""

    monkeypatch.setattr(af, "sink_esta_tocando", lambda nome, *_a, **_k: True)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    monkeypatch.setattr(fs, "derrubar_leitor_de_pipe", lambda *_a, **_k: None)
    monkeypatch.setattr(eh, "ancoras", lambda *a, **k: [])
    monkeypatch.setattr(eh, "endpoints_de_pe", lambda *a, **k: {})
    monkeypatch.setattr(eh, "varrer_endpoints_orfaos", lambda *a, **k: None)
    monkeypatch.setattr(af, "sinks_com_motores", lambda *a, **k: [])
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, c: set())

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=lambda: [])
    # Dois adaptadores de pé e os três controles no A: a terceira ponte tem
    # para onde ir, e por isso a pergunta (R3) — e não o «além do limite» (R4).
    sub.governador = _dois_adaptadores_de_pe(_Relogio(), _Diario(), {})
    return sub, gravadores


def test_a_terceira_espera_a_resposta_sem_gravador_e_sem_derrubar_o_no(som: Any) -> None:
    """A pergunta está com ela: a ponte não sobe, o `pw-record` não nasce, e o
    nó não entra na recusa que o apagaria da lista de som dela."""
    sub, gravadores = som
    sub._casar_as_pontes([_Controle(u) for u in (CONTROLE_1, CONTROLE_2, CONTROLE_3)])
    assert sorted(sub._pontes) == [CONTROLE_1, CONTROLE_2]
    assert af.nome_do_sink(CONTROLE_3) not in gravadores, (
        "o gravador da terceira subiu para esperar uma resposta"
    )
    assert CONTROLE_3 not in sub._ponte_recusada, "a pergunta virou recusa e apagaria o nó"
    assert sub._esperando_vaga == frozenset({(CONTROLE_3, "som")})


def test_quem_espera_vaga_nao_acorda_o_vigia(
    som: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire o `esperando.get(uniq)` do vigia e ele acorda a volta a
    cada 0,4 s enquanto ela não responde."""
    sub, _ = som
    sub._esperando_vaga = frozenset({(CONTROLE_3, "som")})
    sub._endpoints = {CONTROLE_3: type("E", (), {"nome": "endpoint::3"})()}
    monkeypatch.setattr(
        af, "sinks_que_tocam", lambda nomes: {af.nome_do_sink(CONTROLE_3)}
    )
    assert sub._o_modo_de_alguem_mudou() is False


def test_a_ponte_que_terminou_sozinha_sai_e_a_sob_demanda_religa(som: Any) -> None:
    sub, _ = som
    sub._casar_as_pontes([_Controle(CONTROLE_1)])
    primeira = sub._pontes[CONTROLE_1]
    primeira.terminou_sozinha = lambda: True  # type: ignore[method-assign]
    primeira.vaga.soltar(af.MOTIVO_FILA_PARADA)
    sub._casar_as_pontes([_Controle(CONTROLE_1)])
    assert sub._pontes[CONTROLE_1] is not primeira, (
        "a ponte morta ficou no lugar e a ponte sob demanda não religou"
    )

