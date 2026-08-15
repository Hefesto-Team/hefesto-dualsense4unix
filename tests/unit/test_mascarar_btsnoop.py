"""O mascarador de captura binária, e a mordida que prova que o portão morde.

Este arquivo cobre três coisas, e a terceira é a que justifica as outras duas:

1. ``scripts/mascarar_btsnoop.py`` acha o MAC nas DUAS ordens de byte, mascara
   preservando o tamanho, e se RECUSA a escrever quando não pode fazer isso.
2. As três cópias da lista de OUI real — o portão, o mascarador e o bloco em
   ``check_anonymity.sh`` — são a MESMA lista. Duas listas que divergem em
   silêncio são a família do BURACO-DO-PORTÃO-01: controle novo entra na
   bancada, o OUI entra num lugar só, o outro lugar segue cego.
3. **A MORDIDA.** Um ``.btsnoop`` sintético com endereço real em little-endian
   é escrito na árvore; o portão de TEXTO passa verde (é justamente o buraco), o
   portão de BYTES reprova, o mascarador cura, e o portão volta a passar.

Medido em 15/08/2026, com o arquivo sintético em
``docs/data/ensaios-brutos/``, e é a mensagem literal do portão:

    MAC de hardware REAL gravado em BINÁRIO. Nenhum portão de texto o vê.
    Passe o arquivo por `scripts/mascarar_btsnoop.py` (captura HCI) ou zere os
    octetos 4 e 5 dos seis bytes apontados:
      docs/data/ensaios-brutos/MORDIDA-sintetica.btsnoop: offset 42
      (little-endian): MAC real em bytes, sem máscara (<endereço do adaptador>)

Nenhum endereço real aparece escrito aqui: tudo é montado a partir de
``_OUIS_REAIS_OCTETOS`` com sufixo inventado, porque este arquivo é varrido
pelos portões que ele testa.
"""
from __future__ import annotations

import importlib.util
import re
import struct
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_docs_mac_anonimato import (
    _OUIS_REAIS_OCTETOS,
    MAC_COMPLETO_RE,
    _ocorrencias_binarias,
)

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "mascarar_btsnoop.py"
CHECK_SH = RAIZ / "scripts" / "check_anonymity.sh"

#: Sufixo INVENTADO. Não é de aparelho nenhum desta casa; serve só para ter
#: octetos 4 e 5 diferentes de zero, que é o que a máscara tem de apagar.
SUFIXO_FORJADO = (0x11, 0x22, 0x33)


@pytest.fixture(scope="module")
def mascarador() -> Any:
    spec = importlib.util.spec_from_file_location("_mascarar_btsnoop", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # O `@dataclass` do script procura o módulo em `sys.modules` para resolver
    # as anotações; sem esta linha o `exec_module` estoura com AttributeError e
    # a suíte reporta ERRO em vez de falha de conteúdo.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _mac_forjado(indice: int = 0) -> bytes:
    """Seis octetos: um OUI REAL da lista + o sufixo inventado."""
    oui = bytes(int(o, 16) for o in _OUIS_REAIS_OCTETOS[indice])
    return oui + bytes(SUFIXO_FORJADO)


def _btsnoop(payloads: list[bytes]) -> bytes:
    """Um `.btsnoop` válido e mínimo: cabeçalho de 16 B + N registros."""
    saida = b"btsnoop\x00" + struct.pack(">II", 1, 1002)
    for payload in payloads:
        saida += struct.pack(
            ">IIIIq", len(payload), len(payload), 0, 0, 0
        ) + payload
    return saida


# ---------------------------------------------------------------------------
# 2. As três listas de OUI não podem divergir
# ---------------------------------------------------------------------------

def test_a_lista_de_ouis_do_mascarador_e_a_mesma_do_portao(mascarador: Any) -> None:
    """Espelho, não cópia solta.

    Para arrancar e ver morder: acrescente um OUI em
    ``scripts/mascarar_btsnoop.py`` e não em
    ``tests/unit/test_docs_mac_anonimato.py``.
    """
    assert mascarador._OUIS_REAIS_OCTETOS == _OUIS_REAIS_OCTETOS


def test_a_lista_de_ouis_do_check_anonymity_e_a_mesma_do_portao() -> None:
    """O terceiro espelho mora dentro de um heredoc de shell, e é o mais fácil
    de esquecer justamente por isso.

    Para arrancar e ver morder: tire um OUI da tupla ``OUIS`` do bloco de
    varredura binária de ``scripts/check_anonymity.sh``.
    """
    texto = CHECK_SH.read_text(encoding="utf-8")
    bloco = re.search(r"OUIS = \((?P<corpo>[^)]*)\)", texto)
    assert bloco is not None, (
        "não achei a tupla OUIS da varredura binária em check_anonymity.sh"
    )
    do_shell = tuple(re.findall(r'"([0-9a-f]{6})"', bloco.group("corpo")))
    do_portao = tuple("".join(o) for o in _OUIS_REAIS_OCTETOS)
    assert do_shell == do_portao


# ---------------------------------------------------------------------------
# 1. O mascarador
# ---------------------------------------------------------------------------

def test_acha_o_mac_nas_duas_ordens_de_byte(mascarador: Any) -> None:
    """A régua da casa: procurar numa ordem só é o defeito, não a solução."""
    mac = _mac_forjado()
    dados = _btsnoop([b"\x04\x0e" + mac + b"\x00", b"\x04\x0e" + mac[::-1] + b"\x00"])

    achados = mascarador.ocorrencias(dados)
    ordens = sorted(o.ordem for o in achados)
    assert ordens == ["big-endian", "little-endian"], (
        f"a busca tem de ver as duas ordens; viu {ordens}"
    )
    assert all(not o.mascarado for o in achados)


def test_mascara_zera_os_octetos_4_e_5_e_preserva_o_tamanho(mascarador: Any) -> None:
    mac = _mac_forjado()
    dados = _btsnoop([b"\x04\x0e" + mac + b"\x00", b"\x04\x0e" + mac[::-1] + b"\x00"])

    saida, achados = mascarador.mascarar(dados)

    assert len(saida) == len(dados), "tamanho do .btsnoop não pode mudar"
    assert len(achados) == 2
    # Exatamente quatro bytes mudaram: dois por ocorrência.
    diferentes = [i for i in range(len(dados)) if dados[i] != saida[i]]
    assert len(diferentes) == 4
    # E o que sobrou é a máscara da casa: OUI e último octeto de pé.
    assert mascarador.cruas(saida) == []
    oui = bytes(int(o, 16) for o in _OUIS_REAIS_OCTETOS[0])
    assert oui + b"\x00\x00" + bytes([SUFIXO_FORJADO[2]]) in saida
    assert bytes([SUFIXO_FORJADO[2]]) + b"\x00\x00" + oui[::-1] in saida


def test_o_formato_e_lido_de_verdade_e_o_cabecalho_nao_e_tocado(
    mascarador: Any,
) -> None:
    """16 bytes de cabeçalho + 24 por registro: as faixas de dados são exatas."""
    payloads = [b"a" * 7, b"b" * 3]
    dados = _btsnoop(payloads)
    faixas = mascarador.faixas_de_payload(dados)
    assert faixas == [(16 + 24, 16 + 24 + 7), (16 + 24 + 7 + 24, 16 + 24 + 7 + 24 + 3)]
    for inicio, fim in faixas:
        assert dados[inicio:fim] in payloads


def test_recusa_arquivo_que_nao_e_btsnoop(mascarador: Any) -> None:
    with pytest.raises(mascarador.BtsnoopInvalidoError, match="assinatura"):
        mascarador.mascarar(b"nada disso aqui e uma captura de radio")


def test_recusa_registro_truncado(mascarador: Any) -> None:
    """Captura cortada no meio não vira captura mascarada: vira recusa."""
    dados = _btsnoop([b"x" * 10])[:-4]
    with pytest.raises(mascarador.BtsnoopInvalidoError, match="promete"):
        mascarador.mascarar(dados)


def test_recusa_mascarar_fora_de_payload(mascarador: Any) -> None:
    """Zerar dois bytes de cabeçalho de registro corromperia a captura.

    Aqui o endereço é plantado DENTRO do carimbo de tempo do registro. O
    script tem de recusar o arquivo inteiro, não "consertar" a estrutura.
    """
    mac = _mac_forjado()
    payload = b"z" * 4
    registro = struct.pack(">IIII", len(payload), len(payload), 0, 0)
    registro += mac + b"\x00\x00"  # os 8 bytes do carimbo de tempo
    registro += payload
    dados = b"btsnoop\x00" + struct.pack(">II", 1, 1002) + registro

    with pytest.raises(mascarador.BtsnoopInvalidoError, match="fora de payload"):
        mascarador.mascarar(dados)


def test_conferir_relata_as_duas_ordens_mesmo_quando_uma_e_zero(
    mascarador: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O zero é resultado declarado, não busca esquecida."""
    mac = _mac_forjado()
    alvo = tmp_path / "captura.btsnoop"
    alvo.write_bytes(_btsnoop([b"\x04\x0e" + mac[::-1] + b"\x00"]))

    codigo = mascarador.main([str(alvo), "--conferir"])
    saida = capsys.readouterr().out

    assert codigo == 1, "--conferir tem de sair 1 quando sobra MAC cru"
    assert "big-endian    0 ocorrência(s)" in saida
    assert "little-endian 1 ocorrência(s)" in saida


def test_a_captura_mascarada_continua_valida_e_do_mesmo_tamanho(
    mascarador: Any, tmp_path: Path
) -> None:
    mac = _mac_forjado()
    entrada = tmp_path / "entrada.btsnoop"
    saida = tmp_path / "saida.btsnoop"
    entrada.write_bytes(
        _btsnoop([b"\x04\x0e" + mac[::-1] + b"\x00" * 3, b"\x02\x20" + b"y" * 12])
    )

    assert mascarador.main([str(entrada), "-o", str(saida)]) == 0
    assert saida.stat().st_size == entrada.stat().st_size
    # Continua sendo um .btsnoop legível: as faixas de dados ainda batem.
    assert mascarador.faixas_de_payload(saida.read_bytes()) == (
        mascarador.faixas_de_payload(entrada.read_bytes())
    )


# ---------------------------------------------------------------------------
# 3. A MORDIDA — o portão de bytes contra o buraco que ele veio fechar
# ---------------------------------------------------------------------------

def test_o_portao_de_texto_nao_ve_o_mac_em_little_endian() -> None:
    """O buraco, escrito como teste para que ninguém precise reencontrá-lo.

    Isto não é uma falha a corrigir no portão de texto: é o motivo de existir um
    portão de bytes. Texto é texto; seis bytes crus e invertidos não têm
    hexadecimal escrito nenhum para o regex achar.
    """
    dados = _btsnoop([b"\x04\x0e" + _mac_forjado()[::-1] + b"\x00"])
    como_texto = dados.decode("utf-8", errors="ignore")
    assert not list(MAC_COMPLETO_RE.finditer(como_texto))


def test_o_portao_de_bytes_morde_o_mac_em_little_endian() -> None:
    """E o portão de bytes vê — e diz o offset, a ordem e o endereço."""
    dados = _btsnoop([b"\x04\x0e" + _mac_forjado()[::-1] + b"\x00"])
    achados = _ocorrencias_binarias(dados)
    assert len(achados) == 1
    offset, ordem, _mac = achados[0]
    assert ordem == "little-endian"
    assert dados[offset : offset + 6] == _mac_forjado()[::-1]


def test_o_mascarador_cura_o_que_o_portao_de_bytes_reprova(mascarador: Any) -> None:
    """O ciclo inteiro: reprova, mascara, passa — e o tamanho não muda."""
    dados = _btsnoop([b"\x04\x0e" + _mac_forjado()[::-1] + b"\x00"])
    assert _ocorrencias_binarias(dados), "o portão tinha de reprovar ANTES"

    curado, _ = mascarador.mascarar(dados)

    assert _ocorrencias_binarias(curado) == [], "o portão tinha de passar DEPOIS"
    assert len(curado) == len(dados)


def test_o_portao_de_bytes_tambem_ve_a_ordem_natural() -> None:
    """Big-endian dá zero nas capturas de hoje — mas continua sendo procurada.

    Para arrancar e ver morder: apague o laço big-endian de
    ``_ocorrencias_binarias``.
    """
    dados = _btsnoop([b"\x04\x0e" + _mac_forjado() + b"\x00"])
    achados = _ocorrencias_binarias(dados)
    assert [o[1] for o in achados] == ["big-endian"]


def test_a_mascara_da_casa_passa_nas_duas_ordens() -> None:
    """Portão que reprova o já-mascarado é portão que se desliga."""
    oui = bytes(int(o, 16) for o in _OUIS_REAIS_OCTETOS[0])
    mascarado = oui + b"\x00\x00" + bytes([SUFIXO_FORJADO[2]])
    dados = _btsnoop([mascarado, mascarado[::-1]])
    assert _ocorrencias_binarias(dados) == []
