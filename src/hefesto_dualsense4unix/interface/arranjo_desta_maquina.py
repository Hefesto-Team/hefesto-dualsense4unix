#!/usr/bin/env python3
"""O arranjo do computador de QUEM ABRE, na forma que o `mapa-das-portas` desenha.

POR QUE ELE EXISTE — ordem dela, 11/09/2026
--------------------------------------------

    "a ideia é que todas as features mesmo do app funcionem nao so pra  (noqa-acento)
     mim mas pra qualquer outro user"   — citação literal dela, 11/09/2026

O `mapa-das-portas.html` desenhava um gabinete digitado dentro do próprio HTML
— oito aparelhos de UMA máquina, lidos em 24/08/2026 — e chamava aquilo de "o
arranjo de agora". Este módulo é a outra metade da cura: ele monta o arranjo da
máquina de quem abriu, e o piloto o entrega à página por
``window.hefestoArranjo`` (:data:`~hefesto_dualsense4unix.interface.pagina_do_mapa.ABRE_A_PORTA`).

O QUE ELE NÃO FAZ
------------------

**Não inventa o que ninguém declarou.** O número da entrada no metal
(``9``, ``15a``) não existe em leitura nenhuma — é declaração de quem olhou o
gabinete, e está medido no ``integrations/mapa_das_portas``: duas entradas da
frente respondem ``panel``, ``horizontal_position`` e ``vertical_position``
IDÊNTICOS. Sem faces declaradas não há mapa a desenhar, e a resposta é
:data:`None` — a página fica com o exemplo, que se declara exemplo. Devolver um
gabinete inventado seria pior do que devolver o de outra pessoa.

**Não decide nada sobre o arranjo.** Quem julga entrada é
``integrations/arranjo_da_mesa``, e quem junta o mapa dela com o censo do
kernel é ``integrations/mapa_das_portas.mesa_do_motor``. Aqui só se TRADUZ o
que eles produzem para os nomes que o JavaScript da página lê — que é o único
trabalho que sobra, e é por isso que este arquivo é curto.

**Não repete a paleta.** As cores saem de
``pagina_do_mapa.CORES_POR_CLASSE``, derivadas do próprio censo de exemplo. Uma
segunda tabela de cor divergiria da primeira no dia em que alguém trocasse o
roxo do Bluetooth — é a classe de defeito que esta casa chama de segunda
verdade.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import secrets
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from hefesto_dualsense4unix.interface import pagina_do_mapa

#: A página que recebe o que este módulo produz. O piloto compara com o nome do
#: arquivo à vista, e o nome mora aqui para não ser digitado nos dois lados.
PAGINA = "mapa-das-portas.html"

#: O rótulo do cabeçalho quando a leitura é desta máquina. O do exemplo é
#: :data:`pagina_do_mapa.QUANDO_DO_EXEMPLO`, e os dois moram um ao lado do
#: outro de propósito: a frase que distingue "é seu" de "é exemplo" é a defesa
#: inteira da página contra ser lida como verdade de qualquer computador.
QUANDO_DE_AGORA = "leitura deste computador · {quando}"

#: O rótulo das duas leituras. Na primeira abertura só existe UMA, e dizer que
#: a anterior é igual é o que é verdade — inventar um "antes" diferente faria a
#: tela mostrar movimentos que ninguém fez.
ROTULO_DE_AGORA = "lido agora"
ROTULO_DE_ANTES = "a leitura anterior — ainda é esta"
#: O rótulo do «antes» de um reexame: a leitura que a página tinha na tela
#: quando ela clicou em «Examinar».
ROTULO_DA_ANTERIOR = "a leitura anterior"

#: A CHAVE COM QUE UM GESTO DEVOLVE UM ARRANJO À PÁGINA — O-MAPA-DAS-CONEXOES-
#: NO-PRODUTO-02, 26/09/2026. O retorno de um gesto só pintava `data-campo`, e
#: o arranjo não é um valor num campo: é o gabinete inteiro. O piloto tira esta
#: chave da resposta e a entrega por :func:`js_da_entrega`
#: (`hefesto_vivo.Piloto._o_arranjo_relido`), o mesmo caminho da abertura.
CHAVE_DA_ENTREGA = "arranjo"

#: A IDENTIDADE DE UM APARELHO NA PÁGINA — O-MAPA-DAS-CONEXOES-NO-PRODUTO-02.
#: O `id` era o caminho de barramento, e o caminho é justamente o que muda
#: quando ela move o aparelho: o reexame não tinha como dizer «estava em», e
#: dizia `undefined`. O `id` passa a ser um resumo com SAL do que o aparelho é
#: (o serial, ou o modelo quando ele é o único daquele modelo). O sal nasce
#: com o processo e nunca sai da memória: o serial de um dongle Bluetooth é o
#: endereço do rádio, e ele não vai à tela nem ao disco, nem por resumo que se
#: possa refazer noutro dia.
_SAL = secrets.token_bytes(16)
_PREFIXO_DO_ID = "ap-"

#: UMA LEITURA, COMO O REEXAME SEGUINTE A CONFERE: ``id -> (caminho, modelo)``.
#: O modelo (``vid:pid``) não vai à página; ele fica na memória para dizer se
#: quem está hoje num caminho é do mesmo modelo de quem estava ali antes.
Lida = dict[str, tuple[str, str]]

#: A forma do desenho de cada face, e ela não é declarada por ninguém: o
#: ``MapaDaMesa`` guarda quantas entradas a face tem e onde ela fica, não como
#: desenhá-la. A escolha é de tela e mora aqui, com o critério à vista.
_FILEIRA_DO_HUB = "fileira"
_COLUNA_CURTA = "coluna"
_GRADE = "grade-tras"

#: Até quantas entradas uma face do gabinete vira coluna em vez de grade.
_TETO_DA_COLUNA = 2

#: O QUE O DESENHO ESCREVE NO CABO DA ENTRADA-FILHA. O exemplo diz "extensor de
#: 1 m" porque alguém mediu aquele cabo; aqui o comprimento não se sabe, e a
#: frase diz só o que é verdade. Sem ela o desenho escreveria `undefined` ao
#: lado da entrada — o `porta.filho.cabo` é lido sem defesa no JavaScript.
#: FATO SUBSTITUÍDO em 26/09/2026: dizia «extensão declarada por você»; o
#: editor da entrada (`pagina_do_mapa`) escreve «Extensor», e a mesma ponta de
#: cabo não pode ter dois nomes antes e depois de a página ser relida.
CABO_DECLARADO = "Extensor, declarado por você"

#: QUANTAS ENTRADAS O HUB DECLARADO DESENHA — 26/09/2026, o desenho aprovado do
#: editor da entrada. O número de buracos do hub dela não se lê de lugar
#: nenhum que este módulo leia, e quatro é o que o desenho mostra; a entrada
#: que ela mapear nele pelo Mapear vira face de verdade e toma o lugar destas.
ENTRADAS_DO_HUB_DECLARADO = 4


def arranjo(
    agora: _dt.datetime | None = None,
    carregar: Callable[[], Any] | None = None,
    ler_o_barramento: Callable[[], Any] | None = None,
    *,
    antes: Mapping[str, tuple[str, str]] | None = None,
    ler_o_serial: Callable[[str], str] | None = None,
) -> dict[str, Any] | None:
    """O arranjo desta máquina, ou ``None`` quando não há o que desenhar.

    As fontes são injetáveis para que a régua meça esta tradução sem tocar
    no ``/sys`` da máquina de ninguém — e sem um ``monkeypatch`` que alcança
    só quem importar pelo mesmo caminho.

    ``antes`` é a leitura que a página já tem (:data:`Lida`), e só o
    «Examinar» a passa (:func:`reexaminar`): sem ela, as duas leituras nascem
    iguais, que é o que é verdade na primeira abertura.

    LÊ O ``/sys`` USB, e por isso NUNCA roda no fio da janela: ``product``,
    ``bMaxPower`` e ``serial`` esperam o lock do aparelho enquanto o kernel
    enumera o que acabou de chegar (a O-MAPEAR-NAO-CONGELA-A-JANELA-01 mediu
    15 s). Quem chama é um fio próprio do piloto ou o fio do gesto.

    ``None`` acontece em três casos, e os três são honestos:

    * o ``maquina.json`` não tem face declarada — não há gabinete a desenhar;
    * a leitura do barramento falhou — e censo vazio faria toda entrada parecer
      livre, que é o vazio mais convincente que existe;
    * o import falhou (árvore sem ``src``), que é o caso de quem roda a página
      solta no navegador.
    """
    lido = _ler_a_maquina(agora, carregar, ler_o_barramento,
                          antes=antes, ler_o_serial=ler_o_serial)
    return None if lido is None else lido[0]


def _ler_a_maquina(
    agora: _dt.datetime | None = None,
    carregar: Callable[[], Any] | None = None,
    ler_o_barramento: Callable[[], Any] | None = None,
    *,
    antes: Mapping[str, tuple[str, str]] | None = None,
    ler_o_serial: Callable[[str], str] | None = None,
) -> tuple[dict[str, Any], Lida] | None:
    """O :func:`arranjo` e a :data:`Lida` dele, que o reexame seguinte confere."""
    try:
        from hefesto_dualsense4unix.integrations import mapa_das_portas
        from hefesto_dualsense4unix.integrations.censo_do_barramento import (
            ler_o_barramento as _ler,
        )
        from hefesto_dualsense4unix.integrations.entrada_a_entrada import faces_dos_hubs
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina, entradas_do_mapa
    except Exception:
        return None

    try:
        documento = (carregar or carregar_maquina)()
        declarado = getattr(documento, "mapa", None)
        if declarado is None or not declarado.faces:
            return None
        censo = (ler_o_barramento or _ler)()
        bancada = mapa_das_portas.mesa_do_motor(declarado, censo)
        conectados = censo.conectados()
        ids = identidades(
            conectados, ler_o_serial or mapa_das_portas.serial_do_no, antes,
            lido_em=bancada.mesa.leitura)
        modelos = _modelos(conectados)
    except Exception:
        return None

    mesa = bancada.mesa
    if not mesa.faces:
        return None

    quando = (agora or _dt.datetime.now()).strftime("%d/%m/%Y %Hh%M")
    # O CAMINHO É O DA LEITURA DO MOTOR, e não o nome do kernel: o Wi-Fi que
    # enumera no lado 3.0 do buraco (`4-1.1.4`) é lido no caminho da entrada
    # (`3-1.1.4`), que é o que a página compara com o mapa.
    caminhos = {ids.get(a.id, a.id): mesa.leitura.get(a.id, a.id) for a in mesa.aparelhos}
    faces = _faces(mesa.faces)
    _o_que_ela_declarou_nas_entradas(faces, declarado, faces_dos_hubs(declarado))
    anterior = (
        {"rotulo": ROTULO_DE_ANTES, "caminho": dict(caminhos)}
        if antes is None
        else {"rotulo": ROTULO_DA_ANTERIOR,
              "caminho": {i: caminho for i, (caminho, _m) in antes.items()}}
    )
    lida = {ids.get(a.id, a.id): (mesa.leitura.get(a.id, a.id), modelos.get(a.id, ""))
            for a in mesa.aparelhos}
    return {
        "quando": QUANDO_DE_AGORA.format(quando=quando),
        "aparelhos": [_aparelho(a, ids.get(a.id, a.id)) for a in mesa.aparelhos],
        "faces": faces,
        "mapa": dict(mesa.mapa),
        "leituras": {
            "agora": {"rotulo": ROTULO_DE_AGORA, "caminho": caminhos},
            "antes": anterior,
        },
        "declarado": _declarado(declarado, entradas_do_mapa(declarado)),
    }, lida


# ── O «Examinar» relê: a leitura anterior mora aqui, na memória ─────────────


class _ALeituraNaTela:
    """A :data:`Lida` da última leitura entregue à página.

    É o «antes» do próximo «Examinar». Mora na memória do processo, junto com
    o sal das identidades, e nunca vai a disco: fora deste processo os ``id``
    não querem dizer nada. A trava guarda só a troca: a leitura do ``/sys``
    acontece fora dela.
    """

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._lida: Lida | None = None

    def ler(self) -> Lida | None:
        with self._trava:
            return None if self._lida is None else dict(self._lida)

    def guardar(self, lida: Mapping[str, tuple[str, str]]) -> None:
        copia = dict(lida)
        with self._trava:
            self._lida = copia


_NA_TELA = _ALeituraNaTela()


def para_a_pagina(**fontes: Any) -> dict[str, Any] | None:
    """A leitura que a página recebe ao abrir — e que vira o «antes» do reexame."""
    return _guardar_e_entregar(_ler_a_maquina(**fontes))


def reexaminar(**fontes: Any) -> dict[str, Any] | None:
    """O «Examinar»: relê a máquina, e o «antes» é a leitura que a página tem.

    Sem leitura anterior (a página ainda não recebeu nenhuma), as duas nascem
    iguais — a mesma verdade da abertura.
    """
    return _guardar_e_entregar(_ler_a_maquina(antes=_NA_TELA.ler(), **fontes))


def _guardar_e_entregar(lido: tuple[dict[str, Any], Lida] | None) -> dict[str, Any] | None:
    """A leitura que vai à página vira o «antes» do próximo «Examinar»."""
    if lido is None:
        return None
    dado, lida = lido
    _NA_TELA.guardar(lida)
    return dado


def js_da_entrega(dado: Mapping[str, Any], *, reexame: bool = False) -> str:
    """O JavaScript que entrega um arranjo à página — o da abertura e o do reexame.

    UM dono para as duas entregas: o piloto monta as duas por aqui, e a régua
    que abre a página no WebKit também.
    """
    corpo = json.dumps(dado, ensure_ascii=False)
    return f"window.hefestoArranjo({corpo}, {'true' if reexame else 'false'})"


def identidades(
    aparelhos: Sequence[Any],
    ler_o_serial: Callable[[str], str],
    antes: Mapping[str, tuple[str, str]] | None = None,
    *,
    lido_em: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """``caminho -> id`` de cada aparelho, o mesmo enquanto ele for o mesmo.

    A SEMENTE, na ordem da certeza:

    1. o serial do descritor, com o modelo (``vid:pid``);
    2. o modelo sozinho, quando só há UM aparelho dele — o receptor do teclado
       que muda de entrada continua sendo o único receptor daquele modelo;
    3. o caminho, quando nada separa dois aparelhos (dois do mesmo modelo sem
       serial, ou com o MESMO serial de fábrica, como o ``123456`` que um
       adaptador Wi-Fi desta casa responde). Aí mover um deles não se
       reconhece, e a página o mostra como quem chegou — nunca como o outro.
       O caminho vai COM o modelo: outro modelo que chega no mesmo caminho é
       outro aparelho, e não herda o ``id`` de quem saiu dali.

    QUEM FICOU PARADO CONTINUA SENDO ELE (a conferência da 02, 26/09/2026). Com
    ``antes`` (a :data:`Lida` que a página tem), o aparelho sem serial só dele
    que está no MESMO caminho, com o MESMO modelo, de um aparelho da leitura
    anterior é aquele aparelho. Sem isto, o gêmeo que chega (ou sai) trocava a
    semente de quem não se mexeu — o modelo deixava de ser único, ou voltava a
    ser — e o reexame dizia que ele «mudou de lugar». O serial só dele vence
    sempre: com ele, dois aparelhos que trocam de caminho se separam.

    A semente passa por um resumo com :data:`_SAL`: o ``id`` não refaz o
    serial, e o sal morre com o processo.

    ``lido_em`` é o caminho em que o motor LÊ cada aparelho
    (``mapa_das_portas.mesa_do_motor``), e é nele que a :data:`Lida` guarda:
    o parado se confere pelo mesmo caminho em que foi guardado.
    """
    modelos = _modelos(aparelhos)
    sementes: dict[str, str] = {}
    for aparelho in aparelhos:
        caminho = aparelho.nome_do_kernel
        serial = (ler_o_serial(aparelho.no) or "").strip()
        if serial:
            sementes[caminho] = f"serial|{modelos[caminho]}|{serial}"
        elif aparelho.vid or aparelho.pid:
            sementes[caminho] = f"modelo|{modelos[caminho]}"
        else:
            sementes[caminho] = ""
    repetidas = Counter(sementes.values())
    parados = {(caminho, modelo): i for i, (caminho, modelo) in (antes or {}).items()}
    fora: dict[str, str] = {}
    for caminho, semente in sementes.items():
        if semente.startswith("serial|") and repetidas[semente] == 1:
            fora[caminho] = _resumo(semente)
    usados = set(fora.values())
    for caminho in sementes:
        de_antes = parados.get(((lido_em or {}).get(caminho, caminho), modelos[caminho]))
        if caminho not in fora and de_antes is not None and de_antes not in usados:
            fora[caminho] = de_antes
            usados.add(de_antes)
    for caminho, semente in sementes.items():
        if caminho in fora:
            continue
        pelo_caminho = _resumo(f"caminho|{modelos[caminho]}|{caminho}")
        resumo = pelo_caminho if not semente or repetidas[semente] > 1 else _resumo(semente)
        fora[caminho] = pelo_caminho if resumo in usados else resumo
        usados.add(fora[caminho])
    return fora


def _modelos(aparelhos: Sequence[Any]) -> dict[str, str]:
    """``caminho -> vid:pid`` — o modelo, que não separa dois iguais."""
    return {a.nome_do_kernel: f"{a.vid}:{a.pid}" for a in aparelhos}


def _resumo(semente: str) -> str:
    feito = hashlib.blake2s(semente.encode("utf-8"), key=_SAL, digest_size=8)
    return _PREFIXO_DO_ID + feito.hexdigest()


def _declarado(mapa: Any, numeros: Any) -> dict[str, dict[str, Any]]:
    """O que ela disse de cada entrada DO MAPA DELA, para o editor da página.

    TODA entrada do mapa vem, com ``{}`` quando ela não disse nada: a lista de
    chaves é a lista das entradas que o editor GRAVA. A ponta de um extensor
    declarado grava também desde a O-MAPA-DAS-CONEXOES-NO-PRODUTO-02, e quem
    diz isso à página é o ``podeGravar`` dela (o extensor vem aqui, na mãe);
    depois do primeiro gesto a ponta está no disco e vem como as outras. As do
    hub desenhado (``5.1``…) não vêm: o número delas não cabe no disco, e ali
    o editor da página só mostra quem está nelas.
    """
    saida: dict[str, dict[str, Any]] = {}
    for numero in sorted(numeros):
        porta = mapa.portas.get(numero)
        dito: dict[str, Any] = {}
        if porta is not None and porta.liga:
            dito["liga"] = porta.liga
        if porta is not None and porta.usb:
            dito["usb"] = porta.usb
        saida[numero] = dito
    return saida


def _o_que_ela_declarou_nas_entradas(
    faces: list[dict[str, Any]], mapa: Any, hubs: dict[str, str]
) -> None:
    """O hub declarado vira face, e o extensor declarado vira entrada-filha.

    É a MESMA forma que o editor da página monta quando ela declara na tela
    (a `declarar` do `pagina_do_mapa`): a face «Hub na Entrada N», com
    ``daEntrada`` para o editor saber de quem ela é, e a ``filho`` que o motor
    do desenho já sabe desenhar. Reler a página tem de mostrar o que ela viu
    ao clicar.

    O hub que ela JÁ mapeou pelo Mapear tem face de verdade com esse nome, e
    ela vence: as entradas dela são as do metal, e as quatro daqui são desenho.
    """
    por_numero: dict[str, dict[str, Any]] = {}
    for face in faces:
        for entrada in face["portas"]:
            por_numero.setdefault(entrada["n"], entrada)
            # A PONTA DO EXTENSOR que já está no disco é entrada como as outras
            # (O-MAPA-DAS-CONEXOES-NO-PRODUTO-02): o hub que ela declarar ali
            # vira face, igual ao de uma entrada da chapa.
            if "filho" in entrada:
                por_numero.setdefault(entrada["filho"]["n"], entrada["filho"])
    nomes = {face["nome"] for face in faces}
    for numero, nome in hubs.items():
        entrada = por_numero.get(numero)
        if entrada is None or nome in nomes:
            continue
        faces.append({
            "nome": nome,
            "forma": _FILEIRA_DO_HUB,
            "regiao": "hub",
            "daEntrada": numero,
            "portas": [
                {"n": f"{numero}.{i}", "usb": entrada["usb"], "onde": "hub", "pos": i}
                for i in range(1, ENTRADAS_DO_HUB_DECLARADO + 1)
            ],
        })
    for numero, entrada in por_numero.items():
        porta = mapa.portas.get(numero)
        if porta is None or porta.liga != "extensor" or "filho" in entrada:
            continue
        entrada["filho"] = {
            "n": f"{numero}a",
            "usb": entrada["usb"],
            "onde": entrada["onde"],
            "esticada": True,
            "cabo": CABO_DECLARADO,
        }


def _aparelho(aparelho: Any, identidade: str) -> dict[str, Any]:
    """Um aparelho do motor nos cinco campos que a página LÊ.

    São cinco e não oito porque a página lê cinco: ``sementeDoCaminho``,
    ``usb`` e ``mA`` estão no censo de exemplo e nenhuma linha do JavaScript os
    consulta. Copiá-los aqui seria mobília — e mobília que alguém depois
    acreditaria estar sendo usada.

    O ``id`` é a :func:`identidades`, e não o caminho: o caminho vai nas
    leituras, que é onde a página o procura.
    """
    return {
        "id": identidade,
        "tipo": aparelho.tipo,
        "nome": aparelho.nome,
        "classe": aparelho.classe,
        "cor": pagina_do_mapa.CORES_POR_CLASSE.get(
            aparelho.classe, pagina_do_mapa.COR_SEM_CLASSE),
    }


def _faces(faces: Any) -> list[dict[str, Any]]:
    """As faces do motor mais a FORMA do desenho, que não vem de fonte nenhuma.

    ``donaDaFaixaPc`` é a face que recebe os aparelhos que estão numa entrada
    direta do PC sem lugar declarado. Ela tem de ser UMA: duas mostrariam a
    mesma bandeja duas vezes, e zero esconderia os aparelhos sem lugar — que
    são exatamente os que precisam de um clique dela.
    """
    saida = []
    dona = _dona_da_faixa(faces)
    for face in faces:
        corpo: dict[str, Any] = {
            "nome": face.nome,
            "forma": _forma(face),
            "regiao": face.regiao,
            "portas": [_entrada(e) for e in face.entradas],
        }
        if face.perto:
            corpo["perto"] = True
        if face.alto:
            corpo["alto"] = True
        if face is dona:
            corpo["donaDaFaixaPc"] = True
        saida.append(corpo)
    return saida


def _dona_da_faixa(faces: Any) -> Any:
    """A face do PC com mais entradas, ou ``None`` se nenhuma face é do PC."""
    do_pc = [f for f in faces if f.regiao == "pc"]
    return max(do_pc, key=lambda f: len(f.entradas)) if do_pc else None


def _forma(face: Any) -> str:
    if face.regiao == "hub":
        return _FILEIRA_DO_HUB
    return _COLUNA_CURTA if len(face.entradas) <= _TETO_DA_COLUNA else _GRADE


def _entrada(entrada: Any) -> dict[str, Any]:
    """Uma entrada do motor, sem os campos que ela não tem.

    Os opcionais saem quando são vazios em vez de irem como ``null``: o
    JavaScript da página testa `!!p.esticada` e `p.filho`, e um `null` explícito
    diria a mesma coisa com mais bytes — mas `par: null` chegaria ao
    `porNum(p.par)` como uma entrada que não existe.
    """
    corpo: dict[str, Any] = {"n": entrada.n, "usb": entrada.usb, "onde": entrada.onde}
    if entrada.par:
        corpo["par"] = entrada.par
    if entrada.pos is not None:
        corpo["pos"] = entrada.pos
    if entrada.esticada:
        corpo["esticada"] = True
        corpo["cabo"] = CABO_DECLARADO
    if entrada.filho is not None:
        corpo["filho"] = _entrada(entrada.filho)
    return corpo
