"""Testes do `scripts/ensaios/entrada_em_repouso.py` — o instrumento da FRENTE A."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "ensaios" / "entrada_em_repouso.py"


@pytest.fixture(scope="module")
def mod():
    """Importa o instrumento pelo caminho, como a casa já faz com os scripts."""
    if not INSTRUMENTO.exists():  # pragma: no cover - só se alguém apagar o arquivo
        pytest.skip("o instrumento não está na árvore")
    sys.path.insert(0, str(INSTRUMENTO.parent))
    sys.path.insert(0, str(RAIZ / "scripts"))
    spec = importlib.util.spec_from_file_location("entrada_em_repouso", INSTRUMENTO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def corpo_de_mentira(
    *, seq: int = 0x9B, status0: int = 0x28, botoes0: int = 0x08, ts: int = 123456
) -> bytes:
    corpo = bytearray(63)
    corpo[0:4] = bytes((127, 124, 130, 129))
    corpo[4] = 0
    corpo[5] = 0
    corpo[6] = seq
    corpo[7] = botoes0
    corpo[27:31] = ts.to_bytes(4, "little")
    corpo[52] = status0
    return bytes(corpo)


def quadro_do_cabo(corpo: bytes) -> bytes:
    """Report `0x01`, 64 B: id + corpo. O corpo começa em `data[1]`."""
    return bytes([0x01]) + corpo


def quadro_do_radio(corpo: bytes, *, contador: int = 6) -> bytes:
    """Report `0x31`, 78 B: id + `data[1]` + corpo + enchimento + CRC."""
    cabeca = bytes([0x31, ((contador & 0x0F) << 4) | 0x01])
    return (cabeca + corpo).ljust(78, b"\x00")


def test_o_mesmo_corpo_no_cabo_e_no_radio_decodifica_igual(mod):
    """A cura: o offset sai do ID do report, nunca é fixo."""
    corpo = corpo_de_mentira()
    do_cabo, off_cabo = mod.corpo_do_quadro(quadro_do_cabo(corpo))
    do_radio, off_radio = mod.corpo_do_quadro(quadro_do_radio(corpo))

    assert off_cabo == 1
    assert off_radio == 2
    assert do_cabo == do_radio == corpo
    for _nome, i in mod.STICKS:
        assert do_cabo[i] == do_radio[i] == corpo[i]


def test_quadro_que_nao_e_entrada_de_dualsense_e_recusado(mod):
    """Nada de decodificar o que não se sabe o que é."""
    with pytest.raises(mod.QuadroDesconhecidoError):
        mod.corpo_do_quadro(b"")
    with pytest.raises(mod.QuadroDesconhecidoError):
        mod.corpo_do_quadro(bytes([0x31]) + b"\x00" * 9)
    with pytest.raises(mod.QuadroDesconhecidoError):
        mod.corpo_do_quadro(bytes([0x02]) + b"\x00" * 62)


def test_no_radio_o_contador_vivo_nao_e_o_do_corpo(mod):
    """A cura que salva o CONTROLE POSITIVO de aprovar um fluxo morto."""
    vivos = [
        quadro_do_radio(corpo_de_mentira(seq=0x01, ts=1000 + n), contador=n % 16)
        for n in range(8)
    ]

    assert [mod.contador_do_quadro(q) for q in vivos] == list(range(8))
    assert mod.passo_do_contador(vivos[0]) == 16
    assert mod.passo_do_contador(quadro_do_cabo(corpo_de_mentira())) == 256

    coleta = mod.Coleta(aparelho=_aparelho_de_mentira(mod, "hidraw9", mod.RADIO))
    for q in vivos:
        coleta.engole(q)
    assert coleta.contador_andou == 7
    assert coleta.contador_parado == 0
    assert coleta.fluxo_vivo is True


def test_fluxo_morto_no_radio_reprova_o_controle_positivo(mod):
    """O outro lado do mesmo par: quadro repetido tem de REPROVAR."""
    corpo = corpo_de_mentira(seq=0x01)
    coleta = mod.Coleta(aparelho=_aparelho_de_mentira(mod, "hidraw9", mod.RADIO))
    for _ in range(8):
        coleta.engole(quadro_do_radio(corpo, contador=6))
    assert coleta.contador_parado == 7
    assert coleta.fluxo_vivo is False


def test_o_controle_negativo_pega_a_mao_na_mesa(mod):
    """Botão que se mexe na janela invalida a medida de repouso."""
    ap = _aparelho_de_mentira(mod, "hidraw8", mod.CABO)
    limpa = mod.Coleta(aparelho=ap)
    for n in range(4):
        limpa.engole(quadro_do_cabo(corpo_de_mentira(seq=n, ts=1000 + n)))
    assert limpa.botoes_em_repouso is True
    assert limpa.status_parado is True

    suja = mod.Coleta(aparelho=ap)
    for n in range(3):
        suja.engole(quadro_do_cabo(corpo_de_mentira(seq=n, ts=1000 + n)))
    suja.engole(quadro_do_cabo(corpo_de_mentira(seq=3, ts=1003, botoes0=0x08 | 0x20)))
    assert suja.botoes_em_repouso is False


@pytest.mark.parametrize(
    ("status0", "esperado"),
    [
        (0x07, (75, "Discharging")),
        (0x19, (95, "Charging")),
        (0x28, (100, "Full")),
        (0x1A, (100, "Charging")),
        (0x00, (5, "Discharging")),
    ],
)
def test_a_conta_da_bateria_e_a_do_driver(mod, status0, esperado):
    """`nibble * 10 + 5`, limitado a 100 — `hid-playstation.c:1724`."""
    assert mod.bateria_do_status(status0) == esperado


def test_estado_de_erro_nao_inventa_capacidade(mod):
    """`0xF` é erro; devolver 0% ali seria inventar um número que não existe."""
    capacidade, estado = mod.bateria_do_status(0xF3)
    assert capacidade is None
    assert estado == "erro"


def test_o_casamento_nao_depende_de_ordem_nem_de_nome(mod):
    """Regra de produto: nada pode depender de MAC nem de ordem de conexão."""
    fisicos = {
        "hidraw10": (128, 128, 129, 128),
        "hidraw8": (127, 124, 130, 129),
        "hidraw4": (127, 130, 129, 125),
        "hidraw5": (127, 129, 128, 127),
    }
    vpads = {
        "hidraw11": (128, 128, 129, 128),
        "hidraw7": (127, 128, 130, 129),
        "hidraw9": (127, 130, 129, 125),
        "hidraw6": (127, 129, 128, 127),
    }
    esperado = {
        "hidraw11": "hidraw10",
        "hidraw7": "hidraw8",
        "hidraw9": "hidraw4",
        "hidraw6": "hidraw5",
    }

    pares, nota = mod.casar_por_assinatura(fisicos, vpads)
    assert {p.vpad: p.fisico for p in pares} == esperado
    assert all(p.unico for p in pares)
    assert "ÚNICO" in nota

    ao_contrario = mod.casar_por_assinatura(
        dict(reversed(list(fisicos.items()))),
        dict(reversed(list(vpads.items()))),
    )[0]
    assert {p.vpad: p.fisico for p in ao_contrario} == esperado


def test_duas_unidades_com_o_mesmo_centro_saem_como_ambiguas(mod):
    """Empate vira `ambíguo`, nunca palpite."""
    iguais = {"a": (128, 128, 128, 128), "b": (128, 128, 128, 128)}
    vpads = {"v1": (128, 128, 128, 128), "v2": (128, 128, 128, 128)}
    pares, nota = mod.casar_por_assinatura(iguais, vpads)
    assert pares
    assert not any(p.unico for p in pares)
    assert "AMBÍGUO" in nota


def test_a_bateria_confirma_o_casamento_e_se_cala_quando_empata(mod):
    """A segunda régua só fala quando tem o que dizer."""
    fisicos = {"f1": (75, "Discharging"), "f2": (100, "Full"), "f3": (100, "Full")}
    vpads = {"v1": (75, "Discharging"), "v2": (100, "Charging"), "v3": (100, "Charging")}
    casados = mod.casar_por_bateria(fisicos, vpads)
    assert casados == {"v1": "f1"}


def _aparelho_de_mentira(mod, hidraw: str, transporte: str):
    return mod.Aparelho(
        hidraw=hidraw,
        caminho_hidraw=f"/dev/{hidraw}",
        dir_device="",
        mac="00:00:00:00:00:00",
        nome="DualSense de mentira",
        transporte=transporte,
        e_vpad=False,
        rotulo="",
    )
