#!/usr/bin/env python3
"""A TABELA DOS 28 DA ABA 08 SÓ PINTA SE ELA VIVER DENTRO DE UM `<svg>`.

**03/09/2026.** Esta régua nasceu de um ponto cego MEDIDO, e ele deixava DOZE
dos 28 modelos dela sem a tinta que o mapa manda — com o portão da cor verde e
onze testes passando.

O QUE A CURA DA COR FEZ, e ela está certa: a folha dos 28 saiu de dentro de cada
desenho — onde vinha podada para um modelo — e passou a ir UMA vez na página. O
que viaja não é o `<style>` sozinho: é o `<defs id="cores-do-dualsense">`
inteiro, porque DEZ dos 28 modelos são pintados com `url(#hachura-sem-hex)` e
DOIS com gradiente (`casca-god-of-war-20th`, `casca-spider-man-2`).

FATO CORRIGIDO: a nota da cura diz *"oito dos 28"* para a hachura, e são DEZ.
O oito conta só a `--z-casca`; `fortnite` a traz em `--z-touch` e
`30th-anniversary` em `--z-simbolos`. Contados sobre as dez zonas — que é como
ela mapeou —, são dez, e com os dois gradientes o alvo desta régua é DOZE.

O PONTO CEGO É O ENVELOPE. Um `<defs>` solto no corpo do HTML **não é SVG**: o
analisador do navegador só entra no espaço de nomes SVG dentro de um `<svg>`, e
fora dele o `<pattern>` e o `<linearGradient>` viram `HTMLUnknownElement`. O
`id` continua no documento — `document.getElementById` acha —, mas o
`url(#hachura-sem-hex)` de um `fill` não tem tinta a que se ligar.

MEDIDO NO MOTOR (WebKit 2.52, `Gtk.OffscreenWindow`, a bancada da 08 carregada,
`data-colorway` escrito nos dois desenhos e `getComputedStyle` lido de volta nas
dez zonas), com o `<svg width="0">` de `TABELA_DAS_CORES` arrancado e a aba
regerada:

    chroma-teal        url("#hachura-sem-hex")        -> não é SVG   SEM TINTA
    god-of-war-20th    url("#casca-god-of-war-20th")  -> não é SVG   SEM TINTA
    …                                        ONZE dos 28 perderam o `fill`, e os
                                             17 com hex continuavam pintando

E AS RÉGUAS QUE JÁ EXISTIAM NÃO VIRAM NADA, que é a razão desta:

    scripts/check_a_cor_vem_do_aparelho.py --bancada --aba 08  ->  0    (verde)
    test_a_aba08_veste_o_desenho_do_controle_lido.py           ->  11 passed

Inclusive a que parece cobrir isto:
`test_a_hachura_e_os_gradientes_chegam_junto_com_a_folha` pergunta
`f'id="{ident}"' in html` — e a resposta é SIM na página quebrada, porque o
texto está lá. **A régua confunde ESTAR NO ARQUIVO com ESTAR NO ESPAÇO DE NOMES**,
que é a mesma forma das réguas que esta casa já derrubou: elas medem a PALAVRA
onde o defeito está no ATO.

O que esta cobra é o ATO, e sem abrir navegador: a pilha de tags diz se o `id`
citado por um `url(#…)` da folha nasceu **dentro** de um `<svg>`. É a mesma
pergunta que o motor responde, e é determinística.

A MORDIDA (as duas saídas estão no relatório da frente): troque o
`TABELA_DAS_CORES` da `aba08.py` por `f'  {_a_tabela_dos_28()}'`, sem o `<svg>`
de zero pixel, e regenere. O portão da cor continua em 0, os onze testes
continuam verdes, e as duas funções daqui reprovam nomeando os dez modelos.
"""
from __future__ import annotations

import pathlib
import re
import sys
from html.parser import HTMLParser

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"

#: A folha das cores da página. Mesma grafia da régua irmã de propósito — uma
#: segunda expressão para o mesmo alvo divergiria em silêncio.
FOLHA = re.compile(r'<style id="([^"]*cores-do-dualsense-folha)">(.*?)</style>', re.S)

#: A tinta que a folha pede por referência: `fill:url(#hachura-sem-hex)`.
TINTA_POR_REFERENCIA = re.compile(r"url\(\s*['\"]?#([^)'\"\s]+)")

#: O seletor com que a folha escolhe o modelo.
REGRA_DE_COLORWAY = re.compile(r'svg\[data-colorway="([^"]+)"\]')


class _OndeCadaIdNasceu(HTMLParser):
    """Guarda cada `id` da página e se ele nasceu DENTRO de um `<svg>`.

    CONTA `<svg>` EM VEZ DE MANTER UMA PILHA DE TAGS, e a escolha é medida: um
    `<path>` sem barra de fechamento não é tag vazia para o HTMLParser, e uma
    pilha genérica desanda a partir dali — tudo depois ficaria "dentro" de algo
    que já fechou. `<svg>`/`</svg>` são sempre pares no HTML gerado desta casa,
    e é só essa profundidade que decide a pergunta.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fundo = 0
        #: `id` -> nasceu dentro de um `<svg>`?
        self.ids: dict[str, bool] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "svg":
            self.fundo += 1
        ident = dict(attrs).get("id")
        if ident:
            # O PRIMEIRO NASCIMENTO VENCE, que é o que o `getElementById` faz.
            self.ids.setdefault(ident, self.fundo > 0)

    def handle_startendtag(self, tag: str,
                           attrs: list[tuple[str, str | None]]) -> None:
        dentro = self.fundo > 0 or tag == "svg"
        ident = dict(attrs).get("id")
        if ident:
            self.ids.setdefault(ident, dentro)

    def handle_endtag(self, tag: str) -> None:
        if tag == "svg" and self.fundo > 0:
            self.fundo -= 1


def _html() -> str:
    return BANCADA.read_text(encoding="utf-8")


def _folha() -> str:
    achado = FOLHA.search(_html())
    assert achado, (
        "a `08-conexoes` não publica folha de cores nenhuma — sem ela o alvo de "
        "atributo escreve um colorway que nada casa, e os 28 viram um cinza só")
    return achado.group(2)


def _onde_nasceram() -> dict[str, bool]:
    varredor = _OndeCadaIdNasceu()
    varredor.feed(_html())
    return varredor.ids


def test_a_folha_pede_tinta_por_referencia() -> None:
    """A régua tem sujeito: a folha da 08 cita `url(#…)`.

    Sem esta guarda, o dia em que ela medir o hex dos oito modelos de hachura
    deixaria as duas funções abaixo verdes por FALTA DE ALVO — o teste sem
    sujeito, que é o defeito de régua que esta casa mais derruba.
    """
    citados = set(TINTA_POR_REFERENCIA.findall(_folha()))
    assert citados, (
        "a folha da 08 não pinta nenhum modelo com `url(#…)`. Se o mapa dela "
        "deixou de usar hachura e gradiente, esta régua perdeu o alvo e as duas "
        "abaixo passaram a não medir nada — apague-as ou dê-lhes o alvo novo.")


def test_toda_tinta_citada_pela_folha_nasce_dentro_de_um_svg() -> None:
    """O `<defs>` das cores tem de viver num fragmento SVG, não solto no HTML.

    ESTE É O DEFEITO QUE O PORTÃO NÃO VÊ e que os onze testes da cura deixam
    passar: com o `<defs>` fora de um `<svg>`, o `id` continua no documento e o
    `url(#…)` do `fill` não acha tinta. Dez dos 28 modelos ficam sem cor — e só
    na máquina de quem tiver um deles, que é a definição de defeito invisível
    nesta bancada.
    """
    nasceram = _onde_nasceram()
    citados = sorted(set(TINTA_POR_REFERENCIA.findall(_folha())))
    fora = [i for i in citados if not nasceram.get(i, False)]
    ausentes = [i for i in citados if i not in nasceram]
    assert not ausentes, (
        f"a folha da 08 pinta com `url(#{ausentes[0]})` e a página não define "
        f"esse `id` em lugar nenhum: {ausentes}")
    assert not fora, (
        f"a folha da 08 pinta com `url(#…)` apontando para {fora}, que a página "
        f"define FORA de um `<svg>`. Fora do `<svg>` não há espaço de nomes SVG: "
        f"`<pattern>` e `<linearGradient>` viram `HTMLUnknownElement` e o `fill` "
        f"fica sem tinta. A cura é o `<svg width=\"0\">` que envolve o "
        f"`<defs id=\"cores-do-dualsense\">` em `aba08.TABELA_DAS_CORES`.")


def test_nenhum_modelo_do_mapa_dela_pede_tinta_que_a_pagina_nao_resolve() -> None:
    """A conta que ela lê: QUAIS dos 28 a página sabe pintar de verdade.

    A anterior mede o mecanismo; esta traduz o mecanismo para os NOMES da lei
    dela — *"cada user ao usar seu controle se toque disso que o app se adaptou
    ao controle dele"*. Um modelo cuja regra existe mas cuja tinta não resolve
    conta como não adaptado, e é o nome dele que diz de quem é o prejuízo.

    O casamento é por REGRA: cada `svg[data-colorway="…"]` da folha, e a tinta
    que o bloco daquele modelo pede. Não se lê o CSV aqui — a folha é a tabela
    dela publicada, e conferi-la contra si mesma é o que mantém a régua honesta
    no dia em que ela mapear o vigésimo nono modelo.

    ELA CONTA UM A MAIS QUE O MOTOR, e o número maior é o certo. Sob a mordida o
    motor viu ONZE modelos perderem o `fill`; esta acusa DOZE, e o décimo segundo
    é o `30th-anniversary`, cuja hachura mora em `--z-simbolos`. Essa zona é
    consumida por `color:`, e `url(#…)` não é valor válido de `color`: o motor
    descarta a declaração inteira **em silêncio** e os símbolos herdam a cor de
    cima. Não é perda de tinta — é uma tinta que nunca chegou a valer, o que
    para a lei dela dá no mesmo: a página não mostra o que o mapa cataloga.
    """
    folha = _folha()
    nasceram = _onde_nasceram()
    modelos = REGRA_DE_COLORWAY.findall(folha)
    assert len(set(modelos)) >= 28, (
        f"a folha da 08 traz {len(set(modelos))} modelos — ela mapeou 28, e uma "
        f"folha curta é a escolha cravada que a lei dela proíbe")
    perdidos = []
    for modelo in sorted(set(modelos)):
        bloco = "\n".join(
            linha for linha in folha.splitlines()
            if f'data-colorway="{modelo}"' in linha)
        for ident in sorted(set(TINTA_POR_REFERENCIA.findall(bloco))):
            if not nasceram.get(ident, False):
                perdidos.append(f"{modelo} (url(#{ident}))")
    assert not perdidos, (
        f"{len(perdidos)} modelos do mapa dela pedem tinta que a `08` não "
        f"resolve: {perdidos}. Quem tiver um deles vê o controle cru, que na "
        f"tela é indistinguível de 'não li a cor'.")
