"""O-SOM-E-A-HAPTICA-NUM-RELATORIO-SO-01, o primeiro tempo: o formato e o ensaio.

A bancada de 03/10: pelo rádio, cada controle carregou som OU háptica, com dois
ou quatro controles por adaptador; a casa usa dois escritores por controle (o
``0x35`` do som e o ``0x32`` da háptica), cada um com o seu contador no
``0x11``. O fork loteran do DS5Dongle monta um ``0x36`` de 398 B com os quatro
blocos num relatório só (lido no código, nunca tentado aqui).

No primeiro tempo nasceram o montador do relatório combinado
(`alto_falante_bt.montar_relatorio_combinado` e o escritor único
`RelatorioCombinado`) e o ensaio de bancada que prova o formato
(`scripts/ensaios/o_som_e_a_haptica_num_relatorio.py`), que recusa com o daemon
no ar. A bancada provou o formato em 03/10 ~23h15 (som e háptica juntos;
sem o ``0x10`` a háptica cala). No SEGUNDO tempo a ponte passa a ter um
escritor só: a `BombaDeSomPeloRadio` monta o ``0x36`` com o som e a háptica do
quadro e o ``0x10`` sempre (as réguas do fim deste arquivo).

A BANCADA: o montador é o real; o relatório é lido por um leitor de cadeia TLV
escrito aqui, independente do montador (a tag, o tamanho, o próximo bloco logo
depois), e o CRC é conferido pelo `bt_crc32` do dono do relatório de saída. O
ensaio roda pelo `main` real, com a pergunta ao daemon, a lista de controles e
a abertura do hidraw dubladas na borda. A MORDIDA de cada régua está no
docstring dela.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.integrations import alto_falante_bt as af

RAIZ = Path(__file__).resolve().parents[2]
ENSAIO = RAIZ / "scripts" / "ensaios" / "o_som_e_a_haptica_num_relatorio.py"
MAC = "aa:bb:cc:00:00:01"

COMMON = bytes(range(1, rep.COMMON_LEN + 1))
HAPTICO = bytes((i * 3) & 0xFF for i in range(64))
SOM = bytes((0xA0 + i) & 0xFF for i in range(200))


def _cadeia(relatorio: bytes) -> list[tuple[int, int, int, bytes]]:
    """``(posição, bloco, tamanho, dados)`` da cadeia TLV, do [2] até a tag zerada."""
    blocos: list[tuple[int, int, int, bytes]] = []
    pos = 2
    while relatorio[pos] != 0:
        tag, tamanho = relatorio[pos], relatorio[pos + 1]
        assert tag & 0x80, f"tag sem o bit de presente em [{pos}]: {tag:#04x}"
        blocos.append((pos, tag & 0x3F, tamanho, relatorio[pos + 2 : pos + 2 + tamanho]))
        pos += 2 + tamanho
    assert pos <= len(relatorio) - 4, "a cadeia invadiu o CRC"
    assert not any(relatorio[pos : len(relatorio) - 4]), "sobrou byte depois da cadeia"
    return blocos


def _crc_certo(relatorio: bytes) -> bool:
    crc = rep.bt_crc32(relatorio[:-4], seed=rep.BT_CRC_SEED)
    return crc.to_bytes(4, "little") == relatorio[-4:]


def _controle(contador: int) -> bytes:
    return af.controle_de_audio_035(contador_de_quadros=contador)


def test_o_relatorio_combinado_tem_os_quatro_blocos_no_formato() -> None:
    """Régua 1: o ``0x36`` de 398 B com ``0x11``, ``0x10``, ``0x12`` e ``0x13``.

    Na ordem e no tamanho do layout (7, 63, 64 e 200 B, em [2], [11], [76] e
    [142]), o ``common`` nos primeiros 47 B do estado, e o CRC certo.

    MORDIDA: a semente do CRC trocada (o firmware descarta calado), ou a
    háptica e o som fora da ordem, e esta régua reprova.
    """
    relatorio = af.montar_relatorio_combinado(
        seq=5, controle=_controle(42), common=COMMON, haptico=HAPTICO, quadro_de_som=SOM
    )

    assert (relatorio[0], len(relatorio)) == (0x36, 398)
    assert relatorio[1] >> 4 == 5
    blocos = _cadeia(relatorio)
    assert [(p, b, t) for p, b, t, _d in blocos] == [
        (2, 0x11, 7), (11, 0x10, 63), (76, 0x12, 64), (142, 0x13, 200)
    ], blocos
    assert blocos[0][3] == _controle(42) and blocos[0][3][-1] == 42
    assert blocos[1][3][:47] == COMMON and not any(blocos[1][3][47:])
    assert blocos[2][3] == HAPTICO
    assert blocos[3][3] == SOM
    assert _crc_certo(relatorio), "o CRC do 0x36 não confere"


def test_o_bloco_que_nao_veio_nao_entra_e_a_cadeia_nao_tem_buraco() -> None:
    """Sem estado, sem háptica ou sem som: os blocos seguintes sobem na cadeia."""
    sem_estado = af.montar_relatorio_combinado(
        seq=0, controle=_controle(0), haptico=HAPTICO, quadro_de_som=SOM
    )
    assert [(p, b) for p, b, _t, _d in _cadeia(sem_estado)] == [(2, 0x11), (11, 0x12), (77, 0x13)]
    so_som = af.montar_relatorio_combinado(seq=0, controle=_controle(0), quadro_de_som=SOM)
    assert [b for _p, b, _t, _d in _cadeia(so_som)] == [0x11, 0x13]
    fone = af.montar_relatorio_combinado(
        seq=0, controle=_controle(0), quadro_de_som=SOM, tag_som=af.BLOCO_FONE
    )
    assert [b for _p, b, _t, _d in _cadeia(fone)] == [0x11, 0x16]
    for relatorio in (sem_estado, so_som, fone):
        assert _crc_certo(relatorio)


def test_o_montador_recusa_o_bloco_de_tamanho_errado() -> None:
    """Levanta em vez de mentir: um bloco torto não vira relatório."""
    with pytest.raises(ValueError):
        af.montar_relatorio_combinado(seq=0, controle=b"\x00" * 6)
    with pytest.raises(ValueError):
        af.montar_relatorio_combinado(seq=0, controle=_controle(0), haptico=b"\x00" * 63)
    with pytest.raises(ValueError):
        af.montar_relatorio_combinado(seq=0, controle=_controle(0), common=b"\x00" * 46)
    with pytest.raises(ValueError):
        af.montar_relatorio_combinado(seq=0, controle=_controle(0), quadro_de_som=b"\x00" * 201)


def test_um_escritor_um_contador_um_relatorio_por_quadro() -> None:
    """Régua 2: som e háptica no mesmo controle, um relatório por quadro, com os dois.

    O contador do ``0x11`` anda UM por relatório (e dá a volta em 256), e a
    sequência do cabeçalho anda junto (e dá a volta em 16).

    MORDIDA: o contador que anda dois por quadro (o de hoje, com dois
    escritores no mesmo controle, cada um contando o seu) reprova.
    """
    escritor = af.RelatorioCombinado(contador=250)
    relatorios = [
        escritor.relatorio_do_quadro(quadro_de_som=SOM, haptico=HAPTICO) for _ in range(20)
    ]

    for i, relatorio in enumerate(relatorios):
        blocos = {b: d for _p, b, _t, d in _cadeia(relatorio)}
        assert set(blocos) == {0x11, 0x12, 0x13}, f"quadro {i}: {sorted(blocos)}"
        assert relatorio[10] == (250 + i) & 0xFF, f"quadro {i}: contador {relatorio[10]}"
        assert relatorio[1] >> 4 == i & 0x0F
        assert _crc_certo(relatorio)


def _carregar_o_ensaio() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ensaio_som_e_haptica", ENSAIO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def ensaio(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O ensaio real, com a borda dublada: daemon, lista, bancada e hidraw."""
    modulo = _carregar_o_ensaio()
    borda: dict[str, Any] = {"daemon": False, "abriu": [], "escritos": []}
    monkeypatch.setattr(modulo, "daemon_no_ar", lambda: borda["daemon"])
    monkeypatch.setattr(modulo, "_exigir_bancada", lambda: (True, ""))
    from hefesto_dualsense4unix.daemon.subsystems import alto_falante as sub
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

    monkeypatch.setattr(
        sub, "controles_na_lista",
        lambda: [SimpleNamespace(uniq=MAC, caminho="/dev/hidraw-de-mentira", transporte="rádio")],
    )

    def _abrir(caminho: str) -> int:
        borda["abriu"].append(caminho)
        return -1

    monkeypatch.setattr(bt, "abrir_hidraw_rw", _abrir)
    monkeypatch.setattr(modulo.os, "close", lambda fd: None)
    monkeypatch.setattr(
        modulo.af, "escritor_de_hidraw",
        lambda fd: lambda dados: borda["escritos"].append(dados) or len(dados),
    )
    modulo.borda = borda  # type: ignore[attr-defined]
    return modulo


ESCREVER = ["--escrever", "--exigir-mac", MAC, "--eu-estou-ouvindo", "--segundos", "0.1"]


def test_o_ensaio_recusa_com_o_daemon_no_ar(ensaio: Any) -> None:
    """Com o daemon no ar, o ensaio recusa antes de abrir o hidraw.

    MORDIDA: tire a recusa do daemon de `escrever_no_aparelho` e o ensaio abre
    o hidraw e escreve no controle que o daemon também escreve.
    """
    ensaio.borda["daemon"] = True

    assert ensaio.main(ESCREVER) == 2
    assert ensaio.borda["abriu"] == [] and ensaio.borda["escritos"] == []


def test_o_ensaio_para_sem_o_ouvido_dela(ensaio: Any) -> None:
    """Sem ``--eu-estou-ouvindo``, rc=3 e nada é aberto."""
    assert ensaio.main(["--escrever", "--exigir-mac", MAC]) == 3
    assert ensaio.borda["abriu"] == []


def test_o_ensaio_recusa_sem_o_endereco_conferido(ensaio: Any) -> None:
    assert ensaio.main(["--escrever", "--eu-estou-ouvindo"]) == 2
    assert ensaio.main(["--escrever", "--exigir-mac", "aa:bb:cc:00:00:09",
                        "--eu-estou-ouvindo"]) == 2
    assert ensaio.borda["abriu"] == []


def test_o_ensaio_manda_o_relatorio_combinado_a_um_controle(ensaio: Any) -> None:
    """Com tudo de pé, ele escreve ``0x36`` com os quatro blocos, contador andando um."""
    assert ensaio.main(ESCREVER) == 0

    escritos = ensaio.borda["escritos"]
    assert ensaio.borda["abriu"] == ["/dev/hidraw-de-mentira"]
    assert len(escritos) >= 3, f"em 0,1 s saíram {len(escritos)} relatórios"
    for i, relatorio in enumerate(escritos):
        assert [b for _p, b, _t, _d in _cadeia(relatorio)] == [0x11, 0x10, 0x12, 0x13]
        assert relatorio[10] == i & 0xFF
        assert _crc_certo(relatorio)


def test_a_onda_do_lado_esquerdo_vai_so_no_canal_3(ensaio: Any) -> None:
    """``--lado esquerdo`` põe a onda só no primeiro canal do par (o canal 3)."""
    bloco = ensaio.onda_por_bloco(120.0, "esquerdo")()
    assert len(bloco) == 64
    assert any(bloco[0::2]) and not any(bloco[1::2])
    centro = ensaio.onda_por_bloco(120.0, "centro")()
    assert centro[0::2] == centro[1::2]


def test_nao_sei_se_o_daemon_esta_no_ar_e_recusa(monkeypatch: pytest.MonkeyPatch) -> None:
    """«Não sei» nunca é «parado»: só o socket ausente ou recusando libera o ensaio.

    O ``daemon.status`` tem 0,25 s; o daemon ocupado não responde a tempo, e a
    pergunta que propaga um erro inesperado também não. Nos dois, o ensaio
    escrevia no hidraw que o daemon escreve.

    MORDIDA: devolver False no erro ou sem resposta do ``daemon.status``
    (a pergunta do ``test trigger --raw`` sozinha) e o ensaio vê o daemon
    ocupado como parado.
    """
    import shutil
    import socket
    import tempfile

    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.utils import xdg_paths

    modulo = _carregar_o_ensaio()
    pasta = Path(tempfile.mkdtemp(prefix="ens", dir="/tmp"))
    caminho = pasta / "s"
    monkeypatch.setattr(xdg_paths, "ipc_socket_path", lambda: caminho)
    monkeypatch.setattr(ipc_bridge, "daemon_status_basic", lambda: None)
    try:
        assert modulo.daemon_no_ar() is False, "sem socket, o daemon está parado"

        ouvinte = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ouvinte.bind(str(caminho))
        ouvinte.listen(1)
        assert modulo.daemon_no_ar() is True, "alguém aceita a conexão: pode estar no ar"
        ouvinte.close()
        assert modulo.daemon_no_ar() is False, "o socket que sobrou de um daemon morto"

        def _quebra() -> None:
            raise RuntimeError("defeito na pergunta")

        monkeypatch.setattr(ipc_bridge, "daemon_status_basic", _quebra)
        assert modulo.daemon_no_ar() is True, "o erro inesperado virou «parado»"
        monkeypatch.setattr(ipc_bridge, "daemon_status_basic", lambda: {"ok": True})
        assert modulo.daemon_no_ar() is True
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_o_ensaio_recusa_com_a_bancada_tomada(
    ensaio: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`bancada.sh exigir` com rc≠0 (outra reserva viva): rc=2 e nada é aberto."""
    monkeypatch.setattr(ensaio, "_exigir_bancada", lambda: (False, "BANCADA OCUPADA"))

    assert ensaio.main(ESCREVER) == 2
    assert ensaio.borda["abriu"] == [] and ensaio.borda["escritos"] == []


# O SEGUNDO TEMPO: a ponte com UM escritor por controle.


class _Codificador:
    """O Opus de mentira: a régua não depende da libopus da máquina."""

    def codificar(self, _pcm: bytes) -> bytes:
        return bytes(range(1, 181))


def _motor(n: int) -> bytes:
    """PCM de quatro canais com sinal só nos motores (canais 3 e 4)."""
    import struct

    return struct.pack("<4h", 0, 0, 16000, -16000) * (n // 8)


def _voz(n: int) -> bytes:
    import struct

    return struct.pack("<2h", 9000, -9000) * (n // 4)


def _bomba_do_controle(**kw: Any) -> tuple[Any, list[bytes]]:
    escritas: list[bytes] = []

    def _escrever(relatorio: bytes) -> int:
        escritas.append(relatorio)
        return len(relatorio)

    kw.setdefault("fonte", _voz)
    bomba = af.BombaDeSomPeloRadio(
        escritor=_escrever, seco=False, codificador=_Codificador(), so_com_sinal=True, **kw
    )
    return bomba, escritas


def test_som_e_haptica_juntos_vao_num_relatorio_por_quadro_com_o_0x10() -> None:
    """A régua 2 da sprint: os dois pedidos no mesmo controle saem no MESMO relatório.

    MORDIDA: a bomba que monta um relatório por papel (o ``0x35`` e o ``0x32``
    de antes), ou que larga o ``0x10``, reprova aqui.
    """
    bomba, escritas = _bomba_do_controle(fonte_haptica=_motor)
    for _ in range(5):
        assert bomba.escrever(bomba.um_report() or b"")
    assert len(escritas) == 5, "um relatório por quadro, e só um"
    for relatorio in escritas:
        cadeia = _cadeia(relatorio)
        assert relatorio[0] == af.DEGRAU_COMBINADO
        assert [(pos, bloco) for pos, bloco, _n, _d in cadeia] == [
            (2, 0x11), (11, 0x10), (76, 0x12), (142, 0x13)
        ], cadeia
        assert _crc_certo(relatorio)
    assert [r[10] for r in escritas] == list(range(len(escritas))), (
        "o contador do 0x11 é UM e anda um por relatório"
    )
    assert bomba.contagem.reports_montados == len(escritas)
    assert bomba.contagem.hapticos_no_fio == len(escritas)
    assert bomba.contagem.quadros_opus == len(escritas)


def test_a_haptica_que_o_portao_tira_fecha_com_o_silencio_e_o_som_segue() -> None:
    """``leva_a_haptica`` cai no meio: vai UM bloco de silêncio e o som segue sozinho."""
    from hefesto_dualsense4unix.integrations.haptica_bt import bloco_de_silencio

    leva = [True]
    bomba, escritas = _bomba_do_controle(fonte_haptica=_motor, leva_a_haptica=lambda: leva[0])
    for _ in range(2):
        bomba.escrever(bomba.um_report() or b"")
    leva[0] = False
    for _ in range(3):
        bomba.escrever(bomba.um_report() or b"")
    blocos = [[b for _p, b, _n, _d in _cadeia(r)] for r in escritas]
    assert blocos[:2] == [[0x11, 0x10, 0x12, 0x13]] * 2
    assert blocos[2] == [0x11, 0x10, 0x12, 0x13], "o motor tinha de parar no zero"
    assert _cadeia(escritas[2])[2][3] == bloco_de_silencio()
    assert blocos[3:] == [[0x11, 0x10, 0x13]] * 2, "a háptica seguiu no fio sem o portão"


def test_a_ponte_nao_tem_mais_dois_escritores() -> None:
    """Os escritores ``0x35`` e ``0x32`` por controle saíram, sem interruptor.

    MORDIDA: devolver ``ARRANJO_HAPTICA_032`` ou o parâmetro ``arranjo`` da
    ponte reprova.
    """
    import inspect

    assert not hasattr(af, "ARRANJO_HAPTICA_032")
    assert not hasattr(af, "ARRANJO_PADRAO")
    assert "arranjo" not in inspect.signature(af.PonteDeSomPorRadio).parameters
    assert "arranjo" not in inspect.signature(af.BombaDeSomPeloRadio).parameters
