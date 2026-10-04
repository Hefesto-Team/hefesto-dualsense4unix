"""MIC-DA-MESA-ELEICAO-01 — dois controles nunca partilham o nome do nó.

O buraco medido em 01/09/2026: `NoDualSenseBT.nome_curto` devolvia os seis
últimos dígitos hex do endereço, e dois controles com os três últimos octetos
iguais geravam o mesmo `source_name` e o mesmo fifo; `PontePyDualSenseBT.iniciar()`
faz `os.unlink` do fifo, e a segunda ponte apagava a primeira. Com a eleição
por `uniq`, `escolher_fonte` resolveria os dois controles para a mesma source.

Fechado em 03/10/2026 (OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01): o nome curto é
a marca do aparelho, uma HMAC dos doze dígitos com chave da máquina. Esta régua
era um `xfail(strict=True)` à espera da cura; agora é a régua da cura.
"""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import NoDualSenseBT


def _no(uniq: str, caminho: str) -> NoDualSenseBT:
    return NoDualSenseBT(caminho=caminho, uniq=uniq, produto=0x0CE6)


def test_dois_controles_com_o_rabo_igual_nao_podem_gerar_o_mesmo_nome() -> None:
    """Dois MACs distintos, mesmos três últimos octetos: nomes TÊM de diferir."""
    a = _no("aa:bb:cc:00:00:01", "/dev/hidraw3")
    b = _no("02:fe:00:00:00:01", "/dev/hidraw4")

    assert a.uniq != b.uniq, "são dois controles diferentes"
    assert a.nome_curto != b.nome_curto, (
        "mesmo nome de source e mesmo fifo — a segunda ponte apaga a primeira"
    )

