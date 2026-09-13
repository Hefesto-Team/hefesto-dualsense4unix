#!/usr/bin/env python3
"""A RÉGUA DA VIGIA DA STEAM — a promessa que o cartão da 07 fazia sozinho.

O DEFEITO QUE ELA MORDE, medido em 03/09/2026: com a Steam aberta o `Consertar`
da aba 07 recusa com a frase da sentinela, e essa frase termina em *"Feche a
Steam e eu reponho"* (`sentinela_do_wrapper.frase_do_aviso`). Era promessa sem
dono — `reparar_ou_adiar` devolvia `REPARO_ADIADO_STEAM`, a recusa virava tarja
de 30 s e **nada reperguntava depois**. Para o reparo acontecer ela tinha de
fechar a Steam, LEMBRAR da tarja e voltar à aba para clicar de novo. A janela
velha cumpre a mesma frase desde 16/08, com um tique de
`carona_do_wrapper.INTERVALO_DA_VIGIA_S`.

A MORDIDA DE CADA TESTE está na docstring dele. As três que mais importam:

* tire o `VIGIA_DA_STEAM.armar()` do ramo de recusa do `consertar` e o
  `test_a_recusa_do_consertar_arma_a_vigia` reprova — é a promessa voltando a
  não ter quem a cumpra;
* troque o `cdw.passada(completa=False)` por uma cópia local da decisão (ou por
  `completa=True`) e o `test_o_tique_e_o_do_dono_e_barato` reprova — o tique
  caro abriria o `localconfig.vdf` a cada 45 s com a Steam viva;
* digite o intervalo (`45`) em vez de perguntar ao `carona_do_wrapper`, e o
  `test_o_relogio_e_perguntado_ao_dono` reprova — é a régua que digita, que
  esta casa paga desde 26/08.

A NOTÍCIA NO CARTÃO SAIU EM 13/09/2026 (TELA-CALADA-02): a frase do que a vigia
repôs vai ao `[relato]` do stderr, e o cartão diz o estado relido.

NADA AQUI TOCA A MÁQUINA DELA. A vigia SÓ arma com `HEFESTO_CARONA_WRAPPER`
religado por escrito (o `conftest.py` o desliga em todo teste, porque este
caminho ESCREVE no `localconfig.vdf`), e `carona_do_wrapper.passada` é dublado
em todos os casos — nenhum teste daqui abre um vdf de verdade.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))


@pytest.fixture()
def a07() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture()
def cdw() -> Any:
    from hefesto_dualsense4unix.app.actions import carona_do_wrapper

    return carona_do_wrapper


@pytest.fixture(autouse=True)
def _vigia_limpa(a07: Any) -> Any:
    """Nenhum caso herda a vigia do anterior.

    A NOTÍCIA GUARDADA SAIU EM 13/09/2026 (TELA-CALADA-02): a frase da vigia vai
    ao `[relato]` do stderr, e não há mais estado de tela a limpar entre casos.
    """
    a07.VIGIA_DA_STEAM.desarmar()
    yield
    a07.VIGIA_DA_STEAM.desarmar()


@pytest.fixture()
def carona_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Religa a carona POR ESCRITO — o `conftest.py` a desliga em todo teste."""
    monkeypatch.setenv("HEFESTO_CARONA_WRAPPER", "1")


def _resultado(cdw: Any, *, status: str, frase: str, adiado: bool) -> Any:
    return cdw.ResultadoDaCarona(status, frase, frozenset(), adiado)


# ---------------------------------------------------------------------------
# O DESLIGADOR — ele vem primeiro porque é o que protege a máquina dela
# ---------------------------------------------------------------------------
def test_a_vigia_nao_arma_com_a_carona_desligada(a07: Any) -> None:
    """Sem religar nada, `armar()` RECUSA — é o padrão da suíte.

    MORDIDA: apague o `if not cdw.ligada(): return False` do
    :meth:`_VigiaDaSteam.armar` e este teste reprova. Sem ele toda suíte que
    exercitasse a recusa do `Consertar` deixaria uma thread reescrevendo o
    `localconfig.vdf` REAL de quem roda os testes, de 45 em 45 segundos.
    """
    assert a07.VIGIA_DA_STEAM.armar() is False
    assert a07.VIGIA_DA_STEAM.armada() is False


# ---------------------------------------------------------------------------
# QUEM ARMA — e é sempre um clique dela que foi adiado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "qual", ["REPARO_ADIADO_STEAM", "REPARO_ADIADO_JOGO", "REPARO_ERRO"])
def test_a_recusa_do_consertar_arma_a_vigia(
    a07: Any, monkeypatch: pytest.MonkeyPatch, carona_ligada: None, qual: str
) -> None:
    """Os TRÊS desfechos que recusam armam a vigia, como o GTK faz.

    O `erro` entra de propósito: `carona_do_wrapper.passada` devolve
    ``adiado=True`` também no `REPARO_ERRO`, e o `_carona_reagir` da janela
    velha arma sobre esse mesmo campo. Um vdf trancado no meio da escrita é
    transitório.

    MORDIDA: tire o `VIGIA_DA_STEAM.armar()` do ramo de recusa e os três casos
    reprovam.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    censo = sw.Censo()
    status = getattr(sw, qual)  # o status sai do DONO, não de uma cópia daqui
    monkeypatch.setattr(sw, "reparar_ou_adiar", lambda *a, **k: (status, censo, None))
    monkeypatch.setattr(a07.VIGIA, "esquecer", lambda: None)
    # A thread não pode rodar de verdade neste caso: quem se prova aqui é o
    # ARMAR, e um tique real chamaria a passada.
    monkeypatch.setattr(a07.VIGIA_DA_STEAM, "intervalo", lambda: 3600.0)

    with pytest.raises(RuntimeError):
        a07.consertar(_ctx(), {}, None)

    assert a07.VIGIA_DA_STEAM.armada() is True


def test_o_consertar_que_deu_certo_desarma_a_vigia(
    a07: Any, monkeypatch: pytest.MonkeyPatch, carona_ligada: None
) -> None:
    """Reparo feito = nada a vigiar.

    MORDIDA: tire o `VIGIA_DA_STEAM.desarmar()` do caminho de sucesso e este
    teste reprova — uma vigia sobrevivente reabriria o vdf de 45 em 45 s para
    responder "nada a fazer" para sempre.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    monkeypatch.setattr(a07.VIGIA_DA_STEAM, "intervalo", lambda: 3600.0)
    assert a07.VIGIA_DA_STEAM.armar() is True

    censo = sw.Censo()
    monkeypatch.setattr(sw, "reparar_ou_adiar",
                        lambda *a, **k: (sw.REPARO_FEITO, censo, None))
    monkeypatch.setattr(a07.VIGIA, "esquecer", lambda: None)
    monkeypatch.setattr(a07.VIGIA, "ler", lambda: None)

    a07.consertar(_ctx(), {}, None)

    a07.VIGIA_DA_STEAM._thread.join(timeout=5)
    assert a07.VIGIA_DA_STEAM.armada() is False


# ---------------------------------------------------------------------------
# O TIQUE — barato, e do dono
# ---------------------------------------------------------------------------
def test_o_tique_e_o_do_dono_e_barato(
    a07: Any, cdw: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O tique chama `carona_do_wrapper.passada(completa=False)` e mais nada.

    `completa=False` é o que o torna barato: com a Steam viva ele pergunta ao
    `/proc` e nem abre o `localconfig.vdf`.

    MORDIDA: troque para `completa=True` (ou reescreva a decisão aqui) e este
    teste reprova.
    """
    vistos: list[dict[str, Any]] = []

    def _falsa(**kw: Any) -> Any:
        vistos.append(kw)
        return _resultado(cdw, status="adiado_sem_olhar", frase="", adiado=True)

    monkeypatch.setattr(cdw, "passada", _falsa)
    assert a07.VIGIA_DA_STEAM.tique() is True
    assert vistos == [{"completa": False}]


def test_o_tique_que_levanta_nao_desarma_a_vigia(
    a07: Any, cdw: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passada que explode = continue vigiando.

    MORDIDA: deixe a exceção subir (ou devolva `False` no `except`) e este
    teste reprova — seria a promessa morrendo em silêncio no primeiro tropeço
    de disco.
    """
    def _explode(**kw: Any) -> Any:
        raise OSError("vdf ilegível")

    monkeypatch.setattr(cdw, "passada", _explode)
    assert a07.VIGIA_DA_STEAM.tique() is True


def test_o_tique_que_repoe_para_e_esquece_a_leitura(
    a07: Any, cdw: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reposto = para de vigiar, e a leitura da aba fica velha na hora.

    MORDIDA: tire o `VIGIA.esquecer()` do tique e este teste reprova — o cartão
    continuaria mostrando o jogo como faltante por até `TTL_S` segundos depois
    de o atalho já estar de volta no vdf.
    """
    esquecidas: list[int] = []
    monkeypatch.setattr(a07.VIGIA, "esquecer", lambda: esquecidas.append(1))
    monkeypatch.setattr(
        cdw, "passada",
        lambda **kw: _resultado(cdw, status="reparo_feito",
                                frase="Reposta em 1 jogo: PRAGMATA.",
                                adiado=False))

    assert a07.VIGIA_DA_STEAM.tique() is False
    assert esquecidas == [1]


def test_a_vigia_repoe_quando_a_steam_fecha_e_se_desarma(
    a07: Any, cdw: Any, monkeypatch: pytest.MonkeyPatch, carona_ligada: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A vigia VIVE NO TEMPO: adia, adia, e repõe quando a Steam sai.

    Uma régua que rodasse o tique uma vez mediria um INSTANTE, não a promessa —
    é a lição de 29/08 (uma regressão que só aparecia aos 181 s, com 67 testes
    verdes). Aqui o relógio é encurtado e a thread roda de verdade.

    MORDIDA: faça o `_corpo` sair no primeiro tique (ou não sair nunca) e este
    teste reprova.
    """
    voltas: list[int] = []

    def _falsa(**kw: Any) -> Any:
        voltas.append(1)
        if len(voltas) < 3:
            return _resultado(cdw, status="adiado_sem_olhar", frase="",
                              adiado=True)
        return _resultado(cdw, status="reparo_feito",
                          frase="Reposta a Opção de Inicialização do Hefesto "
                                "em 1 jogo da Steam: PRAGMATA.",
                          adiado=False)

    monkeypatch.setattr(cdw, "passada", _falsa)
    monkeypatch.setattr(a07.VIGIA, "esquecer", lambda: None)
    monkeypatch.setattr(a07.VIGIA_DA_STEAM, "intervalo", lambda: 0.01)

    assert a07.VIGIA_DA_STEAM.armar() is True
    a07.VIGIA_DA_STEAM._thread.join(timeout=10)

    assert a07.VIGIA_DA_STEAM.armada() is False
    assert len(voltas) == 3
    # A FRASE VAI AO RELATO, E NÃO AO CARTÃO — TELA-CALADA-02, 13/09/2026.
    erro = capsys.readouterr().err
    assert "[relato]" in erro and "PRAGMATA" in erro


def test_uma_vigia_por_vez(
    a07: Any, monkeypatch: pytest.MonkeyPatch, carona_ligada: None
) -> None:
    """Dois cliques recusados não abrem duas threads no mesmo vdf.

    MORDIDA: tire o `if self.armada(): return False` do `armar` e este teste
    reprova — duas passadas concorrentes seriam a única forma de esta cura
    estragar a biblioteca dela, que é o mesmo cuidado do
    `carona_do_wrapper._carona_em_curso`.
    """
    monkeypatch.setattr(a07.VIGIA_DA_STEAM, "intervalo", lambda: 3600.0)
    assert a07.VIGIA_DA_STEAM.armar() is True
    primeira = a07.VIGIA_DA_STEAM._thread
    assert a07.VIGIA_DA_STEAM.armar() is False
    assert a07.VIGIA_DA_STEAM._thread is primeira


# ---------------------------------------------------------------------------
# O RELÓGIO — perguntado, nunca digitado
# ---------------------------------------------------------------------------
def test_o_relogio_e_perguntado_ao_dono(
    a07: Any, cdw: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mudar `INTERVALO_DA_VIGIA_S` no dono muda a vigia.

    É a régua que PERGUNTA: um `45` digitado aqui envelheceria calado no dia em
    que o dono mudasse o compromisso.

    A METADE DA NOTÍCIA SAIU EM 13/09/2026 (TELA-CALADA-02): o mesmo relógio
    decidia quanto tempo a frase da vigia ficava no cartão, e a frase deixou de
    ir ao cartão. Sobra um uso do relógio, e é ele que se mede.

    MORDIDA: troque `self.intervalo()` por um número literal e este teste
    reprova.
    """
    assert a07.VIGIA_DA_STEAM.intervalo() == float(cdw.INTERVALO_DA_VIGIA_S)

    monkeypatch.setattr(cdw, "INTERVALO_DA_VIGIA_S", 7)
    assert a07.VIGIA_DA_STEAM.intervalo() == 7.0


# ---------------------------------------------------------------------------
# A NOTÍCIA FORA DA TELA — o cartão da Steam diz o estado, não o que a vigia fez
# ---------------------------------------------------------------------------
def test_a_noticia_da_vigia_nao_vai_mais_para_o_cartao_da_steam(
    a07: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """A frase do dono vai ao `[relato]` do stderr; o cartão fica como estava.

    **O CONTRATO SE INVERTEU EM 13/09/2026 — TELA-CALADA-02.** Este teste se
    chamava `test_a_noticia_da_vigia_vai_para_o_cartao_da_steam` e exigia a
    frase no corpo do cartão. A palavra dela sobre as frases de status é *"em
    todas as abas da interface"*; quem mostra que o Hefesto cumpriu é o cartão
    relido (o `VIGIA.esquecer()` do tique), e a frase fica no diário da janela.
    A régua completa dos quatro canais é `test_o_cartao_da_steam_nao_narra.py`.

    MORDIDA: some a frase anotada à `cabeca` de `com_o_que_o_daemon_diz` e
    este teste reprova.
    """
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d

    antes = d.cartoes(None)
    assert a07.com_o_que_o_daemon_diz(list(antes), None, None) == antes

    a07.VIGIA_DA_STEAM._anotar("Reposta a Opção de Inicialização do Hefesto em "
                               "1 jogo da Steam: PRAGMATA.")
    depois = a07.com_o_que_o_daemon_diz(list(antes), None, None)
    assert "PRAGMATA" not in depois[0].diz
    assert depois == antes
    assert "PRAGMATA" in capsys.readouterr().err


def test_a_noticia_nao_acende_o_botao_de_dispensar(a07: Any) -> None:
    """A notícia é texto; o "Não perguntar" pende do AVISO e do appid dele.

    MORDIDA: some a notícia dentro do `aviso` (uma variável só) e este teste
    reprova — a notícia da vigia acenderia um botão que não tem sobre o que
    agir.
    """
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d

    antes = d.cartoes(None)
    a07.VIGIA_DA_STEAM._anotar("reposta em 1 jogo")
    depois = a07.com_o_que_o_daemon_diz(list(antes), None, None)
    assert all(a.rotulo != a07.DISPENSAR for a in depois[0].acoes)


def _ctx() -> Any:
    """Um `Contexto` mínimo — estes gestos não falam com o daemon."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={})
