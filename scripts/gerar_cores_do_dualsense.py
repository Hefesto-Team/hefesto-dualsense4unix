#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GERADOR — a cor do plástico sai do CSV e entra no desenho, zona por zona.

O DEFEITO QUE ELE MATA (27/08/2026). As cinco cores que o produto conhecia eram
CSS escrito à mão, numa zona só (`.corpo` / `[id$="-touchpad"] .peca`), repetido
em `src/hefesto_dualsense4unix/interface/topo.html:295-326` e em `mapa.py`. Duas
consequências, e as duas já custaram:

  1. **nenhuma régua sabia dizer se o hex ali estava certo**, porque não havia
     com o que comparar — o Cosmic Red do desenho era `#b11f54` e a amostragem
     de 27/08 devolveu `#A51C48`, uma distância de 17 que ninguém tinha como ver;
  2. **o desenho pintava o controle inteiro de uma cor**, e o DualSense não é de
     uma cor só: no Cosmic Red a casca é carmim, o painel central é PRETO e os
     analógicos são pretos.

Agora a cor é DADO. Três arquivos, um dono cada, e este script os cruza:

    docs/data/cores-do-dualsense.csv   modelo + zona -> hex        (as CORES)
    docs/data/pecas-do-dualsense.csv   peça -> zona                (as PEÇAS)
    assets/control-svg/dualsense.svg   o desenho dela              (a GEOMETRIA)

O que ele escreve no SVG, e SÓ isto:

  * `class="z-<zona>"` em cada grupo de peça, e `z-simbolos` nos quatro glifos da
    face — as zonas nomeadas, legíveis também na árvore do editor dela;
  * um `<defs id="cores-do-dualsense">` com a hachura do SEM-HEX, os gradientes
    das cascas de duas cores, e o `<style>` dos 28 modelos.

**Ele não toca em geometria.** Nenhum `d`, nenhum `transform`, nenhum `x/y`. É
por isso que ele pode rodar depois de todo `importar.py` sem risco: o que ela
desenha volta intacto, e as zonas são reaplicadas por cima.

    scripts/gerar_cores_do_dualsense.py            gera
    scripts/gerar_cores_do_dualsense.py --check    reprova se o disco divergir

O PORTÃO que mede o resultado é `scripts/check_cores_do_dualsense.py`. Este aqui
gera; aquele confere no navegador, que é onde a cor de verdade acontece.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

#: A CONTA DA LEGIBILIDADE É A DO PRODUTO, e não uma segunda escrita aqui.
#: `tom_para_a_borda` já resolve exatamente este caso — "Midnight Black pintado
#: cru não é uma borda preta: é a AUSÊNCIA de borda" — com a mistura com branco
#: (e não a subida de luminosidade em HLS, que devolve azul elétrico para o
#: quase-preto). Reusar é o que impede a terceira tabela de contraste desta casa.
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    FUNDO_DO_CARD,
    RAZAO_DA_BORDA,
    tom_para_a_borda,
)

CSV_CORES = RAIZ / "docs/data/cores-do-dualsense.csv"
CSV_PECAS = RAIZ / "docs/data/pecas-do-dualsense.csv"
#: os dois são o MESMO arquivo (md5 igual, e o `importar.py` grava nos dois).
#: Gerar num só deixaria o mapa e o produto com desenhos diferentes.
ALVOS = (
    RAIZ / "assets/control-svg/dualsense.svg",
    RAIZ / "src/hefesto_dualsense4unix/interface/ds_limpo.svg",
)

#: As zonas do `cores-do-dualsense.csv` que têm SUPERFÍCIE no desenho, na ordem
#: em que o CSS as escreve. A ordem não é estética: zona que se sobrepõe a outra
#: tem de vir depois, e `simbolos` é a última porque ela mora POR CIMA dos botões
#: da face.
ZONAS_DE_SUPERFICIE = (
    "casca", "painel", "touch", "gatilhos", "dpad", "analogicos",
    "botoes_face", "simbolos",
)

#: `detalhe` é arte impressa — friso, decalque, a teia do Spider-Man, os olhos do
#: Astro Bot. Não é uma superfície do desenho, e inventar uma forma para ela
#: seria inventar geometria. ZONA DECLARADA SEM ALVO, e o portão sabe disso.
ZONAS_SEM_ALVO = ("detalhe",)

#: As zonas do CSV de cores que a coluna `zona` do CSV de peças NÃO nomeia,
#: porque a peça é uma só: `#corpo` recebe as duas metades.
ZONAS_DA_CASCA = ("casca_esq", "casca_dir")

#: A zona `simbolos` é a impressão dos quatro botões da face. Ela não é peça: é o
#: GLIFO em cima da peça. Derivada, e não uma coluna a mais no CSV de peças.
GLIFOS_DA_FACE = ("glifo-triangle", "glifo-circle", "glifo-square", "glifo-cross")

#: O fundo contra o qual a legibilidade é medida, e o piso — os dois são do
#: produto (`integrations/cor_do_plastico.py`), não desta casa de geração:
#: `FUNDO_DO_CARD` = #282a36 e `RAZAO_DA_BORDA` = 2,2:1. O fundo do mapa
#: (`--app-bg`, #21222c) é ainda mais escuro, então o piso serve para os dois.
_FUNDO = FUNDO_DO_CARD
_PISO = RAZAO_DA_BORDA

#: A cor de quem não foi medido. Não é "mais um cinza": é a marca de ausência, e
#: existe pelo mesmo princípio da ONDA-CONEXOES-08 — "sem cor conhecida, sem cor
#: inventada". Quatro modelos (Ghost of Yōtei, Marathon, Genshin, 007) têm o CSV
#: incompleto por falta de amostragem, e a tela tem de DIZER isso.
NAO_MEDIDA = "#4A4A52"

#: O que este script escreve, e o que fica fora dele. Um bloco só — pattern,
#: gradientes e folha juntos — porque duas âncoras num arquivo com vários
#: `</defs>` é como um gerador passa a inserir no lugar errado sem avisar.
ABRE = '<defs id="cores-do-dualsense">'
FECHA = "</defs>"

#: O que pinta dentro de um grupo de zona. `:not([fill="none"])` preserva o botão
#: PS, que é `sem-tinta` por decisão dela (27/08: "Remove o circulo e Deixa só o
#: Glifo do PS pra ser o Botão"), e os quatro glifos da face, que são traço puro.
PINTAVEL = ':is(path,rect,circle,ellipse,polygon):not([fill="none"])'

#: `!important` NÃO É PREGUIÇA, e há medição: três peças do desenho dela trazem a
#: cor dentro do `style` inline — `share`, `options` e `mic` (este último em
#: `rgb(216,216,216)`). Style inline vence qualquer folha; sem `!important` essas
#: três ficariam CARMIM em todo colorway, inclusive no White. É a mesma cicatriz
#: que o `mapa.py` já carrega escrita.
BANG = " !important"


def _le(caminho: pathlib.Path) -> list[dict[str, str]]:
    linhas = [x for x in caminho.read_text().splitlines() if x and not x.startswith("#")]
    return list(csv.DictReader(linhas))


def zonas_das_pecas() -> dict[str, list[str]]:
    """zona -> ids de peça, lido da coluna `zona` do CSV de peças.

    `luz` (lightbar e indicador de jogador) e `-` (os cinco `feat-*`) ficam de
    fora de propósito: luz não é plástico, e marcador de região não tem
    superfície. Pintá-los com a cor do casco foi o que os fazia sumir sobre a
    borda do touchpad — está medido no `mapa.py`.
    """
    fora: dict[str, list[str]] = {}
    for p in _le(CSV_PECAS):
        z = p["zona"]
        if z in ("-", "luz", ""):
            continue
        fora.setdefault(z, []).append(p["id"])
    return fora


def modelos() -> dict[str, dict[str, dict[str, str]]]:
    """id do modelo -> zona -> a linha inteira do CSV de cores."""
    fora: dict[str, dict[str, dict[str, str]]] = {}
    for c in _le(CSV_CORES):
        fora.setdefault(c["id"], {})[c["zona"]] = c
    return fora


def _tinta(linha: dict[str, str] | None) -> str:
    """O `fill` de uma zona: hex, hachura, ou a marca de não-medida.

    As duas respostas que NÃO são um hexadecimal são o ponto desta função:
      * `SEM-HEX`  — iridescente, camuflado, metálico, arte. O CSV manda, com
        todas as letras, não inventar um fill. Hachura, e a lista avisa.
      * ausente    — a zona não tem linha no CSV. Não medido não é sem cor.
    """
    if linha is None:
        return NAO_MEDIDA
    if linha["grau"] == "SEM-HEX" or not linha["hex"].strip():
        return "url(#hachura-sem-hex)"
    return linha["hex"].strip()


def e_split(zonas: dict[str, dict[str, str]]) -> bool:
    """A casca tem duas cores? Spider-Man 2 e God of War 20th têm."""
    esq, dir_ = zonas.get("casca_esq"), zonas.get("casca_dir")
    return bool(esq and dir_ and _tinta(esq) != _tinta(dir_))


def gerar_defs(mods: dict[str, dict[str, dict[str, str]]]) -> str:
    """A hachura do SEM-HEX e um gradiente por casca de duas cores.

    O corte é DURO — dois `stop` no mesmo offset —, e não um degradê: as cascas
    do Spider-Man 2 e do God of War 20th são duas metades, não uma transição.
    """
    partes = [
        '    <pattern id="hachura-sem-hex" width="4" height="4"'
        ' patternUnits="userSpaceOnUse" patternTransform="rotate(45)">',
        '      <rect width="4" height="4" fill="#5A5A64"/>',
        '      <rect width="2" height="4" fill="#8A8A96"/>',
        "    </pattern>",
    ]
    for mid in sorted(mods):
        if not e_split(mods[mid]):
            continue
        # os stops também passam pela conta da legibilidade: a metade Venom do
        # Spider-Man 2 é `#1A1A1C`, e crua ela some no fundo escuro igual às
        # outras zonas — a casca partida ficaria com uma metade só.
        a = legivel(_tinta(mods[mid]["casca_esq"]))
        b = legivel(_tinta(mods[mid]["casca_dir"]))
        partes += [
            f'    <linearGradient id="casca-{mid}" x1="0" y1="0" x2="1" y2="0">',
            f'      <stop offset="50%" stop-color="{a}"/>',
            f'      <stop offset="50%" stop-color="{b}"/>',
            "    </linearGradient>",
        ]
    return "\n".join(partes)


def legivel(tinta: str) -> str:
    """A mesma cor, clareada só o quanto for preciso para se ver no fundo escuro.

    **ELA REPAROU, e o defeito era este** (27/08/2026): com a cor pintando zona
    por zona, *"os glifos, borda do touchpad, caixa de som, botão de microfone,
    analógico (…) botões de share e options, glifos dos botões da face"* sumiram
    do desenho no Cosmic Red. E estava CERTO pelo dado: naquele modelo o painel,
    o touch, os analógicos e os símbolos são `#1A1A1C` — **preto**. O que o dado
    não sabia é que **este desenho é de LINHA sobre fundo escuro**: preto sobre
    `#282a36` dá razão de contraste **1,22**, e a peça deixa de existir.

    É o mesmo defeito que `tom_para_a_borda` já resolve para a borda do card —
    *"Midnight Black pintado cru não é uma borda preta: é a AUSÊNCIA de borda"* —
    e por isso a conta é a DELE, importada, e não uma segunda escrita aqui.
    Acima do piso a cor passa **intacta**: White e Starlight Blue não são mexidos.

    O dado cru não se perde: ele continua em `--z-<zona>-crua`, para quem precisa
    da cor do plástico e não da cor que se vê.
    """
    if not tinta.startswith("#"):
        return tinta                       # gradiente, hachura: não são cor
    return tom_para_a_borda(tinta) or tinta


def tintas_do_modelo(
    mid: str, zonas: dict[str, dict[str, str]]
) -> dict[str, str]:
    """zona -> o valor de `fill` daquele modelo, já resolvido.

    Cada zona sai em DUAS variáveis: `--z-<zona>-crua` é o dado do CSV, intocado,
    e `--z-<zona>` é a cor **legível** (ver `legivel`), que é a que pinta.

    `casca` é a única que pode não ser uma cor: quando as duas metades diferem,
    ela é o gradiente de corte duro. `casca_solida` acompanha, com o hex da
    metade esquerda, para quem precisa de UMA cor — a borda de identidade da
    peça, o traço que arredonda o bico do punho, o chip da fita.
    """
    cru: dict[str, str] = {}
    for zona in ZONAS_DE_SUPERFICIE:
        if zona == "casca":
            cru["casca"] = (f"url(#casca-{mid})" if e_split(zonas)
                            else _tinta(zonas.get("casca_esq")))
            cru["casca-solida"] = _tinta(zonas.get("casca_esq"))
        else:
            cru[zona] = _tinta(zonas.get(zona))
    fora: dict[str, str] = {}
    for k, v in cru.items():
        fora[f"{k}-crua"] = v
        fora[k] = legivel(v)
    return fora


def _regra(mid: str, zona: str) -> str:
    """Uma linha de folha. `simbolos` pinta a PALAVRA, não o preenchimento.

    Os quatro glifos da face são traço puro — `fill="none" stroke="currentColor"`.
    Pintar `fill` neles não faz nada, e pintar `stroke` os arrancaria da folha do
    mapa, que usa `currentColor` para acender no hover. `color` resolve os dois:
    o traço herda a cor do plástico em repouso, e o hover continua mandando.
    """
    if zona == "simbolos":
        return f'    svg[data-colorway="{mid}"] .z-simbolos{{color:var(--z-simbolos){BANG}}}'
    return (f'    svg[data-colorway="{mid}"] .z-{zona} {PINTAVEL}'
            f"{{fill:var(--z-{zona}){BANG}}}")


def gerar_style(
    mods: dict[str, dict[str, dict[str, str]]],
    por_zona: dict[str, list[str]],
) -> tuple[str, list[str]]:
    """As regras dos 28 modelos: primeiro as VARIÁVEIS, depois quem as usa.

    O rodeio pela variável não é enfeite. Sem ela, quem precisa da cor fora de um
    `fill` — o traço que arredonda o bico do punho, a borda que diz a identidade
    da peça, o chip da fita — teria de reescrever a tabela inteira, e voltaríamos
    à duplicata que este gerador existe para matar. Com ela, todo consumidor lê
    `var(--z-casca-solida)` e a fonte continua sendo o CSV.
    """
    linhas = [
        '  <style id="cores-do-dualsense-folha">',
        "    /* Fonte: docs/data/cores-do-dualsense.csv (as cores) e a coluna",
        "       `zona` de docs/data/pecas-do-dualsense.csv (as peças).",
        "",
        "       A cor de plástico nunca pinta a LUZ: o lightbar e as cinco lâmpadas",
        "       do indicador de jogador ficam de fora, e é por isso que eles não",
        "       somem sobre a borda do touchpad. */",
    ]
    incompletos = []
    ordem = sorted(mods, key=lambda k: (next(iter(mods[k].values()))["codigo_da_cor"], k))
    zonas_com_alvo = [z for z in ZONAS_DE_SUPERFICIE
                      if z == "simbolos" or por_zona.get(z)]
    for mid in ordem:
        z = mods[mid]
        qualquer = next(iter(z.values()))
        obrigatorias = [x for x in ZONAS_DE_SUPERFICIE if x != "casca"] + list(ZONAS_DA_CASCA)
        faltam = [x for x in obrigatorias if x not in z]
        if faltam:
            incompletos.append(f"{mid}: {', '.join(faltam)}")
        linhas.append(
            f"\n    /* {qualquer['nome']} · código {qualquer['codigo_da_cor']}"
            + (f" · SEM AMOSTRAGEM em {len(faltam)} zonas" if faltam else "")
            + " */"
        )
        tintas = tintas_do_modelo(mid, z)
        decl = ";".join(f"--z-{k}:{v}" for k, v in tintas.items())
        linhas.append(f'    svg[data-colorway="{mid}"]{{{decl}}}')
        for zona in zonas_com_alvo:
            linhas.append(_regra(mid, zona))
    linhas.append("  </style>")
    return "\n".join(linhas), incompletos


def marcar_zonas(svg: str, por_zona: dict[str, list[str]]) -> str:
    """Escreve `class="z-<zona>"` em cada grupo de peça. Idempotente.

    FUNDE com a classe que já estiver lá em vez de acrescentar um segundo
    atributo `class` — dois `class` na mesma tag e o navegador ignora o segundo,
    em silêncio. O grupo do PS carrega `sem-tinta` e não pode perdê-la.
    """
    porid = {pid: z for z, ids in por_zona.items() for pid in ids}
    for pid in GLIFOS_DA_FACE:
        porid[pid] = "simbolos"

    def _no_grupo(m: re.Match[str]) -> str:
        tag, pid = m.group(0), m.group(1)
        zona = porid.get(pid)
        if not zona:
            return tag
        classe = f"z-{zona}"
        atual = re.search(r'\sclass="([^"]*)"', tag)
        if atual:
            nomes = [c for c in atual.group(1).split() if not c.startswith("z-")]
            nomes.append(classe)
            return tag.replace(atual.group(0), f' class="{" ".join(nomes)}"', 1)
        return tag.replace(f'id="{pid}"', f'id="{pid}" class="{classe}"', 1)

    return re.sub(r'<g\b[^>]*\bid="([^"]+)"[^>]*>', _no_grupo, svg)


def montar(svg: str) -> tuple[str, list[str]]:
    por_zona = zonas_das_pecas()
    mods = modelos()
    style, incompletos = gerar_style(mods, por_zona)
    miolo = (
        "    <!-- GERADO por scripts/gerar_cores_do_dualsense.py — não editar à mão. -->\n"
        + gerar_defs(mods)
        + "\n"
        + style
    )

    svg = marcar_zonas(svg, por_zona)
    # O colorway padrão do arquivo: sem ele o SVG abre no navegador sem cor
    # nenhuma, e quem o abrisse sozinho concluiria que o gerador não rodou.
    cabeca = svg[: svg.index(">", svg.index("<svg ")) + 1]
    if "data-colorway=" not in cabeca:
        svg = svg.replace("<svg ", '<svg data-colorway="cosmic-red" ', 1)

    novo = f"{ABRE}\n{miolo}\n  {FECHA}"
    i = svg.find(ABRE)
    if i >= 0:
        j = svg.index(FECHA, i) + len(FECHA)
        return svg[:i] + novo + svg[j:], incompletos
    # Nasce logo depois do `</defs>` dela — que é o PRIMEIRO do arquivo, e é o
    # único que existe enquanto este bloco não existe. `str.replace` que não casa
    # devolve o texto intacto e não avisa; aqui a âncora ausente é erro.
    k = svg.find("</defs>")
    if k < 0:
        raise SystemExit("ERRO: o SVG não tem <defs> — âncora ausente")
    k += len("</defs>")
    return svg[:k] + "\n  " + novo + svg[k:], incompletos


def main() -> int:
    checar = "--check" in sys.argv
    problemas: list[pathlib.Path] = []
    incompletos: list[str] = []
    for alvo in ALVOS:
        atual = alvo.read_text()
        novo, incompletos = montar(atual)
        if novo == atual:
            if not checar:
                print(f"  igual   {alvo.relative_to(RAIZ)}")
        elif checar:
            problemas.append(alvo)
        else:
            alvo.write_text(novo)
            print(f"  gerado  {alvo.relative_to(RAIZ)}")

    if checar and problemas:
        print("FALHA: o desenho não bate com os CSV. Rode:")
        print("  scripts/gerar_cores_do_dualsense.py")
        for p in problemas:
            print(f"    diverge: {p.relative_to(RAIZ)}")
        return 1

    mods = modelos()
    print(f"\n{len(mods)} modelos · {len(ZONAS_DE_SUPERFICIE)} zonas de superfície"
          f" · {len(ZONAS_SEM_ALVO)} declarada sem alvo ({', '.join(ZONAS_SEM_ALVO)})")
    if incompletos:
        print("SEM AMOSTRAGEM — a zona cai na cor de não-medida, e a tela diz:")
        for x in incompletos:
            print(f"    {x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
