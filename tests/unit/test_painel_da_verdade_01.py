"""PAINEL-DA-VERDADE-01 — a aba Status diz o que CHEGA ao jogo.

O requisito dela, literal: *"naquela aba de Status podemos ver o funcionamento
de tudo, e o funcionamento de lá obviamente impacta o funcionamento real do
controle na hora de jogar"*.

Até esta leva a aba mostrava que o sensor EXISTE, não que ele CHEGA. E os
contadores que o daemon publicava eram todos CUMULATIVOS — um painel sobre
eles diria "já funcionou uma vez" e ficaria verde para sempre depois do
primeiro acerto.

**A honestidade que estes testes protegem.** Nenhuma frase da tela pode
afirmar que o JOGO consumiu o dado: isso depende de qual biblioteca o jogo
carregou, e a medição de 01/08 é a prova de que o erro é fácil — a `libSDL2`
2.30.0 do Ubuntu não enumerava o gamepad virtual e a SDL3 3.4.10 que a Steam
distribui enumerava por completo. Há um teste só para esse vocabulário.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import (
    ATIVIDADE_FRESCA_S,
    SITUACAO_CHEGANDO,
    SITUACAO_IMPOSSIVEL,
    SITUACAO_NATIVO,
    SITUACAO_NUNCA,
    SITUACAO_PARADO,
    estado_do_recurso,
    resumo_do_que_chega_ao_jogo,
)

_PRIMARIO: dict[str, Any] = {"is_primary": True, "player": None}


def _estado(visto: dict[str, float] | None = None, **extra: Any) -> dict[str, Any]:
    """Um `state_full` com o vpad do jogador 1 vivo."""
    vpad: dict[str, Any] = {"player": 1, "visto_ha_s": dict(visto or {})}
    vpad.update(extra)
    return {"rumble_ff": {"per_vpad": [vpad]}}


# ---------------------------------------------------------------------------
# E1 — o vpad ganha recência, e não só contagem
# ---------------------------------------------------------------------------


class _Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avancar(self, s: float) -> None:
        self.t += s


def _vpad_de_bancada() -> Any:
    """Um vpad com os campos de estado que o carimbo usa, e nada mais.

    Sem fd e sem sinks: o que se afere aqui é o CARIMBO, e um device de
    verdade traria ruído de ciclo de vida que outro arquivo já cobre.
    """
    from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid

    class _Bancada(uhid.UhidDualSense):  # type: ignore[misc]
        def __init__(self, relogio: _Relogio) -> None:
            self.time_fn = relogio
            self.player = 1
            self._visto_em = {}
            self._trigger_replicas = 0
            self._lightbar_replicas = 0
            self._player_led_replicas = 0
            self._game_dirty = False
            self.trigger_sink = None
            self.lightbar_sink = None
            self.player_led_sink = None

    return _Bancada


def test_o_vpad_carimba_a_categoria_e_a_idade_envelhece() -> None:
    """O carimbo diz HÁ QUANTO TEMPO, e a categoria ausente diz "nunca".

    As duas coisas são a entrega da E1. A ausência é informação: "o jogo ainda
    não pediu" e "o jogo pediu e parou" levam a ações diferentes de quem lê a
    tela, e publicar 0.0 (ou um número gigante) para o caso nunca-aconteceu
    apagaria a diferença.

    Mordida: fazer `visto_ha_s` devolver `{cat: 0.0}` para toda categoria
    conhecida. A primeira asserção cai.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        ATIVIDADE_LIGHTBAR,
        ATIVIDADE_TRIGGER,
    )

    relogio = _Relogio()
    vpad = _vpad_de_bancada()(relogio)

    assert vpad.visto_ha_s == {}, "vpad recém-nascido não viu nada"

    vpad._carimbar(ATIVIDADE_TRIGGER)
    assert vpad.visto_ha_s == {ATIVIDADE_TRIGGER: 0.0}
    assert ATIVIDADE_LIGHTBAR not in vpad.visto_ha_s, (
        "categoria que nunca aconteceu tem de ficar AUSENTE, não zerada"
    )

    relogio.avancar(7.5)
    assert vpad.visto_ha_s[ATIVIDADE_TRIGGER] == 7.5, "a idade tem de envelhecer"

    vpad._carimbar(ATIVIDADE_TRIGGER)
    assert vpad.visto_ha_s[ATIVIDADE_TRIGGER] == 0.0, "e rejuvenescer no evento"


def test_categoria_sem_sink_nao_e_carimbada() -> None:
    """Réplica sem sink não chegou a lugar nenhum — e não pode dizer que sim.

    O `_forward_replica` sai por `return` quando o sink da categoria é `None`
    (é o caso de um controle sem gatilho conectado, por exemplo). Carimbar
    antes desse guarda faria a tela dizer "o gatilho está chegando" para um
    caminho que termina em nada.

    Mordida: mover o `_carimbar` para o topo do `_forward_replica`, antes dos
    guardas de sink — que é onde ele "naturalmente" iria.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import ATIVIDADE_TRIGGER

    relogio = _Relogio()
    vpad = _vpad_de_bancada()(relogio)
    vpad.trigger_sink = None

    vpad._forward_replica("trigger_right", b"\x00" * 11, primeira=True)

    assert ATIVIDADE_TRIGGER not in vpad.visto_ha_s
    assert vpad.trigger_replicas == 0

    recebido: list[Any] = []
    vpad.trigger_sink = lambda lado, valor: recebido.append((lado, valor))
    vpad._forward_replica("trigger_right", b"\x00" * 11, primeira=False)

    assert recebido, "com sink, a réplica sai"
    assert vpad.visto_ha_s[ATIVIDADE_TRIGGER] == 0.0


def test_o_daemon_publica_o_carimbo_e_sobrevive_a_vpad_sem_ele() -> None:
    """O `state_full` nunca pode morrer por causa de uma linha de telemetria.

    O vpad pode ser um `uinput` (que não tem hidraw e não tem o que carimbar)
    ou um dublê. O saneador devolve `{}` nesses casos, e descarta valores
    não-numéricos — o payload vira JSON, e um valor exótico aqui derrubaria a
    serialização inteira por causa do campo menos importante dela.

    Mordida: trocar o `_visto_ha_s` por `vp.visto_ha_s` direto no
    `ipc_handlers`. As duas últimas asserções levantam AttributeError.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import _visto_ha_s

    class _ComCarimbo:
        visto_ha_s: ClassVar[dict[str, Any]] = {
            "rumble": 0.5,
            "lightbar": 3.0,
            "lixo": "agora",
        }

    class _SemCarimbo:
        pass

    assert _visto_ha_s(_ComCarimbo()) == {"rumble": 0.5, "lightbar": 3.0}
    assert _visto_ha_s(_SemCarimbo()) == {}
    assert _visto_ha_s(None) == {}


# ---------------------------------------------------------------------------
# E2 — a frase que responde "vai funcionar na hora de jogar?"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("idade", "esperado"),
    [
        (0.0, SITUACAO_CHEGANDO),
        (ATIVIDADE_FRESCA_S, SITUACAO_CHEGANDO),
        (ATIVIDADE_FRESCA_S + 0.1, SITUACAO_PARADO),
        (999.0, SITUACAO_PARADO),
        (None, SITUACAO_NUNCA),
    ],
)
def test_a_idade_do_carimbo_decide_a_situacao(idade: Any, esperado: str) -> None:
    """A fronteira entre "chegando" e "parou" é o teto de frescor, e é inclusiva.

    3,0 s não é número redondo por acaso: é o mesmo teto do
    `_RUMBLE_STALE_SEC` do vpad, e existe porque estas categorias são eventos
    ESPARSOS — um jogo manda um efeito de gatilho quando a arma muda, não a
    cada quadro. Um teto curto faria a tela piscar entre "chegando" e "parou"
    no meio de uma partida.

    Mordida: trocar o `<=` por `<`. O caso exato do teto cai.
    """
    visto = {} if idade is None else {"rumble": idade}
    estado = estado_do_recurso("vibracao", _PRIMARIO, _estado(visto))

    assert estado is not None
    assert estado.situacao == esperado


def test_modo_nativo_nao_finge_que_ha_gamepad_virtual() -> None:
    """Em Nativo não existe vpad: o jogo abre o hidraw do controle FÍSICO.

    Perguntar "chegou ao gamepad virtual?" ali não faz sentido, e responder
    "não" seria mentira — em Nativo tudo chega, não porque nós entregamos, mas
    porque não há intermediário. É a primeira pergunta da função, antes de
    qualquer outra.

    Mordida: mover o teste de `native_mode` para depois da consulta ao vpad. A
    frase vira `None` (não há `per_vpad` em Nativo) e a aba fica muda no modo
    que ela usa para jogar os jogos da Sony.
    """
    estado = estado_do_recurso("giroscopio", _PRIMARIO, {"native_mode": True})
    assert estado is not None
    assert estado.situacao == SITUACAO_NATIVO

    frase = resumo_do_que_chega_ao_jogo(_PRIMARIO, {"native_mode": True})
    assert frase is not None
    assert "direto com o controle" in frase


def test_a_mascara_xbox_explica_em_vez_de_parecer_quebrada() -> None:
    """O estado que faltava, e o mais valioso dos quatro.

    Com máscara Xbox o card mostra giroscópio e touchpad desenhados e sem
    tráfego — indistinguível de "está quebrado". O que houve é outra coisa: a
    API do controle de Xbox **não tem** esses dois sensores, o `virtual_pad`
    recusa o backend uhid para todo sabor que não seja `dualsense`, e o vpad
    uinput declara 8 eixos e 11 botões. Não há onde eles caberem.

    Isto é o requisito dela do lado da tela: *"ao deixar o mouse sobre a opção
    Xbox, ele falaria que o Xbox não tem tais features"*. Seis dos oito perfis
    dela usam essa máscara, por decisão dela — a tela tem de explicar, não
    corrigir.

    Mordida: apagar `RECURSOS_SEM_MASCARA_XBOX`. Os dois viram "sem pedido
    ainda", que é a frase que faz o card parecer quebrado.
    """
    xbox = {"gamepad_emulation": {"flavor": "xbox"}, **_estado({})}

    for recurso in ("giroscopio", "touchpad"):
        estado = estado_do_recurso(recurso, _PRIMARIO, xbox)
        assert estado is not None, recurso
        assert estado.situacao == SITUACAO_IMPOSSIVEL, recurso
        assert "Xbox" in estado.frase, recurso

    # A vibração NÃO é afetada: ela existe na API do Xbox, e dizer o contrário
    # seria assustar sem motivo.
    vibra = estado_do_recurso("vibracao", _PRIMARIO, xbox)
    assert vibra is not None
    assert vibra.situacao != SITUACAO_IMPOSSIVEL

    frase = resumo_do_que_chega_ao_jogo(_PRIMARIO, xbox)
    assert frase is not None
    assert "não chegam ao jogo" in frase
    assert "Vibração" in frase, "o que continua funcionando também tem de ser dito"


def test_sem_vpad_a_linha_some_em_vez_de_acusar() -> None:
    """Sem gamepad virtual não há caminho — e não há o que afirmar.

    `None` deixa a linha fora da tela. A alternativa (dizer "nada chega")
    seria alarme crônico: o Modo "Controlar o PC" não tem vpad por design, e
    acusar ali seria ruído em cima de um estado normal.

    Mordida: trocar o `return None` por uma frase de erro.
    """
    assert resumo_do_que_chega_ao_jogo(_PRIMARIO, {}) is None
    assert resumo_do_que_chega_ao_jogo(_PRIMARIO, {"rumble_ff": {}}) is None


def test_a_frase_separa_chegando_de_parado_de_nunca() -> None:
    """As três situações aparecem juntas, cada uma com o seu grupo.

    É o caso comum no meio de uma partida: algumas coisas com tráfego, outras
    que já tiveram, outras que o jogo nunca pediu.

    A asserção é de IGUALDADE, e não por trecho. A primeira versão deste teste
    casava substrings e não mordia: com "parou" e "sem pedido" fundidos num
    grupo só, a frase saía com os recursos REPETIDOS nos dois grupos e todos
    os `in frase` continuavam verdadeiros. A função é pura e a entrada é
    determinística — aqui a frase inteira é o contrato.

    Mordida: juntar "parou" com "sem pedido ainda" num grupo só. A distinção
    que a sprint chama de mais valiosa desaparece.
    """
    estado = _estado(
        {"rumble": 0.2, "trigger": 40.0},
        motion_streaming=True,
        motion_hz=194.0,
    )
    frase = resumo_do_que_chega_ao_jogo(_PRIMARIO, estado)

    # SOM-DO-JOGO-NA-LINHA-01 (09/08/2026, decisão dela: *"sim, na linha de
    # recursos do card"*): o alto-falante é o SEXTO recurso da lista desde
    # hoje. A frase inteira continua sendo o contrato — só que agora ela tem
    # mais um nome, e este teste é o lugar onde isso fica registrado.
    assert frase == (
        "No jogo agora: giroscópio (~194 Hz), vibração · "
        "pararam: gatilho · "
        "sem pedido ainda: luz, clique do touchpad, som do controle."
    )
    # E cada recurso aparece UMA vez na frase — a ordem dos grupos pode mudar,
    # a repetição não pode voltar.
    for nome in (
        "giroscópio",
        "vibração",
        "gatilho",
        "luz",
        "clique do touchpad",
        "som do controle",
    ):
        assert frase.count(nome) == 1, f"{nome!r} aparece mais de uma vez"


def test_a_frase_nunca_afirma_que_o_jogo_recebeu() -> None:
    """O vocabulário proibido, e a razão pela qual ele é proibido.

    O daemon sabe que o dado saiu daqui e que alguém escreveu de volta no
    gamepad virtual. Ele NÃO sabe se o jogo consumiu — isso depende de qual
    biblioteca o jogo carregou, e a medição de 01/08 mostrou o tamanho do
    erro: contra a `libSDL2` 2.30.0 do Ubuntu o gamepad virtual não aparecia,
    e contra a SDL3 3.4.10 que a Steam distribui ele aparece inteiro
    (`054c:0df2 /dev/hidraw5`). Essa confusão produziu um diagnóstico errado
    nesta casa que quase virou trabalho grande sobre premissa falsa.

    Mordida: trocar "No jogo agora" por "O jogo recebeu".
    """
    proibidas = ("o jogo recebeu", "o jogo está recebendo", "confirmado pelo jogo")
    estados = [
        _estado({"rumble": 0.1, "trigger": 0.1, "lightbar": 0.1}),
        _estado({}),
        {"native_mode": True},
        {"gamepad_emulation": {"flavor": "xbox"}, **_estado({})},
    ]
    for estado in estados:
        frase = resumo_do_que_chega_ao_jogo(_PRIMARIO, estado)
        if frase is None:
            continue
        baixa = frase.lower()
        for proibida in proibidas:
            assert proibida not in baixa, (
                f"a frase {frase!r} afirma consumo pelo jogo, que o daemon "
                "não tem como saber"
            )


def test_o_secundario_sem_vpad_proprio_nao_herda_a_linha_do_primario() -> None:
    """GYRO-03-FIX, mantido: jogador 1 sem `is_primary` nunca casa com o vpad.

    Fora do co-op, `resolve_player_numbers` numera TODOS os conectados como
    jogador 1 — é o que o jogo vê. Mas o espelho do vpad P1 lê só o hidraw do
    PRIMÁRIO. Mostrar a linha num secundário seria telemetria mentindo, e o
    casamento tem um dono único (`_item_do_vpad`) exatamente para os
    dois consumidores não divergirem.

    Mordida: apagar o guarda de `is_primary` do `_item_do_vpad`.
    """
    secundario = {"is_primary": False, "player": 1}
    estado = _estado({"rumble": 0.1})

    assert resumo_do_que_chega_ao_jogo(secundario, estado) is None
