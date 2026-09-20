"""SOM-PAINEL-01 — o nó que morre não deixa um MONITOR de herança.

A QUEIXA DELA, 16/09/2026, com o DualSense no rádio
----------------------------------------------------
*"o canal de som não mostra os canais de entrada e saída"* — e, na mesma
frase, o jogo que não a ouvia: *"é como se ele tivesse mutado digitalmente"*.

O QUE FOI MEDIDO NA MÁQUINA DELA
---------------------------------
Duas leituras do mesmo servidor, a minutos de distância::

    COM o controle na mesa   fonte padrão = o canal do controle
    SEM o controle na mesa   fonte padrão = o monitor de uma saída digital

Um monitor é a saída RELIDA, não uma entrada. Quem pedir a fonte padrão grava
o som que SAI — e o medidor mostra sinal, então PARECE funcionar. É a falha
que se disfarça de sucesso, e as duas queixas dela saem dela: o painel escreve
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
Som, e nenhum `pactl` de verdade sai daqui: o servidor de som dela tem quatro
DualSense em cima. O leitor da fonte padrão é dublado em todas as réguas.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic as supervisor

#: Endereços SINTÉTICOS. A faixa `aa:bb:cc` é a desta casa para fixture, e um
#: endereço de teste nunca se deriva do real — nem mascarado.
_P1 = "aabbcc000001"

#: Os NOMES, escritos por extenso de propósito. Montá-los a partir das
#: constantes que o produto lê (`PREFIXO_SOURCE_CANAL_DO_MIC`,
#: `_SUFIXO_DE_MONITOR`) faria a régua construir o esperado com o mesmo dado
#: que a função classifica — tautologia, que passa com a cura arrancada.
_NO_DO_CONTROLE = "hefesto_mic_aabbcc"
_O_MONITOR_QUE_HERDA = "alsa_output.pci-0000_0c_00.4.iec958-stereo.monitor"
_UM_MICROFONE_DE_VERDADE = "alsa_input.pci-0000_0c_00.4.analog-stereo"


class _EleitorDeMentira:
    """O eleitor da sessão, dublado. Conta as devoluções e o que recebeu.

    `recusa` reproduz o desfecho MEDIDO nesta bancada: o único microfone dela é
    o do DualSense, e com o controle fora da mesa não sobra fonte de captura
    com porta usável — então o eleitor recusa e NADA é escrito.
    """

    def __init__(self, *, ok: bool = True, alvo: str | None = None) -> None:
        self.chamadas: list[tuple[Any, ...]] = []
        self._ok = ok
        self._alvo = alvo

    def devolver_o_microfone(self, *args: Any, **kwargs: Any) -> Any:
        self.chamadas.append((args, kwargs))

        class _R:
            ok = self._ok
            alvo = self._alvo
            ativo = self._alvo
            motivo = "" if self._ok else "não há microfone para onde voltar"

        return _R()


class _DaemonComEleitor:
    """O daemon, só com o que `hotkey._eleitor` procura nele."""

    def __init__(self, eleitor: Any) -> None:
        self._eleitor_de_microfone = eleitor


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
    """Um `BtMicSubsystem` dirigível: a mesa, o que está de pé e a escolha.

    `de_pe` e `bruto` são LISTAS de propósito — a régua as edita entre as
    voltas do laço, que é como o ciclo nascer-e-morrer acontece na mesa dela.
    """
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


def _uma_volta_do_laco(sub: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Roda UMA volta de `BtMicSubsystem._loop` e devolve o que ele engoliu.

    **O laço engole toda exceção**, e é por isso que a lista é asserida: sem
    ela, um erro a meio caminho faria a régua reprovar dizendo *"a devolução
    não foi chamada"* — a mesma frase do defeito, apontando para outra coisa.
    """
    engolidas: list[str] = []
    debug_de_verdade = supervisor.logger.debug

    def _espiar(evento: str, **campos: Any) -> Any:
        if evento == "bt_mic_reconciliacao_falhou":
            engolidas.append(str(campos))
        return debug_de_verdade(evento, **campos)

    monkeypatch.setattr(supervisor.logger, "debug", _espiar)
    monkeypatch.setattr(sub, "_dormir", lambda gerenciador: True)
    sub._loop()
    return engolidas


# ---------------------------------------------------------------------------
# A REGRA PURA — e os literais são o oráculo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bruto", "buraco", "eleito"),
    [
        (_O_MONITOR_QUE_HERDA, "monitor", _O_MONITOR_QUE_HERDA),
        ("alsa_output.usb-Sony…Speaker__sink.monitor", "monitor", None),
        # A ESCASSEZ VEM ANTES DO MONITOR, e a ordem é a do dono
        # (`eleicao_de_microfone.fonte_ativa`): o `auto_null` é o nó de
        # mentira que o PipeWire ergue quando NÃO HÁ aparelho nenhum, e o
        # monitor dele não é a saída de ninguém. Chamá-lo de `monitor` mandaria
        # a próxima pessoa procurar qual saída está sendo relida — não há
        # nenhuma. Os dois desfechos abrem o buraco do mesmo jeito.
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
    """As palavras estão digitadas à mão, e é isso que faz a régua morder.

    O `eleito` só é conferido quando a tabela o nomeia: nas linhas em que ele é
    `None` a régua mede a CLASSE, que é o que aquela linha existe para provar.

    MORDIDA: tire o ramo do `.monitor` de `a_heranca_do_no_morto` e as três
    primeiras linhas viram `nenhum` — a fonte padrão da máquina dela passa a
    ser aceita como microfone.
    """
    veredicto = supervisor.a_heranca_do_no_morto(bruto, morreram=frozenset())
    assert veredicto.buraco == buraco
    if eleito is not None:
        assert veredicto.eleito == eleito


def test_o_no_morto_ainda_pedido_e_fantasma() -> None:
    """O padrão aponta para o nó que acabou de morrer.

    É o mecanismo escrito na FONTE-PADRAO-01: o
    `default.configured.audio.source` continua pedindo um nó que não existe, o
    WirePlumber cai na eleição automática, e o monitor vence.

    MORDIDA: tire o `if nome in morreram` e este caso vira `nenhum` — o buraco
    fica aberto exatamente no instante em que ele nasce.
    """
    veredicto = supervisor.a_heranca_do_no_morto(
        _NO_DO_CONTROLE, morreram=frozenset({_NO_DO_CONTROLE})
    )
    assert veredicto.buraco == "fantasma"
    assert veredicto.eleito == _NO_DO_CONTROLE
    assert veredicto.aberto is True


def test_nao_sei_nunca_conta_como_buraco() -> None:
    """`pactl` que não respondeu não dispara devolução nenhuma.

    É a regra desta casa — *"não sei" nunca vira "saiu"*. Sem ela, um servidor
    ocupado faria o produto reeleger a fonte padrão dela às cegas.

    MORDIDA: ponha `BURACO_NAO_SEI` na tupla de `aberto` e a régua cai.
    """
    assert supervisor.a_heranca_do_no_morto(None, morreram=frozenset()).aberto is False


# ---------------------------------------------------------------------------
# O CICLO — e o buraco mora na AUSÊNCIA
# ---------------------------------------------------------------------------


def test_o_ciclo_nascer_e_morrer_devolve_a_fonte_padrao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O nó nasce, é o padrão, MORRE — e alguém devolve a eleição.

    Aqui não se chama `_devolver_a_fonte_padrao`: roda-se o LAÇO, que é o que
    corre na máquina dela de `RECONCILIA_S` em `RECONCILIA_S`. Um método que
    só o teste chama é um método que o daemon não chama — e foi exatamente
    esse o defeito: `devolver_o_microfone` existia e só o BOTÃO do microfone a
    abria.

    **A PRIMEIRA VOLTA NÃO PODE ACUSAR**, e a régua mede isso na mesma corrida:
    com o nó de pé e o padrão apontado para ele, ninguém devolve nada.

    MORDIDA: tire `self._devolver_a_fonte_padrao()` do `_loop` e a segunda
    asserção cai com zero chamadas — a máquina dela fica com o monitor.
    """
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=eleitor, de_pe=de_pe, bruto=bruto)

    assert _uma_volta_do_laco(sub, monkeypatch) == []
    assert eleitor.chamadas == [], "a volta com o nó DE PÉ não devolve nada"

    # Ela desligou o controle: o nó cai e o WirePlumber elege o monitor.
    de_pe.clear()
    bruto[0] = _O_MONITOR_QUE_HERDA

    assert _uma_volta_do_laco(sub, monkeypatch) == []
    assert len(eleitor.chamadas) == 1, (
        "o nó morreu com um MONITOR eleito e ninguém devolveu a fonte padrão"
    )


def test_a_devolucao_passa_pelo_eleitor_da_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem devolve é o eleitor pendurado no DAEMON, não um recém-criado.

    O eleitor guarda a fonte padrão de antes da primeira eleição e de quem é o
    canal da mesa agora. Um segundo eleitor que nascesse neste caminho teria
    memória própria, e a luz do plástico e a fonte padrão passariam a dizer
    coisas diferentes.

    O oráculo é uma SENTINELA entregue pelo daemon: a régua não reconstrói
    nada, ela confere que o objeto chamado é o mesmo que ela pendurou.

    MORDIDA: troque `self._eleitor_da_sessao()` por `EleitorDeMicrofone()` e a
    sentinela nunca é chamada.
    """
    sentinela = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=sentinela, de_pe=de_pe, bruto=bruto)

    sub._devolver_a_fonte_padrao()
    de_pe.clear()
    bruto[0] = _O_MONITOR_QUE_HERDA
    sub._devolver_a_fonte_padrao()

    assert len(sentinela.chamadas) == 1
    assert sentinela.chamadas[0] == ((), {}), (
        "o alvo NÃO se digita aqui: quem escolhe é o eleitor, e é por isso que "
        "nenhum caminho nosso pode terminar num monitor"
    )


def test_a_recusa_do_eleitor_nomeia_o_no_que_ficou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem microfone para onde voltar, a denúncia diz QUAL nó herdou.

    É o estado MEDIDO desta bancada: o único microfone dela é o do DualSense, e
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

    sub._devolver_a_fonte_padrao()
    de_pe.clear()
    bruto[0] = _O_MONITOR_QUE_HERDA
    sub._devolver_a_fonte_padrao()

    denuncias = [c for ev, c in avisos if ev == "bt_mic_heranca_do_no_morto"]
    assert len(denuncias) == 1
    assert denuncias[0]["eleito"] == _O_MONITOR_QUE_HERDA
    assert denuncias[0]["curado"] is False
    assert denuncias[0]["morreram"] == [_NO_DO_CONTROLE]


def test_o_padrao_que_ja_e_microfone_de_verdade_nao_e_tocado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Morreu um nó nosso, mas o padrão é uma entrada de verdade: não se mexe.

    O produto é de acessibilidade e a fonte padrão é da máquina inteira.
    Reeleger porque um nó NOSSO caiu tiraria da pessoa a escolha que ela já
    tinha — o defeito simétrico ao que esta sprint cura.

    MORDIDA: faça `aberto` devolver `True` para `BURACO_NENHUM` e a régua cai.
    """
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=eleitor, de_pe=de_pe, bruto=bruto)

    sub._devolver_a_fonte_padrao()
    de_pe.clear()
    bruto[0] = _UM_MICROFONE_DE_VERDADE
    sub._devolver_a_fonte_padrao()

    assert eleitor.chamadas == []


def test_o_gatilho_e_a_morte_e_nunca_a_presenca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O daemon sobe com o servidor JÁ num monitor — e não se mexe nisso.

    Na primeira volta o canal do controle está de pé e o padrão da máquina é um
    monitor que NÃO veio de nó nosso nenhum. A fonte padrão é da máquina
    inteira, e o produto é de acessibilidade: reeleger aqui tiraria da pessoa
    uma escolha que não é nossa. Só a MORTE de um nó nosso dá o direito, porque
    só ela é buraco que nós abrimos.

    **ESTA RÉGUA NASCEU DE UMA MORDIDA QUE NÃO PEGOU.** A primeira versão
    guardava a volta anterior numa sentinela `None` e prometia medir *"a
    primeira volta não acusa"* — mas `frozenset() - qualquer coisa` já é
    vazio, e a régua
    passava com a sentinela arrancada. A sentinela saiu; o que sobrou mede o
    que de fato decide.

    MORDIDA: troque `morreram = antes - de_pe` por `morreram = de_pe` e a
    devolução passa a disparar por PRESENÇA — esta régua cai na primeira volta.
    """
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    sub = _supervisor_com(
        monkeypatch,
        eleitor=eleitor,
        de_pe=[_NO_DO_CONTROLE],
        bruto=[_O_MONITOR_QUE_HERDA],
    )

    assert sub._devolver_a_fonte_padrao() is None
    assert eleitor.chamadas == []


def test_o_pactl_mudo_nao_dispara_devolucao(monkeypatch: pytest.MonkeyPatch) -> None:
    """O nó morreu e o `pactl` não respondeu: não se devolve às cegas.

    MORDIDA: faça `fonte_padrao_crua` devolver `""` no lugar de `None` quando o
    `pactl` falha e este caso vira `vazio` — uma devolução disparada por um
    servidor ocupado.
    """
    eleitor = _EleitorDeMentira(ok=True, alvo=_UM_MICROFONE_DE_VERDADE)
    de_pe = [_NO_DO_CONTROLE]
    bruto: list[str | None] = [_NO_DO_CONTROLE]
    sub = _supervisor_com(monkeypatch, eleitor=eleitor, de_pe=de_pe, bruto=bruto)

    sub._devolver_a_fonte_padrao()
    de_pe.clear()
    bruto[0] = None
    veredicto = sub._devolver_a_fonte_padrao()

    assert veredicto is not None
    assert veredicto.buraco == "nao_sei"
    assert eleitor.chamadas == []


def test_o_leitor_da_fonte_padrao_nunca_levanta() -> None:
    """Dublê que explode vale como ausência — o laço não cai por causa disto.

    MORDIDA: tire o `try` de `fonte_padrao_crua` e esta régua vira erro.
    """

    def _explode() -> str:
        raise RuntimeError("o servidor de som não atendeu")

    assert supervisor.fonte_padrao_crua(_explode) is None


def test_o_uniq_da_fixture_nao_vem_de_endereco_real() -> None:
    """A faixa de fixture desta casa, escrita aqui para não se perder.

    Guarda contra o descuido que já custou caro: derivar endereço de teste do
    real — mesmo mascarado — põe OUI de aparelho da bancada em arquivo
    versionado.
    """
    assert _P1.startswith("aabbcc")
