"""A regra 79 é o que torna o LED de jogador do Pro gravável sem sudo.

O QUE ESTE ARQUIVO GUARDA
-------------------------
`assets/79-external-controller-leds.rules`. Sem ela, os nós que o `hid-nintendo`
cria (`*057E:*:green:player-N` e o azul `*057E:*:blue:player-5`) nascem
`root:root`, o daemon roda como usuária (sudo-zero) e a escrita falha **em
silêncio**: a numeração do LED cai no default do kernel e dois controles podem
acender o mesmo padrão na mesa. Nenhum erro aparece — o sintoma é a AUSÊNCIA do
efeito, a armadilha mais cara desta casa.

Duas decisões medidas ficam presas aqui, e as duas já custaram:

1. **`RUN` com `chmod 0666`, nunca `TAG+="uaccess"`** (ONDA-R, 19/07/2026). O
   `systemd-logind` só converte `uaccess` em ACL para regras numeradas **< 73**
   (quem faz isso é a `73-seat-late.rules` do próprio systemd). Numa regra 79 a
   TAG é inerte: o arquivo instala, o `udevadm verify` aprova, e nada funciona.
   A TAG foi REMOVIDA por isso — devolvê-la seria trocar a cura por um enfeite;
2. **o azul `player-5` é FUNCIONAL** (R-25, 25/07/2026): ele é o bit "+5" da
   numeração, que estende a barra de 4 para 9 números distinguíveis. Sem a linha
   dele, o slot 7 acende o mesmo padrão do slot 4 e dois controles ficam
   idênticos.

O QUE ELE NÃO PROVA
-------------------
Que o LED acende. Isto é um arquivo de regra: o teste lê o texto que será
instalado, não o `/sys` da máquina. Que o produto ESCREVA no nó é outra linha do
mapa (hoje o portão `EXTERNAL_PLAYER_LED_ENABLED` decide isso) — esta regra
responde só por deixar o nó gravável, que é o que a linha
`luz.led_jogador.udev@pro` afirma nos dois transportes: em modo Switch o Pro
publica os mesmos nós de LED pelo cabo e pelo rádio.

MORDE? Apague uma das linhas de `player-*`, troque o `chmod 0666` por
`TAG+="uaccess"`, ou renumere o arquivo para >= 73 — cada um reprova um teste
distinto deste arquivo.

MORDIDA PROVADA (15/08/2026, no espelho da árvore em `/tmp`, com a árvore de
trabalho intocada): ver a coluna `mordida_provada_em` da linha
`luz.led_jogador.udev@pro` do mapa de canais.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REGRA = REPO_ROOT / "assets" / "79-external-controller-leds.rules"

#: O VID da Nintendo como o kernel o escreve no nome do nó de LED (maiúsculo).
VID_NINTENDO = "057E"

#: Quem converte `TAG+="uaccess"` em ACL é a `73-seat-late.rules`. Regra >= 73
#: roda DEPOIS dela e a TAG morre inerte — a mesma régua do
#: `test_udev_input_uaccess_72.py`, aqui pelo avesso: esta regra é 79, então ela
#: NÃO pode depender de uaccess para nada.
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
    """As duas linhas que a linha `luz.led_jogador.udev@pro` do mapa nomeia.

    MORDIDA: apague a linha do `blue:player-*` e este teste reprova — é o bit
    "+5" do R-25, sem o qual o slot 7 volta a colidir com o slot 4.
    """
    blob = "\n".join(linhas)
    for cor in ("green", "blue"):
        alvo = f'KERNEL=="*{VID_NINTENDO}:*:{cor}:player-*"'
        assert alvo in blob, (
            f"a regra não cobre mais os LEDs `{cor}:player-*` do {VID_NINTENDO}: "
            "o nó fica root:root e a numeração do controle cai no default do "
            "kernel, sem erro nenhum"
        )


def test_toda_linha_torna_o_brightness_gravavel_no_plug(linhas: list[str]) -> None:
    """`ACTION=="add"` + `SUBSYSTEM=="leds"` + `chmod 0666` no `brightness`.

    O `add` é o que reaplica a cada replug/reconexão; sem ele a regra vale uma
    vez e o próximo plug volta ao root:root.
    """
    assert linhas, "o arquivo não tem linha de código nenhuma"
    for ln in linhas:
        assert 'ACTION=="add"' in ln, f"sem ACTION add (não reaplica no replug): {ln}"
        assert 'SUBSYSTEM=="leds"' in ln, f"sem SUBSYSTEM leds: {ln}"
        assert "/bin/chmod 0666" in ln, f"sem o chmod que dá a escrita: {ln}"
        assert "/sys/class/leds/%k/brightness" in ln, (
            f"o chmod tem de cair no `brightness` do próprio nó: {ln}"
        )


def test_a_regra_nunca_volta_a_depender_de_uaccess(linhas: list[str]) -> None:
    """A cura de 19/07: numa regra >= 73 a TAG `uaccess` NUNCA vira ACL.

    MORDIDA: troque o `RUN+="/bin/chmod 0666 …"` por `TAG+="uaccess"` e este
    teste reprova. É o dente que importa, porque a troca parece uma melhoria: o
    arquivo continua instalando e o `udevadm verify` continua aprovando.
    """
    blob = "\n".join(linhas)
    assert "uaccess" not in blob, (
        f"{REGRA.name} é numerada >= {LIMITE_UACCESS}: a TAG uaccess é inerte "
        "aqui (a 73-seat-late.rules já passou) e substituir o chmod por ela "
        "deixa o LED sem escrita sem que nada acuse"
    )
