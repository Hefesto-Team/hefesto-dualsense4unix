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
        # A POSSE CAI MESMO SEM DESTINO — o contrato do módulo de verdade
        # (`eleicao_de_microfone.devolver_o_microfone`), inclusive no ramo que
        # NÃO conseguiu devolver. Um dublê que só zerasse no sucesso esconderia
        # a quinta frase, que é justamente a que nasce do fracasso.
        self.eleito = None
        if self._devolve_ok:
            return _Resultado(ok=True, ativo="mic_da_placa_mae")
        return _Resultado(ok=False, motivo=self._motivo_da_devolucao)


class _Backend:
    """Backend com a mesa toda e o LED de cada plástico."""

    def __init__(self, uniqs: tuple[str, ...]) -> None:
        self.uniqs = list(uniqs)
        self.leds: dict[str, bool] = {}

    def sair_da_mesa(self, uniq: str) -> None:
        """O hotplug-out: o controle deixa de aparecer no `describe_controllers`.

        É exatamente o que o backend faz quando o cabo sai ou o rádio cai — e é
        o único caminho por onde este defeito chega à tela, porque nenhuma
        borda de botão acompanha um controle que sumiu.
        """
        self.uniqs = [u for u in self.uniqs if u != uniq]

    def is_connected(self) -> bool:
        return bool(self.uniqs)

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True} for u in self.uniqs]

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
    daemon, _backend, eleitor = _mesa(
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
    assert bloco["eleito"] is None, (
        "a posse cai mesmo sem destino (contrato de `devolver_o_microfone`), e "
        "a tela tem de ver isso"
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
