"""SOM-PAINEL-01 — o nó que morre não deixa um MONITOR de herança.

A QUEIXA, 16/09/2026, com o DualSense no rádio
----------------------------------------------------
*"o canal de som não mostra os canais de entrada e saída"* — e, na mesma
frase, o jogo que não a ouvia: *"é como se ele tivesse mutado digitalmente"*.

O QUE FOI MEDIDO NA BANCADA
---------------------------------
Duas leituras do mesmo servidor, a minutos de distância::

    COM o controle na mesa   fonte padrão = o canal do controle
    SEM o controle na mesa   fonte padrão = o monitor de uma saída digital

Um monitor é a saída RELIDA, não uma entrada. Quem pedir a fonte padrão grava
o som que SAI — e o medidor mostra sinal, então PARECE funcionar. É a falha
que se disfarça de sucesso, e as duas queixas de uso saem dela: o painel escreve
"Nenhum dispositivo selecionado" (um monitor não é dispositivo de entrada) e o
jogo grava silêncio.

O DEFEITO NÃO É NOVO — E É ISSO QUE ESTA RÉGUA MEDE
----------------------------------------------------
A casa tem a régua desde 29/07/2026: a FONTE-PADRAO-01 do `scripts/doctor.sh`,
com a causa escrita. O que é novo é a **REINCIDÊNCIA**: o buraco se reabre a
cada ciclo de o nó nascer e morrer, e o `doctor` só roda quando alguém o
chama. Quem fecha o buraco a cada ciclo tem de ser o dono do ciclo — o
`BtMicSubsystem`, que abre o canal, o vê publicado e o derruba.

**E O BURACO MORA NA AUSÊNCIA.** Uma régua que só confira o estado com o
controle PRESENTE não mede nada: com o controle na mesa a fonte padrão está
certa, e foi por isso que o defeito atravessou semanas sendo lido como
problema do painel do COSMIC.

O QUE ESTE ARQUIVO NÃO MEDE
----------------------------
Som, e nenhum `pactl` de verdade sai daqui: o servidor de som do usuário tem quatro
DualSense em cima. O leitor da fonte padrão é dublado em todas as réguas.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic as supervisor

_P1 = "aabbcc000001"

_NO_DO_CONTROLE = "hefesto_mic_aabbcc"
_O_MONITOR_QUE_HERDA = "alsa_output.pci-0000_0c_00.4.iec958-stereo.monitor"
_UM_MICROFONE_DE_VERDADE = "alsa_input.pci-0000_0c_00.4.analog-stereo"


class _EleitorDeMentira:
    """O eleitor da sessão, dublado. Conta as perguntas e o que recebeu.

    `recusa` reproduz o desfecho MEDIDO nesta bancada: o único microfone do usuário é
    o do DualSense, e com o controle fora da mesa não sobra fonte de captura
    com porta usável — então o eleitor recusa e NADA é escrito.

    A PORTA É `passar_o_padrao` desde 29/09/2026 (A-VOLTA-DO-MICROFONE-NAO-
    ELEGE-CONTROLE-01): a do nó que morre faz a mesma pergunta do botão, e a
    faz pelo laço do daemon. Era `devolver_o_microfone`, chamado do fio.
    """

    def __init__(self, *, ok: bool = True, alvo: str | None = None) -> None:
        self.chamadas: list[tuple[Any, ...]] = []
        self._ok = ok
        self._alvo = alvo

    def passar_o_padrao(self, *args: Any, **kwargs: Any) -> Any:
        self.chamadas.append((args, kwargs))

        class _R:
            ok = self._ok
            alvo = self._alvo
            ativo = self._alvo
            motivo = "" if self._ok else "não há microfone para onde voltar"

        return _R()


class _DaemonComEleitor:
    """O daemon, só com o que a porta do nó procura nele."""

    def __init__(self, eleitor: Any) -> None:
        self._eleitor_de_microfone = eleitor
        self.controller = _BackendVazio()

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


class _BackendVazio:
    """Nenhum controle na mesa — o estado DEPOIS de ela desligar o controle."""

    def describe_controllers(self) -> list[dict[str, Any]]:
        return []


class _GerenciadorSemPonte:
    """O gerenciador de pontes do rádio, vazio: esta régua mede a MORTE."""

    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}

    def reconciliar(self, alvos: list[Any]) -> None:
        del alvos

    def dormir(self, segundos: float) -> bool:
        del segundos
        return True

    def parar(self) -> None:
        return None


def _supervisor_com(
    monkeypatch: pytest.MonkeyPatch,
    *,
    eleitor: Any,
    de_pe: list[str],
    bruto: list[str | None],
) -> Any:
    """Um `BtMicSubsystem` dirigível: a mesa, o que está de pé e a escolha."""
    sub = supervisor.BtMicSubsystem(registro=supervisor.RegistroDePedidosDeCanal())
    sub._gerenciador = _GerenciadorSemPonte()
    sub._backend = _BackendVazio()
    sub._daemon = _DaemonComEleitor(eleitor)
    monkeypatch.setattr(sub, "_nomes_de_pe", lambda: frozenset(de_pe))
    monkeypatch.setattr(
        supervisor, "fonte_padrao_crua", lambda ler=None: bruto[0], raising=True
    )
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

    monkeypatch.setattr(bt, "nos_dualsense_bluetooth", lambda: [])
    return sub


async def _drenar(sub: Any) -> None:
    """Espera as heranças que o fio entregou ao laço terminarem."""
    for _ in range(50):
        await asyncio.sleep(0)
        em_voo = [t for t in sub._herancas_em_voo if not t.done()]
        if em_voo:
            await asyncio.gather(*em_voo)


async def _porta_do_no(sub: Any) -> Any:
    """`_devolver_a_fonte_padrao` NO FIO, como no daemon, com o laço de pé."""
    sub._laco = asyncio.get_running_loop()
    veredicto = await asyncio.to_thread(sub._devolver_a_fonte_padrao)
    await _drenar(sub)
    return veredicto


async def _uma_volta_do_laco(sub: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Roda UMA volta de `BtMicSubsystem._loop` NO FIO e devolve o que ele engoliu."""
    engolidas: list[str] = []
    debug_de_verdade = supervisor.logger.debug

    def _espiar(evento: str, **campos: Any) -> Any:
        if evento == "bt_mic_reconciliacao_falhou":
            engolidas.append(str(campos))
        return debug_de_verdade(evento, **campos)

    monkeypatch.setattr(supervisor.logger, "debug", _espiar)
    monkeypatch.setattr(sub, "_dormir", lambda gerenciador: True)
    sub._laco = asyncio.get_running_loop()
    await asyncio.to_thread(sub._loop)
    await _drenar(sub)
    return engolidas


@pytest.mark.parametrize(
    ("bruto", "buraco", "eleito"),
    [
        (_O_MONITOR_QUE_HERDA, "monitor", _O_MONITOR_QUE_HERDA),
        ("alsa_output.usb-Sony…Speaker__sink.monitor", "monitor", None),
        ("auto_null.monitor", "vazio", "auto_null.monitor"),
        ("auto_null", "vazio", "auto_null"),
        ("@DEFAULT_SOURCE@", "vazio", "@DEFAULT_SOURCE@"),
        ("", "vazio", None),
        ("   ", "vazio", None),
        (None, "nao_sei", None),
        (_UM_MICROFONE_DE_VERDADE, "nenhum", _UM_MICROFONE_DE_VERDADE),
    ],
)
def test_a_classificacao_da_fonte_padrao(
    bruto: str | None, buraco: str, eleito: str | None
) -> None:
    """As palavras estão digitadas à mão, e é isso que faz a régua morder."""
    veredicto = supervisor.a_heranca_do_no_morto(bruto, morreram=frozenset())
    assert veredicto.buraco == buraco
    if eleito is not None:
        assert veredicto.eleito == eleito


def test_o_no_morto_ainda_pedido_e_fantasma() -> None:
    """O padrão aponta para o nó que acabou de morrer."""
    veredicto = supervisor.a_heranca_do_no_morto(
        _NO_DO_CONTROLE, morreram=frozenset({_NO_DO_CONTROLE})
    )
    assert veredicto.buraco == "fantasma"
    assert veredicto.eleito == _NO_DO_CONTROLE
    assert veredicto.aberto is True


def test_nao_sei_nunca_conta_como_buraco() -> None:
    """`pactl` que não respondeu não dispara devolução nenhuma.

    É a regra desta casa — *"não sei" nunca vira "saiu"*. Sem ela, um servidor
    ocupado faria o produto reeleger a fonte padrão de produto às cegas.

    MORDIDA: ponha `BURACO_NAO_SEI` na tupla de `aberto` e a régua cai.
    """
    assert supervisor.a_heranca_do_no_morto(None, morreram=frozenset()).aberto is False


@pytest.mark.asyncio
async def test_o_ciclo_nascer_e_morrer_devolve_a_fonte_padrao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O nó nasce, é o padrão, MORRE — e alguém devolve a eleição."""
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=eleitor, de_pe=de_pe, bruto=bruto)

    assert await _uma_volta_do_laco(sub, monkeypatch) == []
    assert eleitor.chamadas == [], "a volta com o nó DE PÉ não devolve nada"

    de_pe.clear()
    bruto[0] = _O_MONITOR_QUE_HERDA

    assert await _uma_volta_do_laco(sub, monkeypatch) == []
    assert len(eleitor.chamadas) == 1, (
        "o nó morreu com um MONITOR eleito e ninguém devolveu a fonte padrão"
    )


@pytest.mark.asyncio
async def test_a_devolucao_passa_pelo_eleitor_da_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem devolve é o eleitor pendurado no DAEMON, não um recém-criado."""
    sentinela = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=sentinela, de_pe=de_pe, bruto=bruto)

    await _porta_do_no(sub)
    de_pe.clear()
    bruto[0] = _O_MONITOR_QUE_HERDA
    await _porta_do_no(sub)

    assert len(sentinela.chamadas) == 1
    assert sentinela.chamadas[0] == (([], []), {}), (
        "o alvo NÃO se digita aqui: a porta entrega só quem está no ar (ninguém, "
        "nesta mesa vazia) e quem está na mesa; quem escolhe é o eleitor, e é "
        "por isso que nenhum caminho nosso pode terminar num monitor"
    )


@pytest.mark.asyncio
async def test_a_recusa_do_eleitor_nomeia_o_no_que_ficou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem microfone para onde voltar, a denúncia diz QUAL nó herdou.

    É o estado MEDIDO desta bancada: o único microfone do usuário é o do DualSense, e
    com o controle fora da mesa não há fonte de captura com porta usável. O
    eleitor recusa, nada é escrito — e o que não pode faltar é o NOME, porque
    uma denúncia sem ele obriga a próxima pessoa a remedir o que já foi medido.

    MORDIDA: tire `eleito=heranca.eleito` do `logger.warning` e a régua cai.
    """
    avisos: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        supervisor.logger, "warning", lambda ev, **c: avisos.append((ev, c))
    )
    eleitor = _EleitorDeMentira(ok=False)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=eleitor, de_pe=de_pe, bruto=bruto)

    await _porta_do_no(sub)
    de_pe.clear()
    bruto[0] = _O_MONITOR_QUE_HERDA
    await _porta_do_no(sub)

    denuncias = [c for ev, c in avisos if ev == "bt_mic_heranca_do_no_morto"]
    assert len(denuncias) == 1
    assert denuncias[0]["eleito"] == _O_MONITOR_QUE_HERDA
    assert denuncias[0]["curado"] is False
    assert denuncias[0]["morreram"] == [_NO_DO_CONTROLE]


@pytest.mark.asyncio
async def test_o_padrao_que_ja_e_microfone_de_verdade_nao_e_tocado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Morreu um nó nosso, mas o padrão é uma entrada de verdade: não se mexe."""
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=eleitor, de_pe=de_pe, bruto=bruto)

    await _porta_do_no(sub)
    de_pe.clear()
    bruto[0] = _UM_MICROFONE_DE_VERDADE
    await _porta_do_no(sub)

    assert eleitor.chamadas == []


@pytest.mark.asyncio
async def test_o_gatilho_e_a_morte_e_nunca_a_presenca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O daemon sobe com o servidor JÁ num monitor — e não se mexe nisso."""
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    sub = _supervisor_com(
        monkeypatch,
        eleitor=eleitor,
        de_pe=[_NO_DO_CONTROLE],
        bruto=[_O_MONITOR_QUE_HERDA],
    )

    assert await _porta_do_no(sub) is None
    assert eleitor.chamadas == []


@pytest.mark.asyncio
async def test_o_pactl_mudo_nao_dispara_devolucao(monkeypatch: pytest.MonkeyPatch) -> None:
    """O nó morreu e o `pactl` não respondeu: não se devolve às cegas."""
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=eleitor, de_pe=de_pe, bruto=bruto)

    await _porta_do_no(sub)
    de_pe.clear()
    bruto[0] = None
    veredicto = await _porta_do_no(sub)

    assert veredicto is not None
    assert veredicto.buraco == "nao_sei"
    assert eleitor.chamadas == []


def test_o_leitor_da_fonte_padrao_nunca_levanta() -> None:
    """Dublê que explode vale como ausência — o laço não cai por causa disto."""

    def _explode() -> str:
        raise RuntimeError("o servidor de som não atendeu")

    assert supervisor.fonte_padrao_crua(_explode) is None


def test_o_uniq_da_fixture_nao_vem_de_endereco_real() -> None:
    """A faixa de fixture desta casa, escrita aqui para não se perder."""
    assert _P1.startswith("aabbcc")
