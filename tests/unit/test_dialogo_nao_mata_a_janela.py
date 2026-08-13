"""DIÁLOGO-QUE-MATA-A-JANELA-01 — o aviso que deixou a janela dela morta (06/08).

Em 06/08/2026, às 20h22, ela baixava a prioridade do perfil "Vitória" de 78
para 0 na aba Perfis quando a janela morreu: *"interface travou legal aqui. nem
consigo fazer nada nem fechar"*. O ``py-spy`` (PID 3878063) pegou a thread
principal parada em ``dialog.run()`` dentro do ``confirm_downgrade_priority`` —
e a foto da tela dela, tirada no mesmo minuto, **não tinha diálogo nenhum**.

Este módulo guarda as três testemunhas da cura e o portão da classe:

- **as três testemunhas rodam com GTK de verdade, sob ``xvfb-run``, num
  subprocesso.** Não é preciosismo: o envelope da casa chama ``present()`` num
  toplevel real, e um teste que fizesse isso no processo do ``pytest`` abriria
  uma janela **na tela dela** — o defeito que estamos curando, repetido pelo
  teste. O subprocesso também é o que dá a MORDIDA principal: arrancado o
  vigia, o ``run()`` nunca retorna, o subprocesso estoura o prazo e o teste
  reprova com a frase do defeito;
- **o portão** (por AST) reprova qualquer ``.run()`` bloqueante novo em
  ``app/`` fora do envelope, no idioma da casa: lista de autorizados que só
  encolhe (precedente: ``test_gravacao_de_perfil_passa_pelo_funil.py``).

A CONDIÇÃO REPRODUZIDA, E POR QUE ESTA
---------------------------------------
Não dá para trazer o ``cosmic-comp`` para a bancada. O que dá — e foi MEDIDO em
06/08/2026 — é reproduzir o ESTADO em que a janela dela morreu: um diálogo que
o GTK jura ter mostrado e que o servidor gráfico não exibe. Retirando o
``GdkWindow`` do diálogo (``get_window().hide()`` -> ``WITHDRAWN``), o GTK
responde ``get_mapped()=True`` e ``get_visible()=True`` (as duas mentiras) e
``is_active()=False`` (a verdade). É exatamente o quadro dela: processo vivo,
laço rodando, nada na tela, nenhuma resposta possível.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira no CI
# headless, em vez de pular.
exigir_gi_real("diálogo que não mata a janela")

import ast
import inspect
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_APP = _RAIZ / "src" / "hefesto_dualsense4unix" / "app"

#: Prazo do subprocesso. Generoso para máquina carregada e MUITO menor que
#: "para sempre": é ele que transforma um estrangulamento em teste vermelho.
_PRAZO_S = 30.0


# ---------------------------------------------------------------------------
# Aparelhagem: GTK de verdade, display descartável, longe da tela dela
# ---------------------------------------------------------------------------

_PRELUDIO = """
import json, sys, time
sys.path.insert(0, {raiz!r})
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.app import gui_dialogs

assert Gtk.init_check(None)[0], "o GTK falhou ao iniciar sob o Xvfb"


def _o_dialogo():
    vivos = [
        w for w in Gtk.Window.list_toplevels()
        if isinstance(w, Gtk.MessageDialog)
    ]
    return vivos[0] if vivos else None


marcas = {{}}
pai = Gtk.Window()
pai.set_title("janela principal de mentira")
pai.show_all()
"""

_EPILOGO = """
marcas["dialogos_restantes"] = sum(
    1 for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.MessageDialog)
)
print("HEFESTO_JSON " + json.dumps(marcas))
"""


def _sob_xvfb(corpo: str, tmp_path: Path) -> dict:
    """Roda ``corpo`` com GTK real num display descartável; devolve as marcas.

    Nunca no processo do ``pytest`` e nunca no display dela: o envelope mostra
    e presenteia um toplevel de verdade.
    """
    if shutil.which("xvfb-run") is None:  # pragma: no cover — máquina sem xvfb
        pytest.skip("sem `xvfb-run` — este teste exige um display descartável")

    script = _PRELUDIO.format(raiz=str(_RAIZ / "src")) + corpo + _EPILOGO
    ambiente = dict(os.environ)
    # CANÁRIO-FS-01: o subprocesso não escreve no home de verdade.
    ambiente["HOME"] = str(tmp_path)
    ambiente["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    ambiente["XDG_DATA_HOME"] = str(tmp_path / "data")
    ambiente["GDK_BACKEND"] = "x11"
    ambiente.pop("WAYLAND_DISPLAY", None)
    try:
        proc = subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=_PRAZO_S,
            check=False,
            env=ambiente,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o diálogo ESTRANGULOU a janela: o processo passou de "
            f"{_PRAZO_S:.0f}s dentro do laço sem devolver resposta — é o "
            "defeito de 06/08/2026 (`nem consigo fazer nada nem fechar`) "
            "voltando. O vigia de `gui_dialogs.executar_dialogo` está no lugar?"
        )
    if proc.returncode != 0:
        pytest.fail(f"o subprocesso GTK falhou (rc={proc.returncode}):\n{proc.stderr}")
    for linha in proc.stdout.splitlines():
        if linha.startswith("HEFESTO_JSON "):
            return dict(json.loads(linha[len("HEFESTO_JSON ") :]))
    pytest.fail(f"o subprocesso não imprimiu as marcas:\n{proc.stdout}\n{proc.stderr}")


# ---------------------------------------------------------------------------
# 1. O caminho feliz: o diálogo NASCE visível, focado e com pai transiente
# ---------------------------------------------------------------------------


def test_o_dialogo_nasce_visivel_focado_e_com_pai_transiente(
    tmp_path: Path,
) -> None:
    """O aviso de rebaixamento chega a ela — e o vigia não atrapalha.

    Três coisas na mesma foto, tirada de DENTRO do laço, no instante em que ela
    veria o diálogo: pai transiente (sem ele o compositor não tem relação de
    empilhamento para respeitar), ``GdkWindow`` visível, e foco de teclado —
    que é o critério de `dialogo_alcancavel`, porque sem foco nem o ``Esc``
    chega. E o quarto: `ultimo_socorro()` continua `None`, ou seja, um diálogo
    que aparece direito nunca é cancelado pelo remédio.
    """
    marcas = _sob_xvfb(
        """
# FOTO-QUE-ESPERA-01 (13/08/2026): a foto era tirada UMA vez, 120 ms depois de
# o diálogo nascer. Sob Xvfb não há gerenciador de janelas, e o foco de teclado
# chega quando chega: a MESMA SHA rodou duas vezes no CI e deu success às 05:00
# e failure às 05:11, com `tem_foco` False. Era corrida do instrumento, não
# defeito do produto — e ela barrou o release inteiro na guarda do ci.yml.
#
# A asserção NÃO afrouxou: o diálogo continua tendo de ficar visível, focado,
# transiente e modal. O que mudou é que a foto espera a condição em vez de
# medir num instante arbitrário — até 3 s, olhando a cada 60 ms. Se o foco não
# vier nesse teto, `tem_foco` sai False e o teste reprova como antes.
_ESPERA_MAX_MS = 3000
_tentativas = {"gastas": 0}


def _olhar():
    d = _o_dialogo()
    if d is None:
        marcas["erro"] = "nenhum Gtk.MessageDialog entre os toplevels"
        return False

    _tentativas["gastas"] += 60
    visivel = bool(d.get_window() and d.get_window().is_visible())
    focado = bool(d.is_active())
    if not (visivel and focado) and _tentativas["gastas"] < _ESPERA_MAX_MS:
        return True  # re-agenda: o compositor ainda não entregou o foco

    marcas["transiente_e_o_pai"] = d.get_transient_for() is pai
    marcas["gdk_visivel"] = visivel
    marcas["tem_foco"] = focado
    marcas["esperou_ms"] = _tentativas["gastas"]
    marcas["alcancavel"] = bool(gui_dialogs.dialogo_alcancavel(d))
    marcas["modal"] = bool(d.get_modal())
    d.response(Gtk.ResponseType.CANCEL)
    return False


GLib.timeout_add(60, _olhar)
marcas["retorno"] = bool(
    gui_dialogs.confirm_downgrade_priority(pai, name="Vitoria", de=78, para=0)
)
marcas["socorro"] = gui_dialogs.ultimo_socorro()
""",
        tmp_path,
    )
    assert marcas.get("erro") is None, marcas["erro"]
    assert marcas["transiente_e_o_pai"] is True
    assert marcas["gdk_visivel"] is True
    assert marcas["tem_foco"] is True
    assert marcas["alcancavel"] is True
    assert marcas["modal"] is True
    assert marcas["retorno"] is False  # respondemos CANCELAR
    assert marcas["socorro"] is None
    assert marcas["dialogos_restantes"] == 0


# ---------------------------------------------------------------------------
# 2. A CONDIÇÃO DELA: o diálogo não consegue aparecer — e a janela volta
# ---------------------------------------------------------------------------


def test_a_janela_volta_para_ela_quando_o_dialogo_nao_pode_aparecer(
    tmp_path: Path,
) -> None:
    """O teste central: nada na tela, e mesmo assim a janela não fica presa.

    A sabotagem é CONTÍNUA (a cada 20 ms o ``GdkWindow`` do diálogo é retirado
    do servidor) porque é assim que um compositor que se recusa a mostrar a
    janela se comporta: não adianta pedir de novo. É o único jeito honesto de
    exercitar a desistência — com sabotagem única o socorro RESSUSCITA o
    diálogo, e é isso que o teste seguinte prova.

    De quebra, as marcas registram as duas MENTIRAS medidas: ``get_mapped()``
    e ``get_visible()`` continuam dizendo "está lá" com a janela retirada do
    servidor. Se alguém trocar o critério de `dialogo_alcancavel` por um
    desses, este teste reprova.
    """
    marcas = _sob_xvfb(
        """
gui_dialogs.PRAZO_ATE_O_SOCORRO_MS = 80
gui_dialogs.PRAZO_ATE_DESISTIR_MS = 80


def _o_compositor_se_recusa():
    d = _o_dialogo()
    if d is None or d.get_window() is None:
        return True
    marcas["mente_get_mapped"] = bool(d.get_mapped())
    marcas["mente_get_visible"] = bool(d.get_visible())
    marcas["verdade_tem_foco"] = bool(d.is_active())
    d.get_window().hide()
    return True


GLib.timeout_add(20, _o_compositor_se_recusa)
comeco = time.monotonic()
marcas["retorno"] = bool(
    gui_dialogs.confirm_downgrade_priority(pai, name="Vitoria", de=78, para=0)
)
marcas["segundos"] = time.monotonic() - comeco
marcas["socorro"] = gui_dialogs.ultimo_socorro()
""",
        tmp_path,
    )
    # Ela recuperou a janela — e nada foi rebaixado (o VETO: o aviso não some,
    # e a resposta segura é a que não muda nada).
    assert marcas["retorno"] is False
    assert marcas["socorro"] == "rebaixar_prioridade"
    assert marcas["segundos"] < 5.0, (
        f"o laço durou {marcas['segundos']:.1f}s — o vigia demorou demais"
    )
    assert marcas["dialogos_restantes"] == 0
    # As duas mentiras, medidas dentro do próprio teste.
    assert marcas["mente_get_mapped"] is True
    assert marcas["mente_get_visible"] is True


# ---------------------------------------------------------------------------
# 3. O socorro é SOCORRO: quando dá para ressuscitar, não se cancela nada
# ---------------------------------------------------------------------------


def test_o_socorro_ressuscita_o_dialogo_em_vez_de_cancelar(tmp_path: Path) -> None:
    """Um sumiço passageiro não pode custar o gesto dela.

    Aqui o diálogo é retirado do servidor UMA vez. O socorro
    (``deiconify``/``show_all``/``present``) o traz de volta, a desistência vê
    um diálogo alcançável e se cala, e ela responde "Baixar a prioridade" —
    que é o que o produto tem de honrar.

    Este é o contrapeso do teste anterior: sem ele, "curar" o defeito
    cancelando todo diálogo passaria nos outros dois.
    """
    marcas = _sob_xvfb(
        """
gui_dialogs.PRAZO_ATE_O_SOCORRO_MS = 80
gui_dialogs.PRAZO_ATE_DESISTIR_MS = 120


def _sumir_uma_vez():
    d = _o_dialogo()
    if d is not None and d.get_window() is not None:
        d.get_window().hide()
        marcas["sumiu"] = True
    return False


def _ela_responde():
    d = _o_dialogo()
    if d is None:
        marcas["erro"] = "o diálogo sumiu antes de ela responder"
        return False
    marcas["voltou_a_ser_alcancavel"] = bool(gui_dialogs.dialogo_alcancavel(d))
    d.response(Gtk.ResponseType.OK)
    return False


GLib.timeout_add(40, _sumir_uma_vez)
GLib.timeout_add(600, _ela_responde)
marcas["retorno"] = bool(
    gui_dialogs.confirm_downgrade_priority(pai, name="Vitoria", de=78, para=0)
)
marcas["socorro"] = gui_dialogs.ultimo_socorro()
""",
        tmp_path,
    )
    assert marcas.get("erro") is None, marcas["erro"]
    assert marcas["sumiu"] is True
    assert marcas.get("socorro") is None, (
        "a casa DESISTIU de um diálogo que dava para ressuscitar — um sumiço "
        "passageiro não pode custar o gesto dela"
    )
    assert marcas.get("voltou_a_ser_alcancavel") is True, (
        "o socorro não trouxe o diálogo de volta (falta o `present`?): "
        f"{marcas}"
    )
    assert marcas["retorno"] is True


# ---------------------------------------------------------------------------
# O PORTÃO: nenhum `.run()` bloqueante novo em app/ fora do envelope
# ---------------------------------------------------------------------------

#: Receptores cujo ``.run()`` não tem nada com diálogo — a lista de quem o
#: portão IGNORA. Deliberadamente curta: qualquer nome novo aqui é uma decisão,
#: não um acidente.
_RECEPTORES_QUE_NAO_SAO_DIALOGO = {"subprocess", "asyncio"}

#: ``arquivo::função`` autorizados a chamar ``.run()`` em ``app/``.
#:
#: São TRÊS, e nenhum é diálogo: os dois ``app.run()`` são o laço principal do
#: GTK, e o ``executar_dialogo`` é o envelope da casa — o único lugar do
#: produto onde um diálogo pode bloquear, porque é o único que vigia.
#: **Esta lista só pode ENCOLHER**: o teste abaixo trava o conteúdo dela.
_AUTORIZADOS_A_BLOQUEAR = {
    "app.py::main",
    "gui_dialogs.py::executar_dialogo",
    "main.py::main",
}


def _chamadas_a_run(caminho: Path, raiz: Path | None = None) -> dict[str, list[int]]:
    """``{"arquivo::função": [linhas]}`` para cada ``x.run()`` de ``caminho``.

    Por AST, e não por texto, pelo mesmo motivo do portão irmão do funil de
    gravação: texto acusaria a docstring que CITA ``dialog.run()`` — e este
    módulo, o ``gui_dialogs`` e o ``daemon_actions`` citam de propósito, porque
    é assim que a casa lembra por que o envelope existe. Portão com falso
    positivo em massa vira portão desligado.
    """
    relativo = caminho.relative_to(raiz or _APP).as_posix()
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: dict[str, list[int]] = {}

    def _andar(no: ast.AST, funcao: str) -> None:
        for filho in ast.iter_child_nodes(no):
            dentro = funcao
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dentro = filho.name
            if (
                isinstance(filho, ast.Call)
                and isinstance(filho.func, ast.Attribute)
                and filho.func.attr == "run"
            ):
                receptor = ast.unparse(filho.func.value).split(".")[0]
                if receptor not in _RECEPTORES_QUE_NAO_SAO_DIALOGO:
                    achados.setdefault(f"{relativo}::{dentro}", []).append(
                        filho.lineno
                    )
            _andar(filho, dentro)

    _andar(arvore, "<módulo>")
    return achados


def test_nenhum_dialogo_bloqueante_fora_do_envelope_da_casa() -> None:
    """Quem escrever o próximo aviso não precisa lembrar de nada.

    Se este teste reprovar, a resposta NÃO é acrescentar o arquivo à lista: é
    chamar ``gui_dialogs.executar_dialogo(dialog, nome="...")``, que mostra o
    diálogo de verdade e devolve a janela a ela se ele não conseguir aparecer.
    """
    ofensores: dict[str, list[int]] = {}
    for caminho in sorted(_APP.rglob("*.py")):
        for chave, linhas in _chamadas_a_run(caminho).items():
            if chave in _AUTORIZADOS_A_BLOQUEAR:
                continue
            ofensores[chave] = linhas

    assert ofensores == {}, (
        "`.run()` bloqueante fora do envelope (DIÁLOGO-QUE-MATA-A-JANELA-01): "
        f"{ofensores} — use `gui_dialogs.executar_dialogo(dialog, nome=...)`. "
        "Um diálogo que nasce invisível com `run()` cru deixa a janela dela "
        "morta, e foi o que aconteceu em 06/08/2026 às 20h22"
    )


def test_a_lista_de_autorizados_a_bloquear_nao_cresce_em_silencio() -> None:
    """Sem esta trava o portão se dissolveria por acréscimo.

    Bastaria escrever o nome da função nova na lista para voltar a bloquear a
    thread GTK com um diálogo cru.
    """
    assert sorted(_AUTORIZADOS_A_BLOQUEAR) == [
        "app.py::main",
        "gui_dialogs.py::executar_dialogo",
        "main.py::main",
    ]


def test_o_portao_pegaria_um_dialogo_novo_com_run_cru(tmp_path: Path) -> None:
    """O portão MORDE — provado contra um arquivo forjado, não por fé.

    Sem esta prova, um portão quebrado (um ``ast.walk`` que perdesse o nome da
    função, por exemplo) passaria despercebido justamente por estar sempre
    verde.
    """
    forjado = tmp_path / "aviso_novo.py"
    forjado.write_text(
        "import subprocess\n"
        "\n"
        "def confirmar_algo(dialog):\n"
        "    subprocess.run(['true'])\n"
        "    return dialog.run()\n",
        encoding="utf-8",
    )
    achados = _chamadas_a_run(forjado, raiz=tmp_path)

    # O `subprocess.run` da linha 4 é ignorado; o `dialog.run()` da 5 não.
    assert achados == {"aviso_novo.py::confirmar_algo": [5]}
    assert "aviso_novo.py::confirmar_algo" not in _AUTORIZADOS_A_BLOQUEAR


# ---------------------------------------------------------------------------
# A cobertura da CLASSE: os dez diálogos, não só o que a derrubou
# ---------------------------------------------------------------------------


def test_todo_dialogo_publico_da_casa_passa_pelo_envelope() -> None:
    """Não curar um caso e deixar nove irmãos de pé.

    Espelho por FONTE das funções públicas de `gui_dialogs` (o portão por AST
    acima cobre o app inteiro; esta é a granularidade por função, no idioma que
    `test_gui_dialogs_theme.py` já usa para o tema).
    """
    from hefesto_dualsense4unix.app import gui_dialogs
    from hefesto_dualsense4unix.app.actions import footer_actions, profiles_actions

    alvos = [
        gui_dialogs.prompt_profile_name,
        gui_dialogs.prompt_overwrite_existing,
        gui_dialogs.confirm_downgrade_match_to_any,
        gui_dialogs.confirm_downgrade_priority,
        gui_dialogs.confirm_discard_pending_edits,
        gui_dialogs.prompt_import_conflict,
        gui_dialogs.confirm_restore_default,
        gui_dialogs.confirm_delete_profile,
        gui_dialogs.show_external_controller,
        profiles_actions.dialogo_renomear_ou_copiar,
        footer_actions.FooterActionsMixin.on_import_profile,
    ]
    assert len(alvos) == 11, "a leva mediu DEZ diálogos + o seletor de arquivo"
    faltando = [
        fn.__qualname__
        for fn in alvos
        if "executar_dialogo(" not in inspect.getsource(fn)
    ]
    assert faltando == [], (
        f"diálogos que não passam pelo envelope da casa: {faltando}"
    )


# ---------------------------------------------------------------------------
# DIÁLOGO-QUE-MATA-A-JANELA-01, segunda metade (06/08/2026)
#
# A verificação adversarial refutou a primeira cura por um caminho que o portão
# acima não enxerga: um diálogo `modal=True` mostrado com `show()`/`show_all()`
# cru, respondendo por `connect("response")`. Ele NÃO chama `run()`, então
# passava — e MEDIDO: o `show()` de um modal já instala o grab do GTK, e com a
# janela fora do servidor a principal perde clique, tecla e o "X" do gerenciador
# (0/0/0 contra 2/1/1 no controle). Nem o vigia nem o `SIGUSR1` o alcançavam.
#
# Era o "Desligar o Hefesto?" da aba Início — um botão que ela usa.
#
# Não bloquear NÃO salva: quem prende é a modalidade, não o laço. Por isso o
# portão passou a olhar o PAR (modal + mostrar), e não só o `run()`.
# ---------------------------------------------------------------------------

#: Quem pode mostrar um diálogo modal por conta própria — só o envelope.
_AUTORIZADOS_A_MOSTRAR_MODAL = frozenset({
    "gui_dialogs.py::_mostrar_e_vigiar",
})


def _dialogos_modais_mostrados_crus(
    caminho: Path, raiz: Path | None = None
) -> dict[str, list[int]]:
    """Acha `Gtk.MessageDialog(... modal=True ...)` cujo `show()` é cru.

    Heurística deliberada e declarada: dentro de uma mesma função, se há uma
    construção de diálogo com `modal=True` E uma chamada `.show()`/`.show_all()`
    que não seja do envelope, é ofensa. Não tenta provar que o objeto é o mesmo
    — provar isso exigiria análise de fluxo, e o falso positivo aqui custa uma
    linha de código, enquanto o falso negativo custou a sessão dela.
    """
    relativo = caminho.relative_to(raiz or _APP).as_posix()
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: dict[str, list[int]] = {}

    def _tem_modal_true(no: ast.Call) -> bool:
        return any(
            kw.arg == "modal"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in no.keywords
        )

    def _delega_ao_envelope(no: ast.AST) -> bool:
        """A função entrega o diálogo ao envelope? Então o `show_all` é preparo.

        MEDIDO ao escrever este portão: `prompt_profile_name` e
        `show_external_controller` fazem `content.show_all()` / `dialog.show_all()`
        e na linha SEGUINTE chamam `executar_dialogo`. São preparação de widget,
        não a mostra final — acusá-las seria o falso positivo em massa que
        transforma portão em portão desligado.
        """
        for f in ast.walk(no):
            if isinstance(f, ast.Call):
                alvo = f.func.attr if isinstance(f.func, ast.Attribute) else (
                    f.func.id if isinstance(f.func, ast.Name) else ""
                )
                if alvo in {"executar_dialogo", "mostrar_dialogo_assincrono"}:
                    return True
        return False

    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        chave = f"{relativo}::{no.name}"
        if chave in _AUTORIZADOS_A_MOSTRAR_MODAL:
            continue
        modais = [f for f in ast.walk(no) if isinstance(f, ast.Call) and _tem_modal_true(f)]
        if not modais:
            continue
        if _delega_ao_envelope(no):
            continue
        mostras = [
            f.lineno
            for f in ast.walk(no)
            if isinstance(f, ast.Call)
            and isinstance(f.func, ast.Attribute)
            and f.func.attr in {"show", "show_all"}
            and ast.unparse(f.func.value).split(".")[0]
            not in _RECEPTORES_QUE_NAO_SAO_DIALOGO
        ]
        if mostras:
            achados[chave] = sorted(mostras)
    return achados


def test_nenhum_dialogo_modal_e_mostrado_fora_do_envelope() -> None:
    """O par que a primeira cura não viu: modal + show, sem `run()`.

    Se reprovar, a resposta é `gui_dialogs.mostrar_dialogo_assincrono(dialog,
    nome="...")` no lugar do `show()` — ele mostra de verdade, arma o mesmo
    vigia e registra o diálogo para o `SIGUSR1` alcançar.
    """
    ofensores: dict[str, list[int]] = {}
    for caminho in sorted(_APP.rglob("*.py")):
        ofensores.update(_dialogos_modais_mostrados_crus(caminho))

    assert ofensores == {}, (
        "diálogo modal mostrado fora do envelope: "
        f"{ofensores} — use `gui_dialogs.mostrar_dialogo_assincrono(...)`. "
        "Não bloquear não salva: quem prende a janela dela é a modalidade"
    )


def test_o_portao_pegaria_um_modal_mostrado_cru(tmp_path: Path) -> None:
    """A mordida do portão novo, com arquivo forjado.

    Foi assim que a verificação adversarial provou que o portão ANTIGO era cego:
    com o padrão do `home_actions` os quatro testes ficavam verdes.
    """
    forjado = tmp_path / "acoes_novas.py"
    forjado.write_text(
        "from gi.repository import Gtk\n"
        "def pergunta_nova(janela):\n"
        "    d = Gtk.MessageDialog(transient_for=janela, modal=True, text='oi')\n"
        "    d.connect('response', lambda *a: None)\n"
        "    d.show()\n",
        encoding="utf-8",
    )
    achados = _dialogos_modais_mostrados_crus(forjado, raiz=tmp_path)
    assert achados, "o portão novo não pegou um modal mostrado cru"
    assert "acoes_novas.py::pergunta_nova" in achados
