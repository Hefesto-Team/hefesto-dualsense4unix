"""A regra de anonimato em forma de teste — agora para MACs em fixtures.

O irmão `test_nao_existe_bin_fossilizado_do_0x09` trava a identidade em binário
(captures/); este trava a forma mais fácil de vazá-la: um MAC Bluetooth REAL
(do controle ou do adaptador da máquina de teste) colado numa fixture. Já
aconteceu — MACs reais ficaram fossilizados em testes por dois dias antes da
revisão adversarial pegar — e o push publicaria a identidade da mantenedora
para sempre.

A trava é por ALLOWLIST de prefixos sintéticos, nunca por blocklist: listar os
MACs reais aqui seria exatamente o vazamento que o teste existe para impedir.
Faixas permitidas (todas forjadas, documentadas onde nasceram):

- ``02:fe:...``  — o MAC que o próprio vpad forja por jogador (uhid_gamepad);
- ``aa:bb:cc:...`` — placeholder canônico de fixture (controles/adaptador);
- ``e8:47:3a:...`` — o "Edge físico" forjado dos testes de dedup;
- ``ff:ff:ff...``/``00:00:00...`` — broadcast/zerado.

Tokens de 12 hex são checados também em little-endian (o report 0x09 guarda o
MAC em LE — foi assim que um MAC real escapou da primeira varredura).

Além das faixas, existe uma allowlist de TOKENS EXATOS: hashes abreviados de
commits PÚBLICOS do kernel upstream (12 hex é a abreviação canônica do git no
kernel) citados como proveniência dos patches DKMS. São identidade do KERNEL,
verificável por qualquer um em git.kernel.org — não da mantenedora. A entrada
é sempre exata e documentada linha a linha; nunca prefixo/faixa (um MAC real
jamais ganharia carona num hash documentado).
"""
from __future__ import annotations

import re
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parents[1]

#: Prefixos (3 bytes, sem ":") das faixas sintéticas permitidas em fixtures.
_PREFIXOS_FORJADOS = ("02fe00", "aabbcc", "e8473a", "ffffff", "000000")

#: Hashes abreviados (12 hex) de commits PÚBLICOS do kernel upstream citados
#: nos testes da Onda W (test_dkms_rtw88_usb_assets.py) como proveniência dos
#: patches do rtw88. Match EXATO apenas — nada de faixa.
_HASHES_UPSTREAM_DOCUMENTADOS = frozenset(
    {
        # wifi: rtw88: usb: fix memory leaks on USB write failures — o
        # backport 0001 (CVE-2026-63821), pinado verbatim no teste.
        "6b964941bbfe",
        # commit apontado pelo "Fixes:" do 0001 (onde o memleak nasceu).
        "a82dfd33d123",
        # wifi: rtw89 — modelo do contador continual_io_error portado no
        # 0002 (proveniência gravada no BASELINE e no limiar do teste).
        "2135c28be6a8",
    }
)

_MAC_COM_DOIS_PONTOS = re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b")
_MAC_12_HEX = re.compile(r"\b[0-9a-fA-F]{12}\b")


def _permitido(mac_12hex: str) -> bool:
    """True se o token (12 hex, sem ':') é faixa forjada (BE/LE) ou hash
    upstream documentado (match exato)."""
    norm = mac_12hex.lower()
    if norm in _HASHES_UPSTREAM_DOCUMENTADOS:
        return True
    invertido = "".join(norm[i : i + 2] for i in range(10, -1, -2))
    return norm.startswith(_PREFIXOS_FORJADOS) or invertido.startswith(
        _PREFIXOS_FORJADOS
    )


def test_nenhum_mac_fora_das_faixas_forjadas_em_tests() -> None:
    """Fixture nova com MAC real (ou derivado de real) fica vermelha aqui."""
    violacoes: list[str] = []
    for arquivo in sorted(_TESTS_DIR.rglob("*")):
        if not arquivo.is_file():
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binário/ilegível: coberto pelo teste do 0x09
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
