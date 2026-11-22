"""D-2211-O-RODAPE-ESPERA-O-SERVICO-QUE-REINICIA: o rodapé manda o perfil que vale ao jogo aberto.

Medido em 21/11/2026 (Mad King Redemption aberto, perfil dele valendo): o Reiniciar da aba Sistema
e, 2 a 4 s depois, o Salvar e o Aplicar do rodapé. O serviço já escutava, mas ainda sem perfil
ativo; o rodapé mandou a escolha de fora do jogo («Azahar»), que entrou como perfil ativo e armou a
trava da mão, e o boot desistiu do perfil do jogo (`a_escolha_nao_entra_por_cima`). Dois donos
respondiam diferente a «qual perfil vale com o serviço calado»: a tela lia a escolha do usuário, o
boot lia o Freestyle, o jogo em cena, o último jogo e só então a escolha
(`D-3009-O-REINICIO-COM-O-JOGO-ABERTO-NASCE-NO-PERFIL-DO-JOGO`,
`D-2110-O-PERFIL-ATIVO-FICA-A-DIREITA-COM-O-SERVICO-PARADO`).

O lar é de mentira (`HOME` e `XDG_*` desviados, com guarda que sai): três perfis, o marcador do
wrapper com o appid e um pid vivo. O serviço é um dublê que
nasce parado, escuta depois do `restart` sem perfil ativo e restaura o perfil do jogo dois
segundos depois, desistindo se já houver outro valendo, como `restore_last_profile`.

MORDIDAS (cada uma reprova o que diz, e o md5 do arquivo volta igual):
- o corpo de ``profiles_actions.perfil_que_o_usuario_ativou`` voltando a ``resolve_boot_profile()``
  reprova ``test_a_tela_e_o_boot_dao_o_mesmo_nome``;
- tirar ``_esperar_o_servico_que_reinicia`` dos gestos reprova
  ``test_o_gesto_com_o_servico_fora_espera_e_nao_culpa_o_servico``, o do teto e o do estado que só
  vale depois do restart;
- trocar ``session.reinicio_subiu()`` por ``reinicio_em_curso()`` na espera reprova
  ``test_so_o_estado_depois_do_restart_vale``;
- tirar de ``a09_sistema.reiniciar`` o ``marcar_o_reinicio`` reprova o do teto e o do gesto depois
  do reiniciar.
"""
from __future__ import annotations

import os
import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.connection import _o_nome_que_o_boot_restaura
from hefesto_dualsense4unix.interface.pacotes import Contexto, rodape
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.slug import mesmo_slug
from hefesto_dualsense4unix.utils import session, xdg_paths

APPID = 1912410
JOGO = "Mad King Redemption"
ESCOLHA = "Azahar"
ULTIMO = "Avatar Legends"
FREESTYLE = loader.NOME_DO_PADRAO
REINICIO = "O reinício está demorando e segue em curso"


@pytest.fixture
def lar(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    """O lar de mentira: perfis, escolha à mão e o marcador do wrapper que a régua escreve."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for var, sub in (("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state"),
                     ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")):
        monkeypatch.setenv(var, str(tmp_path / sub))
    casa = xdg_paths.config_dir(ensure=True)
    if not str(casa).startswith(str(tmp_path)):
        pytest.exit(f"a régua ia ler o config_dir de verdade: {casa}", returncode=3)
    loader.save_profile(Profile(name=FREESTYLE, match=MatchAny()), origem="régua")
    loader.save_profile(Profile(
        name=JOGO, match=MatchCriteria(window_class=[f"steam_app_{APPID}"]), priority=80,
    ), origem="régua")
    loader.save_profile(Profile(
        name=ESCOLHA, match=MatchCriteria(window_class=["zathura"]), priority=60,
    ), origem="régua")
    loader.save_profile(Profile(
        name=ULTIMO, match=MatchCriteria(window_class=["steam_app_2"]), priority=70,
    ), origem="régua")
    session.save_last_profile(ESCOLHA)
    session.save_freestyle_ligado(False)
    session.encerrar_o_reinicio()
    yield
    session.encerrar_o_reinicio()


def _marcar_o_jogo(appid: int) -> None:
    pasta = xdg_paths.launch_env_dir(ensure=True)
    (pasta / "last_run").write_text(
        f"appid={appid}\nepoch={int(time.time()) - 300}\npid={os.getpid()}\n", encoding="utf-8")


def _o_disco(caso: str) -> tuple[str, int | None]:
    """Arruma o disco do caso; devolve o perfil esperado e o appid que o serviço teria em cena."""
    if caso == "freestyle-ligado":
        session.save_freestyle_ligado(True)
    if caso == "ultimo-jogo":
        session.lembrar_o_ultimo_jogo(ULTIMO)
    if caso in ("jogo-com-perfil", "freestyle-ligado"):
        _marcar_o_jogo(APPID)
    if caso == "jogo-sem-perfil":
        _marcar_o_jogo(999999)
    em_cena = {"jogo-com-perfil": APPID, "freestyle-ligado": APPID,
               "jogo-sem-perfil": 999999}.get(caso)
    esperado = {"jogo-com-perfil": JOGO, "freestyle-ligado": FREESTYLE,
                "ultimo-jogo": ULTIMO}.get(caso, ESCOLHA)
    return esperado, em_cena


CASOS = ["jogo-com-perfil", "sem-jogo", "freestyle-ligado", "jogo-sem-perfil", "ultimo-jogo"]


@pytest.mark.parametrize("caso", CASOS)
def test_a_tela_e_o_boot_dao_o_mesmo_nome(lar: None, caso: str) -> None:
    """Com o serviço calado, o rodapé nomeia o que o boot restauraria.

    Com o Mad King em cena, «Mad King Redemption» (e não a escolha «Azahar»); sem jogo, a escolha;
    com o Freestyle ligado, o Freestyle; com o jogo sem perfil, a escolha; com o último jogo
    lembrado, ele.

    MORDIDA: o corpo de ``perfil_que_o_usuario_ativou`` voltando a ``resolve_boot_profile()``.
    """
    esperado, em_cena = _o_disco(caso)
    assert rodape.perfil_do_rodape(None) == esperado
    assert rodape.perfil_do_rodape({"active_profile": None}) == esperado
    assert _o_nome_que_o_boot_restaura(None, appid_em_cena=em_cena) == esperado


def test_a_pergunta_da_tela_nao_varre_processo(
        lar: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tela pergunta a cada tique, no fio da janela: nada de `/proc` na perna do disco.

    MORDIDA: faça ``o_jogo_em_cena_no_disco`` chamar ``steam_game_running_appid`` (a varredura
    reprovou ``test_o_fio_da_janela_nunca_espera`` com 8 aberturas de ``/proc/<pid>/cmdline``).
    """
    varreduras: list[int] = []

    def varre(*_a: Any, **_k: Any) -> None:
        varreduras.append(1)

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.steam_launch_options.steam_game_running_appid", varre)
    _o_disco("jogo-com-perfil")
    assert rodape.perfil_do_rodape(None) == JOGO
    assert varreduras == [], "a perna do disco varreu os processos"


def test_o_perfil_do_jogo_lembrado_acompanha_a_pasta_de_perfis(lar: None) -> None:
    """A tela lembra o perfil do jogo entre tiques, e esquece quando a pasta de perfis muda.

    MORDIDA: tire o ``st_mtime_ns`` da chave de ``_o_perfil_do_jogo_lembrado``.
    """
    _o_disco("jogo-com-perfil")
    assert rodape.perfil_do_rodape(None) == JOGO
    loader.save_profile(Profile(
        name="Mad King Redux", match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=95,
    ), origem="régua")
    assert rodape.perfil_do_rodape(None) == "Mad King Redux"


def test_o_estado_do_servico_vence_o_disco(lar: None) -> None:
    """O serviço de pé responde primeiro: o disco só vale quando ele cala."""
    _o_disco("jogo-com-perfil")
    assert rodape.perfil_do_rodape({"active_profile": ESCOLHA}) == ESCOLHA


class _Relogio:
    def __init__(self) -> None:
        self.t = 1000.0
        self.ao_dormir: list[Any] = []

    def agora(self) -> float:
        return self.t

    def dormir(self, s: float) -> None:
        self.t += s
        for quem in self.ao_dormir:
            quem(self.t)


class _Servico:
    """O serviço de mentira, na ordem do que o reinício mediu.

    Vivo e antigo até o `restart`; depois escuta sem perfil ativo; o boot restaura o perfil do jogo
    em ``boot_em`` segundos, e desiste se já houver outro valendo (`a_escolha_nao_entra_por_cima`).
    """

    def __init__(self, relogio: _Relogio, *, ativo_antigo: str, restaura: str,
                 boot_em: float = 2.0) -> None:
        self.r = relogio
        self.ativo: str | None = ativo_antigo
        self.escuta = True
        self.antigo = True
        self.restaura = restaura
        self.boot_em = boot_em
        self.boot_as: float | None = None
        self.desistiu = False
        self.pedidos: list[tuple[str, bool, bool]] = []
        relogio.ao_dormir.append(self.passou)

    def reiniciou(self) -> None:
        self.antigo = False
        self.ativo = None
        self.boot_as = self.r.t + self.boot_em

    def passou(self, agora: float) -> None:
        if self.boot_as is None or agora < self.boot_as:
            return
        self.boot_as = None
        if self.ativo and not mesmo_slug(self.ativo, self.restaura):
            self.desistiu = True
            return
        self.ativo = self.restaura

    def daemon_state_full(self) -> dict[str, Any] | None:
        return {"active_profile": self.ativo} if self.escuta else None

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> dict[str, Any] | None:
        self.pedidos.append((nome, self.antigo, session.reinicio_subiu()))
        if not self.escuta:
            return None
        self.ativo = nome
        return {"active_profile": nome, "mode_aplicado": True, "secoes": {}}

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        return True

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        return {"status": "ok"}


@pytest.fixture
def mundo(lar: None, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O relógio de mentira, a carona calada e a volta do perfil sem IPC."""
    from hefesto_dualsense4unix.interface.pacotes import perfil

    relogio = _Relogio()
    monkeypatch.setattr(session, "_relogio", relogio.agora)
    monkeypatch.setattr(rodape, "_relogio", relogio.agora, raising=False)
    monkeypatch.setattr(rodape, "_dormir", relogio.dormir, raising=False)
    monkeypatch.setattr(perfil, "com_a_carona", lambda *a, **k: "")
    monkeypatch.setattr(perfil, "a_volta_do_perfil", lambda *a, **k: None)
    _marcar_o_jogo(APPID)
    return relogio


@pytest.fixture
def a09(monkeypatch: pytest.MonkeyPatch) -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a09_sistema`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    a09_sistema._PAINEL[0] = None
    a09_sistema._PERGUNTA.clear()
    monkeypatch.setattr(a09_sistema, "_trava", lambda *_a, **_k: None)
    monkeypatch.setattr(a09_sistema, "_repor_o_lancador", lambda: None)
    yield a09_sistema
    a09_sistema._PAINEL[0] = None
    a09_sistema._PERGUNTA.clear()


def _reiniciar(a09: Any, monkeypatch: pytest.MonkeyPatch, servico: _Servico) -> None:
    """O gesto Reiniciar da aba Sistema, com o `systemctl restart` ligado ao serviço de mentira."""
    class _Janela:
        def _invoke_systemctl(self, args: list[str], **_: Any) -> Any:
            if args[0] == "restart":
                servico.reiniciou()
            return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(a09, "_matriz", lambda: _Janela())
    a09.reiniciar(SimpleNamespace(state={}), {}, None)


GESTOS = ["aplicar", "salvar", "salvar-e-aplicar"]


def _gesto(nome: str, servico: _Servico, estado: dict[str, Any] | None) -> None:
    ctx = Contexto(state=estado if estado is not None else {})
    funcao = {"aplicar": rodape.aplicar, "salvar": rodape.salvar,
              "salvar-e-aplicar": rodape.salvar_e_aplicar}[nome]
    funcao(ctx, {"gesto": nome}, servico)


@pytest.mark.parametrize("gesto", GESTOS)
def test_o_gesto_depois_do_reiniciar_manda_o_perfil_do_jogo(
        mundo: _Relogio, a09: Any, monkeypatch: pytest.MonkeyPatch, gesto: str) -> None:
    """O Aplicar, o Salvar e o Salvar e aplicar logo depois do Reiniciar deixam o jogo valendo.

    O reinício volta e o serviço escuta sem perfil; o gesto espera o boot restaurar o do jogo e
    manda ESSE nome, e o boot não desiste. Todos os gestos dão o mesmo desfecho.

    MORDIDA: tire ``_esperar_o_servico_que_reinicia`` do gesto, ou o ``marcar_o_reinicio`` do
    ``reiniciar``: o gesto manda a escolha «Azahar» e o boot desiste.
    """
    servico = _Servico(mundo, ativo_antigo=JOGO, restaura=JOGO)
    _reiniciar(a09, monkeypatch, servico)
    _gesto(gesto, servico, {"active_profile": ""})
    mundo.dormir(10.0)
    assert not servico.desistiu, "o boot desistiu: a escolha entrou por cima do jogo"
    assert servico.ativo == JOGO
    assert servico.pedidos
    assert {nome for nome, _antigo, _subiu in servico.pedidos} == {JOGO}


def test_so_o_estado_depois_do_restart_vale(
        mundo: _Relogio, a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Enquanto o `restart` não voltou, quem responde é o serviço que está parando.

    O serviço antigo ainda responde com o perfil dele; mandar o Aplicar a ele perde o pedido. O
    gesto só pergunta e só manda depois do `restart` (`marcar_que_o_servico_subiu`).

    MORDIDA: trocar ``session.reinicio_subiu()`` por ``session.reinicio_em_curso()`` na espera.
    """
    servico = _Servico(mundo, ativo_antigo=JOGO, restaura=JOGO)
    session.marcar_o_reinicio(80.0)
    sleeps = []

    def depois_de_tres(_agora: float) -> None:
        sleeps.append(1)
        if len(sleeps) == 3:
            servico.reiniciou()
            session.marcar_que_o_servico_subiu(35.0)

    mundo.ao_dormir.append(depois_de_tres)
    _gesto("aplicar", servico, {"active_profile": JOGO})
    assert len(sleeps) >= 3, "o gesto não esperou o restart voltar"
    assert servico.pedidos, "o gesto não mandou nada"
    assert all(not antigo and subiu for _n, antigo, subiu in servico.pedidos), servico.pedidos
    assert servico.ativo == JOGO and not servico.desistiu


@pytest.mark.parametrize("gesto", GESTOS)
def test_o_gesto_com_o_servico_fora_espera_e_nao_culpa_o_servico(
        mundo: _Relogio, a09: Any, monkeypatch: pytest.MonkeyPatch, gesto: str) -> None:
    """O clique que cai com o serviço fora do ar espera a volta, e não diz «desligado».

    Medido às 18h13min14,039 de 21/11: o Aplicar caiu entre a parada e a partida e a tela disse
    «Não consegui aplicar a cor — o Hefesto pode estar desligado», num reinício que a aba pediu.
    Agora o gesto espera, e o único pedido que sai vai ao serviço de pé, com o perfil do jogo.

    MORDIDA: tire ``_esperar_o_servico_que_reinicia`` do gesto.
    """
    servico = _Servico(mundo, ativo_antigo=JOGO, restaura=JOGO)
    session.marcar_o_reinicio(80.0)
    servico.escuta = False
    passos: list[int] = []

    def volta(_agora: float) -> None:
        passos.append(1)
        if len(passos) == 4:
            servico.escuta = True
            servico.reiniciou()
            session.marcar_que_o_servico_subiu(35.0)

    mundo.ao_dormir.append(volta)
    _gesto(gesto, servico, {"active_profile": ""})
    mundo.dormir(10.0)
    assert servico.pedidos, "o gesto não mandou nada"
    assert [(n, antigo) for n, antigo, _s in servico.pedidos] == [(JOGO, False)] * len(
        servico.pedidos), servico.pedidos
    assert servico.ativo == JOGO and not servico.desistiu


@pytest.mark.parametrize("gesto", GESTOS)
def test_estourado_o_teto_recusa_com_a_frase_do_reinicio_e_nao_manda(
        mundo: _Relogio, a09: Any, monkeypatch: pytest.MonkeyPatch, gesto: str) -> None:
    """O serviço que não volta no teto do `start`: a frase que já existe, e nenhum pedido.

    Nenhum texto novo: a recusa é ``REINICIO_EM_CURSO``, do reinício que a aba pediu.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import prazo_do_systemctl

    servico = _Servico(mundo, ativo_antigo=JOGO, restaura=JOGO, boot_em=10_000.0)
    _reiniciar(a09, monkeypatch, servico)
    antes = mundo.t
    with pytest.raises(RuntimeError) as erro:
        _gesto(gesto, servico, {"active_profile": ""})
    assert str(erro.value) == a09.REINICIO_EM_CURSO
    assert REINICIO in str(erro.value)
    assert servico.pedidos == [], "o gesto mandou o perfil com o serviço ainda sem perfil ativo"
    assert prazo_do_systemctl(["start"]) <= mundo.t - antes < prazo_do_systemctl(["start"]) + 1


def test_sem_a_marca_o_gesto_nao_espera_nem_pergunta(mundo: _Relogio) -> None:
    """Sem reinício desta janela (a bandeja é outro processo), o gesto manda na hora."""
    servico = _Servico(mundo, ativo_antigo=JOGO, restaura=JOGO)
    servico.antigo = False
    chamadas: list[str] = []
    original = servico.daemon_state_full
    servico.daemon_state_full = lambda: (chamadas.append("estado"), original())[1]  # type: ignore[method-assign]
    antes = mundo.t
    _gesto("aplicar", servico, {"active_profile": JOGO})
    assert mundo.t == antes and chamadas == []
    assert [n for n, _a, _s in servico.pedidos] == [JOGO]


def test_sem_nada_que_o_boot_restaure_o_gesto_nao_espera(
        mundo: _Relogio, a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem jogo, sem último jogo e sem escolha, o boot não restaura nada: não há o que esperar."""
    session.esquecer_a_escolha()
    (xdg_paths.launch_env_dir() / "last_run").unlink()
    servico = _Servico(mundo, ativo_antigo=JOGO, restaura=JOGO, boot_em=10_000.0)
    _reiniciar(a09, monkeypatch, servico)
    antes = mundo.t
    with pytest.raises(ValueError):
        _gesto("aplicar", servico, {"active_profile": ""})
    assert mundo.t == antes
    assert servico.pedidos == []


def test_o_reiniciar_que_falha_apaga_a_marca(
        mundo: _Relogio, a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `restart` recusado não deixa o rodapé esperando um reinício que não houve."""
    class _Janela:
        def _invoke_systemctl(self, args: list[str], **_: Any) -> Any:
            return SimpleNamespace(returncode=1 if args[0] == "restart" else 0,
                                   stderr="", stdout="")

    monkeypatch.setattr(a09, "_matriz", lambda: _Janela())
    with pytest.raises(RuntimeError):
        a09.reiniciar(SimpleNamespace(state={}), {}, None)
    assert not session.reinicio_em_curso()


def test_a_marca_vence_no_prazo(lar: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A marca acesa não vale para sempre: vence no prazo e o gesto volta a mandar na hora."""
    relogio = _Relogio()
    monkeypatch.setattr(session, "_relogio", relogio.agora)
    session.marcar_o_reinicio(10.0)
    assert session.reinicio_em_curso() and not session.reinicio_subiu()
    session.marcar_que_o_servico_subiu(10.0)
    assert session.reinicio_subiu()
    relogio.t += 11.0
    assert not session.reinicio_em_curso() and not session.reinicio_subiu()
