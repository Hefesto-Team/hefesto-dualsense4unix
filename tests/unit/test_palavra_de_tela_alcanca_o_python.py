"""O portão da palavra de tela enxerga a aba montada em Python — e só ela."""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"


def _validador() -> Any:
    """O `validar-palavra-de-tela.py` importado como módulo."""
    caminho = RAIZ / "scripts" / "validar-palavra-de-tela.py"
    spec = importlib.util.spec_from_file_location("_validador_de_tela", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_validador_de_tela"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def validador() -> Any:
    return _validador()


@pytest.fixture(scope="module")
def nomes_de_tela(validador: Any) -> set[str]:
    """Os nomes de constante que atravessam módulo até um escoadouro."""
    arvores = {
        caminho: ast.parse(caminho.read_text(encoding="utf-8"))
        for caminho in validador.arquivos_de_python()
    }
    return set(validador.nomes_de_constante_de_tela(arvores))


@pytest.fixture(scope="module")
def textos_de_app(validador: Any, nomes_de_tela: set[str]) -> list[Any]:
    """Todo texto de tela que o portão enxerga em `app/`."""
    return [
        rotulo
        for caminho in validador.arquivos_de_python()
        for rotulo in validador.rotulos_do_python(caminho, nomes_de_tela)
    ]


MODULO_COM_JARGAO = '''
"""Uma seção de mentira, com a forma real de `app/actions/config/secao_*.py`."""
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config.moldura import rotulo_de_apoio
from hefesto_dualsense4unix.utils.i18n import _

TITULO = "Daemon offline agora"
DICA = "O daemon pausado não responde."


def montar(host, caixa):
    caixa.add(rotulo_de_apoio("Confira se o uinput disponível está lá."))
    rotulo = Gtk.Label(label=_("Gamepads: nenhum"))
    rotulo.set_markup(f"<span foreground=\\"#ff5555\\">daemon offline: {host}</span>")
    caixa.add(rotulo)
'''


def test_jargao_num_titulo_de_tela_de_python_reprova(
    tmp_path: Path, validador: Any, nomes_de_tela: set[str]
) -> None:
    """A metade que ACUSA — pelos quatro caminhos que a aba usa de verdade."""
    alvo = tmp_path / "secao_de_mentira.py"
    alvo.write_text(MODULO_COM_JARGAO, encoding="utf-8")

    achados = validador.conferir_python(alvo, nomes_de_tela | {"TITULO", "DICA"})
    juntos = "\n".join(achados)

    for esperado in (
        "Daemon offline agora",
        "O daemon pausado não responde.",
        "Confira se o uinput disponível está lá.",
        "Gamepads: nenhum",
        "daemon offline: {}",
    ):
        assert esperado in juntos, (
            f"o portão não acusou {esperado!r}.\nAchados:\n{juntos}"
        )


MODULO_SEM_TELA = '''
"""Um módulo que fala de daemon offline o tempo todo e não põe nada na tela.

Nem esta docstring, que menciona uinput disponível, deve acusar.
"""
from gi.repository import Gtk

# Comentário: daemon offline, daemon pausado, Restaurar Default.

# nome de variável e de função
daemon_offline = True
uinput_disponivel = False


def restaurar_default_do_daemon_offline():
    return daemon_offline


# chave de dicionário e valor de dado
ESTADOS = {"daemon offline": 1, "daemon pausado": 2}
MOTIVOS = ["uinput disponível", "Gamepads:"]

# valor de enum / constante de protocolo, id de widget, classe de CSS
MODE_DESKTOP = "desktop"
UINPUT_DEV = "/dev/uinput"
TRAY_APP_ID = "hefesto-dualsense4unix"
ID_DO_BOTAO = "btn_daemon_offline"
CLASSE_CSS = "daemon-offline"


def montar(host, logger, botao, caixa):
    # nome de sinal
    botao.connect("clicked", host.on_daemon_offline)
    botao.set_name(ID_DO_BOTAO)
    botao.get_style_context().add_class(CLASSE_CSS)

    # mensagem de log e de exceção
    logger.warning("daemon offline ao aplicar perfil")
    if not daemon_offline:
        raise RuntimeError("daemon pausado")

    # leitura de dicionário: a chave é dado, não rótulo
    host.estado = ESTADOS["daemon offline"]

    # construtor de diálogo com valor de enum na posição 1
    dialogo = Gtk.Dialog()
    dialogo.add_button("Fechar", Gtk.ResponseType.CLOSE)

    # o único texto de tela do módulo, e ele está limpo
    caixa.add(Gtk.Label(label="Tudo certo por aqui"))
'''


def test_a_mesma_palavra_fora_da_tela_faz_o_portao_calar(
    tmp_path: Path, validador: Any, nomes_de_tela: set[str]
) -> None:
    """A metade que CALA — e ela é a que decide se o portão sobrevive."""
    alvo = tmp_path / "modulo_sem_tela.py"
    alvo.write_text(MODULO_SEM_TELA, encoding="utf-8")

    achados = validador.conferir_python(alvo, nomes_de_tela)
    assert achados == [], (
        "o portão acusou o que NÃO é texto de tela:\n" + "\n".join(achados)
    )


def test_o_unico_texto_de_tela_do_modulo_mudo_e_o_rotulo_limpo(
    tmp_path: Path, validador: Any, nomes_de_tela: set[str]
) -> None:
    """Prova que o silêncio acima é alcance certo, e não cegueira."""
    alvo = tmp_path / "modulo_sem_tela.py"
    alvo.write_text(MODULO_SEM_TELA, encoding="utf-8")

    vistos = {rotulo.texto for rotulo in validador.rotulos_do_python(alvo, nomes_de_tela)}
    assert vistos == {"Tudo certo por aqui", "Fechar"}, (
        f"o portão enxergou {sorted(vistos)}; esperado só o rótulo e o botão."
    )


def test_a_divida_de_app_que_sumir_reprova_pedindo_para_apagar(validador: Any) -> None:
    """A mesma regra da dívida do `.glade`, agora do lado do Python."""
    validador.DIVIDA_DA_PALAVRA_01_PY["Daemon offline de mentira"] = "23/08/2026 — teste."
    try:
        achados = validador.conferir_app()
    finally:
        del validador.DIVIDA_DA_PALAVRA_01_PY["Daemon offline de mentira"]

    assert any("Daemon offline de mentira" in achado for achado in achados), (
        "a dívida inexistente passou calada:\n" + "\n".join(achados)
    )
    assert any("APAGUE a entrada" in achado for achado in achados)


def test_a_arvore_de_hoje_passa_no_portao(validador: Any) -> None:
    """`--all` verde, com a dívida de 23/08/2026 declarada e nada além dela."""
    assert validador.main(["--all"]) == 0


def test_o_portao_ignora_as_constantes_de_app_que_nao_sao_tela(
    textos_de_app: list[Any],
) -> None:
    """Três casos reais, cada um de uma família diferente de falso positivo."""
    vistos = {rotulo.texto for rotulo in textos_de_app}
    for fora_da_tela in (
        "desktop",
        "/dev/uinput",
        "hefesto-dualsense4unix",
        "identity",
        "escala_fonte",
    ):
        assert fora_da_tela not in vistos, (
            f"{fora_da_tela!r} entrou como texto de tela. Ele não é: nenhuma "
            "dessas strings chega a escoadouro de tela."
        )
