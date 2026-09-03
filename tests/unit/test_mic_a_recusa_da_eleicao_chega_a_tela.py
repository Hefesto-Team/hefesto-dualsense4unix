"""MIC-RECUSA-NA-TELA-01 — a frase da eleição do microfone VAI PARA A TELA.

**O DEFEITO, e ele estava anotado desde a auditoria de 02/09/2026.**
`integrations/eleicao_de_microfone.ResultadoDaEleicao` escreve cinco frases
boas — *"não há canal de captura atribuível a este controle"*, *"o WirePlumber
reelegeu por cima"*, *"não há microfone para onde voltar"* — e o docstring dele
diz, com todas as letras, que `motivo` **"é o texto que vai para a tela"**. Em
`daemon/subsystems/hotkey._eleger_ou_devolver` elas saíam SÓ aqui:

    logger.info("mic_da_mesa_eleicao", uniq=uniq, mudo=mudo,
                ok=resultado.ok, ativo=resultado.ativo, motivo=resultado.motivo)

Nenhuma chave no `state_full`, nenhuma no `mic.led.set`, nada no card. A regra
desta casa é a oposta: *recusar dizendo é obrigatório, e a frase VAI PARA A
TELA* — escrita para quem está com o controle na mão, não para quem lê
`journalctl`.

**E HAVIA UM SEGUNDO CAMINHO, MAIS CALADO AINDA.** Quando quem aperta não é o
eleito (`eleitor.eleito != uniq`), o laço apagava a luz do controle e voltava
com `logger.info("mic_da_mesa_mudo_de_quem_nao_elegeu")` — **sem motivo
nenhum**. É o jogador que apertou o botão e NÃO tem o microfone: ele merece a
frase mais que ninguém, porque a dona do canal pelo menos tem o LED aceso
dizendo que está no ar.

**POR QUE AS RÉGUAS MEDEM A CENA, e não os nomes no bytecode.** As de
`co_names` em `test_mic_da_mesa_o_ipc_a_tela_e_o_gesto.py` são boas nas
asserções negativas, e o próprio arquivo registra o limite delas: *"mede a
PALAVRA e não o ATO — os nomes sobrevivem à arrancada da cura"*. Aqui a borda é
publicada de verdade, o laço do produto a consome, e a frase é procurada na
saída do `_handle_daemon_state_full` DE VERDADE. Arrancar qualquer metade da
cura reprova.

**A TELA PINTA A CADA 500 ms — e é por isso que há a régua do TIQUE.** Uma
frase que existisse só no tique em que a borda chegou teria probabilidade ~0 de
coincidir com o tique em que a interface lê: ela existiria e ninguém a veria.
`test_a_frase_sobrevive_aos_tiques_seguintes` lê o `state_full` três vezes
depois de UM toque.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import recado_do_microfone
from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
    recusa_de_quem_nao_elegeu,
)

# Endereços SINTÉTICOS (`aabbcc`), nunca os da bancada dela: um endereço
# mascarado ainda carrega o OUI do aparelho, e há dois portões sobre isso.
_J1 = "aabbcc000011"
_J2 = "aabbcc000022"

_SEM_CANAL = (
    "não há canal de captura atribuível a este controle — no rádio ele só "
    "aparece com a ponte de microfone de pé"
)


# ---------------------------------------------------------------------------
# A bancada: dublês baratos, e o laço/handler do PRODUTO por cima deles
# ---------------------------------------------------------------------------


class _Resultado:
    """O que `eleger_o_controle`/`devolver_o_microfone` devolvem."""

    def __init__(self, *, ok: bool, ativo: str | None = None, motivo: str = "") -> None:
        self.ok = ok
        self.ativo = ativo
        self.motivo = motivo


class _EleitorDublado:
    """`EleitorDeMicrofone` de bancada, com o MESMO contrato do campo `eleito`.

    Ele passa a valer o `uniq` só na eleição CONFERIDA e cai na devolução. Um
    dublê sem esse campo traria de volta o defeito nº 5 da onda do microfone —
    *"o portão não mordia porque o dublê trazia o mesmo default falso"*.
    """

    def __init__(
        self,
        *,
        elege_ok: bool = True,
        motivo: str = "",
        devolve_ok: bool = True,
        motivo_da_devolucao: str = "",
    ) -> None:
        self.chamadas: list[tuple[str, Any]] = []
        self.eleito: str | None = None
        self._elege_ok = elege_ok
        self._motivo = motivo
        self._devolve_ok = devolve_ok
        self._motivo_da_devolucao = motivo_da_devolucao

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> _Resultado:
        self.chamadas.append(("eleger", uniq))
        if self._elege_ok:
            self.eleito = uniq
            return _Resultado(ok=True, ativo=f"mic_de_{uniq}")
        return _Resultado(ok=False, motivo=self._motivo)

    def devolver_o_microfone(self) -> _Resultado:
        self.chamadas.append(("devolver", None))
        # A POSSE SÓ CAI QUANDO A DEVOLUÇÃO É CONFERIDA — o contrato do módulo
        # de verdade (`eleicao_de_microfone.devolver_o_microfone`) desde
        # 02/09/2026.
        #
        # FATO SUBSTITUÍDO: este dublê zerava SEMPRE, copiando o comentário
        # *"A POSSE CAI MESMO SEM DESTINO"* que estava no produto. A premissa
        # era falsa — na devolução recusada nada é escrito e o padrão do
        # sistema continua sendo o canal daquele controle. Um dublê que zera
        # no fracasso é o defeito nº 5 desta onda de volta: a régua mediria o
        # dublê e daria verde sobre o produto errado.
        if self._devolve_ok:
            self.eleito = None
            return _Resultado(ok=True, ativo="mic_da_placa_mae")
        return _Resultado(ok=False, motivo=self._motivo_da_devolucao)


class _Backend:
    """Backend com a mesa toda e o LED de cada plástico."""

    def __init__(self, uniqs: tuple[str, ...]) -> None:
        self.uniqs = list(uniqs)
        self.caidos: set[str] = set()
        self.leds: dict[str, bool] = {}

    def sair_da_mesa(self, uniq: str) -> None:
        """O hotplug-out NA FORMA MAGRA: a entrada some do `describe_controllers`.

        É o que acontece quando o handle é fechado — e é a metade FÁCIL do
        problema. A forma que o backend real produz está em `caiu_do_cabo`.
        """
        self.uniqs = [u for u in self.uniqs if u != uniq]

    def caiu_do_cabo(self, uniq: str) -> None:
        """O hotplug-out COMO O BACKEND REAL O ENTREGA: `connected: False`.

        `core/backend_pydualsense.describe_controllers` devolve uma entrada por
        HANDLE ABERTO e mantém o `uniq` preenchido quando o controle cai
        (`backend_pydualsense.py:5298`). Quem lê só o `uniq` vê o controle na
        mesa; só quem exige o `connected` vê que ele saiu.
        """
        self.caidos.add(uniq)

    def is_connected(self) -> bool:
        return bool([u for u in self.uniqs if u not in self.caidos])

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [
            {"uniq": u, "connected": u not in self.caidos} for u in self.uniqs
        ]

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:
        self.leds[uniq or "<sem endereço>"] = bool(aceso)


class _Config:
    mic_button_toggles_system = True


class _Daemon:
    def __init__(self, backend: _Backend, eleitor: _EleitorDublado) -> None:
        from hefesto_dualsense4unix.core.events import EventBus

        self.bus = EventBus()
        self.config = _Config()
        self.controller = backend
        self._eleitor_de_microfone = eleitor
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando

    def is_paused(self) -> bool:
        return False

    def is_native_mode(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


def _mesa(
    uniqs: tuple[str, ...] = (_J1, _J2),
    *,
    elege_ok: bool = True,
    motivo: str = "",
    devolve_ok: bool = True,
    motivo_da_devolucao: str = "",
) -> tuple[_Daemon, _Backend, _EleitorDublado]:
    backend = _Backend(uniqs)
    eleitor = _EleitorDublado(
        elege_ok=elege_ok,
        motivo=motivo,
        devolve_ok=devolve_ok,
        motivo_da_devolucao=motivo_da_devolucao,
    )
    return _Daemon(backend, eleitor), backend, eleitor


async def _rodar_o_gesto(daemon: _Daemon, bordas: list[dict[str, Any]]) -> None:
    """Sobe o `mic_button_loop` DO PRODUTO, publica as bordas, drena e derruba."""
    from hefesto_dualsense4unix.core.events import EventTopic
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    tarefa = asyncio.create_task(hotkey.mic_button_loop(daemon))  # type: ignore[arg-type]
    try:
        # O laço só existe depois do primeiro `await`: publicar antes disso
        # entregaria a borda a ninguém, e a régua daria verde sobre o vazio.
        for _ in range(20):
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


async def _rodar_os_passos(
    daemon: _Daemon, passos: list[Any]
) -> list[dict[str, Any]]:
    """Como `_rodar_o_gesto`, mas com um TIQUE lido depois de CADA passo.

    Um passo é uma borda (`dict`) ou um efeito da bancada (`callable` sem
    argumento) — tirar um controle da mesa, por exemplo.

    Existe separado porque `_rodar_o_gesto` derruba o laço no `finally`:
    chamá-lo duas vezes na mesma cena entregaria a segunda borda a ninguém, e a
    régua daria verde sobre o vazio. Cenas que medem o ANTES e o DEPOIS de um
    mesmo laço passam por aqui.

    Devolve um bloco `mic_da_mesa` por passo, na ordem.
    """
    from hefesto_dualsense4unix.core.events import EventTopic
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    blocos: list[dict[str, Any]] = []
    tarefa = asyncio.create_task(hotkey.mic_button_loop(daemon))  # type: ignore[arg-type]
    try:
        for _ in range(20):
            await asyncio.sleep(0.005)
            if daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA):
                break
        assert daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA) == 1

        for passo in passos:
            if callable(passo):
                passo()
            else:
                daemon.bus.publish(EventTopic.MIC_DA_MESA, passo)
                for _ in range(20):
                    await asyncio.sleep(0.005)
            blocos.append((await _tique_async(daemon))["mic_da_mesa"])
    finally:
        daemon._parando = True
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa
    return blocos


async def _tique_async(daemon: _Daemon) -> dict[str, Any]:
    """UM `daemon.state_full` DE VERDADE — o handler do produto, não um resumo.

    Um `StateStore` novo por tique de propósito: o que esta régua mede é o
    bloco `mic_da_mesa`, e ele não pode depender de nada que o store carregue
    de uma leitura para a outra.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.state_store import StateStore

    class _Handlers(IpcHandlersMixin):  # type: ignore[misc]
        def __init__(self, d: _Daemon) -> None:
            self.store = StateStore()
            self.controller = d.controller
            self.daemon = d

    return await _Handlers(daemon)._handle_daemon_state_full({})


# ---------------------------------------------------------------------------
# 1. A RECUSA DA ELEIÇÃO CHEGA AO `state_full`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_recusa_da_eleicao_chega_ao_state_full() -> None:
    """A frase que só existia no `logger.info` agora sai no tique.

    CURA A ARRANCAR: o `recado_do_microfone.anotar(...)` que fica logo abaixo
    do `logger.info("mic_da_mesa_eleicao", ...)` em `_eleger_ou_devolver`.
    Sem ele o `motivo` volta a existir só no journal, e esta régua reprova
    dizendo que o dicionário de recados veio vazio.
    """
    daemon, _backend, _eleitor = _mesa(elege_ok=False, motivo=_SEM_CANAL)

    await _rodar_o_gesto(daemon, [{"uniq": _J2, "mudo": False}])
    estado = await _tique_async(daemon)

    bloco = estado["mic_da_mesa"]
    assert _J2 in bloco["recados"], (
        "a eleição recusou e a tela não recebeu nada — a frase ficou no log: "
        f"{bloco}"
    )
    recado = bloco["recados"][_J2]
    assert recado["ok"] is False
    assert recado["motivo"] == _SEM_CANAL, (
        "a frase da tela tem de ser a MESMA do `ResultadoDaEleicao.motivo` — "
        "reescrevê-la aqui criaria a segunda verdade sobre a mesma recusa"
    )
    assert recado["gesto"] == "eleger"
    assert recado["uniq"] == _J2, "o recado tem de dizer DE QUAL controle é"


# ---------------------------------------------------------------------------
# 2. O SEGUNDO CAMINHO CALADO: quem apertou e NÃO tem o microfone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_mudo_de_quem_nao_elegeu_ganha_frase_na_tela() -> None:
    """A J1 elege; o J2 aperta o botão DELE e vai a mudo. O J2 é quem precisa ler.

    Este ramo voltava com `logger.info("mic_da_mesa_mudo_de_quem_nao_elegeu")` e
    mais nada. Quem está com o controle na mão via a luz apagar, o microfone
    seguir no vizinho, e o produto calado.

    CURA A ARRANCAR: o `recado_do_microfone.anotar(..., gesto="recusa", ...)`
    dentro do `if eleitor.eleito != uniq:`.
    """
    daemon, backend, eleitor = _mesa()

    await _rodar_o_gesto(
        daemon,
        [
            {"uniq": _J1, "mudo": False},  # a J1 elege
            {"uniq": _J2, "mudo": True},  # o J2 aperta o DELE
        ],
    )
    estado = await _tique_async(daemon)
    bloco = estado["mic_da_mesa"]

    assert _J2 in bloco["recados"], (
        "o jogador que apertou e não tem o microfone não recebeu uma palavra: "
        f"{bloco}"
    )
    recado = bloco["recados"][_J2]
    assert recado["gesto"] == "recusa"
    assert recado["ok"] is False
    assert recado["motivo"] == recusa_de_quem_nao_elegeu(_J1).motivo, (
        "a frase da tela tem de ser a MESMA que `recusa_de_quem_nao_elegeu` "
        "escreve — `motivo.strip()` deixava passar 'não rolou' escrito no "
        "laço, que é a segunda verdade sobre a mesma recusa. MEDIDO: com "
        "`motivo='não rolou'` no lugar de `recusa.motivo` os nove testes "
        "passavam, e a função do módulo podia sair do caminho sem ninguém ver"
    )
    assert recado["eleito"] == _J1, (
        "a tela precisa do DADO de quem está com o canal para dizer 'P1' em "
        "vez de repetir um endereço de rádio"
    )
    assert bloco["eleito"] == _J1, (
        "o `eleito` do BLOCO é o único campo VIVO daqui e não tinha régua: "
        "cravá-lo em `None` deixava os nove verdes, e o card pintaria "
        "'ninguém está com o microfone' para sempre"
    )
    assert bloco["eleito_na_mesa"] is True, (
        "a J1 está na mesa; dizer o contrário mandaria a tela apagar um canal "
        "que está no ar"
    )

    # E as DUAS curas da auditoria de 02/09/2026 continuam de pé: quem não
    # elegeu não devolve o microfone da mesa, e só a PRÓPRIA luz apaga.
    assert eleitor.chamadas == [("eleger", _J1)], (
        f"o botão do J2 mexeu no microfone da mesa: {eleitor.chamadas}"
    )
    assert backend.leds == {_J1: True, _J2: False}, (
        f"a luz apagada tem de ser a de quem apertou, e só ela: {backend.leds}"
    )


# ---------------------------------------------------------------------------
# 3. A FRASE SOBREVIVE AOS TIQUES SEGUINTES — a tela pinta a cada 500 ms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_frase_sobrevive_aos_tiques_seguintes() -> None:
    """Um toque, três leituras: a frase está nas três, e ENVELHECE.

    CURA A ARRANCAR: publicar o recado como evento do instante (limpando o
    depósito depois de publicar). O primeiro tique passaria e os outros dois
    reprovariam — que é exatamente o que a pessoa veria na tela dela.
    """
    daemon, _backend, _eleitor = _mesa(elege_ok=False, motivo=_SEM_CANAL)

    await _rodar_o_gesto(daemon, [{"uniq": _J1, "mudo": False}])

    idades: list[float] = []
    for _ in range(3):
        estado = await _tique_async(daemon)
        recados = estado["mic_da_mesa"]["recados"]
        assert _J1 in recados, "a frase durou um instante e a tela não a viu"
        assert recados[_J1]["motivo"] == _SEM_CANAL
        idades.append(recados[_J1]["idade_s"])
        await asyncio.sleep(0.02)

    assert idades == sorted(idades), (
        f"a idade do recado tem de crescer entre tiques: {idades}"
    )
    assert idades[-1] > idades[0], (
        "a idade ficou congelada — quem lê a tela não tem como saber se a "
        f"frase é de agora ou de meia hora atrás: {idades}"
    )


# ---------------------------------------------------------------------------
# 4. UM RECADO POR CONTROLE — a recusa de um não apaga a resposta do outro
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cada_controle_guarda_o_proprio_recado() -> None:
    """Depósito único faria o card errado mostrar a frase do vizinho.

    CURA A ARRANCAR: trocar o dicionário por uma variável só. A J1 perderia a
    resposta dela no instante em que o J2 fosse recusado.
    """
    daemon, _backend, _eleitor = _mesa()

    await _rodar_o_gesto(
        daemon,
        [{"uniq": _J1, "mudo": False}, {"uniq": _J2, "mudo": True}],
    )
    recados = (await _tique_async(daemon))["mic_da_mesa"]["recados"]

    assert set(recados) == {_J1, _J2}, f"faltou o recado de alguém: {sorted(recados)}"
    assert recados[_J1]["gesto"] == "eleger" and recados[_J1]["ok"] is True
    assert recados[_J2]["gesto"] == "recusa" and recados[_J2]["ok"] is False
    assert recados[_J1]["motivo"] == "", (
        "eleição que deu certo não ganha frase inventada: o LED do plástico já "
        "diz que está no ar"
    )
    # Os dois campos que VIAJAM para a tela e não tinham uma única asserção:
    # apagar `ativo=` ou `eleito=` da chamada do produto deixava os nove
    # verdes, e o payload passava a sair `None` sem ninguém acusar.
    assert recados[_J1]["ativo"] == f"mic_de_{_J1}", (
        "o canal que o produto ELEGEU tem de chegar à tela: sem ele o card "
        f"não sabe dizer para onde a voz está indo — {recados[_J1]}"
    )
    assert recados[_J1]["eleito"] == _J1, (
        "o retrato da mesa no instante da eleição também viaja, e é o par do "
        f"que o recado de recusa carrega — {recados[_J1]}"
    )


# ---------------------------------------------------------------------------
# 5. O SHAPE É SEMPRE O MESMO — chave que some é mentira de segunda geração
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_chave_existe_com_a_mesa_vazia_e_sem_ninguem_ter_apertado() -> None:
    """`mic_da_mesa` nasce presente e vazio, nunca ausente.

    É a cicatriz da chave `audio`, que SUMIA do `state_full` no hotplug-out —
    `bool(None)` virava `False` e o selo pintava ATIVO sobre o controle que
    acabara de cair.
    """
    daemon, _backend, _eleitor = _mesa(uniqs=())

    estado = await _tique_async(daemon)

    assert estado["mic_da_mesa"] == {
        "eleito": None,
        "eleito_na_mesa": None,
        "recados": {},
    }


def test_publicar_nao_cria_o_eleitor_da_sessao() -> None:
    """Ler o estado não pode CONSTRUIR estado — o handler roda a 10 Hz.

    Um `getattr` que instanciasse o `EleitorDeMicrofone` aqui faria o relato
    mexer no que ele relata, e a memória do "microfone de antes" nasceria numa
    leitura em vez de num gesto dela.
    """

    class _Cru:
        pass

    cru = _Cru()
    assert recado_do_microfone.publicar(cru) == {
        "eleito": None,
        "eleito_na_mesa": None,
        "recados": {},
    }
    assert not hasattr(cru, "_eleitor_de_microfone")
    assert not hasattr(cru, recado_do_microfone.ATRIBUTO)


# ---------------------------------------------------------------------------
# 6. AS DUAS RECUSAS DE QUEM NÃO ELEGEU SÃO FRASES DIFERENTES
# ---------------------------------------------------------------------------


def test_a_recusa_separa_ninguem_elegeu_de_o_canal_e_de_outro() -> None:
    """`eleito is None` e `eleito` é outro controle não são a mesma notícia.

    CURA A ARRANCAR: devolver a mesma frase nos dois ramos. A pessoa leria "o
    microfone está com outro controle" quando o microfone não está com ninguém
    — e iria procurar um dono que não existe.
    """
    ninguem = recusa_de_quem_nao_elegeu(None)
    de_outro = recusa_de_quem_nao_elegeu(_J1)

    assert ninguem.ok is False and de_outro.ok is False
    assert ninguem.motivo.strip() and de_outro.motivo.strip()
    assert ninguem.motivo != de_outro.motivo
    assert "ninguém" in ninguem.motivo
    assert "outro controle" in de_outro.motivo
    assert _J1 not in de_outro.motivo, (
        "a frase não nomeia o dono por endereço de rádio — o `uniq` viaja como "
        "DADO, ao lado dela"
    )


# ---------------------------------------------------------------------------
# 7. O DEPÓSITO NÃO CRESCE SEM FIM, e quem sai é o mais VELHO
# ---------------------------------------------------------------------------


def test_o_deposito_tem_teto_e_descarta_o_mais_velho() -> None:
    """Um daemon de dias com hotplug não pode acumular recado para sempre.

    O mais NOVO é o que a pessoa acabou de provocar e é o único que ela está
    esperando ver; por isso quem sai é o mais velho.
    """

    class _Cru:
        pass

    cru = _Cru()
    quantos = recado_do_microfone.TETO + 3
    for i in range(quantos):
        recado_do_microfone.anotar(
            cru,  # type: ignore[arg-type]
            f"aabbcc0000{i:02d}",
            gesto="recusa",
            ok=False,
            motivo="sem canal",
            agora_s=float(i),
        )

    guardados = getattr(cru, recado_do_microfone.ATRIBUTO)
    assert len(guardados) == recado_do_microfone.TETO
    assert "aabbcc000000" not in guardados, "o mais velho tinha de ter saído"
    assert f"aabbcc0000{quantos - 1:02d}" in guardados, "o mais novo tem de ficar"


# ---------------------------------------------------------------------------
# 8. O CAMINHO DE VOLTA — o gesto `devolver` era código morto para esta régua
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_gesto_devolver_chega_a_tela_com_a_frase_do_caminho_de_volta() -> None:
    """A J1 elege e aperta de novo: o ramo `devolver` e a QUINTA frase.

    ACHADO DA AUDITORIA (02/09/2026), reproduzido: uma bomba
    (`raise AssertionError`) posta imediatamente antes do
    `eleitor.devolver_o_microfone()` NÃO disparava — nenhuma borda tinha
    `mudo=True` com `eleitor.eleito == uniq`. Consequências medidas: (a)
    `GESTOS` declara três gestos e só dois eram vistos, então colapsar
    `gesto="devolver" if mudo else "eleger"` em `"eleger"` deixava os nove
    verdes; (b) a quinta das cinco frases que esta frente promete atravessar —
    *"não há microfone para onde voltar"* — tinha ZERO cobertura no
    `state_full`.

    CURA A ARRANCAR: qualquer metade do ramo `devolver`.
    """
    sem_volta = (
        "não há microfone para onde voltar: nenhuma fonte de captura com porta "
        "usável nesta máquina"
    )
    daemon, backend, eleitor = _mesa(
        devolve_ok=False, motivo_da_devolucao=sem_volta
    )

    await _rodar_o_gesto(
        daemon,
        [
            {"uniq": _J1, "mudo": False},  # a J1 elege
            {"uniq": _J1, "mudo": True},  # e a J1 devolve
        ],
    )
    bloco = (await _tique_async(daemon))["mic_da_mesa"]

    assert eleitor.chamadas == [("eleger", _J1), ("devolver", None)], (
        "o ramo de VOLTA não foi executado — quem elegeu tem de conseguir "
        f"devolver: {eleitor.chamadas}"
    )
    recado = bloco["recados"][_J1]
    assert recado["gesto"] == "devolver", (
        "o gesto que a tela recebe tem de separar 'devolver' de 'eleger': são "
        f"duas notícias diferentes para quem está com o controle — {recado}"
    )
    assert recado["ok"] is False
    assert recado["motivo"] == sem_volta, (
        "a frase do caminho de volta ficou no log: a pessoa apertou, o "
        f"microfone não voltou para lugar nenhum, e a tela não disse nada — {recado}"
    )
    assert bloco["eleito"] == _J1, (
        "FATO SUBSTITUÍDO (02/09/2026): esta linha exigia `None`, com a razão "
        "'a posse cai mesmo sem destino'. A premissa era falsa — a devolução "
        "recusada não escreve nada, e o padrão do sistema continua sendo o "
        "canal da J1. Publicar `eleito: null` com o canal ainda nela é a tela "
        f"dizendo que ninguém está no ar enquanto o sistema grava por ela: {bloco}"
    )
    assert backend.leds == {_J1: True}, (
        "A LUZ FICA ACESA — decisão dela, e consequência do contrato do LED "
        "('aceso = este mic está no ar'). O canal continua sendo o da J1, "
        "logo o microfone dela está no ar. Aqui o produto cravava "
        f"`aceso = False` antes de saber o desfecho: {backend.leds}"
    )


# ---------------------------------------------------------------------------
# 9. A FRASE ENVELHECE E VIRA MENTIRA — `vale_agora` é quem separa as duas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_recusa_deixa_de_valer_quando_o_dono_devolve_o_microfone() -> None:
    """O J2 é recusado, a J1 devolve, e o recado do J2 vira história.

    ACHADO DA AUDITORIA (02/09/2026), reproduzido com o `mic_button_loop` e o
    `_handle_daemon_state_full` do produto: depois da devolução da J1 o bloco
    dizia `eleito: null` e o card do J2 seguia publicando *"o microfone da mesa
    está com outro controle"* a 10 Hz, para sempre. A pessoa procuraria um dono
    que não existe.

    `idade_s` NÃO resolvia: envelhecimento não é falsidade — uma frase de
    200 ms pode já estar errada. O que faltava era comparar o retrato
    CONGELADO no recado com o dono de AGORA, e nada no payload permitia isso.

    CURA A ARRANCAR: o `vale_agora` de `RecadoDoMicrofone.em_dicionario`, ou o
    `dono_agora` que `publicar` calcula para ele.
    """
    daemon, _backend, _eleitor = _mesa()

    blocos = await _rodar_os_passos(
        daemon,
        [
            {"uniq": _J1, "mudo": False},  # a J1 elege
            {"uniq": _J2, "mudo": True},  # o J2 é recusado
            {"uniq": _J1, "mudo": True},  # e a J1 devolve
        ],
    )

    assert blocos[1]["recados"][_J2]["vale_agora"] is True, (
        "a recusa acabou de nascer e o mundo que ela descreve é este — marcá-la "
        f"inválida aqui apagaria a única resposta que o J2 recebeu: {blocos[1]}"
    )

    # A J1 devolveu. Ninguém encostou no controle do J2, e a frase dele não
    # muda — mas o mundo que ela descreve deixou de existir.
    for volta in range(3):
        bloco = (await _tique_async(daemon))["mic_da_mesa"]
        recado = bloco["recados"][_J2]
        assert bloco["eleito"] is None, "ninguém está com o microfone da mesa"
        assert recado["motivo"] == recusa_de_quem_nao_elegeu(_J1).motivo, (
            "o depósito guarda o que foi dito, não reescreve história"
        )
        assert recado["vale_agora"] is False, (
            "a frase diz que o canal está com outro controle e NINGUÉM está "
            "com ele; sem este campo a tela publica a mentira a cada 500 ms — "
            f"volta {volta}, recado {recado}, bloco.eleito {bloco['eleito']!r}"
        )
        await asyncio.sleep(0.01)


# ---------------------------------------------------------------------------
# 10. O DONO QUE SAIU DA MESA — hotplug-out sem devolução
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_eleito_que_saiu_da_mesa_nao_e_publicado_como_dono_de_agora() -> None:
    """A J1 elege e cai do cabo. Nada em `src/` limpa a posse no hotplug-out.

    ACHADO DA AUDITORIA (02/09/2026), reproduzido: as TRÊS únicas escritas de
    `EleitorDeMicrofone.eleito` são caminhos de eleição, e nenhuma roda quando
    um controle cai. O bloco seguia publicando o `uniq` da J1 como dono do
    microfone da mesa, e o botão do J2 recebia *"está com outro controle"* —
    mandando a pessoa procurar quem não tem card na tela.

    O `eleito` CRU continua saindo, e de propósito: a fonte padrão do sistema
    ainda aponta para o canal morto dele, e apagar esse dado seria trocar uma
    mentira por outra. Quem diz que ele não vale mais é o `eleito_na_mesa`.

    CURA A ARRANCAR: o `eleito_na_mesa` de `publicar`, ou o `dono` que
    `hotkey._eleger_ou_devolver` calcula contra os conectados.
    """
    daemon, backend, _eleitor = _mesa()

    blocos = await _rodar_os_passos(
        daemon,
        [
            {"uniq": _J1, "mudo": False},  # a J1 elege
            lambda: backend.sair_da_mesa(_J1),  # e o cabo dela sai
            {"uniq": _J2, "mudo": True},  # o J2 aperta o DELE
        ],
    )

    bloco = blocos[1]
    assert bloco["eleito"] == _J1, (
        "o dado cru do eleitor não se apaga: a fonte padrão do sistema ainda "
        "aponta para o canal do controle que caiu"
    )
    assert bloco["eleito_na_mesa"] is False, (
        "o controle eleito saiu da mesa e a tela não tem como saber — pintar o "
        f"nome dele seria nomear um controle sem card: {bloco}"
    )
    assert bloco["recados"][_J1]["vale_agora"] is False

    # E o botão do J2 não pode receber a frase que nomeia um ausente.
    recado = blocos[2]["recados"][_J2]

    assert recado["motivo"] == recusa_de_quem_nao_elegeu(None).motivo, (
        "com o dono fora da mesa a notícia certa é a que ela já escreveu para "
        f"'ninguém está com o microfone' — e veio: {recado['motivo']!r}"
    )
    assert "outro controle" not in recado["motivo"], (
        "não há outro controle: o que tinha o canal saiu da mesa"
    )
    assert recado["eleito"] is None, (
        "o retrato da mesa não pode carregar o endereço de quem não está nela: "
        "é dele que o card tira o `data-uniq` para apontar"
    )
    assert recado["vale_agora"] is True, (
        "a frase acaba de nascer e descreve a mesa de agora"
    )


def test_o_handle_que_sobrou_desconectado_nao_conta_como_mesa() -> None:
    """`uniq` sem `connected` não é presença — o backend real preenche os dois.

    `core/backend_pydualsense.describe_controllers` devolve uma entrada por
    HANDLE e escreve o `uniq` mesmo com `connected: False`. Ler só o `uniq` —
    que é o que `hotkey._uniqs_conectados` faz, porque a lista dele vai para a
    ELEIÇÃO — daria "está na mesa" ao handle que o controle já largou, e o
    defeito voltaria inteiro pela porta de trás.
    """

    class _EleitorCru:
        eleito = _J1

    class _HandleFantasma:
        def describe_controllers(self) -> list[dict[str, Any]]:
            return [
                {"uniq": _J1, "connected": False},  # o handle que sobrou
                {"uniq": _J2, "connected": True},
            ]

    class _Cru:
        controller = _HandleFantasma()
        _eleitor_de_microfone = _EleitorCru()

    bloco = recado_do_microfone.publicar(_Cru())

    assert bloco["eleito"] == _J1
    assert bloco["eleito_na_mesa"] is False, (
        f"o handle está aberto e o controle não está nele: {bloco}"
    )


def test_nao_saber_quem_esta_na_mesa_nunca_vira_o_dono_saiu() -> None:
    """Backend que não sabe listar devolve `None`, jamais `False`.

    É a cicatriz de sempre: ausência de dado lida como negação. Um backend
    legado (ou o `FakeController`) não tem `describe_controllers`; se isso
    virasse `eleito_na_mesa=False`, a tela apagaria um canal que está no ar e
    marcaria toda frase como história.
    """

    class _EleitorCru:
        eleito = _J1

    class _SemLista:
        """Sabe acender LED, não sabe dizer quem está na mesa."""

    class _Cru:
        controller = _SemLista()
        _eleitor_de_microfone = _EleitorCru()

    cru = _Cru()
    recado_do_microfone.anotar(
        cru,  # type: ignore[arg-type]
        _J2,
        gesto="recusa",
        ok=False,
        motivo="o microfone da mesa está com outro controle",
        eleito=_J1,
    )
    bloco = recado_do_microfone.publicar(cru)

    assert bloco["eleito"] == _J1
    assert bloco["eleito_na_mesa"] is None, (
        f"'não perguntei a ninguém' não é 'ele saiu': {bloco}"
    )
    assert bloco["recados"][_J2]["vale_agora"] is True, (
        "sem saber quem está na mesa, o dono fica de pé e a frase continua "
        f"valendo: {bloco}"
    )


def test_gesto_desconhecido_sai_nomeado() -> None:
    """Aceitar calado faria a tela receber uma palavra que ela não sabe pintar."""

    class _Cru:
        pass

    with pytest.raises(ValueError, match="gesto de microfone desconhecido"):
        recado_do_microfone.anotar(
            _Cru(),  # type: ignore[arg-type]
            _J1,
            gesto="silenciar",
            ok=False,
        )


# ---------------------------------------------------------------------------
# 12. O HOTPLUG-OUT DE VERDADE — o handle fica aberto com `connected: False`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_dono_que_caiu_do_cabo_com_o_handle_aberto_nao_e_nomeado() -> None:
    """A cura anterior ficou pela METADE: ela só via o hotplug-out magro.

    `test_o_eleito_que_saiu_da_mesa_nao_e_publicado_como_dono_de_agora` tira a
    entrada inteira do `describe_controllers`. **O backend real não faz isso.**
    Ele devolve uma entrada por HANDLE ABERTO e mantém o `uniq` preenchido com
    `connected: False` (`core/backend_pydualsense.py:5298`) — o handle só
    fecha quando alguém o fecha.

    E aí as DUAS leituras da mesa divergiam, no mesmo `state_full`:

    * `recado_do_microfone.publicar` exige o `connected` → `eleito_na_mesa:
      false`;
    * `hotkey._eleger_ou_devolver` perguntava a `_uniqs_conectados`, que lê só
      o `uniq` → o dono continuava de pé, e o J2 recebia *"o microfone da mesa
      está com OUTRO CONTROLE"*.

    O segundo jogador lia que o canal está com alguém que não tem card na
    tela — exatamente o defeito que a cura de 02/09 dizia ter matado.

    CURA A ARRANCAR: trocar `recado_do_microfone.mesa_de_agora(daemon)` por
    `conectados` de volta, em `hotkey._eleger_ou_devolver`.
    """
    daemon, backend, _eleitor = _mesa()

    blocos = await _rodar_os_passos(
        daemon,
        [
            {"uniq": _J1, "mudo": False},  # a J1 elege
            lambda: backend.caiu_do_cabo(_J1),  # o cabo dela sai, o handle fica
            {"uniq": _J2, "mudo": True},  # o J2 aperta o DELE
        ],
    )

    assert blocos[1]["eleito_na_mesa"] is False, (
        "a bancada não reproduziu o hotplug-out: o `connected: False` tem de "
        f"chegar ao `describe_controllers` — {blocos[1]}"
    )

    recado = blocos[2]["recados"][_J2]
    assert recado["motivo"] == recusa_de_quem_nao_elegeu(None).motivo, (
        "o J2 leu que o canal está com outro controle, e esse controle caiu "
        f"do cabo — mandaram ele procurar um dono sem card: {recado['motivo']!r}"
    )
    assert "outro controle" not in recado["motivo"]
    assert recado["eleito"] is None, (
        "o retrato da mesa não pode carregar o endereço de quem não está nela"
    )
    assert blocos[2]["eleito_na_mesa"] is False, (
        "as duas leituras da mesa têm de dar o MESMO veredito no mesmo tique: "
        f"{blocos[2]}"
    )


def test_a_leitura_da_mesa_e_uma_so_e_ela_exige_o_connected() -> None:
    """`hotkey` e `state_full` perguntam à MESMA função quem tem card.

    Duas réguas sobre o mesmo estado é o defeito que esta casa já pagou onze
    vezes, e foi assim que ele voltou aqui. A função pública
    `recado_do_microfone.mesa_de_agora` é a resposta.

    CURA A ARRANCAR: o `connected` de `mesa_de_agora` — trocar o filtro por
    uma leitura só do `uniq` faz a primeira asserção reprovar.

    **O QUE ESTE TESTE NÃO PEGA, e a promessa estava errada** (auditoria de
    02/09/2026): ele chama as DUAS funções diretamente e nunca alcança o ponto
    de chamada em `hotkey._eleger_ou_devolver`. O docstring prometia pegar
    *"qualquer segunda leitura de 'quem está na mesa' dentro do ramo de recusa
    do `hotkey`"*, e a mordida mediu o contrário: trocando aquela linha por
    `mesa = conectados`, quem reprovou foi
    `test_o_dono_que_caiu_do_cabo_com_o_handle_aberto_nao_e_nomeado`, e ESTE
    passou verde. A linha continua com régua — pelo vizinho. Quem apagar o
    vizinho fica sem nenhuma, e é por isso que a promessa foi corrigida em vez
    de apagada: nesta casa a próxima pessoa acredita no docstring.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    class _Fantasma:
        def describe_controllers(self) -> list[dict[str, Any]]:
            return [
                {"uniq": _J1, "connected": False},  # o handle que sobrou
                {"uniq": _J2, "connected": True},
            ]

    class _Cru:
        controller = _Fantasma()

    cru = _Cru()

    assert recado_do_microfone.mesa_de_agora(cru) == [_J2], (
        "a leitura de 'tem card na tela' tem de exigir o `connected`"
    )
    assert hotkey._uniqs_conectados(cru) == [_J1, _J2], (  # type: ignore[arg-type]
        "a lista da ELEIÇÃO continua sendo outra, e de propósito: ela responde "
        "'quem pode ser eleito', não 'quem tem card'. Unificá-las mexeria em "
        "quem pode ganhar o microfone"
    )


# ---------------------------------------------------------------------------
# 13. A LUZ FICA ACESA QUANDO A DEVOLUÇÃO É RECUSADA — decisão dela (02/09)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_luz_apaga_apenas_quando_a_devolucao_e_conferida() -> None:
    """O par simétrico: devolveu de verdade apaga; não conseguiu, fica acesa.

    Contrato do LED, escrito por ela em 01/09: *"aceso = este mic está no
    ar"*. O produto cravava `aceso = False` ANTES de chamar
    `devolver_o_microfone()` — a luz caía pela INTENÇÃO, que é a mesma mentira
    de segunda geração que o lado da eleição já evitava, só que ao contrário.

    CURA A ARRANCAR: `aceso = not bool(resultado.ok)` de volta para
    `aceso = False`. O segundo caso reprova.
    """
    # a devolução DEU CERTO: o canal saiu dela, a luz apaga
    daemon, backend, _eleitor = _mesa()
    await _rodar_o_gesto(
        daemon, [{"uniq": _J1, "mudo": False}, {"uniq": _J1, "mudo": True}]
    )
    assert backend.leds == {_J1: False}, (
        f"a devolução foi conferida e a luz tinha de apagar: {backend.leds}"
    )

    # a devolução FOI RECUSADA: o canal continua dela, a luz fica acesa
    daemon2, backend2, _e2 = _mesa(
        devolve_ok=False,
        motivo_da_devolucao="não há microfone para onde voltar",
    )
    await _rodar_o_gesto(
        daemon2, [{"uniq": _J1, "mudo": False}, {"uniq": _J1, "mudo": True}]
    )
    assert backend2.leds == {_J1: True}, (
        "o produto não conseguiu devolver: o padrão do sistema continua sendo "
        "o canal deste controle, logo o microfone dele está no ar, logo a luz "
        f"fica acesa. {backend2.leds}"
    )


def test_a_posse_so_cai_quando_a_devolucao_e_conferida() -> None:
    """O `EleitorDeMicrofone` DE VERDADE — sem `pactl`, sem aparelho.

    A luz e a posse têm de dar o mesmo veredito: luz acesa com
    `mic_da_mesa.eleito: null` seria o plástico e a tela discordando sobre
    quem está no ar.

    FATO SUBSTITUÍDO (02/09/2026): `devolver_o_microfone` zerava `self.eleito`
    incondicionalmente, com o comentário *"A POSSE CAI MESMO SEM DESTINO — o
    controle saiu do ar"*. A premissa era falsa, e este teste a mede: nas duas
    recusas o `set-default-source` **nunca roda**, então o padrão do sistema
    continua sendo o canal do controle.

    CURA A ARRANCAR: o `if resultado.ok:` de `devolver_o_microfone`.
    """
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele

    def montar(
        monkey: pytest.MonkeyPatch, *, destino: str | None, sustenta: bool
    ) -> tuple[Any, list[list[str]]]:
        escritas: list[list[str]] = []
        monkey.setattr(ele, "melhor_fonte_elegivel", lambda: destino)
        monkey.setattr(ele, "fonte_se_sustenta", lambda _nome: sustenta)
        monkey.setattr(ele, "fonte_ativa", lambda: destino)
        monkey.setattr(
            ele, "_rodar", lambda argv: (escritas.append(argv), (0, ""))[1]
        )
        eleitor = ele.EleitorDeMicrofone()
        eleitor.eleito = _J1
        return eleitor, escritas

    for rotulo, destino, sustenta in (
        ("não há para onde voltar", None, True),
        ("o destino não se sustenta", "mic_da_placa_mae", False),
    ):
        with pytest.MonkeyPatch.context() as monkey:
            eleitor, escritas = montar(monkey, destino=destino, sustenta=sustenta)
            resultado = eleitor.devolver_o_microfone()
            assert resultado.ok is False, rotulo
            assert escritas == [], (
                f"{rotulo}: a recusa não pode ter escrito nada — {escritas}"
            )
            assert eleitor.eleito == _J1, (
                f"{rotulo}: nada foi escrito, o padrão do sistema continua "
                "sendo o canal deste controle, e a posse não pode cair"
            )

    with pytest.MonkeyPatch.context() as monkey:
        eleitor, escritas = montar(
            monkey, destino="mic_da_placa_mae", sustenta=True
        )
        resultado = eleitor.devolver_o_microfone()
        assert resultado.ok is True
        assert escritas == [["pactl", "set-default-source", "mic_da_placa_mae"]]
        assert eleitor.eleito is None, (
            "a devolução foi CONFERIDA pela releitura do ativo: agora a posse cai"
        )


# ---------------------------------------------------------------------------
# 14. O RECADO TEM PRAZO — decisão 19 dela (02/09): "é aviso, não estado"
# ---------------------------------------------------------------------------


def test_o_recado_some_depois_do_prazo_e_o_estado_do_canal_nao() -> None:
    """*"A frase de recusa some depois de um tempo, na ordem de 30 segundos."*

    O depósito republicava a última resposta em TODO `state_full` até o toque
    seguinte DAQUELE controle. Um controle pode ficar horas sem tocar no botão:
    a frase virava um aviso de meia hora atrás com cara de agora.

    O que expira é o AVISO. O estado do canal (`eleito`, `eleito_na_mesa`) é
    fato da máquina e continua saindo — a tela precisa dele para saber de quem
    é o microfone.

    CURA A ARRANCAR: o `and not recado.expirou(agora)` de `publicar`.
    """
    prazo = recado_do_microfone.VALIDADE_DO_RECADO_S

    class _EleitorCru:
        eleito = _J1

    class _Mesa:
        def describe_controllers(self) -> list[dict[str, Any]]:
            return [{"uniq": _J1, "connected": True}, {"uniq": _J2, "connected": True}]

    class _Cru:
        controller = _Mesa()
        _eleitor_de_microfone = _EleitorCru()

    cru = _Cru()
    recado_do_microfone.anotar(
        cru,  # type: ignore[arg-type]
        _J2,
        gesto="recusa",
        ok=False,
        motivo=recusa_de_quem_nao_elegeu(_J1).motivo,
        eleito=_J1,
        agora_s=0.0,
    )

    logo_depois = recado_do_microfone.publicar(cru, agora_s=0.5)
    assert _J2 in logo_depois["recados"], (
        "a frase tem de estar na tela no tique seguinte ao toque"
    )

    quase = recado_do_microfone.publicar(cru, agora_s=prazo - 0.5)
    assert _J2 in quase["recados"], (
        f"meio segundo antes do prazo a frase ainda vale: {quase}"
    )

    depois = recado_do_microfone.publicar(cru, agora_s=prazo + 0.5)
    assert depois["recados"] == {}, (
        "passado o prazo o recado SOME — campo sem informação não mostra nada, "
        f"que é a regra dela: {depois}"
    )
    assert depois["eleito"] == _J1, (
        "o AVISO expira; o ESTADO do canal não. Apagar o dono junto faria a "
        f"tela esquecer de quem é o microfone depois de meio minuto: {depois}"
    )
    assert depois["eleito_na_mesa"] is True

    meia_hora = recado_do_microfone.publicar(cru, agora_s=1800.0)
    assert meia_hora["recados"] == {}, (
        "era exatamente a frase de meia hora atrás com cara de agora"
    )


def test_o_prazo_filtra_e_nao_escreve_no_deposito() -> None:
    """`publicar` roda a 10 Hz no caminho de LEITURA: ele não mexe no estado.

    O módulo já recusou mexer aqui uma vez (o `getattr` que não instancia o
    eleitor). Jogar o recado fora não compra nada — quem limita a memória é o
    `TETO`, e o próximo toque daquele controle substitui a entrada.

    CURA A ARRANCAR: trocar o filtro por um `pop` dentro do laço de `publicar`.
    """

    class _Cru:
        pass

    cru = _Cru()
    recado_do_microfone.anotar(
        cru,  # type: ignore[arg-type]
        _J1,
        gesto="recusa",
        ok=False,
        motivo="qualquer",
        agora_s=0.0,
    )
    recado_do_microfone.publicar(cru, agora_s=1800.0)

    deposito = getattr(cru, recado_do_microfone.ATRIBUTO)
    assert _J1 in deposito, (
        "a leitura apagou o depósito: quem publica o estado não pode escrever "
        f"nele — {deposito}"
    )


# ---------------------------------------------------------------------------
# 15. O TERCEIRO DESFECHO DA VOLTA — a escrita PASSOU e o ativo é um TERCEIRO
# ---------------------------------------------------------------------------
#
# ACHADO DA AUDITORIA DE 02/09/2026, e o buraco era da RÉGUA antes de ser do
# produto: `_eleger_nome` tem QUATRO desfechos e TRÊS devolvem `ok=False`, mas
# nem `_EleitorDublado` nem a seção 13 montavam o terceiro — aquele em que o
# `pactl` ACEITA (`rc == 0`) e o ativo relido não é o alvo. A prova de que a
# régua não o alcançava: o auditor trocou a cura por duas semânticas OPOSTAS
# nesse ramo (`aceso` condicionado ao `ativo`, posse solta no `ativo`) e as 36
# passaram nas duas.
#
# E é o desfecho que MAIS importa: é o `eleicao_mic_nao_pegou`, o defeito que o
# módulo inteiro existe para pegar. Se a escrita pegou e o ativo virou um
# terceiro, aquele controle NÃO está no ar — e a luz não pode continuar acesa
# afirmando que está (contrato dela, 01/09: *"aceso = este mic está no ar"*).
#
# TODA esta seção usa o `EleitorDeMicrofone` DE VERDADE: o que se dubla são as
# quatro portas externas do módulo (`_rodar`, `fonte_se_sustenta`,
# `fonte_ativa`, `melhor_fonte_elegivel`) mais a resolução `uniq → canal`.
# Nenhum `pactl` roda, nenhum aparelho é tocado, nenhuma janela nasce.

_CANAL_DO_J1 = "alsa_input.o_canal_do_j1"
_DA_PLACA = "mic_da_placa_mae"
_DE_UM_TERCEIRO = "mic_de_um_terceiro"


class _PipeWireDublado:
    """As portas externas de `eleicao_de_microfone`, e só elas."""

    def __init__(self, monkey: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele

        self.escritas: list[list[str]] = []
        self.ativo: str | None = None
        self.sustenta: bool | None = True
        self.rc = 0
        monkey.setattr(ele, "_rodar", self._rodar)
        monkey.setattr(ele, "fonte_se_sustenta", lambda _nome: self.sustenta)
        monkey.setattr(ele, "fonte_ativa", lambda: self.ativo)
        monkey.setattr(ele, "melhor_fonte_elegivel", lambda: _DA_PLACA)
        monkey.setattr(
            ele, "fontes_de_captura_agora", lambda: [_CANAL_DO_J1, _DA_PLACA]
        )
        monkey.setattr(ele, "casamento_usb_agora", lambda _uniqs: None)
        monkey.setattr(ele, "escolher_fonte", lambda _f, _u, _a, _usb: _CANAL_DO_J1)
        # O assentamento é REAL, só que sem espera: zerar o passo mede o laço
        # de `_assentar_e_reler` de verdade sem trocar o `time` do processo,
        # que é global e pertence a quem rodar depois.
        monkey.setattr(ele, "SETTLE_PASSOS", 2)
        monkey.setattr(ele, "SETTLE_PASSO_S", 0.0)

    def _rodar(self, argv: list[str]) -> tuple[int, str]:
        self.escritas.append(list(argv))
        return self.rc, ""


def _eleitor_de_verdade(monkey: pytest.MonkeyPatch) -> tuple[Any, _PipeWireDublado]:
    """Um `EleitorDeMicrofone` do produto com o PipeWire de mentira."""
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele

    return ele.EleitorDeMicrofone(), _PipeWireDublado(monkey)


def _elege_a_j1(eleitor: Any, pipewire: _PipeWireDublado) -> None:
    """A J1 elege PELA PORTA DO PRODUTO, e a eleição é CONFERIDA.

    A posse tem de nascer como nasce em serviço: é a eleição conferida que
    grava o NOME do canal (`fonte_do_eleito`), e sem ele o produto não tem com
    o que comparar o ativo relido depois. Cravar `eleitor.eleito` na mão — como
    a seção 13 faz de propósito, para medir OUTRA coisa — nunca alcançaria
    este desfecho.
    """
    pipewire.ativo = _CANAL_DO_J1
    resultado = eleitor.eleger_o_controle(_J1, [_J1])
    assert resultado.ok is True, f"a eleição de partida não pegou: {resultado.motivo}"
    assert eleitor.eleito == _J1
    assert eleitor.fonte_do_eleito == _CANAL_DO_J1, (
        "a eleição conferida tem de guardar o NOME do canal, senão a volta "
        "não tem com o que comparar o ativo relido"
    )
    pipewire.escritas.clear()


def test_a_posse_cai_quando_a_escrita_passou_e_o_ativo_relido_e_um_terceiro() -> None:
    """Os QUATRO desfechos da volta, medidos um a um no eleitor do produto.

    A régua da posse era `resultado.ok`, e ela confunde três recusas muito
    diferentes. O que separa as três é a única pergunta que este módulo aceita:
    **o ativo RELIDO ainda é o canal deste controle?**

    CURA A ARRANCAR: `if self._o_eleito_saiu_do_ar(resultado):` de volta para
    `if resultado.ok:` em `devolver_o_microfone`. O caso do terceiro reprova.
    """
    casos = (
        # rótulo, rc, ativo depois, a posse cai?, escreveu?
        ("o pactl RECUSOU: a escrita não pegou", 1, _CANAL_DO_J1, False, True),
        ("o WirePlumber devolveu o canal à J1", 0, _CANAL_DO_J1, False, True),
        ("o ativo relido é ILEGÍVEL", 0, None, False, True),
        ("a escrita passou e o ativo é um TERCEIRO", 0, _DE_UM_TERCEIRO, True, True),
        ("a devolução foi CONFERIDA", 0, _DA_PLACA, True, True),
    )
    for rotulo, rc, ativo, cai, escreveu in casos:
        with pytest.MonkeyPatch.context() as monkey:
            eleitor, pipewire = _eleitor_de_verdade(monkey)
            _elege_a_j1(eleitor, pipewire)

            pipewire.rc = rc
            pipewire.ativo = ativo
            resultado = eleitor.devolver_o_microfone()

            assert bool(pipewire.escritas) is escreveu, (
                f"{rotulo}: o `set-default-source` — {pipewire.escritas}"
            )
            if cai:
                assert eleitor.eleito is None, (
                    f"{rotulo}: o ativo relido diz que o canal não é mais da "
                    f"J1, e a posse tinha de cair — {resultado.ativo!r}"
                )
                assert eleitor.fonte_do_eleito is None, (
                    f"{rotulo}: a posse caiu e o nome do canal ficou pendurado"
                )
            else:
                assert eleitor.eleito == _J1, (
                    f"{rotulo}: o padrão do sistema continua sendo o canal da "
                    f"J1, e a posse não podia cair — {resultado.ativo!r}"
                )


def test_o_ativo_ilegivel_nunca_vira_o_eleito_saiu_do_ar() -> None:
    """"Não sei" nunca vira "saiu" — a mesma regra do `None` de `mesa_de_agora`.

    Duas ignorâncias caem aqui: o ativo que não deu para ler, e a posse que
    veio de fora sem o nome do canal (teste antigo que crava `eleito` na mão,
    ou um eleitor que atravessou uma versão). Nas duas, soltar a posse seria
    declarar que o microfone saiu do ar por não termos conseguido perguntar.

    CURA A ARRANCAR: a linha
    `if resultado.ativo is None or self.fonte_do_eleito is None: return False`.
    """
    from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
        EleitorDeMicrofone,
        ResultadoDaEleicao,
    )

    sem_nome = EleitorDeMicrofone()
    sem_nome.eleito = _J1  # posse cravada na mão, sem o nome do canal
    assert (
        sem_nome._o_eleito_saiu_do_ar(
            ResultadoDaEleicao(ok=False, alvo=_DA_PLACA, ativo=_DE_UM_TERCEIRO)
        )
        is False
    ), "sem o nome do canal dele, não dá para saber se o ativo é outro"

    com_nome = EleitorDeMicrofone()
    com_nome.eleito = _J1
    com_nome.fonte_do_eleito = _CANAL_DO_J1
    assert (
        com_nome._o_eleito_saiu_do_ar(
            ResultadoDaEleicao(ok=False, alvo=_DA_PLACA, ativo=None)
        )
        is False
    ), "o ativo ilegível é ignorância, não notícia de que ele saiu do ar"
    assert (
        com_nome._o_eleito_saiu_do_ar(
            ResultadoDaEleicao(ok=False, alvo=_DA_PLACA, ativo=_DE_UM_TERCEIRO)
        )
        is True
    ), "o ativo relido é um terceiro: o canal deixou de ser dele"


@pytest.mark.asyncio
async def test_a_luz_apaga_quando_o_wireplumber_deu_o_canal_a_um_terceiro() -> None:
    """O laço do produto + o eleitor do produto: a LUZ e o `state_full`.

    É o par que a auditoria pediu: o MESMO payload dizia `eleito: …011` (o
    canal é dele) e `ativo: mic_de_um_terceiro` (o canal não é dele), com o
    plástico ACESO. Dois vereditos opostos no mesmo tique.

    CURA A ARRANCAR: `aceso = eleitor.eleito == uniq` de volta para
    `aceso = not bool(resultado.ok)` em `hotkey._eleger_ou_devolver`.
    """
    with pytest.MonkeyPatch.context() as monkey:
        eleitor, pipewire = _eleitor_de_verdade(monkey)
        backend = _Backend((_J1,))
        daemon = _Daemon(backend, eleitor)

        pipewire.ativo = _CANAL_DO_J1
        pipewire.rc = 0
        blocos = await _rodar_os_passos(
            daemon,
            [
                {"uniq": _J1, "mudo": False},
                lambda: setattr(pipewire, "ativo", _DE_UM_TERCEIRO),
                {"uniq": _J1, "mudo": True},
            ],
        )

    assert blocos[0]["eleito"] == _J1, (
        f"a eleição de partida tinha de nomear a J1: {blocos[0]}"
    )
    depois = blocos[-1]
    recado = depois["recados"][_J1]
    assert recado["ok"] is False and recado["ativo"] == _DE_UM_TERCEIRO, (
        f"a cena montada não é a do terceiro desfecho: {recado}"
    )
    assert depois["eleito"] is None, (
        "o ativo relido é um terceiro: a J1 não está mais com o microfone da "
        f"mesa, e o `state_full` não pode nomeá-la — {depois}"
    )
    assert backend.leds == {_J1: False}, (
        "o plástico afirmava 'estou no ar' sobre um canal que a própria "
        f"medição diz ser de um terceiro — {backend.leds}"
    )


@pytest.mark.asyncio
async def test_a_luz_fica_acesa_quando_o_wireplumber_devolveu_o_canal_a_ela() -> None:
    """O contra-caso, e é ele que impede a cura preguiçosa.

    `ok=False` com o ativo relido sendo o canal DELA quer dizer que o
    WirePlumber recusou a volta e deixou o microfone onde estava: ela continua
    no ar, logo a luz continua acesa. Uma cura que apagasse a luz em toda
    recusa com `ativo` preenchido passaria o teste de cima e reprovaria aqui.
    """
    with pytest.MonkeyPatch.context() as monkey:
        eleitor, pipewire = _eleitor_de_verdade(monkey)
        backend = _Backend((_J1,))
        daemon = _Daemon(backend, eleitor)

        pipewire.ativo = _CANAL_DO_J1
        blocos = await _rodar_os_passos(
            daemon,
            [{"uniq": _J1, "mudo": False}, {"uniq": _J1, "mudo": True}],
        )

    depois = blocos[-1]
    recado = depois["recados"][_J1]
    assert recado["ok"] is False and recado["ativo"] == _CANAL_DO_J1, (
        f"a cena montada não é a da volta recusada com o canal dela: {recado}"
    )
    assert depois["eleito"] == _J1, (
        f"o canal continua sendo dela, e a posse não podia cair — {depois}"
    )
    assert backend.leds == {_J1: True}, (
        f"o microfone dela continua no ar, logo a luz fica acesa — {backend.leds}"
    )


# ---------------------------------------------------------------------------
# 16. UMA LEITURA DA MESA POR TOQUE DE BOTÃO — não duas
# ---------------------------------------------------------------------------


class _BackendQueConta(_Backend):
    """Um `_Backend` que anota quantas vezes lhe perguntaram a mesa."""

    def __init__(self, uniqs: tuple[str, ...]) -> None:
        super().__init__(uniqs)
        self.perguntas = 0

    def describe_controllers(self) -> list[dict[str, Any]]:
        self.perguntas += 1
        return super().describe_controllers()


@pytest.mark.asyncio
async def test_o_toque_do_botao_le_a_mesa_uma_vez_so() -> None:
    """`conectados` era calculado ANTES do `if mudo:` e jogado fora no ramo mudo.

    Achado de FORMA da auditoria de 02/09/2026, e ele é sobre o arquivo cuja
    cura inteira se justifica por *"duas leituras do mesmo estado é o defeito
    que esta casa já pagou onze vezes"*. Desde que a recusa passou a perguntar
    a `recado_do_microfone.mesa_de_agora`, o ramo `mudo` não usava mais o
    `conectados` — e todo toque de botão pagava DOIS `describe_controllers()`,
    com duas aquisições do `_io_lock`, para descartar o primeiro.

    Não é defeito de comportamento; é caminho de BORDA, não os 10 Hz. Mas a
    régua existe porque a próxima pessoa vai reler o ramo e precisa saber se a
    leitura extra voltou.

    CURA A ARRANCAR: mover `conectados = _uniqs_conectados(daemon)` de volta
    para antes do `if mudo:`.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    # a) A RECUSA de quem não elegeu: uma leitura, a de `mesa_de_agora`.
    backend = _BackendQueConta((_J1, _J2))
    eleitor = _EleitorDublado()
    eleitor.eleito = _J1
    daemon = _Daemon(backend, eleitor)
    await hotkey._eleger_ou_devolver(daemon, _J2, True)  # type: ignore[arg-type]
    assert backend.perguntas == 1, (
        "o ramo da recusa precisa da mesa UMA vez — quem está na mesa AGORA. "
        f"Perguntou {backend.perguntas}"
    )

    # b) A DEVOLUÇÃO do eleito: nenhuma. `devolver_o_microfone()` é global.
    backend_b = _BackendQueConta((_J1,))
    eleitor_b = _EleitorDublado()
    eleitor_b.eleito = _J1
    daemon_b = _Daemon(backend_b, eleitor_b)
    await hotkey._eleger_ou_devolver(daemon_b, _J1, True)  # type: ignore[arg-type]
    assert backend_b.perguntas == 0, (
        "a devolução não pergunta a mesa a ninguém: `devolver_o_microfone()` "
        f"não recebe `uniq`. Perguntou {backend_b.perguntas}"
    )

    # c) A ELEIÇÃO: uma, e é a lista de quem PODE ser eleito.
    backend_c = _BackendQueConta((_J1, _J2))
    daemon_c = _Daemon(backend_c, _EleitorDublado())
    await hotkey._eleger_ou_devolver(daemon_c, _J1, False)  # type: ignore[arg-type]
    assert backend_c.perguntas == 1, (
        "a eleição precisa da lista de quem pode ser eleito, e de uma só vez. "
        f"Perguntou {backend_c.perguntas}"
    )


# ---------------------------------------------------------------------------
# 17. O CAMINHO DE IDA TAMBÉM MEDE O ATIVO — e quem perde o canal é OUTRO
# ---------------------------------------------------------------------------
#
# ACHADO DA SEGUNDA AUDITORIA DE 02/09/2026. A seção 15 fechou o
# `eleicao_mic_nao_pegou` no caminho de VOLTA: a devolução que escreve e vê o
# ativo virar um terceiro solta a posse e apaga a luz. O caminho de IDA ficou
# com a metade velha da régua — `eleger_por_uniq` só sabia dizer *"não foi
# você"*, e nunca perguntava se ainda era do OUTRO.
#
# O sujeito é o que muda, e é o que torna este defeito pior que o da volta:
# quem perde o microfone não é quem apertou o botão. A J1 está jogando, não
# tocou em nada, e o gesto do J2 tira o canal dela — o produto escreveu
# `set-default-source` para o J2, o WirePlumber reelegeu um terceiro por cima e
# ninguém ficou com o canal. O `state_full` seguia publicando `eleito: …011` e
# o plástico da J1 seguia ACESO, os dois afirmando *"estou no ar"*.
#
# Reproduzido com o eleitor DO PRODUTO e o `pactl` dublado, antes da cura:
#
#     eleito_DEPOIS ......... aabbcc000011
#     ativo_do_sistema_agora  alsa_input.pci-0000_00_1f.3.analog-stereo
#     MENTIRA ............... true

_CANAL_DO_J2 = "alsa_input.o_canal_do_j2"


def _eleitor_de_verdade_com_dois(
    monkey: pytest.MonkeyPatch,
) -> tuple[Any, _PipeWireDublado]:
    """Como `_eleitor_de_verdade`, mas com DOIS canais atribuíveis.

    O `_PipeWireDublado` crava `escolher_fonte` no canal da J1 — basta para as
    cenas de um controle só, e é cegueira nas de dois: sem esta troca o J2
    elegeria o canal DELA, que é outro defeito e não o que se mede aqui.
    """
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele

    eleitor, pipewire = _eleitor_de_verdade(monkey)
    canais = {_J1: _CANAL_DO_J1, _J2: _CANAL_DO_J2}
    monkey.setattr(ele, "escolher_fonte", lambda _f, u, _a, _usb: canais.get(u))
    monkey.setattr(
        ele, "fontes_de_captura_agora", lambda: [_CANAL_DO_J1, _CANAL_DO_J2]
    )
    return eleitor, pipewire


def test_a_posse_do_dono_cai_quando_o_gesto_de_outro_tira_o_canal_dele() -> None:
    """Os SEIS desfechos da IDA, medidos um a um no eleitor do produto.

    A pergunta é sempre a mesma — **o ativo RELIDO ainda é o canal do
    eleito?** — e ela não depende de qual gesto a provocou. Tratar toda eleição
    fracassada como "nada mudou" é o que deixava a posse da J1 de pé depois de
    o próprio produto ter tirado o canal dela.

    CURA A ARRANCAR: o ramo `elif self._o_eleito_saiu_do_ar(resultado):` de
    `eleger_por_uniq`. Só a linha do TERCEIRO reprova — as outras cinco existem
    para impedir a cura preguiçosa que solta a posse em toda recusa.
    """
    casos = (
        # rótulo, sustenta, rc, ativo depois, dono no fim
        (
            "a fonte do J2 não se sustenta: nada foi escrito",
            False,
            0,
            _CANAL_DO_J1,
            _J1,
        ),
        ("o pactl RECUSOU: a escrita não pegou", True, 1, _CANAL_DO_J1, _J1),
        ("o WirePlumber devolveu o canal à J1", True, 0, _CANAL_DO_J1, _J1),
        ("o ativo relido é ILEGÍVEL", True, 0, None, _J1),
        ("a escrita passou e o ativo é um TERCEIRO", True, 0, _DE_UM_TERCEIRO, None),
        ("a eleição do J2 foi CONFERIDA", True, 0, _CANAL_DO_J2, _J2),
    )
    for rotulo, sustenta, rc, ativo, dono in casos:
        with pytest.MonkeyPatch.context() as monkey:
            eleitor, pipewire = _eleitor_de_verdade_com_dois(monkey)
            _elege_a_j1(eleitor, pipewire)

            pipewire.sustenta = sustenta
            pipewire.rc = rc
            pipewire.ativo = ativo
            resultado = eleitor.eleger_o_controle(_J2, [_J1, _J2])

            assert eleitor.eleito == dono, (
                f"{rotulo}: o dono do microfone tinha de ser {dono!r} e é "
                f"{eleitor.eleito!r} — ativo relido {resultado.ativo!r}"
            )
            if dono is None:
                assert eleitor.fonte_do_eleito is None, (
                    f"{rotulo}: a posse caiu e o nome do canal ficou pendurado"
                )


@pytest.mark.asyncio
async def test_a_luz_da_j1_apaga_quando_o_gesto_do_j2_tira_o_canal_dela() -> None:
    """O laço do produto + o eleitor do produto, com DOIS controles na mesa.

    É a cena inteira: a J1 no ar, o J2 aperta, a escrita PASSA e o WirePlumber
    reelege um terceiro. Ninguém ficou com o canal — e as três superfícies têm
    de dizer a mesma coisa: o `state_full` sem dono, o plástico do J2 apagado
    (ele não ganhou nada) e o plástico da J1 apagado (ela perdeu o que tinha).

    CURA A ARRANCAR: qualquer metade. Sem o ramo de `eleger_por_uniq` o
    `eleito` volta a ser a J1; sem a chamada a
    `_apagar_a_luz_de_quem_perdeu_o_canal` a luz dela fica acesa.
    """
    with pytest.MonkeyPatch.context() as monkey:
        eleitor, pipewire = _eleitor_de_verdade_com_dois(monkey)
        backend = _Backend((_J1, _J2))
        daemon = _Daemon(backend, eleitor)

        pipewire.ativo = _CANAL_DO_J1
        blocos = await _rodar_os_passos(
            daemon,
            [
                {"uniq": _J1, "mudo": False},
                lambda: setattr(pipewire, "ativo", _DE_UM_TERCEIRO),
                {"uniq": _J2, "mudo": False},
            ],
        )

    assert blocos[0]["eleito"] == _J1, (
        f"a eleição de partida tinha de nomear a J1: {blocos[0]}"
    )
    depois = blocos[-1]
    recado = depois["recados"][_J2]
    assert recado["ok"] is False and recado["ativo"] == _DE_UM_TERCEIRO, (
        f"a cena montada não é a do terceiro desfecho: {recado}"
    )
    assert depois["eleito"] is None, (
        "o produto escreveu e o ativo relido é um terceiro: o canal não é mais "
        f"da J1, e o `state_full` não pode nomeá-la — {depois}"
    )
    assert backend.leds == {_J1: False, _J2: False}, (
        "a J1 não tocou em nada e perdeu o canal; o plástico dela não pode "
        f"continuar afirmando 'estou no ar' — {backend.leds}"
    )


@pytest.mark.asyncio
async def test_a_luz_da_j1_apaga_quando_o_j2_ganha_o_canal_de_verdade() -> None:
    """A troca de turno que FUNCIONA — e ela tinha o mesmo defeito de luz.

    O J2 elege e a eleição é CONFERIDA: o canal é dele, e o contrato dela diz
    *"aceso = este mic está no ar"*. A J1 não está mais no ar. Este laço
    acendia e apagava só a luz de quem apertou o botão, então o plástico dela
    ficava aceso ao lado do dele, os dois dizendo a mesma coisa sobre um canal
    que é de um só.
    """
    with pytest.MonkeyPatch.context() as monkey:
        eleitor, pipewire = _eleitor_de_verdade_com_dois(monkey)
        backend = _Backend((_J1, _J2))
        daemon = _Daemon(backend, eleitor)

        pipewire.ativo = _CANAL_DO_J1
        blocos = await _rodar_os_passos(
            daemon,
            [
                {"uniq": _J1, "mudo": False},
                lambda: setattr(pipewire, "ativo", _CANAL_DO_J2),
                {"uniq": _J2, "mudo": False},
            ],
        )

    assert blocos[-1]["eleito"] == _J2, (
        f"a eleição do J2 foi conferida e ele é o dono: {blocos[-1]}"
    )
    assert backend.leds == {_J1: False, _J2: True}, (
        f"o canal é do J2; só o plástico dele pode estar aceso — {backend.leds}"
    )


@pytest.mark.asyncio
async def test_a_luz_da_j1_fica_acesa_quando_o_wireplumber_devolveu_o_canal_a_ela() -> (
    None
):
    """O contra-caso que impede a cura preguiçosa — e ele é o mais comum.

    O J2 aperta, a escrita passa, e o WirePlumber devolve o canal à J1 (é o que
    ele faz quando o nó do J2 não se sustenta). Ela continua no ar: a posse
    fica, a luz dela fica acesa, e só a do J2 apaga. Uma cura que apagasse a
    luz do dono anterior em toda eleição fracassada passaria os dois testes de
    cima e reprovaria aqui.
    """
    with pytest.MonkeyPatch.context() as monkey:
        eleitor, pipewire = _eleitor_de_verdade_com_dois(monkey)
        backend = _Backend((_J1, _J2))
        daemon = _Daemon(backend, eleitor)

        pipewire.ativo = _CANAL_DO_J1
        blocos = await _rodar_os_passos(
            daemon,
            [{"uniq": _J1, "mudo": False}, {"uniq": _J2, "mudo": False}],
        )

    assert blocos[-1]["eleito"] == _J1, (
        f"o canal continua sendo dela, e a posse não podia cair — {blocos[-1]}"
    )
    assert backend.leds == {_J1: True, _J2: False}, (
        "o microfone dela continua no ar, logo a luz dela fica acesa; e o J2 "
        f"não ganhou nada, logo a dele apaga — {backend.leds}"
    )
