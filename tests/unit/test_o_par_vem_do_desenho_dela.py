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

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.config`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.mapa_das_portas import irmas_de
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

PEER_DA_BANCADA: dict[str, str] = {
    "usb1-port5": "usb2-port1",
    "usb2-port1": "usb1-port5",
    "usb1-port6": "usb2-port2",
    "usb2-port2": "usb1-port6",
    "usb1-port7": "usb2-port3",
    "usb2-port3": "usb1-port7",
}


def test_a_irma_nao_aceita_leitura_de_sistema_nenhuma() -> None:
    """``irmas_de`` recebe o MAPA e mais nada — a assinatura é a régua."""
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
    """Os dois nós do mesmo buraco numa entrada só: o ``peer`` não tem o que dizer."""
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
    """O mapa mal calibrado — e a resposta certa é NÃO INVENTAR par nenhum."""
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
    """Mapa vazio, resposta vazia — e é ela que a tela tem de traduzir."""
    assert irmas_de(MapaDaMesa()) == {}


def test_a_tela_diz_o_que_deixa_de_julgar_sem_o_desenho() -> None:
    """A frase de quem nunca desenhou nomeia o juízo que o produto NÃO faz."""
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
