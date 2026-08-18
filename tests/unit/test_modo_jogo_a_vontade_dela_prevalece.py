"""MODO-JOGO-VONTADE-DELA-01 (09/08/2026) — a junta entre a janela e o daemon.

Decisão dela, 09/08: **a vontade na GUI prevalece sempre**. Ligar o "Modo jogo"
(suspender mouse e teclado) e salvar num perfil *"vale sempre"* (catch-all)
passa a GUARDAR — antes a janela recusava, e cinco dos perfis dela são
catch-all, então para ela isso era literalmente *"liguei e não ficou salvo"*.

A recusa não era capricho: ela guardava a metade do defeito que o daemon ainda
não tinha curado. Este arquivo trava a OUTRA metade — a que permite a recusa
cair — e é ela que impede a decisão de hoje de virar um alçapão amanhã:

**um perfil catch-all com ``suppress_desktop_emulation: true`` não suspende
mouse e teclado na ativação.** O gate mora em
``lifecycle.apply_profile_suppression`` (o ramo ``if desired:``), nasceu em
05/08 com a PERFIL-REESCRITO-NA-PARTIDA-01 e, a partir de hoje, é a CONDIÇÃO da
entrega da janela: sem ele, o ``suppress: true`` que ela agora consegue salvar
liga a supressão em toda ativação — inclusive no restauro do último perfil no
boot — e o caminho de volta continua fechado pelo R-02. Seria trocar a perda de
uma configuração dela por um desktop sem ponteiro.

Por que o perfil aqui nasce de um ``DraftConfig``, e não escrito à mão: o
``DraftConfig`` É a estrutura que a janela salva ("Salvar Perfil" chama
``to_profile``). Construir o perfil por ele prova a junta REAL — o que a janela
grava contra o que o daemon faz com aquilo — sem precisar de PyGObject, então
este portão roda na CI headless, que é onde os testes das abas SKIPAM
(PORTÃO-VIVO-01). O lado da janela (ela LIGA e o gesto é guardado) mora em
``test_perfil_salva_tudo_escritores_das_abas.py``, que exige o GTK real.

Mordida verificada em 09/08, arrancando o gate do ramo ``if desired:`` de
``apply_profile_suppression`` e devolvendo — ver o relatório da entrega.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.lifecycle import (
    APLICADO,
    IGNORADO_CATCH_ALL,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis em ``tmp_path`` (CANÁRIO-FS-01).

    Obrigatório em todo teste que salve perfil: ``xdg_paths`` resolve o
    ``config_dir`` num ``PlatformDirs`` de módulo, avaliado no import, e o
    isolamento XDG do ``conftest`` não o alcança.
    """
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return alvo


@pytest.fixture(autouse=True)
def _sem_notificacao(monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-TEST-DBUS-NOTIFY-NONHERMETIC-01: ``set_emulation_suppressed``
    notifica SEMPRE. Sem este stub cada teste abre uma conexão real com o D-Bus
    de sessão e joga um popup na tela dela no meio da suíte."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_emulation_suppressed",
        lambda _estado: None,
    )


def _perfil_de_origem(nome: str, *, catch_all: bool) -> Profile:
    """O perfil que a janela ABRIU (ainda sem o modo jogo)."""
    return Profile(
        name=nome,
        match=MatchAny() if catch_all else MatchCriteria(window_class=[f"{nome}_cls"]),
        priority=0 if catch_all else 10,
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def o_que_a_janela_salva(nome: str, *, catch_all: bool) -> Profile:
    """O arquivo que nasce do gesto dela: abrir o perfil, ligar o modo jogo, salvar.

    É o caminho de dados REAL da janela — ``DraftConfig.from_profile`` (abrir),
    ``with_suppress(True)`` (o único escritor do modo jogo, ver
    ``emulation_actions.rascunho_com_modo_jogo``) e ``to_profile`` (o "Salvar
    Perfil"). O que muda em 09/08 é que o catch-all deixou de ser recusado ANTES
    do ``with_suppress``; daqui para baixo o arquivo é este.
    """
    draft = DraftConfig.from_profile(_perfil_de_origem(nome, catch_all=catch_all))
    return draft.with_suppress(True).to_profile(nome)


def _daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


def _bancada(perfis: list[Profile], daemon: Daemon) -> tuple[ProfileManager, StateStore]:
    """``ProfileManager`` real com o applier REAL do daemon injetado.

    Nada de dublê no lugar do applier: o alçapão vive justamente na conversa
    entre o manager (que manda SEMPRE o valor do campo, inclusive o default) e o
    applier (que decide se obedece).
    """
    for perfil in perfis:
        save_profile(perfil)
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(
        controller=fc,
        store=store,
        suppression_applier=daemon.apply_profile_suppression,
    )
    return manager, store


# ---------------------------------------------------------------------------
# O que a janela grava a partir de hoje
# ---------------------------------------------------------------------------


def test_o_gesto_dela_num_catch_all_chega_ao_arquivo() -> None:
    """O arquivo que este portão vai ativar existe — e é catch-all mesmo.

    HONESTIDADE sobre a mordida: este teste NÃO morde o lado da janela. Ele
    passa antes e depois da entrega, porque quem recusava era
    ``emulation_actions.rascunho_com_modo_jogo`` (que importa PyGObject e não
    entra aqui), nunca o ``DraftConfig``. O que ele tranca é o *pressuposto*
    dos testes abaixo: se algum dia salvar deixar de produzir um catch-all com
    ``suppress: true``, eles passariam a provar o vazio.

    A mordida do lado da janela é
    ``test_perfil_salva_tudo_escritores_das_abas.py::
    TestOModoJogoEntraNoPerfilQuePodeReceber::
    test_catch_all_agora_guarda_o_modo_jogo``.
    """
    salvo = o_que_a_janela_salva("vitoria", catch_all=True)

    assert salvo.e_catch_all is True
    assert salvo.suppress_desktop_emulation is True


# ---------------------------------------------------------------------------
# E por que isso não vira um desktop sem ponteiro
# ---------------------------------------------------------------------------


def test_o_catch_all_que_ela_salvou_nao_suspende_na_ativacao(
    perfis_isolados: Path,
) -> None:
    """MORDIDA: o alçapão continua fechado no caminho de ativação INTEIRO.

    Sem o gate do ramo ``if desired:``, esta ativação liga a supressão de
    mouse/teclado sem ela pedir — e nenhum outro catch-all consegue liberar
    (R-02, o ramo de baixo).
    """
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("vitoria", catch_all=True)], daemon
    )

    relatorio: dict[str, str] = {}
    manager.activate("vitoria", origin="autoswitch", relatorio=relatorio)

    assert relatorio["suppression"] == IGNORADO_CATCH_ALL
    assert daemon._emulation_suppressed is False
    assert daemon._suppress_from_profile is False


def test_o_restauro_do_boot_nao_acorda_com_mouse_e_teclado_suspensos(
    perfis_isolados: Path,
) -> None:
    """MORDIDA, no caminho que mais dói: o restauro do último perfil no boot.

    O restauro monta o ``ProfileManager`` com ``mouse_applier=None`` e
    ``mode_applier=None``, mas o ``suppression_applier`` VAI injetado
    (``daemon/connection.py``) — então é por aqui que um ``suppress: true`` de
    catch-all chegaria à máquina dela antes de qualquer clique, com o Hefesto
    apenas ligando. Ativação com ``origin="system"``, que é a do restauro.
    """
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("vitoria", catch_all=True)], daemon
    )

    manager.activate("vitoria", origin="system")

    assert daemon._emulation_suppressed is False


def test_o_perfil_com_regra_continua_ligando_o_modo_jogo(
    perfis_isolados: Path,
) -> None:
    """GUARDA: o gate é sobre AUSÊNCIA de regra, não sobre o modo jogo.

    Se este teste cair junto com os de cima, a "cura" virou um interruptor
    quebrado — o perfil do jogo dela também deixaria de suspender mouse e
    teclado, que é o que o modo jogo existe para fazer.
    """
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("sackboy", catch_all=False)], daemon
    )

    relatorio: dict[str, str] = {}
    manager.activate("sackboy", origin="autoswitch", relatorio=relatorio)

    assert relatorio["suppression"] == APLICADO
    assert daemon._emulation_suppressed is True
    assert daemon._suppress_from_profile is True


def test_ela_continua_podendo_sair_do_modo_jogo_pela_janela(
    perfis_isolados: Path,
) -> None:
    """GUARDA: o botão "Sair do modo jogo" é a saída, e ele não passa por perfil.

    A supressão que o perfil COM REGRA ligou sai por gesto manual
    (``daemon.emulation.suppress`` → ``set_emulation_suppressed(origin="manual")``),
    que é o que a janela chama. Sem esta saída, o gate de cima só teria mudado o
    lugar do alçapão.
    """
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("sackboy", catch_all=False)], daemon
    )
    manager.activate("sackboy", origin="autoswitch")
    assert daemon._emulation_suppressed is True

    daemon.set_emulation_suppressed(False)

    assert daemon._emulation_suppressed is False
    assert daemon._suppress_from_profile is False
