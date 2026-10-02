"""A regra de anonimato em forma de teste — agora para MACs em fixtures."""
from __future__ import annotations

import re
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parents[1]

_PREFIXOS_FORJADOS = (
    "02fe00",
    "aabbcc",
    "e8473a",
    "ffffff",
    "000000",
    # DualSense real para o oitavo posto. A partir daí, um controle de prova
    "02001a",
    "3c9d07",
    "d0f1a2",
    "f7e6d5",
    "a1b2c3",  # o DualSense físico por rádio (`…marca_do_vpad_no_nome…`)
    "d2c1b0",
)

_OUIS_DE_FABRICANTE_COM_MASCARA = frozenset(
    {
        "e417d8",
    }
)

_HASHES_UPSTREAM_DOCUMENTADOS = frozenset(
    {
        "6b964941bbfe",
        "a82dfd33d123",
        "2135c28be6a8",
        "00805f9b34fb",
        "444553540000",
        "ae9e1faefc6c",
        "00e098032b8c",
    }
)

_MAC_COM_DOIS_PONTOS = re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b")
_MAC_12_HEX = re.compile(r"\b(?!0[bBxX])[0-9a-fA-F]{12}\b")


def _permitido(mac_12hex: str) -> bool:
    """True se o token (12 hex, sem ':') é faixa forjada (BE/LE) ou hash"""
    norm = mac_12hex.lower()
    if norm in _HASHES_UPSTREAM_DOCUMENTADOS:
        return True
    invertido = "".join(norm[i : i + 2] for i in range(10, -1, -2))
    for candidato in (norm, invertido):
        if candidato.startswith(_PREFIXOS_FORJADOS):
            return True
        if candidato[:6] in _OUIS_DE_FABRICANTE_COM_MASCARA and (
            candidato[6:10] == "0000"
        ):
            return True
    return False


def test_nenhum_mac_fora_das_faixas_forjadas_em_tests() -> None:
    """Fixture nova com MAC real (ou derivado de real) fica vermelha aqui."""
    violacoes: list[str] = []
    for arquivo in sorted(_TESTS_DIR.rglob("*")):
        if not arquivo.is_file():
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for linha_num, linha in enumerate(texto.splitlines(), start=1):
            candidatos = [
                m.group(0).replace(":", "")
                for m in _MAC_COM_DOIS_PONTOS.finditer(linha)
            ] + [m.group(0) for m in _MAC_12_HEX.finditer(linha)]
            violacoes.extend(
                f"{arquivo.relative_to(_TESTS_DIR)}:{linha_num}: {token}"
                for token in candidatos
                if not _permitido(token)
            )

    assert violacoes == [], (
        "MAC fora das faixas sintéticas (02:fe/aa:bb:cc/e8:47:3a) em fixture de "
        "teste — se for identidade real, ISSO é vazamento; se for forjado, mova "
        "para uma faixa permitida ou documente-a aqui: " + "; ".join(violacoes)
    )
