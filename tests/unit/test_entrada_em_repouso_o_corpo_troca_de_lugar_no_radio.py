"""Testes do `scripts/ensaios/entrada_em_repouso.py` — o instrumento da FRENTE A.

Um instrumento de medição é código que produz NÚMERO, e um número errado é pior
que nenhum: ele entra no mapa, vira decisão, e ninguém desconfia. Estes testes
prendem as quatro curas de que o veredito depende — e cada uma delas nasceu de
uma armadilha real desta casa, não de imaginação:

1. **O corpo do report troca de lugar conforme o transporte** (`data[1]` no
   cabo, `data[2]` no rádio). Fixar o offset produz, no rádio, sticks
   plausíveis e ERRADOS — o alarme convincente e falso de sempre.
2. **O contador de sequência também troca de lugar.** No rádio o `seq_number`
   do corpo fica congelado em `0x01` e quem conta é o nibble alto do `data[1]`.
   Ler o do corpo faz o controle POSITIVO ("o fluxo está vivo") passar em cima
   de um fluxo morto, que é o pior modo de falha possível num controle
   positivo.
3. **A bateria é a régua do OUTRO observador.** Se a conta do byte não for a
   mesma do driver, ela nunca vai bater com o `sysfs`, e o instrumento perde a
   única confirmação independente que tem do próprio offset.
4. **O casamento vpad<->físico não pode depender de MAC nem de ordem** (regra
   dela, universalidade), e ambiguidade tem de sair como ambiguidade, nunca
   como palpite.

PROVA DE QUE MORDEM (arrancar, ver reprovar, devolver) — 15/08/2026, no espelho
da árvore, uma cura de cada vez. O que cada arrancamento derrubou está escrito
na docstring do teste correspondente.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "ensaios" / "entrada_em_repouso.py"


@pytest.fixture(scope="module")
def mod():
    """Importa o instrumento pelo caminho, como a casa já faz com os scripts.

    O `sys.path` ganha a pasta dos ensaios porque o instrumento importa
    `comum`, que por sua vez importa o cliente do broker de `src/` — e é assim
    que ele roda de verdade.
    """
    if not INSTRUMENTO.exists():  # pragma: no cover - só se alguém apagar o arquivo
        pytest.skip("o instrumento não está na árvore")
    sys.path.insert(0, str(INSTRUMENTO.parent))
    sys.path.insert(0, str(RAIZ / "scripts"))
    spec = importlib.util.spec_from_file_location("entrada_em_repouso", INSTRUMENTO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    # Registrar ANTES de executar: o instrumento usa `dataclass` com
    # `from __future__ import annotations`, e o `dataclasses` resolve os tipos
    # olhando `sys.modules[cls.__module__]`. Sem esta linha o import estoura
    # com um `AttributeError` que não tem nada a ver com o que se quer testar.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


# ---------------------------------------------------------------------------
# Quadros de mentira, montados a partir do MESMO corpo
# ---------------------------------------------------------------------------

#: Um corpo de 63 bytes com valores reconhecíveis em cada campo que importa.
#: Os números dos sticks são os do `aa:bb:cc:00:00:ab` medido em 15/08/2026 —
#: escolhidos porque o `LY = 124` é o caso que revelou o defeito do vpad.
def corpo_de_mentira(
    *, seq: int = 0x9B, status0: int = 0x28, botoes0: int = 0x08, ts: int = 123456
) -> bytes:
    corpo = bytearray(63)
    corpo[0:4] = bytes((127, 124, 130, 129))  # LX, LY, RX, RY
    corpo[4] = 0  # L2
    corpo[5] = 0  # R2
    corpo[6] = seq
    corpo[7] = botoes0
    corpo[27:31] = ts.to_bytes(4, "little")  # sensor_timestamp
    corpo[52] = status0
    return bytes(corpo)


def quadro_do_cabo(corpo: bytes) -> bytes:
    """Report `0x01`, 64 B: id + corpo. O corpo começa em `data[1]`."""
    return bytes([0x01]) + corpo


def quadro_do_radio(corpo: bytes, *, contador: int = 6) -> bytes:
    """Report `0x31`, 78 B: id + `data[1]` + corpo + enchimento + CRC.

    O `data[1]` é `(contador << 4) | 1` — a forma medida no aparelho em
    15/08/2026, com o nibble alto andando de um em um a cada quadro e o nibble
    baixo fixo em 1.
    """
    cabeca = bytes([0x31, ((contador & 0x0F) << 4) | 0x01])
    return (cabeca + corpo).ljust(78, b"\x00")


# ---------------------------------------------------------------------------
# 1. O corpo troca de lugar com o transporte
# ---------------------------------------------------------------------------


def test_o_mesmo_corpo_no_cabo_e_no_radio_decodifica_igual(mod):
    """A cura: o offset sai do ID do report, nunca é fixo.

    ARRANCAR: em `corpo_do_quadro`, trocar o ramo do rádio por `off = 1` (o
    mesmo do cabo). REPROVA aqui: o corpo do rádio volta deslocado de um byte e
    `LX` deixa de ser 127 — vira o `data[1]` do envelope, que é um número
    perfeitamente plausível para um stick e completamente falso.
    """
    corpo = corpo_de_mentira()
    do_cabo, off_cabo = mod.corpo_do_quadro(quadro_do_cabo(corpo))
    do_radio, off_radio = mod.corpo_do_quadro(quadro_do_radio(corpo))

    assert off_cabo == 1
    assert off_radio == 2
    assert do_cabo == do_radio == corpo
    # E o que o relatório de fato lê: os quatro sticks, nos dois braços.
    for _nome, i in mod.STICKS:
        assert do_cabo[i] == do_radio[i] == corpo[i]


def test_quadro_que_nao_e_entrada_de_dualsense_e_recusado(mod):
    """Nada de decodificar o que não se sabe o que é.

    Um report `0x31` CURTO (o do modo básico do Bluetooth, 10 B) não carrega o
    corpo inteiro: aceitá-lo produziria stick lido de lixo além do fim do
    quadro. Aceitar em silêncio é o defeito; recusar alto é a cura.
    """
    with pytest.raises(mod.QuadroDesconhecidoError):
        mod.corpo_do_quadro(b"")
    with pytest.raises(mod.QuadroDesconhecidoError):
        mod.corpo_do_quadro(bytes([0x31]) + b"\x00" * 9)
    with pytest.raises(mod.QuadroDesconhecidoError):
        mod.corpo_do_quadro(bytes([0x02]) + b"\x00" * 62)


# ---------------------------------------------------------------------------
# 2. O contador de sequência também troca de lugar
# ---------------------------------------------------------------------------


def test_no_radio_o_contador_vivo_nao_e_o_do_corpo(mod):
    """A cura que salva o CONTROLE POSITIVO de aprovar um fluxo morto.

    Medido em 15/08/2026, nas duas unidades que estavam no rádio: o
    `seq_number` do corpo fica CONGELADO em `0x01` em todos os milhares de
    quadros, e quem anda é o nibble alto do `data[1]`. Um instrumento que
    perguntasse "o `corpo[6]` andou?" concluiria que o rádio entrega quadro
    repetido — e um que perguntasse "algum byte andou?" aprovaria qualquer
    coisa.

    ARRANCAR: fazer `contador_do_quadro` devolver sempre `quadro[CORPO_CABO +
    SEQ]`. REPROVA aqui: o fluxo de rádio, que ANDA, passa a contar
    `contador_parado` e `fluxo_vivo` cai para falso — o controle positivo
    reprova um aparelho são.
    """
    # o `seq` fica no valor CONGELADO medido no aparelho; só o carimbo do
    # envelope e o relógio do controle andam, que é o que o rádio faz de fato.
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
    """O outro lado do mesmo par: quadro repetido tem de REPROVAR.

    Sem este, o teste acima seria satisfeito por um `fluxo_vivo` que devolvesse
    `True` sempre — um controle positivo que aprova tudo não controla nada.
    """
    corpo = corpo_de_mentira(seq=0x01)
    coleta = mod.Coleta(aparelho=_aparelho_de_mentira(mod, "hidraw9", mod.RADIO))
    for _ in range(8):
        coleta.engole(quadro_do_radio(corpo, contador=6))  # o MESMO quadro, sempre
    assert coleta.contador_parado == 7
    assert coleta.fluxo_vivo is False


def test_o_controle_negativo_pega_a_mao_na_mesa(mod):
    """Botão que se mexe na janela invalida a medida de repouso.

    ARRANCAR: fazer `botoes_em_repouso` devolver `True` sempre. REPROVA aqui —
    e no relatório o efeito seria pior que uma reprovação: um aperto de botão
    entraria na conta da deriva como se fosse chiado do silício.
    """
    ap = _aparelho_de_mentira(mod, "hidraw8", mod.CABO)
    limpa = mod.Coleta(aparelho=ap)
    for n in range(4):
        limpa.engole(quadro_do_cabo(corpo_de_mentira(seq=n, ts=1000 + n)))
    assert limpa.botoes_em_repouso is True
    assert limpa.status_parado is True

    suja = mod.Coleta(aparelho=ap)
    for n in range(3):
        suja.engole(quadro_do_cabo(corpo_de_mentira(seq=n, ts=1000 + n)))
    # o xis apertado: `DS_BUTTONS0_CROSS` é o BIT(4+1) de `buttons[0]`
    suja.engole(quadro_do_cabo(corpo_de_mentira(seq=3, ts=1003, botoes0=0x08 | 0x20)))
    assert suja.botoes_em_repouso is False


# ---------------------------------------------------------------------------
# 3. A bateria — a régua do outro observador
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status0", "esperado"),
    [
        (0x07, (75, "Discharging")),   # medido: aa:bb:cc:00:00:d8, e o sysfs diz 75
        (0x19, (95, "Charging")),      # medido: aa:bb:cc:00:00:f0, e o sysfs diz 95
        (0x28, (100, "Full")),         # medido: aa:bb:cc:00:00:ab, e o sysfs diz 100
        (0x1A, (100, "Charging")),     # 10*10+5 = 105, GRAMPEADO em 100
        (0x00, (5, "Discharging")),    # nibble 0 é 5%, não 0% — a conta é do driver
    ],
)
def test_a_conta_da_bateria_e_a_do_driver(mod, status0, esperado):
    """`nibble * 10 + 5`, limitado a 100 — `hid-playstation.c:1724`.

    ARRANCAR: trocar por `nibble * 10` (o erro natural de quem lê a fórmula
    depressa). REPROVA em todas as linhas, e no relatório o efeito seria
    silencioso e caro: a coluna "bate com o sysfs?" passaria a dizer NÃO em
    todos os nós, e a próxima pessoa iria caçar defeito no aparelho.
    """
    assert mod.bateria_do_status(status0) == esperado


def test_estado_de_erro_nao_inventa_capacidade(mod):
    """`0xF` é erro; devolver 0% ali seria inventar um número que não existe."""
    capacidade, estado = mod.bateria_do_status(0xF3)
    assert capacidade is None
    assert estado == "erro"


# ---------------------------------------------------------------------------
# 4. O casamento vpad <-> físico: universal, e honesto quando não sabe
# ---------------------------------------------------------------------------


def test_o_casamento_nao_depende_de_ordem_nem_de_nome(mod):
    """Regra dela: nada pode depender de MAC nem de ordem de conexão.

    As assinaturas abaixo são as MEDIDAS em 15/08/2026, às 22h15, com a mesa
    2+2 de pé. Os nomes dos nós entram embaralhados de propósito: o resultado
    tem de ser o mesmo, porque o que casa é o silício e não a enumeração.
    """
    fisicos = {
        "hidraw10": (128, 128, 129, 128),  # aa:bb:cc:00:00:03, cabo
        "hidraw8": (127, 124, 130, 129),   # aa:bb:cc:00:00:ab, cabo
        "hidraw4": (127, 130, 129, 125),   # aa:bb:cc:00:00:f0, rádio
        "hidraw5": (127, 129, 128, 127),   # aa:bb:cc:00:00:d8, rádio
    }
    vpads = {
        "hidraw11": (128, 128, 129, 128),  # P4
        "hidraw7": (127, 128, 130, 129),   # P2 — o LY vem trocado pelo produto
        "hidraw9": (127, 130, 129, 125),   # P3
        "hidraw6": (127, 129, 128, 127),   # P1
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

    # A MESMA mesa, com os dicionários montados em outra ordem de inserção.
    ao_contrario = mod.casar_por_assinatura(
        dict(reversed(list(fisicos.items()))),
        dict(reversed(list(vpads.items()))),
    )[0]
    assert {p.vpad: p.fisico for p in ao_contrario} == esperado


def test_duas_unidades_com_o_mesmo_centro_saem_como_ambiguas(mod):
    """Empate vira `ambíguo`, nunca palpite.

    ARRANCAR: em `casar_por_assinatura`, tirar a checagem de unicidade e
    devolver sempre `unico=True`. REPROVA aqui — e no mapa isso viraria um par
    vpad<->MAC afirmado sem prova, que é exatamente o tipo de linha que a casa
    passa semanas desfazendo.
    """
    iguais = {"a": (128, 128, 128, 128), "b": (128, 128, 128, 128)}
    vpads = {"v1": (128, 128, 128, 128), "v2": (128, 128, 128, 128)}
    pares, nota = mod.casar_por_assinatura(iguais, vpads)
    assert pares
    assert not any(p.unico for p in pares)
    assert "AMBÍGUO" in nota


def test_a_bateria_confirma_o_casamento_e_se_cala_quando_empata(mod):
    """A segunda régua só fala quando tem o que dizer.

    Duas unidades a 100% não se separam pela bateria, e forçar um desempate ali
    transformaria a régua de CONFIRMAÇÃO em mais um palpite — o instrumento
    passaria a concordar consigo mesmo por construção.
    """
    fisicos = {"f1": (75, "Discharging"), "f2": (100, "Full"), "f3": (100, "Full")}
    vpads = {"v1": (75, "Discharging"), "v2": (100, "Charging"), "v3": (100, "Charging")}
    casados = mod.casar_por_bateria(fisicos, vpads)
    assert casados == {"v1": "f1"}


# ---------------------------------------------------------------------------


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
