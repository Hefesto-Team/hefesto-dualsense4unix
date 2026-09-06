"""RESERVA-DO-POSTO-01 — o instrumento que a medição dela vai usar.

**A sprint se divide em duas, e esta metade é a de código** (ROTA CORRIGIDA,
06/09/2026): o INSTRUMENTO é de agente, a MEDIÇÃO é dela. `PRIMARIO_RESERVA_SEC`
**não se mexe aqui** — *"ela mede antes de eu fixar"* —, e o roteiro de bancada
da §5 corre na MESA-DE-QUATRO-01.

O que sobra para o código, e é o que este arquivo morde:

1. **o campo `transporte` na queda** (§RESERVA-1, a metade que faltava). O nível
   já subiu para INFO em 26/08 e tem régua própria em
   `test_reserva_do_posto_01_os_eventos_falam.py` — este arquivo não a repete,
   importa dela o journal e mede o que é novo: uma queda no cabo e uma queda no
   rádio não são a mesma amostra, e sem o campo o caderno recebe uma mistura de
   duas populações que ninguém consegue separar depois;
2. **a trava que impede a constante de sessão de atravessar a leva**
   (§RESERVA-2). A medição roda com a janela aberta de par em par (3600 s, para
   que NENHUMA volta caduque e a amostra seja honesta); um `3600.0` esquecido
   deixaria o posto do Jogador 1 pendurado por uma hora, e quebraria pelo resto
   do boot o gesto oposto — dela também — de desligar um controle e seguir
   jogando com o outro;
3. **o que o produto FAZ quando o deposto volta pelo CABO** (§RESERVA-5). É
   teste de CARACTERIZAÇÃO, e é de propósito: a §6 da sprint infere do código
   que plugar o controle descarregado na tomada tomaria o Jogador 1 de quem
   está jogando, e manda medir antes de perguntar. A pergunta é dela (§7.3) e
   não se decide aqui — mas ela agora vai com o fato ao lado.

**Nada aqui toca no aparelho.** A bancada de queda é dublê declarado
(`test_coop_bancada_de_queda_do_primario`), o relógio é virtual e ninguém dorme.
"""
from __future__ import annotations

import io

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PRIMARIO_RESERVA_SEC
from tests.unit.test_coop_bancada_de_queda_do_primario import (
    UNIQ_A,
    UNIQ_B,
    Bancada,
)
from tests.unit.test_reserva_do_posto_01_os_eventos_falam import (
    P1,
    P2,
    _backend,
    _eventos,
    _HandleFalso,
    journal,
)

#: O journal vem de lá inteiro — é a MESMA régua de nível (o `wrapper_class`
#: real do produto), e duplicá-la aqui seria manter duas versões de um
#: instrumento que já custou uma cicatriz para ficar de pé.
__all__ = ["journal"]

#: Teto do que ainda é um valor de PRODUÇÃO para `PRIMARIO_RESERVA_SEC`.
#: Acima disto só existe valor de sessão de medição (a §RESERVA-2 usa 3600 s).
#: Não é o número escolhido — é a fronteira entre "prazo" e "esquecimento".
TETO_DE_PRODUCAO_SEC = 120.0


def _queda(transporte: str, journal_buf: io.StringIO) -> dict[str, object]:
    """Derruba o primário com o backend nesse transporte e devolve o evento."""
    ctrl = _backend({P1: _HandleFalso()}, primario=P1)
    ctrl._transport = transporte  # type: ignore[assignment]
    ctrl._reservar_o_posto_de_primario(P1)
    quedas = [
        evento
        for evento in _eventos(journal_buf)
        if evento.get("event") == "primario_deposto_reservado"
    ]
    assert len(quedas) == 1, f"esperava UMA queda no journal, vi {quedas}"
    return quedas[0]


def test_a_queda_e_a_caducidade_saem_em_info(journal: io.StringIO) -> None:
    """A MORDIDA da §RESERVA-1: os dois instantes do prazo, com o transporte.

    `t0` é o `primario_deposto_reservado` e `t1` o desfecho. Sem o campo
    `transporte` no primeiro, o caderno da §5.2 tem a coluna `transporte` para
    preencher e nada para preenchê-la — a queda no cabo e a queda no rádio
    entram como a mesma amostra.

    Arrancada a cura (tirando `transporte=self._transport` do `logger.info`),
    este teste reprova dizendo que a queda saiu sem dizer de onde.
    """
    queda = _queda("bt", journal)
    assert queda.get("key") == P1
    assert queda.get("transporte") == "bt", (
        "a queda do primário saiu no journal sem `transporte` — no caderno da "
        "medição a coluna do transporte fica vazia, e uma queda no cabo passa "
        f"a valer tanto quanto uma no rádio. Evento visto: {queda}"
    )

    # E o desfecho ALTERNATIVO, que é a metade que o journal escondia até 26/08.
    caduca = _backend({P2: _HandleFalso()}, primario=P2)
    caduca._reservar_o_posto_de_primario(P1)
    caduca._relogio.agora += PRIMARIO_RESERVA_SEC + 1.0
    assert caduca._posto_reservado_de_volta() is None

    nomes = [str(evento.get("event")) for evento in _eventos(journal)]
    assert "primario_reserva_caducou" in nomes, (
        "a volta que ESTOUROU o prazo não deixou linha no journal — medir a "
        "distribuição assim é contar só as amostras que já cabem no número "
        f"que se quer justificar. Eventos vistos: {nomes}"
    )


def test_o_transporte_da_queda_e_lido_e_nao_digitado(journal: io.StringIO) -> None:
    """A régua que digita o que devia LER é o defeito recorrente desta casa.

    Um `transporte="bt"` fixo no `logger.info` passaria no teste acima e
    mentiria em toda queda no cabo. Aqui o backend está no cabo, e o journal
    tem de dizer cabo.
    """
    assert _queda("usb", journal).get("transporte") == "usb", (
        "o campo não acompanha o transporte do controle — ele está sendo "
        "escrito, não lido"
    )


def test_a_constante_de_producao_nao_saiu_da_bancada() -> None:
    """A trava da §RESERVA-2: a janela da sessão de medição não vai para o disco.

    A medição da §5 roda com `PRIMARIO_RESERVA_SEC` em 3600 s — grande o
    bastante para que NENHUMA volta caduque, que é o que torna a amostra
    honesta (caminho (a) da §RESERVA-2: editar a constante e reiniciar o
    daemon, o único dos três que não deixa superfície nova depois). O preço de
    esquecer de voltar é assimétrico: o posto do Jogador 1 fica pendurado por
    uma hora num controle que ela desligou de propósito, e o gesto de seguir
    jogando com o outro quebra pelo resto do boot.

    **Este teste não escolhe o número** — ele só afirma que o que está no disco
    ainda é um PRAZO. Quando a bancada dela correr, o valor novo entra pela
    §RESERVA-3 e passa por aqui igual.
    """
    assert PRIMARIO_RESERVA_SEC > 0.0, (
        "prazo zero ou negativo não é reserva: a caducidade dispara no mesmo "
        "instante da queda e o posto nunca é guardado"
    )
    assert PRIMARIO_RESERVA_SEC <= TETO_DE_PRODUCAO_SEC, (
        f"`PRIMARIO_RESERVA_SEC` está em {PRIMARIO_RESERVA_SEC} s — acima do "
        f"teto de produção ({TETO_DE_PRODUCAO_SEC} s), isto é a janela de uma "
        "SESSÃO DE MEDIÇÃO que escapou para o commit. Ela desliga um controle "
        "e continua com o outro; por todo esse tempo o produto ainda guarda o "
        "posto para o que ela desligou"
    )


class TestAVoltaPeloCabo:
    """§RESERVA-5 — o que o produto faz, medido, para a pergunta da §7.3.

    O `norm_mac` é estável entre USB e BT, então o handle que nasce no cabo é
    do MESMO controle: a reserva não tem como distinguir "voltou para jogar" de
    "voltou para carregar". A §6 infere disso que plugar o controle morto na
    tomada durante a partida tomaria o Jogador 1 de quem está jogando. Aqui
    isso deixa de ser inferência.
    """

    def test_a_bancada_sabe_a_diferenca_entre_o_cabo_e_o_radio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valida o INSTRUMENTO antes de acreditar nele.

        Se o botão de transporte da bancada fosse inerte, o teste abaixo mediria
        uma volta pelo rádio achando que mede uma volta pelo cabo — e diria
        "verde" sobre a pergunta errada.
        """
        bancada = Bancada(monkeypatch)
        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.get_transport() == "bt"

        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        bancada.sentar(UNIQ_A, transporte="usb")
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.get_transport() == "usb", (
            "a bancada não distingue o cabo do rádio — o `conType` do dublê "
            "não chega ao `_detect_transport` do produto"
        )

    def test_a_volta_pelo_cabo_retoma_o_posto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CARACTERIZAÇÃO: o deposto no rádio que volta pelo CABO retoma o posto.

        O roteiro é o da §RESERVA-5: dois controles no rádio, o Jogador 1 cai,
        ela segue jogando com o outro, e DENTRO da janela o controle derrubado
        é plugado no cabo — para carregar, não para entrar no jogo.

        **Este teste afirma o que o produto FAZ hoje, não o que ele deve
        fazer.** Se a decisão da §7.3 for "não retomar pelo cabo", é ELE que
        muda, e a mudança tem de ser deliberada: quem inverter a asserção sem a
        palavra dela está decidindo por ela.
        """
        bancada = Bancada(monkeypatch)
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.primary_uniq == UNIQ_A

        # A bateria acabou: A cai, e B — o controle que ela tem na mão — assume.
        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.primary_uniq == UNIQ_B, "com A fora, B TEM de assumir"

        # Dentro da janela, A é plugado na tomada. Volta pelo cabo.
        bancada.relogio.avancar(PRIMARIO_RESERVA_SEC / 2.0)
        bancada.sentar(UNIQ_A, transporte="usb")
        bancada.tique_do_reconnect_loop()

        assert bancada.inst.primary_uniq == UNIQ_A, (
            "a caracterização mudou: o deposto que volta pelo cabo NÃO retoma "
            "mais o posto. Se foi decisão dela (§7.3), este teste e a §6 da "
            "sprint mudam junto"
        )
        assert bancada.inst.get_transport() == "usb", (
            "a retomada não refez o `_detect_transport` — o daemon acha que o "
            "primário está no rádio quando ele voltou pelo cabo"
        )

    def test_passada_a_janela_a_tomada_nao_toma_o_posto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O outro lado, e é ele que limita o estrago do de cima.

        Fora da janela não há reserva nenhuma a exercer: quem está na mesa fica
        com o posto, e plugar o controle morto na tomada é só carregar. É por
        isso que o tamanho da janela é a pergunta inteira desta sprint — e por
        isso ela é medida, não escolhida por analogia.
        """
        bancada = Bancada(monkeypatch)
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()

        bancada.relogio.avancar(PRIMARIO_RESERVA_SEC + 1.0)
        bancada.sentar(UNIQ_A, transporte="usb")
        bancada.tique_do_reconnect_loop()

        assert bancada.inst.primary_uniq == UNIQ_B
