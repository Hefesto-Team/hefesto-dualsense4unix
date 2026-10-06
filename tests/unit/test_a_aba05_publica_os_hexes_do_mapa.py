#!/usr/bin/env python3
"""A folha dos 28 da 05 carrega os HEXES do CSV dela — não só os 28 nomes."""
from __future__ import annotations

import csv
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup/05-vibracao.html"
CORES_CSV = RAIZ / "docs/data/cores-do-dualsense.csv"

FORA_DO_DESENHO = ("nova-pink", "astro-bot", "sterling-silver")

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
    """O que a folha tem de dizer para aquela zona: o hex dela, ou a hachura."""
    linha = zonas.get(coluna)
    if linha is None:
        return ""
    if (linha.get("grau") or "").strip() == "SEM-HEX" or not (linha.get("hex") or "").strip():
        return HACHURA
    return (linha["hex"] or "").strip()


def _partida(zonas: dict[str, dict[str, str]]) -> bool:
    """A casca tem duas cores? Só o Spider-Man 2 e o God of War 20th têm."""
    return ("casca_esq" in zonas and "casca_dir" in zonas
            and _esperado(zonas, "casca_esq") != _esperado(zonas, "casca_dir"))


def test_cada_zona_dos_28_traz_o_hex_do_csv_dela() -> None:
    """As oito zonas sólidas dos 28 modelos, comparadas com o CSV linha a linha."""
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
            if visto.replace("\\#", "#").upper() != esperado.upper():
                divergem.append(
                    f"{ident}.{zona}: a página diz {visto!r} e o CSV dela diz "
                    f"{esperado!r} (coluna `{coluna}`)")

    possiveis = sum(1 for zonas in mapa.values() for coluna in ZONA_DA_COLUNA.values()
                    if coluna in zonas)
    assert conferidas == possiveis >= 200, (
        f"a régua conferiu {conferidas} de {possiveis} zonas com linha no CSV — "
        "ela deixou de medir o que prometia, que é pior que reprovar")
    assert not divergem, (
        f"{len(divergem)} zona(s) da folha não são o mapa dela:\n  "
        + "\n  ".join(divergem[:20]))


def test_nenhuma_variavel_da_folha_sai_vazia() -> None:
    """Toda zona publicada tem valor nas DUAS formas — a crua e a que pinta."""
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


def test_os_modelos_que_o_desenho_nao_tem_resolvem_do_mapa_dela() -> None:
    """Nova Pink, Astro Bot e Sterling Silver: o hex é o dela, e é ÚNICO."""
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
    """Declarar a variável não pinta nada — quem pinta é a regra que a usa."""
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


def test_o_sem_hex_do_csv_vira_hachura_e_nao_uma_cor_inventada() -> None:
    """O CSV manda não inventar fill, e a página obedece."""
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
    """Onde o mapa dela tem buraco, a página diz "não medi" — de um jeito só."""
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
    """Spider-Man 2 e God of War 20th têm DUAS cascas, e a página as tem."""
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

    for ident in partidas:
        abre = f'<linearGradient id="casca-{ident}"'
        assert abre not in html.replace(abre, "<linearGradient id=\"morto\""), (
            "a régua não distingue o gradiente presente do arrancado")


def test_a_variavel_que_pinta_sai_da_crua_pela_conta_do_dono() -> None:
    """As variáveis que pintam também são conferidas — não só as `-crua`."""
    import sys

    sys.path.insert(0, str(RAIZ / "scripts"))
    from gerar_cores_do_dualsense import legivel

    folha = _folha(_pagina())
    assert folha, "a página não publica folha nenhuma"

    divergem: list[str] = []
    conferidas = 0
    for ident, variaveis in sorted(folha.items()):
        for nome, cru in sorted(variaveis.items()):
            if not nome.endswith("-crua"):
                continue
            zona = nome[: -len("-crua")]
            pinta = variaveis.get(zona)
            if pinta is None:
                divergem.append(f"{ident}.{zona}: há `-crua` e não há a que pinta")
                continue
            conferidas += 1
            limpo = cru.replace("\\#", "#")
            esperado = legivel(limpo)
            if pinta.replace("\\#", "#").lower() != esperado.lower():
                divergem.append(
                    f"{ident}.{zona}: pinta {pinta!r} e a conta do dono sobre "
                    f"{limpo!r} dá {esperado!r}")

    assert conferidas >= 200, (
        f"a régua conferiu só {conferidas} variáveis de tinta — ela deixou de "
        "medir o que promete, que é pior que reprovar")
    assert not divergem, (
        f"{len(divergem)} variável(is) que PINTAM não saem da crua pela conta "
        "do dono:\n  " + "\n  ".join(divergem[:20]))
