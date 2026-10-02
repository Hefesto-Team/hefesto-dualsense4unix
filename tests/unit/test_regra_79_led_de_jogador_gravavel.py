"""A regra 79 é o que torna o LED de jogador do Pro gravável sem sudo."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REGRA = REPO_ROOT / "assets" / "79-external-controller-leds.rules"

VID_NINTENDO = "057E"

LIMITE_UACCESS = 73


def _linhas_de_codigo() -> list[str]:
    """Só linha de CÓDIGO: o comentário que EXPLICA a regra não prova nada."""
    return [
        ln.strip()
        for ln in REGRA.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


@pytest.fixture(scope="module")
def linhas() -> list[str]:
    if not REGRA.is_file():
        pytest.fail(f"regra ausente: {REGRA}")
    return _linhas_de_codigo()


def test_o_arquivo_existe_e_e_numerado_acima_de_73() -> None:
    """A numeração não é acidente: é ela que decide se `uaccess` funcionaria."""
    assert REGRA.is_file(), (
        "sem esta regra os nós de LED do Pro nascem root:root e a escrita do "
        "daemon falha em silêncio"
    )
    assert int(REGRA.name[:2]) >= LIMITE_UACCESS


def test_os_quatro_verdes_e_o_azul_ficam_gravaveis(linhas: list[str]) -> None:
    """As duas linhas que a linha `luz.led_jogador.udev@pro` do mapa nomeia."""
    blob = "\n".join(linhas)
    for cor in ("green", "blue"):
        alvo = f'KERNEL=="*{VID_NINTENDO}:*:{cor}:player-*"'
        assert alvo in blob, (
            f"a regra não cobre mais os LEDs `{cor}:player-*` do {VID_NINTENDO}: "
            "o nó fica root:root e a numeração do controle cai no default do "
            "kernel, sem erro nenhum"
        )


def test_toda_linha_torna_o_brightness_gravavel_no_plug(linhas: list[str]) -> None:
    """`ACTION=="add"` + `SUBSYSTEM=="leds"` + `chmod 0666` no `brightness`."""
    assert linhas, "o arquivo não tem linha de código nenhuma"
    for ln in linhas:
        assert 'ACTION=="add"' in ln, f"sem ACTION add (não reaplica no replug): {ln}"
        assert 'SUBSYSTEM=="leds"' in ln, f"sem SUBSYSTEM leds: {ln}"
        assert "/bin/chmod 0666" in ln, f"sem o chmod que dá a escrita: {ln}"
        assert "/sys/class/leds/%k/brightness" in ln, (
            f"o chmod tem de cair no `brightness` do próprio nó: {ln}"
        )


def test_a_regra_nunca_volta_a_depender_de_uaccess(linhas: list[str]) -> None:
    """A cura de 19/07: numa regra >= 73 a TAG `uaccess` NUNCA vira ACL."""
    blob = "\n".join(linhas)
    assert "uaccess" not in blob, (
        f"{REGRA.name} é numerada >= {LIMITE_UACCESS}: a TAG uaccess é inerte "
        "aqui (a 73-seat-late.rules já passou) e substituir o chmod por ela "
        "deixa o LED sem escrita sem que nada acuse"
    )
