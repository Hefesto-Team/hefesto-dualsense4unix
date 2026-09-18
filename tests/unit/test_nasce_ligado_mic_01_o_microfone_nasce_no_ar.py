"""NASCE-LIGADO-MIC-01 — o microfone nasce NO AR, sem gesto nenhum dela.

**A QUEIXA, 17/09/2026**, com as palavras dela e sem corrigi-las:

    *"segue por default mudo. eu preciso lembrar de clicar no icon do mic pra
    ativar e ele ser reconhecido. isso deveria ta  # (noqa-acento) dela
    ativado por padrao"*  # (noqa-acento) dela, 17/09/2026

E é a TERCEIRA vez que ela pede: `docs/data/decisoes-dela.csv` id 37
(D-AUDIO-E-GIRO-NASCEM-LIGADOS) e id 38 (D-O-MIC-LIGADO-VALE-NO-RADIO), as duas
de 25/08/2026 — *"LIGADO SEMPRE, NOS DOIS TRANSPORTES, COM A TELA DIZENDO O
PREÇO… o que caduca é o padrão desligado"*.

O BURACO QUE ESTA RÉGUA OCUPA
------------------------------------------------------------------------------
Medido antes de escrevê-la: **nenhuma régua desta casa perguntava qual é o
estado do microfone DEPOIS DE CONECTAR E ANTES DE QUALQUER GESTO.** As que
existem medem o gesto e as portas de saída do latch —
`test_o_gesto_dela_poe_o_microfone_no_ar` mede a costura ato → palavra → `0x32`,
`test_mic_fase_01_…` mede o PRIMEIRO APERTO, `test_os_quatro_microfones_ficam_no_ar`
mede quatro no ar depois de quatro atos. Todas começam com um dedo dela no
plástico ou um clique no 🎙. A chegada não tinha dono.

O QUE SE AFIRMA, E POR QUE SÃO QUATRO COISAS E NÃO UMA
------------------------------------------------------------------------------
O estado do microfone é feito de quatro pedaços que nascem vazios, e meia cura
aqui pinta uma tela que mente::

    o pedaço                        quem o lê             o que falha sem ele
    ------------------------------  --------------------  ---------------------
    `PEDIDOS.abertos()`             `BtMicSubsystem.      a ponte do rádio não
                                     alvos()`, e o        sobe, e no CABO o
                                     `_reconciliar_o_cabo`  `hefesto_mic_<hex6>`
                                                          não é publicado
    `PEDIDOS.no_ar()`               `PonteMicBluetooth`   o nó sobe e o `0x32`
                                                          sai DESLIGADO — é o
                                                          journal dela às
                                                          10:33:27
    `MicrofonesNoAr`                `_ler_o_canal_deste`  o chip do cartão
                                                          continua dizendo MUDO
    `canal_ativo` do selo           `a02_controles.       a face que ela vê
                                     _faces_do_microfone`

Por isso cada um tem um caso PRÓPRIO, com a frase dizendo QUAL faltou: uma
afirmação só passaria com três quartos da cura no lugar.

A SEGUNDA MORDIDA, e é onde a cura vira defeito com o sinal trocado
------------------------------------------------------------------------------
"Estar no ar" é de cada controle, os quatro juntos; "ser a fonte padrão da
máquina" é de UM só (OS-QUATRO-NO-AR-01). Um nascimento que chamasse a eleição
para todo mundo faria o ÚLTIMO controle a conectar tomar a fonte padrão dela —
e o microfone real dela sairia do caminho sem ela ter tocado em nada. Por isso
`TestAMesaComDono` prova que o segundo a nascer **não mexe em `eleitor.eleito`**.

E A TERCEIRA: O SILÊNCIO DELA VENCE
------------------------------------------------------------------------------
`pragmata.json`, na mesa dela, tem `mic.muted: true`. Um nascimento que
ignorasse isso reabriria o microfone de quem pediu silêncio — a SOM-MIC-REPLUG-01
(*"o silêncio que o produto promete e não entrega"*) voltando pela porta da
frente. São DOIS caminhos de silêncio e os dois têm caso: o perfil ativo e o
bit do mudo já aceso no aparelho.

A MORDIDA, ARRANCADA UMA A UMA E MEDIDA (17/09/2026)
------------------------------------------------------------------------------
Cada pedaço da cura foi removido, a régua rodada, e o vermelho anotado::

  o que se arranca                              o que reprova
  --------------------------------------------  ---------------------------
  a linha `nascer_o_microfone_ao_conectar` de    `test_o_replug_de_todos_os_
  `connection.reaplicar_som_em_todos_os_alvos`   alvos…` + `test_a_conexao_
                                                 nao_espera_o_nascimento`
  `dizer_no_ar(uniq, True)` do ramo sem eleição  `test_a_palavra_dela_e_dita_
                                                 sem_roubar_o_padrao` + o do
                                                 replug
  `no_ar.entrou(uniq)` do mesmo ramo             `test_o_segundo_entra_no_ar`
                                                 + `test_o_selo_do_segundo_
                                                 le_ativo` + o do replug
  a condição `_eleitor(daemon).eleito is None`   `test_o_segundo_nao_rouba_a_
  trocada por `True`                             fonte_padrao` + os outros 3
  a guarda `_o_perfil_pede_silencio`             `test_o_perfil_que_pede_
                                                 silencio_impede_o_nascimento`
  a guarda `_o_firmware_esta_mudo`               `test_o_bit_do_mudo_ja_aceso_
                                                 impede_o_nascimento`
  o `async with _fila_do_nascimento(daemon)`     `test_dois_nascimentos_ao_
                                                 mesmo_tempo_elegem_um_so` + o
                                                 do replug

**E UMA ARRANCADA QUE NÃO MORDEU — o achado desta mordida.** A primeira escrita
da cura chamava `pedir_canal(uniq)` antes dos dois ramos; arrancá-la deixou a
régua INTEIRA verde. A razão está no dono: `BtMicSubsystem.no_ar` pede o canal
junto quando a palavra é `True` (*"sem ponte de pé não há a quem entregar a
palavra"*), então aquela linha era uma segunda porta para o mesmo ato — a
família de defeito que esta casa mais paga. Ela SAIU, e
`test_o_canal_deste_controle_e_pedido` continua valendo: ele mede que o canal
FICA pedido, não por qual porta.

Os endereços são SINTÉTICOS e mascarados (octetos 4 e 5 zerados): endereço real
da bancada dela não entra em arquivo versionado, e há dois portões sobre isso.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
)
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm
from hefesto_dualsense4unix.profiles import manager as mgr

#: O primeiro controle da mesa dela, na grafia do plástico (sem dois-pontos).
P1 = "aabbcc000011"

#: O segundo — a mesa de dois é o que separa "no ar" de "fonte padrão".
P2 = "aabbcc000022"


# ---------------------------------------------------------------------------
# Os dublês
# ---------------------------------------------------------------------------


class _Resultado:
    """O que `eleger_o_controle`/`devolver_o_microfone` devolvem."""

    def __init__(self, *, ok: bool, ativo: str | None = None, motivo: str = "") -> None:
        self.ok = ok
        self.ativo = ativo
        self.motivo = motivo


class _EleitorDublado:
    """`EleitorDeMicrofone` de bancada, com o MESMO contrato do campo `eleito`.

    Ele só passa a valer o `uniq` na eleição CONFERIDA, como o produto. Um
    dublê que zerasse sempre seria mais frouxo que o real, e é assim que esta
    casa já deu verde sobre defeito vivo.
    """

    def __init__(self, *, elege_ok: bool = True) -> None:
        self.chamadas: list[tuple[str, Any]] = []
        self.eleito: str | None = None
        self.fonte_do_eleito: str | None = None
        self._elege_ok = elege_ok

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> _Resultado:
        del conectados
        self.chamadas.append(("eleger", uniq))
        if not self._elege_ok:
            return _Resultado(ok=False, motivo="a bancada recusou de propósito")
        self.eleito = uniq
        self.fonte_do_eleito = f"hefesto_mic_{uniq[-6:]}"
        return _Resultado(ok=True, ativo=self.fonte_do_eleito)

    def devolver_o_microfone(self) -> _Resultado:
        self.chamadas.append(("devolver", None))
        self.eleito = None
        return _Resultado(ok=True, ativo="mic_da_placa_mae")

    def eleger_por_uniq(self, uniq: str, **_kw: Any) -> _Resultado:
        return self.eleger_o_controle(uniq, [])


class _Backend:
    """O mínimo do backend que o nascimento e a eleição tocam.

    `audio_status_for` devolve o que o FIRMWARE publica, e ele nasce ABERTO —
    é o `microphone_led_repintado mudo=False` do journal dela. Um dublê que
    nascesse mudo esconderia a premissa da queixa inteira.
    """

    def __init__(self, uniqs: tuple[str, ...] = (P1,), *, mudo: bool = False) -> None:
        self.uniqs = list(uniqs)
        self._mudo = dict.fromkeys(uniqs, mudo)
        self.leds: dict[str, bool] = {}

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True} for u in self.uniqs]

    def alvos_conectados(self) -> dict[str, str | None]:
        return {f"hidraw{i}": u for i, u in enumerate(self.uniqs)}

    def is_connected(self) -> bool:
        return bool(self.uniqs)

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        if uniq not in self._mudo:
            return None
        return {"fone_plugado": False, "mic_externo": False,
                "mic_mudo": self._mudo[uniq]}

    def calar_no_firmware(self, uniq: str) -> None:
        """O dedo dela no botão do plástico ANTES de o daemon ver o controle."""
        self._mudo[uniq] = True

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:
        self.leds[uniq or "<sem endereço>"] = bool(aceso)

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        if uniq in self._mudo and muted is not None:
            self._mudo[uniq] = bool(muted)
        return True


class _Store:
    def __init__(self, ativo: str | None = None) -> None:
        self.active_profile = ativo


class _Config:
    """O pedaço do `DaemonConfig` que a recusa lê: `bt_mic_recusados`, chamável."""

    def __init__(self, recusados: Any) -> None:
        self.bt_mic_recusados = recusados


class _Daemon:
    """O mínimo do daemon que o nascimento toca.

    **`_run_blocking` NÃO ACEITA KEYWORDS**, que é a assinatura do daemon real
    (`daemon/lifecycle.py`). Um dublê com `**kw` é mais frouxo que o produto.
    """

    def __init__(
        self,
        backend: _Backend,
        eleitor: _EleitorDublado,
        *,
        store: _Store | None = None,
    ) -> None:
        self.bus = EventBus()
        self.controller = backend
        self._eleitor_de_microfone = eleitor
        if store is not None:
            self.store = store

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch):
    """A mesa: o REGISTRO e o SUBSYSTEM de verdade atrás dos ganchos.

    **O registro não é dublado, e é o ponto.** `RegistroDePedidosDeCanal` é
    quem guarda os dois valores de nascimento desta queixa (`_abertos` e
    `_no_ar`), e os ganchos são as MESMAS portas públicas que
    `BtMicSubsystem._instalar_o_gancho_da_procura` instala no daemon vivo.
    Dublá-las mediria a régua, não o produto.

    O `BtMicSubsystem` nasce sem `start()`, então `_aplicar_a_palavra_dela`
    sai pela porta (`_gerenciador is None`): a ponte de rádio não é desta
    régua, e ela já tem dono em `test_o_microfone_pelo_radio_alimenta_o_no`.
    """

    class Mesa:
        def __init__(self) -> None:
            self.registro = RegistroDePedidosDeCanal()
            self.subsystem = BtMicSubsystem(registro=self.registro)
            #: A resposta de `outra_captura_elegivel`: `None` é a mesa DELA,
            #: em que o único microfone com porta usável é o do controle.
            self.outro_microfone: str | None = None

        def daemon(
            self,
            uniqs: tuple[str, ...] = (P1,),
            *,
            elege_ok: bool = True,
            mudo_no_firmware: bool = False,
            perfil_ativo: str | None = None,
            recusados: frozenset[str] = frozenset(),
        ) -> _Daemon:
            self.backend = _Backend(uniqs, mudo=mudo_no_firmware)
            self.eleitor = _EleitorDublado(elege_ok=elege_ok)
            store = _Store(perfil_ativo) if perfil_ativo is not None else None
            daemon = _Daemon(self.backend, self.eleitor, store=store)
            # A fonte CHAMÁVEL da recusa, como `lifecycle` a fia sobre o
            # `maquina.json` — e a mesma que o subsystem lê.
            daemon.config = _Config(lambda: recusados)
            self.subsystem._config = daemon.config
            return daemon

    m = Mesa()
    # "EXISTE OUTRO MICROFONE NA MÁQUINA?" É DUBLADO NO DONO, e é obrigatório:
    # sem isto o nascimento perguntaria ao `pactl` de QUEM RODA A SUÍTE, e a
    # régua mediria a máquina — verde na mesa dela, vermelha num PC com
    # headset. `_dualsense_mic_intended` não precisa de dublê: o lar de
    # mentira da suíte não tem drop-in nem marca, e ele responde "não pediu".
    monkeypatch.setattr(elm, "outra_captura_elegivel", lambda: m.outro_microfone)
    anterior_pedidor = elm.registrar_pedidor_de_canal(m.subsystem.pedir_canal)
    anteriores_palavra = elm.registrar_dizedor_do_no_ar(
        m.subsystem.no_ar, m.subsystem.esquecer_a_palavra, m.subsystem.palavra_no_ar
    )
    # O SELO LÊ O PIPEWIRE, e o PipeWire não é desta régua. O que se dubla é a
    # LEITURA (`_ler_o_canal`), com a fonte publicada e `canal_ativo=False` —
    # que é o estado exato de quem tem canal e NÃO é a fonte padrão. Quem tem
    # de acender a face é `_ler_o_canal_deste`, lendo o `MicrofonesNoAr`.
    monkeypatch.setattr(
        hotkey,
        "_ler_o_canal",
        lambda uniq: {
            "fonte": f"hefesto_mic_{uniq[-6:]}",
            "canal_ativo": False,
            "canal_mudo": False,
            "volume_captura": 100,
        },
    )
    try:
        yield m
    finally:
        elm.registrar_pedidor_de_canal(anterior_pedidor)
        elm.registrar_dizedor_do_no_ar(*anteriores_palavra)


def _perfil(mic: dict | None = None, por_peca: dict | None = None):
    """Um perfil real do esquema — `match` e `button_toggles_system` são exigidos."""
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    dados: dict[str, Any] = {"name": "o-perfil-dela", "match": MatchManual()}
    if mic is not None:
        dados["mic"] = {"button_toggles_system": False, **mic}
    if por_peca is not None:
        dados["controllers"] = por_peca
    return Profile(**dados)


async def _esperar_os_nascimentos() -> None:
    """Espera as tarefas que o caminho da conexão soltou.

    O nascimento corre num FIO PRÓPRIO de propósito — ver
    `agendar_o_nascimento_do_microfone` —, então a régua que mede a fiação
    tem de esperar. Um `sleep(0)` solto mediria o instante e daria verde
    intermitente.
    """
    for _ in range(50):
        em_voo = [t for t in hotkey._NASCIMENTOS_EM_VOO if not t.done()]
        if not em_voo:
            break
        await asyncio.gather(*em_voo, return_exceptions=True)
    await asyncio.sleep(0)


# ===========================================================================
# 1. A MESA SEM DONO — o primeiro a chegar nasce no ar E vira a fonte padrão
# ===========================================================================


class TestONascimentoComAMesaSemDono:
    """*"ele ser reconhecido"* — a mesa vazia é o único caso em que se elege."""

    @pytest.mark.asyncio
    async def test_o_canal_deste_controle_e_pedido(self, mesa) -> None:
        """Sem o pedido a ponte não sobe, e no CABO o nó nem é publicado.

        `_reconciliar_o_cabo` monta a lista com `self._registro.abertos()` — a
        declaração do `maquina.json` não entra lá. Este pedido é o que faz o
        `hefesto_mic_<hex6>` do fio existir sem ela ter clicado em nada.

        **MEDE O ESTADO, NÃO A PORTA.** Quem escreve o pedido é
        `BtMicSubsystem.no_ar`, por dentro da palavra — ver a mordida no
        cabeçalho deste arquivo. Afirmar a CHAMADA em vez do registro travaria
        a implementação de hoje e deixaria passar a que importa.
        """
        daemon = mesa.daemon()
        assert mesa.registro.abertos() == frozenset(), "a cena começou suja"

        assert await hotkey.nascer_no_ar(daemon, P1) is True

        assert P1 in mesa.registro.abertos(), (
            "o canal deste controle não foi pedido no nascimento — "
            "a ponte do rádio não sobe e o nó do cabo não é publicado"
        )

    @pytest.mark.asyncio
    async def test_a_palavra_dela_e_dita(self, mesa) -> None:
        """Sem a palavra o nó sobe e o `0x32` sai DESLIGADO.

        É o `bt_mic_pedido ligar=False seq=1` do journal dela às 10:33:27, 34 ms
        depois de a source ser publicada.
        """
        daemon = mesa.daemon()

        await hotkey.nascer_no_ar(daemon, P1)

        assert mesa.registro.no_ar().get(P1) is True, (
            "a palavra dela não foi dita no nascimento — o nó sobe e o "
            "aparelho fica mudo, que é a queixa inteira"
        )

    @pytest.mark.asyncio
    async def test_entra_no_ar(self, mesa) -> None:
        """Sem isto o chip do cartão continua dizendo MUDO sobre um mic no ar."""
        daemon = mesa.daemon()

        await hotkey.nascer_no_ar(daemon, P1)

        assert hotkey._no_ar_da_sessao(daemon).esta(P1), (
            "o controle não entrou no `MicrofonesNoAr` — `canal_ativo` fica "
            "`False` e o selo pinta MUDO"
        )

    @pytest.mark.asyncio
    async def test_o_selo_le_ativo(self, mesa) -> None:
        """A face que ELA vê, lida pelo caminho do produto.

        `_ler_o_canal_deste` é o que alimenta o `canal_ativo` do `state_full`,
        e `_faces_do_microfone` pinta o chip a partir dele. Com a fonte
        publicada e o controle no ar, ele tem de acender mesmo sem ser o
        padrão do sistema.
        """
        daemon = mesa.daemon()

        await hotkey.nascer_no_ar(daemon, P1)
        lido = await hotkey._ler_o_canal_deste(daemon, P1)

        assert lido["canal_ativo"] is True, (
            "o selo da aba Controles continua lendo MUDO depois do nascimento"
        )

    @pytest.mark.asyncio
    async def test_elege_a_fonte_padrao_da_maquina(self, mesa) -> None:
        """*"e ele ser reconhecido"*: com a mesa sem dono, o primeiro elege."""
        daemon = mesa.daemon()

        await hotkey.nascer_no_ar(daemon, P1)

        assert mesa.eleitor.eleito == P1, (
            "o primeiro controle da mesa não virou a fonte padrão — ela "
            "continua tendo de clicar no 🎙 para ser ouvida"
        )

    @pytest.mark.asyncio
    async def test_nao_escreve_o_bit_do_mudo_no_firmware(self, mesa) -> None:
        """A TRAVA MEDIDA: tomar a posse do `common[9]` mata o botão dela.

        Está escrito em `hotkey._o_que_a_borda_pede` e em `_metade_do_firmware`:
        enquanto a posse for nossa, o botão do plástico deixa de valer. E é
        desnecessário — o firmware já nasce ABERTO.
        """
        daemon = mesa.daemon()
        escritas: list[Any] = []
        mesa.backend.set_microphone_mute = (  # type: ignore[method-assign]
            lambda muted, *, uniq=None: escritas.append((muted, uniq)) or True
        )

        await hotkey.nascer_no_ar(daemon, P1)

        assert not [e for e in escritas if e[0] is not None], (
            f"o nascimento escreveu o bit do mudo no firmware ({escritas}) — "
            "a posse fica nossa e o botão do plástico dela para de valer"
        )

    @pytest.mark.asyncio
    async def test_sem_endereco_nao_nasce_nada(self, mesa) -> None:
        """Sem chave não há dono: um pedido fantasma que ninguém solta."""
        daemon = mesa.daemon()

        assert await hotkey.nascer_no_ar(daemon, "") is False
        assert mesa.registro.abertos() == frozenset()
        assert mesa.registro.no_ar() == {}


# ===========================================================================
# 2. A MESA COM DONO — os outros nascem no ar e NÃO roubam a fonte padrão
# ===========================================================================


class TestAMesaComDono:
    """A metade de PRIVACIDADE, e é onde a cura vira defeito com sinal trocado."""

    @pytest.mark.asyncio
    async def test_o_segundo_nao_rouba_a_fonte_padrao(self, mesa) -> None:
        """Com quatro na mesa, o último a conectar tomaria o microfone dela.

        A condição é a que já existia (`_o_que_a_borda_pede`: *"a mesa sem
        dono"*), e reusá-la é o que garante que nenhuma segunda régua sobre a
        posse nasça aqui.
        """
        daemon = mesa.daemon((P1, P2))

        await hotkey.nascer_no_ar(daemon, P1)
        assert mesa.eleitor.eleito == P1
        await hotkey.nascer_no_ar(daemon, P2)

        assert mesa.eleitor.eleito == P1, (
            "o segundo controle a nascer tomou a fonte padrão do primeiro — "
            "com quatro na mesa, o microfone dela sai do caminho sozinho"
        )
        assert [c for c in mesa.eleitor.chamadas if c[1] == P2] == [], (
            "o nascimento do segundo chamou a eleição — ela escreve "
            "`set-default-source` na máquina dela"
        )

    @pytest.mark.asyncio
    async def test_o_segundo_entra_no_ar(self, mesa) -> None:
        """Não roubar o padrão não pode custar o AR: os quatro ficam juntos."""
        daemon = mesa.daemon((P1, P2))

        await hotkey.nascer_no_ar(daemon, P1)
        assert await hotkey.nascer_no_ar(daemon, P2) is True

        no_ar = hotkey._no_ar_da_sessao(daemon)
        assert no_ar.esta(P1) and no_ar.esta(P2), (
            f"os dois não ficaram no ar juntos: {no_ar.todos()}"
        )

    @pytest.mark.asyncio
    async def test_a_palavra_dela_e_dita_sem_roubar_o_padrao(self, mesa) -> None:
        """O `0x32` do SEGUNDO tem de acender igual — ele também transmite."""
        daemon = mesa.daemon((P1, P2))

        await hotkey.nascer_no_ar(daemon, P1)
        await hotkey.nascer_no_ar(daemon, P2)

        assert mesa.registro.no_ar().get(P2) is True, (
            "o segundo nasceu no ar sem a palavra — o nó dele sobe mudo"
        )
        assert P2 in mesa.registro.abertos(), (
            "o canal do segundo não foi pedido"
        )

    @pytest.mark.asyncio
    async def test_o_selo_do_segundo_le_ativo(self, mesa) -> None:
        """Com dois no ar, o cartão do que NÃO é o padrão dizia MUDO."""
        daemon = mesa.daemon((P1, P2))

        await hotkey.nascer_no_ar(daemon, P1)
        await hotkey.nascer_no_ar(daemon, P2)
        lido = await hotkey._ler_o_canal_deste(daemon, P2)

        assert lido["canal_ativo"] is True, (
            "o cartão do segundo controle lê MUDO sobre um microfone no ar"
        )

    @pytest.mark.asyncio
    async def test_dois_nascimentos_ao_mesmo_tempo_elegem_um_so(self, mesa) -> None:
        """**O DEFEITO QUE ESTA RÉGUA ACHOU**, e ele não estava no plano.

        A conexão solta um nascimento POR ALVO no mesmo tique. Sem fila, os
        dois leem `eleitor.eleito is None` antes de qualquer um escrever, os
        DOIS chamam a eleição, e o ÚLTIMO fica com a fonte padrão da máquina —
        a condição *"a mesa sem dono"* burlada por corrida em vez de por regra.

        Medido com a cura ainda sem `_fila_do_nascimento`::

            mic_da_mesa_eleicao  uniq=…0011 ok=True
            mic_da_mesa_eleicao  uniq=…0022 ok=True
            eleitor.eleito == …0022

        MORDIDA: tire o `async with _fila_do_nascimento(daemon)` de
        `nascer_no_ar`. Este caso reprova, e o do replug junto.
        """
        daemon = mesa.daemon((P1, P2))

        await asyncio.gather(
            hotkey.nascer_no_ar(daemon, P1), hotkey.nascer_no_ar(daemon, P2)
        )

        elegeram = [c[1] for c in mesa.eleitor.chamadas if c[0] == "eleger"]
        assert elegeram == [P1], (
            f"mais de um nascimento elegeu ao mesmo tempo: {elegeram} — o "
            "último a responder fica com a fonte padrão da máquina dela"
        )
        assert mesa.eleitor.eleito == P1

    @pytest.mark.asyncio
    async def test_a_ordem_de_chegada_nao_e_reescrita_por_reconexao(
        self, mesa
    ) -> None:
        """A ordem decide para quem o padrão passa quando o dono sair.

        Um nascimento que chamasse `entrou` a cada reconexão embaralharia a
        fila sem ninguém ter ligado nada.
        """
        daemon = mesa.daemon((P1, P2))

        await hotkey.nascer_no_ar(daemon, P1)
        await hotkey.nascer_no_ar(daemon, P2)
        antes = hotkey._no_ar_da_sessao(daemon).todos()
        await hotkey.nascer_no_ar(daemon, P1)

        assert hotkey._no_ar_da_sessao(daemon).todos() == antes, (
            "a reconexão reescreveu a ordem de chegada dos microfones no ar"
        )


# ===========================================================================
# 3. O SILÊNCIO DELA VENCE — as duas formas de ela ter pedido para calar
# ===========================================================================


class TestOSilencioDelaVence:
    """SOM-MIC-REPLUG-01 pela porta da frente: *"o silêncio que o produto
    promete e não entrega"*. Se o nascimento passar por cima, o defeito mais
    grave desta família volta pelo lado de dentro."""

    @pytest.mark.asyncio
    async def test_o_perfil_que_pede_silencio_impede_o_nascimento(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`pragmata.json`, na mesa dela, tem `mic.muted: true`."""
        monkeypatch.setattr(mgr, "load_profile", lambda _n: _perfil(mic={"muted": True}))
        daemon = mesa.daemon(perfil_ativo="o-perfil-dela")

        assert await hotkey.nascer_no_ar(daemon, P1) is False

        assert mesa.registro.abertos() == frozenset(), "o canal subiu mesmo assim"
        assert mesa.registro.no_ar() == {}, "o `0x32` foi aceso mesmo assim"
        assert not hotkey._no_ar_da_sessao(daemon).esta(P1)
        assert mesa.eleitor.eleito is None

    @pytest.mark.asyncio
    async def test_o_silencio_da_peca_vence_o_global_que_cala(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A peça reescreve o global — é a ordem de `reapply_mic_on_connect`.

        Global mudo, peça FALANDO: este controle nasce no ar.
        """
        monkeypatch.setattr(
            mgr,
            "load_profile",
            lambda _n: _perfil(
                mic={"muted": True}, por_peca={P1: {"mic": {"muted": False}}}
            ),
        )
        daemon = mesa.daemon(perfil_ativo="o-perfil-dela")

        assert await hotkey.nascer_no_ar(daemon, P1) is True
        assert mesa.registro.no_ar().get(P1) is True

    @pytest.mark.asyncio
    async def test_o_perfil_sem_opiniao_nasce_ligado(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ordem dela de 17/09/2026: *"os jogos e perfis tem que iniciar com
        todas as features ativadas por default."*  # (noqa-acento: citação dela)

        `muted=None` é *"não tenho opinião"*, e opinião ausente NÃO é silêncio.
        """
        monkeypatch.setattr(mgr, "load_profile", lambda _n: _perfil(mic={"volume": 100}))
        daemon = mesa.daemon(perfil_ativo="o-perfil-dela")

        assert await hotkey.nascer_no_ar(daemon, P1) is True
        assert mesa.registro.no_ar().get(P1) is True

    @pytest.mark.asyncio
    async def test_o_bit_do_mudo_ja_aceso_impede_o_nascimento(self, mesa) -> None:
        """O outro caminho do silêncio: ela apertou o botão do plástico.

        O perfil não sabe disso — o mudo do firmware não vai ao disco. Ler o
        aparelho é o segundo cinto, e ele cobre a reconexão de quem estava
        calado.
        """
        daemon = mesa.daemon(mudo_no_firmware=True)

        assert await hotkey.nascer_no_ar(daemon, P1) is False
        assert mesa.registro.no_ar() == {}
        assert mesa.eleitor.eleito is None

    @pytest.mark.asyncio
    async def test_nao_saber_do_aparelho_nao_e_silencio(self, mesa) -> None:
        """*"Não sei"* nunca vira *"me cale"* — senão o nascimento nunca ocorre.

        Backend enxuto (sem `audio_status_for`) é o caso de todo dublê e de
        toda instalação com backend legado.
        """
        daemon = mesa.daemon()
        mesa.backend.audio_status_for = None  # type: ignore[assignment]

        assert await hotkey.nascer_no_ar(daemon, P1) is True


# ===========================================================================
# 4. A FIAÇÃO — os três caminhos de conexão do daemon
# ===========================================================================


class TestAConexaoChamaONascimento:
    """O ponto UNIVERSAL: vale para o 1º e para o 4º, no cabo e no rádio.

    `reaplicar_som_em_todos_os_alvos` é chamado pela partida do daemon (o
    controle que já estava na mesa, em `Daemon.run`), pela primeira conexão do
    `reconnect_loop` e pelo `connect_with_retry` do `reconnect()`;
    `anunciar_bordas_por_alvo` é o ramo do alvo que nasce. Cobrir os dois cobre
    os caminhos.

    FATO SUBSTITUÍDO (18/09/2026): aqui estava escrito que o primeiro connect
    passava por `connect_with_retry`. Não passava — a partida do daemon conecta
    por conta própria, e até 18/09 era o ÚNICO caminho sem o nascimento. A
    régua que prova a partida é
    `test_o_microfone_nasce_no_boot.py`, com o `Daemon` de verdade.
    """

    @pytest.mark.asyncio
    async def test_o_replug_de_todos_os_alvos_faz_o_microfone_nascer(
        self, mesa
    ) -> None:
        daemon = mesa.daemon((P1, P2))

        await connection.reaplicar_som_em_todos_os_alvos(daemon)  # type: ignore[arg-type]
        await _esperar_os_nascimentos()

        no_ar = hotkey._no_ar_da_sessao(daemon)
        assert no_ar.esta(P1) and no_ar.esta(P2), (
            "a conexão não fez os microfones nascerem — ela continua tendo de "
            f"clicar no 🎙 toda vez ({no_ar.todos()})"
        )
        assert mesa.registro.no_ar() == {P1: True, P2: True}
        assert mesa.eleitor.eleito == P1, (
            "a fonte padrão não ficou com o primeiro da mesa"
        )

    @pytest.mark.asyncio
    async def test_o_alvo_que_nasce_no_hotplug_tambem_nasce_no_ar(
        self, mesa
    ) -> None:
        """O ramo por alvo — a queda de um controle numa mesa que não esvaziou."""
        daemon = mesa.daemon((P1, P2))

        await connection.anunciar_bordas_por_alvo(
            daemon,  # type: ignore[arg-type]
            {"hidraw0": P1},
            {"hidraw0": P1, "hidraw1": P2},
        )
        await _esperar_os_nascimentos()

        assert hotkey._no_ar_da_sessao(daemon).esta(P2), (
            "o controle que voltou no hotplug não nasceu no ar"
        )
        assert not hotkey._no_ar_da_sessao(daemon).esta(P1), (
            "o ramo por alvo tocou quem não se mexeu"
        )

    @pytest.mark.asyncio
    async def test_a_conexao_nao_espera_o_nascimento(self, mesa) -> None:
        """O fio próprio, e ele é medido: eleger custa `pactl` mais até 3 s.

        Esse orçamento dentro de `connect_with_retry` seria a partida do daemon
        inteira parada atrás do microfone, vezes o número de controles. É a
        mesma família do travamento da janela medido em 15/09.
        """
        daemon = mesa.daemon()
        partiu = asyncio.Event()

        async def _demorar(_d: Any, _u: str) -> bool:
            partiu.set()
            await asyncio.sleep(30)
            return True

        original = hotkey.nascer_no_ar
        hotkey.nascer_no_ar = _demorar  # type: ignore[assignment]
        try:
            await asyncio.wait_for(
                connection.reaplicar_som_em_todos_os_alvos(daemon),  # type: ignore[arg-type]
                timeout=2.0,
            )
            await asyncio.wait_for(partiu.wait(), timeout=2.0)
        finally:
            hotkey.nascer_no_ar = original  # type: ignore[assignment]
            for tarefa in list(hotkey._NASCIMENTOS_EM_VOO):
                tarefa.cancel()
            await asyncio.gather(
                *list(hotkey._NASCIMENTOS_EM_VOO), return_exceptions=True
            )

    @pytest.mark.asyncio
    async def test_sem_laco_rodando_devolve_nada_em_vez_de_explodir(
        self, mesa
    ) -> None:
        """CLI e dublê síncrono não têm laço, e o nascimento é um acréscimo."""
        daemon = mesa.daemon()

        def _sem_laco() -> Any:
            return hotkey.agendar_o_nascimento_do_microfone(daemon, uniq=P1)  # type: ignore[arg-type]

        assert await asyncio.to_thread(_sem_laco) is None


# ===========================================================================
# 5. A MÁQUINA COM OUTRO MICROFONE — o nascimento não desaloja o headset
# ===========================================================================

#: O microfone de verdade de quem NÃO é ela: um headset USB, na forma em que o
#: PipeWire o publica. Nome de fabricante genérico, nenhum aparelho real.
HEADSET = "alsa_input.usb-Fabricante_Headset_USB-00.mono-fallback"


class TestAMaquinaComOutroMicrofone:
    """O produto é para qualquer computador, não só o dela (ordem de 18/09).

    Com a mesa sem dono o nascimento ELEGIA, e eleger é `pactl
    set-default-source`: o WirePlumber grava a escolha, e ela vence a
    prioridade 1500 do drop-in 51 que o `install.sh` instala justamente para
    o controle NÃO virar o microfone padrão. Numa máquina com headset, cada
    partida do daemon tomava o microfone da pessoa. Na mesa dela nunca se viu,
    porque o único microfone com porta usável é o do controle.

    MORDIDA: troque a condição de `_nascer_no_ar_na_vez` de volta para só
    `_eleitor(daemon).eleito is None` — os dois primeiros casos reprovam.
    """

    @pytest.mark.asyncio
    async def test_o_controle_nasce_no_ar_sem_tomar_o_padrao(self, mesa) -> None:
        mesa.outro_microfone = HEADSET
        daemon = mesa.daemon()

        assert await hotkey.nascer_no_ar(daemon, P1) is True

        assert mesa.eleitor.chamadas == [], (
            "o nascimento chamou a eleição numa máquina com headset — ela "
            f"escreve `set-default-source` e o WirePlumber grava ({mesa.eleitor.chamadas})"
        )
        assert mesa.eleitor.eleito is None
        assert hotkey._no_ar_da_sessao(daemon).esta(P1), (
            "não tomar o padrão custou o AR: o microfone do controle tem de "
            "nascer ligado do mesmo jeito"
        )
        assert mesa.registro.no_ar().get(P1) is True, "a palavra não foi dita"
        assert P1 in mesa.registro.abertos(), "o canal do controle não foi pedido"

    @pytest.mark.asyncio
    async def test_os_dois_nascem_no_ar_e_nenhum_toma_o_padrao(self, mesa) -> None:
        """O caso que o cético pediu: a mesa de dois numa máquina com headset."""
        mesa.outro_microfone = HEADSET
        daemon = mesa.daemon((P1, P2))

        await hotkey.nascer_no_ar(daemon, P1)
        await hotkey.nascer_no_ar(daemon, P2)

        no_ar = hotkey._no_ar_da_sessao(daemon)
        assert no_ar.esta(P1) and no_ar.esta(P2), no_ar.todos()
        assert mesa.eleitor.eleito is None
        assert mesa.registro.no_ar() == {P1: True, P2: True}

    @pytest.mark.asyncio
    async def test_quem_pediu_o_controle_como_padrao_ainda_elege(
        self, mesa, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """A marca que o `install.sh --keep-dualsense-mic` grava vale como pedido.

        A marca é ESCRITA no lar de mentira, e quem a lê é o dono de verdade
        (`system_check._dualsense_mic_intended`) — dublar a função mediria o
        dublê. Quem usa o microfone do controle por acessibilidade escolheu
        isso no instalador, e o headset plugado não desfaz a escolha.
        """
        estado = tmp_path / "estado"
        marca = estado / "hefesto-dualsense4unix" / "mic-do-dualsense-pedido.conf"
        marca.parent.mkdir(parents=True)
        marca.write_text("pedido\n", encoding="utf-8")
        monkeypatch.setenv("XDG_STATE_HOME", str(estado))
        mesa.outro_microfone = HEADSET
        daemon = mesa.daemon()

        await hotkey.nascer_no_ar(daemon, P1)

        assert mesa.eleitor.eleito == P1, (
            "a marca do gesto não foi honrada — quem pediu o microfone do "
            "controle no instalador perdeu a escolha para o headset"
        )

    @pytest.mark.asyncio
    async def test_o_canal_de_outro_controle_nao_e_o_microfone_da_maquina(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pergunta é "não é CONTROLE NENHUM", e não a lista do install.

        `melhor_fonte_elegivel` responde o canal por controle de propósito (o
        §D.2 da MIC-PADRAO-NO-CABO-01). Foi a primeira escrita desta cura, e
        com ela o canal de um controle passava por headset: na mesa que só tem
        os controles, ninguém elegeria. MORDIDA: troque
        `outra_captura_elegivel` por `melhor_fonte_elegivel` em
        `hotkey._microfone_que_ja_e_da_maquina`.
        """
        monkeypatch.setattr(elm, "melhor_fonte_elegivel", lambda: f"hefesto_mic_{P2[-6:]}")
        daemon = mesa.daemon()

        await hotkey.nascer_no_ar(daemon, P1)

        assert mesa.eleitor.eleito == P1, (
            "o canal de outro controle foi lido como microfone da máquina, e o "
            "único microfone dela deixou de ser eleito"
        )

    @pytest.mark.asyncio
    async def test_na_duvida_nao_toma_o_padrao(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pergunta explodiu: no ar, e sem desalojar ninguém."""

        def _explode() -> str | None:
            raise OSError("o script do WirePlumber sumiu no meio")

        monkeypatch.setattr(elm, "outra_captura_elegivel", _explode)
        daemon = mesa.daemon()

        assert await hotkey.nascer_no_ar(daemon, P1) is True
        assert mesa.eleitor.chamadas == []
        assert hotkey._no_ar_da_sessao(daemon).esta(P1)


# ===========================================================================
# 6. A RECUSA DELA VENCE — o `microfone: false` do `maquina.json`
# ===========================================================================


class TestARecusaDelaVenceONascimento:
    """*"todos os controles tem que nascer com tudo"* — e só o `False` desliga.

    A inversão de 18/09/2026 tem duas metades, e o nascimento só honrava a
    primeira: ele perguntava ao perfil e ao bit do firmware, nunca à recusa. No
    hotplug seguinte ao "Desligar" dela, a palavra era dita e o canal pedido
    para o controle que ela acabara de calar.

    MORDIDA: tire a guarda `_ela_desligou_este_microfone` de
    `_nascer_no_ar_na_vez` e os dois primeiros casos reprovam; tire a
    subtração de `uniqs_negados` de `BtMicSubsystem._reconciliar_o_cabo` e os
    dois últimos reprovam.
    """

    @pytest.mark.asyncio
    async def test_o_controle_desligado_nao_nasce(self, mesa) -> None:
        daemon = mesa.daemon(recusados=frozenset({P1}))

        assert await hotkey.nascer_no_ar(daemon, P1) is False

        assert mesa.registro.no_ar() == {}, "a palavra foi dita a quem ela calou"
        assert mesa.registro.abertos() == frozenset(), (
            "o canal foi pedido para o controle que ela desligou — no cabo ele "
            "reabre o `hefesto_mic_<hex6>` dele"
        )
        assert not hotkey._no_ar_da_sessao(daemon).esta(P1)
        assert mesa.eleitor.chamadas == [], "a eleição correu para quem ela calou"
        assert mesa.eleitor.eleito is None

    @pytest.mark.asyncio
    async def test_a_recusa_de_um_nao_cala_o_vizinho(self, mesa) -> None:
        """A recusa é POR CONTROLE: o outro da mesa nasce e elege normalmente.

        A grafia com dois-pontos é a da tela e do `maquina.json`; a do plástico
        não tem. As duas têm de casar.
        """
        recusado = ":".join(P1[i : i + 2] for i in range(0, 12, 2))
        daemon = mesa.daemon((P1, P2), recusados=frozenset({recusado}))

        await hotkey.nascer_no_ar(daemon, P1)
        await hotkey.nascer_no_ar(daemon, P2)

        assert mesa.registro.no_ar() == {P2: True}
        assert mesa.eleitor.eleito == P2

    def test_o_canal_do_cabo_nao_sobe_para_quem_ela_desligou(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O terceiro leitor do registro, e o único que não subtraía a recusa.

        O pedido que chega DEPOIS da borda de `_soltar_os_que_ela_desmarcou`
        (um gesto velho na fila, o nascimento de uma versão sem a guarda) não
        pode erguer canal com nome de controle para quem ela desligou.
        """
        abertos: list[list[str]] = []
        monkeypatch.setattr(
            BtMicSubsystem, "_abrir_os_canais_do_cabo",
            lambda self, uniqs: abertos.append(list(uniqs)),
        )
        mesa.daemon((P1, P2), recusados=frozenset({P1}))
        mesa.registro.pedir(P1)
        mesa.registro.pedir(P2)

        mesa.subsystem._reconciliar_o_cabo([])

        assert abertos == [[P2]], (
            f"o supervisor do cabo quis abrir {abertos} — o canal do controle "
            "que ela desligou subiria com o nome dele"
        )

    def test_o_canal_do_cabo_de_pe_cai_quando_ela_desliga(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fechados: list[str] = []
        monkeypatch.setattr(
            BtMicSubsystem, "_fechar_o_canal_do_cabo",
            lambda self, uniq: fechados.append(uniq),
        )
        monkeypatch.setattr(
            BtMicSubsystem, "_abrir_os_canais_do_cabo", lambda self, uniqs: None
        )
        mesa.daemon(recusados=frozenset({P1}))
        mesa.registro.pedir(P1)
        mesa.subsystem._canais_do_cabo[P1] = f"hefesto_mic_{P1[-6:]}"

        mesa.subsystem._reconciliar_o_cabo([])

        assert fechados == [P1], (
            "o canal do cabo continuou de pé depois de ela desligar o microfone"
        )
