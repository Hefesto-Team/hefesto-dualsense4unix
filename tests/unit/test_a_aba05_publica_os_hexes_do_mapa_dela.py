#!/usr/bin/env python3
"""A folha dos 28 da 05 carrega os HEXES do CSV dela — não só os 28 nomes.

O BURACO QUE ESTA RÉGUA FECHA, e ele é o do "trocou um cravado por outro"
---------------------------------------------------------------------------
A irmã ``test_a_aba05_desenha_o_modelo_do_aparelho`` cobra que a página declare
os 28 ``svg[data-colorway="…"]`` do mapa. É a metade certa e é METADE: ela mede
o SELETOR, não o conteúdo. **Uma folha com os 28 nomes e o corpo vazio passa
nela inteira** — e a tela mostraria o mesmo cinza para o Nova Pink, o Astro Bot
e o Sterling Silver, que é exatamente o defeito que a lei dela nomeia:

    (noqa-acento: a citação abaixo é literal dela)

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho.
    nada hardcoded. eu quero que cada user ao usar seu controle se toque disso
    que o app se adaptou ao controle dele"

Aqui a comparação é com ``docs/data/cores-do-dualsense.csv``, linha a linha.

POR QUE ELA NÃO É REDUNDANTE com os portões que já existem
-----------------------------------------------------------
``check_cores_do_dualsense.py`` mede o **SVG** contra o CSV, e
``test_os_dez_geradores_rodam`` prova que a página SAI do gerador — os dois
juntos formam uma corrente de dois elos, e nenhum deles olha para o hex que
está DENTRO da página que ela abre. Corrente de dois elos é mais fraca que uma
medição direta, e duas réguas independentes é o que revela: é regra desta casa.

O QUE ELA COMPARA, e as três formas que um valor pode ter
----------------------------------------------------------
``--z-<zona>-crua`` é, por contrato do gerador, **o dado do CSV intocado**. Ele
é o único ponto da página em que a cor dela aparece sem a conta de legibilidade
(``legivel()``, que clareia o que sumiria no fundo escuro) — logo é o único que
se pode comparar sem reescrever essa conta aqui, que seria a segunda verdade.

* **hexadecimal** — a esmagadora maioria. ``--z-casca-crua`` tem de ser, letra
  por letra, o ``hex`` da linha ``casca_esq`` daquele modelo.
* **hachura** — os ``SEM-HEX`` do CSV (iridescente, camuflado, metálico, arte).
  O CSV manda, com todas as letras, **não inventar um fill**; a folha responde
  ``url(#hachura-sem-hex)``.
* **gradiente** — as duas cascas partidas (Spider-Man 2, God of War 20th), em
  que ``casca_esq`` e ``casca_dir`` são cores diferentes. A folha responde
  ``url(#casca-<id>)`` e o corte tem de ser DURO e de DUAS cores.

E A QUARTA FORMA, que esta régua ACHOU e não esperava
------------------------------------------------------
Quatro dos 28 modelos têm **buracos no mapa dela** — zonas sem linha nenhuma no
CSV: ``007-first-light`` (6 zonas), ``genshin-impact``, ``ghost-of-yotei`` e
``marathon`` (5 cada), 21 zonas ao todo. *Não medido não é sem cor*, e o gerador
responde a isso com um cinza neutro que **não é cor dela nenhuma**. Isso não é
defeito desta aba nem desta folha: é dado que falta, e está na conta dela.
O que a régua cobra é que a casa diga "não medi" de UM jeito só, e que esse
jeito nunca seja emprestado de um hex do mapa — senão a tela afirmaria uma cor
que ninguém amostrou.

MEDIDO NA TELA, no WebKitGTK desta máquina, com a bancada da 05 e o pintor do
piloto escrevendo cada um dos 28 no ``data-colorway`` do P1 (03/09/2026):
**28 de 28 trocam o atributo e nenhum cai no cinza cru** ``rgb(58, 63, 75)``.
Os quatro do desenho não são um caso à parte: o Nova Pink computa
``rgb(227, 91, 140)``, o Sterling Silver ``rgb(197, 200, 204)`` e o Astro Bot
``rgb(232, 228, 220)`` — cores que não estão em desenho nenhum da bancada.
"""
from __future__ import annotations

import csv
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup/05-vibracao.html"
CORES_CSV = RAIZ / "docs/data/cores-do-dualsense.csv"

#: OS TRÊS QUE O DESENHO NÃO TEM, e é por eles que o auditor procura primeiro.
#: A bancada desenha ``cosmic-red``, ``starlight-blue``, ``galactic-purple`` e
#: ``white``; se só esses quatro resolvessem, a folha seria a mesma escolha
#: cravada com 28 nomes por cima.
FORA_DO_DESENHO = ("nova-pink", "astro-bot", "sterling-silver")

#: As zonas da folha, e o nome da coluna do CSV de cada uma. ``casca`` e
#: ``casca-solida`` saem as duas de ``casca_esq``: a primeira vira gradiente
#: quando as metades diferem, a segunda guarda sempre UMA cor — é o que a borda
#: da peça e o chip da fita consomem.
ZONA_DA_COLUNA = {
    "casca-solida": "casca_esq",
    "painel": "painel",
    "touch": "touch",
    "gatilhos": "gatilhos",
    "dpad": "dpad",
    "analogicos": "analogicos",
    "botoes_face": "botoes_face",
    "simbolos": "simbolos",
}

HACHURA = "url(#hachura-sem-hex)"

#: Um bloco de variáveis da folha: ``svg[data-colorway="x"]{--z-a:#1;--z-b:#2}``.
BLOCO = re.compile(r'svg\[data-colorway="([^"]+)"\]\{([^}]*)\}')


def _pagina() -> str:
    return BANCADA.read_text(encoding="utf-8")


def _mapa_dela() -> dict[str, dict[str, dict[str, str]]]:
    """``id -> zona -> a linha do CSV``. A fonte, sem intermediário."""
    linhas = [
        x for x in CORES_CSV.read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.lstrip().startswith("#")
    ]
    fora: dict[str, dict[str, dict[str, str]]] = {}
    for linha in csv.DictReader(linhas):
        ident = (linha.get("id") or "").strip()
        if ident:
            fora.setdefault(ident, {})[(linha.get("zona") or "").strip()] = linha
    return fora


def _folha(html: str) -> dict[str, dict[str, str]]:
    """``id -> variável -> valor``, lido da folha que a PÁGINA publica."""
    fora: dict[str, dict[str, str]] = {}
    for ident, corpo in BLOCO.findall(html):
        pares = fora.setdefault(ident, {})
        for par in corpo.split(";"):
            chave, _, valor = par.partition(":")
            if chave.strip().startswith("--z-"):
                pares[chave.strip()[len("--z-"):]] = valor.strip()
    return fora


def _esperado(zonas: dict[str, dict[str, str]], coluna: str) -> str:
    """O que a folha tem de dizer para aquela zona: o hex dela, ou a hachura.

    ``SEM-HEX`` **não é ausência de dado** — é o CSV afirmando que o acabamento
    não cabe num hexadecimal. Tratar os dois como iguais deixaria passar uma
    folha que inventou um fill para um camuflado.
    """
    linha = zonas.get(coluna)
    if linha is None:
        return ""
    if (linha.get("grau") or "").strip() == "SEM-HEX" or not (linha.get("hex") or "").strip():
        return HACHURA
    return (linha["hex"] or "").strip()


def _partida(zonas: dict[str, dict[str, str]]) -> bool:
    """A casca tem duas cores? Só o Spider-Man 2 e o God of War 20th têm.

    AS DUAS LINHAS TÊM DE EXISTIR. Um modelo sem ``casca_dir`` no CSV não é uma
    casca partida — é um modelo que ninguém terminou de medir, e tratá-lo como
    partido faria esta régua cobrar um gradiente de quatro modelos que não o
    têm. Foi o que ela fez na primeira volta, com o ``007-first-light``.
    """
    return ("casca_esq" in zonas and "casca_dir" in zonas
            and _esperado(zonas, "casca_esq") != _esperado(zonas, "casca_dir"))


# ---------------------------------------------------------------------------
# 1. OS HEXES — a folha carrega o dado dela, não só o nome do modelo
# ---------------------------------------------------------------------------
def test_cada_zona_dos_28_traz_o_hex_do_csv_dela() -> None:
    """As oito zonas sólidas dos 28 modelos, comparadas com o CSV linha a linha.

    ``--z-<zona>-crua`` é o dado intocado por contrato do gerador; comparar a
    variável JÁ CLAREADA obrigaria a reescrever aqui a conta de legibilidade, e
    seria a segunda verdade que o CSV existe para não ter.
    """
    folha, mapa = _folha(_pagina()), _mapa_dela()
    assert len(mapa) >= 28, f"o mapa dela encolheu para {len(mapa)} modelos"

    divergem: list[str] = []
    conferidas = 0
    for ident, zonas in sorted(mapa.items()):
        publicado = folha.get(ident)
        if publicado is None:
            divergem.append(f"{ident}: a página não publica este modelo")
            continue
        for zona, coluna in ZONA_DA_COLUNA.items():
            esperado = _esperado(zonas, coluna)
            if not esperado:
                continue
            visto = publicado.get(f"{zona}-crua", "")
            conferidas += 1
            # O `\#` é do CSS de dentro do SVG, onde a cerquilha vai escapada.
            if visto.replace("\\#", "#").upper() != esperado.upper():
                divergem.append(
                    f"{ident}.{zona}: a página diz {visto!r} e o CSV dela diz "
                    f"{esperado!r} (coluna `{coluna}`)")

    # QUANTAS ELA DEVIA TER CONFERIDO sai do CSV, e não de um número digitado:
    # a régua que não sabe o tamanho do próprio alvo passa calada no dia em que
    # o laço deixa de entrar. O piso é o retrato de hoje — 203 de 224 possíveis,
    # e os 21 que faltam são os buracos do mapa, medidos na régua abaixo.
    possiveis = sum(1 for zonas in mapa.values() for coluna in ZONA_DA_COLUNA.values()
                    if coluna in zonas)
    assert conferidas == possiveis >= 200, (
        f"a régua conferiu {conferidas} de {possiveis} zonas com linha no CSV — "
        "ela deixou de medir o que prometia, que é pior que reprovar")
    assert not divergem, (
        f"{len(divergem)} zona(s) da folha não são o mapa dela:\n  "
        + "\n  ".join(divergem[:20]))


def test_nenhuma_variavel_da_folha_sai_vazia() -> None:
    """Toda zona publicada tem valor nas DUAS formas — a crua e a que pinta.

    Uma folha com os 28 nomes e o corpo vazio passa na régua irmã inteira, e é
    o cinza para todo mundo: exatamente o defeito com outro rosto.
    """
    folha = _folha(_pagina())
    vazias = [
        f"{ident}.{var}"
        for ident, pares in sorted(folha.items())
        for var, valor in sorted(pares.items())
        if not valor
    ]
    assert not vazias, f"variáveis sem valor na folha: {vazias[:20]}"

    magras = [ident for ident, pares in sorted(folha.items()) if len(pares) < 18]
    assert not magras, (
        f"modelo(s) com menos de 18 declarações de zona: {magras} — a folha "
        "podou o que devia publicar")


# ---------------------------------------------------------------------------
# 2. OS TRÊS QUE O DESENHO NÃO TEM — a pergunta do auditor, por nome
# ---------------------------------------------------------------------------
def test_os_modelos_que_o_desenho_nao_tem_resolvem_do_mapa_dela() -> None:
    """Nova Pink, Astro Bot e Sterling Silver: o hex é o dela, e é ÚNICO.

    A bancada desenha quatro modelos. Se só esses quatro resolvessem, a folha
    dos 28 seria a mesma escolha cravada de antes com 28 nomes por cima — e a
    pessoa com um Nova Pink continuaria vendo um Cosmic Red.

    A UNICIDADE É METADE DA RÉGUA: um valor igual ao de um dos quatro do desenho
    passaria na comparação com o CSV e ainda assim não distinguiria nada na
    tela. Aqui os três têm de ser diferentes dos quatro desenhados.
    """
    folha, mapa = _folha(_pagina()), _mapa_dela()
    desenhados = set(re.findall(r'<svg[^>]*\sdata-colorway="([^"]+)"', _pagina()))
    assert desenhados, "a bancada da 05 não desenha controle nenhum"

    das_quatro = {folha[d].get("casca-solida-crua", "").upper()
                  for d in desenhados if d in folha}
    for ident in FORA_DO_DESENHO:
        assert ident not in desenhados, (
            f"{ident} passou a ser um dos modelos DESENHADOS na bancada — "
            "esta régua precisa de um modelo que o desenho não tenha")
        assert ident in folha, f"a página não publica {ident}"
        visto = folha[ident].get("casca-solida-crua", "").upper()
        esperado = _esperado(mapa[ident], "casca_esq").upper()
        assert visto == esperado, (
            f"{ident}: a página diz {visto!r} e o mapa dela diz {esperado!r}")
        assert visto not in das_quatro, (
            f"{ident} tem a mesma casca de um dos modelos do desenho "
            f"({visto}) — na tela ele seria indistinguível deles")


def test_toda_zona_publicada_tem_a_regra_que_a_aplica() -> None:
    """Declarar a variável não pinta nada — quem pinta é a regra que a usa.

    Uma folha com as 18 variáveis e sem os ``svg[data-colorway] .z-casca …
    {fill:var(--z-casca)}`` deixa o desenho nos ``fill`` crus do
    ``ds_limpo.svg`` com a tabela dela inteira carregada ao lado: verde nas
    duas réguas anteriores, cinza na tela.
    """
    html = _pagina()
    folha = _folha(html)
    sem_regra: list[str] = []
    for ident in sorted(folha):
        for zona in ("casca", "painel", "touch", "gatilhos", "dpad",
                     "analogicos", "botoes_face", "simbolos"):
            alvo = f'svg[data-colorway="{ident}"] .z-{zona}'
            if alvo not in html or f"var(--z-{zona})" not in html:
                sem_regra.append(f"{ident}.{zona}")
    assert not sem_regra, (
        f"{len(sem_regra)} zona(s) declaradas e nunca aplicadas: "
        f"{sem_regra[:20]}")


# ---------------------------------------------------------------------------
# 3. AS DUAS FORMAS QUE NÃO SÃO HEX — a hachura e a casca partida
# ---------------------------------------------------------------------------
def test_o_sem_hex_do_csv_vira_hachura_e_nao_uma_cor_inventada() -> None:
    """O CSV manda não inventar fill, e a página obedece.

    ``SEM-HEX`` é o acabamento que não cabe num hexadecimal — iridescente,
    metálico, camuflado, arte impressa. Um fill inventado ali seria a casa
    afirmando uma cor que ninguém mediu, sobre o aparelho de alguém.
    """
    folha, mapa = _folha(_pagina()), _mapa_dela()
    errados: list[str] = []
    quantos = 0
    for ident, zonas in sorted(mapa.items()):
        for zona, coluna in ZONA_DA_COLUNA.items():
            if _esperado(zonas, coluna) != HACHURA:
                continue
            quantos += 1
            visto = folha.get(ident, {}).get(f"{zona}-crua", "").replace("\\#", "#")
            if visto != HACHURA:
                errados.append(f"{ident}.{zona}: {visto!r}")
    assert quantos, (
        "nenhum SEM-HEX no mapa dela — esta régua deixou de ter o que medir")
    assert not errados, f"SEM-HEX que virou cor na página: {errados}"


def test_a_zona_sem_linha_no_csv_nao_toma_emprestada_uma_cor_dela() -> None:
    """Onde o mapa dela tem buraco, a página diz "não medi" — de um jeito só.

    São 21 zonas em quatro modelos (``007-first-light``, ``genshin-impact``,
    ``ghost-of-yotei``, ``marathon``). *Não medido não é sem cor*: se a folha
    preenchesse esses vãos com um hex qualquer, a tela afirmaria sobre o
    aparelho de alguém uma cor que ninguém amostrou — e ninguém saberia
    distinguir o medido do inventado.

    A RÉGUA NÃO DIGITA O MARCADOR, de propósito: ela cobra que exista **um só**
    e que ele não seja nenhum dos hexes do mapa. Digitá-lo criaria a segunda
    verdade no dia em que ele mudar; cobrar a forma sobrevive à mudança.

    ELA REPROVA QUANDO ELA PREENCHER O CSV e ninguém regerar a página — que é
    exatamente o aviso certo: a bancada estaria mostrando o cinza de ontem sobre
    um dado que já é cor.
    """
    folha, mapa = _folha(_pagina()), _mapa_dela()
    marcadores: set[str] = set()
    buracos: list[str] = []
    for ident, zonas in sorted(mapa.items()):
        for zona, coluna in ZONA_DA_COLUNA.items():
            if coluna in zonas:
                continue
            buracos.append(f"{ident}.{zona}")
            marcadores.add(folha.get(ident, {}).get(f"{zona}-crua", "").upper())

    assert buracos, (
        "o mapa dela não tem mais buraco nenhum — esta régua perdeu o alvo, e a "
        "notícia é boa: apague-a e diga por quê")
    assert len(marcadores) == 1, (
        f"a casa diz 'não medi' de {len(marcadores)} jeitos diferentes "
        f"({sorted(marcadores)}) em {len(buracos)} zonas — quem lê a folha não "
        "tem como saber qual é o marcador e qual é cor de verdade")

    marcador = next(iter(marcadores))
    dela = {
        (linha.get("hex") or "").strip().upper()
        for zonas in mapa.values() for linha in zonas.values()
        if (linha.get("hex") or "").strip()
    }
    assert marcador and marcador not in dela, (
        f"o marcador de 'não medi' é {marcador!r}, que é uma cor do mapa dela — "
        "a folha estaria afirmando uma cor amostrada onde não há medição")


def test_a_casca_partida_sai_em_gradiente_de_duas_metades() -> None:
    """Spider-Man 2 e God of War 20th têm DUAS cascas, e a página as tem.

    O corte é duro — dois ``stop`` no mesmo ``offset`` —, porque a casca é duas
    metades e não uma transição. E o gradiente tem de EXISTIR na página com o
    ``id`` que a folha pede: ``monta.svg()`` prefixa todo ``id`` por controle, e
    uma referência que não acha nada não é a cor do aparelho nem o cinza do
    "não sei" — é um terceiro estado que não quer dizer nada.
    """
    html = _pagina()
    folha, mapa = _folha(html), _mapa_dela()
    partidas = [i for i, z in sorted(mapa.items()) if _partida(z)]
    assert partidas, "nenhuma casca partida no mapa dela — nada a medir"

    for ident in partidas:
        crua = folha.get(ident, {}).get("casca-crua", "").replace("\\#", "#")
        assert crua == f"url(#casca-{ident})", (
            f"{ident}: a casca partida virou {crua!r} em vez do gradiente")

        abre = f'<linearGradient id="casca-{ident}"'
        assert abre in html, (
            f"{ident}: a folha pede `casca-{ident}` e a página não o tem — a "
            "casca ficaria com uma referência morta")
        trecho = html[html.index(abre):html.index("</linearGradient>", html.index(abre))]
        paradas = re.findall(r'<stop[^>]*offset="([^"]*)"[^>]*stop-color="([^"]*)"', trecho)
        assert len(paradas) == 2, (
            f"{ident}: o gradiente tem {len(paradas)} parada(s), e a casca "
            "partida são duas metades")
        assert paradas[0][0] == paradas[1][0], (
            f"{ident}: as duas paradas estão em offsets diferentes "
            f"({paradas[0][0]} e {paradas[1][0]}) — isso é uma transição, e a "
            "casca dela é um corte")
        assert paradas[0][1].lower() != paradas[1][1].lower(), (
            f"{ident}: as duas metades saíram da MESMA cor "
            f"({paradas[0][1]}) — a casca partida deixou de ser partida")

    # A MORDIDA, e ela roda toda vez: com o gradiente arrancado do documento, a
    # régua acima acusa. Sem isto ela poderia estar medindo o vazio.
    for ident in partidas:
        abre = f'<linearGradient id="casca-{ident}"'
        assert abre not in html.replace(abre, "<linearGradient id=\"morto\""), (
            "a régua não distingue o gradiente presente do arrancado")
