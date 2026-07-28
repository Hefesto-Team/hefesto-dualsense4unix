"""Testes dos widgets de preview (W5.2).

GATE-EMOJI-01 (27/07/2026) — por que nenhum glifo aparece desenhado aqui
=======================================================================

Este arquivo e ``src/hefesto_dualsense4unix/tui/widgets/__init__.py``
guardavam os MESMOS literais de desenho (cerca de 20 de cada lado). O
higienizador do ambiente apaga esses codepoints — que o ADR-011 manda
preservar — e reescreve o arquivo antes de qualquer revisão. Como quem mexe no
``BatteryMeter`` mexe no teste dele, os dois entram no mesmo passe: a função
passa a devolver string vazia, o valor esperado do teste passa a ser string
vazia, e o teste fica VERDE com a função quebrada. Foi o incidente de
21/04/2026, e ele se repetiu em 26/07.

A cura tem duas metades e as duas importam:

1. o esperado nasce de ``chr()`` sobre o codepoint, então nenhuma ferramenta de
   texto consegue mutá-lo;
2. as constantes abaixo são declaradas AQUI, nunca importadas do módulo sob
   teste. Se o teste importasse ``_PILHA_CHEIA`` da produção, arrancar o glifo
   de lá mudaria o esperado junto e o teste voltaria a ser verde por nada.

Há ainda um terceiro cinto: ``test_icone_bateria_e_a_tabela_de_codepoints``
compara ``ord()`` com números inteiros. Esse não depende nem de ``chr()``.
"""
from __future__ import annotations

from hefesto_dualsense4unix.tui.widgets import BatteryMeter, StickPreview, TriggerBar

# Tabela de codepoints do ADR-011 usada por este teste. Declarada aqui de
# propósito (ver o cabeçalho): é a referência independente contra a qual a
# produção é medida.
BLOCO_CHEIO = chr(0x2588)  # FULL BLOCK
BLOCO_VAZIO = chr(0x2591)  # LIGHT SHADE
PILHA_CHEIA = chr(0x25AE)  # BLACK VERTICAL RECTANGLE
PILHA_VAZIA = chr(0x25AF)  # WHITE VERTICAL RECTANGLE
PONTO_GRADE = chr(0x00B7)  # MIDDLE DOT

LARGURA_BARRA = 30


class TestTriggerBar:
    def test_zero_renderiza_barra_vazia(self):
        bar = TriggerBar("L2", 0)
        rendered = bar.render()
        assert "L2" in rendered
        assert BLOCO_VAZIO in rendered
        assert "0/255" in rendered
        assert "[green]" in rendered

    def test_meio_faixa_amarela(self):
        bar = TriggerBar("R2", 128)
        rendered = bar.render()
        assert "[yellow]" in rendered

    def test_cheio_faixa_vermelha(self):
        bar = TriggerBar("R2", 250)
        rendered = bar.render()
        assert "[red]" in rendered
        assert "250/255" in rendered

    def test_clamp_acima_de_255(self):
        bar = TriggerBar("L2", 300)
        rendered = bar.render()
        assert "255/255" in rendered

    def test_clamp_negativo(self):
        bar = TriggerBar("L2", -10)
        rendered = bar.render()
        assert "0/255" in rendered


class TestBatteryMeter:
    def test_none_mostra_interrogacao(self):
        m = BatteryMeter(None)
        rendered = m.render()
        assert "?" in rendered

    def test_100_pct_verde(self):
        m = BatteryMeter(100)
        rendered = m.render()
        assert "[green]" in rendered
        assert "100%" in rendered

    def test_15_pct_vermelho(self):
        m = BatteryMeter(15)
        rendered = m.render()
        assert "[red]" in rendered

    def test_charging_mostra_indicador(self):
        m = BatteryMeter(50, charging=True)
        rendered = m.render()
        assert "CHG" in rendered

    def test_icon_bateria_varia_com_nivel(self):
        assert BatteryMeter._icon_for_level(100) == PILHA_CHEIA * 4
        assert BatteryMeter._icon_for_level(70) == PILHA_CHEIA * 3 + PILHA_VAZIA
        assert BatteryMeter._icon_for_level(50) == PILHA_CHEIA * 2 + PILHA_VAZIA * 2
        assert BatteryMeter._icon_for_level(30) == PILHA_CHEIA + PILHA_VAZIA * 3
        assert BatteryMeter._icon_for_level(5) == PILHA_VAZIA * 4

    def test_icone_bateria_e_a_tabela_de_codepoints(self):
        """Mede ``ord()`` contra inteiros — sem ``chr()``, sem literal, sem desenho.

        É o cinto que sobrevive até a um higienizador que soubesse reescrever
        chamadas de ``chr()``: aqui o esperado é aritmética.
        """
        assert [ord(c) for c in BatteryMeter._icon_for_level(100)] == [
            0x25AE,
            0x25AE,
            0x25AE,
            0x25AE,
        ]
        assert [ord(c) for c in BatteryMeter._icon_for_level(70)] == [
            0x25AE,
            0x25AE,
            0x25AE,
            0x25AF,
        ]
        assert [ord(c) for c in BatteryMeter._icon_for_level(5)] == [
            0x25AF,
            0x25AF,
            0x25AF,
            0x25AF,
        ]

    def test_icone_sempre_tem_quatro_celulas(self):
        """Nenhum nível pode devolver desenho vazio ou de tamanho estranho."""
        for nivel in range(-10, 111):
            icone = BatteryMeter._icon_for_level(nivel)
            assert len(icone) == 4, f"nível {nivel} devolveu {len(icone)} células"
            assert set(icone) <= {PILHA_CHEIA, PILHA_VAZIA}

    def test_render_carrega_o_icone_desenhado(self):
        """A cura tem de chegar até a tela, não só até a função privada."""
        rendered = BatteryMeter(100).render()
        assert rendered.startswith(PILHA_CHEIA * 4 + " ")
        assert PILHA_CHEIA * 2 + PILHA_VAZIA * 2 in BatteryMeter(50).render()

    def test_valor_fora_de_range_satura(self):
        m = BatteryMeter(150)
        rendered = m.render()
        assert "100%" in rendered

        m2 = BatteryMeter(-10)
        rendered2 = m2.render()
        assert "0%" in rendered2


class TestStickPreview:
    def test_centro_renderiza_com_plus(self):
        s = StickPreview("L", 128, 128)
        rendered = s.render()
        # Centro tem o '+' dim e o 'o' yellow sobrepostos (o 'o' ganha prioridade)
        assert "[yellow]o[/]" in rendered or "[dim]+[/]" in rendered
        assert "L" in rendered

    def test_extremos(self):
        s = StickPreview("R", 0, 0)
        rendered = s.render()
        assert "[yellow]o[/]" in rendered
        s2 = StickPreview("R", 255, 255)
        rendered2 = s2.render()
        assert "[yellow]o[/]" in rendered2

    def test_linhas_certas(self):
        s = StickPreview("L", 128, 128)
        rendered = s.render()
        # 5 linhas + label
        lines = rendered.split("\n")
        assert len(lines) == 6  # label + 5 linhas

    def test_fundo_da_grade_e_o_ponto(self):
        rendered = StickPreview("L", 0, 0).render()
        assert PONTO_GRADE in rendered
        assert ord(PONTO_GRADE) == 0x00B7


def test_color_for_trigger_faixas():
    from hefesto_dualsense4unix.tui.widgets import _color_for_trigger

    assert _color_for_trigger(0) == "green"
    assert _color_for_trigger(85) == "green"
    assert _color_for_trigger(86) == "yellow"
    assert _color_for_trigger(170) == "yellow"
    assert _color_for_trigger(171) == "red"
    assert _color_for_trigger(255) == "red"


def test_color_for_battery_faixas():
    from hefesto_dualsense4unix.tui.widgets import _color_for_battery

    assert _color_for_battery(100) == "green"
    assert _color_for_battery(41) == "green"
    assert _color_for_battery(40) == "yellow"
    assert _color_for_battery(16) == "yellow"
    assert _color_for_battery(15) == "red"
    assert _color_for_battery(0) == "red"


def test_bar_progresso():
    from hefesto_dualsense4unix.tui.widgets import _bar

    assert _bar(0) == BLOCO_VAZIO * LARGURA_BARRA
    assert _bar(255) == BLOCO_CHEIO * LARGURA_BARRA
    mid = _bar(128)
    assert BLOCO_CHEIO in mid
    assert BLOCO_VAZIO in mid


def test_bar_e_a_tabela_de_codepoints():
    """Mesma medida do ícone: ``ord()`` contra inteiro, sem desenho no meio."""
    from hefesto_dualsense4unix.tui.widgets import _bar

    assert {ord(c) for c in _bar(0)} == {0x2591}
    assert {ord(c) for c in _bar(255)} == {0x2588}
    assert {ord(c) for c in _bar(128)} == {0x2588, 0x2591}
    assert len(_bar(128)) == LARGURA_BARRA


def test_nenhum_glifo_desenhado_neste_arquivo_nem_na_producao():
    """O portão desta sprint, aplicado aos dois arquivos que ele protege.

    Se alguém voltar a colar um desenho em qualquer um dos dois, este teste
    reprova — antes que o higienizador apague os dois no mesmo passe e o resto
    da suíte fique verde por nada.
    """
    import pathlib

    from hefesto_dualsense4unix.tui import widgets as modulo

    faixas_protegidas = (
        (0x2190, 0x21FF),  # Arrows
        (0x2500, 0x257F),  # Box Drawing
        (0x2580, 0x259F),  # Block Elements
        (0x25A0, 0x25FF),  # Geometric Shapes
    )
    alvos = [pathlib.Path(__file__), pathlib.Path(modulo.__file__)]
    achados: list[str] = []
    for alvo in alvos:
        for n_linha, linha in enumerate(
            alvo.read_text(encoding="utf-8").split("\n"), start=1
        ):
            for coluna, ch in enumerate(linha, start=1):
                if any(ini <= ord(ch) <= fim for ini, fim in faixas_protegidas):
                    achados.append(
                        f"{alvo.name}:{n_linha}:{coluna} U+{ord(ch):04X}"
                    )
    assert not achados, "glifo desenhado (use chr(0x....)): " + ", ".join(achados)
