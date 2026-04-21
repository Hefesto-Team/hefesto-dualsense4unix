"""Testes dos widgets de preview (W5.2)."""
from __future__ import annotations

from hefesto.tui.widgets import BatteryMeter, StickPreview, TriggerBar


class TestTriggerBar:
    def test_zero_renderiza_barra_vazia(self):
        bar = TriggerBar("L2", 0)
        rendered = bar.render()
        assert "L2" in rendered
        assert "░" in rendered
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
        assert BatteryMeter._icon_for_level(100) == "▮▮▮▮"
        assert BatteryMeter._icon_for_level(70) == "▮▮▮▯"
        assert BatteryMeter._icon_for_level(50) == "▮▮▯▯"
        assert BatteryMeter._icon_for_level(30) == "▮▯▯▯"
        assert BatteryMeter._icon_for_level(5) == "▯▯▯▯"

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


def test_color_for_trigger_faixas():
    from hefesto.tui.widgets import _color_for_trigger

    assert _color_for_trigger(0) == "green"
    assert _color_for_trigger(85) == "green"
    assert _color_for_trigger(86) == "yellow"
    assert _color_for_trigger(170) == "yellow"
    assert _color_for_trigger(171) == "red"
    assert _color_for_trigger(255) == "red"


def test_color_for_battery_faixas():
    from hefesto.tui.widgets import _color_for_battery

    assert _color_for_battery(100) == "green"
    assert _color_for_battery(41) == "green"
    assert _color_for_battery(40) == "yellow"
    assert _color_for_battery(16) == "yellow"
    assert _color_for_battery(15) == "red"
    assert _color_for_battery(0) == "red"


def test_bar_progresso():
    from hefesto.tui.widgets import _bar

    assert _bar(0) == "░" * 30
    assert _bar(255) == "█" * 30
    mid = _bar(128)
    assert "█" in mid
    assert "░" in mid
