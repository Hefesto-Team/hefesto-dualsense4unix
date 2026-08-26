"""O par de cada entrada vem do DESENHO DELA — e o ``peer`` do ``/sys`` não volta.

CONEXÕES · MAPA 2D 01 / frente PAR (25/08/2026). Decisão dela do mesmo dia, que
reverte a de mais cedo (``D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS``).

A MEDIÇÃO QUE DERRUBOU A PREMISSA
----------------------------------

O ``peer`` foi oferecido a ela como *"o que responde também na entrada vazia, o
caso que nenhuma outra leitura alcança"*. ``readlink`` em cada ``*/peer`` dos 38
nós de entrada desta bancada, em 25/08/2026::

    usb1-port5  <-> usb2-port1      mesmo buraco, lados 2.0 e 3.x
    usb3-port1  <-> usb4-port1      idem
    3-1-port4   <-> 4-1-port4       idem

**Todo ``peer`` atravessa dois hubs-raiz.** Ele amarra os DOIS LADOS DE UM MESMO
BURACO — é para isso que o kernel o publica — e nunca dois buracos vizinhos.
``arranjo_da_mesa.Entrada.par`` é outra coisa: duas tomadas empilhadas num
plástico só, **cada uma com o seu aparelho ao mesmo tempo** (``plano[porta.par]``
devolve um aparelho DIFERENTE; se fosse o mesmo buraco nunca haveria dois).

Na mesa dela o ``peer`` responde por **zero** entradas; o desenho, pelas
**catorze**. A fonte certa já estava no esquema — ``FaceDeclarada.portas``, de
duas em duas —, responde com o gabinete inteiro vazio, e é **fato dela** em vez
de inferência.

O QUE ESTA BATERIA PRENDE
--------------------------

1. que ``irmas_de`` não aceite leitura de sistema nenhuma — assinatura fechada;
2. que os dois mapas em que o ``peer`` "falaria" continuem respondendo pelo
   desenho, e nunca pelo lado 2.0/3.x do mesmo buraco;
3. **que a consequência chegue à tela**: sem o desenho não há ``par``, logo não
   há as penalidades de vizinho rádio, e o produto tem de DIZER isso. Juízo
   otimista silencioso é pior que juízo nenhum.

A bancada não tem DualSense conectado, e nada aqui precisa de um: as três coisas
acima são função pura e uma constante de texto.
"""
from __future__ import annotations

import inspect

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.mapa_das_portas import irmas_de
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

#: MEDIDO em 25/08/2026 nesta bancada, ``readlink`` em cada ``*/peer`` dos 38 nós
#: de entrada. Os pares abaixo são a leitura real, e é contra ela que se mede.
PEER_DA_BANCADA: dict[str, str] = {
    "usb1-port5": "usb2-port1",
    "usb2-port1": "usb1-port5",
    "usb1-port6": "usb2-port2",
    "usb2-port2": "usb1-port6",
    "usb1-port7": "usb2-port3",
    "usb2-port3": "usb1-port7",
}


def test_a_irma_nao_aceita_leitura_de_sistema_nenhuma() -> None:
    """``irmas_de`` recebe o MAPA e mais nada — a assinatura é a régua.

    Mordida: devolvi o parâmetro ``entradas`` a ``irmas_de``. O teste reprova
    dizendo qual parâmetro entrou, porque é por ele que uma leitura de sistema
    volta a se misturar com o fato dela — e a mistura foi o defeito: as duas
    fontes respondem perguntas diferentes, e a do ``peer`` respondia a errada.
    """
    parametros = list(inspect.signature(irmas_de).parameters)
    assert parametros == ["mapa"], (
        "a irmã tem UMA fonte, e ela é o desenho dela. Parâmetro a mais na "
        f"assinatura é porta de entrada para leitura de sistema: {parametros}"
    )
    assert not hasattr(mapa_das_portas, "SELO_INFERIDO"), (
        "o selo de inferência voltou. Com uma fonte só, e sendo ela fato dela, "
        "não há segunda procedência de que desconfiar — o selo seria enfeite"
    )


def test_o_mapa_declarado_por_buraco_responde_pelo_desenho() -> None:
    """Os dois nós do mesmo buraco numa entrada só: o ``peer`` não tem o que dizer.

    É o mapa que a calibração produz (``PortaDeclarada.nos`` existe para isso).
    As irmãs saem ``5``↔``6`` — que é a fileira do metal —, e não ``5``↔``5``,
    que é o que o ``peer`` amarraria se alguém o consultasse aqui.
    """
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [{"nome": "Traseira", "portas": ["5", "6", "7"]}],
            "portas": {
                "5": {"nos": ["usb1-port5", "usb2-port1"]},
                "6": {"nos": ["usb1-port6", "usb2-port2"]},
                "7": {"nos": ["usb1-port7", "usb2-port3"]},
            },
        }
    )
    assert irmas_de(mapa) == {"5": "6", "6": "5"}, (
        "a fileira do metal é 5-6, e a 7 sobra por ser ímpar"
    )


def test_o_lado_2_0_e_o_lado_3_x_declarados_separados_nao_viram_irmas() -> None:
    """O mapa mal calibrado — e a resposta certa é NÃO INVENTAR par nenhum.

    Aqui ``5`` e ``6`` são os dois lados do MESMO buraco, declarados como duas
    entradas. O ``peer`` da bancada os amarra, e era esse o único caso em que a
    fonte antiga respondia: ela chamaria de "colados no metal" dois nós que são
    o mesmo furo, e o motor cobraria -45 de um vizinho que não existe.

    MORDIDA: fiz :func:`irmas_de` cair para ``mapa.portas`` quando não há face
    desenhada — que é o atalho tentador, porque as duas entradas estão ali. As
    duas viraram irmãs e o teste reprovou, e o par que apareceu é exatamente o
    que o ``peer`` amarraria: os dois nós do MESMO furo virando "colados no
    metal".

    A régua que guarda o ``peer`` em si é a da assinatura, acima: com
    ``entradas`` de volta na função ela reprova, e sem ela nenhuma leitura de
    sistema tem por onde entrar.
    """
    so_os_nos = MapaDaMesa.model_validate(
        {
            "portas": {
                "5": {"nos": ["usb1-port5"]},
                "6": {"nos": ["usb2-port1"]},
            }
        }
    )
    assert irmas_de(so_os_nos) == {}, (
        "sem face desenhada não há fileira, e o peer amarraria 5 a 6 — que são "
        f"o mesmo furo, não dois vizinhos. Medido: {PEER_DA_BANCADA['usb1-port5']}"
    )


def test_o_gabinete_nao_desenhado_devolve_silencio() -> None:
    """Mapa vazio, resposta vazia — e é ela que a tela tem de traduzir.

    É o estado de quem nunca desenhou, o mais comum lá fora. O motor fica sem
    ``Entrada.par``, e as três penalidades de vizinho rádio (-30 no teclado, -45
    no Bluetooth, -40 no mouse) não disparam.
    """
    assert irmas_de(MapaDaMesa()) == {}


def test_a_tela_diz_o_que_deixa_de_julgar_sem_o_desenho() -> None:
    """A frase de quem nunca desenhou nomeia o juízo que o produto NÃO faz.

    Esta é a metade da decisão que não pode faltar: sem o desenho não há par,
    logo não há aviso de vizinho rádio — e calar sobre isso deixa a tela
    publicando juízo otimista silencioso, que é pior que juízo nenhum e é o
    defeito de forma que esta casa persegue.

    A frase tem DUAS metades, e as duas são medidas: dizer que o Hefesto ignora
    quais entradas ficam coladas, **e** recusar a leitura otimista do silêncio.
    Uma reescrita de encurtamento derruba a segunda antes da primeira.

    DUAS MORDIDAS, as duas exercidas em 25/08/2026:

    * devolvi ao ``_SEM_MAPA`` o texto de antes desta frente ("...em vez do
      número da sua entrada."). A primeira asserção reprovou, imprimindo a
      frase inteira — quem lê a reprovação lê o que a tela mostra, não o nome de
      uma variável;
    * cortei só a última oração ("Não é que esteja tudo bem: ele não sabe"),
      deixando o resto. A segunda asserção reprovou. **A primeira redação desta
      régua não pegava esse corte** — ela procurava "não sabe", que continuava
      vivo dentro de "e não sabe quais entradas ficam coladas". Régua que
      confunde a palavra com o ato: trocada pelo termo que só existe na oração
      que garante o resto.

    O texto é PROVISÓRIO — decisão dela: a palavra final sobre tela é dela
    (``PROVA-DE-TELA-01``). Se ela reescrever, o que tem de sobreviver são as
    duas metades; os termos abaixo são só como esta régua as alcança hoje.
    """
    frase = secao_mesa._SEM_MAPA
    assert "coladas" in frase, (
        "a frase de quem nunca desenhou não diz que o Hefesto ignora quais "
        f"entradas ficam coladas — logo esconde o aviso que ele deixa de dar: {frase!r}"
    )
    assert "tudo bem" in frase, (
        "a frase não recusa a leitura otimista: sem dizer que NÃO É QUE ESTEJA "
        "TUDO BEM, o silêncio sobre a vizinhança é lido como aprovação — o "
        f"juízo otimista que esta frente existe para fechar: {frase!r}"
    )
