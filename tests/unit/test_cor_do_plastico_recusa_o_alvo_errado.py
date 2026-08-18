"""COR-DO-PLASTICO-01 — as travas do único instrumento que ESCREVE no aparelho.

O DEFEITO QUE ESTE ARQUIVO FECHA
--------------------------------
`scripts/ensaios/cor_do_plastico.py` é o único instrumento de
`scripts/ensaios/` que manda `SET_FEATURE` para o controle — a família `0x80`,
a de FÁBRICA, onde `[1,1]` reseta o aparelho e `[12,1]` grava na memória
não-volátil. Ele nasceu com sete travas e **nenhum teste**: as travas foram
exercidas à mão, num terminal que morreu às 14:50 de 15/08/2026. As duas
mordidas provadas naquele terminal sobreviveram só no relatório da recuperação.

Uma trava que só foi exercida à mão é uma trava que a próxima edição do arquivo
apaga sem ninguém ver. Este arquivo traz as mordidas para a suíte.

O QUE ESTE ARQUIVO NÃO FAZ, E É DE PROPÓSITO
---------------------------------------------
**Não toca em `/dev/hidraw` nenhum.** A armadilha nº 3 desta casa é o
instrumento que disputa o hidraw com o daemon e imprime "aplicado" sem ter
aplicado; um teste que abrisse o nó de verdade seria essa mesma armadilha com
outro nome. Aqui o `fcntl` do instrumento é substituído por um de mentira que
ANOTA cada `ioctl` em vez de executá-lo, e a prova de vida lê de um
`socketpair` de datagramas — que preserva a fronteira de cada report, coisa que
um `pipe` não faz.

Por isso a asserção central pode ser literal: *quantos `HIDIOCSFEATURE`
chegaram ao aparelho?* Zero é zero, e é medido, não afirmado.

O QUE CADA TESTE PROVA
----------------------
1. `--exigir-mac` com o MAC do nó passa; com o MAC de OUTRO nó recusa, e a
   recusa acontece ANTES de a porta abrir — nenhum byte no fio.
2. O rabo de CRC-32 do envelope de rádio: íntegro passa, corrompido reprova, e
   o miolo continua conferido byte a byte por trás dele.
3. A semente do CRC daqui é a MESMA de `core/ds_output_report.py` — o teste que
   impede as duas cópias do número de divergirem.
4. As duas máscaras: serial com 6 caracteres públicos e o resto em `#` (em
   texto E em hexadecimal), MAC com os octetos 4 e 5 zerados.
5. A trava do modo seco: sem `--escrever` nada sai no fio; com `--escrever` sai
   exatamente um `SET_FEATURE`, e é o payload `80 01 13 00 ... 00`.
6. Alvo de rádio sem `--radio-a-serio` é recusado sem abrir a porta.

O PAR DE NÚMEROS DO CRC É O MEDIDO, NÃO UM INVENTADO
-----------------------------------------------------
O envelope que foi ao rádio às 14:46 de 15/08/2026 terminava em `93 0d 46 73`,
isto é, `0x73460d93`, e a mordida da trava saiu com o rabo corrompido no último
byte: *"veio 0x8c460d93, recalculado 0x73460d93"*. Os dois números estão aqui
como asserção porque são reproduzíveis sem aparelho: o payload é fixo e a
semente é `0xA3`.

PROVA DE QUE MORDE (arrancar, ver reprovar, devolver) — 15/08/2026
-------------------------------------------------------------------
Cada cura foi arrancada numa CÓPIA do instrumento em `/tmp` — nunca no arquivo
do repositório — e a suíte rodou contra a cópia:

- sem o `if esperado and aparelho.mac.lower() != esperado` de `escolher_alvo`:
  reprovam `test_exigir_mac_do_outro_no_recusa_antes_de_abrir_a_porta` (o
  `SystemExit` não veio) e a asserção de que nenhum byte foi ao aparelho —
  `DID NOT RAISE <class 'SystemExit'>`;
- sem a conferência do rabo em `mandar_o_comando`: reprova
  `test_o_rabo_de_crc_corrompido_reprova` — `DID NOT RAISE
  PayloadRecusadoError`;
- sem o `conferir_payload(miolo)` do ramo do CRC: reprova
  `test_o_miolo_continua_conferido_por_tras_do_crc`;
- com a semente trocada para `0xA4`: reprovam os dois testes da semente, um por
  desigualdade e outro pelo `SystemExit` que `conferir_a_semente` levanta;
- sem o corte de `mascarar_serial` / sem os `#` de `sem_o_serial` / com a
  máscara de MAC devolvendo o endereço inteiro: reprovam os testes de máscara;
- sem o `if not escrever: return` de `medir`: reprova
  `test_sem_escrever_nada_vai_ao_fio` — `1 == 0` escritas;
- sem o ramo `transporte == RADIO and not radio_a_serio`: reprova
  `test_radio_sem_radio_a_serio_nao_abre_a_porta`.

A saída literal de cada reprovação está no relatório da leva.
"""
from __future__ import annotations

import array
import errno
import importlib.util
import os
import socket
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.ds_output_report import BT_FEATURE_CRC_SEED, bt_crc32

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "cor_do_plastico.py"


def _carregar_o_instrumento() -> tuple[Any, Any]:
    """Carrega o instrumento pelo caminho, como o precedente desta pasta manda.

    Ele mora em `scripts/ensaios/`, que não é pacote; `spec_from_file_location`
    é o mesmo caminho que `test_ensaio_em_par_recusa_o_vpad_do_proprio_produto`
    usa. O nome sob o qual ele entra em `sys.modules` é outro de propósito, para
    que este arquivo nunca roube o módulo de quem o importa pelo nome real.
    """
    pasta = str(_INSTRUMENTO.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    especificacao = importlib.util.spec_from_file_location(
        "cor_do_plastico_sob_ensaio", _INSTRUMENTO
    )
    if especificacao is None or especificacao.loader is None:
        raise AssertionError(f"não consegui carregar {_INSTRUMENTO}")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo, sys.modules["comum"]


COR, COMUM = _carregar_o_instrumento()

#: Endereços FORJADOS, da faixa de documentação `aa:bb:cc:` — as duas guardas de
#: anonimato desta casa (`check_test_data.sh` e `test_anonimato_de_fixtures.py`)
#: reconhecem essa faixa como sintética. Nenhum aparelho da bancada aparece
#: aqui, nem mascarado: um teste não precisa do endereço dela para nada.
MAC_DO_ALVO = "aa:bb:cc:dd:ee:03"
MAC_DO_OUTRO_NO = "aa:bb:cc:dd:ee:09"

#: Serial FORJADO, com a mesma forma do de fábrica: 17 caracteres ASCII, e a
#: cor nos caracteres 5 e 6. Aqui o código é `02`, que a tabela do instrumento
#: chama de Cosmic Red. Nenhum controle da bancada tem este serial — e é
#: exatamente por isso que ele está num arquivo versionado.
SERIAL_FORJADO = "ZZ9Y02Q0000000000"
COR_DO_SERIAL_FORJADO = "Cosmic Red"

#: A impressão digital de firmware que o `0x20` devolve na bancada de mentira.
#: O conteúdo não importa: o que a prova de sanidade compara é se ele saiu
#: IGUAL antes e depois da escrita.
FIRMWARE_FORJADO = b"FIRMWARE FORJADO"

#: O envelope que foi ao rádio em 15/08/2026, e o rabo que a trava recusou.
CRC_DO_ENVELOPE = 0x73460D93
CRC_CORROMPIDO = 0x8C460D93

#: `HIDIOCGFEATURE` e `HIDIOCSFEATURE` moram no byte baixo do número do ioctl.
_NR_GETFEATURE = 0x07
_NR_SETFEATURE = 0x06


class FcntlDeMentira:
    """Um `fcntl` que ANOTA os ioctl em vez de executá-los. Nada vai ao fio.

    O que ele responde é o mínimo para o instrumento andar até o ponto em que
    escreveria: o feature `0x20` (a prova de sanidade) sempre, e o `0x81` (a
    resposta com o serial) **só depois de um `SET_FEATURE` ter chegado** — que é
    como o aparelho de verdade se comporta, e o que faz o modo seco não colher
    serial nenhum.
    """

    def __init__(self) -> None:
        self.escritas: list[bytes] = []
        self.leituras: list[int] = []

    @property
    def resposta_do_serial(self) -> bytes:
        corpo = bytes([COR.FEATURE_RESPOSTA, COR.BASE_DO_SERIAL, COR.NUM_DO_SERIAL, 2])
        corpo += SERIAL_FORJADO.encode("ascii")
        return corpo.ljust(64, b"\x00")

    @property
    def resposta_do_firmware(self) -> bytes:
        return (bytes([COR.FEATURE_FIRMWARE]) + FIRMWARE_FORJADO).ljust(64, b"\x00")

    def ioctl(self, _fd: int, requisicao: int, buffer: Any, _mutar: bool = False) -> int:
        numero = requisicao & 0xFF
        tamanho = (requisicao >> 16) & 0x3FFF
        if numero == _NR_SETFEATURE:
            self.escritas.append(bytes(buffer))
            return len(buffer)
        if numero != _NR_GETFEATURE:
            raise AssertionError(f"ioctl que este ensaio não conhece: 0x{requisicao:08x}")
        pedido = int(buffer[0])
        self.leituras.append(pedido)
        if pedido == COR.FEATURE_FIRMWARE:
            resposta = self.resposta_do_firmware
        elif pedido == COR.FEATURE_RESPOSTA:
            if not self.escritas:
                raise OSError(errno.EPIPE, "ninguém pediu nada a este aparelho")
            resposta = self.resposta_do_serial
        else:
            raise AssertionError(f"feature que este ensaio não conhece: 0x{pedido:02x}")
        resposta = resposta[:tamanho]
        buffer[: len(resposta)] = array.array("B", resposta)
        return len(resposta)


@dataclass
class NoDeMentira:
    """O que `abrir_no_hidraw` devolveria — sem abrir coisa nenhuma."""

    fd: int
    porta: str = "bancada de mentira"
    motivo: str = "socketpair local; nenhum /dev/hidraw foi aberto"
    fechado: bool = False

    def fechar(self) -> None:
        self.fechado = True


@dataclass
class Bancada:
    """A mesa de mentira de uma execução: o alvo, o outro nó, e os espiões."""

    alvo: Any
    outro: Any
    fcntl: FcntlDeMentira
    aberturas: list[str] = field(default_factory=list)
    nos: list[NoDeMentira] = field(default_factory=list)

    @property
    def alvos(self) -> list[Any]:
        return [self.alvo, self.outro]


def _aparelho(dir_device: Path, *, hidraw: str, mac: str, transporte: str) -> Any:
    return COMUM.Aparelho(
        hidraw=hidraw,
        caminho_hidraw=f"/dev/{hidraw}-que-nao-existe",
        dir_device=str(dir_device),
        mac=mac,
        nome="DualSense de mentira",
        transporte=transporte,
        e_vpad=False,
        rotulo="",
    )


@pytest.fixture()
def bancada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Bancada:
    """A mesa inteira substituída: descritor, porta, `fcntl` e reports.

    O `hardware_version` é arquivo de verdade num diretório temporário, porque
    o instrumento o lê do sysfs com `ler_texto` e a prova de sanidade compara o
    valor antes e depois. O resto é de mentira, e nenhum `/dev` é tocado.
    """
    device = tmp_path / "sysfs-do-alvo"
    device.mkdir()
    (device / "hardware_version").write_text("0x00000811\n", encoding="utf-8")

    esquerda, direita = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    # Um datagrama por report de entrada: `os.read` devolve UM de cada vez,
    # que é o que faz a contagem de `REPORTS_QUE_PROVAM_VIDA` significar algo.
    # São oito porque a prova de vida roda duas vezes, antes e depois.
    for _ in range(8):
        direita.send(bytes([0x01]) + b"\x00" * 63)

    falso = FcntlDeMentira()
    mesa = Bancada(
        alvo=_aparelho(device, hidraw="hidraw4", mac=MAC_DO_ALVO, transporte=COMUM.CABO),
        outro=_aparelho(device, hidraw="hidraw9", mac=MAC_DO_OUTRO_NO, transporte=COR.RADIO),
        fcntl=falso,
    )

    def _abrir(caminho: str, *, escrita: bool = True) -> NoDeMentira:
        mesa.aberturas.append(caminho)
        no = NoDeMentira(fd=esquerda.fileno())
        mesa.nos.append(no)
        return no

    monkeypatch.setattr(COR, "fcntl", falso)
    monkeypatch.setattr(COR, "abrir_no_hidraw", _abrir)
    monkeypatch.setattr(
        COR,
        "tamanhos_do_descritor",
        lambda _dir: {"feature": {0x20: 64, 0x80: 64, 0x81: 64}},
    )
    try:
        yield mesa
    finally:
        esquerda.close()
        direita.close()


def _como_o_main(mesa: Bancada, pedido: str, **argumentos: Any) -> Any:
    """A MESMA ordem do `_corpo()`: escolher o alvo e SÓ ENTÃO medir.

    Sem esta ordem o teste do MAC não valeria nada: a pergunta não é se
    `escolher_alvo` levanta, é se alguma coisa chega ao aparelho depois de ela
    levantar.
    """
    exigir_mac = argumentos.pop("exigir_mac", "")
    aparelho = COR.escolher_alvo(mesa.alvos, pedido, exigir_mac=exigir_mac)
    return COR.medir(
        aparelho,
        escrever=argumentos.pop("escrever", False),
        radio_a_serio=argumentos.pop("radio_a_serio", False),
        com_crc=argumentos.pop("com_crc", True),
    )


# ---------------------------------------------------------------------------
# 1. A trava do MAC — a mordida de 14:45
# ---------------------------------------------------------------------------


def test_exigir_mac_com_o_mac_do_no_devolve_o_alvo(bancada: Bancada) -> None:
    """O caso feliz, e ele importa: uma trava que recusa tudo não é trava."""
    escolhido = COR.escolher_alvo(bancada.alvos, "hidraw4", exigir_mac=MAC_DO_ALVO)
    assert escolhido is bancada.alvo

    # Maiúscula e o prefixo `/dev/` são como o endereço sai do `sysfs` e como a
    # mão o digita; nenhum dos dois pode virar recusa.
    assert (
        COR.escolher_alvo(bancada.alvos, "/dev/hidraw4", exigir_mac=MAC_DO_ALVO.upper())
        is bancada.alvo
    )


def test_exigir_mac_do_outro_no_recusa_antes_de_abrir_a_porta(bancada: Bancada) -> None:
    """A mordida provada à mão: pedir um nó exigindo o MAC de OUTRO controle.

    Em 15/08/2026 isso foi feito pedindo `hidraw8` e exigindo o MAC do branco.
    Aqui é a mesma forma: o nó existe, o pedido é sintaticamente válido, e o
    endereço é de outro aparelho.
    """
    with pytest.raises(SystemExit) as caiu:
        _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_OUTRO_NO, escrever=True)

    recado = str(caiu.value)
    assert "NÃO é o controle que você pediu" in recado
    assert "NADA foi ao aparelho" in recado

    # O que a mordida vale: nem a porta abriu, nem ioctl nenhum saiu.
    assert bancada.aberturas == []
    assert bancada.fcntl.escritas == []
    assert bancada.fcntl.leituras == []


def test_a_recusa_do_mac_nao_imprime_o_endereco_inteiro(bancada: Bancada) -> None:
    """A recusa é texto que vai para transcrito versionado — e ele é mascarado."""
    with pytest.raises(SystemExit) as caiu:
        COR.escolher_alvo(bancada.alvos, "hidraw4", exigir_mac=MAC_DO_OUTRO_NO)

    recado = str(caiu.value)
    assert "aa:bb:cc:00:00:03" in recado
    assert "aa:bb:cc:00:00:09" in recado
    assert "dd:ee" not in recado


# ---------------------------------------------------------------------------
# 2. A trava do CRC — a segunda mordida de 15/08
# ---------------------------------------------------------------------------


def test_o_envelope_de_radio_integro_passa_e_o_rabo_e_o_medido(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """O envelope montado pelo instrumento é aceito, e o CRC é o de 14:46."""
    envelope = COR.envelope_de_radio(COR.montar_payload(64))
    capsys.readouterr()

    assert int.from_bytes(envelope[-4:], "little") == CRC_DO_ENVELOPE
    assert bytes(envelope[:3]) == bytes([0x80, 0x01, 0x13])

    falha = COR.mandar_o_comando(4242, bytearray(envelope), bytes_de_crc=4)

    assert falha == ""
    assert bancada.fcntl.escritas == [bytes(envelope)]


def test_o_rabo_de_crc_corrompido_reprova(bancada: Bancada) -> None:
    """A mordida literal do transcrito: veio `0x8c460d93`, recalculado `0x73460d93`."""
    envelope = COR.envelope_de_radio(COR.montar_payload(64))
    envelope[-1] ^= 0xFF

    with pytest.raises(COR.PayloadRecusadoError) as caiu:
        COR.mandar_o_comando(4242, envelope, bytes_de_crc=4)

    recado = str(caiu.value)
    assert f"veio 0x{CRC_CORROMPIDO:08x}" in recado
    assert f"recalculado 0x{CRC_DO_ENVELOPE:08x}" in recado
    assert bancada.fcntl.escritas == []


def test_o_miolo_continua_conferido_por_tras_do_crc(bancada: Bancada) -> None:
    """Conhecer o rabo não pode afrouxar o miolo — foi essa a promessa da cura.

    O byte 5 sujo é a forma de todo acidente perigoso desta família: um par
    diferente de `[1,19]` no lugar errado do buffer.
    """
    payload = COR.montar_payload(64)
    payload[5] = 0x01
    envelope = COR.envelope_de_radio(payload)

    with pytest.raises(COR.PayloadRecusadoError) as caiu:
        COR.mandar_o_comando(4242, envelope, bytes_de_crc=4)

    assert "vieram sujos" in str(caiu.value)
    assert bancada.fcntl.escritas == []


def test_o_par_que_reseta_o_controle_e_recusado(bancada: Bancada) -> None:
    """`[1,1]` reseta o aparelho. A trava tem de conhecê-lo pelo nome."""
    payload = COR.montar_payload(64)
    payload[2] = 1

    with pytest.raises(COR.PayloadRecusadoError):
        COR.mandar_o_comando(4242, payload)

    assert bancada.fcntl.escritas == []


# ---------------------------------------------------------------------------
# 3. A semente do CRC — duas cópias do mesmo número, e o confronto que as prende
# ---------------------------------------------------------------------------


def test_a_semente_do_instrumento_e_a_mesma_do_pacote() -> None:
    """O instrumento copia a semente para rodar sem o pacote; a cópia é presa aqui.

    "Medir contra a biblioteca errada produz alarme convincente e falso" é a
    armadilha nº 1 desta casa, e duas cópias de um número são duas réguas.
    """
    assert COR.SEMENTE_FEATURE_BT == BT_FEATURE_CRC_SEED

    # E o número tem de produzir o MESMO CRC dos dois lados — não basta o
    # literal bater se o jeito de aplicá-lo divergir.
    miolo = bytes(COR.montar_payload(64))[:60]
    daqui = zlib.crc32(bytes([COR.SEMENTE_FEATURE_BT]) + miolo) & 0xFFFFFFFF
    assert daqui == bt_crc32(miolo, seed=BT_FEATURE_CRC_SEED) == CRC_DO_ENVELOPE


def test_conferir_a_semente_diz_de_onde_veio_o_numero() -> None:
    """A conferência roda em tempo de execução e nomeia a outra cópia."""
    dito = COR.conferir_a_semente()
    assert dito.startswith(f"0x{BT_FEATURE_CRC_SEED:02x},")
    assert "core/ds_output_report.py::BT_FEATURE_CRC_SEED" in dito


# ---------------------------------------------------------------------------
# 4. As duas máscaras — a regra da casa sobre arquivo versionado
# ---------------------------------------------------------------------------


def test_mascarar_serial_deixa_seis_publicos_e_o_resto_em_cerquilha() -> None:
    mascarado = COR.mascarar_serial(SERIAL_FORJADO)

    assert mascarado == "ZZ9Y02###########"
    assert len(mascarado) == len(SERIAL_FORJADO)
    assert mascarado[:6] == SERIAL_FORJADO[:6]
    assert set(mascarado[6:]) == {"#"}
    # Os dois caracteres da cor — o objeto inteiro do ensaio — sobrevivem.
    assert mascarado[COR.FATIA_DA_COR] == "02"
    # E nenhum caractere do número da unidade sobra.
    assert SERIAL_FORJADO[6:] not in mascarado


def test_mascarar_serial_curto_nao_inventa_caractere() -> None:
    assert COR.mascarar_serial("ZZ9Y02") == "ZZ9Y02"
    assert COR.mascarar_serial("") == ""


def test_sem_o_serial_mascara_tambem_o_hexadecimal() -> None:
    """`4d 36 35` é o serial tanto quanto `M65` — o dump também tem de mascarar."""
    resposta = FcntlDeMentira().resposta_do_serial
    limpa = COR.sem_o_serial(resposta)

    inicio = 4 + COR.CARACTERES_PUBLICOS_DO_SERIAL
    fim = 4 + COR.TAMANHO_DO_SERIAL
    assert limpa[:inicio] == resposta[:inicio]
    assert limpa[inicio:fim] == b"#" * (fim - inicio)
    assert SERIAL_FORJADO.encode("ascii")[6:] not in limpa
    # O enquadramento, que é o que o dump precisa mostrar, continua legível.
    assert limpa[:4] == bytes([COR.FEATURE_RESPOSTA, 1, 19, 2])


def test_mascarar_mac_zera_os_octetos_quatro_e_cinco() -> None:
    assert COR.mascarar("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:00:00:ff"
    # O que não tem forma de MAC volta como veio: mascarar às cegas produziria
    # um endereço inventado, que é pior que um ausente.
    assert COR.mascarar("") == ""
    assert COR.mascarar("sem forma de endereço") == "sem forma de endereço"


# ---------------------------------------------------------------------------
# 5. A trava do modo seco — a rodada que mostra o comando e cala o fio
# ---------------------------------------------------------------------------


def test_sem_escrever_nada_vai_ao_fio(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """Seco por omissão: o instrumento chega até a beira da escrita e para."""
    medida = _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=False)
    tela = capsys.readouterr().out

    assert bancada.fcntl.escritas == []
    assert medida.escreveu is False
    assert medida.serial.texto == ""

    # E não é que ele tenha desistido antes: a porta abriu e a prova de vida
    # rodou. O que faltou foi só a escrita.
    assert bancada.aberturas == [bancada.alvo.caminho_hidraw]
    assert COR.FEATURE_FIRMWARE in bancada.fcntl.leituras
    assert medida.antes.vivo is True
    assert "RODADA SECA" in tela
    assert "--escrever" in tela


def test_com_escrever_sai_exatamente_um_set_feature(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """A contraprova do teste acima: com a autorização, o comando sai — UM.

    Sem este teste o anterior passaria por qualquer motivo errado (uma bancada
    que aborta cedo, um `fcntl` que não é chamado). Aqui o mesmo caminho, com
    `--escrever`, produz a escrita esperada byte a byte.
    """
    medida = _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=True)
    capsys.readouterr()

    esperado = bytes([0x80, 0x01, 0x13]) + b"\x00" * 61
    assert bancada.fcntl.escritas == [esperado]
    assert medida.escreveu is True
    assert medida.serial.texto == SERIAL_FORJADO
    assert medida.serial.codigo_da_cor == "02"
    assert medida.serial.nome_da_cor == COR_DO_SERIAL_FORJADO
    # A prova de sanidade é a razão de a escrita ser autorizada: ela roda dos
    # dois lados e compara.
    assert medida.continua_sao is True
    assert bancada.nos[0].fechado is True


def test_a_tela_nunca_mostra_o_serial_em_hexadecimal(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """O dump da resposta sai mascarado já na tela; o texto decodificado, não.

    A regra da casa (o precedente é o CSV de `imu_no_cabo.py`): a tela é dela e
    pode ver o aparelho dela; o ARQUIVO é versionado e nunca vê. O `Transcrito`
    mascara o texto na gravação, mas o hexadecimal ele não saberia reconhecer —
    por isso o dump já nasce com `#`.
    """
    _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=True)
    tela = capsys.readouterr().out

    em_hexadecimal = SERIAL_FORJADO.encode("ascii")[6:].hex(" ")
    assert em_hexadecimal not in tela


def test_radio_sem_radio_a_serio_nao_abre_a_porta(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """Caminho novo não se estreia por omissão — nem com `--escrever` na linha."""
    medida = _como_o_main(bancada, "hidraw9", exigir_mac=MAC_DO_OUTRO_NO, escrever=True)
    tela = capsys.readouterr().out

    assert bancada.aberturas == []
    assert bancada.fcntl.escritas == []
    assert medida.escreveu is False
    assert "--radio-a-serio" in medida.erro_da_escrita
    assert "RECUSADO" in tela


def test_a_familia_do_firmware_nunca_e_escrita(bancada: Bancada) -> None:
    """A D-32 dela: ler a família `0xf0`-`0xf7`, nunca escrever."""
    for report_id in COR.FAMILIA_DO_FIRMWARE:
        payload = COR.montar_payload(64)
        payload[0] = report_id
        with pytest.raises(COR.PayloadRecusadoError) as caiu:
            COR.mandar_o_comando(4242, payload)
        assert "família do FIRMWARE" in str(caiu.value)

    assert bancada.fcntl.escritas == []


def test_o_ensaio_nao_abriu_dev_hidraw_nenhum(bancada: Bancada) -> None:
    """A guarda contra o próprio ensaio: nenhum caminho de `/dev` é real.

    A armadilha nº 3 desta casa é o instrumento que disputa o hidraw com o
    daemon. Um teste que a repetisse seria pior que teste nenhum, porque
    passaria verde numa máquina sem controle e faria estrago numa com.
    """
    _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=True)

    for caminho in bancada.aberturas:
        assert caminho.startswith("/dev/hidraw")
        assert not os.path.exists(caminho)
