"""Toda cura de HOST do `install.sh` alcança os DOIS lados do `exit 0`.

O `install.sh` tem uma cerca no meio: `if [[ "${FORMAT}" != "native" ]]` abre o
ramo dos formatos (flatpak/appimage/deb), que termina em `exit 0`; tudo o que
vem depois do `fi` é o ramo nativo. São DOIS caminhos de instalação, e uma cura
servida de um lado só some para metade das pessoas que instalam.

Esse defeito já aconteceu, com nome e data:

  - achado #7 da Onda S — o broker `hide-hidraw` só rodava no caminho nativo, e
    `--flatpak`/`--appimage`/`--deb` saíam pelo `exit 0` sem ele e sem aviso; o
    P2 duplicado voltava em qualquer jogo sem wrapper;
  - TECLADO-QUE-NAO-DIGITA-01 — o mesmo, uma camada acima: os formatos saíam sem
    o único caminho do produto para digitar texto;
  - MIC-EM-TODO-FORMATO-01 (10/08/2026) — o promotor do microfone do controle
    ficava para trás "por acidente de posição", e o que qualquer aplicativo
    gravava era o eco da saída em vez da voz dela.

Cada um desses foi curado à mão, com um bloco de comentário explicando a
posição. Este arquivo é a GENERALIZAÇÃO desses blocos: o que eles conferem uma
cura por vez, ele confere para todas, e para a próxima.

A ÂNCORA É O SUFIXO `_host`, e ele já é o léxico da casa: uma função `*_host()`
do `install.sh` declara, no nome, que faz trabalho de HOST — mudança de
sistema, ortogonal ao formato do aplicativo. Se é ortogonal ao formato, tem de
acontecer em todo formato. A lista é DERIVADA do arquivo, nunca digitada aqui.

PREÇO MEDIDO EM 12/08/2026: SETE funções `*_host` (não seis — o
`install_dkms_rtw88_usb_host` costuma ser esquecido nas contagens à mão), todas
já servidas dos dois lados. ZERO reprovações. Este portão não cobra dívida
velha; ele impede a próxima.

AS DUAS ARMADILHAS DA RÉGUA, e como cada uma é tratada:

1. POSIÇÃO NO ARQUIVO NÃO É LADO. `install_udev_host` é chamado nas linhas 900 e
   932, que ficam ANTES da cerca — e contá-las como "preâmbulo comum" é errado:
   elas estão DENTRO dos corpos de `format_flatpak` e `format_appimage`, que só
   rodam do lado dos formatos. Por isso a régua ignora a posição e faz
   alcançabilidade de verdade: monta o grafo de chamadas do arquivo e fecha
   transitivamente a partir do código de TOPO de cada região.

2. A PROMESSA PODE SER SERVIDA SEM A FUNÇÃO. Fechado o grafo, `install_udev_host`
   NÃO é alcançável do lado nativo — e mesmo assim as regras udev são
   instaladas lá, porque o passo 3 do fluxo nativo executa o mesmo
   `scripts/install_udev.sh` diretamente. A âncora é a PROMESSA, não a cura: se
   a função delega o trabalho inteiro a helpers de `scripts/` e o outro lado
   executa esses mesmos helpers, a promessa está cumprida e o silêncio é justo.
   Sem essa segunda régua o portão nasceria gritando na única função em que já
   está certo — e portão que grita falso é desligado.

   A régua é estreita de propósito: só conta helper EXECUTADO (`bash
   scripts/x.sh`), nunca helper SOURCEADO. `scripts/dkms_lib.sh` é biblioteca
   compartilhada pelas três funções de DKMS e pelo `flush_initramfs_host`;
   aceitá-lo como prova de alcance perdoaria uma função de DKMS nova chamada de
   um lado só, que é exatamente o defeito que este arquivo existe para pegar.

3. O PREÂMBULO COMUM SERVE OS DOIS LADOS. Código de topo antes da cerca roda em
   todo formato. Hoje nenhuma `*_host` chega por ali, mas a régua já sabe
   disso — se não soubesse, gritaria falso na primeira função que alguém
   movesse para lá, que é justamente o conserto que este portão recomenda.

A RÉGUA ESTAVA CEGA A CINCO CHAMADAS VIVAS (medido em 13/08/2026,
P2-ABERTURAS-01). A lista de aberturas de `chamadas_diretas` tinha `then`,
`else` e `do` — os CORPOS do `if` e do `while` — e não tinha as palavras que
os abrem. No `install.sh` de hoje isso escondia:

  - `install.sh:593`   `elif ! _render_broker_units` (com continuação de linha,
    dentro de `install_broker_host`)
  - `install.sh:1052`, `:1266`, `:1902`, `:2138`  `if run_apt ...`

Nenhuma delas é `*_host`, então NENHUM veredito de hoje muda com a correção —
conferido comparando os três conjuntos de alcance antes e depois, e a única
diferença são esses dois nomes. Mas a direção do erro importa: aresta que falta
no grafo só tira alcance, então a cegueira só sabia produzir ACUSAÇÃO FALSA.
Bastava alguém escrever `if install_osk_host; then` — a forma idiomática de
usar o código de saída de uma função — para o portão cobrar uma dívida que não
existe. Portão que grita falso é portão que se desliga.

PROVA DE QUE MORDE (12/08/2026) — arrancada do `install.sh` a chamada
`install_broker_host` do lado NATIVE (linha 1944), trocada por um `true`.
Reprovou `test_toda_cura_de_host_alcanca_os_dois_lados`, com a mensagem
apontando "o lado NATIVE". Devolvida do original guardado fora da árvore, e a
rodada de controle voltou verde. A segunda mordida: arrancada
`install_osk_host` do lado dos FORMATOS (linha 1119) — reprovou o mesmo teste,
apontando "o lado dos FORMATOS". Devolvida também.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"

#: A linha que abre a cerca. Se ela mudar, a régua tem de saber — daí o teste da
#: âncora. Sem ele, uma reescrita do cabeçalho deixaria este arquivo passando
#: por vacuidade, que é o pior estado possível para um portão.
ABERTURA_DA_CERCA = 'if [[ "${FORMAT}" != "native" ]]; then'

#: Quantas funções `*_host` o arquivo tinha quando esta guarda nasceu. Trava de
#: encolhimento contra parser quebrado, não meta.
PISO_DE_FUNCOES = 7

#: Uma função `*_host` que, por decisão registrada, serve um lado só. Vazio em
#: 12/08/2026. Chave é o nome da função; valor é a razão, com data e com o
#: motivo de o outro lado não precisar dela.
SERVE_UM_LADO_SO: dict[str, str] = {}

_DEF_DE_UMA_LINHA = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{.*\}\s*$")
_DEF_QUE_ABRE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{\s*$")
#: Helper de `scripts/` EXECUTADO — a linha invoca um interpretador. `source` e
#: `.` ficam de fora de propósito: biblioteca não é promessa.
_HELPER_EXECUTADO = re.compile(
    r"(?:^|[;&|(]|\s)(?:sudo\s+(?:-n\s+)?)?(?:bash|sh|python3?)\s+"
    r'["\']?(?:\$\{ROOT_DIR\}/|\$ROOT_DIR/)?["\']?(scripts/[\w./-]+\.(?:sh|py))'
)


def linhas_do_install() -> list[str]:
    return INSTALL.read_text(encoding="utf-8").splitlines()


def corpos_e_topo() -> tuple[dict[str, list[str]], list[bool]]:
    """Separa o corpo de cada função do código de TOPO do `install.sh`.

    Devolve os corpos por nome e uma máscara paralela às linhas dizendo quais
    delas moram dentro de alguma função. O fim de um corpo é a primeira linha
    que é exatamente `}` na coluna zero — a convenção que o arquivo inteiro usa.
    """
    linhas = linhas_do_install()
    corpos: dict[str, list[str]] = {}
    dentro = [False] * len(linhas)
    i = 0
    while i < len(linhas):
        de_uma_linha = _DEF_DE_UMA_LINHA.match(linhas[i])
        if de_uma_linha:
            miolo = linhas[i].split("{", 1)[1].rsplit("}", 1)[0]
            corpos[de_uma_linha.group(1)] = [miolo]
            dentro[i] = True
            i += 1
            continue
        que_abre = _DEF_QUE_ABRE.match(linhas[i])
        if que_abre:
            fim = i + 1
            while fim < len(linhas) and linhas[fim] != "}":
                fim += 1
            corpos[que_abre.group(1)] = linhas[i + 1 : fim]
            for k in range(i, min(fim + 1, len(linhas))):
                dentro[k] = True
            i = fim + 1
            continue
        i += 1
    return corpos, dentro


def regioes() -> dict[str, list[str]]:
    """As três regiões de código de TOPO, cortadas pela cerca do `exit 0`."""
    linhas = linhas_do_install()
    _, dentro = corpos_e_topo()
    abertura = next(
        (k for k, linha in enumerate(linhas) if linha.startswith(ABERTURA_DA_CERCA)),
        -1,
    )
    if abertura < 0:
        return {}
    saida = next(
        (k for k in range(abertura, len(linhas)) if linhas[k].strip() == "exit 0"),
        -1,
    )
    fechamento = next(
        (k for k in range(max(saida, abertura), len(linhas)) if linhas[k] == "fi"),
        -1,
    )
    if saida < 0 or fechamento < 0:
        return {}

    def topo(inicio: int, fim: int) -> list[str]:
        return [linhas[k] for k in range(inicio, fim) if not dentro[k]]

    return {
        "preambulo": topo(0, abertura),
        "formatos": topo(abertura, saida + 1),
        "native": topo(fechamento + 1, len(linhas)),
    }


def sem_comentario(linhas: list[str]) -> str:
    """Junta as linhas descartando as que são só comentário.

    Comentário citando o nome de uma função satisfaria a busca e o portão
    viraria decoração — é a mesma armadilha do bloco do teclado na tela.
    """
    return "\n".join(linha for linha in linhas if not linha.strip().startswith("#"))


#: O que pode vir ANTES de uma chamada para que ela esteja em posição de
#: comando. A lista foi montada caso a caso e ficou incompleta, e isso tem
#: preço conhecido: uma abertura que falta faz a chamada VIVA parecer
#: inexistente, e o portão acusa de dívida quem está em dia.
#:
#: P2-ABERTURAS-01 (13/08/2026): entraram `if`, `elif`, `while`, `until` e o
#: `!` de negação. Sem eles a forma mais idiomática que o bash tem de usar o
#: código de saída de uma função — `if install_osk_host; then` — era invisível
#: para a régua, e `if ! install_osk_host; then` também. O `)` já estava ali,
#: pelo `case` que despacha o formato (`flatpak)  format_flatpak ;;`): sem ele
#: o fecho do lado dos formatos parava no `case`.
#:
#: Isto é o oposto de afrouxar: reconhecer MAIS aberturas só acrescenta
#: chamadas ao grafo de alcance, e o teste que consome o grafo cobra que a cura
#: chegue aos DOIS lados. Quem afrouxaria seria o contrário — deixar de
#: reconhecer.
_ABERTURA_DE_COMANDO = (
    r"(?:^|[;&|()]|\b(?:then|else|elif|do|if|while|until)\b|\{)"
    r"\s*(?:!\s*)*(?:sudo\s+(?:-n\s+)?)?"
)


def chamadas_diretas(linhas: list[str], conhecidas: set[str]) -> set[str]:
    """As funções conhecidas invocadas em POSIÇÃO DE COMANDO nestas linhas.

    Posição de comando, e não "o nome aparece": o nome citado dentro de uma
    string de aviso (`warn "rode install_udev_host"`) não instala coisa nenhuma.

    A busca é ANCORADA NA LINHA DA CHAMADA, uma linha por vez. O `\\s*` do
    padrão casa `\\n` também, então alargar a lista de aberturas alargaria junto
    o ALCANCE de cada uma: um `if` no fim de uma linha passaria a valer como
    abertura de um nome que aparece linhas abaixo. Casar linha a linha corta
    isso na raiz — e não muda veredito nenhum de hoje, porque o `^` do padrão
    já era por linha.
    """
    achadas = set()
    linhas_uteis = sem_comentario(linhas).split("\n")
    for nome in conhecidas:
        padrao = _ABERTURA_DE_COMANDO + re.escape(nome) + r"(?![\w.-])"
        if any(re.search(padrao, linha) for linha in linhas_uteis):
            achadas.add(nome)
    return achadas


def alcancadas_de(linhas: list[str], corpos: dict[str, list[str]]) -> set[str]:
    """Fecho transitivo das funções alcançáveis a partir destas linhas."""
    vistas: set[str] = set()
    pilha = list(chamadas_diretas(linhas, set(corpos)))
    while pilha:
        atual = pilha.pop()
        if atual in vistas:
            continue
        vistas.add(atual)
        pilha.extend(chamadas_diretas(corpos.get(atual, []), set(corpos)))
    return vistas


def helpers_executados(linhas: list[str]) -> set[str]:
    return set(_HELPER_EXECUTADO.findall(sem_comentario(linhas)))


def helpers_do_fecho(nomes: set[str], corpos: dict[str, list[str]]) -> set[str]:
    achados: set[str] = set()
    for nome in nomes:
        achados |= helpers_executados(corpos.get(nome, []))
    return achados


def curas_de_host() -> list[str]:
    """As funções `*_host` do `install.sh`, derivadas do arquivo."""
    corpos, _ = corpos_e_topo()
    return sorted(nome for nome in corpos if nome.endswith("_host"))


def test_a_ancora_da_cerca_continua_de_pe() -> None:
    """Sem esta trava, uma reescrita do `install.sh` desligaria tudo calada."""
    achadas = regioes()
    assert achadas, (
        f"não achei a cerca do install.sh (`{ABERTURA_DA_CERCA}`, o `exit 0` "
        "do ramo dos formatos e o `fi` que o fecha).\n"
        "Se a bifurcação MUDOU DE FORMA, conserte `ABERTURA_DA_CERCA` e "
        "`regioes()` neste arquivo — sem elas todos os testes daqui passam "
        "sem olhar nada."
    )
    assert all(achadas[regiao] for regiao in ("preambulo", "formatos", "native")), (
        f"alguma região da cerca saiu vazia: "
        f"{ {regiao: len(ls) for regiao, ls in achadas.items()} }"
    )


def test_a_lista_de_curas_de_host_nao_encolheu() -> None:
    """Trava contra parser quebrado: lista derivada vazia passa por vacuidade."""
    achadas = curas_de_host()
    assert len(achadas) >= PISO_DE_FUNCOES, (
        f"achei {len(achadas)} funções `*_host` no install.sh, piso "
        f"{PISO_DE_FUNCOES}: {achadas}\n"
        "Se uma cura de host FOI EMBORA de propósito, baixe o piso no mesmo "
        "commit. Se não foi, o leitor de funções deste arquivo quebrou — e um "
        "portão que lê zero funções aprova qualquer coisa."
    )


def test_toda_cura_de_host_alcanca_os_dois_lados() -> None:
    corpos, _ = corpos_e_topo()
    por_regiao = regioes()
    alcance = {
        regiao: alcancadas_de(linhas, corpos) for regiao, linhas in por_regiao.items()
    }
    helpers_por_regiao = {
        regiao: helpers_do_fecho(alcance[regiao], corpos) | helpers_executados(linhas)
        for regiao, linhas in por_regiao.items()
    }

    for cura in curas_de_host():
        if cura in SERVE_UM_LADO_SO:
            continue
        if cura in alcance["preambulo"]:
            # Preâmbulo comum: roda para todo formato, serve os dois lados.
            continue

        proprios = helpers_do_fecho({cura}, corpos)
        faltando = []
        for regiao, apelido in (
            ("formatos", "o lado dos FORMATOS (flatpak/appimage/deb, antes do `exit 0`)"),
            ("native", "o lado NATIVE (depois do `fi`)"),
        ):
            if cura in alcance[regiao]:
                continue
            # A promessa também vale servida pelos helpers que a função delega.
            if proprios and proprios <= helpers_por_regiao[regiao]:
                continue
            faltando.append(apelido)

        assert not faltando, (
            f"`{cura}` é cura de HOST e não chega a todos os formatos.\n"
            + "".join(f"  falta em {lado}\n" for lado in faltando)
            + f"  helpers que ela executa: {sorted(proprios) or 'nenhum'}\n"
            "FAÇA UMA das três:\n"
            f"  1. CHAME `{cura}` também do lado que falta — é o conserto do "
            "achado #7 da Onda S, do TECLADO-QUE-NAO-DIGITA-01 e do "
            "MIC-EM-TODO-FORMATO-01, todos o mesmo defeito;\n"
            "  2. MOVA a chamada para o preâmbulo comum, antes da cerca, se ela "
            "serve a todo formato de qualquer jeito — mas cuidado: chamada "
            "dentro de `format_flatpak`/`format_appimage` NÃO é preâmbulo, é o "
            "lado dos formatos;\n"
            "  3. DECLARE em `SERVE_UM_LADO_SO`, com data e com o motivo de o "
            "outro lado não precisar dela.\n"
            "Quem instala pelo .deb tem o mesmo aparelho que quem instala do "
            "fonte."
        )


def test_a_lista_de_lacunas_nao_envelhece_calada() -> None:
    """Sem isto, `SERVE_UM_LADO_SO` vira o lugar onde se esconde o que incomoda."""
    derivadas = curas_de_host()
    for chave, razao in SERVE_UM_LADO_SO.items():
        assert chave in derivadas, (
            f"{chave!r} está declarada como cura de um lado só e nem existe "
            "mais no install.sh — APAGUE a entrada."
        )
        assert len(razao) > 120, (
            f"a razão de {chave!r} não diz por que o outro lado dispensa a "
            f"cura: {razao!r}"
        )
        assert re.search(r"\d{2}/\d{2}/\d{4}", razao), (
            f"a lacuna {chave!r} não tem data. Sem data ninguém sabe se ela "
            "envelheceu — e uma lacuna sem idade vira paisagem."
        )


# ---------------------------------------------------------------------------
# P2-ABERTURAS-01 (13/08/2026) — a régua tem de enxergar `if minha_cura; then`
#
# `chamadas_diretas` é a lente por onde TODO o resto deste arquivo enxerga o
# `install.sh`: o fecho transitivo, o alcance de cada região e o veredito final
# saem dela. Uma abertura que falta na lista não deixa o portão frouxo — deixa
# o portão MENTIROSO na direção pior de todas, a de acusar de dívida quem está
# em dia, e portão que grita falso é portão que se desliga.
#
# Os testes abaixo exercitam a lente diretamente, com linhas plantadas. Não
# tocam o `install.sh` de verdade: mexer no arquivo que a suíte inteira lê para
# provar um detalhe da régua trocaria uma medição por um susto.
# ---------------------------------------------------------------------------

CURA_DE_MENTIRA = "install_exemplo_host"


def test_a_regua_enxerga_a_chamada_dentro_de_um_if() -> None:
    """`if minha_cura; then` é a forma idiomática, e era invisível.

    O bash usa o código de saída da função para decidir; escrever assim é o
    normal, não a exceção. Antes desta correção a lista de aberturas tinha
    `then`, `else` e `do` — os CORPOS do `if` e do `while` — e não tinha as
    palavras que os abrem.
    """
    linhas = [f"    if {CURA_DE_MENTIRA}; then", '        ok "instalado"', "    fi"]
    assert chamadas_diretas(linhas, {CURA_DE_MENTIRA}) == {CURA_DE_MENTIRA}


def test_a_regua_enxerga_a_chamada_negada_e_nos_lacos() -> None:
    """As outras quatro formas que faltavam: `if !`, `elif`, `while`, `until`."""
    for linha in (
        f"    if ! {CURA_DE_MENTIRA}; then",
        f"    elif {CURA_DE_MENTIRA}; then",
        f"    while {CURA_DE_MENTIRA}; do",
        f"    until {CURA_DE_MENTIRA}; do",
        f"    ! {CURA_DE_MENTIRA}",
        f"    if ! sudo {CURA_DE_MENTIRA}; then",
    ):
        assert chamadas_diretas([linha], {CURA_DE_MENTIRA}) == {CURA_DE_MENTIRA}, (
            f"a régua não enxergou a chamada em {linha!r} — a lista de "
            "aberturas de `_ABERTURA_DE_COMANDO` voltou a ficar incompleta."
        )


def test_a_regua_continua_cega_ao_nome_que_e_so_texto() -> None:
    """O outro lado: alargar a lista não pode virar "o nome aparece".

    Sem este teste, a correção acima seria indistinguível de aceitar qualquer
    citação — e aí bastaria um aviso mencionando a função para o portão dar
    a cura por servida. É a mesma armadilha do bloco do teclado na tela: um
    texto que EXPLICA a regra satisfazendo a regra.
    """
    for linha in (
        f'    warn "se falhar, rode {CURA_DE_MENTIRA} à mão"',
        f"    # se falhar, rode {CURA_DE_MENTIRA}",
        f'    echo "pulei o {CURA_DE_MENTIRA}"',
        f"    local doc={CURA_DE_MENTIRA}_doc",
    ):
        assert chamadas_diretas([linha], {CURA_DE_MENTIRA}) == set(), (
            f"a régua deu por chamada o que é só texto em {linha!r}."
        )


def test_a_regua_nao_inventa_chamada_onde_nao_ha() -> None:
    """Arrancada a chamada, a régua tem de dizer que não há. O caso de vacuidade."""
    linhas = ["    if true; then", '        ok "nada instalado"', "    fi"]
    assert chamadas_diretas(linhas, {CURA_DE_MENTIRA}) == set()


def test_a_abertura_nao_atravessa_a_quebra_de_linha() -> None:
    """A âncora por linha: um `if` lá em cima não abre um nome cá embaixo.

    O `\\s*` do padrão casa `\\n`, então sem a âncora as aberturas novas
    passariam a valer para linhas seguintes — que é justamente como uma
    correção vira afrouxamento sem ninguém perceber.
    """
    linhas = [
        '    warn "leia o manual e decida se",',
        f'          "{CURA_DE_MENTIRA} é o que você quer"',
    ]
    assert chamadas_diretas(linhas, {CURA_DE_MENTIRA}) == set()
