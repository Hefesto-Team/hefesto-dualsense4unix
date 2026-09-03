"""LUZ-DO-MIC-01, PEÇA C — a luz do microfone diz QUEM TE ESCUTA.

O alvo destes testes é `daemon/subsystems/luz_do_mic.py`: a precedência da §1.1
da sprint, o laço que só escreve na MUDANÇA, a devolução que REPINTA (§2) e as
degradações declaradas quando as peças irmãs não estão no ar.

**POR QUE VÁRIOS DESTES TESTES RODAM CENTENAS DE TIQUES.** Uma régua que roda o
laço UMA vez mede um instante, não um comportamento — e o defeito que esta peça
mais arrisca reintroduzir é exatamente temporal: reafirmar o mesmo valor no
`common[8]` a cada tique é o commit `3d9bb7e` no byte vizinho, e ele não
aparece em nenhum tique isolado. Em 29/08/2026 esta casa deixou passar uma
regressão que só aparecia aos 181 segundos com 67 testes verdes. Aqui os laços
correm com `INTERVALO_S` encolhido e o número de voltas é MEDIDO (o dublê conta
quantas vezes foi consultado), para que "rodou muito" seja um fato do teste e
não uma esperança.

**A MORDIDA, provada em 03/09/2026** (arrancar a cura, ver reprovar, devolver):

* sem a guarda `escrito.get(uniq) == alvo` → `test_escreve_so_na_mudanca_...`
  e `test_o_pisca_nao_vira_martelo...` reprovam (1 escrita esperada, 620
  medidas);
* sem a repintura em `_devolver` → `test_o_desligamento_repinta_...` e
  `test_quando_para_de_saber_...` reprovam (a luz é solta no vocabulário
  errado);
* trocando `set_microphone_led` por `set_mic_led` →
  `test_o_nivel_chega_inteiro_...` reprova (o `2` e o `3` viram `1`).
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as mod

#: OS DOIS CONTROLES DA MESA, na faixa FORJADA `aa:bb:cc` — a do
#: `test_anonimato_de_fixtures`. Aqui não vale a máscara da casa (octetos 4 e 5
#: zerados): ela preserva o OUI, e o OUI é identidade de fabricante do aparelho
#: dela. Fixture quer endereço que nunca existiu, não endereço real podado.
UM = "aabbcc0000f1"
OUTRO = "aabbcc0000f2"


# ---------------------------------------------------------------------------
# Dublês mínimos — o alvo é o laço, não o daemon inteiro
# ---------------------------------------------------------------------------


class _Controle:
    """Backend dublado com as QUATRO portas que o laço toca.

    As três primeiras ele usa; a quarta (`set_microphone_mute`, o `common[9]`)
    está aqui só para PROVAR que ele nunca a chama — a §3 da sprint proíbe.
    """

    def __init__(
        self,
        *,
        uniqs: list[str],
        mudo: dict[str, bool | None] | None = None,
        bateria: dict[str, int] | None = None,
    ) -> None:
        self.uniqs = list(uniqs)
        self.mudo: dict[str, bool | None] = mudo or {}
        self.bateria: dict[str, int] = bateria or {}
        self.conectados: set[str] = set(uniqs)
        #: `set_microphone_led` — o caminho CERTO, o único que carrega o nível.
        self.escritas: list[tuple[str | None, int | None]] = []
        #: `set_mic_led` — o caminho que ESMAGA em bool. Tem de ficar vazio.
        self.escritas_esmagadas: list[Any] = []
        #: `set_microphone_mute` — o `common[9]`. Tem de ficar vazio.
        self.mudos_escritos: list[Any] = []
        #: quantas vezes o laço nos consultou (a régua de "rodou muito").
        self.voltas = 0

    def set_microphone_led(self, aceso: bool | int | None, *, uniq: str | None = None) -> bool:
        self.escritas.append((uniq, aceso))
        return True

    def set_mic_led(self, aceso: Any, *, uniq: str | None = None) -> bool:
        self.escritas_esmagadas.append((uniq, aceso))
        return True

    def set_microphone_mute(self, muted: Any, *, uniq: str | None = None) -> bool:
        self.mudos_escritos.append((uniq, muted))
        return True

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        valor = self.mudo.get(uniq if uniq is not None else "")
        if valor is None:
            return None
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": valor}

    def describe_controllers(self) -> list[dict[str, object]]:
        self.voltas += 1
        return [
            {
                "index": i,
                "connected": u in self.conectados,
                "transport": "usb",
                "is_primary": i == 0,
                "uniq": u,
                "battery_pct": self.bateria.get(u),
            }
            for i, u in enumerate(self.uniqs)
        ]


class _Daemon:
    def __init__(self, controller: _Controle) -> None:
        self.bus = EventBus()
        self.controller = controller
        self._parando = False
        self._tasks: list[asyncio.Task[Any]] = []
        #: o que o laço mandou para o executor — a régua de "nada que fale com
        #: o mundo roda no event loop".
        self.no_executor: list[str] = []

    def _is_stopping(self) -> bool:
        return self._parando

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        self.no_executor.append(getattr(fn, "__name__", str(fn)))
        await asyncio.sleep(0)
        return fn(*args)


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Encolhe as cadências, e deixa o MUNDO do lado de fora.

    As constantes são lidas como globais DENTRO do laço a cada volta — é o que
    torna o encolhimento possível sem tocar no código de produção.

    **A segunda metade não é higiene, é contenção.** As peças irmãs são
    procuradas em `sys.modules`, e um teste que não as planta acha as DE
    VERDADE: a PEÇA A dispara `pactl` contra a máquina dela, e a PEÇA B
    instancia o medidor real, que abre processos `parec` na fonte de captura do
    controle. Medido em 03/09/2026 — antes desta trava, os testes que exercitam
    a AUSÊNCIA das peças eram justamente os que caíam nas peças reais. Teste de
    unidade não toca o mundo; nesta casa a suíte já derrubou a sessão gráfica
    dela uma vez por fazer isso.

    Quem quiser as peças de verdade tira o tapume à mão — só
    `test_a_junta_com_as_pecas_irmas_existe_de_verdade` o faz, e ele explica
    por quê.
    """
    monkeypatch.setattr(mod, "INTERVALO_S", 0.001)
    monkeypatch.setattr(mod, "INTERVALO_DE_QUEM_OUVE_S", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DO_REPORT_S", 0.001)
    monkeypatch.setattr(mod, "SEM_RESPOSTA_ATE_SOLTAR_S", 0.05)
    monkeypatch.setattr(mod, "_fontes_para", lambda _uniqs, _mesa: {})
    for caminho in (mod.MODULO_DE_QUEM_OUVE, mod.MODULO_DO_NIVEL):
        monkeypatch.setitem(sys.modules, caminho, types.ModuleType(caminho))


class _MedidorFalso:
    """Dublê da PEÇA B **com a forma real dela**: `seguir` + `captando` + `parar`.

    A forma importa mais que a resposta, e é a lição de 03/09/2026: este
    arquivo plantava aqui uma FUNÇÃO `captando_agora`, que o laço procurava e
    que a PEÇA B de verdade nunca teve. Os testes passavam sobre uma junta
    morta — dois dos quatro estados eram inalcançáveis no produto e verdes na
    suíte. Um dublê que inventa a forma do vizinho não mede o vizinho: mede a
    própria invenção.
    """

    def __init__(self, responder: Any) -> None:
        self._responder = responder
        #: cada `seguir` recebido — a régua de "só mede quem tem ouvinte".
        self.seguidos: list[dict[str, str]] = []
        self.parado = False

    def seguir(self, alvos: Any) -> None:
        self.seguidos.append(dict(alvos))

    def captando(self) -> dict[str, Any]:
        # Responde SÓ por quem está sendo seguido, como a de verdade
        # (`NivelDoMicrofone.captando` itera `self._desejado`). Um dublê mais
        # generoso que o original deixaria passar um laço que lê nível de quem
        # nunca mandou medir.
        seguidos = list(self.seguidos[-1]) if self.seguidos else []
        return {u: v for u, v in self._responder(seguidos).items() if u in seguidos}

    def parar(self) -> None:
        self.parado = True


def _pecas(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ouvintes: Any = None,
    captando: Any = None,
) -> _MedidorFalso | None:
    """Planta as peças A e B em `sys.modules`, do jeito que o laço as procura.

    Passar `None` deixa a peça AUSENTE — o estado que as degradações
    declaradas têm de aguentar.

    **`_fontes_para` é sempre substituída**, mesmo quando a PEÇA B está
    ausente: a de verdade dispara `pactl` contra a máquina DELA. Um teste de
    unidade que abre subprocesso para descobrir o grafo de áudio da bancada não
    é teste de unidade — e nesta casa a suíte já derrubou a sessão gráfica dela
    uma vez por tocar o mundo real.
    """
    def _fontes_para(uniqs: list[str], _mesa: list[str]) -> dict[str, str]:
        return {u: f"fonte-de-{u}" for u in uniqs}

    monkeypatch.setattr(mod, "_fontes_para", _fontes_para)
    if ouvintes is not None:
        peca_a = types.ModuleType(mod.MODULO_DE_QUEM_OUVE)
        peca_a.quem_ouve_agora = ouvintes  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, mod.MODULO_DE_QUEM_OUVE, peca_a)
    if captando is None:
        return None
    medidor = _MedidorFalso(captando)
    peca_b = types.ModuleType(mod.MODULO_DO_NIVEL)
    peca_b.NivelDoMicrofone = lambda: medidor  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod.MODULO_DO_NIVEL, peca_b)
    return medidor


async def _rodar(
    daemon: _Daemon, *, voltas: int, entre: Any = None
) -> list[tuple[str | None, int | None]]:
    """Sobe o laço, deixa dar `voltas` consultas, e o derruba pelo cancelamento.

    O derrube é o do produto: `connection.shutdown` faz `task.cancel()` e
    depois `await task` (`daemon/connection.py:1383-1387`). Testar com um
    `_parando = True` educado mediria um caminho que o daemon nunca toma.

    **Devolve o que foi escrito EM VOO**, tirado antes do cancelamento. A
    devolução de posse escreve mais duas vezes (a repintura e o `None`), e
    misturá-las com o que o laço fez enquanto vivia faria toda régua de
    "escreveu só na mudança" contar a despedida como reafirmação.
    """
    tarefa = asyncio.create_task(mod.luz_do_mic_loop(daemon))
    controle = daemon.controller
    try:
        while controle.voltas < voltas:
            await asyncio.sleep(0.002)
            if entre is not None:
                entre(controle.voltas)
        em_voo = list(controle.escritas)
    finally:
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa
    return em_voo


# ---------------------------------------------------------------------------
# 1. A precedência da §1.1, escrita como tabela
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mudo", "ouvintes", "captando", "bateria", "esperado"),
    [
        # mudo no firmware -> 0, e ele vence TUDO (inclusive a bateria baixa)
        (True, ["chrome"], True, 5, mod.APAGADA),
        (True, None, None, None, mod.APAGADA),
        # captando + bateria < 30% -> 3
        (False, ["chrome"], True, 29, mod.PISCANDO_LENTO),
        # o limiar é ABAIXO de 30, não abaixo-ou-igual
        (False, ["chrome"], True, 30, mod.PISCANDO),
        # captando -> 2
        (False, ["chrome"], True, 80, mod.PISCANDO),
        # bateria desconhecida NÃO vira pisca lento — ausência não é 3
        (False, ["chrome"], True, None, mod.PISCANDO),
        # algum app com o microfone aberto -> 1
        (False, ["chrome"], False, 10, mod.ACESA),
        # bateria baixa SEM captação não acende nada além do 1
        (False, ["chrome"], None, 4, mod.ACESA),
        # resto -> 0
        (False, [], False, 90, mod.APAGADA),
        (False, [], None, None, mod.APAGADA),
    ],
)
def test_a_precedencia_e_a_da_sprint(
    mudo: bool | None,
    ouvintes: list[str] | None,
    captando: bool | None,
    bateria: int | None,
    esperado: int,
) -> None:
    assert (
        mod.decidir(
            mudo=mudo, ouvintes=ouvintes, captando=captando, bateria_pct=bateria
        )
        == esperado
    )


@pytest.mark.parametrize(
    ("mudo", "ouvintes"),
    [
        # o controle ainda não reportou o byte de estado de áudio
        (None, ["chrome"]),
        (None, []),
        # a PEÇA A não sabe responder — "não perguntei" != "ninguém ouve"
        (False, None),
    ],
)
def test_nao_sei_nao_e_zero(mudo: bool | None, ouvintes: list[str] | None) -> None:
    """`None` é *"não escreva"*, e ele NÃO pode virar `APAGADA` por descuido.

    Confundir os dois é o `bool(None)` que esta casa já publicou como ATIVO
    sobre um controle que tinha acabado de cair: a ausência de dado vira uma
    afirmação, e ela é convincente.
    """
    assert (
        mod.decidir(mudo=mudo, ouvintes=ouvintes, captando=None, bateria_pct=None)
        is None
    )


def test_a_lista_vazia_e_uma_resposta_e_a_ausencia_nao_e() -> None:
    """`[]` (medi, ninguém ouve) e `None` (não medi) NÃO podem coincidir."""
    vazia = mod.decidir(mudo=False, ouvintes=[], captando=None, bateria_pct=None)
    ausente = mod.decidir(mudo=False, ouvintes=None, captando=None, bateria_pct=None)
    assert vazia == mod.APAGADA
    assert ausente is None


def test_o_produto_nao_inventa_um_quinto_estado() -> None:
    """A faixa é `0..3` e `decidir` nunca sai dela (§4 da sprint)."""
    saidas = {
        mod.decidir(mudo=m, ouvintes=o, captando=c, bateria_pct=b)
        for m in (True, False, None)
        for o in (None, [], ["a"], ["a", "b"])
        for c in (True, False, None)
        for b in (None, 0, 29, 30, 100)
    }
    assert saidas <= {None, 0, 1, 2, 3}


# ---------------------------------------------------------------------------
# 2. O TEMPO — escreve só na mudança, e a régua roda centenas de tiques
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escreve_so_na_mudanca_ao_longo_de_centenas_de_tiques(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Estado parado por ~300 voltas = UMA escrita. É o guarda do `3d9bb7e`.

    Reafirmar o mesmo valor a cada tique não quebra nenhum tique isolado — ele
    quebra o barramento e atropela o kernel, e só aparece no acumulado. Por
    isso a asserção é sobre o NÚMERO de escritas depois de muitas voltas, e o
    número de voltas é medido pelo dublê.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    _pecas(monkeypatch, ouvintes=lambda _u: {UM: ["chrome"]}, captando=lambda _u: {UM: False})
    daemon = _Daemon(controle)

    em_voo = await _rodar(daemon, voltas=300)

    assert controle.voltas >= 300, "o laço tem de ter rodado muito, não uma vez"
    assert em_voo == [(UM, mod.ACESA)], (
        f"esperava UMA escrita em ~{controle.voltas // 2} tiques, "
        f"vieram {len(em_voo)}: {em_voo[:8]}"
    )


@pytest.mark.asyncio
async def test_o_pisca_nao_vira_martelo_quando_ela_fala_sem_parar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ela fala por centenas de tiques seguidos: `2` é escrito UMA vez.

    Este é o caso que a cadência de 4 Hz cria e que o `mic_da_mesa` não tem: a
    PEÇA B responde `True` volta após volta, e um laço sem a guarda de mudança
    escreveria `2` em cada uma delas.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    _pecas(
        monkeypatch,
        ouvintes=lambda _u: {UM: ["obs"]},
        captando=lambda _u: {UM: True},
    )
    daemon = _Daemon(controle)

    em_voo = await _rodar(daemon, voltas=300)

    assert em_voo == [(UM, mod.PISCANDO)]


@pytest.mark.asyncio
async def test_cada_virada_de_estado_vale_uma_escrita_e_so_uma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro viradas ao longo do tempo = quatro escritas, na ordem certa.

    A luz tem de ACOMPANHAR, e não só ficar quieta: um laço que nunca escreve
    passaria nos dois testes de cima e reprovaria aqui.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    estado = {"ouve": False, "fala": False}
    _pecas(
        monkeypatch,
        ouvintes=lambda _u: {UM: ["chrome"] if estado["ouve"] else []},
        captando=lambda _u: {UM: estado["fala"]},
    )
    daemon = _Daemon(controle)

    def virar(voltas: int) -> None:
        if voltas > 60:
            estado["ouve"] = True
        if voltas > 120:
            estado["fala"] = True
        if voltas > 180:
            controle.bateria[UM] = 12
        if voltas > 240:
            controle.mudo[UM] = True

    em_voo = await _rodar(daemon, voltas=320, entre=virar)

    escritas_do_laco = [v for _u, v in em_voo if v is not None]
    assert escritas_do_laco == [
        mod.APAGADA,  # ninguém ouvindo
        mod.ACESA,  # um app abriu o microfone
        mod.PISCANDO,  # entrou som
        mod.PISCANDO_LENTO,  # a bateria caiu abaixo de 30%
        mod.APAGADA,  # ela apertou o botão e ficou muda
    ]


# ---------------------------------------------------------------------------
# 3. O caminho de escrita — o nível chega inteiro, e o `common[9]` não é tocado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_nivel_chega_inteiro_pelo_caminho_que_carrega_o_nivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`2` e `3` saem como `2` e `3`, e `set_mic_led` NUNCA é chamado.

    Medido em 03/09/2026 nesta árvore: `set_mic_led` coage a `bool` duas vezes
    em série (`core/backend_pydualsense.py:3995` e `:372`), e o `2` e o `3`
    viram `1` sem erro e sem log — luz acesa fixa onde devia piscar, que se lê
    como *"a PEÇA B não está detectando som"*. O dublê expõe as DUAS portas de
    propósito: se alguém trocar o caminho, a lista errada é que enche.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 10})
    _pecas(
        monkeypatch,
        ouvintes=lambda _u: {UM: ["chrome"]},
        captando=lambda _u: {UM: True},
    )
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=60)

    assert (UM, mod.PISCANDO_LENTO) in controle.escritas
    assert controle.escritas_esmagadas == [], (
        "o laço escreveu por `set_mic_led`, que esmaga o nível em bool"
    )


@pytest.mark.asyncio
async def test_o_laco_nunca_toca_o_mudo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `common[9]` é campo de outro dono, com bit de autorização separado."""
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    estado = {"ouve": True}
    _pecas(
        monkeypatch,
        ouvintes=lambda _u: {UM: ["chrome"] if estado["ouve"] else []},
        captando=lambda _u: {UM: estado["ouve"]},
    )
    daemon = _Daemon(controle)

    def virar(voltas: int) -> None:
        estado["ouve"] = voltas % 80 < 40

    await _rodar(daemon, voltas=200, entre=virar)

    assert controle.mudos_escritos == []


# ---------------------------------------------------------------------------
# 4. §2 — a devolução REPINTA, e repinta na língua do KERNEL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_desligamento_repinta_na_lingua_do_kernel_e_so_entao_solta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ela está MUDA: a posse volta com a luz ACESA — o contrário do que pintamos.

    O §2 da sprint nasceu do que ela viu: *"ambos tão ligados. e ficaram."* O
    kernel escreve `mute_button_led = ds->mic_muted` só na BORDA do botão
    (`hid-playstation.c:1538-1540`), então o valor que largamos no byte fica no
    ar até ela apertar o botão. E o vocabulário dele é o INVERSO do nosso:
    para o kernel, aceso = mudo.

    Com ela muda, o laço pinta `APAGADA` (contrato dela: mudo e apagado são
    sinônimos). Ao soltar, o valor certo a deixar é `ACESA`. Duas maneiras de
    errar isto reprovam aqui: soltar sem repintar (sobra só o `None`), e
    repintar com o ÚLTIMO valor que escrevemos (sobra `0`).
    """
    controle = _Controle(uniqs=[UM], mudo={UM: True}, bateria={UM: 90})
    _pecas(monkeypatch, ouvintes=lambda _u: {UM: ["chrome"]}, captando=lambda _u: {UM: True})
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=60)

    assert controle.escritas[0] == (UM, mod.APAGADA), "muda = apagada, enquanto é nossa"
    assert controle.escritas[-2:] == [(UM, mod.ACESA), (UM, None)], (
        "a posse tem de voltar REPINTADA na língua do kernel, e só então solta"
    )


@pytest.mark.asyncio
async def test_o_desligamento_devolve_a_posse_de_todos_os_controles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesa de dois: os dois voltam ao kernel, nenhum fica para trás."""
    controle = _Controle(
        uniqs=[UM, OUTRO], mudo={UM: False, OUTRO: False}, bateria={UM: 90, OUTRO: 90}
    )
    _pecas(
        monkeypatch,
        ouvintes=lambda _u: {UM: ["chrome"], OUTRO: ["obs"]},
        captando=lambda _u: {UM: False, OUTRO: False},
    )
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=60)

    soltos = [uniq for uniq, valor in controle.escritas if valor is None]
    assert sorted(soltos) == sorted([UM, OUTRO])


@pytest.mark.asyncio
async def test_quando_para_de_saber_o_laco_devolve_a_luz_repintada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PEÇA A cai no meio da sessão: a luz não pode ficar travada num `2`.

    Segurar para sempre deixaria um pisca eterno sobre um microfone que talvez
    ninguém esteja ouvindo. Devolver na PRIMEIRA não-resposta faria um `pactl`
    que estourou o `timeout` uma vez virar um pisca-pisca de posse. O laço
    segura por `SEM_RESPOSTA_ATE_SOLTAR_S` e então devolve — REPINTADO.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    estado = {"viva": True}

    def peca_a(_uniqs: Any) -> dict[str, list[str]] | None:
        return {UM: ["chrome"]} if estado["viva"] else None

    _pecas(monkeypatch, ouvintes=peca_a, captando=lambda _u: {UM: True})
    daemon = _Daemon(controle)

    def derrubar_a_peca_a(voltas: int) -> None:
        if voltas > 60:
            estado["viva"] = False

    await _rodar(daemon, voltas=400, entre=derrubar_a_peca_a)

    assert controle.escritas[0] == (UM, mod.PISCANDO)
    solturas = [i for i, (_u, v) in enumerate(controle.escritas) if v is None]
    assert solturas, "o laço segurou a posse para sempre com a PEÇA A caída"
    primeira = solturas[0]
    assert controle.escritas[primeira - 1] == (UM, mod.APAGADA), (
        "soltou sem repintar: a luz fica presa no último valor que escrevemos"
    )


# ---------------------------------------------------------------------------
# 5. As degradações declaradas — as peças irmãs podem não existir
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sem_as_pecas_irmas_a_luz_ainda_apaga_quando_ela_fica_muda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nem PEÇA A nem PEÇA B no ar: o laço entrega o que SABE, e nada mais.

    Este é o estado real da árvore enquanto as três peças são construídas em
    paralelo. `mudo` vence a precedência inteira e não depende de ninguém, e é
    por isso que a metade do contrato que ela mais nota — apertar o botão e a
    luz apagar — já funciona sozinha.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    _pecas(monkeypatch)  # as duas AUSENTES
    daemon = _Daemon(controle)

    def emudecer(voltas: int) -> None:
        if voltas > 60:
            controle.mudo[UM] = True

    em_voo = await _rodar(daemon, voltas=200, entre=emudecer)

    escritas_do_laco = [e for e in em_voo if e[1] is not None]
    assert (UM, mod.APAGADA) in escritas_do_laco
    assert mod.ACESA not in [v for _u, v in escritas_do_laco], (
        "sem a PEÇA A o laço não pode AFIRMAR que alguém está ouvindo"
    )


@pytest.mark.asyncio
async def test_sem_a_peca_b_a_luz_acende_fixa_e_nunca_pisca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PEÇA A sim, PEÇA B não: `0` e `1` completos, sem inventar o `2`."""
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 5})
    _pecas(monkeypatch, ouvintes=lambda _u: {UM: ["chrome"]})
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=200)

    valores = {v for _u, v in controle.escritas if v is not None}
    assert mod.ACESA in valores
    assert mod.PISCANDO not in valores
    assert mod.PISCANDO_LENTO not in valores


@pytest.mark.asyncio
async def test_uma_peca_que_quebra_ao_importar_nao_derruba_o_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Peça irmã que levanta no `import` degrada, não derruba o subsistema."""
    controle = _Controle(uniqs=[UM], mudo={UM: True}, bateria={UM: 90})

    def explodir(_uniqs: Any) -> dict[str, Any]:
        raise RuntimeError("o pactl sumiu")

    _pecas(monkeypatch, ouvintes=explodir, captando=explodir)
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=120)

    assert (UM, mod.APAGADA) in controle.escritas
    assert controle.voltas >= 120, "o laço morreu no meio"


@pytest.mark.asyncio
async def test_um_backend_sem_a_porta_do_led_nao_derruba_o_laco() -> None:
    """`FakeController` e backends legados não declaram `set_microphone_led`."""

    class _Legado:
        def __init__(self) -> None:
            self.voltas = 0
            #: `_rodar` lê esta lista para tirar o que foi escrito EM VOO; um
            #: dublê sem ela rebenta o helper antes de exercitar o laço.
            self.escritas: list[Any] = []

        def audio_status_for(self, uniq: str | None = None) -> dict[str, bool]:
            del uniq
            return {"fone_plugado": False, "mic_externo": False, "mic_mudo": True}

        def describe_controllers(self) -> list[dict[str, object]]:
            self.voltas += 1
            return [{"index": 0, "connected": True, "uniq": UM, "battery_pct": 90}]

    legado = _Legado()
    daemon = _Daemon(legado)  # type: ignore[arg-type]
    await _rodar(daemon, voltas=80)  # type: ignore[arg-type]
    assert legado.voltas >= 80


# ---------------------------------------------------------------------------
# 6. A mesa vira — a borda invalida, e quem sai perde a memória
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_borda_do_botao_faz_o_laco_esquecer_o_que_escreveu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A eleição escreve no MESMO byte; o laço tem de reescrever depois dela.

    `hotkey._eleger_ou_devolver` chama `set_mic_led(aceso, uniq=)` na borda do
    botão. Se o laço confiasse na memória do que ELE escreveu, o valor posto
    pela eleição ficaria de pé para sempre — nós nunca reescrevemos o que
    achamos já estar lá. Assinar `EventTopic.MIC_DA_MESA` limita a briga a um
    tique.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    _pecas(monkeypatch, ouvintes=lambda _u: {UM: ["chrome"]}, captando=lambda _u: {UM: False})
    daemon = _Daemon(controle)

    # LIMIAR COM TRAVA, e não `voltas == 100`. O amostrador de `_rodar` lê o
    # contador a cada 2 ms enquanto o laço gira a cada 1 ms: ele enxerga a
    # série aos saltos (medido: passos de 2 e 4), e um valor exato pode nunca
    # aparecer. Uma régua que depende de acertar o número em cheio reprova por
    # escalonamento, não por defeito — foi o que aconteceu aqui.
    ja_bateu = {"sim": False}

    def bater_no_botao(voltas: int) -> None:
        if voltas >= 100 and not ja_bateu["sim"]:
            ja_bateu["sim"] = True
            daemon.bus.publish(
                str(EventTopic.MIC_DA_MESA), {"uniq": UM, "mudo": False, "seq": 7}
            )

    em_voo = await _rodar(daemon, voltas=300, entre=bater_no_botao)

    escritas_do_laco = [e for e in em_voo if e[1] is not None]
    assert escritas_do_laco == [(UM, mod.ACESA), (UM, mod.ACESA)], (
        "depois da borda o laço tem de repor o valor dele — exatamente uma vez"
    )


@pytest.mark.asyncio
async def test_o_controle_que_sai_da_mesa_perde_a_memoria(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Na reconexão o handle é NOVO e não lembra do que escrevemos no velho.

    Guardar o valor antigo faria o laço achar que o byte já está certo e nunca
    reescrevê-lo: a luz nasceria errada e ficaria. E o controle que saiu não
    pode ser "devolvido" — não há a quem devolver.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    _pecas(monkeypatch, ouvintes=lambda _u: {UM: ["chrome"]}, captando=lambda _u: {UM: False})
    daemon = _Daemon(controle)

    # JANELAS, e não dois valores exatos: o amostrador lê o contador aos
    # saltos (ver a nota do teste da borda). As duas operações são
    # idempotentes de propósito, então repeti-las a cada amostra não muda
    # nada — o que muda é que a régua deixa de depender de acertar o número.
    def tirar_e_por(voltas: int) -> None:
        if 100 <= voltas < 200:
            controle.conectados.discard(UM)
        elif voltas >= 200:
            controle.conectados.add(UM)

    em_voo = await _rodar(daemon, voltas=400, entre=tirar_e_por)

    escritas_do_laco = [e for e in em_voo if e[1] is not None]
    assert escritas_do_laco == [(UM, mod.ACESA), (UM, mod.ACESA)]
    assert controle.escritas.count((UM, None)) <= 1, (
        "o laço tentou devolver a posse de um controle que não está na mesa"
    )


@pytest.mark.asyncio
async def test_a_mesa_indecifravel_nao_faz_o_laco_soltar_ninguem() -> None:
    """Backend que não sabe listar = *"não perguntei"*, não *"a mesa esvaziou"*."""

    class _Mudo:
        def __init__(self) -> None:
            self.voltas = 0
            self.escritas: list[Any] = []

        def set_microphone_led(self, aceso: Any, *, uniq: str | None = None) -> bool:
            self.escritas.append((uniq, aceso))
            return True

        def describe_controllers(self) -> Any:
            self.voltas += 1
            return "não sei responder"

    backend = _Mudo()
    daemon = _Daemon(backend)  # type: ignore[arg-type]
    await _rodar(daemon, voltas=80)  # type: ignore[arg-type]
    assert backend.escritas == []


# ---------------------------------------------------------------------------
# 7. A fiação — o laço nasce pelo caminho do produto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_starter_pendura_a_task_no_daemon() -> None:
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    daemon = _Daemon(controle)
    mod.start_luz_do_mic(daemon)  # type: ignore[arg-type]
    try:
        assert len(daemon._tasks) == 1
        assert daemon._tasks[0].get_name() == "luz_do_mic_loop"
    finally:
        daemon._tasks[0].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await daemon._tasks[0]


def test_o_ciclo_de_vida_sobe_a_luz_do_mic() -> None:
    """O laço tem de estar LIGADO — um subsistema que ninguém sobe não existe.

    A régua lê o fonte do `lifecycle` em vez de subir um daemon: o boot toca
    uinput e rede, e o que se quer provar aqui é só que a linha de registro
    está lá, sem gate (§5.3b: um `install.sh` limpo entrega a luz funcionando,
    sem passo manual e sem flag).
    """
    from pathlib import Path

    import hefesto_dualsense4unix.daemon.lifecycle as ciclo

    fonte = Path(ciclo.__file__).read_text(encoding="utf-8")
    assert "start_luz_do_mic" in fonte
    assert 'self._safe_start("luz_do_mic"' in fonte


# ---------------------------------------------------------------------------
# 8. A JUNTA COM AS PEÇAS IRMÃS — a régua que faltava, e o defeito que ela pegou
# ---------------------------------------------------------------------------


def test_a_junta_com_as_pecas_irmas_existe_de_verdade() -> None:
    """Os nomes que o laço procura EXISTEM nos módulos de verdade.

    **ESTA RÉGUA NASCEU DE UM DEFEITO QUE A SUÍTE INTEIRA NÃO VIA, e o defeito
    é do dia 03/09/2026.** O laço procurava na PEÇA B quatro nomes de função —
    `captando_agora`, `esta_captando_agora`, `nivel_agora`, `captando_por_uniq`
    — e a PEÇA B não publica nenhum deles: ela é a classe `NivelDoMicrofone`,
    dirigida por `seguir`/`captando`. Resultado medido: `captando` ficava
    `None` para sempre e os estados `2` (piscando) e `3` (pisca lento) eram
    INALCANÇÁVEIS no produto — metade do contrato dela, morta em silêncio.

    Todos os outros testes deste arquivo passavam, porque todos plantavam um
    dublê com o nome que o laço queria. Um dublê que inventa a forma do vizinho
    não mede o vizinho. Esta régua é a única que olha para os módulos REAIS, e
    é por isso que ela não usa dublê nenhum.

    Ela não roda `pactl`: só importa e olha os nomes.
    """
    import importlib

    # TIRA O TAPUME da bancada: este é o único teste do arquivo que quer os
    # módulos DE VERDADE. Todos os outros os recebem dublados, para não
    # disparar `pactl` nem `parec` na máquina dela.
    for caminho in (mod.MODULO_DE_QUEM_OUVE, mod.MODULO_DO_NIVEL):
        sys.modules.pop(caminho, None)

    peca_a = importlib.import_module(mod.MODULO_DE_QUEM_OUVE)
    achada = getattr(peca_a, mod.NOME_DE_QUEM_OUVE, None)
    assert callable(achada), (
        f"a PEÇA A não publica `{mod.NOME_DE_QUEM_OUVE}` — a junta está morta e "
        f"a luz fica apagada para sempre, sem erro e sem log"
    )

    peca_b = importlib.import_module(mod.MODULO_DO_NIVEL)
    classe = getattr(peca_b, mod.NOME_DO_MEDIDOR, None)
    assert callable(classe), (
        f"a PEÇA B não publica `{mod.NOME_DO_MEDIDOR}` — sem ela os estados "
        f"`2` e `3` são inalcançáveis"
    )
    for metodo in ("seguir", "captando", "parar"):
        assert callable(getattr(classe, metodo, None)), (
            f"`{mod.NOME_DO_MEDIDOR}.{metodo}` sumiu; o laço dirige o medidor "
            f"por estes três e PARA por `parar` — sem ele o `parec` vaza"
        )


@pytest.mark.asyncio
async def test_o_medidor_e_parado_no_desligamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O medidor segura `parec` VIVO: não pará-lo prende o microfone dela.

    Medido nesta bancada em 03/09/2026: um `parec` órfão ficou 25 minutos
    segurando a fonte de captura do DualSense em RUNNING. Ele tem o stdout em
    `/dev/null`, logo nunca toma `SIGPIPE`, e nasce num cgroup que não é unit
    do Hefesto — um `systemctl --user stop` do daemon não o recolhe.

    O derrube aqui é o do produto: `cancel()` e `await`, como o
    `connection.shutdown` faz.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    medidor = _pecas(
        monkeypatch,
        ouvintes=lambda _u: {UM: ["chrome"]},
        captando=lambda _u: {UM: True},
    )
    assert medidor is not None
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=60)

    assert medidor.parado, (
        "o laço morreu sem parar o medidor — os `parec` ficam vivos segurando "
        "a fonte de captura dela aberta, e ninguém os recolhe"
    )


@pytest.mark.asyncio
async def test_o_medidor_so_segue_quem_tem_ouvinte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§1.1: o `2` vive dentro do `1`, então só quem tem ouvinte é medido.

    Medir quem ninguém está ouvindo abriria um `parec` para responder uma
    pergunta que a precedência já respondeu — e cada `parec` é custo na máquina
    dela e uma fonte de captura segurada aberta.
    """
    controle = _Controle(uniqs=[UM, OUTRO], mudo={UM: False, OUTRO: False}, bateria={})
    medidor = _pecas(
        monkeypatch,
        # só UM tem ouvinte; OUTRO tem a fonte publicada e ninguém nela
        ouvintes=lambda _u: {UM: ["chrome"], OUTRO: []},
        captando=lambda seguidos: dict.fromkeys(seguidos, True),
    )
    assert medidor is not None
    daemon = _Daemon(controle)

    em_voo = await _rodar(daemon, voltas=120)

    assert medidor.seguidos, "o medidor nunca foi instruído"
    for alvos in medidor.seguidos:
        assert OUTRO not in alvos, (
            f"o laço mandou medir {OUTRO}, que não tem ouvinte nenhum: "
            f"{alvos}"
        )
    assert any(UM in alvos for alvos in medidor.seguidos)

    escritos = {u: v for u, v in em_voo if v is not None}
    assert escritos.get(UM) == mod.PISCANDO
    assert escritos.get(OUTRO) == mod.APAGADA


@pytest.mark.asyncio
async def test_com_ninguem_ouvindo_o_medidor_nem_nasce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custo zero com a sala vazia: nem thread, nem `parec`, nem processo.

    É o degrau menor da sprint feito desenho. Se o medidor nascesse no boot,
    uma máquina onde ninguém nunca abre o microfone pagaria uma thread parada
    para sempre.
    """
    nascidos: list[Any] = []
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})

    def _fontes_para(uniqs: list[str], _mesa: list[str]) -> dict[str, str]:
        return {u: f"fonte-de-{u}" for u in uniqs}

    monkeypatch.setattr(mod, "_fontes_para", _fontes_para)
    peca_a = types.ModuleType(mod.MODULO_DE_QUEM_OUVE)
    peca_a.quem_ouve_agora = lambda _u: {UM: []}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod.MODULO_DE_QUEM_OUVE, peca_a)

    def _nascer() -> Any:
        medidor = _MedidorFalso(lambda _s: {})
        nascidos.append(medidor)
        return medidor

    peca_b = types.ModuleType(mod.MODULO_DO_NIVEL)
    peca_b.NivelDoMicrofone = _nascer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod.MODULO_DO_NIVEL, peca_b)

    daemon = _Daemon(controle)
    await _rodar(daemon, voltas=150)

    assert nascidos == [], (
        "o medidor nasceu com ninguém ouvindo — é uma thread e um `parec` "
        "pagos para responder uma pergunta que a §1.1 já respondeu"
    )


@pytest.mark.asyncio
async def test_o_pactl_nunca_roda_no_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que fala com o mundo vai para o executor, e a régua nomeia quem foi.

    A PEÇA A dispara três `pactl` com `timeout` de 3 s cada, e a resolução de
    fonte mais dois. Chamados de dentro da corrotina, congelam o mesmo event
    loop que serve o IPC e reafirma o report de saída — até 9 s no pior caso,
    que na máquina dela se lê como travamento.
    """
    controle = _Controle(uniqs=[UM], mudo={UM: False}, bateria={UM: 90})
    _pecas(
        monkeypatch,
        ouvintes=lambda _u: {UM: ["chrome"]},
        captando=lambda seguidos: dict.fromkeys(seguidos, True),
    )
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=80)

    assert "_quem_ouve" in daemon.no_executor, (
        "a PEÇA A foi chamada de dentro do event loop: até 9 s de daemon "
        "congelado por leitura"
    )
    assert "_fontes_para" in daemon.no_executor, (
        "a resolução de fonte (dois `pactl`) rodou no event loop"
    )
