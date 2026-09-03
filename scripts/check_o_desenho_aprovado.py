#!/usr/bin/env python3
"""O produto não anda na frente do desenho dela, e não fica atrás dele calado.

DECISÃO DELA, 31/08/2026, com o diagnóstico dela:

    "o problema original foi não ter separado a pasta do mockup e ter feito a
    interface usando o HTML do mockup. **Se alteramos no layout final a
    referência do mockup se perde.**"

E a reorientação do mesmo dia, que é o que inverteu este arquivo:

    "primeiro **nunca terminamos o mockup**, por isso não era pra ser feito no
    layout final. **Vamos concluir lá e depois seguimos pra interface.**"

O FLUXO, e a direção é `mockup/` → `layout/`:

    src/hefesto_dualsense4unix/interface/abaNN.py   ← os geradores ficam aqui
              │  python3 abaNN.py
    mockup/NN-*.html               ← a BANCADA. O desenho sendo concluído.
              │  --publicar NN, depois do OK dela na aba INTEIRA
    layout/NN-*.html               ← o PUBLICADO. É o que o produto renderiza.

ELE NASCEU INVERTIDO, e o ponto 0 do `mockup/TODO-DELA.md` era consertá-lo. Na
primeira versão o `--aprovar` copiava `layout/` → `mockup/`, o que faz o desenho
seguir o produto — o contrário do que ela decidiu. Enquanto isso valia, todo
desenho novo caía direto no produto que ela usa: `monta()` gravava em `layout/`,
e `src/hefesto_dualsense4unix/interface/paginas/02-controles.html` é a página que o piloto `controles_vivos.py` abre
num `WebKit2.WebView`. Gerar uma aba **já trocava o produto**, sem passar pelo
olho dela.

QUANDO O PUBLICADO RECEBE, e é escolha dela em 31/08: **a cada aba fechada** —
quando todos os pontos daquela aba do `mockup/TODO-DELA.md` tiverem o OK dela.
Nem a cada ponto, nem só no fim da lista.

O QUE ELE MEDE: sha256, arquivo a arquivo. Reprova quando o produto está **atrás
do desenho** sem que a aba esteja declarada em trabalho em `mockup/DIVERGENCIAS.md`.

O QUE ELE NÃO FAZ, e é decisão: não compara byte a byte dentro do arquivo. Um
diff de HTML gerado seria ruído — a régua diz QUAL página se afastou, e o
`git diff` diz o quê. Uma linha por arquivo é acionável; mil linhas de diff são
desligadas na primeira semana.

    check_o_desenho_aprovado.py            confere (rc=1 se o produto estiver atrás)
    check_o_desenho_aprovado.py --publicar        ela aprovou tudo: publica as dez
    check_o_desenho_aprovado.py --publicar 02 09  ela aprovou essas abas
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
#: A bancada — o desenho de hoje. É onde os geradores escrevem e é o que ela olha.
sys.path.insert(0, str(RAIZ / "src"))
from hefesto_dualsense4unix.interface import onde

BANCADA = onde.BANCADA
#: O publicado — o que o produto renderiza. Só muda pelo `--publicar`.

PUBLICADO = onde.PUBLICADO
DECLARACOES = BANCADA / "DIVERGENCIAS.md"


def paginas() -> list[str]:
    """As páginas que a régua cobre, enumeradas a partir da BANCADA.

    A enumeração mudou de lado junto com o fluxo: página nova nasce no desenho,
    não no produto. `.dc.html` fica de FORA — são canvas de ferramenta de desenho
    (logo, paleta, telas), ferramenta de desenho, não página que ela abre.
    Cobri-los faria o portão cobrar publicação de rascunho.
    """
    return sorted(
        p.name
        for p in BANCADA.glob("*.html")
        if not p.name.startswith(".") and not p.name.endswith(".dc.html")
    )


#: O QUE NÃO MUDA UM PIXEL, e por isso não conta como divergência de DESENHO.
#:
#: Decisão dela, 01/09/2026, com a razão: *"a ideia do mockup é o desenho ser
#: possível de ser comparado ao produto final. sempre a nossa referência."* —
#: e, sobre este portão: *"ok, pode comparar então o que se vê."*
#:
#: POR QUE ELE PRECISOU EXISTIR: ligar a interface exige marcar cada valor da
#: tela com um endereço (`data-campo`, `data-papel`, `data-gesto`) para a pintura
#: saber onde escrever. São 100 marcações nas dez abas, e nenhuma move um pixel —
#: mas todas mudam o sha256. Sem esta regra, o portão passaria a acusar
#: divergência em toda aba que ganhasse vida, e a resposta natural seria
#: desligá-lo. **Portão que grita falso é portão que se desliga.**
#:
#: A ALTERNATIVA ERA PIOR, e ela chegou a pedi-la: *"ajustar o portão pra ignorar
#: o mockup"*. Ignorar mata a régua inteira; comparar o que se VÊ mantém-na
#: medindo exatamente o que ela nasceu para medir.
#:
#: O QUE CONTINUA ACUSANDO: texto, classe, estilo, estrutura, ordem — tudo o que
#: chega aos olhos. Trocar uma palavra, mover um bloco ou mudar uma cor reprova
#: como sempre reprovou. A mordida abaixo prova as duas metades.
INVISIVEIS = re.compile(
    r'\s(?:data-campo|data-papel|data-gesto|data-controle|data-uniq|data-id'
    r'|data-eixo|data-bloco|data-lado|data-sensor|data-mudo|data-rota'
    r'|data-mic-modo|data-forca|data-mascara|data-conectado|data-lista'
    r'|data-degrau|data-modo|data-gatilho|data-entrada|data-clique'
    # `data-hef` e `data-hef-gesto` são o esquema que a aba Perfis usa — o
    # outro agente marcou as 77 do arquivo dela com esse nome enquanto eu
    # usava `data-campo` nas minhas. OS DOIS CONVIVEM de propósito: unificar
    # agora custaria reescrever 77 marcações que já funcionam, e o nome do
    # atributo não é o contrato — o contrato é o despachante, que aceita os
    # dois. O que NÃO pode é um deles ficar de fora daqui e o portão acusar
    # divergência de desenho onde só há endereço.
    r'|data-hef-gesto|data-hef|data-ajuste|data-player'
        r'|data-hex|data-v|data-hef-alvo|data-hef-rolar'
    # `data-hef-quando` e `data-hef-classe` SÃO O RESTO DO ALVO `classe`, e a
    # falta deles aqui era um buraco de ESTRUTURA — 03/09/2026. O alvo `classe`
    # do piloto (`hefesto_vivo.escrever`) precisa de três atributos no mesmo
    # elemento: `data-campo` (o endereço), `data-hef-alvo="classe"` (o alvo) e
    # `data-hef-quando` (qual valor acende) / `data-hef-classe` (que classe).
    # Os dois primeiros estavam nesta lista e os dois últimos não — logo TODO
    # endereço de estado por classe caía como "o DESENHO mudou" no
    # `--publicar-enderecos`, e a única saída era o `--publicar`, que é ato
    # dela. Nenhum dos dois chega aos olhos: medido por grep, não há uma regra
    # de CSS `[data-hef-quando]` nem `[data-hef-classe]` em nenhuma das dez
    # páginas — eles são endereço puro, como os trinta acima.
    r'|data-hef-quando|data-hef-classe'
    r'|data-linha|data-hef-forma|data-face'
    r')="[^"]*"'
)


def o_que_se_ve(caminho: Path) -> bytes:
    """O HTML sem os endereços de pintura — o que chega aos olhos.

    NÃO É "ignorar atributo": é ignorar ESTES, nomeados um a um. Uma regra
    genérica (`data-*`) engoliria também o `data-colorway`, que PINTA o desenho
    inteiro — e aí o portão deixaria passar a troca da cor do plástico, que é a
    informação de qual controle é qual.
    """
    return INVISIVEIS.sub("", caminho.read_text(encoding="utf-8")).encode("utf-8")


def soma(caminho: Path) -> str:
    return hashlib.sha256(o_que_se_ve(caminho)).hexdigest()


def declaradas() -> set[str]:
    """As páginas declaradas EM TRABALHO, lidas dos títulos `## nome.html`.

    A razão fica no corpo da seção e é para gente ler; o portão só cobra que a
    seção EXISTA. Cobrar o formato da razão faria a régua brigar com quem
    escreve bem — é a lição do `SERVE_UM_LADO_SO`.
    """
    if not DECLARACOES.exists():
        return set()
    texto = DECLARACOES.read_text(encoding="utf-8")
    # SÓ DEPOIS DO `---`: o cabeçalho do arquivo mostra o FORMATO com um exemplo
    # (`## 01-jogar.html`), e ler o exemplo como declaração faria o portão
    # absolver de graça a primeira aba da lista. Pego na primeira execução.
    corpo = texto.split("\n---\n", 1)[-1]
    return {m.group(1).strip() for m in re.finditer(r"^##\s+(\S+\.html)\s*$", corpo, re.M)}


def medir() -> tuple[list[str], list[str], list[str]]:
    """Devolve (atrasadas, só-na-bancada, só-no-publicado)."""
    atrasadas, so_bancada, so_publicado = [], [], []
    for nome in paginas():
        no_produto = PUBLICADO / nome
        if not no_produto.exists():
            so_bancada.append(nome)
        elif soma(BANCADA / nome) != soma(no_produto):
            atrasadas.append(nome)
    for p in PUBLICADO.glob("*.html"):
        if p.name.endswith(".dc.html"):
            continue
        if not (BANCADA / p.name).exists():
            so_publicado.append(p.name)
    return atrasadas, so_bancada, sorted(so_publicado)


def _alvos(argv: list[str]) -> list[str]:
    """Traduz `--publicar 02 09` nos nomes de arquivo. Sem argumento: todas."""
    pedidos = [a for a in argv if not a.startswith("-")]
    if not pedidos:
        return paginas()
    escolhidas, desconhecidos = [], []
    for pedido in pedidos:
        casam = [n for n in paginas() if n == pedido or n.startswith(f"{pedido}-")]
        if casam:
            escolhidas.extend(casam)
        else:
            desconhecidos.append(pedido)
    if desconhecidos:
        # RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE. Um `--publicar 11` calado
        # publicaria NADA e imprimiria sucesso — o silêncio que esta casa já
        # pagou quatro vezes em 31/08. Aqui ele é erro, com a lista ao lado.
        raise SystemExit(
            f"ERRO: não achei página para {', '.join(desconhecidos)}.\n"
            f"  As que existem na bancada: {', '.join(paginas())}"
        )
    return sorted(set(escolhidas))


def publicar(argv: list[str]) -> int:
    """Leva o desenho ao produto. É o que roda depois do OK dela numa aba."""
    alvos = _alvos(argv)
    atrasadas, _, _ = medir()
    for nome in alvos:
        shutil.copy2(BANCADA / nome, PUBLICADO / nome)
    # A página que sumiu da bancada some do produto — mas SÓ numa publicação
    # geral. Publicar uma aba não pode apagar outra.
    if len(alvos) == len(paginas()):
        for p in PUBLICADO.glob("*.html"):
            if not p.name.endswith(".dc.html") and not (BANCADA / p.name).exists():
                p.unlink()
    _tirar_declaracoes(alvos)
    mudaram = [n for n in alvos if n in atrasadas]
    print(f"publicado: {len(alvos)} página(s) · {len(mudaram)} mudou/mudaram de fato")
    for nome in mudaram:
        print(f"  - {nome}")
    if not mudaram:
        print("  (o produto já estava igual ao desenho nessas páginas)")
    return 0


#: A frase que toda declaração precisa ter: o que o produto FAZ enquanto espera.
#:
#: PEÇA 3 da cura de 02/09/2026, decidida por ela. Uma declaração que só diz
#: "esta aba mudou" deixa a próxima pessoa adivinhar o custo da espera — e o
#: custo foi medido três vezes num dia: clique morto, tela afirmando o contrário
#: e conteúdo vazando por cima da linha de baixo.
#:
#: A declaração passa a ser CONTRATO: ela diz o que ela vê HOJE, com a página
#: que o produto renderiza agora.
DIZ_O_QUE_ESPERA = re.compile(
    r"enquanto|at[ée] (?:ela |voc[êe] )?publicar|hoje ela v[êe]|"
    r"o produto continua|na tela dela hoje|sem publicar|at[ée] l[áa]",
    re.I,
)


def declaracoes_sem_custo() -> list[str]:
    """As seções que não dizem o que o produto faz enquanto espera o OK dela."""
    if not DECLARACOES.exists():
        return []
    _, sep, corpo = DECLARACOES.read_text(encoding="utf-8").partition("\n---\n")
    if not sep:
        return []
    mudas, atual, texto = [], None, []
    for linha in corpo.splitlines():
        titulo = re.match(r"^##\s+(\S+\.html)\s*$", linha)
        if titulo:
            if atual and not DIZ_O_QUE_ESPERA.search("\n".join(texto)):
                mudas.append(atual)
            atual, texto = titulo.group(1), []
        elif atual:
            texto.append(linha)
    if atual and not DIZ_O_QUE_ESPERA.search("\n".join(texto)):
        mudas.append(atual)
    return mudas


def so_mudou_endereco(nome: str) -> bool:
    """A bancada e o produto MOSTRAM a mesma coisa, e só os endereços mudaram?

    `o_que_se_ve` apaga os trinta atributos de endereçamento antes de comparar;
    se as duas páginas batem depois disso, a diferença não move um pixel.
    """
    no_produto = PUBLICADO / nome
    if not no_produto.exists():
        return False
    return o_que_se_ve(BANCADA / nome) == o_que_se_ve(no_produto)


def publicar_enderecos(argv: list[str]) -> int:
    """Leva ao produto SÓ o que não muda um pixel — e recusa o resto.

    POR QUE ISTO EXISTE, e ela decidiu em 02/09/2026 depois de a armadilha
    derrubar TRÊS frentes num dia:

    O pacote (Python) e o desenho (HTML) mudam juntos e chegam ao produto em
    tempos diferentes — o pacote entra no merge, o desenho espera o OK dela. No
    intervalo, o produto roda com METADE NOVA E METADE VELHA, e é aí que o
    clique morre calado (o gesto emite o rótulo novo, a página publicada só
    oferece o antigo) e o conteúdo vaza (o pacote enche uma caixa que só cresce
    na bancada).

    **Mas metade do que esperava por ela NUNCA FOI DECISÃO DELA.** Um
    `data-campo` novo num elemento que já existia não muda nada do que ela vê:
    não há o que aprovar. O que ela decide é o DESENHO — rótulo, ordem, tamanho,
    o que aparece.

    Esta função separa os dois. Ela publica a página **só se** o desenho for
    idêntico, e RECUSA dizendo quando um pixel mudou — nesse caso o `--publicar`
    continua sendo o caminho, e continua sendo ato dela.

    A distinção não é nova: o portão já a fazia em `o_que_se_ve`. O que faltava
    era ela chegar à publicação.
    """
    alvos = _alvos(argv)
    levadas, recusadas, ja_iguais = [], [], []
    for nome in alvos:
        if not (PUBLICADO / nome).exists():
            recusadas.append((nome, "a página não existe no produto — é desenho novo"))
        # "JÁ IGUAL" É BYTE A BYTE, e não pelo que se VÊ — 03/09/2026.
        #
        # Estava `soma(BANCADA) == soma(PUBLICADO)`, e `soma` é o sha256 do
        # `o_que_se_ve`, que APAGA os trinta atributos de endereço antes de
        # comparar. Duas páginas que diferem SÓ num `data-hef-alvo` têm a mesma
        # `soma` — então caíam aqui, em "já igual", e o `shutil.copy2` do ramo
        # de baixo nunca rodava. Pior: o ramo era INALCANÇÁVEL por construção,
        # porque `so_mudou_endereco` é exatamente `soma igual`, e o `elif`
        # acima já tinha levado esse caso embora. **Esta função nunca carregou
        # uma página**, e o que ela existe para carregar é precisamente o
        # endereço que não muda um pixel.
        #
        # Medido no `10-perfis.html` com o `data-hef-alvo="classe"` novo:
        # bytes iguais = False, `soma()` igual = True, `so_mudou_endereco` =
        # True — e a saída dizia "0 levada(s) · 1 já igual(is)".
        elif (BANCADA / nome).read_bytes() == (PUBLICADO / nome).read_bytes():
            ja_iguais.append(nome)
        elif so_mudou_endereco(nome):
            shutil.copy2(BANCADA / nome, PUBLICADO / nome)
            levadas.append(nome)
        else:
            recusadas.append((nome, "o DESENHO mudou — isto é decisão dela"))

    print(f"endereços: {len(levadas)} levada(s) · {len(recusadas)} recusada(s) "
          f"· {len(ja_iguais)} já igual(is)")
    for nome in levadas:
        print(f"  levada   {nome}  (nenhum pixel mudou)")
    for nome, porque in recusadas:
        print(f"  RECUSADA {nome}  ({porque})")
    if recusadas:
        print("\n  As recusadas esperam o OK dela:")
        for nome, _ in recusadas:
            print(f"      scripts/check_o_desenho_aprovado.py --publicar {nome[:2]}")
    # As levadas deixam de estar em trabalho SÓ se nada mais as separa.
    _tirar_declaracoes([n for n in levadas if soma(BANCADA / n) == soma(PUBLICADO / n)])
    return 0


def _tirar_declaracoes(alvos: list[str]) -> None:
    """Apaga do DIVERGENCIAS.md a seção das páginas publicadas.

    A aba deixou de estar em trabalho: a declaração sai junto. Declaração que
    envelhece calada vira paisagem, e paisagem ninguém lê.
    """
    if not DECLARACOES.exists():
        return
    texto = DECLARACOES.read_text(encoding="utf-8")
    cabeca, sep, corpo = texto.partition("\n---\n")
    if not sep:
        return
    guardadas, pulando = [], False
    for linha in corpo.splitlines():
        titulo = re.match(r"^##\s+(\S+\.html)\s*$", linha)
        if titulo:
            pulando = titulo.group(1).strip() in alvos
        if not pulando:
            guardadas.append(linha)
    novo = "\n".join(guardadas).strip("\n")
    if not re.search(r"^##\s+\S+\.html\s*$", novo, re.M):
        novo = "<!-- Nenhuma aba em trabalho: o produto está igual ao desenho dela. -->"
    DECLARACOES.write_text(f"{cabeca}\n---\n\n{novo}\n", encoding="utf-8")


def main() -> int:
    if not BANCADA.exists():
        print("ERRO: não há `mockup/`. Ela é a bancada — sem ela não há desenho.")
        return 2
    if "--publicar-enderecos" in sys.argv:
        return publicar_enderecos(
            sys.argv[sys.argv.index("--publicar-enderecos") + 1:]
        )
    if "--publicar" in sys.argv:
        return publicar(sys.argv[sys.argv.index("--publicar") + 1:])
    if "--aprovar" in sys.argv:
        # O NOME ANTIGO NÃO FICA CALADO. Ele copiava `layout/` → `mockup/`, que
        # é a direção errada; quem o digitar por hábito faria o desenho seguir o
        # produto e apagaria em silêncio o que ela aprovou.
        print("ERRO: `--aprovar` copiava o PRODUTO para o DESENHO — a direção errada.")
        print("  O fluxo é `mockup/` → `layout/`. O comando de hoje é:")
        print("      scripts/check_o_desenho_aprovado.py --publicar [NN ...]")
        return 2

    atrasadas, so_bancada, so_publicado = medir()
    decl = declaradas()
    sem_declarar = [n for n in atrasadas if n not in decl]
    orfas = sorted(decl - set(atrasadas) - set(so_bancada))

    print(f"desenho: {len(paginas())} página(s) na bancada `mockup/`")
    print(f"  o produto já tem ..... {len(paginas()) - len(atrasadas) - len(so_bancada)}")
    print(f"  o produto está atrás . {len(atrasadas)}  ({len(atrasadas) - len(sem_declarar)} em trabalho)")

    if so_publicado:
        print(f"\nFALHA: {len(so_publicado)} página(s) do produto sumiram do desenho:")
        for n in so_publicado:
            print(f"  - {n}")
        print("  O produto renderiza uma página sem referência — é o colapso que ela mandou desfazer.")
    if so_bancada and any(n not in decl for n in so_bancada):
        novas = [n for n in so_bancada if n not in decl]
        print(f"\nFALHA: {len(novas)} página(s) novas no desenho e ainda fora do produto:")
        for n in novas:
            print(f"  - {n}")
        print("  Declare a aba em trabalho, ou publique quando ela aprovar.")
    if sem_declarar:
        print(f"\nFALHA: o produto está ATRÁS do desenho em {len(sem_declarar)} página(s), sem declaração:")
        for n in sem_declarar:
            print(f"  - {n}")
        print(f"\n  Veja o que mudou:   diff <(git show HEAD:layout/{sem_declarar[0]}) mockup/{sem_declarar[0]}")
        print(f"  Se a aba ainda está em trabalho, declare em {DECLARACOES.relative_to(RAIZ)}:")
        print(f"      ## {sem_declarar[0]}")
        print("      - **31/08/2026** — o ponto da lista que está aberto nela.")
        print("  Se ela aprovou a aba INTEIRA:")
        print(f"      scripts/check_o_desenho_aprovado.py --publicar {sem_declarar[0][:2]}")
    if orfas:
        print(f"\nFALHA: {len(orfas)} declaração(ões) sem trabalho aberto — APAGUE de {DECLARACOES.name}:")
        for n in orfas:
            print(f"  - {n}")
        print("  Declaração que envelhece calada vira paisagem, e paisagem ninguém lê.")

    mudas = declaracoes_sem_custo()
    if mudas:
        print(f"\nFALHA: {len(mudas)} declaração(ões) não dizem o que o produto FAZ")
        print("       enquanto espera o OK dela:")
        for n in mudas:
            print(f"  - {n}")
        print("\n  Isto custou TRÊS frentes em 02/09/2026, e sempre do mesmo jeito: o")
        print("  pacote foi para o merge com o rótulo novo e a página publicada ficou")
        print("  com o antigo. O produto rodou com metade nova e metade velha —")
        print("  clique morto, tela afirmando o contrário, conteúdo vazando.")
        print("\n  Escreva na seção o que ela vê HOJE, com a página de agora. Por")
        print("  exemplo: `Até publicar, o pacote se limita às quatro casas que a")
        print("  página tem e diz quantos ajustes ficaram de fora.`")

    if (sem_declarar or so_publicado or orfas or mudas
            or [n for n in so_bancada if n not in decl]):
        return 1
    print("\nOK: o produto não está atrás do desenho dela sem dizer por quê.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
