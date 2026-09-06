"""A FOLHA DE USUÁRIO DA CASA — o CSS que o produto põe por cima das dez abas.

Ela vinha morando no módulo `ponte_da_tela`, e **mudou de casa em 06/09/2026**
(`A-REGUA-DA-PALAVRA-VE-O-PRODUTO-01`) por uma razão que não é de arrumação:

    A RÉGUA DA PALAVRA PRECISA SABER O QUE O PRODUTO ESCONDE.

`interface/olhar.py --palavra mesa --publicado` dizia **34 ocorrência(s)
visível(eis) em o produto** e o produto não mostrava NENHUMA delas: as 34 moram
dentro de `.nota` — o bilhete de projeto que o mockup carrega —, e a primeira
regra desta folha é `.nota{display:none !important}`. O instrumento respondia
sobre o ARQUIVO e dizia "o produto", que é a assinatura de instrumento falso
que esta casa persegue desde 04/09.

Para a régua perguntar ao DONO em vez de digitar `.nota` uma segunda vez, ela
tem de importar a folha — e a ponte importa `gi`, `Gtk` e `WebKit2` na
primeira linha. Uma régua que roda sem tela não pode exigir PyGObject, e uma
régua que lê o TEXTO do módulo com `ast` volta a responder sobre o fonte em vez
de sobre o valor. Sobra o caminho honesto: **a folha desce para um módulo sem
dependência de GUI**, e a ponte a importa de cá.

E POR QUE `interface/` E NÃO `gui/`: a janela GTK está sendo aposentada
(`D-0609-GTK-LEVA-INTEIRA` — *"a ideia sempre foi reaproveitar o que fiz no gtk
e não apontar nada mais pra lá mas pro html"*), e o inventário
`docs/data/o-que-ainda-aponta-para-a-janela.csv` já dá a `ponte_da_tela` como
`MOTOR-MUDA-DE-CASA`: ela sobrevive, mas sai de `gui/`. Nascer em `gui/` seria
dar à folha um endereço com data de validade — e o portão
`nada-aponta-para-a-janela` reprovou a primeira escrita desta sprint, que fazia
exatamente isso. A folha é da INTERFACE NOVA: é o CSS que o piloto põe sobre as
dez páginas dela.

`ponte_da_tela.FOLHA_DA_CASA` CONTINUA VALENDO como endereço — a ponte
reexporta o nome, e os dois usos dela (`JanelaDaAba(folha=…)` nos dois
construtores) não mudaram de forma. Isto não é gentileza: `docs/` e
`tests/unit/test_a_janela_estreita_nao_engole_o_desenho.py` citam aquele
endereço, e mudar o endereço de um valor por causa de uma régua seria a régua
mandando no produto.

QUEM ACRESCENTAR UMA REGRA AQUI acrescenta junto o que ela esconde: a
:func:`seletores_escondidos` lê `display:none` da própria folha, então uma
segunda regra de esconder passa a valer para a régua **sozinha**. O que ela
NÃO sabe ler ela RECUSA em voz alta — ver o `ValueError` de
:func:`seletores_escondidos`.
"""

from __future__ import annotations

import re

#: A folha de usuário da casa, e ela é do MÓDULO — não de uma aba.
#:
#: ``.nota{display:none}`` tira os bilhetes de projeto que o mockup carrega para
#: quem o lê no navegador; eles não são produto.
#:
#: ``select{appearance:none}`` é a cura sem a qual o WebKitGTK ignora as cores
#: do autor e desenha a caixa BRANCA do tema do sistema. São **117** ``<select>``
#: nas dez abas, e a aba Controles não tem nenhum: aqui a cura não se prova pelo
#: olho, ela viaja no módulo para as outras nove.
#: ``.hef-em-voo`` é o BOTÃO QUE ESTÁ TRABALHANDO — decisão dela, `09` [03],
#: 04/09/2026: *"o botão diz que está trabalhando"*, e fala **durante** a espera,
#: no lugar exato do clique. Há um gesto desta casa que leva 9,5 s
#: (``daemon.reload``, medido em 01/09) e nenhuma das dez abas tinha estado "em
#: voo": o clique sumia por nove segundos e meio e o segundo clique parecia o
#: primeiro.
#:
#: A REGRA MORA AQUI, NA FOLHA DO MÓDULO, e não no CSS das dez páginas: o piloto
#: é um só para as dez, e a classe tem de valer em todas sem que ninguém
#: republique desenho. ``cursor:progress`` é o que o ponteiro dela já diz em
#: qualquer aplicativo; a opacidade é o sinal que não depende de texto — quem
#: publicar um ``data-hef-em-voo`` ganha o rótulo por cima, quem não publicar
#: ganha o sinal mesmo assim.
#:
#: O ``!important`` NÃO É EXAGERO, e o número é medido (04/09/2026, foto
#: ``--oculta`` da aba 02): sem ele o ``cursor`` saiu **``pointer``**, e não
#: ``progress``. A razão é do cascade: uma folha de USUÁRIO **perde** para o
#: autor em declaração normal — só o ``!important`` do usuário vence. As dez
#: páginas declaram ``cursor:pointer`` nos botões, então a metade do sinal que
#: mora no ponteiro dela estava morta. É a mesma razão pela qual o ``.nota``
#: acima o carrega desde sempre.
#:
#: E O RÓTULO NÃO CABE EM BOTÃO DE ÍCONE — medido na mesma foto: publicado num
#: 🎙 de 20 px, o ``"Calando…"`` transborda. **Quem publica o
#: ``data-hef-em-voo`` é quem responde por caber**; num botão de ícone a
#: resposta certa é NÃO publicar e deixar o sinal da classe falar. A decisão
#: dela (`09` [03]) é sobre o "Atualizar", que tem 184 px de coluna.
#: E A PISCADA DO "DEU CERTO" MORA AQUI PELA MESMA RAZÃO — 05/09/2026, decisão
#: dela na `03-Q4`: *"O campo que você acabou de mexer ganha uma borda verde por
#: cerca de um segundo e meio e volta ao normal sozinho; nada muda de lugar e
#: nenhuma palavra nova entra na tela."*
#:
#: `outline` E NÃO BORDA MAIS GROSSA, e é metade da decisão: `outline` não ocupa
#: espaço na caixa, então o vizinho não anda. Uma `border-width` maior empurraria
#: a linha inteira, e "nada muda de lugar" é o que ela pediu junto com a cor.
#:
#: O `!important` pela MESMA razão medida do `cursor` acima: as dez páginas
#: declaram `border-color` nos campos — `.mudo-i.on` pede `var(--red)`
#: (`paginas/02-controles.html:1420`) e `select.modo` pede `var(--purple)`
#: (`paginas/03-gatilhos.html:1050`) —, e folha de usuário perde para o autor em
#: declaração normal. Sem ele o campo pisca nos elementos SEM cor declarada e
#: fica mudo justamente nos que têm.
#:
#: E A RÉGUA NÃO ALCANÇA ESTE PONTO, declarado em vez de esquecido:
#: `test_o_sucesso_calado_pisca_e_nao_fala` clica um `.mudo-i` APAGADO, que não
#: declara cor — arrancar o `!important` deixa aquela régua verde. Quem quiser
#: fechar o buraco mede um dos dois seletores acima.
#:
#: A COR TEM DONO e não se digita uma segunda: `--green:#50fa7b`
#: (`interface/topo.html:34`), com o mesmo fallback que o canal de sucesso já usa.
FOLHA_DA_CASA = (
    ".nota{display:none !important}"
    "select{appearance:none;-webkit-appearance:none}"
    ".hef-em-voo{opacity:.6 !important;cursor:progress !important}"
    ".hef-deu-certo{border-color:var(--green,#50fa7b) !important;"
    "outline:1px solid var(--green,#50fa7b) !important}"
)


#: Uma regra de CSS inteira: o que vem antes da chave e o que vem dentro dela.
#: A folha é uma linha só, sem `@media` e sem aninhamento — e é assim de
#: propósito: ela é a folha do PILOTO, não uma folha de tema.
_REGRA = re.compile(r"([^{}]+)\{([^{}]*)\}")

#: O SELETOR QUE ESTA CASA SABE LER: `.classe`, `#id` ou `tag`, um só, sem
#: combinador e sem descendente. Não é preguiça — é o que a régua consegue
#: HONRAR sem um motor de CSS. Ver a recusa em :func:`seletores_escondidos`.
_SIMPLES = re.compile(r"^[.#]?[A-Za-z][A-Za-z0-9_-]*$")


def seletores_escondidos(folha: str | None = None) -> tuple[str, ...]:
    """Os seletores que esta folha APAGA da tela (`display:none`).

    Ela existe para a régua da palavra perguntar ao dono em vez de digitar
    `.nota`: quem acrescentar uma segunda regra de esconder na
    :data:`FOLHA_DA_CASA` ganha a régua acompanhando sem tocar em régua nenhuma.

    A PROPRIEDADE É LIDA, NUNCA PROCURADA POR SUBSTRING, e a folha de hoje já
    traz a armadilha: ``select{appearance:none}`` contém a palavra ``none`` e
    NÃO esconde coisa nenhuma. Um ``"display:none" in folha`` também erraria no
    outro sentido, porque ``display : none`` com espaço é o mesmo CSS.

    RECUSA EM VOZ ALTA o seletor que não sabe honrar. Uma régua que ignorasse
    em silêncio um ``.nota > p`` novo voltaria a contar o que o produto esconde
    — que é o defeito exato que este módulo nasceu para fechar, e ele custou uma
    sprint.
    """
    # O PADRÃO SE RESOLVE AQUI DENTRO, e não na assinatura: um
    # `folha: str = FOLHA_DA_CASA` congela o valor no `def`, e quem trocasse a
    # folha em tempo de execução (uma régua, um ensaio) leria a de ontem.
    achados: list[str] = []
    for regra in _REGRA.finditer(FOLHA_DA_CASA if folha is None else folha):
        esconde = False
        for declaracao in regra.group(2).split(";"):
            prop, _, valor = declaracao.partition(":")
            if prop.strip().lower() != "display":
                continue
            if valor.replace("!important", "").strip().lower() == "none":
                esconde = True
        if not esconde:
            continue
        for seletor in regra.group(1).split(","):
            limpo = seletor.strip()
            if limpo:
                achados.append(limpo)
    desconhecidos = [s for s in achados if not _SIMPLES.match(s)]
    if desconhecidos:
        raise ValueError(
            "a FOLHA_DA_CASA esconde "
            + ", ".join(repr(s) for s in desconhecidos)
            + " e quem lê esta lista só sabe honrar `.classe`, `#id` e `tag`. "
            "ENSINE A RÉGUA antes de publicar a regra: "
            "`interface/frases_que_ela_baniu.texto_visivel_no_produto` conta "
            "como VISÍVEL tudo o que não souber esconder, e foi assim que o "
            "`--palavra mesa --publicado` acusou 34 ocorrências que o produto "
            "nunca mostrou."
        )
    return tuple(achados)
