#!/usr/bin/env python3
"""OS GESTOS DO CONTROLE FAZEM O QUE A TELA DIZ — OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01.

A pergunta dela (29/09): *«Essa aba tá integrada e realmente funciona?»*. Medido
no `dev` de 01/10: os seis gestos disparavam, cada um com o ato cravado em
`start_hotkey_manager`, e a lista ao lado de cada um era desenho sem dono — o
`maquina.json` recusava o campo, o pacote da 06 declarava `acao-do-gesto` em
`SEM_GESTO`, e o PS sozinho abria a Steam com o jogo na frente (os 17 toques da
noite de 01/10, a §14). <!-- noqa-acento: citação literal dela -->

Tudo aqui roda num lar de mentira (o `HOME` e os `XDG_*` da suíte), com
endereços na faixa sintética da casa, e sem gerenciador nem processo de verdade:
o `systemd-run`, o `Popen`, a Steam e o `notify` são de mentira.

As réguas, na numeração da §6 da sprint (e as da §14 no fim):

1. a lista é o vocabulário, e todo token tem atendente;
2. o de fábrica pergunta ao dono (o gerente de atalhos e o ato de antes);
3. escolher na tela muda o controle — pelo `machine.declare` de verdade;
4. vale para os quatro controles, no cabo e no rádio;
5. o script roda com as guardas, uma vez só;
6. o perfil não carrega script;
7. a bandeja e o controle chamam o mesmo ato;
8. a tela pinta o que vale, e sobrevive a reabrir;
§14. o PS sozinho na matriz inteira, e o «— Nada —» nos seis.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import re
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.core import acoes_do_gesto as ag
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import (
    desktop_notifications,
    fora_do_servico,
    hotkey_daemon,
    steam_launcher,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager
from hefesto_dualsense4unix.profiles import autoswitch
from hefesto_dualsense4unix.utils import maquina as mq

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

CONTROLES = [
    ("aa:bb:cc:00:00:01", "usb", 1),
    ("aa:bb:cc:00:00:02", "bt", 2),
    ("aa:bb:cc:00:00:03", "usb", 3),
    ("aa:bb:cc:00:00:04", "bt", 4),
]


class _Controle:
    """O `describe_controllers` do backend, com os quatro da faixa sintética."""

    def __init__(self, controles: list[tuple[str, str, int]] = CONTROLES) -> None:
        self._lista = [
            {"connected": True, "transport": via, "is_primary": i == 0,
             "uniq": mac.replace(":", ""), "player_slot": n}
            for i, (mac, via, n) in enumerate(controles)
        ]

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [dict(c) for c in self._lista]


def _daemon(gestos: dict[str, Any] | None = None, *, autoridade: str = "daemon",
            acao_do_ps: str = "steam") -> Any:
    """Um daemon com o que os gestos tocam, e a tabela da máquina em memória."""
    chamados: list[tuple[str, tuple[Any, ...]]] = []
    d = SimpleNamespace(
        config=SimpleNamespace(ps_button_action=acao_do_ps, ps_button_command="",
                               ps_long_press_ms=0),
        _emulation_suppressed=False, store=None, controller=_Controle(),
        _keyboard_device=None, display_authority=autoridade,
        _maquina=mq.MaquinaConfig.model_validate({"gestos": gestos or {}}),
        _hotkey_manager=None,
        chamados=chamados,
    )
    d.set_emulation_suppressed = lambda *a: chamados.append(("suspender", a))
    return d


@pytest.fixture
def atendentes(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Os atendentes de antes trocados por anotadores — o que muda é QUEM se chama."""
    feitos: dict[str, list[Any]] = {"chamou": []}

    def _corrotina(nome: str) -> Any:
        async def _feita() -> None:
            feitos["chamou"].append((nome, hotkey_daemon.quem_faz_o_gesto()))
        return _feita

    monkeypatch.setattr(hotkey, "build_profile_cycle_callback",
                        lambda _d, sentido: _corrotina("perfil+" if sentido > 0 else "perfil-"))
    monkeypatch.setattr(hotkey, "build_next_bridge_callback", lambda _d: _corrotina("modo"))
    monkeypatch.setattr(hotkey, "build_next_mask_callback", lambda _d: _corrotina("mascara"))
    monkeypatch.setattr(steam_launcher, "open_or_focus_steam",
                        lambda *a, **k: feitos["chamou"].append(("steam", None)) or True)
    monkeypatch.setattr(autoswitch, "jogo_do_wrapper_vivo", lambda **_k: None)
    monkeypatch.setattr(fora_do_servico, "abrir",
                        lambda argv, **k: feitos["chamou"].append(("abrir", list(argv)))
                        or fora_do_servico.Abertura(caminho="unidade", motivo="régua"))
    return feitos


def _rodar(resultado: Any) -> None:
    if asyncio.iscoroutine(resultado):
        asyncio.run(resultado)


def _apertar(mgr: HotkeyManager, botoes: tuple[str, ...], *, de: str | None = None,
             t0: float = 0.0) -> None:
    """Segura o combo além do buffer e solta — um gesto inteiro, de um controle."""

    async def _cena() -> None:
        mgr.observe(list(botoes), now=t0, de=de)
        mgr.observe(list(botoes), now=t0 + 0.2, de=de)
        mgr.observe([], now=t0 + 0.3, de=de)
        atual = asyncio.current_task()
        pendentes = [t for t in asyncio.all_tasks() if t is not atual]
        if pendentes:
            await asyncio.gather(*pendentes)

    asyncio.run(_cena())


def _listas_da_bancada() -> dict[str, list[str]]:
    import onde

    doc = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    fora: dict[str, list[str]] = {}
    for m in re.finditer(r'<select\b([^>]*data-gesto="acao-do-gesto"[^>]*)>(.*?)</select>',
                         doc, re.S):
        linha = re.search(r'data-linha="([^"]+)"', m.group(1))
        assert linha, "uma lista da tabela dos gestos nasceu sem `data-linha`"
        fora[linha.group(1)] = re.findall(r"<option[^>]*>([^<]*)</option>", m.group(2))
    return fora


def test_a_lista_da_bancada_e_o_vocabulario_do_produto() -> None:
    """As seis listas do mockup regerado oferecem EXATAMENTE os rótulos do dono."""
    listas = _listas_da_bancada()
    assert set(listas) == set(ag.GESTOS), listas.keys()
    rotulos = [r for _g, ops in ag.por_grupo() for r in ops]
    for gesto, ops in listas.items():
        assert ops == rotulos, f"a lista do {gesto} diverge do vocabulário: {ops}"
        assert "Religar o controle" not in ops
        assert ag.rotulo(ag.NADA) in ops, "o «— Nada —» saiu: a §14 o devolveu nos seis"


def test_todo_token_tem_atendente(atendentes: dict[str, list[Any]],
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada ato do vocabulário chega a QUEM o faz — nenhum cai no vazio."""
    rodados: list[str] = []
    monkeypatch.setattr(hotkey, "_rodar_o_script_do_gesto",
                        lambda _d, gesto, caminho, quem: rodados.append(caminho))
    esperado = {
        ag.PERFIL_SEGUINTE: ("perfil+",), ag.PERFIL_ANTERIOR: ("perfil-",),
        ag.MODO_SEGUINTE: ("modo",), ag.MASCARA_SEGUINTE: ("mascara",),
        ag.ABRIR_A_STEAM: ("steam",),
        ag.ABRIR_O_HEFESTO: ("abrir",), ag.REINICIAR_O_SERVICO: ("abrir",),
        ag.PARAR_O_SERVICO: ("abrir",),
    }
    for faz in ag.ACOES:
        atendentes["chamou"].clear()
        rodados.clear()
        d = _daemon()
        atos = hotkey._AtosDoGesto(d)
        escolha = ag.EscolhaDoGesto(faz, "/x/y.sh" if faz == ag.SCRIPT else None, True)
        _rodar(atos.fazer("ps_options", escolha, None))
        assert atos._fio("ps_options").esperar(5.0)
        nomes = tuple(n for n, _ in atendentes["chamou"])
        if faz in esperado:
            assert nomes == esperado[faz], (faz, nomes)
        elif faz == ag.SUSPENDER:
            assert d.chamados == [("suspender", ())]
        elif faz == ag.SAIR_DO_MODO_JOGO:
            assert d.chamados == [("suspender", (False,))]
        elif faz == ag.SCRIPT:
            assert rodados == ["/x/y.sh"]
        elif faz == ag.NADA:
            assert nomes == () and d.chamados == []
        else:  # pragma: no cover - token novo sem atendente
            pytest.fail(f"o token {faz!r} não tem atendente nesta régua")


def test_o_de_fabrica_e_o_ato_de_antes(atendentes: dict[str, list[Any]]) -> None:
    """Sem declaração, cada gesto faz o que o `start_hotkey_manager` fazia."""
    assert {g.nome_no_gerente: g.botoes for g in ag.GESTOS.values()} == {
        "gamemode": hotkey_daemon.DEFAULT_COMBO_GAMEMODE,
        "next": hotkey_daemon.DEFAULT_COMBO_NEXT,
        "prev": hotkey_daemon.DEFAULT_COMBO_PREV,
        "ponte": hotkey_daemon.DEFAULT_COMBO_PONTE,
        "mascara": hotkey_daemon.DEFAULT_COMBO_MASCARA,
        "ps_solo": ("ps",),
    }
    d = _daemon()
    hotkey.start_hotkey_manager(d)
    mgr = d._hotkey_manager
    assert set(mgr._combos_configurados()) == {
        g.nome_no_gerente for g in ag.GESTOS.values() if g.chave != ag.GESTO_DO_PS}
    feitos = []
    for gesto in ("ps_cima", "ps_baixo", "ps_r3", "ps_l3"):
        atendentes["chamou"].clear()
        _apertar(mgr, ag.GESTOS[gesto].botoes)
        feitos.append(atendentes["chamou"][0][0])
    assert feitos == ["perfil+", "perfil-", "modo", "mascara"]
    _apertar(mgr, ag.GESTOS["ps_options"].botoes)
    assert d.chamados == [("suspender", ())], "o PS + Options deixou de suspender"


class _PonteDoDaemon:
    """A ponte da janela com o `machine.declare` ligado ao handler de VERDADE."""

    def __init__(self, daemon: Any, *, arquivo: str | None = None) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _Servidor(IpcHandlersMixin):
            pass

        self.servidor = _Servidor()
        self.servidor.daemon = daemon  # type: ignore[assignment]
        self.arquivo = arquivo
        self.escolhas: list[str] = []
        self.declarados: list[dict[str, Any]] = []

    def machine_declare(self, maquina: dict[str, Any]) -> tuple[bool, str | None]:
        self.declarados.append(maquina)
        r = asyncio.run(self.servidor._handle_machine_declare({"maquina": maquina}))
        return bool(r.get("ok")), r.get("reason")

    def escolher_arquivo(self, titulo: str, padrao: str = "*", **_: Any) -> str | None:
        self.escolhas.append(f"{titulo}|{padrao}")
        return self.arquivo


def _clicar(ponte: Any, gesto: str, rotulo: str) -> Any:
    import pacotes

    pacotes._carregar_tudo()
    fn = pacotes.gesto_da_pagina(PAGINA, "acao-do-gesto")
    assert fn is not None, "a lista dos gestos voltou a não ter dono"
    ctx = pacotes.Contexto(state={})
    return fn(ctx, {"linha": gesto, "rotulo": rotulo, "valor": rotulo}, ponte)


def test_escolher_na_tela_muda_o_controle(atendentes: dict[str, list[Any]]) -> None:
    """A 06 grava pelo `machine.declare` de verdade, e o PS + Options passa a trocar de perfil."""
    d = _daemon()
    hotkey.start_hotkey_manager(d)
    _clicar(_PonteDoDaemon(d), "ps_options", "Próximo perfil")
    assert mq.carregar_maquina().gestos["ps_options"].faz == ag.PERFIL_SEGUINTE
    assert d._maquina.gestos["ps_options"].faz == ag.PERFIL_SEGUINTE, (
        "o daemon não releu a tabela no mesmo pedido")
    _apertar(d._hotkey_manager, ("ps", "options"))
    assert [n for n, _ in atendentes["chamou"]] == ["perfil+"]
    assert d.chamados == []


def test_a_pagina_de_antes_recusa_como_antes() -> None:
    """A página publicada antes da sprint não tem `data-linha`: o clique recusa, nada grava."""
    d = _daemon()
    ponte = _PonteDoDaemon(d)
    with pytest.raises(ValueError):
        _clicar(ponte, "", "— Nada —")
    assert ponte.declarados == []


@pytest.mark.parametrize("mac,via,numero", CONTROLES)
def test_o_gesto_de_qualquer_controle_faz_o_escolhido(
        atendentes: dict[str, list[Any]], mac: str, via: str, numero: int) -> None:
    """O PS + L3 em «Próximo perfil» troca de perfil, venha de P1 a P4, no cabo ou no rádio."""
    d = _daemon({"ps_l3": {"faz": "mascara_seguinte"}, "ps_cima": {"faz": "modo_seguinte"}})
    hotkey.start_hotkey_manager(d)
    _apertar(d._hotkey_manager, ("ps", "l3"), de=mac)
    _apertar(d._hotkey_manager, ("ps", "dpad_up"), de=mac, t0=1.0)
    assert atendentes["chamou"] == [("mascara", mac), ("modo", mac)]


def _script(pasta: pathlib.Path, nome: str = "limpa.sh", *, corpo: bytes = b"#!/bin/sh\nexit 0\n",
            modo: int = 0o700) -> pathlib.Path:
    pasta.chmod(0o700)
    arquivo = pasta / nome
    arquivo.write_bytes(corpo)
    arquivo.chmod(modo)
    return arquivo


def test_as_guardas_do_arquivo(tmp_path: pathlib.Path) -> None:
    """Cada regra recusa com o seu motivo; o arquivo bom passa."""
    bom = _script(tmp_path)
    assert ag.conferir_o_script(str(bom)) is None
    assert ag.conferir_o_script("limpa.sh") == ag.CAMINHO_INVALIDO
    assert ag.conferir_o_script(str(tmp_path / "nao-ha.sh")) == ag.SEM_O_ARQUIVO
    assert ag.conferir_o_script(str(bom), uid=os.getuid() + 1) == ag.DE_OUTRO_DONO
    grupo = _script(tmp_path, "g.sh", modo=0o720)
    assert ag.conferir_o_script(str(grupo)) == ag.GRAVAVEL_POR_OUTROS
    assert ag.conferir_o_script(str(_script(tmp_path, "x.sh", modo=0o600))) == ag.SEM_EXECUCAO
    assert ag.conferir_o_script(
        str(_script(tmp_path, "b.sh", corpo=b"echo oi\n"))) == ag.SEM_O_INTERPRETADOR
    tmp_path.chmod(0o770)
    try:
        assert ag.conferir_o_script(str(bom)) == ag.PASTA_GRAVAVEL
    finally:
        tmp_path.chmod(0o700)


@pytest.fixture
def gerenciador(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O `systemd-run --wait` de mentira, e o `notify` anotado."""
    estado: dict[str, Any] = {"cmds": [], "recados": [], "rc": 0,
                              "fim": "Finished with result: success"}

    def _run(cmd: Any, env: Any) -> subprocess.CompletedProcess[str]:
        estado["cmds"].append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), estado["rc"], "",
                                           f"Running as unit: x\n{estado['fim']}\n")

    monkeypatch.setattr(fora_do_servico, "contexto_atual",
                        lambda **_k: fora_do_servico.Contexto(
                            gerenciador=True, herdaria="dentro do serviço h.service",
                            oom_do_gerenciador=100))
    monkeypatch.setattr(fora_do_servico, "_executar_esperando", lambda _teto: _run)
    monkeypatch.setattr(desktop_notifications, "notify",
                        lambda **k: estado["recados"].append(k["body"]) or True)
    return estado


def test_o_script_roda_sem_shell_com_teto_e_diz_quem_fez(
        tmp_path: pathlib.Path, gerenciador: dict[str, Any]) -> None:
    """Um argumento só depois do `--`, `RuntimeMaxSec=60`, `--wait`, e o jogador e o transporte."""
    arquivo = _script(tmp_path)
    d = _daemon()
    hotkey._rodar_o_script_do_gesto(d, "ps_l3", str(arquivo), "aa:bb:cc:00:00:02")
    assert len(gerenciador["cmds"]) == 1
    cmd = gerenciador["cmds"][0]
    assert cmd[cmd.index("--") + 1:] == [str(arquivo)], cmd
    assert "sh" not in cmd and "-c" not in cmd
    assert "--wait" in cmd and "--property=RuntimeMaxSec=60" in cmd
    assert f"--setenv={ag.VARIAVEL_DO_JOGADOR}=2" in cmd
    assert f"--setenv={ag.VARIAVEL_DO_TRANSPORTE}=bt" in cmd
    assert not any("aa:bb:cc" in a or "aabbcc" in a for a in cmd), "o endereço vazou"
    assert gerenciador["recados"] == []


def test_o_script_que_sai_com_3_roda_uma_vez_e_da_o_recado(
        tmp_path: pathlib.Path, gerenciador: dict[str, Any]) -> None:
    """O código do script não é recusa do gerenciador: uma chamada, e o recado com o 3."""
    gerenciador["rc"] = 3
    gerenciador["fim"] = ("Finished with result: exit-code\n"
                          "Main processes terminated with: code=exited/status=3")
    hotkey._rodar_o_script_do_gesto(_daemon(), "ps", str(_script(tmp_path)), None)
    assert len(gerenciador["cmds"]) == 1
    assert gerenciador["recados"] == ["limpa.sh: saiu com o código 3."]


def test_o_script_que_passa_do_teto_e_parado(
        tmp_path: pathlib.Path, gerenciador: dict[str, Any]) -> None:
    gerenciador["rc"] = 1
    gerenciador["fim"] = "Finished with result: timeout"
    hotkey._rodar_o_script_do_gesto(_daemon(), "ps", str(_script(tmp_path)), None)
    assert gerenciador["recados"] == ["limpa.sh: passou de 60 s e foi parado."]


def test_a_recusa_do_gerenciador_tenta_a_outra_forma(
        tmp_path: pathlib.Path, gerenciador: dict[str, Any]) -> None:
    """Sem o resumo do fim, o rc é do gerenciador: a forma seguinte, como no `abrir`."""
    gerenciador["rc"] = 1
    gerenciador["fim"] = "Unknown assignment: ExitType=cgroup"
    resultado = fora_do_servico.rodar_e_esperar(
        [str(_script(tmp_path))], env={}, teto_s=60,
        popen=lambda *a, **k: SimpleNamespace(pid=1, wait=lambda timeout=None: 0))
    assert len(gerenciador["cmds"]) == 2
    assert resultado.caminho == "popen" and resultado.saiu_com == 0


@pytest.mark.parametrize("estrago", ["dono", "sumiu"])
def test_o_daemon_confere_de_novo_na_hora_de_rodar(
        tmp_path: pathlib.Path, gerenciador: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch, estrago: str) -> None:
    """O arquivo mudou entre a escolha e o gesto: não roda, e o recado diz o motivo."""
    arquivo = _script(tmp_path)
    if estrago == "sumiu":
        arquivo.unlink()
    else:
        outro = os.getuid() + 1
        monkeypatch.setattr(ag.os, "getuid", lambda: outro)
    hotkey._rodar_o_script_do_gesto(_daemon(), "ps", str(arquivo), None)
    assert gerenciador["cmds"] == []
    motivo = ag.SEM_O_ARQUIVO if estrago == "sumiu" else ag.DE_OUTRO_DONO
    assert gerenciador["recados"] == [f"limpa.sh: {motivo}."]


def test_a_tela_recusa_o_script_sem_permissao_e_nao_grava(tmp_path: pathlib.Path) -> None:
    """Escolhido no seletor e conferido ao escolher: o sem `#!` não chega ao disco."""
    ruim = _script(tmp_path, "ruim.sh", corpo=b"echo oi\n")
    d = _daemon()
    ponte = _PonteDoDaemon(d, arquivo=str(ruim))
    with pytest.raises(RuntimeError, match="#!"):
        _clicar(ponte, "ps", "Escolher um script…")
    assert ponte.escolhas == ["Escolher um script|*.sh"]
    assert ponte.declarados == []
    assert "ps" not in mq.carregar_maquina().gestos


def test_cancelar_o_seletor_nao_grava(tmp_path: pathlib.Path) -> None:
    d = _daemon()
    ponte = _PonteDoDaemon(d, arquivo=None)
    assert _clicar(ponte, "ps", "Escolher um script…") is None
    assert ponte.declarados == []


def test_o_script_escolhido_vai_para_a_maquina(tmp_path: pathlib.Path) -> None:
    bom = _script(tmp_path)
    d = _daemon()
    _clicar(_PonteDoDaemon(d, arquivo=str(bom)), "ps_cima", "Escolher um script…")
    gesto = mq.carregar_maquina().gestos["ps_cima"]
    assert (gesto.faz, gesto.script) == (ag.SCRIPT, os.path.realpath(bom))


def test_o_perfil_nao_carrega_gesto_nem_script() -> None:
    """Um perfil importado de outra pessoa não traz script (`D-2909-OS-GESTOS-SAO-DA-MAQUINA`)."""
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import Profile

    base = {"name": "x", "match": {"type": "criteria"}}
    for intruso in ({"gestos": {"ps": {"faz": "script", "script": "/x.sh"}}},
                    {"script": "/x.sh"}):
        with pytest.raises(ValidationError):
            Profile.model_validate({**base, **intruso})


def test_a_maquina_so_aceita_a_forma_certa() -> None:
    for ruim in ({"gestos": {"ps_x": {"faz": "nada"}}},
                 {"gestos": {"ps": {"faz": "voar"}}},
                 {"gestos": {"ps": {"faz": "script", "script": "relativo.sh"}}},
                 {"gestos": {"ps": {"faz": "script"}}}):
        with pytest.raises(ValueError):
            mq.MaquinaConfig.model_validate(ruim)
    assert mq.gravar_maquina({"gestos": {"ps": {"faz": "script", "script": "/a/b.sh"}}})
    assert mq.gravar_maquina({"gestos": {"ps": {"faz": "nada"}}})
    assert mq.carregar_maquina().gestos["ps"].script is None, (
        "trocar o script por outro ato deixou o caminho velho guardado")
    assert mq.gravar_maquina({"gestos": {"ps": None}})
    assert "ps" not in mq.carregar_maquina().gestos


def test_a_bandeja_e_o_controle_chamam_o_mesmo_ato(atendentes: dict[str, list[Any]]) -> None:
    """O `cmd_tray` usa os atos do dono (`is`), e o gesto os abre noutro processo."""
    from hefesto_dualsense4unix.app.actions import atos_da_bandeja as ab
    from hefesto_dualsense4unix.cli import cmd_tray

    assert cmd_tray._abrir_o_painel is ab.abrir_o_painel
    assert cmd_tray._servico is ab.mexer_no_servico
    assert cmd_tray.LANCADOR_DO_PAINEL is ab.LANCADOR_DO_PAINEL
    for faz, ato in ((ag.ABRIR_O_HEFESTO, "abrir"), (ag.REINICIAR_O_SERVICO, "reiniciar"),
                     (ag.PARAR_O_SERVICO, "parar")):
        atendentes["chamou"].clear()
        atos = hotkey._AtosDoGesto(_daemon())
        atos.fazer("ps_l3", ag.EscolhaDoGesto(faz, None, True), None)
        assert atos._fio("ps_l3").esperar(5.0)
        assert atendentes["chamou"] == [
            ("abrir", [sys.executable, "-m", "hefesto_dualsense4unix.app.actions.atos_da_bandeja",
                       ato])]


def test_o_main_da_bandeja_e_o_ato_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.app.actions import atos_da_bandeja as ab

    feitos: list[str] = []
    monkeypatch.setattr(ab, "mexer_no_servico", lambda v: feitos.append(v) or True)
    monkeypatch.setattr(ab, "abrir_o_painel", lambda: feitos.append("painel"))
    assert [ab.main([a]) for a in ("reiniciar", "parar", "abrir")] == [0, 0, 0]
    assert feitos == ["restart", "stop", "painel"]
    assert ab.main(["ativar-de-mentira"]) == 2


def _pintar() -> dict[str, Any]:
    from pacotes import a06_navegacao

    a06_navegacao._A_MAQUINA = None
    return a06_navegacao._o_que_os_gestos_fazem()


def test_a_tela_pinta_o_que_a_maquina_diz(tmp_path: pathlib.Path) -> None:
    """Com o `maquina.json` dizendo `ps_l3: abrir_o_hefesto`, a linha 5 diz «Abrir o Hefesto»."""
    bom = _script(tmp_path)
    assert mq.gravar_maquina({"gestos": {
        "ps_l3": {"faz": "abrir_o_hefesto"}, "ps": {"faz": "nada"},
        "ps_cima": {"faz": "script", "script": str(bom)}}})
    pintado = _pintar()
    assert pintado["faz-ps_l3"] == "Abrir o Hefesto"
    assert pintado["faz-ps"] == "— Nada —"
    assert pintado["faz-ps_options"] == "Suspender mouse e teclado"
    assert pintado["script-ps_cima"] == "limpa.sh" and pintado["faz-ps_cima"] == "limpa.sh"
    assert pintado["script-ps"] == "Escolher um script…"
    chaves = list(pintado)
    assert chaves.index("script-ps_cima") < chaves.index("faz-ps_cima"), (
        "a opção do script tem de ganhar o nome ANTES de a lista pedir por ele")


def test_a_escolha_sobrevive_a_reabrir_a_aba(atendentes: dict[str, list[Any]]) -> None:
    """O «— Nada —» escolhido na 06 continua lá depois de a aba (ou a janela) reabrir."""
    d = _daemon()
    _clicar(_PonteDoDaemon(d), "ps", "— Nada —")
    assert _pintar()["faz-ps"] == "— Nada —"
    assert _pintar()["faz-ps"] == "— Nada —"


def test_a_dica_diz_a_saida_que_ficou_sem_gesto() -> None:
    assert mq.gravar_maquina({"gestos": {"ps_r3": {"faz": "nada"},
                                         "ps_l3": {"faz": "parar_o_servico"}}})
    dica = _pintar()["gestos-dica"]
    assert "Próximo Modo" in dica and "Suspender" not in dica
    assert "Parar o serviço" in dica and "bandeja" in dica
    assert mq.gravar_maquina({"gestos": {"ps_r3": None, "ps_l3": None}})
    from pacotes.a06_navegacao import NADA_A_DIZER

    assert _pintar()["gestos-dica"] == NADA_A_DIZER


def test_a_bancada_tem_os_enderecos_da_pintura() -> None:
    """Cada lista tem `data-campo` de valor, e a opção do script tem o seu."""
    import onde

    doc = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    for g in ag.GESTOS:
        assert f'data-campo="faz-{g}" data-hef-alvo="valor"' in doc, g
        assert f'<option data-campo="script-{g}">' in doc, g
    assert 'data-campo="gestos-dica"' in doc


MODOS = {
    "dualsense": {"gamepad_caminho": "dualsense"},
    "xbox": {"gamepad_caminho": "xbox"},
    "navegacao": {"gamepad_caminho": "mouse_teclado"},
    "steam_input": {"gamepad_caminho": "dualsense", "steam_input": True},
}
JOGOS = {"fechado": ("daemon", None), "com_autoridade": ("game", None),
         "vivo_sem_autoridade": ("daemon", 3621330)}
SEXTOS = {"nada": {"ps": {"faz": "nada"}}, "steam": {"ps": {"faz": "abrir_a_steam"}},
          "nao_declarado": {}}


@pytest.mark.parametrize("sexto", list(SEXTOS))
@pytest.mark.parametrize("jogo", list(JOGOS))
@pytest.mark.parametrize("modo", list(MODOS))
def test_o_ps_sozinho_so_abre_a_steam_sem_jogo_e_com_o_sexto_na_steam(
        monkeypatch: pytest.MonkeyPatch, modo: str, jogo: str, sexto: str) -> None:
    """A Steam abre se, e só se, não há jogo e o ⑥ diz Steam (declarado ou de fábrica)."""
    abertas: list[str | None] = []
    autoridade, appid = JOGOS[jogo]
    monkeypatch.setattr(steam_launcher, "open_or_focus_steam",
                        lambda *a, **k: abertas.append("steam") or True)
    monkeypatch.setattr(autoswitch, "jogo_do_wrapper_vivo", lambda **_k: appid)
    deve_abrir = jogo == "fechado" and sexto in ("steam", "nao_declarado")
    for mac, _via, _n in CONTROLES:
        abertas.clear()
        d = _daemon(SEXTOS[sexto], autoridade=autoridade)
        d.config.__dict__.update(MODOS[modo])
        gesto = hotkey.build_ps_solo_callback(d)
        mgr = HotkeyManager(on_ps_solo=gesto)
        mgr.observe(["ps"], now=0.0, de=mac)
        mgr.observe([], now=0.1, de=mac)
        assert gesto.esperar(5.0)
        assert abertas == (["steam"] if deve_abrir else []), (modo, jogo, sexto, mac)


@pytest.mark.parametrize("gesto", list(ag.GESTOS))
def test_o_nada_cala_os_seis(atendentes: dict[str, list[Any]], gesto: str,
                             monkeypatch: pytest.MonkeyPatch) -> None:
    """O «— Nada —» vale nos seis gestos (a §14, dela): nenhum atendente é chamado."""
    no_fio: list[str] = []
    original = hotkey._AtosDoGesto._fio

    def _anotar(self: Any, g: str) -> Any:
        no_fio.append(g)
        return original(self, g)

    monkeypatch.setattr(hotkey._AtosDoGesto, "_fio", _anotar)
    d = _daemon({gesto: {"faz": "nada"}})
    hotkey.start_hotkey_manager(d)
    mgr = d._hotkey_manager
    _apertar(mgr, ag.GESTOS[gesto].botoes)
    assert mgr.on_ps_solo.esperar(5.0)
    assert atendentes["chamou"] == [] and d.chamados == []
    assert no_fio == [], f"o «— Nada —» de {gesto} foi ao fio dos atos de fora"


def test_o_sexto_que_nao_e_a_steam_vai_ao_laco_com_quem_fez(
        atendentes: dict[str, list[Any]]) -> None:
    """O ⑥ em «Próxima Máscara» anda o cartão de QUEM fez, pelo laço do daemon."""

    async def _cena() -> None:
        d = _daemon({"ps": {"faz": "mascara_seguinte"}})
        hotkey.start_hotkey_manager(d)
        mgr = d._hotkey_manager
        mgr.observe(["ps"], now=0.0, de="aa:bb:cc:00:00:03")
        mgr.observe([], now=0.1, de="aa:bb:cc:00:00:03")
        for _ in range(200):
            if atendentes["chamou"]:
                break
            await asyncio.sleep(0.01)

    asyncio.run(_cena())
    assert atendentes["chamou"] == [("mascara", "aa:bb:cc:00:00:03")]
