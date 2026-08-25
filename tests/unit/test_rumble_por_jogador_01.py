"""As mordidas do caminho POR PEÇA da aba Rumble (RUM-11, 25/08/2026).

Até esta leva, o caminho por peça DA ABA não tinha uma linha de teste. Os dois
métodos que o fazem (``_rumble_edit_uniq``, ``_gravar_intensidade_no_rascunho``)
apareciam em ``tests/unit/test_rumble_actions.py`` **só na lista de composição do
dublê**, e o censo era literal::

    $ grep -rn "_edit_target_uniq" tests/ | grep -ci rumble    # 0

Os dois testes de ``with_controller_rumble`` que existiam
(``test_por_unidade_01_todas_as_abas.py``) exercitam o **modelo**, não a aba.

Quatro mordidas, uma por defeito medido:

1. **RUM-1** — com um controle escolhido no seletor, a aba grava no override
   daquela peça e manda ``rumble.policy_set`` **sem endereço**, que é da máquina
   inteira. A frase que confessa isso estava escrita desde 10/08 na docstring de
   ``_gravar_intensidade_no_rascunho`` e nunca chegou à tela;
2. **RUM-2** — ``rumble.set`` com o alvo apontado e FORA da mesa respondia
   ``ok`` tendo escrito zero byte. A metade "não escreveu" já é provada por
   ``tests/unit/test_p4_alvo_ausente_nao_vira_broadcast.py``; o que falta lá, e
   é o que este arquivo acrescenta, é a metade "e DIZ" — **a RESPOSTA**. Separar
   *"não fez"* de *"fez e não contou"* é o ponto inteiro da tarefa, e um teste
   que só conta bytes não separa os dois;
3. **RUM-3** — com uma peça escolhida, clicar "Auto" apaga o override dela
   (``with_controller_rumble`` limpa, e a regra está certa: o esquema recusa
   ``auto`` por unidade porque ele escala pela bateria do controle PRINCIPAL).
   O toast dizia só *"Intensidade da vibração: Auto"* — indistinguível do caso
   "Todos", com o ajuste da peça apagado em silêncio;
4. **RUM-9** — a linha de pedidos somava os quatro jogadores. *"O jogo pediu
   vibração 40x"* com o Jogador 2 mudo é verdade sobre a mesa e mentira sobre
   quem reclamou.

**Por que os quatro num arquivo só, sendo que a 2 não precisa de GTK.** A RUM-11
nomeia UM arquivo, e o motivo é que as quatro mordidas descrevem UM gesto — o
clique com uma peça no seletor — da tela ao daemon. O preço é declarado: a
mordida 2 herda a guarda de `gi` real e só roda no job `gtk-real`. A prova de
que ela **não escreve** não paga esse preço, porque mora no `test_p4`, que não
importa `gi`.

**Endereços:** faixa sintética ``02:fe:00`` da casa, nunca a ``aabbcc`` — foi a
`aabbcc` que vazou para o ``controllers.json`` VIVO dela em 23/08.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: no TOPO, antes de qualquer import de `gi`. O módulo sob
# teste (`app.actions.rumble_actions`) importa `gi` na primeira linha, e sem
# esta guarda o arquivo inteiro passaria verde contra widget de mentira.
exigir_gi_real("aba Rumble: o caminho por peça, da tela ao daemon")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import rumble_actions
from hefesto_dualsense4unix.app.draft_config import DraftConfig

#: A peça escolhida no seletor. Faixa sintética `02:fe:00` (CLAUDE.md), fora da
#: `aabbcc` que vazou para a mesa de produção dela em 23/08.
PECA = "02:fe:00:00:00:02"

#: A segunda peça, para a mordida por jogador não depender de uma só.
OUTRA_PECA = "02:fe:00:00:00:03"


# --- dublês de widget --------------------------------------------------


class _FakeToggle:
    def __init__(self, active: bool = False) -> None:
        self._active = bool(active)

    def get_active(self) -> bool:
        return self._active

    def set_active(self, v: bool) -> None:
        self._active = bool(v)


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = float(v)


class _FakeLabel:
    def __init__(self) -> None:
        self.texto = ""
        self.visivel = False

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

    @property
    def ultima(self) -> str:
        return self.mensagens[-1] if self.mensagens else ""


class _Aba(rumble_actions.RumbleActionsMixin):
    """A aba Rumble com os widgets que estas mordidas tocam.

    O ``rumble_policy_aviso`` é um ``Gtk.Label`` DE VERDADE dentro de uma
    ``Gtk.Box`` de verdade, e não um dublê: ``_rotulo_do_alcance_do_gesto``
    pendura o rótulo novo no PAI dele (``get_parent()`` + ``pack_start``), e um
    dublê sem pai faz a função devolver ``None`` — o teste ficaria verde por
    não ter onde escrever, que é o falso verde mais caro desta casa.
    """

    def __init__(self) -> None:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        self.draft = DraftConfig.default()
        self._rumble_guard_refresh = False
        self._rumble_policy = "balanceado"
        self._rumble_test_source = None
        # Z2-1: "Todos" precisa existir explicitamente; sem o atributo,
        # `alvo_de_edicao` devolve DESCONHECIDO e nada é escrito no rascunho.
        self._edit_target_uniq: str | None = None

        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        aviso = Gtk.Label(label="")
        self.caixa.pack_start(aviso, False, False, 0)

        self._widgets: dict[str, Any] = {
            "rumble_policy_economia": _FakeToggle(),
            "rumble_policy_balanceado": _FakeToggle(active=True),
            "rumble_policy_max": _FakeToggle(),
            "rumble_policy_auto": _FakeToggle(),
            "rumble_policy_slider": _FakeScale(100.0),
            "rumble_policy_auto_label": _FakeLabel(),
            "rumble_policy_aviso": aviso,
            "rumble_state_label": _FakeLabel(),
            "status_bar": _FakeBarra(),
        }

    def _get(self, key: str) -> Any:  # type: ignore[override]
        return self._widgets.get(key)

    # O rótulo de RUM-1 nasce em código; quem lê é este atalho.
    @property
    def linha_do_alcance(self) -> Any:
        return getattr(self, "_rumble_alcance_do_gesto_label", None)


@pytest.fixture
def aba(monkeypatch: pytest.MonkeyPatch) -> _Aba:
    """A aba com o IPC neutralizado — o daemon vivo não entra nesta bancada."""
    monkeypatch.setattr(
        rumble_actions,
        "rumble_policy_set_checked",
        lambda policy, timeout=None: (True, None),
    )
    monkeypatch.setattr(
        rumble_actions, "rumble_policy_custom", lambda mult: True
    )
    return _Aba()


# ===========================================================================
# Mordida 1 — RUM-1: a aba diz onde grava e onde manda
# ===========================================================================


def test_com_uma_peca_escolhida_a_aba_confessa_o_alcance(aba: _Aba) -> None:
    """Arranque a linha e a aba volta a afirmar o alvo calando o escopo.

    Régua: o texto lido do ``Gtk.Label`` depois da montagem — **não** OCR.
    """
    aba._edit_target_uniq = PECA
    aba._apply_policy_to_widgets("balanceado", 100.0)

    rotulo = aba.linha_do_alcance
    assert rotulo is not None, (
        "a aba montou com uma peça escolhida e não criou a linha de alcance — "
        "ela afirma o alvo três centímetros acima e cala que o comando vivo "
        "vai para a mesa inteira"
    )
    assert rotulo.get_visible() is True
    assert rotulo.get_text() == rumble_actions.TEXTO_ONDE_GRAVA_E_ONDE_MANDA


def test_com_todos_no_seletor_a_linha_nao_aparece(aba: _Aba) -> None:
    """Em "Todos" o que ela grava e o que ela manda são a mesma coisa.

    Um aviso permanente ali viraria ruído crônico — a mesma disciplina do
    ``texto_do_alcance_da_intensidade``, e o motivo de a frase ser condicional
    em vez de um rótulo fixo no Glade.
    """
    aba._edit_target_uniq = None
    aba._apply_policy_to_widgets("balanceado", 100.0)

    rotulo = aba.linha_do_alcance
    assert rotulo is None or rotulo.get_visible() is False, (
        "sem peça escolhida não há divergência a confessar, e a linha apareceu"
    )


def test_a_frase_nomeia_as_duas_metades_do_gesto(aba: _Aba) -> None:
    """A frase tem de dizer o AGORA e o SALVO — sem as duas ela não explica nada.

    Mordida de REDAÇÃO, e ela existe porque a mentira que RUM-1 cura não é a
    ausência de um rótulo: é a ausência da distinção. Um texto que diga só
    *"vale para todos"* deixa a usuária sem saber por que ela escolheu um
    controle no seletor.
    """
    frase = rumble_actions.TEXTO_ONDE_GRAVA_E_ONDE_MANDA
    assert "agora" in frase, "a metade do que ela OUVE sumiu da frase"
    assert "salvar" in frase, "a metade do que ela SALVA sumiu da frase"
    # §6 da sprint: nenhuma frase nova desta onda pode afirmar comportamento
    # POR TRANSPORTE — o rádio não está medido, e a aba responde pelo que o
    # produto MANDA, nunca pelo que o motor FAZ.
    for palavra in ("Bluetooth", "rádio", "cabo", "USB"):
        assert palavra.lower() not in frase.lower(), (
            f"a frase de alcance passou a falar de transporte ({palavra}) — "
            "a §6 da RUMBLE-POR-JOGADOR-01 proíbe: o rádio não está medido"
        )


# ===========================================================================
# Mordida 2 — RUM-2: mesa vazia deixa de comemorar
# ===========================================================================


@pytest.mark.asyncio
async def test_rumble_set_com_alvo_fora_da_mesa_responde_recusado() -> None:
    """A metade "e DIZ": a RESPOSTA, não a contagem de bytes.

    O ``test_p4_alvo_ausente_nao_vira_broadcast.py`` já prova que ninguém
    recebe motor. O que ele **não** prova — e o que manda a aba comemorar — é o
    ``{"status": "ok"}`` que o handler devolvia mesmo assim: o toast dizia
    *"Vibração travada (fraca=160, forte=220)"* com zero byte escrito.

    Arrancar a consulta a ``alvo_de_output_ausente`` faz o handler voltar a
    responder ``ok``, e é essa a diferença que morde.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.subsystems.rumble import (
        MOTIVO_ALVO_FORA_DA_MESA,
        RUMBLE_RECUSADO_ALVO_AUSENTE,
    )

    escritas: list[tuple[int, int]] = []

    class _Controle:
        def alvo_de_output_ausente(self) -> str | None:
            return PECA

        def set_rumble(self, weak: int = 0, strong: int = 0) -> None:
            escritas.append((weak, strong))

    class _Config:
        rumble_active: tuple[int, int] | None = None
        rumble_active_uniq: str | None = None
        rumble_policy = "balanceado"

    class _Daemon:
        config = _Config()

        def is_native_mode(self) -> bool:
            return False

    class _Store:
        def __init__(self) -> None:
            self.travas: list[str] = []

        def mark_manual_trigger_active(self, categoria: str) -> None:
            self.travas.append(categoria)

    class _Servidor:
        controller = _Controle()
        daemon = _Daemon()
        store = _Store()

    servidor = _Servidor()
    handler = IpcHandlersMixin._handle_rumble_set.__get__(servidor, _Servidor)
    resposta = await handler({"weak": 160, "strong": 220})

    assert resposta["status"] == "recusado", (
        "o alvo está apontado e fora da mesa: o handler escreveu zero byte e "
        "respondeu que aplicou. A aba comemora o que não aconteceu — é o "
        "falso verde que a BROADCAST-PROIBIDO-01 mediu"
    )
    assert resposta["desfecho"] == RUMBLE_RECUSADO_ALVO_AUSENTE
    assert resposta["motivo"] == MOTIVO_ALVO_FORA_DA_MESA
    # A recusa vem ANTES de qualquer escrita: nem o par armado (que desarmaria
    # a HARM-16), nem o handle do backend, nem a trava manual.
    assert escritas == []
    assert servidor.daemon.config.rumble_active is None
    assert servidor.store.travas == []


# ===========================================================================
# Mordida 3 — RUM-3: o "Auto" para de apagar em silêncio
# ===========================================================================


def test_auto_com_peca_escolhida_nomeia_o_apagamento(aba: _Aba) -> None:
    """Grava na peça, clica Auto, e o toast tem de NOMEAR o que sumiu.

    Sem a oração, o toast é *"Intensidade da vibração: Auto"* — a MESMA frase
    do caso "Todos" — e o ajuste próprio daquela peça foi apagado sem uma
    palavra.
    """
    aba._edit_target_uniq = PECA
    aba._gravar_intensidade_no_rascunho("max", None)
    assert aba.draft.controller_override(PECA) is not None, (
        "a bancada não conseguiu nem gravar o override — sem o ANTES não há "
        "apagamento a provar"
    )

    barra: _FakeBarra = aba._widgets["status_bar"]
    aba._set_policy("auto")

    assert rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL in barra.ultima, (
        "clicar Auto com uma peça escolhida apagou o ajuste dela e o toast "
        f"não disse uma palavra: {barra.ultima!r}"
    )
    # E o apagamento é real — a oração não pode virar promessa vazia.
    override = aba.draft.controller_override(PECA)
    assert override is None or getattr(override, "rumble", None) is None


def test_auto_com_todos_no_seletor_nao_fala_em_apagamento(aba: _Aba) -> None:
    """A oração é do gesto que APAGA — em "Todos" não há peça a devolver.

    A contra-classe da mordida acima: sem ela, um `True` constante passaria.
    """
    aba._edit_target_uniq = None
    barra: _FakeBarra = aba._widgets["status_bar"]
    aba._set_policy("auto")

    assert rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL not in barra.ultima
    assert "Auto" in barra.ultima


def test_max_com_peca_escolhida_nao_fala_em_apagamento(aba: _Aba) -> None:
    """A segunda contra-classe: um preset que GRAVA na peça não apaga nada.

    Sem ela, "toda escolha com peça no seletor avisa" passaria — e aí a frase
    viraria ruído em todo clique, que é o defeito oposto.
    """
    aba._edit_target_uniq = PECA
    aba._gravar_intensidade_no_rascunho("economia", None)
    barra: _FakeBarra = aba._widgets["status_bar"]
    aba._set_policy("max")

    assert rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL not in barra.ultima
    override = aba.draft.controller_override(PECA)
    assert override is not None and getattr(override, "rumble", None) is not None


# ===========================================================================
# Mordida 4 — RUM-9: o contador de pedidos, por jogador
# ===========================================================================


def _estado(per_vpad: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """Um ``state`` de ``daemon.state_full`` com só o que esta linha lê."""
    ff: dict[str, Any] = {
        "vpads": len(per_vpad),
        "plays": sum(int(i.get("ff_play_count", 0)) for i in per_vpad),
        "nao_nulos": sum(int(i.get("ff_nao_nulo_count", 0)) for i in per_vpad),
        "per_vpad": per_vpad,
    }
    ff.update(extra)
    return {"native_mode": False, "rumble_ff": ff}


def test_dois_jogadores_deixam_de_virar_um_numero_somado() -> None:
    """40x + 0x não é "o jogo pediu 40x" — é o Jogador 2 mudo.

    Somar manda caçar no lugar errado: a frase agregada é verdade sobre a mesa
    e mentira sobre quem reclamou.
    """
    texto = rumble_actions.texto_dos_pedidos_de_vibracao(
        _estado(
            [
                {"player": 1, "ff_play_count": 40, "ff_nao_nulo_count": 40},
                {"player": 2, "ff_play_count": 0, "ff_nao_nulo_count": 0},
            ]
        )
    )
    assert texto is not None
    assert "Jogador 1" in texto and "40x" in texto, (
        f"o jogador que recebeu vibração sumiu da linha: {texto!r}"
    )
    assert "Jogador 2" in texto and "nenhuma" in texto, (
        "os dois jogadores viraram um número somado, e quem reclamou não "
        f"aparece: {texto!r}"
    )


def test_a_ordem_e_a_do_jogador_nao_a_do_payload() -> None:
    """O payload não promete ordem; a tela promete. Ordenar é da tela."""
    texto = rumble_actions.texto_dos_pedidos_de_vibracao(
        _estado(
            [
                {"player": 3, "ff_play_count": 5, "ff_nao_nulo_count": 5},
                {"player": 1, "ff_play_count": 9, "ff_nao_nulo_count": 9},
            ]
        )
    )
    assert texto is not None
    assert texto.index("Jogador 1") < texto.index("Jogador 3")


def test_forca_zero_continua_separado_de_nao_falou_por_jogador() -> None:
    """As perguntas 5 e 6 do agregado sobrevivem inteiras dentro do escopo.

    "Falou e pediu zero" e "não falou" mandam caçar em lugares OPOSTOS — o
    primeiro é o jogo, o segundo é a nossa ponte. Fundi-los seria trocar a
    mentira da soma por outra.
    """
    texto = rumble_actions.texto_dos_pedidos_de_vibracao(
        _estado(
            [
                {"player": 1, "ff_play_count": 12, "ff_nao_nulo_count": 0},
                {"player": 2, "ff_play_count": 0, "ff_nao_nulo_count": 0},
            ]
        )
    )
    assert texto is not None
    assert "Jogador 1: 12x, todas com força zero" in texto
    assert "Jogador 2: nenhuma" in texto


def test_com_um_jogador_so_a_frase_e_byte_identica_a_de_sempre() -> None:
    """Quem joga sozinho não vê mudança nenhuma nesta leva.

    O contrato explícito da RUM-9, e a razão de ``_pedidos_por_jogador``
    devolver ``None`` com menos de dois jogadores em vez de escrever
    *"Jogador 1: 40x"* para quem tem um controle só.
    """
    um = _estado([{"player": 1, "ff_play_count": 40, "ff_nao_nulo_count": 40}])
    sem_lista = {
        "native_mode": False,
        "rumble_ff": {k: v for k, v in um["rumble_ff"].items() if k != "per_vpad"},
    }
    assert rumble_actions.texto_dos_pedidos_de_vibracao(
        um
    ) == rumble_actions.texto_dos_pedidos_de_vibracao(sem_lista)


def test_entrada_sem_o_contador_cai_para_a_soma_em_vez_de_mentir() -> None:
    """Daemon mais velho (ou vpad que não respondeu): "não sei" ≠ "nenhuma".

    A frase por jogador teria um buraco no meio, e um buraco lido como
    "nenhuma" manda caçar no lado errado. Somar perde granularidade; afirmar
    perderia a verdade.
    """
    texto = rumble_actions.texto_dos_pedidos_de_vibracao(
        _estado(
            [
                {"player": 1, "ff_play_count": 40, "ff_nao_nulo_count": 40},
                {"player": 2, "ff_play_count": 3},
            ],
            nao_nulos=40,
            plays=43,
        )
    )
    assert texto is not None
    assert "Jogador" not in texto, (
        "uma entrada sem `ff_nao_nulo_count` virou 'nenhuma' — o produto "
        f"afirmou o que não sabe: {texto!r}"
    )


def test_a_ordem_da_verdade_nao_mudou_o_descartado_vem_antes() -> None:
    """O escopo mudou; a ORDEM das perguntas, não.

    ``descartados`` é defeito NOSSO e vale para a mesa inteira — ele continua
    respondendo antes de qualquer resposta por jogador. Inverter a ordem
    mandaria a usuária caçar do lado dela um defeito que é do nosso.
    """
    texto = rumble_actions.texto_dos_pedidos_de_vibracao(
        _estado(
            [
                {"player": 1, "ff_play_count": 40, "ff_nao_nulo_count": 40},
                {"player": 2, "ff_play_count": 0, "ff_nao_nulo_count": 0},
            ],
            descartados=7,
        )
    )
    assert texto is not None
    assert "suporte" in texto and "Jogador" not in texto
