"""O Ativar da aba Perfis vale com o serviço parado, ou a tela diz por que não valeu.

O-ATIVAR-DO-PERFIL-VALE-OU-A-TELA-DIZ-POR-QUE-01, medido no diário de 22/10/2026: às 20:17:12 o
«Sair» da bandeja parou o serviço, o dock reabriu a janela às 20:17:16 e nada o trouxe de volta. O
Ativar mandava o `profile.switch` para ninguém, e o topo seguia nomeando o perfil do marcador do
disco, que ninguém aplicava. A resposta de produto às fotos: «Um clique religa e troca»,
inclusive depois do Parar da aba Sistema.

AS MORDIDAS (executadas em 22/10/2026):

1. tire a chamada a `_religar_o_servico` de `a10_perfis._ativar_o`: os três testes do clique com o
   serviço parado reprovam, porque a troca sai sem o serviço subir antes;
2. troque `_em_uso` por `_valendo` em `a10_perfis.pacote`: a lista volta a acender o perfil do
   marcador com o serviço parado, e `test_com_o_servico_parado_nada_esta_em_uso_na_tela` reprova;
3. devolva `"perfil": ativo or "—"` em `pacotes.topo`: o mesmo teste reprova no chip;
4. tire o `lembrar_o_parar(True)` de `a09_sistema.desligar`: a janela reaberta liga o serviço que
   ela parou de propósito, e `test_o_parar_da_aba_sistema_segura_o_servico_parado` reprova.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atos_da_bandeja, profiles_actions
from hefesto_dualsense4unix.interface import abrir
from hefesto_dualsense4unix.interface.pacotes import Contexto, a09_sistema, a10_perfis, fios, topo

PARADO: dict[str, Any] = {}
DE_PE: dict[str, Any] = {"active_profile": "meu_perfil", "paused": False, "controllers": []}


class PonteDeMentira:
    """Anota o que foi pedido e nunca fala com o daemon vivo."""

    def __init__(self, cala: bool = False) -> None:
        self.cala = cala
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def resultado(self, metodo: str, *args: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, tuple(kw.values())))
        if self.cala:
            raise RuntimeError("sem resposta")
        return {}


@pytest.fixture(autouse=True)
def _mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> list[str]:
    """Três perfis no disco, o marcador em `meu_perfil` e o runtime da sessão numa pasta própria."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    todos = [Profile(name=n, match=MatchAny(), priority=10 - i)
             for i, n in enumerate(("meu_perfil", "Ação", "Navegação"))]
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(profiles_actions, "perfil_que_ela_ativou", lambda: "meu_perfil")
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PROCURA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_RECUSA_DO_ATIVAR", [""])
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    atos: list[str] = []
    monkeypatch.setattr(atos_da_bandeja, "garantir_a_bandeja", lambda: atos.append("bandeja"))
    return atos


def _servico_que_sobe(monkeypatch: pytest.MonkeyPatch, atos: list[str],
                      erro: str = "") -> None:
    """O dono do ato de ligar (`a09_sistema.ativar_o_servico`), sem tocar o systemd."""
    def _ligar() -> bool:
        atos.append("ligar")
        if erro:
            raise RuntimeError(erro)
        return True

    monkeypatch.setattr(a09_sistema, "ativar_o_servico", _ligar)


def _ctx(state: dict[str, Any] | None) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def test_com_o_servico_parado_o_ativar_religa_e_troca(
    monkeypatch: pytest.MonkeyPatch, _mesa: list[str],
) -> None:
    """Um clique: o serviço sobe, a bandeja volta e a troca sai, nessa ordem, sem recusa."""
    _servico_que_sobe(monkeypatch, _mesa)
    a10_perfis._ESCOLHIDO = "Ação"
    ponte = PonteDeMentira()
    a10_perfis.ativar(_ctx(PARADO), {"texto": "Ativar"}, ponte)
    assert _mesa == ["ligar", "bandeja"], _mesa
    assert ponte.chamadas == [("profile.switch", ("Ação",))], ponte.chamadas
    assert a10_perfis.pacote(_ctx(PARADO))[a10_perfis.CAMPO_DA_RAZAO_DO_ATIVAR] == ""


def test_o_perfil_do_marcador_tambem_se_ativa_com_o_servico_parado(
    monkeypatch: pytest.MonkeyPatch, _mesa: list[str],
) -> None:
    """O marcador do disco não «já vale» com o serviço parado: o Ativar e a linha trocam."""
    _servico_que_sobe(monkeypatch, _mesa)
    a10_perfis._ESCOLHIDO = "meu_perfil"
    ponte = PonteDeMentira()
    a10_perfis.ativar(_ctx(PARADO), {"texto": "Ativar"}, ponte)
    a10_perfis.selecionar(_ctx(PARADO), {"hefPerfil": "meu_perfil"}, ponte)
    assert ponte.chamadas == [("profile.switch", ("meu_perfil",))] * 2, ponte.chamadas
    assert _mesa == ["ligar", "bandeja"] * 2, _mesa


def test_com_o_servico_de_pe_o_ativar_nao_liga_nada(
    monkeypatch: pytest.MonkeyPatch, _mesa: list[str],
) -> None:
    """A metade de controle: de pé, só a troca, e a guarda do «já vale» segue de pé."""
    _servico_que_sobe(monkeypatch, _mesa)
    a10_perfis._ESCOLHIDO = "Ação"
    ponte = PonteDeMentira()
    a10_perfis.ativar(_ctx(DE_PE), {"texto": "Ativar"}, ponte)
    assert _mesa == [] and ponte.chamadas == [("profile.switch", ("Ação",))]
    a10_perfis._ESCOLHIDO = "meu_perfil"
    with pytest.raises(RuntimeError, match="já é o perfil que está valendo"):
        a10_perfis.ativar(_ctx(DE_PE), {"texto": "Ativar"}, ponte)


def test_o_servico_que_nao_sobe_diz_por_que_no_ativar(
    monkeypatch: pytest.MonkeyPatch, _mesa: list[str],
) -> None:
    """A recusa vai à tarja e ao campo do Ativar, e some quando o serviço responde."""
    _servico_que_sobe(monkeypatch, _mesa, erro="Failed to start unit.")
    a10_perfis._ESCOLHIDO = "Ação"
    ponte = PonteDeMentira()
    with pytest.raises(RuntimeError, match=a10_perfis.SERVICO_NAO_SUBIU) as recusa:
        a10_perfis.ativar(_ctx(PARADO), {"texto": "Ativar"}, ponte)
    assert ponte.chamadas == [], ponte.chamadas
    razao = a10_perfis.pacote(_ctx(PARADO))[a10_perfis.CAMPO_DA_RAZAO_DO_ATIVAR]
    assert razao == str(recusa.value) and "Failed to start unit." in razao, razao
    assert a10_perfis.pacote(_ctx(DE_PE))[a10_perfis.CAMPO_DA_RAZAO_DO_ATIVAR] == ""


def test_o_servico_que_sobe_e_cala_diz_por_que(
    monkeypatch: pytest.MonkeyPatch, _mesa: list[str],
) -> None:
    """Ligou e não respondeu à troca: a frase diz o que fazer, e não «não confirmou»."""
    _servico_que_sobe(monkeypatch, _mesa)
    a10_perfis._ESCOLHIDO = "Ação"
    with pytest.raises(RuntimeError, match=a10_perfis.SERVICO_NAO_RESPONDEU):
        a10_perfis.ativar(_ctx(PARADO), {"texto": "Ativar"}, PonteDeMentira(cala=True))
    razao = a10_perfis.pacote(_ctx(PARADO))[a10_perfis.CAMPO_DA_RAZAO_DO_ATIVAR]
    assert razao == a10_perfis.SERVICO_NAO_RESPONDEU


def _acesos(state: dict[str, Any]) -> int:
    pacote = a10_perfis.pacote(_ctx(state))
    assert "blocos" in pacote, pacote
    return str(pacote["blocos"][a10_perfis.SELETOR_DA_LISTA]).count('class="ativo"')


def test_com_o_servico_parado_nada_esta_em_uso_na_tela() -> None:
    """O topo diz «—» e a lista não acende linha; de pé, os dois nomeiam o perfil."""
    assert topo(_ctx(PARADO))["perfil"] == "—"
    assert _acesos(PARADO) == 0
    assert topo(_ctx(DE_PE))["perfil"] == "meu_perfil"
    assert _acesos(DE_PE) == 1


class JanelaDeMentira:
    """O dublê de `DaemonActionsMixin`: guarda o que TERIA ido ao systemd."""

    _user_stopped_daemon: bool | None = None

    def __init__(self) -> None:
        self.comandos: list[list[str]] = []

    def _daemon_status(self) -> str:
        return "online_systemd"

    def _systemctl_status_text(self, unit: str) -> str:
        return "● unidade ativa"

    def _is_service_active(self) -> str:
        return "active"

    def _daemon_pid_alive(self) -> bool:
        return False

    def _invoke_systemctl(self, args: Any, capture: bool = False, check: bool = False) -> Any:
        self.comandos.append(list(args))
        return SimpleNamespace(returncode=0, stderr="")


def _janela_traz(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Abre a janela com o fio síncrono e diz se ela tentou ligar o serviço."""
    tentou: list[str] = []

    def _ligar() -> bool:
        tentou.append("ligar")
        return False

    monkeypatch.setattr(a09_sistema, "ativar_o_servico", _ligar)
    monkeypatch.setattr(fios, "soltar", lambda _nome, alvo, *a: alvo(*a))
    abrir.trazer_o_servico()
    return tentou


def test_o_parar_da_aba_sistema_segura_o_servico_parado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O Parar em dois cliques deixa a marca, e a janela reaberta não liga o serviço."""
    janela = JanelaDeMentira()
    monkeypatch.setattr(a09_sistema, "_JANELA_ANTIGA", [janela])
    monkeypatch.setattr(a09_sistema, "_autostart", lambda: "enabled")
    monkeypatch.setattr(a09_sistema, "_PAINEL", [None])
    monkeypatch.setattr(a09_sistema, "_LENTO", {})
    monkeypatch.setattr(a09_sistema, "_LENTO_EM_VOO", [False])
    a09_sistema._ARMADO.clear()
    ctx = _ctx({"paused": False, "controllers": []})
    a09_sistema.desligar(ctx, {"texto": a09_sistema._rotulo_do_desenho(a09_sistema.DESLIGAR)},
                         None)
    a09_sistema.desligar(ctx, {"texto": a09_sistema.CONFIRMA}, None)
    assert ["stop"] in [c[:1] for c in janela.comandos], janela.comandos
    assert abrir.marca_do_parar().exists()
    assert _janela_traz(monkeypatch) == []
    a09_sistema._ARMADO.clear()


def test_o_sair_da_bandeja_deixa_a_janela_trazer_o_servico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O «Sair» tira a marca (é o caso das 20:17); o «Parar o serviço» da bandeja a põe."""
    from hefesto_dualsense4unix.app import ipc_bridge, tray

    monkeypatch.setattr(ipc_bridge, "run_in_thread", lambda ato, ok, _erro: ok(ato()))
    pedidos: list[str] = []
    def _servico(verbo: str) -> bool:
        pedidos.append(verbo)
        return True

    bandeja = SimpleNamespace(on_servico=_servico,
                              on_quit=lambda: pedidos.append("fechou"),
                              _fora_do_fio=lambda ato, *_a, **_k: ato())
    tray.AppTray._mexer_no_servico(bandeja, "stop")
    assert abrir.marca_do_parar().exists()
    tray.AppTray._ao_sair(bandeja)
    assert pedidos == ["stop", "stop", "fechou"], pedidos
    assert not abrir.marca_do_parar().exists()
    assert _janela_traz(monkeypatch) == ["ligar"]
