"""A sequência do rádio se mede no aparelho, e a casa não afirma o que o caderno não mediu.

O ensaio ``scripts/ensaios/a_sequencia_do_radio.py`` roda aqui contra um dublê de firmware que lê
o ``0x31`` de saída (CRC, número e bloco do R2) e devolve o efeito ativo no byte 47 do corpo do
report de entrada.

Mordidas:

* tirar o ``saida[-1] ^= 0xFF`` de ``quadro``: o controle negativo sai com o CRC certo, e
  :func:`test_o_controle_negativo_sai_com_o_crc_estragado` reprova;
* devolver a frase «fazem o firmware descartar o quadro» ao ``writeReport``: a régua de texto
  :func:`test_src_nao_afirma_o_que_o_caderno_nao_diz` reprova.
"""

from __future__ import annotations

import csv
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_INPUT_CRC_SEED,
    BT_REPORT_ID,
    BT_REPORT_LEN,
    bt_crc32,
)
from hefesto_dualsense4unix.core.trigger_effects import TriggerMode

RAIZ = Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"
CADERNO = RAIZ / "docs" / "data" / "ensaios.csv"


def _instrumento() -> ModuleType:
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    apelido = "instrumento_a_sequencia_do_radio"
    especie = importlib.util.spec_from_file_location(apelido, ENSAIOS / "a_sequencia_do_radio.py")
    assert especie is not None and especie.loader is not None
    modulo = importlib.util.module_from_spec(especie)
    sys.modules[apelido] = modulo
    especie.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def ens() -> ModuleType:
    return _instrumento()


class Firmware:
    """O aparelho de mentira: aceita o quadro de CRC certo e, se pedido, descarta pelo número."""

    def __init__(
        self, *, descarta: bool = False, engole_crc: bool = False, cego: bool = False
    ) -> None:
        self.descarta = descarta
        self.engole_crc = engole_crc
        self.cego = cego
        self.ultimo: int | None = None
        self.efeito = 0
        self.escritos: list[bytes] = []

    def escrever(self, saida: bytes) -> None:
        self.escritos.append(saida)
        assert len(saida) == BT_REPORT_LEN and saida[0] == BT_REPORT_ID
        crc = int.from_bytes(saida[-4:], "little")
        if crc != bt_crc32(saida[:-4]) and not self.engole_crc:
            return
        numero = saida[1] >> 4
        if self.descarta and self.ultimo is not None and not 1 <= (numero - self.ultimo) % 16 <= 7:
            return  # o repetido e o que anda para trás
        self.ultimo = numero
        if saida[3] & 0x04:
            self.efeito = 0x2 if saida[3 + 10] == TriggerMode.WEAPON else 0x0

    def ler_efeito(self, espera: float) -> int | None:
        entrada = bytearray(BT_REPORT_LEN)
        entrada[0] = BT_REPORT_ID
        entrada[2 + 47] = 0 if self.cego else self.efeito
        entrada[-4:] = bt_crc32(entrada[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
        efeito: int | None = _ens().efeito_do_r2(bytes(entrada))
        return efeito


def _ens() -> ModuleType:
    return sys.modules.get("instrumento_a_sequencia_do_radio") or _instrumento()


def test_o_aparelho_que_aceita_obedece(ens: ModuleType) -> None:
    resultados = ens.medir(Firmware(), espera=0)
    assert {r.caso: r.veredito for r in resultados} == {
        "crc errado": ens.DESCARTADO, "repetido": ens.ACEITO, "fora de ordem": ens.ACEITO}
    assert ens.veredito(resultados) == ens.OBEDECE


def test_o_aparelho_que_descarta_o_repetido_nao_obedece(ens: ModuleType) -> None:
    resultados = ens.medir(Firmware(descarta=True), espera=0)
    assert {r.caso: r.veredito for r in resultados} == {
        "crc errado": ens.DESCARTADO, "repetido": ens.DESCARTADO, "fora de ordem": ens.DESCARTADO}
    assert ens.veredito(resultados) == ens.NAO_OBEDECE


def test_quem_engole_o_crc_errado_deixa_o_ensaio_inconclusivo(ens: ModuleType) -> None:
    resultados = ens.medir(Firmware(engole_crc=True), espera=0)
    assert ens.veredito(resultados) == ens.INCONCLUSIVO, "sem controle negativo não há veredito"


def test_o_byte_47_que_nao_muda_e_cego(ens: ModuleType) -> None:
    resultados = ens.medir(Firmware(cego=True), espera=0)
    assert {r.veredito for r in resultados} == {ens.CEGO}
    assert ens.veredito(resultados) == ens.INCONCLUSIVO


def test_o_controle_negativo_sai_com_o_crc_estragado(ens: ModuleType) -> None:
    firmware = Firmware()
    resultados = ens.medir(firmware, espera=0)
    negativo = next(r for r in resultados if r.caso == "crc errado")
    assert not negativo.crc_do_caso
    estragados = [
        q for q in firmware.escritos if int.from_bytes(q[-4:], "little") != bt_crc32(q[:-4])
    ]
    assert len(estragados) == 1, "só o quadro do controle negativo sai com o CRC errado"


def test_os_numeros_de_cada_dupla(ens: ModuleType) -> None:
    por_caso = {r.caso: r.numeros for r in ens.medir(Firmware(), espera=0)}
    assentar, armar, repetido = por_caso["repetido"]
    assert (armar - assentar) % 16 == 1 and repetido == armar
    _assentar, armar, fora = por_caso["fora de ordem"]
    assert (armar - fora) % 16 == 3


def test_o_efeito_so_se_le_de_um_0x31_integro(ens: ModuleType) -> None:
    entrada = bytearray(BT_REPORT_LEN)
    entrada[0] = BT_REPORT_ID
    entrada[2 + 47] = 0x52
    entrada[-4:] = bt_crc32(entrada[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    assert ens.efeito_do_r2(bytes(entrada)) == 0x2, "o R2 mora nos bits 0-3"
    entrada[-1] ^= 0x01
    assert ens.efeito_do_r2(bytes(entrada)) is None
    assert ens.efeito_do_r2(bytes(entrada[:64])) is None


def test_a_linha_do_veredito_vai_ao_caderno(ens: ModuleType) -> None:
    linhas = ens.linhas_do_caderno(ens.medir(Firmware(), espera=0))
    veredito = next(csv.reader([linhas[-1]]))
    assert veredito[0] == ens.ID_DO_VEREDITO
    assert veredito[8] == ens.OBEDECE
    assert veredito[11] == ens.FONTE


# ---- a régua de texto: as duas afirmações não convivem -------------------------------------

#: a casa afirma que o firmware descarta o número repetido ou fora de ordem
DESCARTE = (
    re.compile(r"fazem o firmware descartar"),
    re.compile(r"firmware descarta o (?:report|quadro|segundo)"),
    re.compile(r"o que o firmware joga fora"),
    re.compile(r"descartad[oa] pelo firmware"),
)
#: a casa afirma que o número não importa ao firmware
NAO_IMPORTA = (
    re.compile(r"(?:firmware|controle) aceita(?: o)? 0 fixo"),
    re.compile(r"desde sempre e o controle aceita"),
)


def veredito_do_caderno(caderno: Path = CADERNO) -> str | None:
    """O ``resultado`` da última linha do veredito do ensaio, ou ``None`` se ele não rodou."""
    ens = _ens()
    with caderno.open(encoding="utf-8", newline="") as arquivo:
        linhas = [linha for linha in csv.DictReader(arquivo) if linha["id"] == ens.ID_DO_VEREDITO]
    return linhas[-1]["resultado"] if linhas else None


def _prosa(texto: str) -> str:
    return re.sub(r"\s*\n\s*(?:#:?\s*)?", " ", texto)


def afirmacoes_que_o_caderno_nao_sustenta(
    veredito: str | None, textos: dict[str, str]
) -> list[str]:
    """Enquanto o aparelho não disser que descarta, o descarte não se afirma; se disser, o
    «não importa» é que cai."""
    proibidas = NAO_IMPORTA if veredito == _ens().NAO_OBEDECE else DESCARTE
    return [
        f"{nome}: {achado.group(0)!r}"
        for nome, texto in textos.items()
        for padrao in proibidas
        if (achado := padrao.search(_prosa(texto)))
    ]


def _src() -> dict[str, str]:
    raiz = RAIZ / "src" / "hefesto_dualsense4unix"
    return {str(p.relative_to(RAIZ)): p.read_text(encoding="utf-8") for p in raiz.rglob("*.py")}


def test_src_nao_afirma_o_que_o_caderno_nao_diz() -> None:
    veredito = veredito_do_caderno()
    assert afirmacoes_que_o_caderno_nao_sustenta(veredito, _src()) == [], veredito


@pytest.mark.parametrize(("veredito", "texto", "reprova"), [
    (None, "duas threads com o mesmo `seq` fazem o firmware\n        descartar o quadro", True),
    ("obedece", "o firmware descarta o report\n    como fora de sequência", True),
    ("obedece", "#: o SDL manda 0 fixo em todo report BT desde sempre e o controle aceita", False),
    ("não obedece", "#: o SDL manda 0 fixo desde sempre e o controle aceita", True),
    ("não obedece", "o firmware aceita 0 fixo (comportamento do SDL)", True),
    ("não obedece", "o firmware descarta o report fora de ordem", False),
    (None, "um 0x31 com ``seq`` fora do fluxo do handle é\n    descartado pelo firmware", True),
    ("não obedece", "um 0x31 com ``seq`` repetido é descartado pelo firmware", False),
])
def test_a_regua_le_o_veredito(veredito: str | None, texto: str, reprova: bool) -> None:
    assert bool(afirmacoes_que_o_caderno_nao_sustenta(veredito, {"x.py": texto})) is reprova


def test_o_veredito_se_le_da_ultima_linha(tmp_path: Path) -> None:
    ens = _ens()
    caderno = tmp_path / "ensaios.csv"
    cabecalho = ",".join(sys.modules["escrita_pelo_broker"].COLUNAS_DO_CADERNO)
    caderno.write_text(cabecalho + "\n", encoding="utf-8")
    assert veredito_do_caderno(caderno) is None
    linhas = [ens.linhas_do_caderno(ens.medir(Firmware(descarta=True), espera=0))[-1],
              ens.linhas_do_caderno(ens.medir(Firmware(), espera=0))[-1]]
    caderno.write_text(cabecalho + "\n" + "\n".join(linhas) + "\n", encoding="utf-8")
    assert veredito_do_caderno(caderno) == ens.OBEDECE
