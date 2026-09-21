"""REPOR-O-LANCADOR-01 — o «Reiniciar o serviço» fecha e reabre o lançador.

**Decisão dela, 21/09/2026.** A pergunta foi dela — *"seria importante ele
fechar e reabrir o launcher, seja steam, epic, heroic ou qualquer outro"* —, e
posta entre três formas (automático · oferecido num segundo clique · botão
separado), ela escolheu a primeira: *"Faz automático mesmo"*.
<!-- noqa-acento: citação literal dela -->

**A RÉGUA QUE MAIS IMPORTA É A DO PGREP**, e ela nasceu de um defeito vivo
medido na mesma hora: a primeira versão de `pids_de` perguntava
`pgrep -f com.heroicgameslauncher.hgl`, e a resposta foi **o shell que estava
perguntando** — o id da aplicação estava na cmdline dele. Numa máquina com os
dois lançadores FECHADOS o módulo respondeu "Heroic e Lutris abertos", e um
`fechar()` ali teria mandado `SIGTERM` no terminal de quem chamou.

Nenhum teste deste arquivo toca processo de verdade: o que se mede é a
DECISÃO — quem é perguntado, em que ordem, e o que se recusa a fazer.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl


class _Saida:
    def __init__(self, texto: str = "", rc: int = 0) -> None:
        self.stdout = texto
        self.returncode = rc


@pytest.fixture(autouse=True)
def _sem_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Por padrão não há jogo aberto — quem mede o contrário diz."""
    monkeypatch.setattr(rl, "jogo_aberto", lambda: False)


# ---------------------------------------------------------------------------
# 1 — NENHUMA PERGUNTA LÊ LINHA DE COMANDO
# ---------------------------------------------------------------------------
def test_ninguem_pergunta_por_pgrep_dash_f(monkeypatch: pytest.MonkeyPatch) -> None:
    """O DEFEITO VIVO DE 21/09/2026, preso por régua.

    `pgrep -f <id>` casa a cmdline de quem pergunta — e este módulo manda
    `SIGTERM` no que ele achar. Um `-f` aqui é um tiro no próprio pé, e a régua
    não deixa voltar.

    MORDE: troque o `flatpak ps` de `_pids_de_flatpak` por um
    `pgrep -f lancador.flatpak` e esta régua reprova.
    """
    vistos: list[list[str]] = []

    def _espiao(args: list[str], **_k: Any) -> _Saida:
        vistos.append(args)
        return _Saida(rc=1)

    monkeypatch.setattr(rl, "_rodar", _espiao)
    monkeypatch.setattr(rl.shutil, "which", lambda _n: "/usr/bin/flatpak")

    for lancador in rl.LANCADORES:
        rl.pids_de(lancador)

    for args in vistos:
        assert not (args[:1] == ["pgrep"] and "-f" in args), (
            f"{args!r} pergunta por LINHA DE COMANDO — ela casa quem pergunta")


def test_o_flatpak_e_lido_por_instancia_e_nao_por_texto(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`flatpak ps` lista instâncias; a coluna tem de casar o id INTEIRO."""
    saida = ("com.heroicgameslauncher.hgl\t4242\n"
             "net.lutris.Lutris\t99\n"
             "io.github.outro.Coisa\t7\n")
    monkeypatch.setattr(rl, "_rodar", lambda *_a, **_k: _Saida(saida))
    monkeypatch.setattr(rl.shutil, "which", lambda _n: "/usr/bin/flatpak")

    assert rl._pids_de_flatpak("com.heroicgameslauncher.hgl") == [4242]
    assert rl._pids_de_flatpak("net.lutris.Lutris") == [99]
    assert rl._pids_de_flatpak("com.heroicgameslauncher") == []


def test_o_proprio_processo_nunca_entra_na_lista(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O cinto de segurança antes do `os.kill`."""
    import os

    monkeypatch.setattr(rl, "_rodar", lambda *_a, **_k: _Saida(f"{os.getpid()}\n"))
    monkeypatch.setattr(rl.shutil, "which", lambda _n: None)

    assert rl.pids_de(rl.LANCADORES[0]) == []


def test_a_leitura_prende_o_idioma(monkeypatch: pytest.MonkeyPatch) -> None:
    """`LC_ALL=C` em toda leitura — o `flatpak` desta máquina fala português."""
    ambientes: list[dict[str, str]] = []

    def _espiao(*_a: Any, **kwargs: Any) -> _Saida:
        ambientes.append(kwargs.get("env") or {})
        return _Saida(rc=1)

    monkeypatch.setattr(subprocess, "run", _espiao)
    rl._rodar(["pgrep", "-x", "lutris"])

    assert ambientes and ambientes[0].get("LC_ALL") == "C"


# ---------------------------------------------------------------------------
# 2 — O JOGO ABERTO VEM ANTES DE QUALQUER DECISÃO
# ---------------------------------------------------------------------------
def test_com_jogo_aberto_nada_e_fechado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fechar o lançador fecharia o jogo junto.

    Não é ressalva desta leva: é o contrato que
    `steam_launch_options._fechar_a_steam_uma_vez` aplica desde 18/09/2026.

    MORDE: tire o `if jogo_aberto()` de `repor` e a régua reprova, porque
    `fechar` passa a ser chamado.
    """
    monkeypatch.setattr(rl, "jogo_aberto", lambda: True)
    monkeypatch.setattr(rl, "abertos", lambda: list(rl.LANCADORES))
    monkeypatch.setattr(rl, "fechar", lambda _x: pytest.fail(
        "fechou o lançador com jogo aberto — o jogo morreria junto"))

    recibo = rl.repor()

    assert recibo.barrado_por_jogo is True
    assert recibo.repostos == ()


def test_a_pergunta_do_jogo_invalida_a_foto_antes(
        monkeypatch: pytest.MonkeyPatch, request: Any) -> None:
    """Decidir um ato destrutivo sobre uma foto de 5 s atrás é decidir errado."""
    request.getfixturevalue("monkeypatch").undo()
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    passos: list[str] = []
    monkeypatch.setattr(slo, "invalidar_varredura_de_proc",
                        lambda: passos.append("invalidou"))
    monkeypatch.setattr(slo, "steam_game_running",
                        lambda: passos.append("perguntou") or False)

    rl.jogo_aberto()

    assert passos == ["invalidou", "perguntou"]


# ---------------------------------------------------------------------------
# 3 — O ATO INTEIRO, E A ORDEM
# ---------------------------------------------------------------------------
def test_fecha_todos_antes_de_reabrir_qualquer_um(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Fechar-e-reabrir um a um faria o segundo subir disputando o físico.

    MORDE: junte o fechar e o abrir num laço só e a ordem medida aqui muda.
    """
    ordem: list[str] = []
    dois = [rl.LANCADORES[1], rl.LANCADORES[2]]
    monkeypatch.setattr(rl, "abertos", lambda: dois)
    monkeypatch.setattr(rl, "fechar",
                        lambda x: ordem.append(f"fechou:{x.chave}") or True)
    monkeypatch.setattr(rl, "abrir",
                        lambda x: ordem.append(f"abriu:{x.chave}") or True)

    rl.repor()

    assert ordem == ["fechou:heroic", "fechou:lutris",
                     "abriu:heroic", "abriu:lutris"]


def test_quem_nao_fecha_nao_e_reaberto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Abrir um lançador que continua aberto criaria a segunda instância."""
    monkeypatch.setattr(rl, "abertos", lambda: list(rl.LANCADORES))
    monkeypatch.setattr(rl, "fechar", lambda x: x.chave != "lutris")
    abertos_de_novo: list[str] = []
    monkeypatch.setattr(rl, "abrir",
                        lambda x: abertos_de_novo.append(x.chave) or True)

    recibo = rl.repor()

    assert "lutris" not in abertos_de_novo
    assert recibo.nao_fecharam == ("Lutris",)


def test_sem_lancador_aberto_nao_se_faz_nada(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "abertos", list)
    monkeypatch.setattr(rl, "fechar", lambda _x: pytest.fail("não havia o que fechar"))

    recibo = rl.repor()

    assert recibo == rl.Recibo()
    assert "Nenhum lançador estava aberto" in rl.frase_do_recibo(recibo)


# ---------------------------------------------------------------------------
# 4 — A STEAM TEM DONO, E ELE É CHAMADO
# ---------------------------------------------------------------------------
def test_a_steam_fecha_pelo_dono_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """`stop_steam` salva a nuvem e fecha o runtime; TERM seria outro dono."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    chamou: list[str] = []
    monkeypatch.setattr(slo, "stop_steam", lambda: chamou.append("stop") or True)
    monkeypatch.setattr(rl.os, "kill", lambda *_a: pytest.fail(
        "mandou sinal na Steam em vez de chamar o dono"))

    assert rl.fechar(rl.LANCADORES[0]) is True
    assert chamou == ["stop"]


def test_a_steam_abre_pelo_dono_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """`open_or_focus_steam` ainda FOCA a janela quando ela já está de pé."""
    from hefesto_dualsense4unix.integrations import steam_launcher

    chamou: list[str] = []
    monkeypatch.setattr(steam_launcher, "open_or_focus_steam",
                        lambda *_a, **_k: chamou.append("abriu") or True)

    assert rl.abrir(rl.LANCADORES[0]) is True
    assert chamou == ["abriu"]


def test_o_lancador_abre_com_ambiente_limpo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Herdar o interpretador de quem chamou contamina TODO jogo dali em diante.

    **O QUE O DONO PROMETE É O AMBIENTE DE INTERPRETADOR**, e só ele:
    `ambiente_do_jogo.VARIAVEIS_DO_INTERPRETADOR`. É o que quebra jogo — o
    `/usr/bin/env python3` do `proton` acha o da venv. Um marcador de sessão
    qualquer no ambiente não quebra nada, e cobrá-lo aqui seria régua medindo
    outra coisa que não o produto.

    A LISTA NÃO SE DIGITA: ela é LIDA do dono, senão esta régua envelhece no
    dia em que ele aprender uma variável nova.

    MORDE: tire o `env=ambiente_limpo(...)` do `Popen` e a régua reprova.
    """
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import (
        VARIAVEIS_DO_INTERPRETADOR,
    )

    for nome in VARIAVEIS_DO_INTERPRETADOR:
        monkeypatch.setenv(nome, "/uma/coisa")
    vistos: list[dict[str, str]] = []

    class _Popen:
        def __init__(self, _cmd: list[str], **kwargs: Any) -> None:
            vistos.append(kwargs.get("env") or {})

    monkeypatch.setattr(rl.subprocess, "Popen", _Popen)
    monkeypatch.setattr(rl.shutil, "which", lambda _n: "/usr/bin/flatpak")

    assert rl.abrir(rl.LANCADORES[1]) is True
    assert vistos, "o lançador não foi aberto"
    for nome in VARIAVEIS_DO_INTERPRETADOR:
        assert nome not in vistos[0], (
            f"{nome} atravessou para o lançador — e daí para todo jogo dele")


# ---------------------------------------------------------------------------
# 5 — O REINICIAR CHAMA A REPOSIÇÃO, E A FALHA DELA NÃO DESFAZ O REINÍCIO
# ---------------------------------------------------------------------------
def test_o_reiniciar_da_aba_repoe_depois_do_restart(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A ORDEM É A ENTREGA: o lançador nasce com o daemon já de pé.

    MORDE: chame `_repor_o_lancador()` antes do `_systemctl("restart")` e a
    régua reprova — o lançador pegaria o físico de novo.
    """
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    passos: list[str] = []
    monkeypatch.setattr(a09_sistema, "_trava", lambda *_a: "")
    monkeypatch.setattr(a09_sistema, "_systemctl",
                        lambda v: passos.append(f"systemctl:{v}"))
    monkeypatch.setattr(rl, "repor", lambda: passos.append("repôs") or rl.Recibo())

    a09_sistema.reiniciar(None, {}, None)

    assert passos == ["systemctl:restart", "repôs"]


def test_a_reposicao_que_falha_nao_derruba_o_reiniciar(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O `restart` já deu `rc=0` — levantar aqui mentiria sobre ele."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    monkeypatch.setattr(a09_sistema, "_trava", lambda *_a: "")
    monkeypatch.setattr(a09_sistema, "_systemctl", lambda _v: None)

    def _explode() -> rl.Recibo:
        raise RuntimeError("o flatpak sumiu")

    monkeypatch.setattr(rl, "repor", _explode)

    a09_sistema.reiniciar(None, {}, None)  # não levanta


def test_a_trava_continua_vindo_antes_de_tudo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o serviço desligado não há o que reiniciar — nem o que repor."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    monkeypatch.setattr(a09_sistema, "_trava",
                        lambda *_a: "O serviço está desligado.")
    monkeypatch.setattr(a09_sistema, "_systemctl",
                        lambda _v: pytest.fail("reiniciou com a trava de pé"))
    monkeypatch.setattr(rl, "repor",
                        lambda: pytest.fail("repôs com a trava de pé"))

    with pytest.raises(RuntimeError):
        a09_sistema.reiniciar(None, {}, None)


def test_o_reiniciar_do_tray_repoe_tambem(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Mesmo botão, mesmo ato — venha da aba ou da bandeja."""
    from hefesto_dualsense4unix.cli import cmd_tray

    class _Janela:
        def _invoke_systemctl(self, *_a: Any, **_k: Any) -> Any:
            return _Saida(rc=0)

    import hefesto_dualsense4unix.app.actions.daemon_actions as da

    monkeypatch.setattr(da, "DaemonActionsMixin", _Janela)
    repos: list[str] = []
    monkeypatch.setattr(rl, "repor", lambda: repos.append("repôs") or rl.Recibo())

    assert cmd_tray._servico("restart") is True
    assert repos == ["repôs"]


def test_parar_o_servico_nao_mexe_no_lancador(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A decisão dela é sobre o REINICIAR. Parar é outro ato."""
    from hefesto_dualsense4unix.cli import cmd_tray

    class _Janela:
        def _invoke_systemctl(self, *_a: Any, **_k: Any) -> Any:
            return _Saida(rc=0)

    import hefesto_dualsense4unix.app.actions.daemon_actions as da

    monkeypatch.setattr(da, "DaemonActionsMixin", _Janela)
    monkeypatch.setattr(rl, "repor", lambda: pytest.fail(
        "o «Parar o serviço» mexeu no lançador"))

    assert cmd_tray._servico("stop") is True


# ---------------------------------------------------------------------------
# 6 — A FRASE TEM UM DONO SÓ
# ---------------------------------------------------------------------------
def test_a_frase_diz_o_que_aconteceu() -> None:
    frase = rl.frase_do_recibo(rl.Recibo(
        estavam_abertos=("Steam", "Heroic"),
        repostos=("Steam",),
        nao_fecharam=("Heroic",)))
    assert "Steam" in frase
    assert "Heroic" in frase
    assert "Não consegui fechar" in frase
