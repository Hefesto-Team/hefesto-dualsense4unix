"""O censo do gabinete não inventa gabinete — e declara quando as fontes brigam.

MOTOR-7 da ``MOTOR-DO-ARRANJO-01``. As duas mordidas que a sprint nomeia estão
aqui com o nome que ela deu:

* ``test_placa_sem_tabela_8_nao_inventa_gabinete`` — arrancado o filtro de
  gabarito (``conector_de_verdade``), uma placa cuja tabela 8 é template puro
  vira 18 conectores com selo de firmware, e a aba desenha um gabinete que
  ninguém tem;
* ``test_tabela_8_que_contradiz_o_kernel_nao_vence_sozinha`` — arrancada a
  declaração de divergência, a BIOS vence com 5 e a aba desenha cinco entradas
  para quem tem oito.

DE ONDE VÊM OS NÚMEROS DESTE ARQUIVO
-------------------------------------

* **5 conectores USB, 18 blocos, ``J1500``..``J1504``, um ``USB-C`` que esta
  placa não tem** — medido em 25/08/2026 com ``pkexec dmidecode -t 8`` na
  Gigabyte B450M S2H e registrado na §7.4 da sprint. **O texto de
  :data:`TABELA_8_DESTA_PLACA` é uma RECONSTRUÇÃO** no formato canônico do
  ``dmidecode``, não um transcrito capturado: nesta árvore não há ``sudo`` sem
  senha, e ``pkexec`` abriria um diálogo na tela dela. O que está medido é o
  CONTEÚDO (quais designações, quantas, de que tipo); a moldura é a do programa;
* **22 nós de raiz, 15 buracos, 11 de encaixe, ``maxchild`` 10+4+4+4** — remedido
  nesta árvore em 25/08/2026 às 21h18, com o hub externo de volta ao barramento
  (``listar_entradas`` devolve 38 nós no total, 16 deles do hub dela).

E A SEXTA MORDIDA MEDE O CONSUMIDOR, NÃO O CENSO (26/08/2026)
---------------------------------------------------------------

O censo já gravava a divergência e a pergunta desde 25/08, e **nenhuma linha de
``app/`` abria o arquivo** — o defeito não estava aqui, estava na ausência de
quem lesse. Por isso este arquivo importa ``app/actions/config/secao_mesa`` e
mede as duas funções de MÓDULO que a seção ganhou. Nenhuma delas monta widget:
sem GTK, sem display e sem ``/sys``, como o resto do arquivo.
"""

import json
import re

import pytest

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations import censo_do_gabinete as cg
from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa

# ---------------------------------------------------------------------------
# As fixtures — a placa desta bancada, e a placa que só tem gabarito
# ---------------------------------------------------------------------------

_MOLDE = """Handle 0x{handle:04X}, DMI type 8, 9 bytes
Port Connector Information
\tInternal Reference Designator: {interna}
\tInternal Connector Type: {tipo_interno}
\tExternal Reference Designator: {externa}
\tExternal Connector Type: {tipo_externo}
\tPort Type: {porta}
"""

_PREAMBULO = "# dmidecode 3.5\nGetting SMBIOS data from sysfs.\nSMBIOS 3.3.0 present.\n\n"


def _bloco(handle, *, interna="Not Specified", tipo_interno="None",
           externa="Not Specified", tipo_externo="None", porta="None"):
    return _MOLDE.format(
        handle=handle, interna=interna, tipo_interno=tipo_interno,
        externa=externa, tipo_externo=tipo_externo, porta=porta,
    )


def _tabela(blocos):
    return _PREAMBULO + "\n".join(blocos)


#: Os CINCO USB desta placa, com o `USB-C` que ela não tem — §7.4 da sprint.
_USB_DESTA_PLACA = (
    ("J1500", "Access Bus (USB)", "USB 3.0"),
    ("J1501", "Access Bus (USB)", "USB 3.0"),
    ("J1502", "USB Type-C Receptacle", "USB-C"),
    ("J1503", "Access Bus (USB)", "USB 3.0"),
    ("J1504", "Access Bus (USB)", "USB 3.1"),
)

#: 18 blocos: os 5 com conteúdo e 13 de gabarito, como a tabela real.
TABELA_8_DESTA_PLACA = _tabela(
    [
        _bloco(0x0C + i, externa=designacao, tipo_externo=tipo_externo, porta=porta)
        for i, (designacao, tipo_externo, porta) in enumerate(_USB_DESTA_PLACA)
    ]
    + [_bloco(0x20 + i) for i in range(13)]
)

#: A placa que respondeu 18 vezes "não preenchi" — o caso comum, e o que a §7.4
#: avisou. Uma tabela assim é gabarito, não descrição.
TABELA_8_SO_DE_GABARITO = _tabela([_bloco(0x0C + i) for i in range(18)])

#: E a placa que não tem tabela nenhuma: o `dmidecode` imprime só o preâmbulo.
TABELA_8_AUSENTE = _PREAMBULO

#: A placa desta bancada, lida em 25/08/2026 de ``/sys/class/dmi/id/`` — sem root,
#: e é por isso que a aba também a enxerga.
PLACA_DESTA_BANCADA = {
    "fabricante": {"valor": "Gigabyte Technology Co., Ltd.", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "modelo": {"valor": "B450M S2H", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "bios": {"valor": "F68a", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "tipo_de_chassi": {"valor": 3, "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "movel": {"valor": False, "de_onde_sei": cg.LIDO_DO_FIRMWARE},
}


def _no(hub, numero, *, par="", encaixe="hotplug", aparelho=""):
    return NoDeEntrada(
        no=f"{hub}-port{numero}",
        caminho_sysfs=f"/sys/bus/usb/devices/{hub}/{hub}-port{numero}",
        hub=hub,
        numero=numero,
        estado="configured" if aparelho else "not attached",
        tipo_de_encaixe=encaixe,
        par=par,
        aparelho=aparelho,
    )


def entradas_desta_bancada():
    """Os 22 nós de raiz TRANSCRITOS da bancada em 25/08/2026, 21h18.

    Não é topologia inventada para dar o número certo: é a leitura, nó a nó, com
    os ``peer`` que o kernel publica. **Três** pares no lado de gabinete
    (``usb1-port5..7`` com ``usb2-port1..3``; ``usb1-port8`` e ``usb2-port4``
    ficam sozinhos) e **quatro** nos internos (``usb3-port1..4`` com
    ``usb4-port1..4``). Sete pares, 15 buracos, 11 deles ``hotplug``.

    A primeira versão desta fixture supôs quatro pares em cima e três embaixo — a
    mesma soma, e ``buracos_de_encaixe`` deu 10 em vez de 11. A régua reprovou a
    si mesma antes de reprovar o produto, que é para isso que
    ``test_a_fixture_reproduz_a_bancada_medida`` existe.
    """
    nos = []
    for n in range(1, 11):
        par = f"usb2-port{n - 4}" if 5 <= n <= 7 else ""
        nos.append(_no("usb1", n, par=par, aparelho="1-3" if n == 3 else ""))
    for n in range(1, 5):
        nos.append(_no("usb2", n, par=f"usb1-port{n + 4}" if n <= 3 else ""))
    for n in range(1, 5):
        nos.append(_no("usb3", n, par=f"usb4-port{n}", encaixe="unknown",
                       aparelho="3-1" if n == 1 else ""))
    for n in range(1, 5):
        nos.append(_no("usb4", n, par=f"usb3-port{n}", encaixe="unknown",
                       aparelho="4-1" if n == 1 else ""))
    return tuple(nos)


MAXCHILD_DESTA_BANCADA = {"usb1": 10, "usb2": 4, "usb3": 4, "usb4": 4}


def censo_desta_bancada(dmidecode=TABELA_8_DESTA_PLACA):
    return cg.montar_censo(
        dmidecode=dmidecode,
        entradas=entradas_desta_bancada(),
        maxchild=MAXCHILD_DESTA_BANCADA,
        placa=dict(PLACA_DESTA_BANCADA),
        entradas_da_tabela_8=18,
        agora="2026-08-25T21:18:00-03:00",
    )


# ---------------------------------------------------------------------------
# A fixture confere consigo mesma — régua que só sabe passar não é régua
# ---------------------------------------------------------------------------


def test_a_fixture_reproduz_a_bancada_medida():
    """Antes de medir o produto, medir a régua.

    Se a fixture não reproduzir os 22/15/11 e os 5 USB, todo veredito abaixo é
    sobre uma máquina imaginária — a família "o instrumento mente mais que o
    produto", que esta casa já pagou três vezes num dia.
    """
    entradas = entradas_desta_bancada()
    assert len(entradas) == 22
    assert sum(MAXCHILD_DESTA_BANCADA.values()) == 22
    kernel = cg.censo_do_kernel(entradas, MAXCHILD_DESTA_BANCADA)
    assert kernel["soquetes"]["valor"] == 22
    assert kernel["buracos"]["valor"] == 15
    assert kernel["buracos_de_encaixe"]["valor"] == 11
    assert kernel["reguas_concordam"] is True
    assert cg.blocos_da_tabela_8(TABELA_8_DESTA_PLACA) == 18
    assert len(cg.conectores_do_dmidecode(TABELA_8_DESTA_PLACA)) == 5


# ---------------------------------------------------------------------------
# MORDIDA 1 — a placa que não respondeu
# ---------------------------------------------------------------------------


# O `ids=` não é enfeite: sem ele o pytest usa o TEXTO como nome do caso, e a
# tabela de gabarito tem 3 KB — a mordida imprimia três telas de `Not Specified`
# em vez de dizer qual placa falhou. Régua que reprova de um jeito ilegível é
# régua que se aprende a ignorar.
@pytest.mark.parametrize(
    "texto,apelido",
    [
        (TABELA_8_AUSENTE, "sem tabela nenhuma"),
        (TABELA_8_SO_DE_GABARITO, "18 blocos de gabarito"),
        ("", "dmidecode ausente ou sem root"),
    ],
    ids=["sem-tabela", "so-gabarito", "sem-dmidecode"],
)
def test_placa_sem_tabela_8_nao_inventa_gabinete(texto, apelido):
    """**A MORDIDA.** Firmware que não respondeu não vira gabinete de mentira.

    Os três casos são *"não respondeu"* e têm de sair idênticos: placa sem tabela,
    placa com tabela de gabarito, e install sem poder de root. Um gabinete
    inventado é PIOR que nenhum, porque ela confia no que o produto desenha —
    procura no metal um buraco que o mapa mostra e não existe, e conclui que
    entendeu errado.

    ARRANCANDO ``conector_de_verdade`` (fazendo-a devolver ``True``): o caso do
    gabarito passa a produzir 18 conectores, ``de_onde_sei`` vira
    ``lido-do-firmware``, ``tabela_8_respondeu`` vira ``True`` e
    ``conectores_usb`` vira um número — cinco afirmações abaixo caem de uma vez.
    """
    censo = censo_desta_bancada(dmidecode=texto)
    assert censo["faces"] == [], f"{apelido}: inventou face"
    assert censo["de_onde_sei"] == cg.NAO_RESPONDEU, apelido
    assert censo["firmware"]["tabela_8_respondeu"] is False, apelido
    assert censo["firmware"]["conectores"] == [], apelido
    assert censo["firmware"]["conectores_usb"] == {
        "valor": None,
        "de_onde_sei": cg.NAO_RESPONDEU,
    }, apelido
    # Sem segunda fonte não há divergência a declarar — mas a pergunta continua,
    # porque nenhuma das contagens de kernel viu o gabinete por fora.
    assert censo["contagens"]["divergem"] is False, apelido
    assert censo["contagens"]["precisa_da_palavra_dela"] is True, apelido


def test_zero_conectores_nao_e_a_mesma_coisa_que_nao_perguntei():
    """A recusa que o dublê tem de saber: ``None`` com selo, nunca ``0``.

    ``conectores_usb = 0`` com selo ``lido-do-firmware`` AFIRMA que a placa não
    tem entrada USB nenhuma — uma afirmação que este módulo não tem como fazer, e
    que a aba leria como fato.
    """
    censo = censo_desta_bancada(dmidecode=TABELA_8_SO_DE_GABARITO)
    for caminho, fato in _todos_os_fatos(censo):
        if fato["valor"] is None:
            assert fato["de_onde_sei"] == cg.NAO_RESPONDEU, caminho
        else:
            assert fato["de_onde_sei"] != cg.NAO_RESPONDEU, caminho


def test_faces_nascem_vazias_mesmo_com_a_bios_falante():
    """Nem a BIOS mais loquaz produz uma face.

    O DMI tipo 8 dá o inventário, não a face; e o ``physical_location`` do kernel
    também não — medido em 25/08/2026, o teclado e o mouse desta bancada são byte
    a byte iguais nos três campos. Quem sabe qual buraco é da frente é ela.
    """
    censo = censo_desta_bancada()
    assert censo["firmware"]["tabela_8_respondeu"] is True
    assert censo["faces"] == []
    assert "física" not in censo["por_que_faces_vazias"]  # é frase de gente
    assert censo["por_que_faces_vazias"].strip()


# ---------------------------------------------------------------------------
# MORDIDA 2 — a BIOS não vence sozinha
# ---------------------------------------------------------------------------


def test_tabela_8_que_contradiz_o_kernel_nao_vence_sozinha():
    """**A MORDIDA.** As três contagens ficam gravadas, e a briga é declarada.

    A BIOS desta placa diz **5** conectores USB; o kernel conta **22** soquetes de
    raiz e **15** buracos; ela conta **8** externos na foto. Nenhuma é
    autoritativa, e por isso o censo grava todas e marca ``divergem``.

    ARRANCANDO a declaração (fazendo ``declarar_divergencia`` eleger o firmware — devolver
    só a contagem da BIOS e ``divergem=False``): o censo passa a afirmar 5, a aba
    desenha cinco entradas para quem tem oito, e a pessoa procura no gabinete três
    buracos que o mapa não mostra.
    """
    contagens = censo_desta_bancada()["contagens"]
    assert contagens["firmware"] == {"valor": 5, "de_onde_sei": cg.LIDO_DO_FIRMWARE}
    assert contagens["kernel_soquetes"] == {"valor": 22, "de_onde_sei": cg.LIDO_DO_KERNEL}
    assert contagens["kernel_buracos"] == {"valor": 15, "de_onde_sei": cg.LIDO_DO_KERNEL}
    assert contagens["divergem"] is True
    # E a divergência tem de chegar em PALAVRA, senão a aba pode escondê-la.
    assert "5" in contagens["pergunta"] and "15" in contagens["pergunta"]
    assert contagens["pergunta"].endswith("?")


def test_quando_as_contas_batem_nao_ha_divergencia_a_declarar():
    """A outra metade da régua: ela precisa saber ficar CALADA.

    Uma placa cuja BIOS declara exatamente os 15 buracos que o barramento mostra
    não tem divergência — e gritar ali ensinaria a ignorar o aviso quando ele for
    verdadeiro. O que NÃO some é ``precisa_da_palavra_dela``: nem com as duas
    fontes de acordo alguém viu o gabinete por fora.
    """
    contagens = cg.declarar_divergencia(firmware=15, soquetes=22, buracos=15)
    assert contagens["divergem"] is False
    assert contagens["precisa_da_palavra_dela"] is True


def test_uma_fonte_sozinha_nao_diverge_de_nada():
    """Sem segunda régua não há briga — e inventar uma seria ruído."""
    assert cg.declarar_divergencia(firmware=5, soquetes=None, buracos=None)["divergem"] is False
    assert cg.declarar_divergencia(firmware=None, soquetes=22, buracos=15)["divergem"] is False


def test_a_pergunta_diz_o_que_faltou_em_cada_caso():
    """Três silêncios diferentes, três frases diferentes.

    "Não perguntei à BIOS", "a BIOS calou" e "ninguém respondeu" mandam a pessoa
    fazer coisas diferentes, e a mesma frase para os três é o F6 outra vez.
    """
    muda = cg.declarar_divergencia(firmware=None, soquetes=None, buracos=None)["pergunta"]
    so_kernel = cg.declarar_divergencia(firmware=None, soquetes=22, buracos=15)["pergunta"]
    briga = cg.declarar_divergencia(firmware=5, soquetes=22, buracos=15)["pergunta"]
    assert len({muda, so_kernel, briga}) == 3
    assert "nem a BIOS" in muda


# ---------------------------------------------------------------------------
# MORDIDA 3 — o censo de outra placa não serve
# ---------------------------------------------------------------------------


def test_censo_de_outra_placa_nao_serve():
    """**A MORDIDA.** ``gabinete.json`` que veio de outro PC é recusado.

    HOME restaurado de backup, ``~/.local/state`` num disco que anda entre duas
    máquinas — e o produto desenharia o gabinete de outra placa com selo de
    firmware. Arrancada a conferência (fazendo-a devolver ``True`` sempre), a aba
    abre com o gabinete de OUTRA pessoa e ela confia nele.
    """
    censo = censo_desta_bancada()
    assert cg.serve_para_esta_placa(censo, dict(PLACA_DESTA_BANCADA)) is True
    outra = {
        "fabricante": {"valor": "ASUSTeK COMPUTER INC.", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
        "modelo": {"valor": "PRIME B450M-A", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    }
    assert cg.serve_para_esta_placa(censo, outra) is False


def test_placa_que_nao_sabe_quem_e_tambem_e_recusa():
    """Não saber quem é a placa não autoriza a dizer que serve.

    ``Default string`` no ``board_name`` é o gabarito do fabricante — medido nesta
    placa, no ``board_version``. Comparar dois desconhecidos e concluir "é a
    mesma" é a forma mais barata de errar aqui.
    """
    censo = censo_desta_bancada()
    anonima = {
        "fabricante": {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU},
        "modelo": {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU},
    }
    assert cg.serve_para_esta_placa(censo, anonima) is False
    assert cg.serve_para_esta_placa({}, dict(PLACA_DESTA_BANCADA)) is False


# ---------------------------------------------------------------------------
# MORDIDA 4 — reinstalar não apaga o que ela ensinou
# ---------------------------------------------------------------------------


def _censo_com_a_palavra_dela():
    """O arquivo depois de ela responder na aba: faces declaradas e a contagem."""
    antigo = censo_desta_bancada()
    antigo["faces"] = [
        {"nome": "traseira", "entradas": 6, "de_onde_sei": cg.DECLARADO_POR_ELA},
        {"nome": "frente", "entradas": 2, "de_onde_sei": cg.DECLARADO_POR_ELA},
    ]
    antigo["contagens"]["declarado_por_ela"] = {
        "valor": 8,
        "de_onde_sei": cg.DECLARADO_POR_ELA,
    }
    return antigo


def test_o_install_nao_apaga_o_que_ela_ensinou():
    """**A MORDIDA.** A segunda instalação não pode zerar a resposta dela.

    Este arquivo tem DOIS escritores: o install, que traz o firmware, e a aba,
    onde ela responde *"a minha traseira tem 8"*. É o único lugar onde essa
    resposta mora. Arrancada ``preservar_o_que_ela_disse``, o segundo
    ``install.sh`` grava por cima e a aba volta a perguntar o que ela já
    respondeu — em silêncio, que é o pior modo de perder trabalho de alguém.
    """
    antigo = _censo_com_a_palavra_dela()
    novo = censo_desta_bancada(dmidecode="")  # uma reinstalação sem root
    herdado = cg.preservar_o_que_ela_disse(novo, antigo, dict(PLACA_DESTA_BANCADA))
    assert len(herdado["faces"]) == 2
    assert herdado["contagens"]["declarado_por_ela"]["valor"] == 8
    assert herdado["contagens"]["declarado_por_ela"]["de_onde_sei"] == cg.DECLARADO_POR_ELA
    # E o que ela respondeu ENCERRA a pergunta — senão a aba pergunta de novo.
    assert herdado["contagens"]["precisa_da_palavra_dela"] is False
    # O resto continua sendo a leitura de agora, não a de ontem.
    assert herdado["de_onde_sei"] == cg.NAO_RESPONDEU


def test_a_declaracao_de_outra_placa_nao_pega_carona():
    """A recusa: faces de outro gabinete descreveriam um metal que não é este.

    E a troca não pode ser silenciosa — ``substituiu_outra_placa`` existe para a
    aba poder dizer o que aconteceu.
    """
    outra = {
        "fabricante": {"valor": "ASUSTeK COMPUTER INC.", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
        "modelo": {"valor": "PRIME B450M-A", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    }
    herdado = cg.preservar_o_que_ela_disse(_censo_com_a_palavra_dela(), {}, outra)
    assert "substituiu_outra_placa" not in herdado  # não havia censo anterior

    herdado = cg.preservar_o_que_ela_disse(
        censo_desta_bancada(), _censo_com_a_palavra_dela(), outra
    )
    assert herdado["faces"] == []
    assert herdado["substituiu_outra_placa"] is True


def test_arquivo_ausente_ou_quebrado_nao_derruba_o_install(tmp_path):
    """Primeira instalação, JSON truncado, formato de outra versão: tudo é ``{}``."""
    assert cg.ler_do_disco(str(tmp_path / "nao-existe.json")) == {}
    quebrado = tmp_path / "quebrado.json"
    quebrado.write_text('{"faces": [', encoding="utf-8")
    assert cg.ler_do_disco(str(quebrado)) == {}
    lista = tmp_path / "lista.json"
    lista.write_text("[1, 2, 3]", encoding="utf-8")
    assert cg.ler_do_disco(str(lista)) == {}
    inteiro = tmp_path / "bom.json"
    cg.gravar(_censo_com_a_palavra_dela(), str(inteiro))
    assert len(cg.ler_do_disco(str(inteiro))["faces"]) == 2


# ---------------------------------------------------------------------------
# O selo em TODO campo — a segunda mordida que a sprint nomeia
# ---------------------------------------------------------------------------


def test_o_que_o_firmware_disse_vem_com_selo():
    """Todo ``valor`` deste arquivo tem um ``de_onde_sei`` ao lado, e ele é válido.

    Sem isto a aba não distingue o que a BIOS AFIRMOU do que o kernel CONTOU — e
    é essa distinção que impede raciocínio de se vestir de medição. A varredura é
    da árvore inteira, não de uma lista digitada: campo novo que alguém escrever
    sem selo reprova sozinho.
    """
    fatos = _todos_os_fatos(censo_desta_bancada())
    assert len(fatos) >= 15, "a varredura não achou os campos — a régua quebrou"
    for caminho, fato in fatos:
        assert fato["de_onde_sei"] in cg.SELOS, f"{caminho}: selo desconhecido"
    # E o selo tem de ser o CERTO: a BIOS não pode carimbar contagem de kernel.
    censo = censo_desta_bancada()
    assert censo["kernel"]["soquetes"]["de_onde_sei"] == cg.LIDO_DO_KERNEL
    assert censo["firmware"]["conectores_usb"]["de_onde_sei"] == cg.LIDO_DO_FIRMWARE
    for conector in censo["firmware"]["conectores"]:
        assert conector["de_onde_sei"] == cg.LIDO_DO_FIRMWARE


def test_o_selo_de_ela_existe_e_o_censo_nunca_o_grava():
    """``declarado-por-ela`` é do vocabulário, e é da ABA — não deste módulo.

    Ele precisa existir aqui porque a aba escreve no MESMO arquivo; se o censo o
    gravasse, estaria pondo palavra na boca dela.
    """
    assert cg.DECLARADO_POR_ELA in cg.SELOS
    selos = {fato["de_onde_sei"] for _, fato in _todos_os_fatos(censo_desta_bancada())}
    assert cg.DECLARADO_POR_ELA not in selos


# ---------------------------------------------------------------------------
# O kernel: o chassi, e não o hub da mesa
# ---------------------------------------------------------------------------


def test_o_hub_da_mesa_nao_entra_no_gabinete():
    """O gabinete é o CHASSI. O hub que ela pendurou não muda o metal.

    Medido às 21h18: com o hub de volta, ``listar_entradas`` devolve 38 nós em
    oito hubs. Sem o filtro de raiz, o gabinete dela cresceria de 15 para 23
    buracos ao plugar um hub e encolheria ao desplugá-lo — que é o oposto do que
    um mapa de gabinete tem de fazer.
    """
    do_hub = tuple(_no("3-1", n) for n in range(1, 5)) + tuple(_no("3-1.1", n) for n in range(1, 5))
    com_hub = entradas_desta_bancada() + do_hub
    assert len(com_hub) == 30
    assert len(cg.soquetes_de_raiz(com_hub)) == 22
    assert cg.censo_do_kernel(com_hub, MAXCHILD_DESTA_BANCADA)["buracos"]["valor"] == 15


def test_o_buraco_3x_conta_uma_vez_so():
    """Um furo USB 3.x publica DOIS nós, e é UM furo.

    O lado 2.0 e o lado 3.x são amarrados pelo ``peer``. Contar nó mandaria ela
    procurar 22 furos num gabinete que tem 15 — e chamar o lado 2.0 de "vazio"
    mandaria encaixar o cabo onde o mouse já está.
    """
    kernel = cg.censo_do_kernel(entradas_desta_bancada(), MAXCHILD_DESTA_BANCADA)
    assert kernel["soquetes"]["valor"] == 22
    assert kernel["buracos"]["valor"] == 15
    assert kernel["buracos"]["valor"] < kernel["soquetes"]["valor"]


def test_as_duas_reguas_do_kernel_se_conferem():
    """Contar nós e ler ``maxchild`` são dois caminhos, e o censo diz se batem.

    Bateram nesta bancada (22 e 22). Quando não baterem, o censo grava as duas e
    marca ``reguas_concordam: False`` — nunca escolhe, pelo mesmo motivo de
    sempre. E sem ``maxchild`` a resposta é ``None``: *não sei* é resposta.
    """
    entradas = entradas_desta_bancada()
    assert cg.censo_do_kernel(entradas, MAXCHILD_DESTA_BANCADA)["reguas_concordam"] is True
    mentiroso = dict(MAXCHILD_DESTA_BANCADA, usb1=4)
    torto = cg.censo_do_kernel(entradas, mentiroso)
    assert torto["reguas_concordam"] is False
    assert torto["soquetes"]["valor"] == 22 and torto["maxchild"]["valor"] == 16
    assert cg.censo_do_kernel(entradas, {})["reguas_concordam"] is None


def test_barramento_mudo_nao_vira_gabinete_sem_buracos():
    """``/sys`` ausente — contêiner, sandbox — é ``None``, nunca zero buracos."""
    kernel = cg.censo_do_kernel((), {})
    assert kernel["soquetes"] == {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU}
    assert kernel["buracos"] == {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU}


# ---------------------------------------------------------------------------
# O parser — e as recusas dele
# ---------------------------------------------------------------------------


def test_o_parser_le_os_cinco_campos_de_cada_conector():
    """A palavra do fabricante é o dado, e sai verbatim."""
    primeiro = cg.conectores_do_dmidecode(TABELA_8_DESTA_PLACA)[0]
    assert primeiro.designacao_externa == "J1500"
    assert primeiro.tipo_externo == "Access Bus (USB)"
    assert primeiro.tipo_de_porta == "USB 3.0"
    assert primeiro.e_usb is True and primeiro.externo is True


def test_usb_sai_do_tipo_e_nunca_da_designacao():
    """``J1500`` não diz protocolo; ``Access Bus (USB)`` diz.

    Aceitar a designação faria qualquer placa que serigrafa ``USB1`` num conector
    de áudio contar como USB — adivinhar por texto é como se erra com confiança.
    """
    serigrafia = cg.Conector(designacao_externa="USB1", tipo_externo="Mini Jack (headphones)")
    assert serigrafia.e_usb is False
    for rotulo in ("USB", "USB 3.0", "USB-C", "Access Bus (USB)", "USB Type-C Receptacle"):
        assert cg.Conector(tipo_de_porta=rotulo).e_usb is True


def test_conector_interno_nao_vira_buraco_do_gabinete():
    """Cabeçote de placa-mãe é fato, e não é buraco que ela alcança.

    Ele fica gravado — é informação sobre a placa — mas fora de
    ``conectores_usb``: mandar alguém procurar um ``F_USB1`` atrás do gabinete é
    pior que não dizer nada.
    """
    interno = _bloco(0x30, interna="F_USB1", tipo_interno="Access Bus (USB)", porta="USB")
    censo = censo_desta_bancada(dmidecode=TABELA_8_DESTA_PLACA + "\n" + interno)
    conectores = censo["firmware"]["conectores"]
    assert len(conectores) == 6, "o cabeçote tem de FICAR gravado"
    assert conectores[-1]["externo"] is False and conectores[-1]["usb"] is True
    assert censo["firmware"]["conectores_usb"]["valor"] == 5, "e não pode CONTAR"


def test_bloco_de_outro_tipo_nao_confunde_o_parser():
    """A recusa: só ``DMI type 8`` entra, mesmo recebendo o ``dmidecode`` inteiro.

    Um dia alguém passa a saída completa em vez de ``-t 8``, e o resultado tem de
    ser o mesmo. O bloco de tipo 9 abaixo tem os MESMOS rótulos de designação —
    é a armadilha de verdade, não uma inventada.
    """
    tipo_9 = (
        "Handle 0x0040, DMI type 9, 17 bytes\n"
        "System Slot Information\n"
        "\tDesignation: PCIEX16\n"
        "\tExternal Reference Designator: J9999\n"
        "\tPort Type: USB\n"
    )
    misturado = TABELA_8_DESTA_PLACA + "\n" + tipo_9
    conectores = cg.conectores_do_dmidecode(misturado)
    assert len(conectores) == 5
    assert "J9999" not in {c.designacao_externa for c in conectores}
    assert cg.blocos_da_tabela_8(misturado) == 18


def test_a_contagem_bruta_da_tabela_conta_o_gabarito_tambem():
    """18 blocos com zero conteúdo é uma afirmação — sobre o fabricante.

    Ela some se contarmos só o que sobreviveu ao filtro, e é ela que permite
    dizer *"a sua placa TEM tabela e ela está em branco"*.
    """
    assert cg.blocos_da_tabela_8(TABELA_8_SO_DE_GABARITO) == 18
    assert cg.conectores_do_dmidecode(TABELA_8_SO_DE_GABARITO) == ()
    assert cg.blocos_da_tabela_8("") == 0


def test_a_tabela_existe_mesmo_sem_root_para_le_la():
    """O diretório do ``/sys`` é listável; o ``raw`` de cada entrada não é.

    Isso separa *"a sua placa não tem tabela"* de *"tem 18 e eu não tive root"* —
    e as duas frases mandam a pessoa fazer coisas diferentes.
    """
    falso = ["8-0", "8-1", "8-2", "1-0", "4-0", "17-3"]
    assert cg.entradas_no_sysfs(raiz_dmi="/qualquer", listar=lambda _: falso) == 3
    assert cg.entradas_no_sysfs(raiz_dmi="/qualquer", listar=lambda _: []) == 0

    def _explode(_):
        raise OSError("sem /sys")

    assert cg.entradas_no_sysfs(raiz_dmi="/qualquer", listar=_explode) is None


# ---------------------------------------------------------------------------
# A placa, e a gravação
# ---------------------------------------------------------------------------


def test_gabarito_de_fabricante_nao_vira_modelo():
    """``Default string`` no ``board_version`` é medido NESTA placa, hoje."""
    campos = {
        "board_vendor": "Gigabyte Technology Co., Ltd.",
        "board_name": "Default string",
        "bios_version": "F68a",
        "chassis_type": "3",
    }
    placa = cg.ler_a_placa(raiz_dmi_id="/x", ler=lambda c: campos[c.rsplit("/", 1)[-1]])
    assert placa["modelo"] == {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU}
    assert placa["fabricante"]["valor"] == "Gigabyte Technology Co., Ltd."
    assert placa["movel"]["valor"] is False


@pytest.mark.parametrize(
    "tipo,movel",
    [("3", False), ("10", True), ("9", True), ("7", False), ("2", None), ("", None)],
)
def test_notebook_e_desktop_se_separam_e_o_resto_e_nao_sei(tipo, movel):
    """Três estados, e o terceiro é o que impede mandar um notebook achar rack."""
    campos = {"board_vendor": "X", "board_name": "Y", "bios_version": "Z", "chassis_type": tipo}
    placa = cg.ler_a_placa(raiz_dmi_id="/x", ler=lambda c: campos[c.rsplit("/", 1)[-1]])
    assert placa["movel"]["valor"] is movel


def test_gravar_e_atomico_e_nao_deixa_sobra(tmp_path):
    """Escrita por troca de nome — JSON pela metade é aba sem gabinete e sem porquê."""
    alvo = tmp_path / "estado" / cg.NOME_DO_ARQUIVO
    escrito = cg.gravar(censo_desta_bancada(), str(alvo))
    assert escrito == str(alvo)
    assert json.loads(alvo.read_text(encoding="utf-8"))["versao_do_censo"] == cg.VERSAO_DO_CENSO
    assert not (tmp_path / "estado" / f"{cg.NOME_DO_ARQUIVO}.novo").exists()
    # Regravar por cima não duplica nem corrompe.
    cg.gravar(censo_desta_bancada(dmidecode=""), str(alvo))
    assert json.loads(alvo.read_text(encoding="utf-8"))["de_onde_sei"] == cg.NAO_RESPONDEU


def test_o_caminho_padrao_le_o_home_na_chamada(tmp_path):
    """CANARIO-FS-01: constante de módulo apontaria para a pasta REAL dela.

    ``caminho_padrao`` resolve o ``HOME`` na hora, então a suíte nunca escreve na
    mesa dela — e o produto continua achando o arquivo certo.
    """
    caminho = cg.caminho_padrao(home=str(tmp_path))
    assert caminho.startswith(str(tmp_path))
    assert caminho.endswith("/.local/state/hefesto-dualsense4unix/gabinete.json")
    fonte = (cg.__file__ or "").replace(".pyc", ".py")
    with open(fonte, encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            if re.match(r"^[A-Z_]+\s*=.*(expanduser|Path\.home|os\.environ)", linha):
                pytest.fail(f"censo_do_gabinete.py:{numero} lê o HOME na importação")


def test_o_resumo_diz_o_que_nao_soube():
    """A linha que o install imprime não pode ficar bonita quando faltou dado."""
    assert "DIVERGEM" in cg.resumo(censo_desta_bancada())
    mudo = cg.resumo(censo_desta_bancada(dmidecode=""))
    assert "não respondeu" in mudo and "DIVERGEM" not in mudo


# ---------------------------------------------------------------------------
# A máquina de verdade — sem root, sem hardware, sem bancada
# ---------------------------------------------------------------------------


def test_a_maquina_de_verdade_responde_sem_root():
    """O censo roda contra o ``/sys`` desta máquina, como o install vai rodar.

    Afirma só INVARIANTES, nunca os números desta bancada: a suíte roda no CI e
    em qualquer PC. E não abre ``/dev``, não cria nó ``uinput`` e não chama
    subprocesso — custo medido de ``listar_entradas``: 6,87 ms.
    """
    censo = cg.ler_o_gabinete(dmidecode="")
    assert censo["faces"] == []
    assert censo["de_onde_sei"] == cg.NAO_RESPONDEU  # sem root não há tabela 8
    kernel = censo["kernel"]
    if kernel["soquetes"]["valor"] is None:
        pytest.skip("sem /sys/bus/usb nesta máquina — a ausência é resposta")
    assert kernel["buracos"]["valor"] <= kernel["soquetes"]["valor"]
    assert kernel["buracos_de_encaixe"]["valor"] <= kernel["buracos"]["valor"]
    assert kernel["reguas_concordam"] is not False, (
        "contar nós e ler maxchild discordaram nesta máquina — "
        f"{kernel['soquetes']['valor']} contra {kernel['maxchild']['valor']}"
    )


# ---------------------------------------------------------------------------
# A varredura que sustenta o teste do selo
# ---------------------------------------------------------------------------


def _todos_os_fatos(no, caminho=""):
    """Todo dicionário com ``valor`` na árvore, com o caminho até ele.

    Derivada do objeto, nunca digitada: campo novo sem selo reprova sozinho, que
    é a diferença entre um portão e uma lista que envelhece.
    """
    achados = []
    if isinstance(no, dict):
        if "valor" in no:
            assert "de_onde_sei" in no, f"{caminho}: valor sem de_onde_sei"
            return [(caminho, no)]
        for chave, filho in no.items():
            achados += _todos_os_fatos(filho, f"{caminho}.{chave}" if caminho else str(chave))
    elif isinstance(no, list):
        for indice, filho in enumerate(no):
            achados += _todos_os_fatos(filho, f"{caminho}[{indice}]")
    return achados


# ---------------------------------------------------------------------------
# MORDIDA 6 — a ABA publica a divergência, e o hub em comum vira conselho
# ---------------------------------------------------------------------------
#
# As duas moram aqui, e não num arquivo de tela, porque o que elas medem é a
# CHEGADA do censo à seção "A mesa": o `install.sh` grava o `gabinete.json` em
# toda instalação desde 25/08/2026 e, até 26/08, nenhuma linha de `app/` o
# abria. A régua que faltava não era do censo — era do consumidor.
#
# Nenhuma delas monta widget: as duas funções sob medição são de MÓDULO e puras,
# que é o mesmo desenho de `_onde_esta_o_adaptador` (a régua de
# `test_a_porta_dela_chega_na_frase.py`). Sem GTK, sem display, sem `/sys`.

#: A controladora xHCI onde mora o hub desta bancada, e a OUTRA. Os dois valores
#: são a forma real de um `controlador_pci` — o caminho PCI do `/sys` —, e o que
#: importa aqui é só que são diferentes.
_PCI_DO_HUB = "0000:0c:00.3"
_PCI_DA_PLACA = "0000:03:00.0"


def _bancada_dos_tres_adaptadores():
    """O arranjo medido em 22/08/2026: três adaptadores, DOIS pais, um hub.

    ``3-3.1.1`` e ``3-3.1.2`` penduram no hub ``3-3.1``; ``3-3.2`` pendura direto
    no ``3-3``. É por isso que comparar o pai responde "não estão juntos", e
    responde errado — os três têm o ``3-3`` acima.
    """
    def _hub(no, pai, pci):
        return Aparelho(
            no=no, nome_do_kernel=no.rsplit("/", 1)[-1], pai=pai,
            controlador_pci=pci, e_hub=True,
        )

    censo = Censo(
        aparelhos=(
            Aparelho(no="/sys/usb1", nome_do_kernel="usb1",
                     controlador_pci=_PCI_DA_PLACA, e_hub=True, e_raiz=True),
            Aparelho(no="/sys/usb3", nome_do_kernel="usb3",
                     controlador_pci=_PCI_DO_HUB, e_hub=True, e_raiz=True),
            _hub("/sys/3-3", "/sys/usb3", _PCI_DO_HUB),
            _hub("/sys/3-3.1", "/sys/3-3", _PCI_DO_HUB),
            Aparelho(no="/sys/3-3.1.1", nome_do_kernel="3-3.1.1", pai="/sys/3-3.1",
                     controlador_pci=_PCI_DO_HUB, atras_de_hub=True),
            Aparelho(no="/sys/3-3.1.2", nome_do_kernel="3-3.1.2", pai="/sys/3-3.1",
                     controlador_pci=_PCI_DO_HUB, atras_de_hub=True),
            Aparelho(no="/sys/3-3.2", nome_do_kernel="3-3.2", pai="/sys/3-3",
                     controlador_pci=_PCI_DO_HUB, atras_de_hub=True),
        )
    )
    mesa = Mesa(
        adaptadores=(
            Adaptador(interface="hci0", no="/sys/3-3.1.1", busnum=3, devpath="3.1.1",
                      atras_de_hub=True),
            Adaptador(interface="hci1", no="/sys/3-3.1.2", busnum=3, devpath="3.1.2",
                      atras_de_hub=True),
            Adaptador(interface="hci2", no="/sys/3-3.2", busnum=3, devpath="3.2",
                      atras_de_hub=True),
        )
    )
    return mesa, censo


def _entradas(hub, quantas, *, encaixe="hotplug"):
    """``quantas`` entradas VAZIAS neste hub — nenhum ``peer``, um nó por buraco."""
    return tuple(
        _no(hub, numero, encaixe=encaixe) for numero in range(1, quantas + 1)
    )


def test_a_aba_mostra_a_divergencia_em_vez_de_escolher():
    """**A MORDIDA.** BIOS 5, barramento 8: a seção publica AS DUAS e a pergunta.

    É o §7.4 chegando à tela. O censo já grava as duas contagens e a pergunta
    desde 25/08/2026; o que faltava era alguém publicá-las.

    ARRANCANDO a cura — fazendo ``_linhas_do_gabinete`` eleger uma fonte, que é
    o que qualquer "simplificação" faria — este teste reprova imprimindo o
    número que sumiu da tela.
    """
    contagens = cg.declarar_divergencia(firmware=5, soquetes=None, buracos=8)
    assert contagens["divergem"] is True
    linhas = secao_mesa._linhas_do_gabinete({"contagens": contagens})
    juntas = " | ".join(linhas)
    # As contagens têm de estar na tela POR SI, e não só de carona dentro da
    # pergunta. Medido ao arrancar a cura em 26/08/2026: com a seção elegendo o
    # firmware, o "8" continuava aparecendo — dentro do texto da pergunta — e a
    # régua passava com o defeito de pé. Uma régua que só sabe passar não é
    # régua, e esta linha é a diferença.
    contadas = [linha for linha in linhas if linha != contagens["pergunta"]]
    for numero in ("5", "8"):
        assert any(numero in linha for linha in contadas), (
            f"a seção deixou de publicar a contagem {numero}: {juntas!r}. "
            "Com as fontes em briga a aba mostra AS DUAS — escolher uma "
            "desenha um gabinete que ninguém tem"
        )
    assert contagens["pergunta"] in linhas, (
        "a pergunta sumiu da tela. Divergência declarada e escondida é a "
        f"mesma coisa que divergência não declarada: {juntas!r}"
    )


def test_sem_gabinete_gravado_a_secao_fala_como_antes():
    """A outra metade da régua: ela precisa saber ficar CALADA.

    Primeira instalação, ou install anterior a 25/08/2026: não há
    ``gabinete.json``, e a seção não pode inventar contagem nenhuma. Um gabinete
    de mentira é pior que nenhum, porque ela confia nele.
    """
    assert secao_mesa._linhas_do_gabinete({}) == ()
    assert secao_mesa._linhas_do_gabinete({"contagens": "lixo de outra versão"}) == ()


def test_a_resposta_dela_entra_na_tela_e_cala_a_pergunta():
    """Respondido uma vez, o produto para de perguntar — e mostra o que ela disse."""
    censo = censo_desta_bancada()
    guardado = cg.preservar_o_que_ela_disse(
        censo, _censo_com_a_palavra_dela(), dict(PLACA_DESTA_BANCADA)
    )
    linhas = secao_mesa._linhas_do_gabinete(guardado)
    assert any("8" in linha for linha in linhas)
    assert cg.pergunta_pendente(guardado) == ""
    assert not any(linha.endswith("?") for linha in linhas), linhas


def test_o_hub_em_comum_so_vira_conselho_com_buraco_livre_em_outra_pci():
    """**A MORDIDA.** O fato nasce sempre; o conselho, só com para onde mandar.

    Três adaptadores no mesmo hub é o arranjo que o próprio
    ``GUIA-RADIO-DA-SALA.md`` manda comprar — a contra-regra R3 da
    ``ORDEM-DE-SERVICO-01``. Sem buraco livre em OUTRA controladora não há
    conselho a dar, e dar um seria mandar a pessoa se ajoelhar atrás do gabinete
    para nada.

    ARRANCANDO ``hub_em_comum`` — trocando-o por uma comparação de pai — os três
    param de aparecer juntos (eles têm dois pais, ``3-3.1`` e ``3-3``), o fato
    some, e este teste reprova nas duas metades.
    """
    mesa, censo = _bancada_dos_tres_adaptadores()

    # (a) o hub está lotado e a placa não tem buraco livre: fato, e silêncio.
    fato, por_que, conselho = secao_mesa._frase_do_hub_em_comum(
        mesa, censo, _entradas("3-3", 2)
    )
    assert "3" in fato, (
        f"o fato do hub em comum não nasceu: {fato!r}. Comparar o pai diria "
        "que os três não estão juntos, e diria errado"
    )
    assert por_que
    assert conselho == "", (
        "nasceu conselho sem para onde mandar. Mudar de buraco dentro do mesmo "
        f"hub não muda o caminho que ele divide: {conselho!r}"
    )

    # (b) a mesma mesa com buracos livres na OUTRA controladora: o conselho vem.
    _, _, com_destino = secao_mesa._frase_do_hub_em_comum(
        mesa, censo, _entradas("3-3", 2) + _entradas("usb1", 2)
    )
    assert "2" in com_destino, (
        f"o conselho não nasceu com dois buracos livres em {_PCI_DA_PLACA}: "
        f"{com_destino!r}"
    )

    # E ele NUNCA acusa um adaptador de atrapalhar outro (a contra-regra R3).
    for frase in (fato, por_que, com_destino):
        assert "atrapalh" not in frase.lower(), frase


def test_o_conselho_do_hub_ignora_o_buraco_que_a_mao_nao_alcanca():
    """``connect_type`` que não é ``hotplug`` é conector soldado dentro da caixa.

    Mandar alguém encaixar um cabo ali é pior que não mandar nada — e é a régua
    de ``portas_do_barramento.livres``, que esta seção NÃO reimplementa.
    """
    mesa, censo = _bancada_dos_tres_adaptadores()
    _, _, conselho = secao_mesa._frase_do_hub_em_comum(
        mesa, censo, _entradas("usb1", 3, encaixe="unknown")
    )
    assert conselho == ""


def test_um_adaptador_sozinho_nao_tem_hub_em_comum():
    """Menos de dois não tem "em comum" nenhum — e a linha some inteira."""
    mesa, censo = _bancada_dos_tres_adaptadores()
    sozinho = Mesa(adaptadores=mesa.adaptadores[:1])
    assert secao_mesa._frase_do_hub_em_comum(
        sozinho, censo, _entradas("usb1", 4)
    ) == ("", "", "")
