"""Guarda de anonimato de hardware: MAC e SERIAL reais NUNCA saem inteiros."""
from __future__ import annotations

import gzip
import re
import subprocess
from pathlib import Path

from hefesto_dualsense4unix.core.formas_do_endereco import (
    CARACTERES_PUBLICOS_DO_SERIAL,
    PADRAO_DE_SERIAL,
    formas_do_endereco,
)

#: OUIs de hardware REAL desta bancada (adaptador BT, DualSense, 8BitDo,
#: NOTA DATADA — 06/08/2026: entrou `14:3a:9a`, o OUI do SEGUNDO DualSense da
#: `44:46:48`, o TERCEIRO e o QUARTO DualSense — os dois que chegaram na mesa
_OUIS_REAIS_OCTETOS = (
    ("d8", "44", "89"),
    ("a0", "fa", "9c"),
    ("e4", "17", "d8"),
    ("e0", "f6", "b5"),
    ("48", "b2", "5d"),
    ("14", "3a", "9a"),
    ("d4", "2f", "4b"),
    ("44", "46", "48"),
)

OUIS_REAIS = tuple("[:_-]".join(o) for o in _OUIS_REAIS_OCTETOS)

_OUIS_COLADOS = tuple("".join(o) for o in _OUIS_REAIS_OCTETOS)

# (`...battery-44:46:48:xx:xx:xxPOWER_SUPPLY_TYPE=`), que é como o endereço
_NAO_HEX_ANTES = r"(?<![0-9a-f])"
_NAO_HEX_DEPOIS = r"(?![0-9a-f])"
MAC_COMPLETO_RE = re.compile(
    r"(?i)" + _NAO_HEX_ANTES + r"(?:"
    r"(?P<oui_sep>" + "|".join(OUIS_REAIS) + r")"
    r"[:_-](?P<a>[0-9a-f]{2})[:_-](?P<b>[0-9a-f]{2})[:_-](?P<c>[0-9a-f]{2})"
    r"|"
    r"(?P<oui_col>" + "|".join(_OUIS_COLADOS) + r")"
    r"(?P<a2>[0-9a-f]{2})(?P<b2>[0-9a-f]{2})(?P<c2>[0-9a-f]{2})"
    r")" + _NAO_HEX_DEPOIS
)


def _partes(m: re.Match[str]) -> tuple[str, str, str]:
    """Devolve (oui, octeto4, octeto5) de qualquer uma das duas grafias."""
    if m.group("oui_sep") is not None:
        return m.group("oui_sep"), m.group("a"), m.group("b")
    return m.group("oui_col"), m.group("a2"), m.group("b2")

_SKIP_SUFFIXES = {".png", ".mo", ".ico", ".gif", ".jpg", ".jpeg"}


def _conteudo(path: Path) -> bytes | None:
    """Os bytes a varrer: o arquivo, ou o que ele CONTÉM quando é comprimido."""
    try:
        dados = path.read_bytes()
    except (OSError, IsADirectoryError):
        return None
    if path.suffix.lower() != ".gz":
        return dados
    try:
        return gzip.decompress(dados)
    except (OSError, EOFError, ValueError):
        return dados


def _tracked_files(repo_root: Path) -> list[Path]:
    """A LISTA do git: o rastreado E o novo, sem o ignorado."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        repo_root / nome
        for nome in out.split("\0")
        if nome and Path(nome).suffix.lower() not in _SKIP_SUFFIXES
    ]


def test_nenhum_mac_real_completo_sem_mascara_no_repo() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        dados = _conteudo(path)
        if dados is None:
            continue
        texto = dados.decode("utf-8", errors="ignore")
        for num, linha in enumerate(texto.splitlines(), start=1):
            for m in MAC_COMPLETO_RE.finditer(linha):
                oui, oct4, oct5 = _partes(m)
                if oct4 == "00" and oct5 == "00":
                    continue
                violacoes.append(
                    f"{path.relative_to(repo_root)}:{num}: "
                    f"MAC real sem máscara ({oui}:xx:xx:xx)"
                )
    assert not violacoes, (
        "MAC de hardware REAL com sufixo exposto — mascare os 3 últimos "
        "octetos (convenção OUI:00:00:NN dos estudos):\n" + "\n".join(violacoes)
    )


MAC_ELIDIDO_RE = re.compile(
    r"(?i)\.\.\.[:_-]?"
    r"(?P<a>[0-9a-f]{2})[:_-](?P<b>[0-9a-f]{2})[:_-](?P<c>[0-9a-f]{2})\b"
)


def test_nenhum_sufixo_de_mac_real_com_o_oui_elidido() -> None:
    """Omitir o OUI não é máscara — o sufixo é o que identifica o aparelho."""
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        if path.name == Path(__file__).name:
            continue
        dados = _conteudo(path)
        if dados is None:
            continue
        texto = dados.decode("utf-8", errors="ignore")
        for num, linha in enumerate(texto.splitlines(), start=1):
            for m in MAC_ELIDIDO_RE.finditer(linha):
                if m.group("a") == "00" and m.group("b") == "00":
                    continue
                violacoes.append(
                    f"{path.relative_to(repo_root)}:{num}: "
                    "sufixo de MAC com o OUI elidido — omitir o OUI não "
                    "mascara nada (use ...:00:00:NN)"
                )
    assert not violacoes, (
        "sufixo de MAC real exposto com o OUI omitido:\n" + "\n".join(violacoes)
    )


def _mac_de_seis_octetos(dados: bytes, inicio: int) -> bytes:
    return dados[inicio : inicio + 6]


def _ocorrencias_binarias(dados: bytes) -> list[tuple[int, str, str]]:
    """(offset, ordem, mac) de todo MAC de OUI real CRU dentro de ``dados``."""
    achados: list[tuple[int, str, str]] = []
    for octetos in _OUIS_REAIS_OCTETOS:
        oui_be = bytes(int(o, 16) for o in octetos)
        oui_le = oui_be[::-1]

        pos = dados.find(oui_be)
        while pos != -1:
            campo = _mac_de_seis_octetos(dados, pos)
            if len(campo) == 6 and not (campo[3] == 0 and campo[4] == 0):
                achados.append((pos, "big-endian", campo.hex(":")))
            pos = dados.find(oui_be, pos + 1)

        pos = dados.find(oui_le)
        while pos != -1:
            inicio = pos - 3
            if inicio >= 0:
                campo = _mac_de_seis_octetos(dados, inicio)
                if not (campo[1] == 0 and campo[2] == 0):
                    achados.append((inicio, "little-endian", campo[::-1].hex(":")))
            pos = dados.find(oui_le, pos + 1)
    return sorted(achados)


def test_nenhum_mac_real_em_bytes_no_repo() -> None:
    """Nenhum arquivo versionado carrega MAC real em BINÁRIO, em ordem nenhuma."""
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        dados = _conteudo(path)
        if dados is None:
            continue
        for offset, ordem, mac in _ocorrencias_binarias(dados):
            violacoes.append(
                f"{path.relative_to(repo_root)}: offset {offset} ({ordem}): "
                f"MAC real em bytes, sem máscara ({mac})"
            )
    assert not violacoes, (
        "MAC de hardware REAL gravado em BINÁRIO. Nenhum portão de texto o vê. "
        "Passe o arquivo por `scripts/mascarar_btsnoop.py` (captura HCI) ou "
        "zere os octetos 4 e 5 dos seis bytes apontados:\n" + "\n".join(violacoes)
    )


def test_o_mac_colado_na_chave_seguinte_do_uevent_reprova() -> None:
    """BURACO-DO-PORTAO-03: `\\b` não existe entre um octeto e uma letra."""
    primeiro = ":".join(_OUIS_REAIS_OCTETOS[0])
    segundo = ":".join(_OUIS_REAIS_OCTETOS[-1])
    sufixo_cru = ":".join(("11", "22", "33"))
    sufixo_mascarado = ":".join(("00", "00", "33"))
    linha = (
        "uevent|DRIVER=playstation"
        f"HID_PHYS={primeiro}:{sufixo_cru}HID_UNIQ={segundo}:{sufixo_cru}"
        "MODALIAS=hid:b0005g0000v0000054Cp00000CE6"
    )
    achados = [_partes(m) for m in MAC_COMPLETO_RE.finditer(linha)]
    assert len(achados) == 2, (
        "o portão tem de ver os DOIS endereços colados na mesma linha de "
        f"uevent, e viu {len(achados)}: {achados}"
    )
    assert all(oct4 != "00" or oct5 != "00" for _, oct4, oct5 in achados)

    mascarada = linha.replace(sufixo_cru, sufixo_mascarado)
    encontrados = [_partes(m) for m in MAC_COMPLETO_RE.finditer(mascarada)]
    assert len(encontrados) == 2
    assert all((oct4, oct5) == ("00", "00") for _, oct4, oct5 in encontrados)


def test_o_regex_nao_confunde_pedaco_de_hexadecimal_maior() -> None:
    """A fronteira de hexadecimal é fronteira nos DOIS sentidos."""
    oui_colado = "".join(_OUIS_REAIS_OCTETOS[0])
    sha_falso = "9f" + oui_colado + "112233" + "ab" * 24
    assert not list(MAC_COMPLETO_RE.finditer(sha_falso))


#       legítimos, os dois com prefixo forjado — o exemplo da docstring  # serial-de-mentira
#       de `mascarar_serial` e o de  # serial-de-mentira

#: do serial de fábrica do DualSense, como MEDIDA nos aparelhos da bancada: as
SERIAL_DE_FABRICA_RE = re.compile(PADRAO_DE_SERIAL)

_PAR_HEX_SOLTO = re.compile(rb"(?<![0-9A-Fa-f])([0-9A-Fa-f]{2})(?![0-9A-Fa-f])")

_CORRIDA_HEX_COLADA = re.compile(
    rb"(?<![0-9A-Fa-f])((?:[0-9A-Fa-f]{2}){17,})(?![0-9A-Fa-f])"
)


def mascarar_para_relatorio(serial: str) -> str:
    """A máscara da casa, aplicada à MENSAGEM DE ERRO do próprio portão."""
    if len(serial) <= CARACTERES_PUBLICOS_DO_SERIAL:
        return serial
    return serial[:CARACTERES_PUBLICOS_DO_SERIAL] + "#" * (
        len(serial) - CARACTERES_PUBLICOS_DO_SERIAL
    )


def _fluxo_de_hexdump(dados: bytes) -> bytes:
    """Remonta a carga de um hexdump: todo par hexadecimal solto, decodificado."""
    return bytes(int(par, 16) for par in _PAR_HEX_SOLTO.findall(dados))


def _ocorrencias_de_serial(dados: bytes) -> list[tuple[str, str]]:
    """(forma, serial mascarado) de todo serial de fábrica CRU em ``dados``."""
    achados: list[tuple[str, str]] = []
    texto = dados.decode("latin-1")
    for m in SERIAL_DE_FABRICA_RE.finditer(texto):
        achados.append(("texto", mascarar_para_relatorio(m.group(0))))
    for m in SERIAL_DE_FABRICA_RE.finditer(
        _fluxo_de_hexdump(dados).decode("latin-1")
    ):
        achados.append(("hexdump", mascarar_para_relatorio(m.group(0))))
    for corrida in _CORRIDA_HEX_COLADA.finditer(dados):
        bruto = bytes.fromhex(corrida.group(1).decode("ascii")).decode("latin-1")
        for m in SERIAL_DE_FABRICA_RE.finditer(bruto):
            achados.append(("hex colado", mascarar_para_relatorio(m.group(0))))
    return achados


def test_nenhum_serial_de_fabrica_real_no_repo() -> None:
    """Nenhum arquivo versionado carrega serial de fábrica sem a máscara da casa."""
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        dados = _conteudo(path)
        if dados is None:
            continue
        for forma, mascarado in _ocorrencias_de_serial(dados):
            violacoes.append(
                f"{path.relative_to(repo_root)} ({forma}): "
                f"SERIAL DE FÁBRICA real, sem máscara ({mascarado})"
            )
    assert not violacoes, (
        "SERIAL DE FÁBRICA de aparelho REAL em arquivo versionado. Ele "
        "identifica a unidade tão bem quanto o MAC. Máscara da casa: os "
        f"{CARACTERES_PUBLICOS_DO_SERIAL} primeiros caracteres e o resto em "
        "'#' (a COR, nos caracteres 5 e 6, fica preservada):\n"
        + "\n".join(violacoes)
    )


def _serial_forjado_na_forma_real() -> str:
    """Um serial FORJADO que tem a forma real — montado, nunca escrito."""
    return "Q" + "88" + "X" + "77" + "K" + "9876543210"


def test_o_serial_de_fabrica_em_texto_reprova_e_a_mascara_passa() -> None:
    """A mordida da forma 1: texto puro."""
    forjado = _serial_forjado_na_forma_real()
    assert len(forjado) == 17
    achados = _ocorrencias_de_serial(f"  SERIAL ... {forjado}\n".encode())
    assert achados == [("texto", "Q88X77###########")], achados

    mascarado = forjado[:CARACTERES_PUBLICOS_DO_SERIAL] + "#" * 11
    assert not _ocorrencias_de_serial(f"  SERIAL ... {mascarado}\n".encode())


def _como_hexdump(carga: bytes) -> bytes:
    """A carga escrita como o E7 a escreve: offset, 16 bytes por linha."""
    linhas = []
    for offset in range(0, len(carga), 16):
        pares = " ".join(f"{b:02x}" for b in carga[offset : offset + 16])
        linhas.append(f"    {offset:04x}  {pares}")
    return ("\n".join(linhas) + "\n").encode("ascii")


def test_o_serial_de_fabrica_em_hexdump_reprova_atravessando_a_linha() -> None:
    """A mordida da forma 2: bytes num hexdump, repartidos em duas linhas."""
    forjado = _serial_forjado_na_forma_real().encode("ascii")
    carga = bytes([0x81, 0x01, 0x13, 0x02]) + forjado

    formas = [forma for forma, _ in _ocorrencias_de_serial(_como_hexdump(carga))]
    assert "hexdump" in formas, (
        "o serial em hexdump tem de reprovar; o portão viu " + repr(formas)
    )

    carga_mascarada = carga[: 4 + CARACTERES_PUBLICOS_DO_SERIAL] + b"#" * 11
    assert not _ocorrencias_de_serial(_como_hexdump(carga_mascarada))


def test_o_serial_de_fabrica_em_hexadecimal_colado_reprova() -> None:
    """A mordida da forma 3: a corrida hexadecimal sem separador nenhum."""
    forjado = _serial_forjado_na_forma_real().encode("ascii")
    colado = ("payload=" + forjado.hex() + "\n").encode("ascii")
    formas = [forma for forma, _ in _ocorrencias_de_serial(colado)]
    assert "hex colado" in formas, formas


def test_o_portao_de_serial_nao_reprova_palavra_comprida_nem_forjado() -> None:
    """O aperto contra falso positivo, exercido nos casos que ele custou medir."""
    ruido = (
        "MICROCASSYVOLTAGE",
        "MICROCASSYCURRENT",
        "INDEPENDENTEMENTE",
        "PROGRAMATICAMENTE",  # transcrito de sessão
        "REDIMENSIONAMENTO",
        "AB1C05D1234567890",  # serial-de-mentira: da docstring de mascarar_serial
        "ZZ9Y02Q0000000000",  # serial-de-mentira: de test_cor_do_plastico_recusa
    )
    for palavra in ruido:
        assert len(palavra) == 17, palavra
        assert not SERIAL_DE_FABRICA_RE.search(palavra), (
            f"{palavra} não é serial de fábrica e o portão não pode reprová-la"
        )

    sha_falso = "AB" + _serial_forjado_na_forma_real() + "CD" * 20
    assert not SERIAL_DE_FABRICA_RE.search(sha_falso)


def test_o_check_anonymity_usa_o_mesmo_padrao_de_serial() -> None:
    """As duas cópias do padrão têm de ser a MESMA — divergência é buraco."""
    repo_root = Path(__file__).resolve().parents[2]
    script = (repo_root / "scripts" / "check_anonymity.sh").read_text(
        encoding="utf-8"
    )
    assert "SERIAL" in script, (
        "o check_anonymity.sh voltou a ser cego a serial de fábrica"
    )
    bloco = re.search(r"^PADRAO = \((.*?)^\)$", script, re.S | re.M)
    assert bloco, "não achei a atribuição `PADRAO = (...)` no check_anonymity.sh"
    remontado = "".join(re.findall(r'r"([^"]*)"', bloco.group(1)))
    assert remontado == PADRAO_DE_SERIAL, (
        "o padrão de serial do script divergiu do deste arquivo.\n"
        f"  script: {remontado}\n"
        f"  aqui:   {PADRAO_DE_SERIAL}"
    )


# como bytes soltos por espaço, e o ``0x09`` e o ``0x0b`` do DualSense o trazem

_SEIS_OCTETOS_EM_TEXTO = re.compile(
    r"(?i)(?<![0-9a-f])(?=([0-9a-f]{2})([:_\-. ]?)([0-9a-f]{2})\2([0-9a-f]{2})\2"
    r"([0-9a-f]{2})\2([0-9a-f]{2})\2([0-9a-f]{2})(?![0-9a-f]))"
)


def _ocorrencias_em_texto_nas_duas_ordens(texto: str) -> list[tuple[int, str, str]]:
    """(linha, ordem, oui) de todo endereço de OUI real em texto que entrega o 4.º ou o 5.º."""
    achados: list[tuple[int, str, str]] = []
    for m in _SEIS_OCTETOS_EM_TEXTO.finditer(texto):
        lidos = tuple(m.group(i).lower() for i in (1, 3, 4, 5, 6, 7))
        trecho = m.group(2).join(lidos)
        for ordem, octetos in (("direta", lidos), ("invertida", lidos[::-1])):
            if octetos[:3] not in _OUIS_REAIS_OCTETOS:
                continue
            if any(p in trecho for p in formas_do_endereco(octetos) if p == p.lower()):
                linha = texto.count("\n", 0, m.start()) + 1
                achados.append((linha, ordem, ":".join(octetos[:3])))
    return achados


def test_nenhum_mac_real_em_texto_em_toda_grafia_e_nas_duas_ordens() -> None:
    """Nenhum arquivo versionado escreve um endereço real invertido, ou solto por espaço."""
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        dados = _conteudo(path)
        if dados is None:
            continue
        texto = dados.decode("utf-8", errors="ignore")
        for num, ordem, oui in _ocorrencias_em_texto_nas_duas_ordens(texto):
            violacoes.append(
                f"{path.relative_to(repo_root)}:{num}: MAC real sem máscara, "
                f"na ordem {ordem} ({oui}:xx:xx:xx)"
            )
    assert not violacoes, (
        "MAC de hardware REAL em texto, com o 4.º ou o 5.º octeto à mostra. Zere "
        "os dois nas posições do endereço (na invertida, o 2.º e o 3.º bytes "
        "depois do sexto octeto):\n" + "\n".join(violacoes)
    )


def _despejo_invertido(sufixo: tuple[str, str, str]) -> str:
    """Um report ``0x09`` com o endereço de um OUI real invertido, montado aqui."""
    octetos = (*_OUIS_REAIS_OCTETOS[0], *sufixo)
    return "0x09: 09 " + " ".join(reversed(octetos)) + " 08 25\n"


def test_o_despejo_invertido_com_espaco_reprova_e_o_mascarado_passa() -> None:
    cru = _despejo_invertido(("11", "22", "33"))
    assert _ocorrencias_em_texto_nas_duas_ordens(cru) == [
        (1, "invertida", ":".join(_OUIS_REAIS_OCTETOS[0]))
    ]
    assert _ocorrencias_em_texto_nas_duas_ordens(_despejo_invertido(("00", "00", "33"))) == []
    for separador in (":", "."):
        linha = cru.replace(" ", separador).replace("0x09:" + separador, "0x09: ")
        assert _ocorrencias_em_texto_nas_duas_ordens(linha), separador
    colado = "".join(reversed((*_OUIS_REAIS_OCTETOS[0], "11", "22", "33")))
    assert _ocorrencias_em_texto_nas_duas_ordens(f"bruto={colado}\n")

