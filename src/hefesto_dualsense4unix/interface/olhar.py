#!/usr/bin/env python3
"""Abre a aba num Chrome de verdade (Playwright) e fotografa o que aparece.

Por que Playwright e não só `--screenshot`: o headless puro não roda o
JavaScript da página com o mesmo relógio, não espera fonte carregar, e não
deixa medir DEPOIS de tudo assentar. Aqui a foto sai da página já pronta.

ONDE ELE OLHA: a BANCADA (`mockup/`), que é o desenho de hoje. Com
`--publicado` ele fotografa `interface/paginas/`, o que o produto renderiza —
serve para comparar o antes e o depois de uma publicação, e para mais nada. O
padrão é a bancada de propósito: instrumento apontado para a página congelada
dá **verde sobre o desenho velho**, que é a armadilha mais cara do
`COMO-OLHAR-A-TELA.md` e reincidiu quatro vezes só em 31/08.

ELE É O RETRATISTA DA INTERFACE NOVA — 05/09/2026
--------------------------------------------------

**ELE É O ÚNICO — desde 06/09/2026.** Quem fotografava a JANELA GTK era
`scripts/gui-captura/retratar_abas.py`, e era ele que o `CLAUDE.md` mandava
rodar antes de commitar. A janela tinha ONZE abas e o produto tem DEZ páginas
HTML — as fotos do README mostravam uma tela que não é mais a que abre. A
janela saiu inteira (`D-0609-GTK-LEVA-INTEIRA`) e o retratista dela saiu junto;
**este arquivo é o retratista desta casa, e não há outro.** Queixa dela que
abriu o caminho, 05/09/2026:

    *"termos scripts no repo atual que ou apontam pro gtk ou só funcionam lá
    (…) o certo é ajustar ele pra comportar todas as features do html"*

O modo `--todas` é esse ajuste, e nasceu AQUI e não lá por uma razão de
dependência que a remoção confirmou: o retratista da janela importava GTK na
primeira linha, e um modo que não precisa de GTK dentro dele obrigaria toda
máquina a ter PyGObject para fotografar HTML. Este arquivo já era o dono do
Chrome e da receita da foto — e por isso sobreviveu à janela sem uma linha de
migração.

    interface/olhar.py --todas              # as dez, da bancada, em /tmp
    interface/olhar.py --todas --publicado --doc   # as dez do produto,
                                                   # para docs/usage/assets/

ELE TAMBÉM PROCURA PALAVRA — 06/09/2026, A-PALAVRA-MESA-SAI-01

`--palavra mesa` lista, página por página, cada ocorrência que uma pessoa LÊ,
com o contexto e o ARQUIVO:LINHA de onde ela vem. Ele não abre navegador: a
leitura é a do `frases_que_ela_baniu`, que é a mesma que a régua usa —
instrumento e portão têm de responder o mesmo número, senão um dos dois mente.
O `--palavra` é o "antes" da sprint, e um `--palavra mesa` vazio é o "depois".

**E A LEITURA MUDA COM O ALVO — 06/09/2026, e não é detalhe.** A bancada ela
abre no navegador crua; o produto renderiza a mesma página com a folha do
piloto por cima, que apaga a `.nota` (o bilhete de projeto). Até esta data o
`--publicado` contava a `.nota` e dizia **"34 ocorrência(s) visível(eis) em o
produto"** sobre uma tela que não mostrava nenhuma — o instrumento respondia
sobre o ARQUIVO. Agora o modo publicado lê por `texto_visivel_no_produto`, que
pergunta à `interface.folha_da_casa` o que o produto esconde.

    interface/olhar.py --palavra mesa               # a bancada
    interface/olhar.py --palavra mesa --publicado   # o que o produto renderiza

ELE FOTOGRAFA A VISTA QUE SE PEDIR — 11/09/2026, PRINTS-DAS-DEZ-01

Ordem dela: *"quero que vc maximize as telas e tire prints de todas as abas"*.
Até hoje o retratista tinha UMA vista cravada (1920x1080) e o `--doc` recortava
na `.janela`, e **as duas coisas juntas tornavam a ordem impossível de
atender**: a `.janela` é `width:min(100%,1600px)` por `height:var(--alt-janela)`
com `--alt-janela:777px` fixo, então o recorte sai **o mesmo pixel em qualquer
vista** acima de 1632x809. Fotografar maximizado não mudava a foto.

    interface/olhar.py --todas --publicado --doc --vista 1918x840

`--vista LARGxALT` faz DUAS coisas, e a segunda é a razão da primeira:

1. abre o Chrome nessa vista;
2. no `--doc`, a foto passa a ser a **VISTA INTEIRA** em vez do recorte da
   `.janela` — porque é a vista que responde à pergunta dela. O que ela vê
   maximizada não é o cartão: é o cartão **mais** os vãos dos lados e a faixa
   morta embaixo, e é exatamente isso que o recorte jogava fora.

Sem `--vista` nada muda: 1920x1080, recorte na `.janela`, as fotos do README.

Uso:  olhar.py 05-vibracao.html [--publicado] [--vista 1918x840|dela]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402

# FULL HD, como a TV dela: a janela do produto abre com 1180 px dentro de
# 1920x1080. Medir em 1230 escondia o que sobra de vão dos lados e o quanto a
# aba passa da dobra.
LARG, ALT = 1920, 1080

#: A VISTA MAXIMIZADA DA MÁQUINA DELA, e cada parcela é medida — 11/09/2026.
#:
#: A TV é 1920x1080 a 100 % (`cosmic-randr`, saída DP-1). O que o compositor
#: come dela está medido pixel a pixel em
#: `docs/process/sprints/2026-09-09-ALTURA-DA-VISTA-01-*.md` §1, sobre a foto
#: da janela dela maximizada às 22:24 de 09/09:
#:
#:     painel do COSMIC (zona exclusiva)   82   em cima
#:     doca do COSMIC   (zona exclusiva)  110   embaixo
#:     borda da janela                      1   de cada lado
#:     Gtk.HeaderBar                       46   (= ponte_da_tela.ALTURA_DA_BARRA)
#:
#:     altura da vista: 1080 − 82 − 1 − 46 − 1 − 110 = 840   <- MEDIDO na foto
#:     largura da vista: 1920 − 1 − 1 = 1918                 <- derivado: o
#:         painel e a doca são de cima e de baixo, e não há zona exclusiva
#:         lateral; sobra a mesma borda de 1 px que a foto mostra em cima e
#:         embaixo. NÃO foi lida pixel a pixel — está na entrega, declarada.
VISTA_DELA = (1918, 840)

#: Onde as fotos da documentação moram — as mesmas que o README mostra.
DESTINO_DOC = onde.RAIZ / "docs" / "usage" / "assets"

#: E AS FOTOS DE VISTA MORAM AO LADO, NÃO POR CIMA — 11/09/2026.
#:
#: As duas famílias respondem perguntas diferentes: o recorte da `.janela` é a
#: miniatura do README (*"como é a aba?"*) e a vista é a tela dela maximizada
#: (*"como fica na TV dela?"*). Gravar as duas com o MESMO NOME repetiria, num
#: nível acima, a armadilha que o recibo existe para desfazer — e teria uma
#: consequência medida: o `CLAUDE.md` manda todo mundo rodar
#: `--todas --publicado --doc` antes de commitar, e a execução seguinte
#: apagaria calada a foto da vista. Pasta própria, recibo próprio.
SUBPASTA_DA_VISTA = "maximizada"

#: O NOME DAS FOTOS NÃO SE INVENTOU — 05/09/2026. O
#: `docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md` já pedia
#: `assets/aba-01-jogar.png` nas dez seções, e as dez imagens NÃO EXISTIAM: o
#: documento publicava dez imagens quebradas desde que foi escrito. O prefixo é
#: o que ele já cita, e o `--doc` passa a preencher exatamente esses dez nomes.
#:
#: As `readme_*.png` são da janela GTK. **A janela morreu em 06/09/2026 e elas
#: FICARAM**, que era a condição escrita aqui antes: apagá-las deixaria o
#: `docs/usage/interface.md` com furo, e o histórico de uma tela que existiu não
#: é fato errado a substituir — é decisão medida, e leva data. Nenhum
#: instrumento vivo as refaz, e é por isso que o recibo abaixo só soma o que
#: começa com este prefixo.
PREFIXO_NOVO = "aba-"

#: Só as DEZ abas. As avulsas (`mapa-do-controle`, `calibrar-sensores`,
#: `mapa-das-portas`) abrem por fora da janela e não são aba de documentação.
E_ABA = re.compile(r"^\d\d-")

#: O RECIBO, e ele diz DE QUE BANCADA a foto saiu — 08/09/2026.
#:
#: Este arquivo já existia, escrito pelo retratista da JANELA GTK
#: (`scripts/gui-captura/retratar_abas.py`), que saiu com ela em 06/09
#: (`D-0609-GTK-LEVA-INTEIRA`). O recibo ficou órfão: nomeava um programa
#: apagado e listava dezesseis fotos que nenhum instrumento vivo refaz.
#:
#: O FATO QUE ELE GUARDA NÃO CADUCOU, e a forma dele mudou de risco. Na janela
#: a pergunta era *"esta foto é medição ou dublê?"* — as onze abas podiam ser
#: alimentadas por IPC vivo ou por fixture, e sem o recibo ninguém separava.
#: Aqui não há essa dúvida: a foto é sempre de uma página do repositório. A
#: dúvida que sobra é OUTRA, e é a armadilha mais cara do `COMO-OLHAR-A-TELA`:
#:
#:   `--todas` fotografa a BANCADA (`mockup/`), o desenho sendo concluído;
#:   `--todas --publicado` fotografa o PRODUTO (`interface/paginas/`).
#:
#: As duas gravam PNG com o mesmo nome. Uma foto da bancada em
#: `docs/usage/assets/` documenta uma tela que o produto NÃO renderiza — e
#: reincidiu quatro vezes só em 31/08. O recibo é o que deixa isso legível
#: depois, sem reabrir o navegador.
NOME_DA_PROVA = "PROVA-DA-FOTO.txt"


def _gravar_prova_da_foto(destino: pathlib.Path, modo: str, origem: str,
                          vista: str = "") -> pathlib.Path:
    """O recibo do ensaio: quando, quantas, de que bancada, e a soma de cada PNG.

    `modo` é o que a pessoa pediu (`--todas --publicado --doc`); `origem` é a
    pasta de onde as páginas foram lidas, relativa à raiz — os dois, porque o
    primeiro é a INTENÇÃO e o segundo é o que de fato aconteceu, e é a
    divergência entre eles que denuncia o instrumento apontado para o lugar
    errado.

    A data existe por um motivo medido: uma mudança de tela que não move pixel
    deixa as fotos idênticas, e sem recibo o portão das fotos
    (`test_as_fotos_acompanham_a_versao`) ficaria vermelho para sempre — a
    régua confundindo a PALAVRA com o ATO, que é o defeito mais caro desta casa.
    """
    import datetime
    import hashlib

    pngs = sorted(p for p in destino.glob(f"{PREFIXO_NOVO}*.png") if p.is_file())
    linhas = [
        f"# Recibo do ensaio de fotos — gerado por {_meu_endereco()}",
        "#",
        "# NÃO edite à mão. Rode o retratista; ele reescreve este arquivo.",
        "# Existe porque uma mudança de tela que não move pixel deixa as fotos",
        "# idênticas, e sem este recibo o portão das fotos ficaria vermelho",
        "# para sempre.",
        "",
        f"ensaio:  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"abas:    {len(pngs)}",
        f"modo:    {modo}",
        f"origem:  {origem}",
        # A VISTA É PARTE DA PROCEDÊNCIA — 11/09/2026. Duas fotos da mesma
        # página em vistas diferentes são telas diferentes, e nada no PNG diz
        # em qual delas ele nasceu. Sem esta linha, a foto da vista maximizada
        # dela e a do recorte de 1600x777 ficam indistinguíveis na pasta.
        f"vista:   {vista or 'recorte da .janela'}",
        "",
        "# Toda linha destas imagens é PÁGINA DO REPOSITÓRIO fotografada num",
        "# Chrome headless — nenhuma delas é medição desta ou de qualquer",
        "# máquina, e o retratista não fala com o daemon (portão:",
        "# tests/unit/test_retrato_das_abas_nao_vaza_dado_real.py).",
        "",
        "# soma sha256 de cada foto, em ordem alfabética",
    ]
    for p in pngs:
        linhas.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")

    alvo = destino / NOME_DA_PROVA
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return alvo


def _meu_endereco() -> str:
    """Como o recibo se refere a quem o escreveu.

    DERIVADO DO PRÓPRIO ARQUIVO, e não digitado — é a razão inteira de esta
    função existir: o recibo velho nomeava `scripts/gui-captura/retratar_abas.py`
    e continuou nomeando por dois dias depois de o programa ser APAGADO,
    porque o nome era um literal. Um endereço que sai de `__file__` não pode
    envelhecer sem que o arquivo se mova junto.

    Instalado não há repositório acima, e `relative_to` levanta — aí o nome do
    módulo basta, e é o que se pode afirmar com honestidade.
    """
    meu = pathlib.Path(__file__).resolve()
    try:
        return str(meu.relative_to(onde.RAIZ))
    except ValueError:
        return f"hefesto_dualsense4unix.interface.{meu.stem}"


def _navegador(pw):
    # `ignore_default_args=["--hide-scrollbars"]` — 30/08/2026, e não é detalhe.
    # O Playwright headless passa `--hide-scrollbars` por default, e com ele o
    # Chrome NÃO PINTA barra de rolagem nenhuma: `offsetWidth == clientWidth`
    # mesmo num contêiner que rola 300px. Medido no mesmo dia, numa varredura das
    # dez abas: nove agentes concluíram "não há barra" e um deles ia relatar como
    # DEFEITO GRAVE um comentário do gerador que estava certo. A régua não media  # (noqa-acento: verbo medir, imperfeito)
    # a tela — media o próprio flag.  # (noqa-acento: verbo medir, imperfeito) verbo medir
    return pw.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        args=["--no-sandbox"],
        ignore_default_args=["--hide-scrollbars"],
    )


def _retratar(navegador, alvo: pathlib.Path, saida: pathlib.Path,
              so_a_janela: bool = False,
              vista: tuple[int, int] | None = None) -> dict:
    """Uma página, já assentada, medida e fotografada.

    `so_a_janela` recorta na moldura em vez de gravar a página inteira, e é o
    modo da DOCUMENTAÇÃO: a janela do produto tem 777 px de altura dentro de um
    viewport de 1080, então a foto de página inteira publica 300 px de fundo
    vazio — que numa miniatura de README come um terço da imagem.

    `vista` troca o viewport E o enquadramento: pedida a vista, a foto é o que
    a vista mostra (nem recorte, nem página inteira). Ver o topo do arquivo —
    com a `.janela` de altura fixa, o recorte é o mesmo pixel em toda vista, e
    "fotografar maximizado" só significa alguma coisa se a foto for a vista.
    """
    larg, alt = vista or (LARG, ALT)
    pg = navegador.new_page(viewport={"width": larg, "height": alt}, device_scale_factor=1)
    try:
        pg.goto(f"file://{alvo}")
        pg.wait_for_load_state("networkidle")
        # O QUE SE ESCONDE VEM DA FOLHA DO PILOTO, e não deste arquivo —
        # 06/09/2026. Aqui estava `.nota{display:none}` digitado, a segunda
        # cópia de um valor que tem dono: a foto mostrava o que o produto
        # esconde HOJE e continuaria mostrando no dia em que a folha ganhasse a
        # segunda regra de esconder. Agora ela pergunta.
        from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

        pg.add_style_tag(
            content="".join(f"{s}{{display:none}}" for s in seletores_escondidos())
        )
        pg.wait_for_timeout(400)
        # AS DUAS FAMÍLIAS DE PÁGINA, e ele precisa saber medir as duas: as dez
        # ABAS moram numa `.janela`; as páginas AVULSAS que abrem por fora dela (o
        # mapa do controle, a calibração) moram numa `.cx`. Antes ele só conhecia
        # a primeira e ESTOURAVA na segunda, com `Cannot read properties of null`
        # — que ao menos é um erro barulhento. O caso perigoso é o silencioso, e
        # por isso o `else` abaixo devolve o motivo em vez de um número inventado:
        # seletor que casou ZERO elemento é ERRO, nunca medida.
        # O `1080` ESTAVA DIGITADO AQUI, e era a segunda cópia da altura da
        # vista — 11/09/2026. Com a vista de 840 ele diria "passa 0 da dobra"
        # sobre uma página que passa 240: a régua responderia sobre o viewport
        # de ontem. Agora ela PERGUNTA à janela em que está.
        #
        # E as duas medidas NOVAS são as que a foto maximizada existe para
        # mostrar: `morto_abaixo` é o que sobra entre o rodapé da `.janela` e a
        # borda da vista (`ALTURA-DA-VISTA-01` §4.3: *"nenhuma régua a
        # enxerga — todas medem dentro da `.janela`, e a tela dela não para
        # ali"*), e `vao_dos_lados` é a mesma cegueira na largura.
        cx = pg.evaluate("""() => {
          const d = document.documentElement;
          const cx = document.querySelector('.janela') || document.querySelector('.cx');
          if (!cx) return {erro: 'nem .janela nem .cx nesta página — não há o que medir'};
          const j = cx.getBoundingClientRect();
          return {caixa: cx.className, larg: Math.round(j.width), alt: Math.round(j.height),
                  vista: `${window.innerWidth}x${window.innerHeight}`,
                  morto_abaixo: Math.round(window.innerHeight - j.bottom),
                  vao_dos_lados: Math.round((window.innerWidth - j.width) / 2),
                  passa_da_dobra: Math.max(0, Math.round(d.scrollHeight - window.innerHeight)),
                  rolagem_lateral: d.scrollWidth > d.clientWidth};
        }""")
        if cx.get("erro"):
            return {"erro": cx["erro"]}
        # PÁGINA INTEIRA: o viewport de 1080 cortava tudo o que nasce abaixo da
        # dobra, e era justamente o que ela precisava ver.
        saida.parent.mkdir(parents=True, exist_ok=True)
        moldura = pg.query_selector(".janela") or pg.query_selector(".cx")
        if vista is not None:
            # A VISTA PEDIDA: nem recorte, nem página inteira — o que a vista
            # mostra. É o único enquadramento que responde *"como fica
            # maximizado?"*, porque é o único que carrega o que está FORA da
            # `.janela` e dentro da tela.
            pg.screenshot(path=str(saida))
        elif so_a_janela and moldura is not None:
            moldura.screenshot(path=str(saida))
        else:
            pg.screenshot(path=str(saida), full_page=True)
        return {"png": str(saida), **cx}
    finally:
        pg.close()


def _uma(arq: str, publicado: bool, vista: tuple[int, int] | None = None) -> int:
    alvo = onde.pagina(arq, publicado=publicado)
    saida = pathlib.Path(f"/tmp/olhar-{arq[:2]}{'-publicado' if publicado else ''}.png")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            r = _retratar(nav, alvo, saida, vista=vista)
        finally:
            nav.close()
    if "erro" in r:
        sys.exit(f"ERRO ao medir {arq}: {r['erro']}")
    print(json.dumps({**r, "olhou": str(alvo.relative_to(onde.RAIZ))}))
    return 0


def _todas(publicado: bool, para_a_doc: bool,
           vista: tuple[int, int] | None = None) -> int:
    paginas = [p for p in onde.paginas(publicado=publicado) if E_ABA.match(p.name)]
    # RETRATISTA QUE ACHA ZERO NÃO É RETRATISTA VERDE: se a pasta mudar de
    # lugar, ele reprova em vez de dizer "pronto" sobre nenhuma foto.
    if len(paginas) < 10:
        sys.exit(f"achei {len(paginas)} abas em {'publicado' if publicado else 'bancada'} — o caminho mudou?")

    if not para_a_doc:
        destino = pathlib.Path("/tmp")
    elif vista is not None:
        destino = DESTINO_DOC / SUBPASTA_DA_VISTA
    else:
        destino = DESTINO_DOC
    from playwright.sync_api import sync_playwright

    saiu: list[dict] = []
    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            for p in paginas:
                nome = f"{PREFIXO_NOVO}{p.stem}.png" if para_a_doc else f"olhar-{p.stem}.png"
                r = _retratar(nav, p, destino / nome, so_a_janela=para_a_doc,
                              vista=vista)
                if "erro" in r:
                    sys.exit(f"ERRO ao medir {p.name}: {r['erro']}")
                saiu.append({"aba": p.name, **r})
        finally:
            nav.close()

    for r in saiu:
        dobra = f" · passa {r['passa_da_dobra']} px da dobra" if r["passa_da_dobra"] else ""
        sobra = f" · {r['morto_abaixo']} px mortos embaixo" if r["morto_abaixo"] else ""
        lados = f" · vão {r['vao_dos_lados']} px de cada lado" if r["vao_dos_lados"] else ""
        print(f"{r['aba']:<20} {r['larg']}x{r['alt']} em {r['vista']}"
              f"{dobra}{sobra}{lados}  ->  {r['png']}")
    print(f"\n{len(saiu)} abas retratadas em {destino}")

    # O RECIBO SÓ NO `--doc`, e a assimetria é de propósito: `/tmp` é rascunho,
    # e `docs/usage/assets/` é o que a próxima pessoa lê sem ter visto o
    # comando. É lá que a diferença entre a bancada e o produto precisa estar
    # escrita.
    if para_a_doc:
        origem = paginas[0].parent
        try:
            origem_legivel = str(origem.relative_to(onde.RAIZ))
        except ValueError:
            origem_legivel = str(origem)
        pedida = f"{vista[0]}x{vista[1]}" if vista else ""
        recibo = _gravar_prova_da_foto(
            destino,
            modo=("--todas --publicado --doc" if publicado else "--todas --doc")
            + (f" --vista {pedida}" if pedida else ""),
            origem=origem_legivel,
            vista=pedida,
        )
        print(f"recibo: {recibo}")
    return 0


#: ONDE UMA FRASE DE TELA PODE TER NASCIDO: os dez geradores (o desenho e a
#: legenda) e os dez pacotes (o que o piloto escreve por tique). `app/` fica de
#: fora porque não é posse desta sprint — e quando a origem não está aqui, o
#: instrumento diz "não achei", que é a resposta honesta.
def _fontes() -> list[pathlib.Path]:
    aqui = pathlib.Path(__file__).resolve().parent
    return sorted(aqui.glob("aba??.py")) + sorted((aqui / "pacotes").glob("a??_*.py"))


def _de_onde(trecho: str) -> str:
    """O arquivo:linha do gerador que escreveu ``trecho``, ou por que não achei.

    DUAS COISAS SEPARAM O FONTE DA PÁGINA, e ignorar qualquer uma devolve "não
    achei" sobre um arquivo que está logo ali:

    * **a quebra de linha** — a mesma frase mora numa linha do HTML e em duas do
      fonte, com o recuo no meio. Por isso a busca é por regex com `\\s+` no
      lugar de todo espaço, e não por `str.find`;
    * **o tamanho** — a legenda é escrita em literais que o Python junta, e um
      pedaço de 60 letras pode cair bem no ponto da emenda. Ele tenta 60, 40,
      24 e 14, e para na primeira medida que casa.
    """
    for tamanho in (60, 40, 24, 14):
        alvo = trecho[:tamanho].strip()
        if len(alvo) < 8:
            continue
        # o último pedaço pode ter sido cortado no meio de uma palavra; o `\s+`
        # não ajuda aí, então a busca é do começo até o último espaço inteiro.
        agulha = re.compile(r"\s+".join(re.escape(p) for p in alvo.split()))
        achados = []
        for fonte in _fontes():
            texto = fonte.read_text(encoding="utf-8")
            m = agulha.search(texto)
            if m is not None:
                achados.append(f"{fonte.name}:{texto.count(chr(10), 0, m.start()) + 1}")
        if achados:
            return " · ".join(achados[:3])
    return "não achei no fonte (pode vir de `app/`, que não é desta posse)"


def _palavra(alvo: str, publicado: bool) -> int:
    """A palavra que uma pessoa LÊ, página por página, com origem e contexto."""
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        _borda,
        texto_visivel,
        texto_visivel_no_produto,
    )

    # AS DUAS LEITURAS, e a diferença é o ponto inteiro deste instrumento:
    # a BANCADA ela abre no navegador crua, e ali a `.nota` é texto de verdade;
    # o PRODUTO renderiza com a folha do piloto por cima, que apaga a `.nota`.
    # Contar a `.nota` no modo `--publicado` deu 34 "ocorrências visíveis em o
    # produto" sobre uma tela que não mostrava nenhuma (06/09/2026).
    ler = texto_visivel_no_produto if publicado else texto_visivel

    paginas = [p for p in onde.paginas(publicado=publicado) if E_ABA.match(p.name)]
    if len(paginas) < 10:
        sys.exit(f"achei {len(paginas)} abas — o caminho mudou?")

    total = 0
    for p in paginas:
        cru = p.read_text(encoding="utf-8")
        visivel = ler(cru)
        achados = list(_borda(alvo).finditer(visivel))
        total += len(achados)
        print(f"\n{p.name}  —  {len(achados)} ocorrência(s) visível(eis)")
        for m in achados:
            linha = visivel.count("\n", 0, m.start()) + 1
            a, b = max(0, m.start() - 55), m.end() + 55
            contexto = " ".join(visivel[a:b].split())
            print(f"  linha {linha}: …{contexto}…")
            print(f"      vem de: {_de_onde(' '.join(cru[m.start():b].split()))}")
    print(f"\n{alvo!r}: {total} ocorrência(s) visível(eis) em "
          f"{'o produto' if publicado else 'a bancada'}")
    return 1 if total else 0


def _vista_pedida(texto: str) -> tuple[int, int]:
    """`1918x840` -> `(1918, 840)`, e recusa qualquer outra forma.

    RECUSAR É METADE DO TRABALHO: um `--vista 1918` aceito calado viraria uma
    vista inventada, e a foto sairia respondendo sobre outra tela — que é o
    defeito que esta casa mais paga.

    A palavra `dela` resolve para a vista maximizada da máquina dela, medida em
    `VISTA_DELA`, para que esse número não precise ser redigitado a cada
    execução — um número com dono, digitado de novo, é um número esperando
    para envelhecer.
    """
    if texto.strip().lower() == "dela":
        return VISTA_DELA
    m = re.fullmatch(r"\s*(\d{3,5})\s*[xX×]\s*(\d{3,5})\s*", texto)
    if not m:
        raise argparse.ArgumentTypeError(
            f"vista {texto!r} não tem a forma LARGURAxALTURA (ex.: 1918x840), "
            "nem é a palavra 'dela'"
        )
    return int(m.group(1)), int(m.group(2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="fotografa a interface nova")
    p.add_argument("pagina", nargs="?",  # (noqa-acento)  (nome do argumento)
                   help="uma página, com extensão: 05-vibracao.html")
    p.add_argument("--publicado", action="store_true", help="o que o produto renderiza")
    p.add_argument("--todas", action="store_true", help="as dez abas de uma vez")
    p.add_argument("--doc", action="store_true", help="grava em docs/usage/assets/")
    p.add_argument("--palavra", metavar="PALAVRA",
                   help="lista onde esta palavra é LIDA nas dez abas, com a origem")
    p.add_argument("--vista", metavar="LARGxALT", type=_vista_pedida,
                   help="a vista em que fotografar — 'dela' é a janela dela "
                        "maximizada. Com ela a foto é a VISTA INTEIRA, não o "
                        "recorte da .janela")
    a = p.parse_args(argv)
    if a.palavra:
        return _palavra(a.palavra, a.publicado)
    if a.todas:
        return _todas(a.publicado, a.doc, a.vista)
    if not a.pagina:  # (noqa-acento)  (nome do argumento)
        p.error("diga a página, ou peça --todas")
    if a.doc:
        p.error("--doc é do modo --todas")
    return _uma(a.pagina, a.publicado, a.vista)  # (noqa-acento)  (nome do argumento)


if __name__ == "__main__":
    sys.exit(main())
