"""O esquema aprende o fato físico — ``perto``, ``alto`` e a IRMÃ de cada entrada.

CONEXÕES · MAPA 2D 01 / G3 (25/08/2026).

O DEFEITO, EM UMA FRASE
------------------------

O motor do arranjo (``integrations/arranjo_da_mesa``) lê ``Face.perto``,
``Face.alto`` e ``Entrada.par`` para decidir se um aparelho fica bem numa
entrada — e **nenhum dos três tinha fonte**. O esquema declarado
(``utils/maquina.MapaDaMesa``) não tinha onde guardá-los, então toda face nascia
``perto=False``/``alto=False`` e toda entrada nascia sem par. As três penalidades
de vizinho rádio da tabela de notas — **-30** no teclado, **-45** no Bluetooth,
**-40** no mouse — nunca podiam disparar, e cada quadrado da tela diria *"aqui
fica bem"* onde deveria dizer *"aqui não"*.

**Juízo otimista demais é pior que juízo nenhum**: um mapa que só sabe elogiar
não é um mapa, é um enfeite, e quem seguir o conselho dele põe dois receptores
de 2,4 GHz encostados.

O QUE ESTA BATERIA MEDE, E O QUE ELA NÃO MEDE
----------------------------------------------

Mede o ESQUEMA e a JUNÇÃO: que o fato físico tem onde ficar, que ele sobrevive
ao disco, e que a irmã responde **com o gabinete inteiro vazio** — que é o caso
que nenhuma leitura de aparelho alcança.

**Não mede o motor.** ``arranjo_da_mesa`` é de outra frente e não foi tocado:
esta bateria prova que o dado existe e é buscável, não que quem o consome já o
busca. Quem fecha esse último palmo é a G5 (a janela do desenho que julga).

A BANCADA
----------

``tests/unit/test_mapa_a_bancada_de_mentira`` — a leitura de 25/08 às 02h30.
Nenhum caminho de ``/sys`` desta máquina é tocado; os nós de entrada abaixo são
os NOMES medidos naquela leitura, montados à mão.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada
from hefesto_dualsense4unix.integrations.mapa_das_portas import (
    SELO_DECLARADO,
    SELO_INFERIDO,
    irmas_de,
    vizinhas_de_verdade,
)
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    carregar_maquina,
    gravar_maquina,
)
from tests.unit.test_mapa_a_bancada_de_mentira import bancada_de_agora, mapa_dela

#: Os pares que o mockup dela declara à mão, entrada por entrada
#: (``2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html``:341-350). É a
#: resposta CERTA, escrita por ela antes de existir código, e é contra ela que a
#: derivação se mede.
PARES_DO_MOCKUP: dict[str, str] = {
    "1": "2", "2": "1",
    "3": "4", "4": "3",
    "5": "6", "6": "5",
    "7": "8", "8": "7",
    "9": "10", "10": "9",
    "11": "12", "12": "11",
    "13": "14", "14": "13",
}

#: MEDIDO em 25/08/2026 nesta bancada, ``readlink`` em cada ``*/peer`` dos 38
#: nós de entrada. TODO ``peer`` atravessa dois hubs-raiz: ele amarra o lado 2.0
#: e o lado 3.x de UM MESMO BURACO, e nunca dois buracos vizinhos.
PEER_DA_BANCADA: dict[str, str] = {
    "usb1-port5": "usb2-port1",
    "usb2-port1": "usb1-port5",
    "usb1-port6": "usb2-port2",
    "usb2-port2": "usb1-port6",
    "usb1-port7": "usb2-port3",
    "usb2-port3": "usb1-port7",
}


def _leitura(peer: dict[str, str]) -> tuple[NoDeEntrada, ...]:
    """Nós de entrada com o ``peer`` que se quer medir, e nada mais.

    ``hub`` e ``numero`` são preenchidos porque o dataclass os exige; nenhuma
    função sob teste os lê, e enchê-los de valor plausível seria dar ao teste
    uma aparência de medição que ele não tem.
    """
    return tuple(
        NoDeEntrada(no=no, caminho_sysfs="", hub="", numero=0, par=par)
        for no, par in sorted(peer.items())
    )


# --- 1. A face guarda o que só ela sabe --------------------------------------


def test_a_face_guarda_perto_e_alto() -> None:
    """``perto`` e ``alto`` entram no esquema, e são fato DELA.

    O ``/sys`` desta bancada responde ``panel=right``,
    ``horizontal_position=left`` e ``vertical_position=lower`` — idênticos —
    para ``usb1-port3`` e ``usb1-port6``, que ficam em faces DIFERENTES do
    metal. Nenhuma leitura sabe qual face está virada para a pessoa.

    Mordida: tirei os dois campos de ``FaceDeclarada``. Com ``extra="forbid"``,
    a validação passa a levantar e o teste reprova dizendo que a face não tem
    onde guardar o fato — que é o defeito inteiro, em uma linha.
    """
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [
                {"nome": "Frente", "portas": ["1", "2"], "perto": True},
                {"nome": "Traseira", "portas": ["3", "4"]},
                {"nome": "Hub", "portas": ["9", "10"], "alto": True},
            ]
        }
    )
    frente, traseira, hub = mapa.faces
    assert (frente.perto, frente.alto) == (True, False)
    assert (traseira.perto, traseira.alto) == (False, False), (
        "face que ela não marcou tem de nascer sem bônus nenhum"
    )
    assert (hub.perto, hub.alto) == (False, True)


def test_o_fato_fisico_sobrevive_ao_disco() -> None:
    """Ida e volta pelo ``maquina.json``: o que ela marcou continua marcado.

    Campo que não sobrevive à gravação é campo que não existe — a pessoa
    declara, fecha a janela, e o motor volta a julgar com o mapa de ontem.
    """
    assert gravar_maquina(
        {
            "mapa": {
                "faces": [
                    {"nome": "Frente", "portas": ["1", "2"], "perto": True},
                    {"nome": "Hub", "portas": ["9"], "alto": True},
                ],
                "portas": {"9": {"nos": ["usb1-port5", "usb2-port1"]}},
            }
        }
    )
    de_volta = carregar_maquina().mapa
    assert [(f.nome, f.perto, f.alto) for f in de_volta.faces] == [
        ("Frente", True, False),
        ("Hub", False, True),
    ]
    assert de_volta.portas["9"].nos == ["usb1-port5", "usb2-port1"]


# --- 2. `nos` é o que alcança a entrada VAZIA --------------------------------


def test_a_entrada_vazia_existe_no_esquema_sem_caminho_nenhum() -> None:
    """Uma entrada sem aparelho tem lugar no mapa — pelo NÓ, não pelo caminho.

    ``caminho`` nomeia o aparelho (``3-1.2``) e some do ``/sys`` quando ele sai;
    ``nos`` nomeia o buraco (``usb1-port5``), e MEDIDO em 25/08 os 38 nós desta
    bancada respondem ``state`` com e sem aparelho. Sem este campo, "a entrada
    7" só existe enquanto houver algo nela — que é como quatro dos cinco
    aparelhos que ela moveu em 24/08 sumiram do mapa.
    """
    mapa = MapaDaMesa.model_validate(
        {"portas": {"7": {"nos": ["usb1-port7", "usb2-port3"]}}}
    )
    vazia = mapa.portas["7"]
    assert vazia.caminho is None
    assert vazia.nos == ["usb1-port7", "usb2-port3"]


@pytest.mark.parametrize(
    "nos",
    [
        pytest.param(["porta5"], id="nome-que-nao-e-de-no"),
        pytest.param(["3-1.2"], id="caminho-de-aparelho-no-lugar-do-no"),
        pytest.param(["usb1-port5", "usb1-port5"], id="no-repetido"),
        pytest.param([f"usb1-port{n}" for n in range(9)], id="acima-do-teto"),
    ],
)
def test_o_no_torto_e_recusado(nos: list[str]) -> None:
    """A régua sabe RECUSAR — chave sem validador herda lixo.

    O caso ``3-1.2`` é o que mais engana: é um nome de kernel legítimo, só que
    de APARELHO. Aceitá-lo faria o mapa guardar um endereço que some quando o
    aparelho sai, exatamente o defeito que ``nos`` existe para fechar.
    """
    with pytest.raises(ValidationError):
        MapaDaMesa.model_validate({"portas": {"7": {"nos": nos}}})


# --- 3. A irmã de cada entrada, inclusive da vazia ---------------------------


def test_a_irma_bate_com_o_desenho_dela_entrada_por_entrada() -> None:
    """As catorze irmãs saem iguais às que ela escreveu à mão no mockup.

    Mordida: arranquei o ``_pelo_desenho`` (deixei só a fonte do ``peer``, que
    é a que a decisão nomeia). A resposta veio VAZIA e o teste reprovou
    imprimindo as catorze entradas que perderam a irmã — que é o estado em que
    as penalidades de vizinho rádio nunca disparam.
    """
    achadas = {n: irma.numero for n, irma in irmas_de(mapa_dela()).items()}
    assert achadas == PARES_DO_MOCKUP, (
        "a irmã derivada divergiu do desenho dela: "
        f"faltam {sorted(set(PARES_DO_MOCKUP) - set(achadas))}, "
        f"sobram {sorted(set(achadas) - set(PARES_DO_MOCKUP))}"
    )


def test_a_irma_responde_com_o_gabinete_inteiro_vazio() -> None:
    """Nenhum aparelho na mesa, e as catorze irmãs continuam de pé.

    É a propriedade que decide a tarefa: ``vizinhas_de_verdade`` responde pelos
    pares OCUPADOS AGORA e devolve nada numa mesa vazia — correto para a
    pergunta dela e inútil para esta. A irmã existe no metal esteja o buraco
    cheio ou vazio, e o motor precisa dela para dizer "aqui não" ANTES de a
    pessoa encaixar qualquer coisa.
    """
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [
                {"nome": "Frente", "portas": ["1", "2"], "perto": True},
                {"nome": "Traseira", "portas": ["3", "4", "5", "6", "7", "8"]},
            ]
        }
    )
    assert vizinhas_de_verdade(mapa, bancada_de_agora().censo()) == ()
    irmas = irmas_de(mapa)
    assert {n: irma.numero for n, irma in irmas.items()} == {
        "1": "2", "2": "1", "3": "4", "4": "3", "5": "6", "6": "5", "7": "8",
        "8": "7",
    }
    assert {irma.de_onde_sei for irma in irmas.values()} == {SELO_DECLARADO}


def test_a_fileira_impar_deixa_a_ultima_sem_irma_e_a_esticada_de_fora() -> None:
    """A ``15`` não tem irmã, e a ``15a`` também não — as duas por motivos.

    A fileira do hub tem SETE entradas: a última sobra, e inventar uma irmã
    para ela seria colar no metal duas coisas que não estão coladas. A ``15a``
    nasce de um extensor de um metro e não está na fileira — o cabo a põe longe
    de todo mundo, que é justamente por que o Bluetooth ganha +25 nela.
    """
    irmas = irmas_de(mapa_dela())
    assert "15" not in irmas
    assert "15a" not in irmas


def test_a_irma_nao_e_a_vizinha_da_fileira() -> None:
    """Na fileira do hub, a ``9`` é irmã da ``10`` — e NÃO da ``11``.

    Irmã é a outra tomada do mesmo conjunto de metal; vizinha é a próxima da
    fileira. As duas relações existem, e só a primeira é a que o motor pesa em
    ``Entrada.par``. Derivar irmã de ``pairwise`` (que é como
    ``vizinhas_de_verdade`` acha vizinha) daria ``10`` irmã de ``9`` e de
    ``11`` ao mesmo tempo, e ``Entrada.par`` é um valor só.
    """
    irmas = irmas_de(mapa_dela())
    assert irmas["9"].numero == "10"
    assert irmas["10"].numero == "9", "a relação tem de ser recíproca"
    assert irmas["11"].numero == "12"


# --- 4. As duas fontes, e o selo de cada uma ---------------------------------


def test_o_peer_da_bancada_nao_amarra_duas_entradas_e_o_desenho_responde() -> None:
    """MEDIDO: o ``peer`` desta placa não sabe dizer quem está colado em quem.

    Nos 38 nós desta bancada, todo ``peer`` atravessa dois hubs-raiz
    (``usb1-port5`` ↔ ``usb2-port1``): ele amarra os DOIS NÓS DE UM BURACO — o
    lado 2.0 e o lado 3.x — e nunca dois buracos vizinhos. Num mapa declarado
    por buraco, que é o que ``PortaDeclarada.nos`` existe para permitir, os dois
    nós caem na MESMA entrada e a fonte do ``peer`` não responde por ninguém.

    Isto não é um defeito da implementação: é a medição contradizendo a
    premissa da ``D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS``, e está escrita como teste
    para que a próxima pessoa não a redescubra do zero. O ``peer`` continua no
    código porque a decisão é dela e porque ele pega o mapa mal calibrado do
    teste seguinte.
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
    irmas = irmas_de(mapa, _leitura(PEER_DA_BANCADA))
    assert {n: irma.numero for n, irma in irmas.items()} == {"5": "6", "6": "5"}
    assert {irma.de_onde_sei for irma in irmas.values()} == {SELO_DECLARADO}, (
        "o peer desta placa não amarra duas entradas: quem respondeu foi o "
        "desenho dela, e o selo tem de dizer isso"
    )


def test_o_peer_vence_quando_ele_fala_e_entra_como_inferencia() -> None:
    """O mapa que declarou os dois lados do mesmo buraco como duas entradas.

    É um erro de calibração, e um que vale mostrar em vez de esconder: a fonte
    do ``peer`` responde, o desenho perde, e o selo diz ``inferido`` — *"lido do
    sistema, nunca como fato dela"* (``D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS``).

    Mordida: tirei o ``achadas.setdefault`` do ``irmas_de`` e deixei o desenho
    sobrescrever. A entrada ``5`` passou a responder ``6`` com selo
    ``declarado``, e o teste reprovou — a procedência tinha virado enfeite, que
    é exatamente o que o selo existe para não ser.
    """
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [{"nome": "Traseira", "portas": ["5", "6"]}],
            "portas": {
                "5": {"nos": ["usb1-port5"]},
                "6": {"nos": ["usb2-port1"]},
            },
        }
    )
    irmas = irmas_de(mapa, _leitura(PEER_DA_BANCADA))
    assert irmas["5"].numero == "6" and irmas["5"].de_onde_sei == SELO_INFERIDO
    assert irmas["6"].numero == "5" and irmas["6"].de_onde_sei == SELO_INFERIDO


def test_peer_que_aponta_para_fora_do_mapa_nao_inventa_irma() -> None:
    """Nó cujo par não está declarado não vira irmã de ninguém.

    O outro lado pode ser um cabeçote interno que ela nunca numerou. Inventar
    uma irmã ali poria uma penalidade de -45 num vizinho que não existe.
    """
    mapa = MapaDaMesa.model_validate(
        {"portas": {"5": {"nos": ["usb1-port5"]}}}
    )
    assert irmas_de(mapa, _leitura(PEER_DA_BANCADA)) == {}


def test_o_mapa_de_ontem_continua_valendo() -> None:
    """Campo novo sem bump de versão: o mapa dela, sem ``perto`` nem ``nos``.

    ``MAQUINA_SCHEMA_VERSION`` não subiu, e não há passo de migração a
    escrever. Um arquivo declarado antes de 25/08 tem de continuar abrindo, com
    os campos novos no ``default_factory`` — o contrário faria toda máquina que
    já declarou perder a mesa na primeira leitura.
    """
    antigo = mapa_dela()
    assert all(not f.perto and not f.alto for f in antigo.faces)
    assert all(p.nos == [] for p in antigo.portas.values())
    assert irmas_de(antigo)["1"].numero == "2", (
        "o desenho dela responde sem uma linha de campo novo declarada"
    )
