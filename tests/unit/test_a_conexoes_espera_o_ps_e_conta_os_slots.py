#!/usr/bin/env python3
"""A RÉGUA DA ESPERA PELO PS e da CONTA DE SLOTS — as duas linhas da 08.

**A PRIMEIRA É UMA PROMESSA QUE O DESENHO FAZIA E O PRODUTO NÃO CUMPRIA.** O
`title` do botão diz, desde que nasceu: *"Enquanto ele espera o PS, o mesmo
botão vira 'Cancelar'"*. Até 06/09/2026 o gesto derrubava o controle e voltava —
sem contagem, sem Cancelar e sem recado. Ela clicava, o controle caía, e a tela
não dizia uma palavra sobre o que fazer nem por quanto tempo esperar.

**A SEGUNDA RESPONDE OUTRA PERGUNTA QUE A RÉGUA DE CIMA NÃO RESPONDE.** A barra
do Desempenho mostra o que ESTÁ em cada adaptador; a conta de slots responde o
que CABE — e isso não se lê de uma fatia: olhar 260,4 em 1.600 não diz se o
PRÓXIMO controle entra.

O QUE ESTA RÉGUA COBRA, e nenhuma delas passa por acaso
--------------------------------------------------------

1. **O relógio é de SEGUNDOS, não de tiques.** O tique do piloto é de 100 ms
   (`hefesto_vivo.TIQUE_MS`), e a espera do dono conta 60 SEGUNDOS. Um `tique()`
   por pintura faria os 60 s virarem 6 — a contagem correria dez vezes mais
   rápido que o relógio dela, e a tela diria "não voltou" com 54 segundos
   sobrando. É a armadilha inteira desta cura, e o caso 2 a mede.
2. **O mesmo botão cancela**, e o Cancelar **não fala com o BlueZ**: não existe
   reconexão neste produto, o botão PS é dela.
3. **A contagem só começa se o controle CAIU.** A condição é a do dono
   (`_BlocoDaLuz._chegou_o_gesto`): `caiu` falso significa "não achei" ou "não
   consegui falar com o `bluetoothd`", e nos dois mandar apertar PS é gastar o
   gesto dela por uma coisa que não aconteceu.
4. **O fim da espera não fala na tela** — MUDOU DE CONTRATO EM 13/09/2026
   (TELA-CALADA-03). Até ali o recado do fim sobrevivia à espera, pela razão do
   ELO-MUDO-01 (*sem ele "não voltou" viraria silêncio*), e morria quando o
   controle voltava. A palavra dela vence essa razão: *"essas frases de status
   (…) não deveria estar aparecendo"*, *"em todas as abas da interface"*. A
   instrução do segundo tempo (o PS com a contagem) fica; a frase do fim vai ao
   diário da janela, uma vez só.
5. **Nenhuma frase nasce na interface.** As sete que a tela mostra são
   comparadas contra o DONO em `app/`, e não redigitadas aqui.
6. **Os três endereços existem na página que o produto renderiza.** Campo sem
   endereço é pintura que cai no vazio, e ela dá verde em toda régua que só
   pergunte se o motor existe.

A MORDIDA
---------
Troque, em `a08_conexoes._EsperaNaTela.correr`, o avanço por tempo
(`int(agora - self.desde)`) por um `tique()` fixo: o caso
`test_o_relogio_conta_segundos_e_nao_tiques` reprova dizendo que 10 pinturas em
um segundo comeram 10 segundos da espera dela. E comente a chamada a
`comecar_a_espera` no fim do gesto: `test_o_clique_entra_na_espera` reprova
dizendo que o botão não virou Cancelar.
"""
from __future__ import annotations

import html
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a08(pac):
    """O pacote da aba, com o depósito de esperas VAZIO nos dois sentidos.

    Ele é estado de módulo (o `Contexto` é remontado a cada tique e não tem onde
    guardar nada), então uma régua que não o limpasse mediria o caso anterior.
    """
    from pacotes import a08_conexoes

    a08_conexoes._ESPERAS.clear()
    yield a08_conexoes
    a08_conexoes._ESPERAS.clear()


@pytest.fixture
def dono():
    from hefesto_dualsense4unix.app.actions.config import secao_controles

    return secao_controles


@pytest.fixture
def gesto(pac):
    fn = pac.gesto_da_pagina("08-conexoes.html", "luz-nao-acende")
    assert fn is not None, "08-conexoes.html:luz-nao-acende perdeu o dono"
    return fn


def _ctx(pac, transporte: str = "bt"):
    dele = {"uniq": UNIQ, "transport": transporte, "connected": True}
    return pac.Contexto(state={"controllers": [dele]}, mesa=[], conectados=[dele],
                        estados={})


def _caiu(monkeypatch, estado: str = "ESTADO_DESCONECTOU") -> list[str]:
    """Faz o `Disconnect` responder "caiu" e devolve a lista do que foi pedido."""
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    pediu: list[str] = []

    def falso(mac: str, **_: Any) -> Any:
        pediu.append(mac)
        codigo = getattr(radio, estado)
        return radio.Resultado(codigo, getattr(radio, estado.replace("ESTADO_", "FRASE_")),
                               "…")

    monkeypatch.setattr(radio, "desconectar", falso)
    return pediu


# ---------------------------------------------------------------------------
# 1 · O clique entra na espera, e o mesmo botão vira Cancelar
# ---------------------------------------------------------------------------


def test_o_clique_entra_na_espera(pac, a08, dono, gesto, monkeypatch) -> None:
    pediu = _caiu(monkeypatch)
    assert a08.texto_do_botao_da_luz(UNIQ) == dono.TEXTO_DO_BOTAO

    gesto(_ctx(pac), {"uniq": UNIQ}, None)

    assert pediu == [UNIQ], "o gesto não chegou a pedir o Disconnect"
    assert a08.esperando(UNIQ), (
        "o controle caiu e a tela NÃO entrou na espera — é a promessa do `title` "
        "do botão, e ela continua sem cumprimento")
    assert a08.texto_do_botao_da_luz(UNIQ) == dono.TEXTO_CANCELAR, (
        "o botão não virou Cancelar; o desenho promete que o MESMO botão vira")


def test_a_contagem_e_a_do_dono(pac, a08, dono, gesto, monkeypatch) -> None:
    """A linha junta as DUAS falas do dono, e nem uma palavra nova."""
    _caiu(monkeypatch)
    gesto(_ctx(pac), {"uniq": UNIQ}, None)
    linha = a08.linha_da_espera(UNIQ)
    assert dono.FRASE_APERTE_PS in linha, (
        f"o pedido do PS não é o do dono: {linha!r}")
    assert dono.frase_da_procura(dono.ESPERA_PELO_PS_S) in linha, (
        f"a contagem não é a `frase_da_procura` do dono: {linha!r}")


def test_o_que_nao_caiu_nao_entra_na_espera(pac, a08, gesto, monkeypatch) -> None:
    """`nao_deu` levanta com a frase do dono — e NÃO liga o relógio.

    Mandar apertar PS depois de um `Disconnect` que não surtiu efeito é gastar o
    gesto dela por uma coisa que não aconteceu.
    """
    _caiu(monkeypatch, "ESTADO_NAO_DEU")
    with pytest.raises(RuntimeError):
        gesto(_ctx(pac), {"uniq": UNIQ}, None)
    assert not a08.esperando(UNIQ), (
        "a tela entrou na espera sem o controle ter caído")


# ---------------------------------------------------------------------------
# 2 · O relógio — a armadilha desta cura
# ---------------------------------------------------------------------------


def test_o_relogio_conta_segundos_e_nao_tiques(a08, dono) -> None:
    """DEZ pinturas em UM segundo gastam UM segundo, nunca dez.

    O tique do piloto é de 100 ms; a espera do dono é de 60 SEGUNDOS. Um
    `tique()` por pintura faria a tela dizer "não voltou" com 54 segundos
    sobrando na mão dela.
    """
    a08.comecar_a_espera(UNIQ, agora=0.0, sonda=lambda: set())
    for i in range(1, 11):
        a08._correr_as_esperas(agora=i / 10.0)
    dele = a08._ESPERAS[CHAVE]
    assert dele.espera.restantes == dono.ESPERA_PELO_PS_S - 1, (
        f"dez pinturas num segundo comeram "
        f"{dono.ESPERA_PELO_PS_S - dele.espera.restantes} segundos da espera dela")


def test_a_espera_termina_no_tempo_do_dono(a08, dono) -> None:
    a08.comecar_a_espera(UNIQ, agora=0.0, sonda=lambda: set())
    a08._correr_as_esperas(agora=float(dono.ESPERA_PELO_PS_S) - 1)
    assert a08.esperando(UNIQ), "a espera acabou ANTES dos segundos do dono"
    a08._correr_as_esperas(agora=float(dono.ESPERA_PELO_PS_S))
    assert not a08.esperando(UNIQ), "a espera passou dos segundos do dono"


# ---------------------------------------------------------------------------
# 3 · O Cancelar, e ele não fala com o BlueZ
# ---------------------------------------------------------------------------


def test_o_segundo_clique_cancela_sem_falar_com_o_radio(
    pac, a08, dono, gesto, monkeypatch,
) -> None:
    pediu = _caiu(monkeypatch)
    gesto(_ctx(pac), {"uniq": UNIQ}, None)
    assert a08.esperando(UNIQ)

    # O CONTROLE JÁ CAIU, então ele não está mais no `conectados` — e é assim
    # que o clique do Cancelar chega de verdade. Um ramo que dependesse do
    # transporte recusaria o próprio Cancelar com a frase do cabo.
    gesto(pac.Contexto(state={"controllers": []}, conectados=[]), {"uniq": UNIQ}, None)

    assert not a08.esperando(UNIQ), "o Cancelar não saiu da espera"
    assert pediu == [UNIQ], (
        f"o Cancelar falou com o BlueZ ({len(pediu)} pedidos) — não existe "
        f"reconexão neste produto, o botão PS é dela")
    assert a08.texto_do_botao_da_luz(UNIQ) == dono.TEXTO_DO_BOTAO
    assert a08.linha_da_espera(UNIQ) == a08._sem_valor(), (
        "o Cancelar deixou recado; desistir não é notícia")


# ---------------------------------------------------------------------------
# 4 · O fim da espera — ele não fala na tela, e vai ao diário
#
# MUDOU DE CONTRATO EM 13/09/2026 (TELA-CALADA-03). Os três casos que moravam
# aqui cobravam o recado do fim NA LINHA DO CARTÃO: `nao_voltou` sobrevivendo à
# espera, morrendo quando o controle voltava, e `nao_caiu` com a frase do dono.
# A palavra dela tirou a frase da tela — ver o item 4 do cabeçalho. O que se
# cobra agora é a outra metade de cada um: a frase continua sendo a do DONO, e
# ela chega ao diário da janela UMA vez.
# ---------------------------------------------------------------------------


def test_o_fim_de_nao_voltou_nao_fala_na_tela_e_vai_ao_diario(
        a08, dono, capsys) -> None:
    a08.comecar_a_espera(UNIQ, agora=0.0, sonda=lambda: set())
    a08._correr_as_esperas(agora=float(dono.ESPERA_PELO_PS_S))
    assert not a08.esperando(UNIQ)
    assert a08.linha_da_espera(UNIQ) == a08._sem_valor(), (
        "a espera acabou e a linha do cartão continuou falando")
    diario = capsys.readouterr().err
    assert dono.frase_nao_voltou(dono.ESPERA_PELO_PS_S) in diario, (
        "a frase do fim não chegou ao diário — ou não é a do dono, que tem DUAS "
        f"orações de propósito: {diario!r}")


def test_o_fim_vai_ao_diario_uma_vez_so(a08, dono, capsys) -> None:
    """Dez tiques depois do fim, UMA linha — o diário não vira dez por segundo."""
    a08.comecar_a_espera(UNIQ, agora=0.0, sonda=lambda: set())
    for i in range(10):
        a08._correr_as_esperas(agora=float(dono.ESPERA_PELO_PS_S) + i)
    frase = dono.frase_nao_voltou(dono.ESPERA_PELO_PS_S)
    assert capsys.readouterr().err.count(frase) == 1


def test_o_que_nao_caiu_do_radio_vai_ao_diario_com_a_frase_do_dono(
        a08, dono, capsys) -> None:
    """Nunca viu sumir → `nao_caiu`: a frase é a do dono, e fica fora do cartão."""
    a08.comecar_a_espera(UNIQ, agora=0.0, sonda=lambda: {CHAVE})
    a08._correr_as_esperas(agora=float(dono.ESPERA_PELO_PS_S))
    assert a08.linha_da_espera(UNIQ) == a08._sem_valor()
    assert dono.FRASE_NAO_CAIU in capsys.readouterr().err


def test_o_controle_que_volta_sai_da_espera_sem_recado(a08, dono) -> None:
    presentes = [{CHAVE}]
    a08.comecar_a_espera(UNIQ, agora=0.0, sonda=lambda: presentes[0])
    a08._correr_as_esperas(agora=1.0)
    presentes[0] = set()            # caiu
    a08._correr_as_esperas(agora=2.0)
    presentes[0] = {CHAVE}          # ela apertou PS
    a08._correr_as_esperas(agora=3.0)
    assert not a08.esperando(UNIQ), "o controle voltou e a espera continuou contando"
    assert a08.linha_da_espera(UNIQ) == a08._sem_valor(), (
        "voltar não é notícia ruim; a linha não tem o que dizer")


def test_em_repouso_a_linha_nao_ocupa_nada(a08) -> None:
    """`monta.NADA_A_DIZER`, nunca `""`.

    O `escrever()` do piloto troca vazio por travessão ANTES de olhar o alvo, e
    uma ressalva vazia viraria uma linha com um `—` — altura gasta para não
    dizer nada.
    """
    assert a08.linha_da_espera(UNIQ) == a08._sem_valor()
    assert a08.linha_da_espera(UNIQ) != ""


# ---------------------------------------------------------------------------
# 5 · A pintura leva os dois campos para o cartão
# ---------------------------------------------------------------------------


def test_a_pintura_emite_os_dois_campos_no_cartao(pac, a08, dono, monkeypatch) -> None:
    """Os campos saem POR CONTROLE — a mesa tem quatro colunas iguais."""
    dele = {"uniq": UNIQ, "transport": "bt", "connected": True, "index": 0}
    eu = {"pref": "p1", "uniq": UNIQ, "jogador": 1, "cor": "white",
          "nome": "White", "via": "rádio", "transporte": "bt",
          "mascara": "DualSense"}
    ctx = pac.Contexto(state={"controllers": [dele]}, mesa=[eu],
                       conectados=[dele], estados={})
    fora = a08.pacote(ctx)
    coluna = (fora.get("colunas") or {}).get(UNIQ) or {}
    assert coluna.get("luz-texto") == dono.TEXTO_DO_BOTAO, (
        f"o cartão não recebeu o rótulo do botão: {coluna.get('luz-texto')!r}")
    assert "luz-espera" in coluna, "o cartão não recebeu a linha da espera"


# ---------------------------------------------------------------------------
# 6 · A conta de slots — os três estados, com as frases do dono
# ---------------------------------------------------------------------------


@pytest.fixture
def orcamento():
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento

    return secao_orcamento


def test_sem_resposta_do_servico_a_conta_diz_que_nao_sabe(
    pac, a08, orcamento,
) -> None:
    """**Nunca "Folgada"** — a cicatriz da B1, medida pelo dono em 23/08/2026.

    Com o Hefesto parado as três barras diziam "Folgada", em verde, "0/1600" —
    byte a byte a tela de um rádio vazio. Não saber e estar vazio são coisas
    diferentes, e a diferença é a informação inteira.
    """
    assert a08._conta_de_slots(pac.Contexto(state={})) == orcamento.SEM_RESPOSTA_DO_DAEMON


def test_com_o_radio_vazio_a_conta_diz_que_esta_vazio(pac, a08, orcamento) -> None:
    dele = {"uniq": UNIQ, "transport": "usb", "connected": True}
    conta = a08._conta_de_slots(pac.Contexto(state={"controllers": [dele]}))
    assert conta == orcamento.NINGUEM_NO_RADIO
    assert conta != orcamento.SEM_RESPOSTA_DO_DAEMON, (
        "rádio vazio e serviço mudo não podem dizer a mesma coisa")


def test_com_gente_no_radio_a_conta_responde_por_adaptador(
    pac, a08, monkeypatch,
) -> None:
    """A frase é a do dono (`plano_de_radio.linha_do_cabe_mais_um`), inteira."""
    from hefesto_dualsense4unix.integrations import plano_de_radio

    dele = {"uniq": UNIQ, "transport": "bt", "connected": True, "player_slot": 1}
    plano = plano_de_radio.PlanoDoAdaptador(
        endereco="aabbcc000009", apelido="Sala", jogadores=(1,),
        agora=plano_de_radio.Ocupacao(controles=1, com_microfone=0,
                                      slots_input=260.4, slots_teto=1600))
    monkeypatch.setattr(plano_de_radio, "plano_por_adaptador",
                        lambda *a, **k: {"aabbcc000009": plano})
    conta = a08._conta_de_slots(pac.Contexto(state={"controllers": [dele]}))
    # O `html.escape` é da TELA, não da frase: o alvo é `html`, e as aspas do
    # nome do adaptador têm de sair escapadas ou o nome dela quebra a marcação.
    assert conta == html.escape(plano_de_radio.linha_do_cabe_mais_um(plano)), (
        f"a conta não é a frase do dono: {conta!r}")
    assert "Sala" in conta, "o nome que ELA deu ao adaptador não chegou à frase"


def test_o_declarado_que_nao_subiu_vem_antes_do_cabe_mais_um(
    pac, a08, monkeypatch,
) -> None:
    """O que está errado AGORA vem antes do que se pode planejar — ordem do dono.

    E ele existe porque ausência de notícia lida como notícia de sucesso é o
    padrão que a queixa do Sackboy revelou: sem esta linha a tela mostraria
    "está tudo certo" sobre uma ponte no chão.
    """
    from hefesto_dualsense4unix.integrations import plano_de_radio

    dele = {"uniq": UNIQ, "transport": "bt", "connected": True}
    plano = plano_de_radio.PlanoDoAdaptador(
        endereco="aabbcc000009", apelido="Sala", jogadores=(1,),
        com_mic_declarado=frozenset({CHAVE}),
        agora=plano_de_radio.Ocupacao(controles=1, com_microfone=0,
                                      slots_input=260.4, slots_teto=1600))
    monkeypatch.setattr(plano_de_radio, "plano_por_adaptador",
                        lambda *a, **k: {"aabbcc000009": plano})
    conta = a08._conta_de_slots(pac.Contexto(state={"controllers": [dele]}))
    pendente = html.escape(plano_de_radio.linha_do_declarado_que_nao_subiu(plano) or "")
    cabe = html.escape(plano_de_radio.linha_do_cabe_mais_um(plano))
    assert pendente and pendente in conta and cabe in conta
    assert conta.index(pendente) < conta.index(cabe), (
        "o que está errado agora tem de vir antes do que se pode planejar")


def test_o_hcin_nunca_chega_a_conta(pac, a08, monkeypatch) -> None:
    """Decisão M1: o índice é a VAGA, não o aparelho, e inverte entre boots."""
    from hefesto_dualsense4unix.integrations import plano_de_radio

    dele = {"uniq": UNIQ, "transport": "bt", "connected": True}
    plano = plano_de_radio.PlanoDoAdaptador(
        endereco="aabbcc000009", jogadores=(1,),
        agora=plano_de_radio.Ocupacao(controles=1, slots_input=260.4,
                                      slots_teto=1600))
    monkeypatch.setattr(plano_de_radio, "plano_por_adaptador",
                        lambda *a, **k: {"aabbcc000009": plano})
    conta = a08._conta_de_slots(pac.Contexto(state={"controllers": [dele]}))
    assert "hci" not in conta.lower(), f"o `hciN` chegou à tela: {conta!r}"
    assert "aabbcc" not in conta.lower(), (
        "o endereço de rádio chegou à tela — ele é chave de casamento e mais nada")


# ---------------------------------------------------------------------------
# 7 · Os endereços existem na página
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("endereco", ["luz-texto", "luz-espera", "conta-de-slots"])
def test_a_pagina_tem_o_endereco(endereco: str) -> None:
    """Campo sem endereço é pintura que cai no vazio — e dá verde calado.

    A régua lê a BANCADA (`mockup/`), que é o desenho de HOJE: apontá-la para o
    publicado a faria dar verde sobre a página congelada.
    """
    from hefesto_dualsense4unix.interface import onde

    pagina = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert f'data-campo="{endereco}"' in pagina, (
        f"a página não tem `data-campo=\"{endereco}\"` — o pacote escreveria "
        f"para ninguém")


# ---------------------------------------------------------------------------
# 8 · DO PACOTE AO PIXEL — a bancada num WebKit, com o BOOTSTRAP do piloto
# ---------------------------------------------------------------------------
#
# POR QUE ESTA PARTE EXISTE, e ela não é a segunda cópia de nada: os casos acima
# provam o PACOTE (o que ele emite) e a página (que ela tem os endereços). O elo
# do meio — o `escrever()` do piloto achando os dois campos DENTRO do cartão
# certo e a `.ressalva` deixando de estar escondida — não tem régua nenhuma nos
# dois lados, e é justamente onde uma pintura cai no vazio calada.
#
# AQUI NADA É IMITADO: a página é a BANCADA de verdade, o roteiro é o
# `hefesto_vivo.BOOTSTRAP` de verdade (lido do módulo, nunca copiado), e a carga
# sai de `a08_conexoes.pacote` + `pacotes.normalizar`, que é a MESMA sequência
# do piloto. O molde é o do `test_a_aba01_veste_o_controle_de_ponta_a_ponta.py`.

ROTEIRO_DA_ESPERA = """
(function(){
  const raiz = document.querySelector('[data-controle="p1"]');
  if(!raiz) return JSON.stringify({erro: 'não achei o cartão do p1'});
  const linha = raiz.querySelector('[data-campo="luz-espera"]');
  const rotulo = raiz.querySelector('[data-campo="luz-texto"]');
  if(!linha || !rotulo) return JSON.stringify({erro: 'a página não tem os endereços'});
  const fora = {};
  for(const [nome, carga] of CARGAS){
    fora[nome] = {
      pintou: window.__hef.pintar(carga),
      rotulo: rotulo.textContent.trim(),
      linha: linha.textContent.trim(),
      mostra: getComputedStyle(linha).display,
      classe: raiz.querySelector('button[data-gesto="luz-nao-acende"]').className,
      opacidade: getComputedStyle(
        raiz.querySelector('button[data-gesto="luz-nao-acende"]')).opacity,
    };
  }
  return JSON.stringify(fora);
})()
"""


def _carga_da_luz(a08, pac, esperando_agora: bool, transporte: str = "bt") -> dict:
    """A carga do tique, com e sem a espera de pé — pelo caminho do piloto."""
    cru = {"uniq": UNIQ, "connected": True, "player_slot": 1,
           "transport": transporte, "battery_pct": 95, "index": 0}
    eu = {"uniq": UNIQ, "pref": "p1", "jogador": 1, "nome": "White",
          "cor": "white", "via": "rádio" if transporte == "bt" else "cabo",
          "transporte": transporte, "mascara": "DualSense"}
    a08._ESPERAS.clear()
    if esperando_agora:
        # O RELÓGIO É O DE VERDADE, e tem de ser: `pacote()` chama
        # `_correr_as_esperas` com `time.monotonic()`, e uma base de zero faria a
        # espera VENCER no mesmo tique — foi o que esta régua mediu na primeira
        # volta, e o sintoma era mudo (a pintura escreveu ZERO campos, porque a
        # carga tinha voltado a ser a de repouso).
        agora = a08._agora()
        a08.comecar_a_espera(UNIQ, agora=agora, sonda=lambda: set())
        a08._correr_as_esperas(agora=agora + 1)
    ctx = pac.Contexto(state={"controllers": [cru]}, mesa=[eu], conectados=[cru],
                       estados={})
    return dict(pac.normalizar(a08.pacote(ctx), {UNIQ: "p1"}))


@pytest.fixture(scope="module")
def no_webkit():
    """Uma abertura de WebKit offscreen para os dois estados da linha."""
    import json

    import pacotes as _pac
    from pacotes import a08_conexoes as _a08

    from hefesto_dualsense4unix.interface import onde

    import hefesto_vivo

    pagina = onde.pagina("08-conexoes.html")
    if not pagina.is_file():
        pytest.skip("a bancada da 08 não está no disco — rode o gerador")

    cargas = [("repouso", _carga_da_luz(_a08, _pac, False)),
              ("espera", _carga_da_luz(_a08, _pac, True)),
              ("cabo", _carga_da_luz(_a08, _pac, False, transporte="usb"))]
    _a08._ESPERAS.clear()

    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    saiu: list[str] = []
    # `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    # janelas e uma janela comum fica 1x1 para sempre. E offscreen também porque
    # ela tem UMA tela — janela de teste não nasce na frente dela.
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()
    roteiro = (f"const CARGAS = {json.dumps(cargas, ensure_ascii=False)};\n"
               f"{ROTEIRO_DA_ESPERA}")

    def guardou(v, res) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def bootou(v, res) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO no BOOTSTRAP: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v, evento) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None,
                                  bootou)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    # O `timeout_add` PENDENTE DISPARA NO LAÇO DO PRÓXIMO TESTE de GUI do mesmo
    # processo — a cicatriz de 05/09, e ela já matou onze medições nesta casa.
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def test_no_motor_o_botao_vira_cancelar(no_webkit, dono) -> None:
    assert no_webkit["repouso"]["rotulo"] == dono.TEXTO_DO_BOTAO
    assert no_webkit["espera"]["rotulo"] == dono.TEXTO_CANCELAR, (
        "no motor de verdade o botão NÃO virou Cancelar — é a promessa que o "
        "`title` do desenho faz desde que nasceu")


def test_no_motor_a_linha_da_espera_nasce_e_some(no_webkit, dono) -> None:
    """Em repouso ela não ocupa NADA; na espera ela aparece com a contagem."""
    assert no_webkit["repouso"]["mostra"] == "none", (
        f"a linha ocupa altura em repouso ({no_webkit['repouso']['mostra']}) — "
        f"decisão dela: *linha fixa só quando HÁ ressalva*")
    assert no_webkit["espera"]["mostra"] != "none", (
        "a linha da espera continuou escondida COM a espera de pé")
    texto = no_webkit["espera"]["linha"]
    assert dono.FRASE_APERTE_PS in texto, f"o pedido do PS não chegou: {texto!r}"
    assert dono.frase_da_procura(dono.ESPERA_PELO_PS_S - 1) in texto, (
        f"a contagem não chegou ao pixel: {texto!r}")


def test_no_motor_o_botao_segue_o_transporte(no_webkit) -> None:
    """O botão da linha do P1 deixou de nascer apagado PARA SEMPRE — 06/09/2026.

    **MEDIDO NO DOM, e é o que trouxe esta linha para a régua:** com um controle
    no RÁDIO no lugar do P1, o `luz-trava` chegava certo (o `<i>` ficava
    `ltrava`, sem o `on`) e o botão continuava com `class="btn apagado"`,
    opacidade 0,55 e cursor `help` — a classe do MOCKUP, que o pintor não tem
    como apagar porque o `data-campo` do botão está gasto no `title`. Quem
    herdasse o lugar do P1 pelo rádio veria um botão com cara de desligado, e o
    "Cancelar" desta sprint nasceria cinza.

    A APARÊNCIA PASSOU A TER UM DONO SÓ: o `<i class="ltrava">`, que é dado.
    """
    assert "apagado" not in no_webkit["espera"]["classe"], (
        f"o Cancelar nasceu com cara de desligado: "
        f"{no_webkit['espera']['classe']!r}")
    assert float(no_webkit["repouso"]["opacidade"]) == 1.0, (
        f"no rádio o botão continua esmaecido (opacidade "
        f"{no_webkit['repouso']['opacidade']}) — a cura de 03/09 parou no `<i>`")
    assert float(no_webkit["cabo"]["opacidade"]) < 1.0, (
        "no CABO o botão tem de continuar apagado — regra dela: *sempre visível "
        "mas só acionável quando tiver no rádio*")
