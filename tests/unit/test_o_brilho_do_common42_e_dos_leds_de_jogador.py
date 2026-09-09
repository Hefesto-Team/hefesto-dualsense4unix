"""O `common[42]` é o brilho dos LEDS DE JOGADOR — e o produto manda ali o da BARRA.

MEDIDO POR ELA EM 09/09/2026, na bancada, com um DualSense no cabo e outro no
rádio, mexendo um controle deslizante e olhando o aparelho. Palavra dela:

    "o que o slicer altera não são as cores do lightbar mas os leds que indicam
    qual player é o dono daquele controle, tipo player 1...2 e tanto no cabo
    quanto bt eles tem o mesmo impacto e precisam da autorização do byte"

Até esse dia esta casa chamava o byte de *brilho da lightbar* — no comentário
de `ds_output_report.py`, na chave `luz.lightbar.brilho` do mapa e na sprint
BRILHO-DE-HARDWARE-01. A fonte externa já dizia o certo e ninguém tinha olhado:
`flag_2: SET_PLAYER_LED_BRIGHTNESS 0x01` (RPCS3 `.h:26-44`).

O QUE ESTE TESTE GUARDA, e por que ele é DE DÍVIDA e não de feature
-------------------------------------------------------------------
`backend_pydualsense` escreve `common[42] = self.light.brightness.value` — o
brilho da BARRA — e **nunca liga** o `flag2` bit0. Hoje isso é inerte: sem o
bit, o firmware ignora o byte. O risco é do dia seguinte: alguém liga o bit
para "fazer o brilho funcionar", e o que escurece são as lâmpadas de numeração.

Então a régua tem DUAS metades, e a segunda é a que morde:

1. a constante do bit diz de qual LED ela é (o fato substituído fica escrito);
2. enquanto a FONTE do valor for `light.brightness`, o bit tem de continuar
   desligado. Ligar um sem trocar o outro reprova aqui, nomeando a dívida.

A prova do aparelho não mora num teste: mora em `docs/data/ensaios.csv`
(`painel-do-brilho-*-0909`), porque quem a produziu foi o olho dela.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
REPORT = RAIZ / "src/hefesto_dualsense4unix/core/ds_output_report.py"
BACKEND = RAIZ / "src/hefesto_dualsense4unix/core/backend_pydualsense.py"

#: A linha que escreve o byte, e a fonte do valor que ela usa hoje.
_ESCRITA_DO_42 = re.compile(r"common\[42\]\s*=\s*int\(self\.light\.(\w+)\.value\)")

#: Quem LIGA o bit (um `|=` sobre o flag2 com a constante). Desligar (`&= ~`)
#: não conta — é o que o `suppress_leds` faz, e é o oposto do risco.
_LIGA_O_BIT = re.compile(
    r"flag2\s*\|=[^\n]*VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE"
    r"|flag2\s*\|=\s*\(\s*[^)]*VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE",
    re.S,
)


def test_a_constante_diz_de_qual_led_ela_e() -> None:
    """O fato substituído fica escrito onde alguém vai lê-lo antes de usar."""
    fonte = REPORT.read_text(encoding="utf-8")
    trecho = fonte.split("VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE")[0][-1200:]
    assert "LEDS DE JOGADOR" in trecho.upper(), (
        "o comentário da VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE tem de dizer que o "
        "byte é dos LEDs de jogador. Ele dizia «BRILHO da lightbar» até 09/09/2026, e "
        "foi por isso que a chave do mapa nasceu com o dono errado."
    )
    assert "NÃO É O BRILHO DA LIGHTBAR" in trecho.upper(), (
        "o desmentido tem de estar junto da constante: quem lê o nome dela em inglês "
        "conclui «lightbar» sozinho, que foi o que esta casa fez por um mês."
    )


def test_a_constante_existe_e_e_o_bit_zero() -> None:
    """Régua que não acha o alvo dá verde sobre o vazio."""
    arvore = ast.parse(REPORT.read_text(encoding="utf-8"))
    valores = {
        alvo.id: no.value.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.Constant)
        for alvo in no.targets
        if isinstance(alvo, ast.Name)
    }
    assert valores.get("VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE") == 0x01
    assert valores.get("COMMON_VALID_FLAG2") == 38


def test_o_bit_fica_desligado_enquanto_a_fonte_do_valor_for_a_barra() -> None:
    """A METADE QUE MORDE.

    Ligar o bit mandando `light.brightness` faz o produto atenuar as lâmpadas
    de numeração achando que escurece a barra. Enquanto os dois andarem juntos,
    isto reprova — e a mensagem diz o que fazer.
    """
    fonte = BACKEND.read_text(encoding="utf-8")
    escrita = _ESCRITA_DO_42.search(fonte)
    assert escrita is not None, (
        "ninguém escreve mais `common[42] = int(self.light.<x>.value)` no backend. "
        "Se a fonte do valor mudou, esta régua tem de mudar junto — leia a docstring."
    )
    fonte_do_valor = escrita.group(1)
    liga = _LIGA_O_BIT.search(fonte)
    if fonte_do_valor == "brightness":
        assert liga is None, (
            "o produto passou a LIGAR o `flag2` bit0 e continua mandando "
            "`light.brightness` no `common[42]`. Esse byte é o brilho dos LEDS DE "
            "JOGADOR (medido por ela em 09/09/2026): o efeito é atenuar as lâmpadas "
            "de numeração, não a barra.\n"
            "Para fechar isto de verdade, o valor tem de vir de um campo próprio do "
            "brilho das lâmpadas — e aí esta régua muda com ele."
        )
