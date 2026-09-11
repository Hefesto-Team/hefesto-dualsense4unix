"""A aba Perfis não pode escrever num endereço que CONTÉM a página.

O QUE ELA FOTOGRAFOU, em 02/09/2026: a tabela `Controle / Ajuste próprio / ID
da peça` mostrando um **`2` sozinho**, e o trilho da prioridade substituído pela
frase *"Prioridade 1 de 200. O maior vence a disputa quando dois perfis poderiam
entrar."*. As duas coisas são o MESMO defeito, e ele não é de texto: é a página
se desmontando a cada meio segundo.

A CAUSA, uma só. O pintor termina em ``el.textContent = t``
(``hefesto_vivo.py:170``), e ``textContent`` num elemento que tem
FILHOS-ELEMENTO apaga todos eles::

    guarda.linhas          <tbody>   4 filhos   as 4 linhas, com 24 endereços dentro
    guarda.secao           <span>   16 vezes 2   o glifo SVG de cada seção
    editor.prioridade.dica <span>    2 filhos   o TRILHO e o número ao lado

A régua é geral e mecânica, e é o que a torna útil fora desta aba: **todo
endereço que o pacote emite tem de ser pintável na página PUBLICADA** — sem
ESTRUTURA dentro, ou então com um ``data-hef-alvo`` que não escreva
``textContent``.

E ela separa ESTRUTURA de DECORAÇÃO, porque a diferença decide um caso real: o
``guarda.nome`` do desenho traz dois ``<span class="pt">•</span>``, que é o
``monta.SEPARADOR`` — um ponto entre palavras, sem endereço e sem glifo.
Pintá-lo custa a COR dos dois pontos; **não** pintá-lo deixa na tela o nome de
um controle do MOCKUP para o controle que está na mesa dela — a sétima
reincidência do defeito mais caro desta casa. A troca é essa, e ela está
medida: dois pontos perdem a cor, dois controles ganham o nome.

A MORDIDA: devolva qualquer nome à emissão — apague uma linha de
``a10_perfis.NAO_PINTAVEIS`` — e ``test_nenhum_endereco_emitido_apaga_a_pagina``
reprova nomeando o endereço, a tag e o que sumiria.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

#: As tags HTML sem conteúdo — elas nunca abrem um nível na pilha do parser.
VAZIAS = frozenset({
    "br", "img", "input", "meta", "link", "hr", "source", "area", "base",
    "col", "embed", "track", "wbr",
})

#: OS ALVOS QUE NÃO ESCREVEM ``textContent``. São os do ``escrever()`` do piloto
#: (``hefesto_vivo.py``): a largura de uma barra, uma cor de fundo, o ``value``
#: de um campo, a marcação de um bloco, uma CLASSE, o ``color`` do elemento e a
#: variável ``--plastico``. Só o alvo padrão — o texto — apaga filhos.
#:
#: ERAM QUATRO ATÉ 03/09/2026, e a lista tinha envelhecido calada: o piloto
#: ganhou ``classe``, ``cor`` e ``plastico``, e nenhum dos três toca em
#: ``textContent`` — ``classe`` chama ``classList.toggle``, ``cor`` escreve
#: ``style.color`` e ``plastico`` escreve uma propriedade personalizada. Faltando
#: os três aqui, esta régua reprovava justamente quem tinha CURADO o defeito que
#: ela existe para pegar: pôr ``data-hef-alvo="classe"`` num ``<span>`` com glifo
#: dentro passou a ser acusado de apagar o glifo. É a armadilha desta casa —
#: *a régua confunde a PALAVRA com o ATO* — e ela desliga exatamente quando
#: alguém acerta.
#: E ``altura`` entrou em 05/09/2026, pelo mesmo motivo dos três de 03/09: ele
#: escreve ``style.height`` e não toca ``textContent``. É o alvo das ondas
#: sonoras da aba 02.
#: E ``atributo`` ENTROU EM 11/09/2026, pela TERCEIRA vez que esta lista
#: envelhece calada — depois dos três de 03/09 e do ``altura`` de 05/09. Ele
#: escreve ``el.setAttribute(nome, valor)`` (``hefesto_vivo.py:795``) e passa
#: antes pela guarda ``atributo_escrevivel``, que recusa nome fora da lista
#: curta; ``textContent`` não é tocado em nenhum dos dois ramos. A
#: PERFIS-LIMPA-01 o usou para devolver ao ``<table>`` a largura de coluna que
#: ela arrastou (``data-larguras``), e esta régua acusou de apagar a página
#: justamente quem estava fazendo a coisa certa. O padrão é sempre o mesmo:
#: *a régua confunde a PALAVRA com o ATO*, e desliga quando alguém acerta.
ALVOS_SEGUROS = frozenset({"largura", "altura", "fundo", "valor", "html",
                           "classe", "cor", "plastico", "atributo"})


class _Leitor(HTMLParser):
    """Para cada ``data-hef`` da página: a tag, quantos filhos-elemento tem,
    se algum deles é um ``<svg>``, e qual ``data-hef-alvo`` foi declarado."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[list[Any]] = []
        self.achados: list[dict[str, Any]] = []

    def _contar_no_pai(self, tag: str, d: dict[str, str | None]) -> None:
        """Um filho a mais no pai — e o que ele é, que é o que decide tudo.

        `decoracao` é o `<span class="pt">•</span>` do `monta.SEPARADOR`: um
        ponto entre palavras, sem endereço e sem glifo. Perdê-lo custa a COR do
        ponto e nada mais. Todo o resto — outro endereço, um `<svg>`, um
        `<tr>` — é estrutura, e perdê-lo é a página se desmontando.
        """
        if not self.pilha:
            return
        self.pilha[-1][2] += 1
        if tag == "svg":
            self.pilha[-1][3] = True
        if not (tag == "span" and (d.get("class") or "") == "pt"
                and not d.get("data-hef")):
            self.pilha[-1][5] += 1

    def _fechar(self) -> None:
        tag, endereco, filhos, tem_svg, alvo, estruturais = self.pilha.pop()
        if endereco:
            self.achados.append({"endereco": endereco, "tag": tag,
                                 "filhos": filhos, "svg": tem_svg, "alvo": alvo,
                                 "estruturais": estruturais})

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        self._contar_no_pai(tag, d)
        if tag in VAZIAS:
            return
        self.pilha.append(
            [tag, d.get("data-hef"), 0, False, d.get("data-hef-alvo"), 0]
        )

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        d = dict(attrs)
        self._contar_no_pai(tag, d)
        if d.get("data-hef"):
            self.achados.append({"endereco": d["data-hef"], "tag": tag,
                                 "filhos": 0, "svg": False,
                                 "alvo": d.get("data-hef-alvo"),
                                 "estruturais": 0})

    def handle_endtag(self, tag: str) -> None:
        if tag in VAZIAS:
            return
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                while len(self.pilha) > i:
                    self._fechar()
                return


def _pagina_publicada() -> list[dict[str, Any]]:
    """Os elementos endereçados do ``10-perfis.html`` que o produto RENDERIZA.

    `publicado=True` de propósito, e é o contrário do padrão desta casa: quem
    recebe a pintura é a página do pacote, não a bancada. Medir contra a
    bancada daria verde sobre um HTML que ela ainda não publicou — que é
    exatamente o buraco que este arquivo existe para tapar.
    """
    leitor = _Leitor()
    leitor.feed(
        onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    )
    return leitor.achados


#: A MESA DA RÉGUA — dois controles, com os endereços já MASCARADOS (octetos 4
#: e 5 zerados, a máscara desta casa). Nenhum endereço real de rádio entra em
#: arquivo versionado.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1,
     "cor": "cosmic-red", "nome": "Cosmic Red", "via": "BT",
     "transporte": "bt", "alvo": True, "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2,
     "cor": "starlight-blue", "nome": "Starlight Blue", "via": "USB",
     "transporte": "usb", "alvo": False, "mascara": "DualSense"},
]


def _perfil_de_regua() -> Any:
    """Um perfil com ajuste próprio SÓ do primeiro controle.

    O DISCO NÃO SERVE, e a medição é de 02/09/2026: no lar de mentira do
    `conftest.py`, `load_all_profiles()` devolve **zero** perfis nesta suíte —
    a semeadura dos presets não roda aqui. (A nota em `a10_perfis.PROVAS`
    afirma nove; ela vale no processo em que a semeadura já correu, não neste.)
    Uma régua que dependesse disso daria verde por vacuidade: sem perfil,
    `pacote_da_aba` devolve `guarda=[]` e a tabela nunca é medida.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    return Profile(
        name="régua", match=MatchAny(),
        controllers={MESA[0]["uniq"]: ControllerOverrides(
            rumble={"policy": "economia"})},
    )


def _emitidos(monkeypatch: Any = None) -> dict[str, Any]:
    """O que ``a10_perfis.pacote()`` manda pintar, com uma mesa de dois."""
    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    return a10_perfis.pacote(ctx)


@pytest.fixture(autouse=True)
def _perfil_no_lugar_do_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """O perfil da régua no lugar da pasta dela — e o `_ESCOLHIDO` limpo.

    O `_ESCOLHIDO` é estado de MÓDULO (é a linha aberta no editor, e vive no
    Python de propósito). Sem limpá-lo, um teste herdaria a escolha do
    anterior — que é pior que não ter prova nenhuma.
    """
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [_perfil_de_regua()])


def test_nenhum_endereco_emitido_apaga_a_pagina() -> None:
    """A régua-mãe: pintar um endereço não pode custar outro pedaço da tela."""
    por_endereco: dict[str, list[dict[str, Any]]] = {}
    for item in _pagina_publicada():
        por_endereco.setdefault(item["endereco"], []).append(item)

    estragos = []
    for chave, valor in _emitidos().items():
        if isinstance(valor, dict):  # `cobertura`, `sem_dono`: não são valor
            continue
        for elemento in por_endereco.get(chave, []):
            if (elemento["alvo"] or "") in ALVOS_SEGUROS:
                continue
            if elemento["estruturais"]:
                estragos.append(
                    f"{chave}: <{elemento['tag']}> tem {elemento['estruturais']} "
                    f"filho(s) de ESTRUTURA — pintar como texto apaga "
                    f"{'o glifo SVG' if elemento['svg'] else 'a marcação'} "
                    f"dentro dele"
                )
    assert not estragos, (
        "endereços que o pacote emite e a página publicada não sabe receber:\n  "
        + "\n  ".join(sorted(estragos))
    )


def test_nenhuma_porcentagem_vai_para_um_elemento_sem_largura() -> None:
    """Um `"37%"` só é BARRA onde o HTML declara `data-hef-alvo="largura"`.

    Sem o alvo o pintor cai no ramo padrão e escreve a porcentagem como TEXTO
    dentro da barra, deixando a LARGURA no valor do desenho. Foi o segundo
    defeito da Prioridade: `"0%"` escrito dentro de um `<span class="cheio">`
    de 5px que continuava com `style="width:90%"` — quase cheio, para um
    perfil em 1 de 200.
    """
    import re

    por_endereco: dict[str, list[dict[str, Any]]] = {}
    for item in _pagina_publicada():
        por_endereco.setdefault(item["endereco"], []).append(item)

    fora_do_alvo = [
        f"{chave} = {valor!r} — <{elemento['tag']}> sem data-hef-alvo='largura'"
        for chave, valor in _emitidos().items()
        if isinstance(valor, str) and re.fullmatch(r"\d+(\.\d+)?%", valor)
        for elemento in por_endereco.get(chave, [])
        if (elemento["alvo"] or "") != "largura"
    ]
    assert not fora_do_alvo, (
        "porcentagem escrita como texto em vez de virar largura:\n  "
        + "\n  ".join(fora_do_alvo)
    )


@pytest.mark.parametrize("endereco", a10_perfis.NAO_PINTAVEIS)
def test_os_que_nao_saem_continuam_na_pagina(endereco: str) -> None:
    """Eles NÃO são endereços mortos: a página os tem, e o dia em que o HTML
    ganhar o ``data-hef-alvo`` certo eles voltam. Se um sumir do HTML, a lista
    envelheceu calada — e é o defeito que esta casa persegue.

    O NOME PERDEU O NÚMERO em 02/09/2026: ele dizia "os quatro" enquanto a lista
    tinha três, e voltou a ter quatro no mesmo dia. Contagem escrita fora do
    lugar onde ela é decidida diverge no primeiro dia."""
    existe = {item["endereco"] for item in _pagina_publicada()}
    assert endereco in existe, (
        f"“{endereco}” saiu da página publicada e continua em "
        f"`a10_perfis.NAO_PINTAVEIS` — a lista virou fóssil"
    )


def test_a_tabela_da_guarda_nomeia_os_controles_da_mesa() -> None:
    """`guarda.nome` saía `["", ""]`: o `perfis_web` pede `rotulo` e a
    `mesa_do_estado` não devolve nenhum. É a cura de `_mesa_com_rotulo`."""
    fora = _emitidos()
    # AS QUATRO LINHAS SEMPRE — 05/09/2026, palavra dela: *"os svgs não deveriam
    # aparecer prós demais controles desconectados"*. O pacote passou a emitir a
    # tabela INTEIRA, e não só os controles da mesa, porque o `forEach` do
    # bootstrap escreve `''` no que sobra: `''` APAGA uma classe e nunca a
    # ACENDE, então o lugar vazio não tinha como ligar o `fora` que esconde os
    # glifos, nem como receber o rótulo `P3 • Desconectado` que ela pediu em
    # 31/08. Esta régua cobrava o tamanho da MESA; passa a cobrar o tamanho da
    # TABELA, com o conteúdo dos dois primeiros intacto.
    assert fora["guarda.nome"] == ["P1 • Cosmic Red • BT",
                                   "P2 • Starlight Blue • USB",
                                   "P3 • Desconectado",
                                   "P4 • Desconectado"]
    assert len(fora["guarda.id"]) == 4
    assert fora["guarda.id"][2:] == ["", ""], (
        "o lugar sem controle ganhou um ID — sem peça ali, não há o que mostrar")
    assert fora["guarda.vazio"] == ["", "", "sim", "sim"], (
        "a marca do lugar vazio não acende nos dois últimos: os glifos do "
        "mockup voltam à tela de um lugar sem controle")
    # E O CABEÇALHO CONTA OS DOIS: só o primeiro tem ajuste próprio.
    assert fora["perfis.com-ajuste"] == (
        "1 de 2 controles com ajuste próprio neste perfil")


def test_o_rotulo_da_guarda_e_o_mesmo_do_monta() -> None:
    """A ordem do rótulo tem UM dono — `monta.rotulo`, decisão dela de 26/08.

    Esta régua compara o rótulo em TEXTO PURO desta aba com o do gerador, com a
    marcação trocada pelo separador de texto. Se ela mudar a gramática
    (**marca • player • plástico • transporte**), reprova aqui em vez de a tela
    passar a discordar de si mesma.
    """
    monta = pytest.importorskip(
        "hefesto_dualsense4unix.interface.monta",
        reason="o gerador lê o repositório no import; num pacote instalado não há",
    )
    controle = {"jogador": 2, "nome": "Starlight Blue", "via": "USB"}
    do_gerador = monta.rotulo(controle, "curta").replace(
        monta.SEPARADOR, a10_perfis.SEPARADOR_EM_TEXTO
    )
    assert a10_perfis._rotulo_curto(controle) == do_gerador
