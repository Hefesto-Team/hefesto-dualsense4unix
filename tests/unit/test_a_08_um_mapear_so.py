"""Um mapear só — A-08-UM-MAPEAR-SO-01 (25/09/2026).

O pedido dela: *«mapear entradas e mapear entrada a entrada. […] Dava pra ser
um botão só né?»* e *«Use um controle do dualsense (o mesmo), vá de porta em
porta conectando ele, carrega a informação que medimos, aí ele salva,
adiciona um nome e adiciona o posicionamento»*. <!-- noqa-acento: citação literal dela -->

O QUE ESTA RÉGUA COBRA, no ``/sys`` de mentira da ENTRADA-A-ENTRADA-02 (o
``Gabinete``, lido pelos leitores DE VERDADE — ``ler_o_barramento`` e
``listar_entradas``), com uma porta de cada tipo:

* ``1-5`` — do computador, só USB 2.0;
* ``1-1`` — do computador, USB 3.0 (os dois nós do buraco, pelo ``peer``);
* ``3-4.2`` — atrás do hub de dois chips (``3-4``/``4-4``), 3.0;
* ``3-4.1`` — o dongle Bluetooth, com cinco -71 no log;
* ``3-2`` — o Bluetooth da placa, num conector interno (``hardwired``).

1. **o mesmo controle de porta em porta**: cada porta que ele mostra chega com
   o medido, e gravar nome e lugar dá número, face e amarra numa gravação só;
2. **a leitura pelo nome único** (``ler_o_mapa``): o declarado e o medido de
   cada porta, as ocupadas sem número incluídas;
3. **a revisita é o mesmo fluxo e não apaga**: renomear e reposicionar trocam
   SÓ o que ela trocou — a MORDIDA da sprint;
4. **um gravador só**: toda escrita do dono passa por ``_gravar_no_mapa`` — a
   outra MORDIDA da sprint;
5. **o lugar é universal**, e a face que ela já tinha continua aceita.

AS MORDIDAS (arranque a cura, veja reprovar, devolva):

* :func:`test_a_revisita_so_troca_o_que_ela_trocou` — faça o ramo da revisita
  de ``_gravar_a_porta`` (o hub desligado) começar as faces de ``[]`` e as
  outras faces somem do disco;
* :func:`test_um_gravador_so_no_dono` — ponha um ``self._gravar({...})`` direto
  em qualquer método, ou um ``Path(…).write_text`` cru, e ela reprova;
* :func:`test_o_controle_que_ja_estava_no_cabo_nao_e_a_porta_da_vez` — troque
  o ``nos not in self._antes`` de ``MapearAsPortas.olhar`` por ``agora[:1]`` e a
  porta da vez vira o controle que já estava no cabo;
* :func:`test_a_revisita_so_troca_o_que_ela_trocou` (a segunda) — troque o
  ``nome is not None`` de ``_gravar_as_portas`` por nada e reposicionar apaga
  o nome;
* :func:`test_cada_porta_diz_o_que_o_metal_e` — troque o ``hardwired`` do
  Bluetooth da placa por ``hotplug`` e o nativo vira dongle;
* :func:`test_o_mesmo_controle_de_porta_em_porta_mapeia_cada_uma` — parta a
  gravação de ``_gravar_as_portas`` em duas (o mapa numa, os lugares noutra) e
  o gesto deixa de ser UMA gravação;
* :func:`test_o_encaixe_que_o_kernel_nao_sabe_nao_vira_dongle` — devolva o
  ``else BLUETOOTH_DONGLE`` de antes (todo encaixe que não é ``hardwired`` vira
  dongle) e o rádio numa entrada ``unknown`` vira dongle;
* :func:`test_a_porta_que_ela_so_nomeou_e_do_mapa_e_se_renomeia` — tire o laço
  dos lugares identificados de ``ler_o_mapa`` e o nome que ela deu em Rádio e
  Adaptadores some da lista; tire o ``and caminhos`` de ``fatos_do_buraco`` e
  o -71 da porta sem nó lido vira zero;
* :func:`test_o_lugar_e_universal_e_o_dela_continua_aceito` — tire o ``+ dela``
  dos lugares de ``ler_o_mapa`` e a face que ela já tem deixa de ser escolhível;
* :func:`test_renomear_pela_lista_nao_troca_a_testemunha` — devolva o
  ``porta.aparelho or …`` na testemunha, ou tire o ``or da_vez``/``numero is
  None`` do ramo vivo, e o pendrive no lado 3.x vira o caminho da porta.

Faixa sintética da casa: controladores ``0000:0a:00.0`` e ``0000:0b:00.0``.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mapa_das_portas as junta
from hefesto_dualsense4unix.integrations import lugar_declarado
from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador
from hefesto_dualsense4unix.utils import maquina as utils_maquina
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
    lugar_de,
)
from tests.unit.test_entrada_a_entrada_02_as_telas_aprovadas import (
    BOOT_1,
    DONGLE_BT,
    DUALSENSE,
    HUB,
    PCI_A,
    PCI_B,
    Gabinete,
)

RAIZ = Path(__file__).resolve().parents[2]
DONO = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "entrada_a_entrada.py"

#: O -71 que o log do kernel-watch daria: cinco no dongle.
STORM = {"3-4.1": 5}

#: Um aparelho que só existe no lado 3.x do buraco (classe de armazenamento).
PENDRIVE = ("aa01", "0001", ("08", "06", "50"))


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta régua mora no ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    return alvo


@pytest.fixture()
def mesa(tmp_path: Path) -> Gabinete:
    """Uma porta de cada tipo — o hub de dois chips, o dongle e o BT da placa."""
    gabinete = Gabinete(
        tmp_path / "sys",
        BOOT_1,
        encaixe={"usb3-port2": "hardwired", "usb4-port2": "hardwired"},
    )
    gabinete.plugar(3, "4", HUB, portas=4)
    gabinete.plugar(4, "4", HUB, portas=4)
    gabinete.plugar(3, "4.1", DONGLE_BT)
    gabinete.plugar(3, "2", DONGLE_BT)
    return gabinete


def _fluxo(gabinete: Gabinete) -> ee.MapearAsPortas:
    return ee.MapearAsPortas(
        ler=gabinete.ler,
        entradas=gabinete.entradas,
        storm=STORM,
        adaptadores=lambda: (Adaptador(interface="hci9"),),
    )


def _mapear_tres(gabinete: Gabinete, fluxo: ee.MapearAsPortas) -> None:
    """O gesto dela: o MESMO DualSense em três portas, nome e lugar em cada."""
    assert fluxo.comecar()["estado"] == ee.ESPERANDO
    for bus, devpath, nome, lugar in (
        (1, "5", "Frente de baixo", ee.LUGAR_FRENTE),
        (1, "1", "Atrás, a azul", ee.LUGAR_TRASEIRA),
        (3, "4.2", "Hub da mesa", ee.LUGAR_HUB),
    ):
        gabinete.plugar(bus, devpath, DUALSENSE)
        foto = fluxo.olhar()
        assert foto["estado"] == ee.NA_PORTA
        assert foto["porta"]["aparelho"] == f"{bus}-{devpath}"
        gravacao = fluxo.gravar(nome=nome, lugar=lugar)
        assert gravacao.gravou, gravacao
        gabinete.tirar(f"{bus}-{devpath}")
        fluxo.olhar()


# ---------------------------------------------------------------------------
# 1. o mesmo controle de porta em porta
# ---------------------------------------------------------------------------


def test_o_mesmo_controle_de_porta_em_porta_mapeia_cada_uma(
    mesa: Gabinete, disco: Path
) -> None:
    gravacoes: list[dict[str, Any]] = []

    def contar(declaracao: Any) -> Any:
        gravacoes.append(json.loads(json.dumps(declaracao)))
        return declarar_a_maquina(declaracao)

    fluxo = ee.MapearAsPortas(
        ler=mesa.ler,
        entradas=mesa.entradas,
        storm=STORM,
        gravar=contar,
        adaptadores=lambda: (Adaptador(interface="hci9"),),
    )
    _mapear_tres(mesa, fluxo)
    assert len(gravacoes) == 3, "cada gesto dela é UMA gravação: número, face, amarra e nome juntos"
    assert all({"mapa", "lugares"} <= set(g) for g in gravacoes), gravacoes

    documento = carregar_maquina()
    faces = {face.nome: face.portas for face in documento.mapa.faces}
    assert faces == {
        ee.LUGAR_FRENTE: ["1"],
        ee.LUGAR_TRASEIRA: ["2"],
        ee.LUGAR_HUB: ["3"],
    }
    assert documento.mapa.portas["1"].nos == ["usb1-port5"]
    assert documento.mapa.portas["2"].nos == ["usb1-port1", "usb2-port1"]
    assert documento.mapa.portas["3"].nos == ["3-4-port2", "4-4-port2"]
    lugar_1 = lugar_de(PCI_A, "5")
    assert documento.lugares[lugar_1].entrada == "1"
    assert documento.lugares[lugar_1].nome == "Frente de baixo"
    assert documento.lugares[lugar_de(PCI_B, "4.2")].nome == "Hub da mesa"
    assert fluxo.estado()["feitas"] == 3


def test_o_controle_que_ja_estava_no_cabo_nao_e_a_porta_da_vez(
    mesa: Gabinete, disco: Path
) -> None:
    """A mesa de quatro: dois controles já no cabo não viram «a porta dela»."""
    mesa.plugar(1, "5", DUALSENSE)
    mesa.plugar(1, "6", DUALSENSE)
    fluxo = _fluxo(mesa)
    assert fluxo.comecar()["porta"] is None

    mesa.tirar("1-6")
    mesa.plugar(3, "4.3", DUALSENSE)
    foto = fluxo.olhar()
    assert foto["porta"]["nos"] == ["3-4-port3", "4-4-port3"], (
        "a porta da vez é a que APARECEU, não a primeira da leitura"
    )
    assert fluxo.olhar()["porta"]["nos"] == ["3-4-port3", "4-4-port3"]

    sozinho = Gabinete(mesa.raiz.parent / "outra", BOOT_1)
    sozinho.plugar(1, "3", DUALSENSE)
    assert _fluxo(sozinho).comecar()["porta"]["aparelho"] == "1-3", (
        "com UM controle já encaixado, a porta dele é a da vez"
    )


def test_ela_tira_o_controle_antes_de_gravar_e_a_porta_continua_a_da_vez(
    mesa: Gabinete, disco: Path
) -> None:
    fluxo = _fluxo(mesa)
    fluxo.comecar()
    mesa.plugar(1, "5", DUALSENSE)
    fluxo.olhar()
    mesa.tirar("1-5")
    foto = fluxo.olhar()
    assert foto["porta"] is not None and foto["porta"]["ocupada"] is False

    assert fluxo.gravar(nome="Frente", lugar=ee.LUGAR_FRENTE).gravou
    assert carregar_maquina().mapa.portas["1"].caminho == "1-5"


# ---------------------------------------------------------------------------
# 2. a leitura pelo nome único
# ---------------------------------------------------------------------------


def test_cada_porta_diz_o_que_o_metal_e(mesa: Gabinete, disco: Path) -> None:
    fluxo = _fluxo(mesa)
    _mapear_tres(mesa, fluxo)

    mapa = ee.ler_o_mapa(
        censo=mesa.ler(),
        entradas=mesa.entradas(),
        storm=STORM,
        adaptadores=(Adaptador(interface="hci9"),),
    )
    frente, traseira, hub = (mapa.porta(n) for n in ("1", "2", "3"))
    assert frente is not None and traseira is not None and hub is not None
    assert (frente.usb, frente.controlador, frente.hub) == (junta.USB_2, PCI_A, "")
    assert (traseira.usb, traseira.lugar_no_gabinete) == (junta.USB_3, ee.LUGAR_TRASEIRA)
    assert (hub.usb, hub.hub, hub.controlador) == (junta.USB_3, "3-4", PCI_B)
    assert frente.rotulo == "Frente de baixo" and frente.storm == 0

    dongle = mapa.porta(lugar_de(PCI_B, "4.1"))
    placa = mapa.porta(lugar_de(PCI_B, "2"))
    assert dongle is not None and placa is not None, "a ocupada sem número também é porta"
    assert dongle.numero is None and dongle.chave == dongle.lugar
    assert (dongle.bluetooth, dongle.storm, dongle.hub) == (junta.BLUETOOTH_DONGLE, 5, "3-4")
    assert placa.bluetooth == junta.BLUETOOTH_DA_PLACA
    assert mapa.bluetooth_sem_porta == 1, "o adaptador sem USB é o da placa"

    assert fluxo.estado()["portas"] == mapa.como_dicionario()["portas"], (
        "a tela e os leitores leem a MESMA coisa pelo mesmo nome"
    )


def test_a_raiz_desviada_nao_le_o_log_desta_maquina(mesa: Gabinete) -> None:
    mapa = ee.ler_o_mapa(
        maquina=MaquinaConfig(), raiz_usb=str(mesa.lista), adaptadores=()
    )
    assert {p.aparelho for p in mapa.portas} == {"3-2", "3-4", "3-4.1"}, (
        "a raiz desviada tem de LER o /sys de mentira — lista vazia passaria calada"
    )
    assert {p.controlador for p in mapa.portas} == {PCI_B}
    assert all(p.storm is None for p in mapa.portas), "outra raiz: o -71 é não medido"


# ---------------------------------------------------------------------------
# 3. a revisita é o mesmo fluxo, e não apaga
# ---------------------------------------------------------------------------


def _sem(documento: dict[str, Any], *caminhos: tuple[str, ...]) -> dict[str, Any]:
    copia = json.loads(json.dumps(documento))
    for caminho in caminhos:
        alvo = copia
        for chave in caminho[:-1]:
            alvo = alvo[chave]
        alvo.pop(caminho[-1], None)
    return copia


def test_a_revisita_so_troca_o_que_ela_trocou(mesa: Gabinete, disco: Path) -> None:
    fluxo = _fluxo(mesa)
    _mapear_tres(mesa, fluxo)
    antes = json.loads(disco.read_text(encoding="utf-8"))

    # renomear pela lista, sem encaixar nada
    assert fluxo.gravar(chave="1", nome="Frente").gravou
    depois = json.loads(disco.read_text(encoding="utf-8"))
    lugar_1 = lugar_de(PCI_A, "5")
    assert depois["lugares"][lugar_1]["nome"] == "Frente"
    assert _sem(depois, ("lugares", lugar_1, "nome")) == _sem(
        antes, ("lugares", lugar_1, "nome")
    ), "renomear mexeu em mais do que o nome"

    # reposicionar pela lista
    assert fluxo.gravar(chave="2", lugar=ee.LUGAR_TOPO).gravou
    faces = {f.nome: f.portas for f in carregar_maquina().mapa.faces}
    assert faces[ee.LUGAR_TOPO] == ["2"] and faces[ee.LUGAR_FRENTE] == ["1"]
    assert faces[ee.LUGAR_HUB] == ["3"]
    assert faces[ee.LUGAR_TRASEIRA] == [], "a face de antes fica, vazia — é o desenho dela"

    # a revisita pelo controle: a porta chega com o que ela já disse
    mesa.plugar(1, "5", DUALSENSE)
    foto = fluxo.olhar()
    assert (foto["porta"]["numero"], foto["porta"]["nome"]) == ("1", "Frente")
    assert fluxo.gravar(lugar=ee.LUGAR_LATERAL).gravou
    documento = carregar_maquina()
    assert documento.lugares[lugar_1].nome == "Frente", "mudar o lugar não apaga o nome"
    assert documento.lugares[lugar_1].entrada == "1", "a revisita não troca o número"
    assert documento.mapa.portas["3"].nos == ["3-4-port2", "4-4-port2"]

    # o hub desligado: a porta 3 não está no /sys, e a revisita ainda vale
    mesa.tirar("3-4")
    mesa.tirar("4-4")
    antes = json.loads(disco.read_text(encoding="utf-8"))
    assert fluxo.gravar(chave="3", nome="Hub do monitor", lugar=ee.LUGAR_MONITOR).gravou
    depois = json.loads(disco.read_text(encoding="utf-8"))
    faces_antes = {f["nome"]: f["portas"] for f in antes["mapa"]["faces"]}
    faces_depois = {f["nome"]: f["portas"] for f in depois["mapa"]["faces"]}
    assert faces_depois.pop(ee.LUGAR_MONITOR) == ["3"]
    faces_antes[ee.LUGAR_HUB] = []
    assert faces_depois == faces_antes, "a revisita apagou as outras faces"
    assert depois["mapa"]["portas"] == antes["mapa"]["portas"]
    lugar_3 = lugar_de(PCI_B, "4.2")
    assert depois["lugares"][lugar_3]["nome"] == "Hub do monitor"
    assert _sem(depois, ("lugares", lugar_3, "nome"), ("mapa",)) == _sem(
        antes, ("lugares", lugar_3, "nome"), ("mapa",)
    )


def test_a_revisita_nao_apaga_o_que_o_laco_de_antes_gravou(
    mesa: Gabinete, disco: Path
) -> None:
    """O laço da cerimônia de antes e o fluxo único escrevem pelo mesmo gravador."""
    laco = ee.LacoDaEntrada(ler=mesa.ler, entradas=mesa.entradas)
    laco.comecar()
    while laco.estado()["estado"] == ee.SENTADA:
        assert laco.responder(ee.FACE_HUB).gravou
    laco.parar()
    antes = carregar_maquina()

    fluxo = _fluxo(mesa)
    fluxo.comecar()
    mesa.plugar(1, "5", DUALSENSE)
    fluxo.olhar()
    assert fluxo.gravar(nome="Frente", lugar=ee.LUGAR_FRENTE).gravou

    depois = carregar_maquina()
    for numero, porta in antes.mapa.portas.items():
        assert depois.mapa.portas[numero] == porta, numero
    hub_antes = next(f for f in antes.mapa.faces if f.nome == ee.FACE_HUB)
    hub_depois = next(f for f in depois.mapa.faces if f.nome == ee.FACE_HUB)
    assert hub_depois == hub_antes
    for lugar, dele in antes.lugares.items():
        assert depois.lugares[lugar] == dele, lugar


# ---------------------------------------------------------------------------
# 4. um gravador só
# ---------------------------------------------------------------------------

#: Os nomes que ESCREVEM o ``maquina.json`` quando chamados.
_GRAVADORES = frozenset(
    {
        "gravar",
        "_gravar",
        "declarar_a_maquina",
        "declarar_a_mesa",
        "gravar_maquina",
        "gravar_maquina_com_descartes",
        "gravar_rascunho_da_mesa",
    }
)

#: As escritas cruas de arquivo — o ``maquina.json`` escrito à mão, sem o lock.
_ESCRITAS_CRUAS = frozenset({"open", "write_text", "write_bytes", "dump", "replace", "rename"})


def _gravadores() -> frozenset[str]:
    """Os de hoje e TODO escritor público que nascer nos dois donos do disco.

    A lista digitada acima envelheceria calada no dia em que ``utils/maquina``
    ou ``lugar_declarado`` ganhassem um ``gravar_…`` novo; o que se deriva
    deles não envelhece.
    """
    derivados = {
        nome
        for modulo in (utils_maquina, lugar_declarado)
        for nome in dir(modulo)
        if nome.startswith(("gravar", "declarar", "salvar", "escrever"))
        and callable(getattr(modulo, nome))
    }
    assert {"declarar_a_maquina", "gravar_maquina_com_descartes"} <= derivados
    return _GRAVADORES | derivados


def test_um_gravador_so_no_dono() -> None:
    arvore = ast.parse(DONO.read_text(encoding="utf-8"))
    achados: list[tuple[str, int]] = []

    def visitar(no: ast.AST, dentro: str) -> None:
        for filho in ast.iter_child_nodes(no):
            nome = dentro
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nome = filho.name
            if isinstance(filho, ast.Call):
                alvo = filho.func
                chamado = (
                    alvo.id
                    if isinstance(alvo, ast.Name)
                    else alvo.attr
                    if isinstance(alvo, ast.Attribute)
                    else ""
                )
                if chamado in gravadores:
                    achados.append((nome, filho.lineno))
                cru = chamado in _ESCRITAS_CRUAS and (
                    isinstance(alvo, ast.Name)
                    or (
                        isinstance(alvo, ast.Attribute)
                        and chamado in {"write_text", "write_bytes"}
                    )
                    or (
                        isinstance(alvo, ast.Attribute)
                        and isinstance(alvo.value, ast.Name)
                        and alvo.value.id in {"os", "json", "shutil"}
                    )
                )
                if cru:
                    crus.append((nome, filho.lineno))
            visitar(filho, nome)

    gravadores = _gravadores()
    crus: list[tuple[str, int]] = []
    visitar(arvore, "<módulo>")
    fora = [(f, linha) for f, linha in achados if f != "_gravar_no_mapa"]
    assert achados, "a régua não achou nem o gravador único"
    assert not fora, f"um segundo gravador no dono do mapa: {fora}"
    assert not crus, f"uma escrita crua de arquivo no dono do mapa, fora do lock: {crus}"


# ---------------------------------------------------------------------------
# 5. o lugar é universal
# ---------------------------------------------------------------------------


def test_o_lugar_e_universal_e_o_dela_continua_aceito(mesa: Gabinete, disco: Path) -> None:
    assert len(set(ee.LUGARES_DA_PORTA)) == len(ee.LUGARES_DA_PORTA) == 7
    for antigo in (ee.FACE_FRENTE, ee.FACE_ATRAS, ee.FACE_HUB):
        assert antigo in ee.LUGARES_DA_PORTA, "a grafia de antes fica, ou a face dela fica órfã"

    fluxo = _fluxo(mesa)
    fluxo.comecar()
    mesa.plugar(1, "5", DUALSENSE)
    fluxo.olhar()
    with pytest.raises(ValueError):
        fluxo.gravar(nome="x", lugar="Na lua")
    so_o_nome = fluxo.gravar(nome="só o nome, porta nova")
    assert so_o_nome.gravou and so_o_nome.entrada == "" and so_o_nome.face == ""
    documento = carregar_maquina()
    assert documento.lugares[lugar_de(PCI_A, "5")].nome == "só o nome, porta nova"
    assert not documento.mapa.faces and not documento.mapa.portas, (
        "sem o «onde fica», o produto não inventa face nem número por ela"
    )
    assert fluxo.gravar(lugar=ee.FACE_ESCRIVANINHA).gravou, "a quarta resposta de antes"
    assert carregar_maquina().lugares[lugar_de(PCI_A, "5")].nome == "só o nome, porta nova"
    assert fluxo.estado()["lugares"] == [*ee.LUGARES_DA_PORTA, ee.FACE_ESCRIVANINHA], (
        "a face que ela já tem continua escolhível para a próxima porta"
    )
    assert fluxo.gravar(chave="1", lugar=ee.FACE_ESCRIVANINHA).gravou
    with pytest.raises(RuntimeError):
        fluxo.gravar(chave="99", nome="não existe")


# ---------------------------------------------------------------------------
# 6. o que ela só nomeou também é do mapa (conferência, 25/09/2026)
# ---------------------------------------------------------------------------


def test_a_porta_que_ela_so_nomeou_e_do_mapa_e_se_renomeia(
    mesa: Gabinete, disco: Path
) -> None:
    """O nome dado em Rádio e Adaptadores (``dar_nome``) mora no lugar, sem número.

    Ela pediu que o mesmo botão renomeie *«as entradas já mapeadas ou
    identificadas»*: o dongle que ela nomeou é identificado, e continua dela
    com o dongle fora da porta. <!-- noqa-acento: citação literal dela -->
    """
    lugar_do_dongle = lugar_de(PCI_B, "4.1")
    assert ee.dar_nome(lugar_do_dongle, "Dongle azul").gravou
    mesa.tirar("3-4.1")
    fluxo = _fluxo(mesa)
    fluxo.comecar()

    mapa = ee.ler_o_mapa(
        censo=mesa.ler(), entradas=mesa.entradas(), storm=STORM, adaptadores=()
    )
    dongle = mapa.porta(lugar_do_dongle)
    assert dongle is not None, "a porta que ela só nomeou sumiu do mapa"
    assert (dongle.nome, dongle.numero, dongle.ocupada) == ("Dongle azul", None, False)
    assert dongle.nos == ("3-4-port1", "4-4-port1")
    mesa.tirar("3-4")
    mesa.tirar("4-4")
    sem_o_hub = ee.ler_o_mapa(
        censo=mesa.ler(), entradas=mesa.entradas(), storm=STORM, adaptadores=()
    ).porta(lugar_do_dongle)
    assert sem_o_hub is not None and sem_o_hub.nos == ()
    assert (sem_o_hub.ocupada, sem_o_hub.usb, sem_o_hub.storm) == (None, "", None), (
        "o hub desligado: nada foi lido, e não sei não é zero"
    )
    assert [p.lugar for p in mapa.portas].count(lugar_do_dongle) == 1

    assert fluxo.gravar(chave=lugar_do_dongle, nome="Dongle da TV").gravou
    documento = carregar_maquina()
    assert documento.lugares[lugar_do_dongle].nome == "Dongle da TV"
    assert documento.lugares[lugar_do_dongle].entrada is None
    assert not documento.mapa.faces, "renomear não inventa face"


def test_o_encaixe_que_o_kernel_nao_sabe_nao_vira_dongle(tmp_path: Path) -> None:
    """``unknown`` é "não sei", e o hub encaixado de fora faz o dongle."""
    gabinete = Gabinete(
        tmp_path / "sys",
        BOOT_1,
        encaixe={
            "usb3-port2": "unknown",
            "usb4-port2": "unknown",
            "3-4-port1": "unknown",
            "usb1-port3": "hardwired",
            "1-3-port1": "unknown",
            "3-3-port1": "unknown",
        },
    )
    gabinete.plugar(3, "2", DONGLE_BT)
    gabinete.plugar(3, "4", HUB, portas=4)
    gabinete.plugar(3, "4.1", DONGLE_BT)
    gabinete.plugar(1, "3", HUB, portas=4)
    gabinete.plugar(1, "3.1", DONGLE_BT)
    gabinete.plugar(3, "3", HUB, portas=4)
    gabinete.plugar(3, "3.1", DONGLE_BT)

    mapa = ee.ler_o_mapa(
        maquina=MaquinaConfig(), raiz_usb=str(gabinete.lista), adaptadores=()
    )
    sem_saber = mapa.porta(lugar_de(PCI_B, "2"))
    atras_do_hub = mapa.porta(lugar_de(PCI_B, "4.1"))
    no_hub_de_fora = mapa.porta(lugar_de(PCI_B, "3.1"))
    assert sem_saber is not None and atras_do_hub is not None and no_hub_de_fora is not None
    assert (sem_saber.e_bluetooth, sem_saber.bluetooth) == (True, ""), (
        "entrada unknown: o produto não sabe se é da placa ou dongle"
    )
    assert atras_do_hub.bluetooth == junta.BLUETOOTH_DONGLE, (
        "o hub numa entrada hotplug foi encaixado de fora — o que pende dele é dongle"
    )
    assert no_hub_de_fora.bluetooth == junta.BLUETOOTH_DONGLE
    no_hub_interno = mapa.porta(lugar_de(PCI_A, "3.1"))
    assert no_hub_interno is not None and no_hub_interno.bluetooth == "", (
        "o hub interno hospeda o rádio da placa E o painel da frente: não sei"
    )
    hub = mapa.porta(lugar_de(PCI_B, "4"))
    assert hub is not None and (hub.e_bluetooth, hub.bluetooth) == (False, "")


def test_renomear_pela_lista_nao_troca_a_testemunha(mesa: Gabinete, disco: Path) -> None:
    """Um pendrive no lado 3.x da porta 2 não vira a testemunha dela.

    Renomear e reposicionar pela lista não provam nada do buraco: o aparelho que
    estiver nele agora pode só existir no lado 3.x (``2-1``), e a amarra da
    porta é do lado 2.0 (``1-1``), onde o DualSense a ensinou.
    """
    fluxo = _fluxo(mesa)
    _mapear_tres(mesa, fluxo)
    mesa.plugar(2, "1", PENDRIVE)
    # o «Não alcanço» que ela deu um dia fica: renomear não é o cabo provando
    assert declarar_a_maquina({"lugares": {lugar_de(PCI_A, "1"): {"fora": True}}}).gravou
    antes = json.loads(disco.read_text(encoding="utf-8"))

    assert fluxo.gravar(chave="2", nome="Atrás, a de cima").gravou
    assert fluxo.gravar(chave="2", lugar=ee.LUGAR_TOPO).gravou
    depois = json.loads(disco.read_text(encoding="utf-8"))
    assert depois["mapa"]["portas"] == antes["mapa"]["portas"], (
        "a revisita pela lista trocou o caminho da porta"
    )
    lugar_2 = lugar_de(PCI_A, "1")
    assert depois["lugares"][lugar_2]["caminho"] == "1-1"
    assert depois["lugares"][lugar_2]["entrada"] == "2"
    assert depois["lugares"][lugar_2]["nome"] == "Atrás, a de cima"
    assert depois["lugares"][lugar_2].get("fora") is True, "renomear desfez o «Não alcanço»"

    # e a porta nova tocada pela lista, com o pendrive só no lado 3.x, também
    # amarra pelo lado 2.0
    mesa.plugar(4, "3", PENDRIVE)
    assert fluxo.gravar(chave=lugar_de(PCI_B, "3"), lugar=ee.LUGAR_LATERAL).gravou
    documento = carregar_maquina()
    numero = documento.lugares[lugar_de(PCI_B, "3")].entrada
    assert numero is not None and documento.mapa.portas[numero].caminho == "3-3"
