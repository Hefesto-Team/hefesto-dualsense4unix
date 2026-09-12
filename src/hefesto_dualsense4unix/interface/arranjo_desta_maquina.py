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
from collections.abc import Callable
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
CABO_DECLARADO = "extensão declarada por você"


def arranjo(
    agora: _dt.datetime | None = None,
    carregar: Callable[[], Any] | None = None,
    ler_o_barramento: Callable[[], Any] | None = None,
) -> dict[str, Any] | None:
    """O arranjo desta máquina, ou ``None`` quando não há o que desenhar.

    As duas fontes são injetáveis para que a régua meça esta tradução sem tocar
    no ``/sys`` da máquina de ninguém — e sem um ``monkeypatch`` que alcança
    só quem importar pelo mesmo caminho.

    ``None`` acontece em três casos, e os três são honestos:

    * o ``maquina.json`` não tem face declarada — não há gabinete a desenhar;
    * a leitura do barramento falhou — e censo vazio faria toda entrada parecer
      livre, que é o vazio mais convincente que existe;
    * o import falhou (árvore sem ``src``), que é o caso de quem roda a página
      solta no navegador.
    """
    try:
        from hefesto_dualsense4unix.integrations import mapa_das_portas
        from hefesto_dualsense4unix.integrations.censo_do_barramento import (
            ler_o_barramento as _ler,
        )
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina
    except Exception:
        return None

    try:
        documento = (carregar or carregar_maquina)()
        declarado = getattr(documento, "mapa", None)
        if declarado is None or not declarado.faces:
            return None
        censo = (ler_o_barramento or _ler)()
        bancada = mapa_das_portas.mesa_do_motor(declarado, censo)
    except Exception:
        return None

    mesa = bancada.mesa
    if not mesa.faces:
        return None

    quando = (agora or _dt.datetime.now()).strftime("%d/%m/%Y %Hh%M")
    caminhos = {aparelho.id: aparelho.id for aparelho in mesa.aparelhos}
    return {
        "quando": QUANDO_DE_AGORA.format(quando=quando),
        "aparelhos": [_aparelho(a) for a in mesa.aparelhos],
        "faces": _faces(mesa.faces),
        "mapa": dict(mesa.mapa),
        "leituras": {
            "agora": {"rotulo": ROTULO_DE_AGORA, "caminho": caminhos},
            "antes": {"rotulo": ROTULO_DE_ANTES, "caminho": dict(caminhos)},
        },
    }


def _aparelho(aparelho: Any) -> dict[str, Any]:
    """Um aparelho do motor nos cinco campos que a página LÊ.

    São cinco e não oito porque a página lê cinco: ``sementeDoCaminho``,
    ``usb`` e ``mA`` estão no censo de exemplo e nenhuma linha do JavaScript os
    consulta. Copiá-los aqui seria mobília — e mobília que alguém depois
    acreditaria estar sendo usada.
    """
    return {
        "id": aparelho.id,
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
