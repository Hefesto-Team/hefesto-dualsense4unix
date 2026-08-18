"""O que a aba Rumble PRECISA dizer, e antes de 11/08/2026 não dizia.

Dois silêncios, os dois medidos:

1. **O deslizador que apagava os quatro botões sem uma palavra.** Mover a
   "Intensidade global" para fora dos degraus vira um ajuste dela e desmarca
   os quatro — e o handler não falava na barra de estado, ao contrário do irmão
   (o clique num botão, que sempre falou). A palavra "personalizado" não existe
   em lugar nenhum da tela, então ela ficava olhando quatro botões apagados sem
   saber que tinha escolhido algo, nem o quê.

2. **A intensidade que não alcança jogo nenhum.** No journal da máquina dela:
   `launch_env_materializado ... backends=[] emulacao=False mascara=dualsense
   native=False`. Sem gamepad virtual **e** sem Conexão Nativa (Sony), o
   multiplicador dos quatro botões não age sobre a vibração do jogo — ele mora
   no caminho de saída do gamepad virtual (`apply_game_rumble`, alcançado só
   pelo sink de `make_primary_rumble_sink`). A aba seguia mostrando
   Economia/Balanceado/Máximo como se valessem.

A escada em si (30/100/150), a saturação em 255 e os textos do `.glade` estão
em `test_politica_de_vibracao_a_escada_que_amplifica.py`, que NÃO importa GTK —
aquelas provas não podem afundar num skip por falta de PyGObject.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: no TOPO do arquivo, antes de qualquer import de `gi`. O
# módulo sob teste (`app.actions.rumble_actions`) importa `gi` na primeira
# linha, então não há como exercitá-lo contra widget de mentira sem que o
# arquivo inteiro passe a rodar verde fora do job gtk-real.
exigir_gi_real("aba Rumble: a voz do deslizador e o aviso de alcance")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import rumble_actions
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    sem_dono_do_rumble,
)


def test_a_tela_oferece_exatamente_a_escada_que_o_daemon_aplica() -> None:
    """A tabela da aba deriva da do daemon — não é cópia que possa divergir.

    Quem multiplica de verdade é o daemon; se a tela oferecer um degrau que ele
    não aplique, ela mente por construção. `auto` é o único extra, e não é mult
    fixo: é só onde o deslizador para.
    """
    da_tela = dict(rumble_actions._POLICY_MULT)
    assert da_tela.pop("auto") == pytest.approx(1.0)
    assert da_tela == RUMBLE_POLICY_MULT


def test_o_padrao_de_desempate_nao_e_mais_ancora_morta() -> None:
    """Era o literal 0,7 em quatro lugares — um degrau que deixou de existir."""
    padrao = rumble_actions._MULT_PADRAO
    assert padrao == RUMBLE_POLICY_MULT["balanceado"]


# ---------------------------------------------------------------------------
# Dublês de widget
# ---------------------------------------------------------------------------


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = float(v)


class _FakeToggle:
    def __init__(self, active: bool = False) -> None:
        self._active = active

    def get_active(self) -> bool:
        return self._active

    def set_active(self, v: bool) -> None:
        self._active = bool(v)


class _FakeLabel:
    def __init__(self) -> None:
        self.visivel = False
        self.texto = ""

    def set_visible(self, v: bool) -> None:
        self.visivel = bool(v)

    def get_visible(self) -> bool:
        return self.visivel

    def set_text(self, t: str) -> None:
        self.texto = t

    def set_markup(self, t: str) -> None:
        self.texto = t


class _FakeBarra:
    def __init__(self) -> None:
        self.mensagens: list[str] = []

    def get_context_id(self, _key: str) -> int:
        return 1

    def pop(self, _ctx: int) -> None:
        if self.mensagens:
            self.mensagens.pop()

    def push(self, _ctx: int, msg: str) -> None:
        self.mensagens.append(msg)


class _Aba(rumble_actions.RumbleActionsMixin):
    """A aba Rumble por composição — só os widgets que estes testes tocam."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._rumble_guard_refresh = False
        self._rumble_policy = "balanceado"
        self._rumble_test_source = None
        self._widgets: dict[str, Any] = {
            "rumble_policy_economia": _FakeToggle(),
            "rumble_policy_balanceado": _FakeToggle(active=True),
            "rumble_policy_max": _FakeToggle(),
            "rumble_policy_auto": _FakeToggle(),
            "rumble_policy_slider": _FakeScale(100.0),
            "rumble_policy_auto_label": _FakeLabel(),
            "rumble_policy_aviso": _FakeLabel(),
            "rumble_state_label": _FakeLabel(),
            "status_bar": _FakeBarra(),
        }

    def _get(self, key: str) -> Any:  # type: ignore[override]
        return self._widgets.get(key)


@pytest.fixture
def aba(monkeypatch: pytest.MonkeyPatch) -> _Aba:
    enviados: list[float] = []
    monkeypatch.setattr(
        rumble_actions,
        "rumble_policy_custom",
        lambda mult: (enviados.append(mult), True)[1],
    )
    monkeypatch.setattr(
        rumble_actions,
        "rumble_policy_set_checked",
        lambda policy, timeout=None: (True, None),
    )
    instancia = _Aba()
    instancia.enviados = enviados  # type: ignore[attr-defined]
    return instancia


# ---------------------------------------------------------------------------
# 1 — o deslizador que ficava mudo
# ---------------------------------------------------------------------------


def test_sair_dos_degraus_avisa_na_barra_de_estado(aba: _Aba) -> None:
    barra: _FakeBarra = aba._widgets["status_bar"]
    slider: _FakeScale = aba._widgets["rumble_policy_slider"]
    slider.set_value(145.0)
    aba.on_rumble_policy_slider_changed(slider)

    assert aba._rumble_policy == "custom"
    for pid in (
        "rumble_policy_economia",
        "rumble_policy_balanceado",
        "rumble_policy_max",
        "rumble_policy_auto",
    ):
        assert aba._widgets[pid].get_active() is False
    assert barra.mensagens, "o deslizador continuou mudo ao apagar os 4 botões"
    assert "145%" in barra.mensagens[-1]
    assert "Intensidade da vibração" in barra.mensagens[-1], (
        "a frase tem de ser a MESMA do clique num botão"
    )


def test_o_deslizador_vai_alem_dos_botoes_e_o_daemon_aceita(aba: _Aba) -> None:
    """A faixa acima do "Máximo" é usável de ponta a ponta.

    Decisão dela, 11/08/2026: o botão "Máximo" para em 150% (preset seguro) e o
    deslizador segue até 200% (ajuste livre de quem aceita o preço). Este teste
    guarda as duas metades — que o 200% CHEGA ao daemon, e que ele chega como
    ajuste livre, sem se disfarçar de botão.
    """
    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    slider: _FakeScale = aba._widgets["rumble_policy_slider"]
    fim_do_curso = RUMBLE_CUSTOM_MULT_MAX * 100
    slider.set_value(fim_do_curso)
    aba.on_rumble_policy_slider_changed(slider)

    assert aba._rumble_policy == "custom", (
        "o fim do curso do deslizador não é degrau de botão nenhum"
    )
    esperado = pytest.approx(RUMBLE_CUSTOM_MULT_MAX)
    assert aba.enviados[-1] == esperado  # type: ignore[attr-defined]

    # E o degrau do "Máximo" continua afundando o BOTÃO, não virando ajuste.
    slider.set_value(RUMBLE_POLICY_MULT["max"] * 100)
    aba.on_rumble_policy_slider_changed(slider)
    assert aba._rumble_policy == "max"


# ---------------------------------------------------------------------------
# 2 — a intensidade que não alcança
# ---------------------------------------------------------------------------


def test_sem_gamepad_virtual_a_tela_diz_que_a_intensidade_nao_alcanca() -> None:
    texto = rumble_actions.texto_do_alcance_da_intensidade(
        {"rumble_ff": {"vpads": 0}, "native_mode": False}
    )
    assert texto is not None, (
        "o quadro medido na máquina dela (sem gamepad virtual e sem Nativo) "
        "não pode ser silêncio: a tela seguia oferecendo os quatro botões"
    )
    assert "não está chegando" in texto
    assert "Jogar pelo Hefesto" in texto, "a frase tem de dizer o gesto que cura"
    assert "aqui embaixo" in texto, (
        "sem dizer o que a intensidade AINDA faz, o aviso vira 'não serve para "
        "nada' — que é falso: ela vale para a vibração fixada"
    )


def test_no_nativo_a_frase_e_outra() -> None:
    """Ali não há defeito nenhum: é o modo funcionando como deve.

    Mandá-la mexer na aba Início seria mandá-la consertar o que está certo.
    """
    texto = rumble_actions.texto_do_alcance_da_intensidade(
        {"rumble_ff": {"vpads": 0}, "native_mode": True}
    )
    assert texto is not None
    assert "Conexão Nativa (Sony)" in texto
    assert "Jogar pelo Hefesto" not in texto


@pytest.mark.parametrize(
    ("native", "vpads"),
    [(False, 0), (True, 0), (False, 2), (True, 2)],
)
def test_a_tela_e_o_journal_usam_um_criterio_so(native: bool, vpads: int) -> None:
    """A tabela-verdade inteira, comparada contra o predicado do daemon.

    Por algumas horas em 11/08/2026 houve dois critérios paralelos para o mesmo
    buraco: a borda de materialização olhava `backends` (e gritava
    `rumble_sem_dono` no journal) e esta tela olhava `rumble_ff.vpads`. Dois
    critérios para o mesmo fato divergem na primeira mudança — é a classe de
    defeito que o HARM-19 já pagou no teto do multiplicador.

    A MORDIDA: faça a tela decidir sozinha de novo (troque a chamada de
    `sem_dono_do_rumble` por um `if not native` qualquer) e o dia em que o
    predicado mudar de forma, esta comparação reprova.
    """
    estado = {"rumble_ff": {"vpads": vpads}, "native_mode": native}
    texto = rumble_actions.texto_do_alcance_da_intensidade(estado)
    e_o_quadrante = sem_dono_do_rumble(
        native=native, backends=("vpad",) * vpads
    )
    disse_defeito = texto is not None and "não está chegando" in texto
    assert disse_defeito is e_o_quadrante, (
        "a tela e o journal discordaram sobre o mesmo quadrante"
    )


def test_com_gamepad_virtual_nao_ha_aviso() -> None:
    assert (
        rumble_actions.texto_do_alcance_da_intensidade({"rumble_ff": {"vpads": 2}})
        is None
    )


@pytest.mark.parametrize(
    "estado",
    [
        {},
        {"rumble_ff": {}},
        {"rumble_ff": {"vpads": None}},
        {"rumble_ff": {"vpads": True}},
        {"rumble_ff": "sei lá"},
    ],
)
def test_sem_o_dado_a_tela_nao_inventa_defeito(estado: dict[str, Any]) -> None:
    """"Não sei" e "não alcança" mandam caçar em lugares opostos.

    Daemon mais velho, resposta que não chegou: a linha fica calada. É a mesma
    disciplina de `texto_dos_pedidos_de_vibracao`, e `bool` é `int` em Python —
    daí o caso `vpads: True`.
    """
    assert rumble_actions.texto_do_alcance_da_intensidade(estado) is None


def test_o_aviso_aparece_e_some_no_widget(aba: _Aba) -> None:
    rotulo: _FakeLabel = aba._widgets["rumble_policy_aviso"]

    aba._update_rumble_state_label({"rumble_ff": {"vpads": 0}, "native_mode": False})
    assert rotulo.visivel is True
    assert "não está chegando" in rotulo.texto

    aba._update_rumble_state_label({"rumble_ff": {"vpads": 1}})
    assert rotulo.visivel is False
