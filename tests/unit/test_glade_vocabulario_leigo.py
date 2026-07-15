"""O `main.glade` não mostra jargão na tela (LEIGO-03 + LEIGO-06).

Lê o XML do Glade e olha só o que a usuária LÊ: `label` e `tooltip-text`. Ids,
handlers e nomes de classe ficam de fora de propósito — eles são código, e o
sprint é sobre texto (trocar id de Glade quebraria os handlers).

Por que testar o XML e não a janela: montar o `Gtk.Builder` exige display; o
contrato aqui é textual e o arquivo é a fonte da verdade.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_GLADE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "main.glade"
)


def _textos_visiveis() -> list[str]:
    """Todo texto que chega aos olhos: rótulos e tooltips."""
    raiz = ET.parse(_GLADE).getroot()
    return [
        prop.text
        for prop in raiz.iter("property")
        if prop.get("name") in {"label", "tooltip-text"} and prop.text
    ]


def test_glade_existe_e_tem_texto() -> None:
    """Guarda contra o teste virar vacuoso se o caminho mudar."""
    assert _textos_visiveis()


@pytest.mark.parametrize(
    "jargao",
    [
        "systemctl",
        "systemd",
        "rc=",
        ".service",
        "Unit:",
        "Motor fraco",
        "Motor forte",
        "weak",
        "strong",
        "Throttle",
        "throttle",
        "Política de rumble",
        "Preview do perfil",
        "JSON",
        "Anti-storm",
        "sudo",
    ],
)
def test_jargao_nao_aparece_na_tela(jargao: str) -> None:
    ofensores = [t for t in _textos_visiveis() if jargao in t]
    assert not ofensores, f"{jargao!r} ainda visível em: {ofensores}"


def test_aba_daemon_virou_sistema() -> None:
    """LEIGO-03. A aba é achada pelo id do Glade (`daemon_box`) — o EST-10 foi
    justamente o código identificar a página pelo TEXTO."""
    textos = _textos_visiveis()
    assert "Sistema" in textos
    assert "Daemon" not in textos


def test_ids_carregados_pelo_codigo_continuam_existindo() -> None:
    """LEIGO-03/06 mexem em TEXTO. Se um id sumir junto, o handler
    correspondente vira no-op SILENCIOSO (`self._get` devolve None)."""
    raiz = ET.parse(_GLADE).getroot()
    ids = {obj.get("id") for obj in raiz.iter("object")}
    for esperado in (
        "daemon_box",
        "daemon_status_label",
        "daemon_status_text",
        "daemon_autostart_switch",
        "daemon_start_button",
        "daemon_stop_button",
        "daemon_logs_button",
        "btn_restart_daemon",
        "btn_migrate_to_systemd",
        "storm_diag_label",
        "rumble_weak_scale",
        "rumble_strong_scale",
        "rumble_passthrough",
        "profiles_tree",
    ):
        assert esperado in ids, f"id {esperado!r} sumiu do glade"


def test_vibracao_fala_de_vibracao_e_nao_de_motor() -> None:
    """LEIGO-06: os sliders do teste de vibração."""
    textos = _textos_visiveis()
    assert "Vibração leve" in textos
    assert "Vibração forte" in textos
    assert "Intensidade da vibração" in textos


def test_botao_de_passthrough_fala_do_jogo() -> None:
    assert "Deixar o jogo controlar a vibração" in _textos_visiveis()


def test_tooltips_citam_botoes_que_existem() -> None:
    """O tooltip do 'Parar' mandava clicar em 'Devolver rumble ao jogo'; se o
    rótulo do botão mudar de novo, o tooltip tem de acompanhar."""
    textos = _textos_visiveis()
    rotulo = "Deixar o jogo controlar a vibração"
    citacoes = [t for t in textos if "Devolver rumble ao jogo" in t]
    assert not citacoes, f"tooltip cita um botão que não existe mais: {citacoes}"
    assert any(rotulo in t and t != rotulo for t in textos), (
        "nenhum tooltip aponta para o botão que devolve a vibração ao jogo"
    )
