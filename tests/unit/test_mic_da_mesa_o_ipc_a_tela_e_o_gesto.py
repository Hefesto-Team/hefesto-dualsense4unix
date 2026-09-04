"""MIC-DA-MESA-ELEICAO-01 — o IPC da devolução, a tela na ausência, e o gesto.

Três réguas, três defeitos diferentes:

* **`mic.led.set`** é a porta de emergência da inversão. A devolução de posse
  por-byte já existia, já era testada e **não tinha um único chamador de
  produção** — tomada a posse do LED numa sessão, ela só caía quando o handle
  morresse. Confundir `false` com `null` foi o defeito do `3d9bb7e`, no byte
  vizinho; por isso a chave é obrigatória.

* **A tela não mente na ausência.** O byte de áudio é atributo de INSTÂNCIA do
  handle: no hotplug-out o handle morre, o novo nasce sem leitura e a chave
  `audio` SOME do `state_full`. `bool(None)` é `False`, que o selo pintava como
  ATIVO — o controle que acabou de cair anunciando que está no ar.

* **O gesto exige endereço.** Sem `uniq` não se elege "o primeiro": numa mesa
  de quatro isso elegeria sempre o mesmo.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import pytest


# ---------------------------------------------------------------------------
# 5 (IPC). A devolução DEVOLVE, e `null` não é `false`
# ---------------------------------------------------------------------------


class _ControllerFalso:
    def __init__(self) -> None:
        self.pedidos: list[tuple[Any, Any]] = []

    def set_microphone_led(self, aceso: bool | None, *, uniq: str | None = None) -> bool:
        self.pedidos.append((aceso, uniq))
        return True


class _Handlers:
    """O mixin de handlers com o mínimo que `mic.led.set` toca."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        self._mixin = IpcHandlersMixin
        self.controller = _ControllerFalso()

    async def chamar(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._mixin._handle_mic_led_set(self, params)  # type: ignore[arg-type]


def test_aceso_null_devolve_a_posse_ao_kernel() -> None:
    """`null` chega ao backend como `None` — nunca como `False`.

    CURA A ARRANCAR: fazer o handler tratar `null` como `False`. O bit de
    autorização continuaria ligado e o kernel nunca voltaria a mandar na luz.
    """
    h = _Handlers()
    r = asyncio.run(h.chamar({"aceso": None}))

    assert h.controller.pedidos == [(None, None)]
    assert r == {"status": "ok", "aceso": None}


def test_aceso_false_e_uma_ordem_e_continua_valendo() -> None:
    """A metade que prova que a régua não confunde os dois no outro sentido."""
    h = _Handlers()
    asyncio.run(h.chamar({"aceso": False, "uniq": "aabbcc000002"}))
    assert h.controller.pedidos == [(False, "aabbcc000002")]


def test_a_chave_omitida_levanta_erro_de_parametro() -> None:
    """No molde do `mic.set`: omitir a chave não pode virar um `False` calado.

    O `ValueError` vira `-32003` (CODE_INVALID_PARAMS) no dispatcher.
    """
    h = _Handlers()
    with pytest.raises(ValueError, match="obrigatório"):
        asyncio.run(h.chamar({}))
    assert h.controller.pedidos == []


def test_mic_led_set_esta_registrado_no_dispatcher() -> None:
    """O handler existir e não estar na tabela seria um método invisível."""
    import inspect

    from hefesto_dualsense4unix.daemon import ipc_server

    fonte = inspect.getsource(ipc_server)
    assert '"mic.led.set": self._handle_mic_led_set' in fonte


# ---------------------------------------------------------------------------
# 10. A tela não mente na AUSÊNCIA
# ---------------------------------------------------------------------------


def test_o_selo_pinta_desconhecido_quando_o_state_full_nao_traz_audio() -> None:
    """CURA A ARRANCAR: voltar `"MUDO" if mudo else "ATIVO"` sem o `sabemos`.

    Pinta ATIVO sobre um controle que acabou de cair — e, com a inversão, o
    plástico dele estaria dizendo "estou no ar".

    **Esta régua só morde porque o dublê parou de trazer o default falso**: com
    o `FALSO` de sempre, que sempre tem a chave `audio`, o caminho de "não sei"
    nunca era exercitado.
    """
    from hefesto_dualsense4unix.interface import casamento
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    class _Ctx:
        conectados: ClassVar[list[Any]] = [casamento.FALSO_SEM_AUDIO]
        mesa: ClassVar[list[Any]] = casamento.MESA_FALSA

    saida = a02_controles.pacote(_Ctx())  # type: ignore[arg-type]
    card = saida["cards"][casamento.FALSO["uniq"]]
    assert card["mic-selo"] == "—", "sem leitura, o selo diz NÃO SEI"


def test_o_selo_continua_dizendo_a_verdade_quando_ha_leitura() -> None:
    """A metade que prova que a cura não é "nunca mais mostra nada".

    **O SELO PASSOU A DIZER O ESTADO COMPOSTO — 04/09/2026, decisão [03] da
    ONDA2-02, pela D-12 dela.** ATIVO agora exige as QUATRO faces, e o
    `casamento.FALSO` traz UMA: `{"audio": {"mic_mudo": False}}`. Com só ela, a
    resposta certa é `—` (*"ainda não perguntamos ao canal"*) — e é o que o
    caso ACIMA já mede.

    ENTÃO ESTE CASO PASSOU A MONTAR AS QUATRO, no lugar de mexer no `FALSO`.
    O dublê compartilhado é a fixture de DEZ abas e a ONDA1-D1 já relatou que
    ele precisa crescer; encolher a decisão dela para caber num dublê velho
    seria o contrário do que esta casa faz. Enquanto ele não cresce, quem
    precisa de leitura completa a monta — e diz por quê.
    """
    from hefesto_dualsense4unix.interface import casamento
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    com_o_canal = {**casamento.FALSO,
                   "audio": {**(casamento.FALSO.get("audio") or {}),
                             "canal_ativo": True, "canal_mudo": False}}

    class _Ctx:
        conectados: ClassVar[list[Any]] = [com_o_canal]
        mesa: ClassVar[list[Any]] = casamento.MESA_FALSA

    saida = a02_controles.pacote(_Ctx())  # type: ignore[arg-type]
    assert saida["cards"][casamento.FALSO["uniq"]]["mic-selo"] == "ATIVO"


def test_o_dublê_da_ausencia_realmente_nao_tem_a_chave() -> None:
    """Sem isto a régua de cima passaria por acidente."""
    from hefesto_dualsense4unix.interface import casamento

    assert "audio" not in casamento.FALSO_SEM_AUDIO
    assert "audio" in casamento.FALSO


def test_o_estado_do_card_diz_quando_nao_leu() -> None:
    """`estado_do_card` sem a chave `audio`: `mic_sabemos` tem de ser falso.

    São DOIS pintores do mesmo selo — o pacote da aba 02 e o card do piloto
    vivo — e o segundo tinha a mesma mentira. Curar só um deixaria as duas
    versões vivas, que é o defeito que a regra da casa existe para matar.
    """
    from hefesto_dualsense4unix.interface import casamento, mesa_viva

    sem = mesa_viva.estado_do_card(casamento.FALSO_SEM_AUDIO)
    com = mesa_viva.estado_do_card(casamento.FALSO)

    assert sem["mic_sabemos"] is False
    assert com["mic_sabemos"] is True
    assert sem["mic_mudo"] is False, (
        "o valor continua sendo False — o que muda é SABERMOS que não é leitura"
    )


def test_o_selo_do_mic_tem_tres_estados_e_um_dono_so() -> None:
    """O selo do card, medido pelo COMPORTAMENTO — e nos DOIS pintores.

    ACHADO DA AUDITORIA DE 02/09/2026. Esta régua era `inspect.getsource` do
    `Janela._pacote_do_card` mais `assert '<literal>' in fonte`. Olhava o TEXTO:
    arrancada a cura de verdade (`mic_sabemos = True`, que faz o card do
    controle CAÍDO voltar a pintar ATIVO), ela ficava VERDE — e nenhuma outra
    régua desta casa pegava, porque `test_regua_de_tela_a_aba_controles.py` é
    SKIP nesta máquina.

    O ternário vivia escrito duas vezes; agora tem um dono só,
    `mesa_viva.selo_do_mic`, chamado pelo pacote `a02_controles` e pelo
    `_pacote_do_card` do piloto. Uma régua sobre a função guarda os dois.

    CURA A ARRANCAR: fazer `selo_do_mic` ignorar `sabemos` — reprova aqui.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    assert mesa_viva.selo_do_mic(False, False) == "—", (
        "sem leitura, a tela tem de dizer que não sabe — pintar ATIVO é o "
        "controle que acabou de cair anunciando que está no ar"
    )
    assert mesa_viva.selo_do_mic(True, False) == "—"
    assert mesa_viva.selo_do_mic(False, True) == "ATIVO"
    assert mesa_viva.selo_do_mic(True, True) == "MUDO"


def test_os_dois_pintores_chamam_o_mesmo_dono_do_selo() -> None:
    """Nenhum dos dois pode voltar a escrever o ternário por conta própria.

    O commit da onda escreve *"curar só um deixaria as duas versões vivas, que
    é o defeito que a regra da casa existe para matar"*. Ele curou os dois e
    guardou um. Esta régua guarda os dois.

    E ela lê o BYTECODE, não o texto: o comentário dos dois pintores explica o
    defeito e cita "ATIVO" com todas as letras, e uma régua de substring
    reprovaria justamente porque alguém escreveu bem — a forma exata das onze
    réguas que caíram nesta casa em 26/08. Comentário não entra em `co_consts`.

    CURA A ARRANCAR: reescrever o ternário em qualquer um dos dois — reprova.
    """
    from hefesto_dualsense4unix.interface import controles_vivos
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    for alvo, nome in (
        (a02_controles.pacote, "pacotes/a02_controles.py"),
        (controles_vivos.Janela._pacote_do_card, "interface/controles_vivos.py"),
    ):
        codigo = alvo.__code__
        nomes = set(codigo.co_names)
        constantes = {c for c in codigo.co_consts if isinstance(c, str)}
        constantes.discard(alvo.__doc__)

        assert "selo_do_mic" in nomes, f"{nome} não chama o dono do selo"
        assert "ATIVO" not in constantes, (
            f"{nome} voltou a decidir o selo por conta própria — duas versões "
            "vivas do mesmo ternário é o defeito que a casa mata"
        )


def test_o_default_de_mic_sabemos_no_piloto_e_nao_sei() -> None:
    """A ausência da chave não pode virar ATIVO — nem por default.

    A cura trazia `e.get("mic_sabemos", True)` embutido: no dia em que o
    `estado_do_card` deixasse de emitir a chave, o card voltava a mentir
    CALADO. É o mesmo `bool(None)` que esta onda foi curar, com outro nome.

    CURA A ARRANCAR: devolver o default para `True` — reprova.
    """
    import inspect

    from hefesto_dualsense4unix.interface import controles_vivos

    fonte = inspect.getsource(controles_vivos.Janela._pacote_do_card)
    assert 'e.get("mic_sabemos", False)' in fonte, (
        "o default de `mic_sabemos` no piloto voltou a ser `True` — a ausência "
        "de leitura passaria a pintar ATIVO de novo"
    )


def test_mesa_viva_publica_o_terceiro_estado() -> None:
    """`mic_sabemos` é o que permite à tela escolher entre três, e não dois."""
    import inspect

    from hefesto_dualsense4unix.interface import mesa_viva

    fonte = inspect.getsource(mesa_viva)
    assert '"mic_sabemos": mic_sabemos' in fonte
    assert 'mic_sabemos = isinstance(audio.get("mic_mudo"), bool)' in fonte


# ---------------------------------------------------------------------------
# 11. O gesto novo EXIGE endereço
# ---------------------------------------------------------------------------


def _nomes_do_laco() -> frozenset[str]:
    """Os nomes que o laço do mic REALMENTE toca — código, nunca prosa.

    Ler `inspect.getsource` e procurar substring mediria a PALAVRA em vez do
    ATO: o docstring desta casa cita os nomes que saíram, com o motivo de
    terem saído. É a família das onze réguas falsas — a régua reprovaria
    justamente porque alguém explicou bem a cura.

    `co_names` é o que o bytecode carrega: atributos lidos e nomes globais.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    nomes: set[str] = set()
    for fn in (hotkey.mic_button_loop, hotkey._eleger_ou_devolver):
        c = fn.__code__
        nomes.update(c.co_names)
        nomes.update(c.co_varnames)
        for const in c.co_consts:
            # O DOCSTRING FICA DE FORA, e é o ponto: ele CITA os nomes que
            # saíram, com o motivo. Contá-lo faria a régua reprovar justamente
            # porque alguém explicou bem a cura.
            if const is fn.__doc__:
                continue
            if isinstance(const, str):
                nomes.add(const)
            elif hasattr(const, "co_names"):
                nomes.update(const.co_names)
                nomes.update(
                    k for k in const.co_consts if isinstance(k, str)
                )
    return frozenset(nomes)


def test_o_laco_recusa_a_borda_sem_uniq() -> None:
    """CURA A ARRANCAR: cair no primário quando a borda não diz o controle.

    É esta régua que impede a mesa de quatro de eleger sempre o mesmo.
    """
    nomes = _nomes_do_laco()
    assert "MIC_DA_MESA" in nomes, "o laço lê o tópico COM endereço"
    assert "BUTTON_DOWN" not in nomes, "o BUTTON_DOWN não carrega uniq"

    # E a recusa deixa rastro — o log é a única coisa que sobra quando o gesto
    # dela não vira nada.
    assert "mic_da_mesa_sem_endereco" in nomes


def test_o_toggle_global_de_mute_saiu_do_gesto() -> None:
    """`toggle_default_source_mute` opera em `@DEFAULT_AUDIO_SOURCE@` — global.

    E a guarda `fonte_padrao_e_o_controle` pergunta por SUBSTRING "dualsense":
    responde "é ALGUM DualSense", nunca "é ESTE". Numa mesa de quatro os quatro
    respondem `True`. As duas saíram; se voltarem, esta régua reprova.
    """
    nomes = _nomes_do_laco()
    assert "toggle_default_source_mute" not in nomes
    assert "fonte_padrao_e_o_controle" not in nomes
    assert "set_mic_led" in nomes, "e o que ficou foi a LUZ, com endereço"


# ---------------------------------------------------------------------------
# 7 (o ATO). O botão elege o controle QUE APERTOU — medido, não digitado
# ---------------------------------------------------------------------------
#
# AUDITORIA DE 02/09/2026. As duas réguas acima leem `co_names` e exigem que
# certos NOMES estejam (ou não) no bytecode do laço. Isso é mais forte que
# `inspect.getsource`, e ainda assim mede a PALAVRA e não o ATO: os nomes
# sobrevivem à arrancada da cura. Provado com duas mordidas —
#
#   (a) o `continue` da recusa sem endereço virando queda no primário;
#   (b) `_eleger_ou_devolver` elegendo SEMPRE `conectados[0]`, que é
#       literalmente o defeito que a onda existe para impedir;
#
# — e nas duas as réguas de mic/áudio/hotkey/eleição desta casa ficaram verdes
# (855 passaram com a mordida (b) em pé). Nenhuma ligava a borda à eleição ao
# LED.
#
# As de cima FICAM: elas são boas nas asserções NEGATIVAS (o que saiu do laço),
# que é o que sabem medir. O que falta é a cena, e é ela que vem aqui.


class _Resultado:
    """O que `eleger_o_controle`/`devolver_o_microfone` devolvem."""

    def __init__(self, *, ok: bool, ativo: str, motivo: str) -> None:
        self.ok = ok
        self.ativo = ativo
        self.motivo = motivo


class _EleitorDublado:
    """`EleitorDeMicrofone` de bancada: guarda o que lhe pediram.

    O campo `eleito` é o do produto, com o mesmo contrato: passa a valer o
    `uniq` na eleição CONFERIDA e cai na devolução. Um dublê sem ele traria de
    volta o defeito nº 5 desta própria onda — *"o portão não mordia porque o
    dublê trazia o mesmo default falso"*.
    """

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, Any]] = []
        self.eleito: str | None = None

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> _Resultado:
        self.chamadas.append(("eleger", uniq))
        self.eleito = uniq
        return _Resultado(ok=True, ativo=f"mic_de_{uniq}", motivo="")

    def devolver_o_microfone(self) -> _Resultado:
        self.chamadas.append(("devolver", None))
        self.eleito = None
        return _Resultado(ok=True, ativo="mic_da_placa_mae", motivo="")


class _BackendDaMesa:
    """Backend com dois controles na mesa e o LED de cada um."""

    def __init__(self, uniqs: tuple[str, ...]) -> None:
        self._uniqs = uniqs
        self.leds: dict[str, bool] = {}

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u} for u in self._uniqs]

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:
        self.leds[uniq or "<sem endereço>"] = bool(aceso)


class _ConfigDoGesto:
    mic_button_toggles_system = True


class _DaemonDoGesto:
    def __init__(self, backend: _BackendDaMesa) -> None:
        from hefesto_dualsense4unix.core.events import EventBus

        self.bus = EventBus()
        self.config = _ConfigDoGesto()
        self.controller = backend
        self._eleitor_de_microfone = _EleitorDublado()
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


_J1 = "aabbcc000011"
_J2 = "aabbcc000022"


async def _rodar_o_gesto(daemon: _DaemonDoGesto, bordas: list[dict[str, Any]]) -> None:
    """Sobe o `mic_button_loop`, publica as bordas, drena e derruba."""
    from hefesto_dualsense4unix.core.events import EventTopic
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    tarefa = asyncio.create_task(hotkey.mic_button_loop(daemon))  # type: ignore[arg-type]
    try:
        # O laço só existe depois do primeiro `await`: publicar antes disso
        # entregaria a borda a ninguém, e a régua daria verde sobre o vazio.
        for _ in range(10):
            await asyncio.sleep(0.005)
            if daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA):
                break
        assert daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA) == 1

        for borda in bordas:
            daemon.bus.publish(EventTopic.MIC_DA_MESA, borda)
            for _ in range(20):
                await asyncio.sleep(0.005)
    finally:
        daemon._parando = True
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa


@pytest.mark.asyncio
async def test_o_botao_elege_o_controle_que_apertou_e_nao_o_primeiro_da_mesa() -> None:
    """O CORAÇÃO DA ONDA, medido: o Jogador 2 aperta, o Jogador 2 é eleito.

    A decisão dela: *"Se eu apertar o botão físico mic do controle e ele
    acender, significa que eu quero que o canal de áudio do microfone seja o
    controle."* Numa mesa de quatro, "o controle" é o que APERTOU — e a mesa
    deste teste tem o Jogador 1 na frente, exatamente para que eleger o
    primeiro passe despercebido se ninguém olhar o endereço.

    CURA A ARRANCAR: em `_eleger_ou_devolver`, trocar o `uniq` recebido por
    `conectados[0]`. As réguas de `co_names` ficam verdes (nome nenhum muda);
    esta reprova, dizendo qual controle foi eleito no lugar de qual.
    """
    backend = _BackendDaMesa((_J1, _J2))
    daemon = _DaemonDoGesto(backend)

    await _rodar_o_gesto(daemon, [{"uniq": _J2, "mudo": False}])

    eleitor = daemon._eleitor_de_microfone
    assert eleitor.chamadas == [("eleger", _J2)], (
        "o botão do Jogador 2 elegeu outro controle — é a mesa de quatro "
        f"elegendo sempre o mesmo: {eleitor.chamadas}"
    )
    assert backend.leds == {_J2: True}, (
        "o LED tem de acender no plástico de quem apertou, e só nele: "
        f"{backend.leds}"
    )


@pytest.mark.asyncio
async def test_a_borda_sem_endereco_nao_elege_ninguem() -> None:
    """A recusa é ATO: eleitor nenhum é chamado, LED nenhum acende.

    A régua de `co_names` acima exige o log `mic_da_mesa_sem_endereco` no
    bytecode. Ele sobrevive a arrancar o `continue` — medido em 02/09/2026, com
    a recusa trocada por queda no primário e a régua verde. Esta olha o efeito.

    CURA A ARRANCAR: trocar o `continue` do ramo sem `uniq` por
    `uniq = (_uniqs_conectados(daemon) or [""])[0]` — esta régua reprova.
    """
    backend = _BackendDaMesa((_J1, _J2))
    daemon = _DaemonDoGesto(backend)

    await _rodar_o_gesto(daemon, [{"uniq": "", "mudo": False}, {"mudo": False}])

    assert daemon._eleitor_de_microfone.chamadas == [], (
        "uma borda sem endereço elegeu alguém — é o gesto de um jogador virando "
        "eleição de outro"
    )
    assert backend.leds == {}, "e nenhum plástico pode acender por isso"


@pytest.mark.asyncio
async def test_o_mudo_de_quem_nao_elegeu_nao_tira_o_microfone_de_quem_elegeu() -> None:
    """A MESA DE QUATRO, na cena que ela nomeou — e era alcançável no 1º toque.

    ACHADO DA AUDITORIA DE 02/09/2026. `devolver_o_microfone()` é GLOBAL: não
    recebe `uniq`. `_eleger_ou_devolver` decidia só pelo bit `mudo` e nunca
    perguntava se ESTE controle era o eleito. Medido com dublês puros, antes da
    cura:

        apos J1 eleger  : leds = {J1: True}            chamadas = [(eleger, J1)]
        apos J2 apertar : leds = {J1: True, J2: False} chamadas = [..., (DEVOLVER,)]

    A J1 nunca soltou o microfone e ainda assim o perdeu — com o LED dela
    ACESO, dizendo "estou no ar". É a mentira que esta onda existe para matar,
    e o próprio módulo escreve *"o LED do controle passaria a mentir sobre o
    microfone dela"*.

    CURA A ARRANCAR: o ramo `if eleitor.eleito != uniq:` de
    `_eleger_ou_devolver` — esta régua reprova com a devolução fantasma.
    """
    backend = _BackendDaMesa((_J1, _J2))
    daemon = _DaemonDoGesto(backend)

    await _rodar_o_gesto(
        daemon,
        [
            {"uniq": _J1, "mudo": False},  # a J1 elege
            {"uniq": _J2, "mudo": True},   # o J2 aperta o botão DELE
        ],
    )

    eleitor = daemon._eleitor_de_microfone
    assert ("devolver", None) not in eleitor.chamadas, (
        "o mudo do Jogador 2 devolveu o microfone da MESA — tirou o padrão do "
        f"sistema da Jogadora 1, que nunca o soltou: {eleitor.chamadas}"
    )
    assert eleitor.eleito == _J1, "e a J1 continua sendo quem está com o mic"
    assert backend.leds[_J1] is True, (
        "o LED da J1 tem de continuar aceso — ela continua no ar"
    )
    assert backend.leds[_J2] is False, (
        "e o do J2 apaga: o mudo do firmware é dele, a luz é dele"
    )


@pytest.mark.asyncio
async def test_o_eleito_que_vai_a_mudo_devolve_de_verdade() -> None:
    """A outra metade: uma cura que mata o caminho de volta não é cura.

    CURA A ARRANCAR: transformar o ramo novo em `return` incondicional — o
    caminho de volta morreria calado, e é ele que impede o `.monitor` do sink
    de virar a fonte padrão dela (FONTE-PADRÃO-01/MONITOR-QUE-VENCE-01).
    """
    backend = _BackendDaMesa((_J1, _J2))
    daemon = _DaemonDoGesto(backend)

    await _rodar_o_gesto(
        daemon,
        [
            {"uniq": _J1, "mudo": False},  # a J1 elege
            {"uniq": _J1, "mudo": True},   # e a J1 devolve
        ],
    )

    eleitor = daemon._eleitor_de_microfone
    assert eleitor.chamadas == [("eleger", _J1), ("devolver", None)]
    assert eleitor.eleito is None, "a posse cai quando o eleito devolve"
    assert backend.leds[_J1] is False, "e o plástico dela apaga junto"


@pytest.mark.asyncio
async def test_sem_ninguem_eleito_o_mudo_nao_reelege_a_melhor_fonte() -> None:
    """Não se devolve o que não se tomou.

    Com `eleito is None`, uma borda de mudo caía em `devolver_o_microfone()`,
    que elege a "melhor fonte elegível" — trocando o padrão do sistema dela sem
    que ninguém tivesse elegido nada. Na bancada de hoje isso não aparece só
    porque não há fonte elegível, o que é sorte, não cura.

    E é o PRIMEIRO toque: medido no daemon vivo em 02/09, os dois controles
    dela estão `mic_mudo: False`, logo o próximo aperto de qualquer um é
    `mudo=True`.
    """
    backend = _BackendDaMesa((_J1, _J2))
    daemon = _DaemonDoGesto(backend)

    await _rodar_o_gesto(daemon, [{"uniq": _J2, "mudo": True}])

    assert daemon._eleitor_de_microfone.chamadas == [], (
        "um mudo sem eleição prévia mexeu no microfone padrão do sistema"
    )
    assert backend.leds == {_J2: False}, "só a luz de quem apertou"
