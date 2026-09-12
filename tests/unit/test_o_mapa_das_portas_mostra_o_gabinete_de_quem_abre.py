"""O `mapa-das-portas` deixou de ser a tela de UMA máquina — e as réguas disso.

O DEFEITO, medido em 11/09/2026
--------------------------------

A página dizia **"o arranjo de agora"** sobre um censo de 24/08/2026 **cravado
em JavaScript**: oito aparelhos, três faces, um mapa e duas leituras digitados
dentro do HTML, todos de um gabinete só. Quem abrisse o produto noutro
computador lia a máquina de outra pessoa e não tinha como saber disso — a única
defesa da página era um `<p class="nota">`, e a primeira regra de
`folha_da_casa.FOLHA_DA_CASA` é `.nota{display:none !important}`.

A ordem dela, do mesmo dia, é o contrário:

    "a ideia é que todas as features mesmo do app funcionem nao so pra  (noqa-acento)
     mim mas pra qualquer outro user"   — citação literal dela, 11/09/2026

AS TRÊS PEÇAS QUE ESTE ARQUIVO MEDE
------------------------------------

* `interface/pagina_do_mapa.py` — o gerador. A página nasce da origem congelada
  mais `EDICOES` datadas, e o censo de exemplo tem dono em vez de estar
  digitado no HTML;
* `interface/arranjo_desta_maquina.py` — o produtor. Monta o gabinete de quem
  abriu a partir do que a pessoa declarou mais o que o kernel leu, ou devolve
  `None` quando não há o que desenhar;
* `interface/hefesto_vivo.py` — o piloto, que entrega um ao outro.

A igualdade entre as duas casas versionadas da página está em
`test_arranjo_invariantes.py`, que é onde ela sempre morou.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, pagina_do_mapa
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MapaDaMesa,
    PortaDeclarada,
)

# ── os dublês: um gabinete que não é o de ninguém ────────────────────────
#
# O CENSO É O DA PRODUÇÃO, não uma classe escrita aqui. A primeira versão deste
# arquivo montou um `_Aparelho` à mão com os campos que pareciam bastar, e ele
# era MAIS POBRE que o do produto: faltava `e_hub`, que é a primeira coisa que
# `_classe_do_motor` pergunta. Um dublê mais pobre que o produto é a armadilha
# que esta casa já pagou várias vezes — ele responde o que o autor do teste
# imaginou, não o que o código encontra.

#: A tripla do kernel que faz do aparelho um adaptador Bluetooth, para o motor:
#: `mapa_das_portas._CLASSE_DO_MOTOR_POR_TRIPLA`. Ela é citada e não copiada —
#: se aquela tabela mudar, esta régua acusa em vez de seguir medindo o de antes.
_TRIPLA_BT = ("e0", "01", "01")
_TRIPLA_TECLADO = ("03", "01", "01")
_TRIPLA_MOUSE = ("03", "01", "02")


def _aparelho(no: str, especie: str, produto: str,
              tripla: tuple[str, str, str] = _TRIPLA_BT) -> Aparelho:
    return Aparelho(
        no=no, nome_do_kernel=no, produto=produto, especie=especie,
        classe=tripla[0], subclasse=tripla[1], protocolo=tripla[2],
        velocidade_mbps=480.0,
    )


class _Documento:
    def __init__(self, mapa: MapaDaMesa) -> None:
        self.mapa = mapa


def _gabinete() -> tuple[_Documento, Censo]:
    """Duas entradas declaradas, dois aparelhos lidos. Não é o de ninguém."""
    mapa = MapaDaMesa(
        faces=[FaceDeclarada(nome="Traseira", portas=["1", "2"], perto=True)],
        portas={"1": PortaDeclarada(caminho="9-1"), "2": PortaDeclarada(caminho="9-2")},
    )
    censo = Censo(aparelhos=(
        _aparelho("9-1", "Bluetooth", "Adaptador de prova"),
        _aparelho("9-2", "Teclado", "Teclado de prova", _TRIPLA_TECLADO),
    ))
    return _Documento(mapa), censo


# ── 1. sem declaração não há gabinete, e isso se DIZ ─────────────────────


def test_sem_face_declarada_o_arranjo_nao_existe() -> None:
    """`None` é a resposta honesta — e a outra metade prova que não é vacuidade.

    O número da entrada no metal (`9`, `15a`) não sai de leitura nenhuma: está
    medido em `integrations/mapa_das_portas` que duas entradas da frente de uma
    mesma placa respondem `panel`, `horizontal_position` e `vertical_position`
    IDÊNTICOS. Sem face declarada, desenhar um gabinete seria inventá-lo.

    UMA RÉGUA QUE SÓ MEDE O `None` MEDIRIA UM IMPORT QUEBRADO com a mesma cara.
    Por isso o caso de baixo: com uma face declarada, o arranjo VEM.
    """
    vazio = _Documento(MapaDaMesa())
    _, censo = _gabinete()
    assert arranjo_desta_maquina.arranjo(
        carregar=lambda: vazio, ler_o_barramento=lambda: censo) is None

    documento, censo = _gabinete()
    veio = arranjo_desta_maquina.arranjo(
        carregar=lambda: documento, ler_o_barramento=lambda: censo)
    assert veio is not None, (
        "com face declarada e censo lido o arranjo tem de vir — se ele não vem, "
        "o `None` de cima não prova nada")


def test_a_leitura_que_falha_nao_vira_gabinete_vazio() -> None:
    """Censo que estourou é `None`, nunca um gabinete sem nada ligado.

    A diferença é a que `a08_conexoes._censo` já escreve: um censo VAZIO faria
    toda entrada parecer livre, e a página publicaria "nada está plugado" sobre
    uma leitura que não aconteceu.
    """
    documento, _ = _gabinete()

    def estourou() -> Any:
        raise OSError("o /sys não respondeu")

    assert arranjo_desta_maquina.arranjo(
        carregar=lambda: documento, ler_o_barramento=estourou) is None


# ── 2. a forma que a página LÊ, medida na página ─────────────────────────


def _a_porta() -> str:
    """O JavaScript da porta, conferido contra a página que foi gerada.

    Ele é lido do dono (`pagina_do_mapa.ABRE_A_PORTA`) e não recortado do HTML
    por marcadores: recortar por marcador dá `""` calado no dia em que o
    marcador mudar, e uma régua que lê o vazio passa por vacuidade. O `assert`
    abaixo é o que garante que o dono e a página não se separaram.
    """
    porta = pagina_do_mapa.ABRE_A_PORTA
    assert porta in pagina_do_mapa.pagina(), (
        "o JavaScript da porta não está na página gerada — ou a edição que o "
        "acrescenta caiu, ou ele passou a ser montado noutro lugar")
    return porta


def test_o_arranjo_traz_tudo_o_que_a_pagina_le_e_nada_alem() -> None:
    """Os campos do produtor e os que o desenho consome são os MESMOS.

    Esta é a régua que impede as duas pontas de se afastarem sem um erro: a
    página lê `f.faces` e o produtor manda `faces`. Se alguém renomear de um
    lado, o outro recebe `undefined` — e `undefined` desenha um gabinete sem
    entrada nenhuma, calado, que se lê como *"não tenho nada ligado"*.

    Os dois lados são LIDOS, nunca digitados aqui: os campos saem do JavaScript
    da página e as chaves saem de uma chamada de verdade ao produtor.
    """
    documento, censo = _gabinete()
    veio = arranjo_desta_maquina.arranjo(
        carregar=lambda: documento, ler_o_barramento=lambda: censo)
    assert veio is not None

    porta = _a_porta()
    lidos = set(re.findall(r"\b(?:f|fonte)\.(\w+)", porta))
    assert len(lidos) >= 5, (
        f"li {len(lidos)} campos na porta — o seletor ficou cego e a régua "
        "passaria por vacuidade")
    # `controles` é o simulador: a página o aceita e o produtor não o manda,
    # de propósito — ver `pagina_do_mapa.CENSO_DE_EXEMPLO["controles"]`.
    assert lidos - {"controles"} == set(veio), (
        "o que a página lê e o que o produtor manda se afastaram.\n"
        f"  a página lê: {sorted(lidos)}\n"
        f"  o produtor manda: {sorted(veio)}")
    assert set(pagina_do_mapa.CAMPOS_DO_ARRANJO) <= set(veio), (
        "o produtor não manda algum campo que a própria página EXIGE em "
        "`window.hefestoArranjo` — a entrega seria recusada em voz alta, o que "
        "é melhor que passar, mas não é o que se quer")


def test_a_entrada_esticada_leva_o_cabo_que_o_desenho_escreve() -> None:
    """Sem o `cabo`, o desenho escreve `undefined` ao lado da entrada.

    `porta.filho.cabo` é lido sem defesa no JavaScript: ele vai direto para o
    HTML da linha do extensor. O exemplo diz "extensor de 1 m" porque alguém
    mediu aquele cabo; aqui o comprimento não se sabe, e a frase diz só o que é
    verdade.
    """
    mapa = MapaDaMesa(
        faces=[FaceDeclarada(nome="Hub", portas=["1", "1a"])],
        portas={"1": PortaDeclarada(caminho="9-1"),
                "1a": PortaDeclarada(caminho="9-2", filha_de="1")},
    )
    censo = Censo(aparelhos=(
        _aparelho("9-1", "Bluetooth", "Adaptador de prova"),
        _aparelho("9-2", "Bluetooth", "Adaptador de prova"),
    ))
    veio = arranjo_desta_maquina.arranjo(
        carregar=lambda: _Documento(mapa), ler_o_barramento=lambda: censo)
    assert veio is not None
    filhas = [p["filho"] for f in veio["faces"] for p in f["portas"] if "filho" in p]
    assert filhas, "a entrada-filha declarada não chegou ao desenho"
    for filha in filhas:
        assert filha.get("cabo") == arranjo_desta_maquina.CABO_DECLARADO
        assert filha.get("esticada") is True


def test_uma_face_so_e_dona_da_faixa_do_pc() -> None:
    """Duas donas mostrariam a mesma bandeja duas vezes; zero a esconderia.

    A bandeja é onde aparecem os aparelhos que estão numa entrada direta do PC
    sem lugar declarado — os que precisam exatamente de um clique dela.
    """
    mapa = MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente", portas=["1"]),
               FaceDeclarada(nome="Traseira", portas=["2", "3"])],
        portas={"1": PortaDeclarada(caminho="9-1"),
                "2": PortaDeclarada(caminho="9-2"),
                "3": PortaDeclarada(caminho="9-3")},
    )
    censo = Censo(aparelhos=(
        _aparelho("9-1", "Bluetooth", "Adaptador de prova"),
        _aparelho("9-2", "Teclado", "Teclado de prova", _TRIPLA_TECLADO),
        _aparelho("9-3", "Mouse", "Mouse de prova", _TRIPLA_MOUSE),
    ))
    veio = arranjo_desta_maquina.arranjo(
        carregar=lambda: _Documento(mapa), ler_o_barramento=lambda: censo)
    assert veio is not None
    donas = [f["nome"] for f in veio["faces"] if f.get("donaDaFaixaPc")]
    assert len(donas) == 1, f"faces donas da faixa do PC: {donas}"
    assert donas[0] == "Traseira", "a dona é a face do PC com mais entradas"


# ── 3. o cabeçalho diz de QUANDO é o que está na tela ────────────────────


def test_o_cabecalho_diz_de_quando_e_o_que_esta_na_tela() -> None:
    """A única defesa da página contra ser lida como verdade de qualquer máquina.

    As duas frases moram uma ao lado da outra em `pagina_do_mapa` e
    `arranjo_desta_maquina`, e as duas são diferentes de propósito: "exemplo" e
    "deste computador" não podem sair iguais, senão a distinção não existe.

    E A CLASSE NÃO PODE SER `.nota`, que é o defeito inteiro: a folha do produto
    apaga `.nota` com `!important`, e no Chrome o aviso aparecia enquanto na
    tela dela não. Quem responde o que o produto esconde é o dono da folha.
    """
    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    pagina = pagina_do_mapa.pagina()
    linha = re.search(r'<p class="([^"]+)" id="de-quando">([^<]+)</p>', pagina)
    assert linha, "a linha que diz de quando é a leitura sumiu do cabeçalho"
    classe, texto = linha.group(1), linha.group(2)
    assert texto == pagina_do_mapa.QUANDO_DO_EXEMPLO
    escondidas = {s.lstrip(".").split()[-1] for s in seletores_escondidos()}
    assert classe not in escondidas, (
        f"a folha do produto esconde `.{classe}` — o aviso da página volta a "
        f"existir só no Chrome. O que ela esconde hoje: {sorted(escondidas)}")

    documento, censo = _gabinete()
    veio = arranjo_desta_maquina.arranjo(
        agora=datetime.datetime(2026, 9, 11, 23, 4),
        carregar=lambda: documento, ler_o_barramento=lambda: censo)
    assert veio is not None
    assert veio["quando"] != pagina_do_mapa.QUANDO_DO_EXEMPLO, (
        "a leitura desta máquina diz a mesma coisa que o exemplo — e aí a "
        "página não distingue mais uma da outra")
    assert "11/09/2026 23h04" in veio["quando"]


# ── 4. a porta, e o que ela recusa ───────────────────────────────────────


def test_a_pagina_abre_a_porta_e_recusa_meio_arranjo() -> None:
    """`window.hefestoArranjo` existe, e confere o que recebe antes de desenhar.

    Meio arranjo desenharia um gabinete sem entradas, e isso se lê como *"não
    tenho nada ligado"* — o vazio mais convincente que existe.
    """
    pagina = pagina_do_mapa.pagina()
    assert "window.hefestoArranjo = function (dado)" in pagina
    assert "CAMPOS_DO_ARRANJO.filter" in pagina, (
        "a porta parou de conferir o que recebe")
    assert 'throw new Error("arranjo incompleto' in pagina, (
        "a recusa virou silêncio — e silêncio aqui vira gabinete vazio na tela")
    for campo in pagina_do_mapa.CAMPOS_DO_ARRANJO:
        assert f'"{campo}"' in pagina


def test_o_piloto_entrega_o_arranjo_a_esta_pagina_e_so_a_ela() -> None:
    """O piloto tem o gesto, e ele é disparado pelo nome DESTA página.

    A ligação é lida do fonte do próprio método em vez de digitada: uma régua
    que escrevesse a condição aqui estaria conferindo a si mesma.
    """
    import inspect

    from hefesto_dualsense4unix.interface import hefesto_vivo

    assert hasattr(hefesto_vivo.Piloto, "_entregar_o_arranjo")
    fonte = inspect.getsource(hefesto_vivo.Piloto._instalado)
    assert "arranjo_desta_maquina.PAGINA" in fonte, (
        "o piloto não decide pela PÁGINA — ou ele entrega a todas, ou o nome "
        "está digitado num segundo lugar")
    assert "self._entregar_o_arranjo()" in fonte
    assert arranjo_desta_maquina.PAGINA == "mapa-das-portas.html"

    # e a falha não pode ser calada: ela vai para o relato, como a da dica
    entrega = inspect.getsource(hefesto_vivo.Piloto._arranjo_entregue)
    assert "cegueiras" in entrega, (
        "uma entrega que falha calada deixa a página com o exemplo e ninguém "
        "sabendo que a leitura desta máquina não chegou")


# ── 5. o gerador não deixa uma edição errar o alvo ───────────────────────


def test_o_gerador_recusa_a_edicao_que_erra_o_alvo() -> None:
    """A MORDIDA do gerador: `str.replace` que não acha nada não levanta nada.

    É assim que uma edição envelhece em silêncio — a frase muda de lado na
    origem, a troca deixa de acontecer, e a declaração continua no lugar
    dizendo que aconteceu.
    """
    inteiras = pagina_do_mapa.EDICOES
    fantasma = pagina_do_mapa.Edicao(
        antes="isto não está na origem congelada em lugar nenhum",
        depois="tanto faz",
        porque="11/09/2026 — dublê desta régua",
    )
    pagina_do_mapa.EDICOES = (*inteiras, fantasma)
    try:
        with pytest.raises(SystemExit) as caiu:
            pagina_do_mapa.pagina()
    finally:
        pagina_do_mapa.EDICOES = inteiras
    assert "0 vez(es)" in str(caiu.value)
    assert "dublê desta régua" in str(caiu.value), (
        "a recusa não diz QUAL edição errou o alvo — e sem isso quem lê tem de "
        "procurar entre todas")


def test_a_cor_de_cada_especie_e_lida_do_censo_e_nao_digitada() -> None:
    """Uma segunda tabela de cor divergiria da primeira, e ninguém veria.

    O desenho pinta o chip com `ap.cor`; o arranjo vivo precisa da mesma cor.
    A tabela sai do censo de exemplo por leitura — a mordida é trocar a cor no
    censo e ver a tabela acompanhar sozinha.
    """
    do_censo = {a["classe"]: a["cor"] for a in pagina_do_mapa.CENSO_DE_EXEMPLO["aparelhos"]}
    assert do_censo == pagina_do_mapa.CORES_POR_CLASSE
    assert do_censo["hub"] == pagina_do_mapa.COR_SEM_CLASSE

    documento, censo = _gabinete()
    veio = arranjo_desta_maquina.arranjo(
        carregar=lambda: documento, ler_o_barramento=lambda: censo)
    assert veio is not None
    for aparelho in veio["aparelhos"]:
        esperada = do_censo.get(aparelho["classe"], pagina_do_mapa.COR_SEM_CLASSE)
        assert aparelho["cor"] == esperada, (
            f"{aparelho['id']} ({aparelho['classe']!r}) saiu com "
            f"{aparelho['cor']} e o desenho pinta {esperada}")
