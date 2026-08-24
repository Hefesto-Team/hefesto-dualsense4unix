"""O portão da palavra de tela enxerga a aba montada em Python — e só ela.

O DEFEITO QUE ESTE ARQUIVO FECHA, medido em 23/08/2026.
`scripts/validar-palavra-de-tela.py` lia UM arquivo: o `main.glade`. A aba
Configurações tem 4.605 linhas de Python com cem por cento do texto de tela em
código, e o portão era cego a ela: 212 rótulos vistos no XML, ZERO em `app/`.
Bastava injetar jargão banido num título de tela real de `app/` para o portão
continuar verde.

O QUE ESTE ARQUIVO COBRA, e são DUAS metades que valem só juntas:

* **ele acusa** jargão banido que chega à tela por Python;
* **ele CALA** sobre a mesma palavra quando ela é nome de variável, chave de
  dicionário, nome de sinal, valor de enum, classe de CSS, mensagem de log,
  comentário ou docstring.

A segunda metade é a que decide se o portão sobrevive. Um portão que grita
sobre o que não é texto de tela é desligado na primeira semana — e esta casa já
pagou por isso (`o-portao-que-nao-mede-o-que-promete`, 19/08/2026).

A RÉGUA, declarada: os testes chamam as funções do PRÓPRIO validador, carregado
do arquivo em `scripts/`. Nada é reimplementado aqui — uma cópia da regra
divergiria da original na primeira edição, e os dois passariam verdes medindo
coisas diferentes.
"""
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
    """O `validar-palavra-de-tela.py` importado como módulo.

    Ele mora em `scripts/` e tem hífen no nome, então não é importável pelo
    caminho normal.
    """
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


# --------------------------------------------------------------------------
# 1. O ALCANCE — o buraco medido, agora fechado.
# --------------------------------------------------------------------------


def test_o_portao_enxerga_o_texto_de_tela_montado_em_python(textos_de_app: list[Any]) -> None:
    """MEDIDO em 23/08/2026: 294 textos, 242 únicos. Antes eram ZERO.

    O piso é 200 e não 294 de propósito: o número exato cai quando uma frase é
    fundida ou some, e um teste que trava o número vira manutenção sem
    informação. O que ele defende é a ORDEM DE GRANDEZA — se o alcance
    despencar para dezenas, alguma coisa quebrou o reconhecimento de
    escoadouro, e é isso que precisa acordar alguém.
    """
    unicos = {rotulo.texto for rotulo in textos_de_app}
    assert len(unicos) >= 200, (
        f"o portão só enxerga {len(unicos)} textos de tela em app/; em "
        "23/08/2026 eram 242. Um escoadouro deixou de ser reconhecido."
    )


def test_o_titulo_de_cada_secao_da_aba_configuracoes_esta_no_alcance(
    textos_de_app: list[Any],
) -> None:
    """A prova de que a constante que ATRAVESSA módulo é vista.

    `TITULO` e `DICA` são declarados em `secao_*.py` e consumidos em
    `config/mixin.py:46` por `moldura_de_secao(secao.TITULO, secao.DICA)`.
    Nenhum literal desses títulos aparece perto de um `set_label`. Se o portão
    os vê, é porque seguiu o fluxo — que é a regra inteira.
    """
    from hefesto_dualsense4unix.app.actions.config.secoes import SECOES_DA_ABA

    vistos = {rotulo.texto for rotulo in textos_de_app}
    faltando = [secao.TITULO for secao in SECOES_DA_ABA if secao.TITULO not in vistos]
    assert not faltando, (
        "títulos de seção da aba Configurações fora do alcance do portão: "
        f"{faltando}. O contrato `secao.TITULO` parou de ser seguido."
    )


def test_os_nomes_que_atravessam_modulo_sao_so_o_contrato_da_aba(
    nomes_de_tela: set[str],
) -> None:
    """Só `TITULO` e `DICA` — e este teste existe por um falso positivo real.

    A primeira versão da regra não cortava por POSIÇÃO de argumento, e
    `add_button("Fechar", Gtk.ResponseType.CLOSE)` fazia `CLOSE`, `CANCEL`,
    `OK`, `APPLY` e `REJECT` entrarem como "nome de constante de tela". Efeito:
    toda constante de módulo chamada `OK` da árvore viraria texto de tela.

    Se este teste crescer, a pergunta certa é "que escoadouro passou a aceitar
    argumento demais?", e não "adiciono o nome novo à lista?".
    """
    assert nomes_de_tela == {"TITULO", "DICA"}, (
        f"nomes que atravessam módulo: {sorted(nomes_de_tela)}. Esperados só "
        "TITULO e DICA (o contrato de `config/secoes.py:23`)."
    )


# --------------------------------------------------------------------------
# 2. A MORDIDA, metade 1: jargão que CHEGA à tela reprova.
# --------------------------------------------------------------------------

#: Um módulo com a forma EXATA de uma seção da aba Configurações: constante de
#: título consumida por atributo, ajudante de rótulo, gettext e `set_markup`.
#: O jargão está em quatro caminhos diferentes, e o portão tem de achar os
#: quatro.
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

    achados = validador.conferir_python(alvo, nomes_de_tela)
    juntos = "\n".join(achados)

    for esperado in (
        "Daemon offline agora",  # constante TITULO, por atributo
        "O daemon pausado não responde.",  # constante DICA, por atributo
        "Confira se o uinput disponível está lá.",  # ajudante da casa
        "Gamepads: nenhum",  # gettext
        "daemon offline: {}",  # f-string remontada dentro de set_markup
    ):
        assert esperado in juntos, (
            f"o portão não acusou {esperado!r}.\nAchados:\n{juntos}"
        )


# --------------------------------------------------------------------------
# 3. A MORDIDA, metade 2: a MESMA palavra fora da tela tem de CALAR.
# --------------------------------------------------------------------------

#: Todo lugar onde `daemon offline` e companhia aparecem SEM ir para a tela.
#: Cada bloco é uma categoria que o enunciado do portão promete não acusar, e
#: os três últimos são constantes REAIS de `app/`, copiadas daqui de dentro.
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
    """A metade que CALA — e ela é a que decide se o portão sobrevive.

    Dez categorias de `daemon offline` fora da tela num arquivo só. Uma única
    reprovação aqui significa que o portão passou a responder "esta string
    aparece na tela?" pela FORMA da string, e não pelo fluxo — que é o
    caminho para ele ser desligado.
    """
    alvo = tmp_path / "modulo_sem_tela.py"
    alvo.write_text(MODULO_SEM_TELA, encoding="utf-8")

    achados = validador.conferir_python(alvo, nomes_de_tela)
    assert achados == [], (
        "o portão acusou o que NÃO é texto de tela:\n" + "\n".join(achados)
    )


def test_o_unico_texto_de_tela_do_modulo_mudo_e_o_rotulo_limpo(
    tmp_path: Path, validador: Any, nomes_de_tela: set[str]
) -> None:
    """Prova que o silêncio acima é alcance certo, e não cegueira.

    Sem este teste, `conferir_python` podendo devolver lista vazia por não ter
    lido nada passaria pelo teste anterior com louvor. Aqui se cobra que ele
    tenha visto EXATAMENTE o rótulo que vai para a tela, e nenhuma das dez
    aparições de jargão que não vão.
    """
    alvo = tmp_path / "modulo_sem_tela.py"
    alvo.write_text(MODULO_SEM_TELA, encoding="utf-8")

    vistos = {rotulo.texto for rotulo in validador.rotulos_do_python(alvo, nomes_de_tela)}
    assert vistos == {"Tudo certo por aqui", "Fechar"}, (
        f"o portão enxergou {sorted(vistos)}; esperado só o rótulo e o botão."
    )


# --------------------------------------------------------------------------
# 4. As constantes REAIS de `app/` que não podem entrar.
# --------------------------------------------------------------------------


def test_o_portao_ignora_as_constantes_de_app_que_nao_sao_tela(
    textos_de_app: list[Any],
) -> None:
    """Três casos reais, cada um de uma família diferente de falso positivo.

    `TRAY_APP_ID` é o que mais custou: `indicator_cls.new(TRAY_APP_ID, ...)`
    parecia construtor de widget enquanto `new` genérico estava na lista de
    escoadouros, e o id do aplicativo entrava como texto de tela.
    """
    vistos = {rotulo.texto for rotulo in textos_de_app}
    for fora_da_tela in (
        "desktop",  # MODE_DESKTOP, valor de protocolo
        "/dev/uinput",  # UINPUT_DEV, caminho de dispositivo
        "hefesto-dualsense4unix",  # TRAY_APP_ID, id do aplicativo
        "identity",  # _IDENTITY_FIELD, chave de dicionário
        "escala_fonte",  # CHAVE_ESCALA, chave de preferência
    ):
        assert fora_da_tela not in vistos, (
            f"{fora_da_tela!r} entrou como texto de tela. Ele não é: nenhuma "
            "dessas strings chega a escoadouro de tela."
        )


# --------------------------------------------------------------------------
# 5. A dívida declarada não envelhece calada.
# --------------------------------------------------------------------------


def test_a_divida_de_app_que_sumir_reprova_pedindo_para_apagar(validador: Any) -> None:
    """A mesma regra da dívida do `.glade`, agora do lado do Python.

    Uma entrada de `DIVIDA_DA_PALAVRA_01_PY` que não corresponde mais a
    nenhuma frase de `app/` tem de reprovar — senão a lista vira o armário
    onde se guarda o que incomoda, e o portão passa a perdoar frase que nem
    existe.
    """
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
