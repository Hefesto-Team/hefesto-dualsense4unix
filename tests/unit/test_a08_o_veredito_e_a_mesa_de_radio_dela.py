#!/usr/bin/env python3
"""O CHECK-UP RESPONDE EM UMA LINHA, e a mesa de rádio é a DELA.

**04/09/2026.** Duas frentes desta leva, e as duas fecham o mesmo tipo de
buraco — a tela mostrando cenário onde o produto já sabia responder.

**S-09 — a linha de veredito (decisão D-16 dela):** *"Uma linha de veredito no
topo."*, *"Na cor do pior achado."* O Check-up tinha cinco pílulas e nenhum
juízo: para saber se estava tudo certo era preciso ler as cinco e achar a pior,
e a segunda ordem de serviço desta bancada — que não cabe nas cinco — não
entrava nessa leitura de jeito nenhum. O pacote já emitia `achados` e `graves`
(as duas contagens de que a frase precisa) e a página não tinha onde recebê-las.

**A MESA DE RÁDIO — três coisas que a tela cravava do mockup:**

    a tabela de adaptadores     "Sala / TP-Link UB500 / Entrada 3" e "Sem nome /
                                Intel AX211 / Interno", sobre uma máquina com
                                TRÊS adaptadores `2357:0604`
    a régua de Desempenho       uma pista, sem nome, quando `ler_a_mesa()`
                                enumera os três e o BlueZ dá o nome de cada um
    a coluna "Onde" dos rádios  não existia — a linha do Check-up diz "dois
    vizinhos                    rádios em entradas vizinhas" e não diz QUAL

**A REGRA QUE ESTA LEVA CONFIRMOU:** as duas frases que o próprio código
escrevia como impossíveis — *"UMA PISTA POR ADAPTADOR espera uma fonte"* e *"o
apelido mora na declaração dela … as duas não casam hoje"* — descreviam o
caminho errado, não uma falta. `mesa_de_radio.ler_a_mesa().adaptadores` enumera,
e o `Dongle` do BlueZ carrega o endereço, o `hciN` e o nome no MESMO objeto.

AS MORDIDAS — ONZE, arrancadas de verdade em 04/09/2026, uma a uma, com o
desenho devolvido byte a byte idêntico no fim. Cada uma derrubou **um** teste, e
só ele:

===  ============================================  ==========================
 #   o que se arranca                              quem reprova
===  ============================================  ==========================
 1   `frase = topo.texto` incondicional em         `..._nao_diz_nada_a_mudar_
     `_veredito_do_exame`                          com_uma_linha_grave`
 2   `ordens=todas` no lugar de `ordens=novas`     `..._o_que_ela_calou_nao_
                                                   segura_a_cor`
 3   um `<i class="vst">` fora de                  `..._tem_um_interruptor_
     `aba08.veredito_do_checkup`, e regerar        por_estado_do_veredito`
 4   `pistas` voltando a nascer só dos GRUPOS      `..._uma_pista_por_
     de controle                                   adaptador` (e a irmã)
 5   `<table class="tab">` sem `data-campo`        `..._a_tabela_dos_
                                                   adaptadores_tem_endereco`
 6   o `<i class="vaviso">` DEPOIS do `.onde`      `..._a_coluna_onde_dos_
                                                   vizinhos_tem_endereco`
 7   `dica_do_botao(dados)` sem `mesa_suja`        `..._anexa_o_aviso_da_
                                                   mesa_suja`
 8   `razao = None` em `dica_da_luz`               `..._a_razao_do_nascimento_
                                                   so_fala_na_condenacao`
 9   `"Custa +16,3 turnos"` digitado no lugar      `..._o_custo_do_mic_no_
     da frase derivada                             radio_nao_e_digitado`
10   o `<select data-gesto="mic-escopo">` de       `..._e_leitura_e_nao_
     volta no lugar da leitura                     escolha`
11   o `data-campo="mic-dica"` fora do `title`     `..._do_resumo_do_mic_
     do resumo                                     tem_endereco`
===  ============================================  ==========================
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"


def _pacote():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _item(estado: str, chave: str = "", ordem: object = None):  # type: ignore[no-untyped-def]
    """Um `Item` do exame — o do PRODUTO, nunca um dublê de forma parecida."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item

    return Item(chave=chave or f"c-{estado}", rotulo="", estado=estado,
                porque="", ordem=ordem)


def _ordem(chave: str, arranjo: str):  # type: ignore[no-untyped-def]
    """Uma `Ordem` do catálogo, com o mínimo que a dispensa endereça.

    A CLASSE É A DO PRODUTO, e não um dublê de forma parecida: `ordens_novas` e
    `ordens_caladas` leem `chave` e `arranjo`, e um objeto anônimo passaria neste
    teste e mentiria no dia em que a dispensa mudar de chave.
    """
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Linha, Ordem

    vazia = Linha(texto="", selo="medido_aqui")
    return Ordem(
        chave=chave,
        acao="Mova o adaptador",
        o_que_eu_vi=vazia,
        por_que_importa=vazia,
        ganho_esperado=vazia,
        arranjo=arranjo,
    )


# ---------------------------------------------------------------------------
# S-09 — A LINHA DE VEREDITO
# ---------------------------------------------------------------------------
def test_a_frase_do_veredito_e_a_do_dono() -> None:
    """A frase NÃO nasce no pacote: ela é de `ordens_da_mesa.cabecalho()`.

    Quatro frases, quatro cenas — e as quatro conferidas contra o dono, que é
    quem as escreve. Um literal no pacote seria a segunda grafia, e a primeira
    coisa que uma segunda grafia perde é o dia em que a outra muda.
    """
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("certo"), _item("certo")])
    esperado = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0)
    assert saiu["veredito"] == esperado.texto, (
        f"o veredito disse {saiu['veredito']!r} e o dono escreve "
        f"{esperado.texto!r} — alguém digitou a frase no pacote")


def test_a_cor_e_a_do_pior_achado() -> None:
    """Um `problema` entre cinco `certo` acende o vermelho, e só ele."""
    p = _pacote()
    itens = [_item("certo"), _item("problema"), _item("certo")]
    saiu = p._veredito_do_exame(itens)
    assert saiu["veredito-problema"] == "problema", (
        "a linha de veredito não acendeu no pior achado")
    for estado, endereco in p.ENDERECO_DO_VEREDITO.items():
        if estado == "problema":
            continue
        assert saiu[endereco] == "", (
            f"`{endereco}` acendeu junto com o `problema`. Um instante com dois "
            f"acesos deixa o que está QUEBRADO com a cor do que só podia estar "
            f"melhor, que é a confusão que ela mandou desfazer em 02/09.")


def test_o_veredito_nao_diz_nada_a_mudar_com_uma_linha_grave() -> None:
    """A MORDIDA da cicatriz `6c86e295`, e ela é a razão de a função existir.

    `ordens_da_mesa.cabecalho()` **não conhece `problema`**: sem ordem aberta
    ele responde "Nada a mudar", em verde. `exame_da_mesa.veredito()` sobre as
    linhas conhece — e é `secao_exame.o_mais_grave` quem os concilia. Um selo
    pintado só pelo segundo diria *"Nada a mudar"* em verde com a linha de
    pareamentos em vermelho, que é o defeito que esta casa pagou duas vezes em
    agosto.

    ARRANQUE A CURA: troque o `frase = topo.texto if estado == topo.estado else
    …` por `frase = topo.texto` e este teste reprova.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_exame import FRASE_DO_SELO
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("problema"), _item("certo")])
    verde = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0).texto
    assert saiu["veredito"] != verde, (
        f"com uma linha em `problema` o veredito escreveu {verde!r} — a frase "
        f"do cabeçalho, que não conhece `problema`. É a cicatriz 6c86e295 "
        f"voltando: o verde convivendo com o vermelho na mesma seção.")
    assert saiu["veredito"] == FRASE_DO_SELO["problema"], (
        "quando o estado das linhas vence o do cabeçalho, a frase tem de ser a "
        "do estado — e ela também tem dono (`secao_exame.FRASE_DO_SELO`)")


def test_o_que_ela_calou_nao_segura_a_cor() -> None:
    """A ordem DISPENSADA sai da conta — senão o ⊘ é botão morto.

    É a mesma regra do `_escrever_o_cabecalho` da janela estável: uma ordem
    dispensada prenderia o topo em laranja para sempre e o clique dela não
    faria nada visível.

    ARRANQUE A CURA: faça `_veredito_do_exame` passar `todas` no lugar de
    `novas` e este teste reprova.
    """
    p = _pacote()
    ordem = _ordem("vizinhanca", "arranjo-de-hoje")
    itens = [_item("certo"), _item("atencao", chave="o1", ordem=ordem)]  # noqa-acento

    antes = dict(p._DISPENSADAS)
    try:
        p._DISPENSADAS = {}
        com_ordem = p._veredito_do_exame(itens)
        p._DISPENSADAS = {"vizinhanca": "arranjo-de-hoje"}
        calada = p._veredito_do_exame(itens)
    finally:
        p._DISPENSADAS = antes

    assert com_ordem["veredito-atencao"] == "atencao", (  # noqa-acento: chave e valor de dado
        "com a ordem aberta o topo tinha de estar em `atencao`")  # noqa-acento: nome do estado
    assert calada["veredito-atencao"] == "", (
        "a ordem que ela dispensou continuou segurando o topo em laranja — o ⊘ "
        "grava e a tela não muda, que é a definição de botão morto")


def test_o_veredito_chega_ao_pacote() -> None:
    """A LIGAÇÃO, e não só a peça.

    A lição está escrita no `test_a08_o_selo_do_exame_tem_um_endereco_por_estado`:
    um teste que prova a peça e não a ligação dá verde sobre um fio solto.
    """
    p = _pacote()
    saiu = p.pacote(_ctx())
    assert "veredito" in saiu, (
        "o `pacote()` não emite `veredito` — a linha do desenho fica com a "
        "frase da bancada para sempre")
    for endereco in p.ENDERECO_DO_VEREDITO.values():
        assert endereco in saiu, (
            f"o `pacote()` não emite `{endereco}`: o desenho tem o interruptor "
            f"e ninguém o acende")


def test_o_desenho_tem_um_interruptor_por_estado_do_veredito() -> None:
    """A outra metade: sem o endereço no HTML, o pacote escreve no vazio.

    ARRANQUE A CURA: tire um `<i class="vst">` de `aba08.veredito_do_checkup`,
    regenere, e este teste reprova.
    """
    p = _pacote()
    html = BANCADA.read_text()
    for endereco in p.ENDERECO_DO_VEREDITO.values():
        assert f'data-campo="{endereco}"' in html, (
            f"o desenho não tem `{endereco}` — o pacote emite e a tela não "
            f"recebe")
    assert 'data-campo="veredito"' in html, (
        "a linha de veredito não tem endereço para a frase")
    assert html.count('class="veredito"') == 1, (
        "a linha de veredito tem de ser UMA — ela responde pela seção inteira, "
        "e duas seriam duas respostas para a mesma pergunta")


def test_a_linha_de_veredito_mora_acima_das_duas_colunas() -> None:
    """*"Uma linha de veredito no topo"* — a palavra dela é TOPO.

    Dentro da coluna do exame ela responderia por metade da seção: a ordem de
    serviço vive na outra.
    """
    html = BANCADA.read_text()
    veredito = html.index('class="veredito"')
    colunas = html.index('class="duas-colunas"', html.index('id="cx8-2"'))
    assert veredito < colunas, (
        "a linha de veredito nasceu DENTRO das colunas — ela responde pelas "
        "duas, e pendurada em uma delas responde por metade da seção")


# ---------------------------------------------------------------------------
# A MESA DE RÁDIO — a tabela, a régua e a coluna "Onde"
# ---------------------------------------------------------------------------
class _Adaptador:
    """O mínimo que `_html_dos_adaptadores` e a régua perguntam."""

    def __init__(self, interface: str, no: str = "", devpath: str = "") -> None:
        self.interface = interface
        self.no = no or f"/sys/{interface}"
        self.caminho = devpath or "3-1"
        self.vid = "2357"
        self.pid = "0604"
        self.busnum = 3
        self.devpath = devpath or "1"
        self.painel = ""
        self.atras_de_hub = False
        self.controlador_pci = ""


class _Mesa:
    def __init__(self, adaptadores: object, radios: object = ()) -> None:
        self.adaptadores = adaptadores
        self.radios = radios
        self.apertadas = ()


class _Dongle:
    """O `Dongle` do BlueZ tem as TRÊS pontas: endereço, `hciN` e nome."""

    def __init__(self, endereco: str, interface: str, nome: str) -> None:
        self.endereco = endereco
        self.objeto = f"/org/bluez/{interface}"
        self.nome = nome


def _com_a_bancada(monkeypatch, adaptadores, dongles):  # type: ignore[no-untyped-def]
    """Troca as duas leituras de máquina por uma bancada declarada."""
    p = _pacote()
    monkeypatch.setattr(p, "_MESA_DO_RADIO", _Mesa(adaptadores))
    monkeypatch.setattr(p, "_DONGLES", tuple(dongles))
    return p


def test_a_tabela_dos_adaptadores_tem_uma_linha_por_adaptador(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """TRÊS adaptadores viram TRÊS linhas — e cada uma com o nome DELA.

    A máquina desta casa tem três `2357:0604`, e é por isso que o nome importa:
    a coluna do meio repete nos três, e o que os separa é o apelido do BlueZ.
    """
    p = _com_a_bancada(
        monkeypatch,
        [_Adaptador("hci0"), _Adaptador("hci1"), _Adaptador("hci2")],
        [_Dongle("AA:BB:CC:00:00:01", "hci0", "Sala"),
         _Dongle("AA:BB:CC:00:00:02", "hci1", "Extra"),
         _Dongle("AA:BB:CC:00:00:03", "hci2", "")],
    )
    html = p._html_dos_adaptadores()
    assert html.count("<tr>") == 4, (
        f"a tabela saiu com {html.count('<tr>') - 1} linhas para três "
        f"adaptadores (mais o cabeçalho)")
    assert "Sala" in html and "Extra" in html, (
        "o nome que ela deu ao adaptador não chegou à tabela")
    assert p.SEM_NOME in html, (
        "o adaptador sem apelido tinha de dizer a palavra do produto, e não "
        "ficar em branco")
    assert "TP-Link UB500" not in html and "Intel AX211" not in html, (
        "a tabela ainda traz os modelos da bancada de exemplo do mockup")


def test_a_tabela_nao_confunde_nao_li_com_nao_ha(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Varredura FALHA e mesa VAZIA dizem coisas diferentes.

    Ausência de leitura lida como ausência de aparelho é o defeito que esta
    casa chama de *ausência de notícia lida como sucesso*.
    """
    p = _pacote()
    monkeypatch.setattr(p, "_MESA_DO_RADIO", None)
    monkeypatch.setattr(p, "_dongles", lambda recarregar=False: None)
    # `_mesa_do_radio()` só devolve `None` quando a leitura levanta.
    monkeypatch.setattr(p, "_mesa_do_radio", lambda recarregar=False: None)
    falhou = p._html_dos_adaptadores()

    monkeypatch.setattr(p, "_mesa_do_radio", lambda recarregar=False: _Mesa([]))
    vazia = p._html_dos_adaptadores()

    assert falhou != vazia, (
        "a tabela diz a mesma coisa quando não conseguiu ler e quando leu e "
        "não achou nada — são afirmações opostas")
    assert p._NAO_CONSEGUI_LER_OS_ADAPTADORES in falhou
    assert p._NENHUM_ADAPTADOR in vazia


def test_a_tabela_dos_adaptadores_tem_endereco() -> None:
    """Sem o `data-campo` no `<table>`, o pacote pinta no vazio.

    ARRANQUE A CURA: tire o `data-campo="adaptadores-tabela"` do `aba08.py`,
    regenere, e este teste reprova.
    """
    html = BANCADA.read_text()
    assert re.search(r'<table class="tab" data-campo="adaptadores-tabela" '
                     r'data-hef-alvo="html">', html), (
        "a tabela de adaptadores voltou a ser HTML fixo do mockup — ela é a "
        "peça mais lida desta aba, e era cenário")


def test_a_regua_tem_uma_pista_por_adaptador(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """TRÊS adaptadores e NINGUÉM no rádio ainda são três pistas.

    Era UMA, sem nome: `pistas` nascia dos GRUPOS de controle, e com os dois
    DualSense dela no cabo a seção Desempenho respondia *"cabe mais um controle
    no rádio?"* mostrando uma barra sobre três adaptadores.

    ARRANQUE A CURA: volte o `pistas` a nascer só de `grupos` e este teste
    reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p = _com_a_bancada(
        monkeypatch,
        [_Adaptador("hci0"), _Adaptador("hci1"), _Adaptador("hci2")],
        [_Dongle("AA:BB:CC:00:00:01", "hci0", "Sala"),
         _Dongle("AA:BB:CC:00:00:02", "hci1", "Extra"),
         _Dongle("AA:BB:CC:00:00:03", "hci2", "Terceiro")],
    )
    uniq = "aa:bb:cc:00:00:09"
    mesa = [{"pref": "p1", "uniq": uniq, "jogador": 1, "cor": "white",
             "nome": "White", "via": "USB", "transporte": "usb",
             "mascara": "DualSense"}]
    conectados = [{"uniq": uniq, "transport": "usb", "connected": True,
                   "battery_pct": 100}]
    html = p._regua_do_radio(
        Contexto(state={"controllers": conectados}, mesa=mesa,
                 conectados=conectados, estados={}))

    quantas = html.count('class="pista"')
    assert quantas == 3, (
        f"a régua saiu com {quantas} pistas para três adaptadores — ela é a que "
        f"responde 'cabe mais um controle no rádio?'")
    for nome in ("Sala", "Extra", "Terceiro"):
        assert nome in html, (
            f"a pista do adaptador {nome!r} saiu sem o nome que ela deu — era "
            f"'Sem nome' para os três, que é o problema que os nomes vieram "
            f"resolver")


def test_a_regua_nao_empresta_o_adaptador_do_vizinho(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Adaptador sem gente fica com a pista VAZIA, não com a fatia de outro."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p = _com_a_bancada(
        monkeypatch, [_Adaptador("hci0"), _Adaptador("hci1")],
        [_Dongle("AA:BB:CC:00:00:01", "hci0", "Sala"),
         _Dongle("AA:BB:CC:00:00:02", "hci1", "Extra")])
    mesa: list[dict[str, object]] = []
    html = p._regua_do_radio(
        Contexto(state={"controllers": []}, mesa=mesa, conectados=[], estados={}))
    assert html.count("Nenhum controle neste rádio") == 2, (
        "com dois adaptadores e ninguém no rádio, as DUAS pistas têm de dizer "
        "que estão vazias — a frase é do dono (`html_da_regua_do_radio`)")


def test_o_endereco_de_radio_nao_vai_para_a_tela(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """O MAC do adaptador é chave de casamento, e mais nada.

    Há dois portões de anonimato nesta casa, e a régua e a tabela passaram a
    ler o BlueZ — que entrega endereço. Ele não pode atravessar.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    endereco = "AA:BB:CC:00:00:01"
    p = _com_a_bancada(monkeypatch, [_Adaptador("hci0")],
                       [_Dongle(endereco, "hci0", "Sala")])
    saidas = [p._html_dos_adaptadores(),
              p._regua_do_radio(Contexto(state={"controllers": []}, mesa=[],
                                         conectados=[], estados={}))]
    for html in saidas:
        assert endereco not in html and endereco.lower() not in html, (
            "o endereço do adaptador chegou à tela — ele é chave de casamento "
            "entre o sysfs e o BlueZ, nunca texto de tela")


# ---------------------------------------------------------------------------
# A COLUNA "ONDE" DOS RÁDIOS VIZINHOS
# ---------------------------------------------------------------------------
def test_a_coluna_onde_dos_vizinhos_tem_endereco() -> None:
    """Um `.onde` por bloco `.viz`, com o interruptor do aviso antes dele.

    A ORDEM IMPORTA: a cor chega pelo combinador `~`, que só alcança IRMÃOS
    POSTERIORES. Com o `<i>` depois do `<span>`, o amarelo nunca acende.
    """
    html = BANCADA.read_text()
    blocos = re.findall(r'<div class="viz">.*?</div>', html)
    assert blocos, "nenhum bloco de rádio vizinho no desenho"
    for bloco in blocos:
        assert 'data-campo="vizinho-onde"' in bloco, (
            "um bloco de vizinho ficou sem a coluna 'Onde' — a linha do "
            "Check-up acusa 'dois rádios em entradas vizinhas' e não diz qual")
        assert bloco.index('data-campo="vizinho-onde-dica"') < bloco.index(
            'data-campo="vizinho-onde"'), (
            "o interruptor do aviso nasceu DEPOIS da linha que ele pinta — o "
            "`~` do CSS só alcança irmãos posteriores, e o amarelo nunca acende")


def test_o_onde_e_o_aviso_saem_do_produto(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Um rádio colado num adaptador ACUSA; os outros calam.

    As duas frases são de `secao_mesa` — `_onde_esta_o_radio` e
    `_avisos_de_vizinhanca` —, e a segunda garante **um** aviso por par: são
    dois aparelhos e UM problema, e marcar os dois leria como dois.
    """
    class _Radio:
        def __init__(self, no: str, devpath: str) -> None:
            self.no = no
            self.caminho = devpath
            self.vid = "3554"
            self.pid = "fa09"
            self.busnum = 3
            self.devpath = devpath
            self.painel = ""
            self.atras_de_hub = True
            self.controlador_pci = ""
            self.usb3 = False

    p = _pacote()
    adaptador = _Adaptador("hci0", no="/sys/3-1.1.1", devpath="1.1.1")
    perto = _Radio("/sys/3-1.1.2", "1.1.2")
    longe = _Radio("/sys/4-3", "3")
    mesa = _Mesa([adaptador], (perto, longe))
    mesa.apertadas = ((adaptador.no, perto.no),)

    onde = p._onde_dos_vizinhos(mesa)
    dicas = p._dicas_dos_vizinhos(mesa)
    assert len(onde) == 2 and len(dicas) == 2, (
        "a coluna 'Onde' tem de ter uma resposta por rádio — a tela endereça "
        "por POSIÇÃO, e uma lista curta cala o rádio do fim")
    assert dicas[0] and not dicas[1], (
        f"o aviso de vizinhança saiu {dicas!r}: ele tem de acusar o rádio "
        f"colado no adaptador e calar sobre o outro")
    assert onde[0] != onde[1], (
        "os dois rádios dizem a mesma coisa na coluna 'Onde', e só um está "
        "encostado no adaptador")


def test_o_vizinho_onde_chega_ao_pacote() -> None:
    """A ligação — as duas listas saem do `pacote()`, na mesma ordem do nome."""
    p = _pacote()
    saiu = p.pacote(_ctx())
    assert "vizinho-onde" in saiu and "vizinho-onde-dica" in saiu, (
        "o `pacote()` não emite a coluna 'Onde' dos vizinhos")
    assert len(saiu["vizinho-onde"]) == len(saiu["vizinho-nome"]), (
        "a coluna 'Onde' e a do nome têm comprimentos diferentes — a tela "
        "distribui as duas por POSIÇÃO, e um descompasso escreve o 'onde' de "
        "um rádio na linha de outro")


# ---------------------------------------------------------------------------
# O CONTEXTO VIVO — a mesa de dois que faz o `pacote()` correr inteiro
# ---------------------------------------------------------------------------
def _ctx():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    # A FAIXA SINTÉTICA DA CASA — há dois portões de anonimato nesta árvore.
    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": "galactic-purple",
         "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
         "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


# ---------------------------------------------------------------------------
# O BOTÃO "A luz não acende" — a dica que era do desenho
# ---------------------------------------------------------------------------
def test_a_dica_da_luz_segue_o_transporte() -> None:
    """As duas frases são do dono, e não a mesma congelada.

    O `title` do desenho era do transporte da CENA: o cartão da esquerda dizia
    *"Este controle está no cabo"* e o da direita explicava o rádio — e os dois
    continuavam dizendo isso quando o controle trocava de transporte. A cor já
    obedecia desde 03/09; a frase, não.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        DICA_NO_CABO,
        DICA_NO_RADIO,
    )

    p = _pacote()
    assert p.dica_da_luz("usb") == DICA_NO_CABO
    assert p.dica_da_luz("bt") == DICA_NO_RADIO
    assert p.dica_da_luz("") == DICA_NO_CABO, (
        "transporte vazio é TRAVA, pela mesma razão do gesto: `Disconnect` "
        "sobre um controle cujo transporte ninguém leu é um pedido no escuro")


def test_a_dica_da_luz_anexa_o_aviso_da_mesa_suja() -> None:
    """Mesa suja ANEXA, nunca substitui — e o "não sei" cala.

    A janela estável anexa de propósito: a pessoa continua precisando saber o
    que o botão faz. E `None` (a sonda não pôde responder) NÃO vira aviso —
    alarme sem medição atrás ensina a ignorar alarme.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        AVISO_DA_MESA_SUJA,
        DICA_NO_RADIO,
    )

    p = _pacote()
    suja = p.dica_da_luz("bt", mesa_suja=True)
    assert AVISO_DA_MESA_SUJA in suja and DICA_NO_RADIO in suja, (
        "o aviso da mesa suja substituiu a dica em vez de se juntar a ela")
    assert AVISO_DA_MESA_SUJA not in p.dica_da_luz("bt", mesa_suja=None), (
        "a sonda respondeu 'não sei' e a tela acusou mesmo assim")
    assert AVISO_DA_MESA_SUJA not in p.dica_da_luz("bt", mesa_suja=False)


def test_a_razao_do_nascimento_so_fala_na_condenacao() -> None:
    """Ausência, `limpa` e `nao_sei` calam; só a condenação escreve.

    A razão vem PRONTA do daemon (`sinal_da_barra.Carimbo.porque`): a tela não
    reescreve diagnóstico, e é isso que mantém uma frase só para as duas
    superfícies.
    """
    p = _pacote()
    porque = "Esta conexão nasceu com outro programa segurando o controle"
    condenado = p.dica_da_luz("bt", {"pede_reconexao": True, "porque": porque})
    assert porque in condenado, (
        "a razão do carimbo de nascimento não chegou à dica — o botão oferece "
        "uma cura sem dizer por que ela se aplica a ESTA conexão")
    for calado in (None, {}, {"pede_reconexao": False, "porque": porque}):
        assert porque not in p.dica_da_luz("bt", calado), (
            f"o nascimento {calado!r} não condena e a tela acusou mesmo assim")


def test_o_botao_da_luz_tem_a_dica_e_a_trava_em_nos_diferentes() -> None:
    """Um `data-campo` por nó — a classe no `<i>`, a dica no `<button>`.

    ARRANQUE A CURA: devolva o `data-campo="luz-trava"` ao próprio botão, e o
    `title` volta a ser o do desenho — o defeito que a dívida do gerador
    declarava com todas as letras.
    """
    html = BANCADA.read_text()
    botoes = re.findall(r'<button[^>]*data-gesto="luz-nao-acende"[^>]*>', html)
    assert botoes, "o botão 'A luz não acende' sumiu do desenho"
    for botao in botoes:
        assert 'data-campo="luz-dica"' in botao, (
            "o botão da luz não tem endereço para a dica — ela continua sendo "
            "a do desenho e mente quando o controle troca de transporte")
        assert 'data-hef-atributo="title"' in botao
        assert 'data-campo="luz-trava"' not in botao, (
            "a classe e a dica voltaram para o mesmo nó — o vocabulário é UM "
            "`data-campo` por nó, e uma das duas vai ficar sem endereço")
    # O `<i>` COLADO NO `<button>`: é assim que o `~` do CSS alcança a cor, e é
    # a única forma que prova a ORDEM dos dois. O `[^>]*></i><button` não deixa
    # nada entrar no meio.
    irmaos = re.findall(r'<i class="ltrava[^"]*"[^>]*></i><button[^>]*'
                        r'data-gesto="luz-nao-acende"', html)
    assert len(irmaos) == len(botoes), (
        f"{len(irmaos)} dos {len(botoes)} botões da luz têm o interruptor "
        f"colado ANTES deles — o `~` do CSS só alcança irmãos posteriores, e o "
        f"botão sem irmão anterior nunca apaga")
    for irmao in irmaos:
        assert 'data-campo="luz-trava"' in irmao, (
            "o interruptor da trava ficou sem endereço — a classe volta a ser a "
            "do desenho, cravada pela posição no mockup")


def test_a_dica_da_luz_chega_ao_pacote() -> None:
    """A ligação — uma dica por controle, no `colunas`."""
    p = _pacote()
    saiu = p.pacote(_ctx())
    for uniq, coluna in saiu["colunas"].items():
        assert coluna.get("luz-dica"), (
            f"o controle {uniq[:4]}… saiu sem `luz-dica` — o botão fica com o "
            f"`title` do desenho")


# ---------------------------------------------------------------------------
# O MICROFONE — o escopo virou leitura (D-12) e o custo virou derivado
# ---------------------------------------------------------------------------
def test_o_escopo_do_botao_do_mic_e_leitura_e_nao_escolha() -> None:
    """**D-12.** A tela DIZ o que o botão físico faz; não pergunta.

    A doutrina é a desta mesma aba, e está escrita na legenda dela: a chavinha
    *"pelo cabo / pelo rádio"* saiu porque *"oferecia uma escolha que o
    transporte já tinha feito"*. Aqui a escolha já tinha sido feita por ELA.
    """
    html = BANCADA.read_text()
    assert 'data-gesto="mic-escopo"' not in html, (
        "o `<select>` do escopo do microfone voltou: ele oferecia por CONTROLE "
        "um valor que o produto guarda por MÁQUINA, e o segundo cartão "
        "sobrescreveria a escolha do primeiro, calado")
    assert html.count('data-campo="mic-escopo"') >= 1, (
        "a leitura do escopo do microfone ficou sem endereço — trocar um botão "
        "morto por um texto morto não é cura")


def test_o_escopo_le_o_valor_da_maquina() -> None:
    """As duas falas são as do `<select>` que saiu — nem uma palavra nova.

    E a ausência devolve VAZIO, nunca o padrão do `DaemonConfig`: um daemon que
    não respondeu não é um daemon que respondeu `True`.
    """
    p = _pacote()
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": True}) == (
        p.FALA_DO_BOTAO_DO_MIC[True])
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": False}) == (
        p.FALA_DO_BOTAO_DO_MIC[False])
    assert p.escopo_do_botao_do_mic({}) == "", (
        "sem resposta do daemon a tela afirmou um dos dois — o travessão do "
        "piloto é a resposta honesta")
    assert p.pacote(_ctx())["mic-escopo"] == "", (
        "o `_ctx()` não publica a chave, e o pacote inventou um valor")


def test_o_custo_do_mic_no_radio_nao_e_digitado(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A MORDIDA do número: mude a constante do medidor e a frase acompanha.

    Os 16,3 do desenho conferiam com `radio_da_mesa` HOJE — eles eram a segunda
    grafia. `frase_da_capacidade_do_mic` deriva os quatro números das constantes
    do medidor, *"que é o mesmo lugar de onde a barra de Rádio em uso tira os
    dela"*.
    """
    from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

    p = _pacote()
    antes = p.dica_do_microfone("bt")
    monkeypatch.setattr(rm, "HZ_AUDIO_COM_MIC", rm.HZ_AUDIO_COM_MIC * 3)
    depois = p.dica_do_microfone("bt")
    assert antes != depois, (
        "a frase do custo do microfone não seguiu a constante do medidor — ela "
        "está digitada, e no dia em que alguém remedir o A/B a janela estável "
        "acompanha e o HTML não")


def test_o_mic_pelo_cabo_nao_cobra_turno_de_radio() -> None:
    """Pelo cabo não há conta a fazer — e "0 turnos" seria um número sem conta."""
    p = _pacote()
    cabo = p.dica_do_microfone("usb")
    assert p._MIC_NAO_CUSTA_RADIO in cabo
    assert "turnos de rádio" not in cabo.replace(p._MIC_NAO_CUSTA_RADIO, ""), (
        "a frase do cabo trouxe a conta do rádio junto")


def test_o_titulo_do_resumo_do_mic_tem_endereco() -> None:
    """Sem o endereço, o `title` congela no transporte da cena.

    ARRANQUE A CURA: tire o `data-campo="mic-dica"` do `aba08.py`, regenere, e
    este teste reprova.
    """
    html = BANCADA.read_text()
    resumos = re.findall(r'<span[^>]*title="[^"]*microfone[^"]*"[^>]*>Microfone ',
                         html)
    assert resumos, "o resumo do microfone sumiu da linha fechada"
    for resumo in resumos:
        assert 'data-campo="mic-dica"' in resumo, (
            "o `title` do resumo do microfone continua sendo o do desenho — "
            "ele diz 'pelo cabo' com o controle no rádio")
