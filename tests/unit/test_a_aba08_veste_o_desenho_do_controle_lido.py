#!/usr/bin/env python3
"""O DESENHO DA ABA 08 É O CONTROLE DELA, e não o do mockup.

**03/09/2026.** A lei é dela:

    "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
    players com cada controle — tudo isso muda de acordo com o controle
    identificado no canto superior. é white no p1, mas a borda de tudo é cosmic
    red e os svgs não são os que o meu mapa cataloga. isso tá errado"

A `08-conexoes` desenha DOIS controles, um por linha do acordeão, e os dois
mostravam o plástico do mockup. Medido no motor, com a mesa dela — o White no
cabo e o Galactic Purple no rádio — antes desta cura:

    p1 | data-colorway=cosmic-red      casca rgb(174,  51,  90)   ← rótulo: White
    p2 | data-colorway=starlight-blue  casca rgb(126, 184, 212)   ← rótulo: Galactic Purple

O rótulo ao lado já dizia o nome certo desde a leva da identidade; o desenho
continuava vermelho porque a cor dele viaja num ATRIBUTO, e não havia alvo que
escrevesse atributo.

O QUE ESTA RÉGUA TRAVA, e são TRÊS metades porque a cura tem três — nenhuma
delas sozinha põe uma cor certa na tela:

    (a) o ENDEREÇO         os dois `<svg>` da aba trazem `data-hef-alvo="atributo"`
                           com `data-hef-atributo="data-colorway"`
    (b) a TABELA DELA       a página publica a folha dos 28 modelos, e nenhuma
                           folha PODADA sobra dentro dos desenhos
    (c) o PACOTE ESCREVE   `pacote()` emite, por controle, o slug do modelo que
                           a mesa leu do aparelho

A (b) é a que quase ninguém vê, e é a que decide: `monta._so_o_colorway` guarda
na folha de cada `<svg>` só as regras do modelo pedido — 3.082 bytes dos 45.452
dos 28. Com ela podada, escrever `white` num desenho que só conhece `cosmic-red`
dá o MESMO cinza (`rgb(58, 63, 75)`) de um desenho sem atributo nenhum: o
endereço estaria lá, o pacote escrevendo certo, e a tela trocaria uma cor errada
por um cinza. Por isso :func:`test_todo_modelo_do_mapa_dela_tem_regra_na_pagina`
cobra os VINTE E OITO, e não os dois que a mesa dela tem hoje.

E A QUARTA COISA É A REGRA DELA: **campo sem informação não mostra nada.** Pelo
rádio o mapa de canais responde `identidade.cor_do_aparelho = não`, e a mesa
devolve slug vazio. O alvo `atributo` então APAGA o `data-colorway`, e o desenho
cai no cinza cru do `ds_limpo.svg` — o controle sem identidade. Medido no motor
com `--sem-cor`: `data-colorway=null`, casca `rgb(58, 63, 75)` nos dois.

A MORDIDA, e as duas saídas estão no relatório desta frente:

    * tire o `_FOLHA_NO_DESENHO.sub("", x)` de `desenho_do_controle` e regenere —
      `so_uma_folha` e `todo_modelo_do_mapa_dela` reprovam, e o endereço continua
      lá, que é a prova de que endereço sozinho não cura;
    * comente a linha `"desenho"` do `pacote()` — `o_pacote_escreve_o_modelo`
      reprova e as duas de bancada continuam VERDES.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/08-conexoes.html"
REGUA = RAIZ / "scripts/check_a_cor_vem_do_aparelho.py"

#: A tag de abertura de cada desenho pequeno da aba, inteira. Ele mede a TAG e
#: não a ordem dos atributos: um teste que procura a fatia literal
#: `data-campo="desenho" data-hef-alvo=…` reprova a página CERTA no dia em que o
#: gerador emitir os mesmos atributos noutra ordem. Foi assim que o teste dos
#: chips da fita reprovou uma fita curada, em 03/09/2026.
DESENHO_DA_LINHA = re.compile(r"<svg\b[^>]*\bclass=\"ds-svg ds-mini\"[^>]*>")

#: A folha das cores, onde quer que ela esteja — dentro de um `<svg>` ou na
#: página. O `id` vem prefixado por controle quando mora num desenho
#: (`p1-cores-do-dualsense-folha`), e é por isso que o casamento é por sufixo.
FOLHA = re.compile(r'<style id="([^"]*cores-do-dualsense-folha)">(.*?)</style>', re.S)

#: O seletor com que a folha escolhe o modelo. Mesma expressão do portão da
#: cor, e de propósito: uma segunda grafia divergiria em silêncio.
REGRA_DE_COLORWAY = re.compile(r'svg\[data-colorway="([^"]+)"\]')


def _html() -> str:
    return BANCADA.read_text(encoding="utf-8")


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _modelos_do_mapa() -> set[str]:
    """Os 28 slugs que a mesa pode emitir, pelo dono deles.

    `mesa_viva.CORES` lê `docs/data/cores-do-dualsense.csv` e traduz código de
    fábrica → (slug, nome). Digitar os 28 aqui criaria a segunda lista que
    envelhece sozinha no dia em que ela mapear o vigésimo nono.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    return {slug for slug, _nome in mesa_viva.CORES.values() if slug}


# ---------------------------------------------------------------------------
# (a) O ENDEREÇO — na bancada, e em TODO desenho da aba
# ---------------------------------------------------------------------------
def test_todo_desenho_da_aba_tem_o_endereco_do_colorway() -> None:
    """Nenhum `<svg>` da linha nasce sem por onde o produto trocar a cor.

    A contagem é o que morde: um desenho a mais sem endereço — a mesa dela pode
    crescer para quatro — é uma cor do mockup de volta na tela, e um teste que
    só perguntasse "existe algum endereço" passaria verde por cima dele.
    """
    tags = DESENHO_DA_LINHA.findall(_html())
    assert tags, "a bancada da 08 não tem mais nenhum desenho `.ds-mini`"
    for tag in tags:
        assert 'data-hef-alvo="atributo"' in tag, (
            f"um desenho da 08 perdeu o alvo de atributo — sem ele o "
            f"`escrever()` cai no ramo padrão e escreve a cor como TEXTO por "
            f"cima do desenho: {tag[:160]}")
        assert 'data-hef-atributo="data-colorway"' in tag, (
            f"o alvo não NOMEIA o atributo certo — `data-hef-atributo` com "
            f"outro nome escreve outra coisa e deixa o colorway cravado: "
            f"{tag[:160]}")
        assert 'data-campo="desenho"' in tag, (
            f"o desenho tem alvo e não tem ENDEREÇO: o `achar()` do piloto "
            f"procura por `data-campo`, e sem ele o alvo nunca é alcançado: "
            f"{tag[:160]}")


# ---------------------------------------------------------------------------
# (b) A TABELA DELA — publicada uma vez, inteira
# ---------------------------------------------------------------------------
def test_so_uma_folha_de_cores_e_ela_nao_esta_dentro_de_um_desenho() -> None:
    """A folha é UMA, da página, e não uma cópia podada por desenho.

    Duas metades, e as duas importam: **uma** (quatro cópias dos 28 seriam os
    300 KB de CSS que `monta._so_o_colorway` existe para evitar) e **fora dos
    desenhos** (a que mora dentro de um `<svg>` vem podada pelo `svg()`, e uma
    folha podada não tem como virar outro modelo).
    """
    folhas = FOLHA.findall(_html())
    assert len(folhas) == 1, (
        f"a 08 tem {len(folhas)} folhas de cores: "
        f"{[i for i, _ in folhas]}. Ela é UMA, da página.")
    ident, _css = folhas[0]
    assert ident == "cores-do-dualsense-folha", (
        f"a folha da 08 está dentro de um desenho (`id={ident}`) — o `svg()` "
        f"prefixa o `id` por controle, e é ele que a poda para um modelo só")


def test_todo_modelo_do_mapa_dela_tem_regra_na_pagina() -> None:
    """Os VINTE E OITO, e não os dois da mesa de hoje.

    ESTE É O TESTE QUE IMPEDE A CURA PELA METADE. Quem tiver um Nova Pink não
    aparece na mesa desta bancada nem na dela; se a folha trouxer só os modelos
    que alguém teve na mão, o alvo escreve `nova-pink`, nenhuma regra casa e o
    desenho cai no cinza cru — que é indistinguível, na tela, de "não li a cor".
    """
    declarados = set(REGRA_DE_COLORWAY.findall(_html()))
    faltam = _modelos_do_mapa() - declarados
    assert not faltam, (
        f"faltam {len(faltam)} modelos do mapa dela na folha da 08: "
        f"{sorted(faltam)[:6]}… Quem tiver um deles vê um controle cinza.")


def test_a_hachura_e_os_gradientes_chegam_junto_com_a_folha() -> None:
    """Toda tinta que a folha REFERENCIA existe na página, com o `id` que ela cita.

    ESTE É O DEFEITO QUE QUASE PASSOU, e ele não aparece na mesa dela: oito dos
    28 modelos são pintados com `url(#hachura-sem-hex)` e dois com gradiente
    (`casca-god-of-war-20th`, `casca-spider-man-2`) — 68 referências a três
    `id`. O `monta.svg()` prefixa TODO `id` por controle, então uma folha
    publicada solta apontaria para `#hachura-sem-hex` enquanto os desenhos
    definiriam `#p1-hachura-sem-hex`: dez modelos ficariam sem tinta, e só na
    máquina de quem tivesse um deles.

    A cura é mover o `<defs id="cores-do-dualsense">` INTEIRO, que é a unidade
    que `scripts/gerar_cores_do_dualsense.py` escreve. Esta régua cobra o
    resultado, não a forma: cada `url(#…)` da folha achando o seu `id`.
    """
    html = _html()
    _ident, css = FOLHA.search(html).groups()  # type: ignore[union-attr]
    citados = set(re.findall(r"url\(#([^)]+)\)", css))
    assert citados, (
        "a folha da 08 não cita tinta nenhuma por `url(#…)` — se o mapa dela "
        "deixou de usar hachura, esta régua perdeu o sujeito")
    for ident in sorted(citados):
        assert f'id="{ident}"' in html, (
            f"a folha pinta com `url(#{ident})` e a página não define esse "
            f"`id`. Os modelos que dependem dele ficam SEM TINTA, e ninguém que "
            f"não tenha um deles na mão vê o defeito.")


def test_a_folha_nao_e_digitada_no_gerador() -> None:
    """A tabela da página é LIDA do desenho, nunca escrita à mão.

    O dono das 233 linhas é `scripts/gerar_cores_do_dualsense.py`, que as põe no
    `ds_limpo.svg` a partir do CSV dela. Uma cópia no gerador da aba envelheceria
    sozinha — é a regra desta casa sobre o que tem dono.
    """
    import monta

    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py").read_text(
        encoding="utf-8")
    hexes = set(re.findall(r"--z-[a-z0-9_-]+\s*:\s*#[0-9a-fA-F]{3,8}", fonte))
    assert not hexes, (
        f"o gerador da 08 digitou hex de zona: {sorted(hexes)[:4]} — a folha "
        f"tem dono, e ele não é esta aba")
    do_desenho = FOLHA.search(monta.DS)
    assert do_desenho, "a folha sumiu do `ds_limpo.svg`"
    na_pagina = FOLHA.search(_html())
    assert na_pagina and na_pagina.group(2).strip() == do_desenho.group(2).strip(), (
        "a folha da página não é a do `ds_limpo.svg` — alguém a editou no meio "
        "do caminho, e a partir daqui as duas divergem caladas")


# ---------------------------------------------------------------------------
# (c) O PACOTE ESCREVE — e é esta metade que impede a maquiagem
# ---------------------------------------------------------------------------
def _ctx(cor_do_p2: str = "galactic-purple") -> Any:
    """A mesa dela: o White no cabo, e um no rádio com a cor variável."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    # A FAIXA SINTÉTICA DA CASA — há dois portões de anonimato nesta árvore.
    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": cor_do_p2,
         "nome": "Galactic Purple" if cor_do_p2 else "Não sei",
         "via": "BT", "transporte": "bt", "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_o_pacote_escreve_o_modelo_que_a_mesa_leu() -> None:
    """Por controle, o SLUG do mapa — nunca o do desenho."""
    colunas = _pacote().pacote(_ctx())["colunas"]
    modelos = [c.get("desenho", "") for c in colunas.values()]
    assert "white" in modelos, (
        f"o pacote não escreveu o modelo do White — escreveu {modelos!r}")
    assert "galactic-purple" in modelos
    for m in modelos:
        assert m not in ("cosmic-red", "starlight-blue"), (
            f"o pacote escreveu `{m}`, que é do MOCKUP e não da mesa")


def test_o_pacote_fala_a_lingua_do_atributo_e_nao_a_do_hex() -> None:
    """O desenho escolhe por NOME de modelo; a barra da linha, por hex.

    São dois alvos diferentes no mesmo dado, e trocá-los é o defeito silencioso
    que este teste existe para pegar: um `#edeef0` no `data-colorway` não casa
    regra nenhuma e dá o mesmo cinza do atributo apagado.
    """
    import monta

    for coluna in _pacote().pacote(_ctx())["colunas"].values():
        assert not coluna["desenho"].startswith("#"), (
            f"o pacote mandou um hex para o `data-colorway`: {coluna['desenho']!r}")
        assert coluna["plastico"] == monta.cor_da_zona(coluna["desenho"]), (
            "a barra e o desenho deixaram de falar do mesmo modelo — a linha "
            "mostraria uma cor na aresta e outra no controle")


def test_o_modelo_sem_hex_medido_nao_derruba_a_aba() -> None:
    """OITO dos 28 modelos não têm hex, e isso derrubava a `08` inteira.

    Achado em 03/09/2026 passando os 28 pelo pacote: Chroma Teal, Chroma Indigo,
    Chroma Pearl, Grey Camouflage, Ghost of Yōtei, Marathon, Genshin Impact e
    007 First Light são pintados no mapa dela com `url(#hachura-sem-hex)` — a
    hachura com que ela escreve *"esta cor eu não medi"*. O valor chegava a
    `tinta_legivel`, e `int("ur", 16)` levanta `ValueError` **fora** do `try` do
    `_hex_do_plastico`: quem ligasse um Chroma Teal via a aba parar de pintar
    por inteiro, sem uma barra na tela e sem um erro que dissesse por quê.

    AS DUAS METADES, e as duas importam: a aba não morre, **e** a hachura não
    vira cor de barra — ela é resposta legítima para o DESENHO (que a mostra) e
    ausência de leitura para tudo que precisa de um hex.
    """
    import monta

    sem_hex = [m for m in sorted(_modelos_do_mapa())
               if not monta.cor_da_zona(m).startswith("#")]
    assert sem_hex, (
        "nenhum modelo do mapa usa a hachura — se ela mediu os 28, esta régua "
        "perdeu o alvo e vira teste sem sujeito")
    for modelo in sem_hex:
        colunas = _pacote().pacote(_ctx(cor_do_p2=modelo))["colunas"]
        do_radio = [c for c in colunas.values() if c.get("via") == "BT"]
        assert do_radio, f"a mesa de prova perdeu o rádio com `{modelo}`"
        for c in do_radio:
            assert c["desenho"] == modelo, (
                f"o desenho perdeu o modelo `{modelo}` — a hachura É a resposta "
                f"certa para ele, e o SVG sabe desenhá-la")
            assert c["plastico"] == "", (
                f"a barra recebeu {c['plastico']!r} para `{modelo}` — uma "
                f"hachura não é uma cor, e `tinta_legivel` morre com ela")


def test_todo_modelo_que_o_pacote_pode_emitir_e_pintavel() -> None:
    """Os 28 caminhos, e não só os dois da mesa de prova.

    A mesa entrega o slug que `mesa_viva.CORES` traduziu do código de fábrica —
    qualquer um dos 28. Este teste passa cada um pelo pacote e cobra que a
    página saiba pintá-lo; é a costura entre a metade (b) e a metade (c), e sem
    ela as duas podem estar verdes sobre modelos diferentes.
    """
    declarados = set(REGRA_DE_COLORWAY.findall(_html()))
    for modelo in sorted(_modelos_do_mapa()):
        colunas = _pacote().pacote(_ctx(cor_do_p2=modelo))["colunas"]
        emitidos = {c.get("desenho", "") for c in colunas.values()}
        assert modelo in emitidos, (
            f"o pacote engoliu o modelo `{modelo}` — emitiu {emitidos!r}")
        assert modelo in declarados, (
            f"a página não tem regra para `{modelo}`, que o pacote emite")


def test_sem_cor_lida_o_desenho_fica_sem_identidade() -> None:
    """Regra dela: campo sem informação NÃO MOSTRA NADA.

    O vazio APAGA o atributo (o alvo `atributo` chama `removeAttribute` no vazio
    e no travessão), nenhuma regra da folha casa e o desenho cai nos `fill` crus
    do `ds_limpo.svg` — medido no motor: `rgb(58, 63, 75)`, o mesmo cinza de um
    `<rect>` que nunca teve zona. Não é desenho quebrado: é o controle sem
    identidade, que é o que a lei pede quando não há leitura.

    O QUE ELE PROÍBE é o contrário: manter o colorway do MOCKUP sobre um
    aparelho que é outro.
    """
    colunas = _pacote().pacote(_ctx(cor_do_p2=""))["colunas"]
    do_radio = [c for c in colunas.values() if c.get("via") == "BT"]
    assert do_radio, "a mesa de prova perdeu o controle de rádio"
    for c in do_radio:
        assert c["desenho"] == "", (
            f"sem cor lida o desenho recebeu {c['desenho']!r} — isso é inventar")


# ---------------------------------------------------------------------------
# O PORTÃO DA LEVA, quando ele estiver nesta árvore
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not REGUA.exists(),
                    reason="o portão da cor ainda não chegou a esta árvore")
def test_a_bancada_da_08_nao_tem_mais_cor_cravada() -> None:
    """A régua da leva, chamada como a leva manda, tem de devolver zero.

    Ela nasceu em 38 para esta aba: 2 `data-colorway` sem endereço e 36 hexes de
    zona em duas folhas podadas.
    """
    saida = subprocess.run(
        [sys.executable, str(REGUA), "--bancada", "--aba", "08"],
        capture_output=True, text=True, cwd=str(RAIZ), check=False)
    assert saida.returncode == 0, (
        "a `08-conexoes` voltou a ter cor de aparelho cravada na bancada:\n"
        + saida.stdout + saida.stderr)
