#!/usr/bin/env python3
"""O gancho pergunta pela RÉGUA quando o commit mexe na tela — REGUA-NO-GANCHO-01.

Pedido dela, 29/08/2026: *"temos que ter no nosso hook do novo dev algo que
induza a construção de validações via interface pra ver se tal problema foi
resolvido ou se tal coisa traz regressão."*

O verbo é **INDUZIR**, não bloquear — e é por isso que este arquivo, no grau em
que nasce, sai com `exit 0` em todos os caminhos. A escada está no fim deste
comentário.

O QUE ELE PERGUNTA, e por que essa é a pergunta certa
=====================================================

Uma pergunta só: **este commit mexe na tela e não traz régua nenhuma junto?**

Ela é respondível pelo ÍNDICE, em ~40 ms, sem montar GTK, sem abrir Chrome e
sem tocar aparelho — a mesma economia do `check_fotos_da_tela.py`, que é o
irmão mais velho deste arquivo.

E ela é a pergunta certa porque o defeito que ela persegue é de CONSTRUÇÃO, não
de execução. O caso medido de 29/08/2026: o `--prova-gesto` do piloto da
interface nova dava VERDE sobre seis gestos e **nunca clicava** o botão do
microfone nem o do som — dois botões mortos, aprovados por uma régua que não os
visitava. Não foi rodar a régua que achou o defeito; foi **AMPLIAR** a régua. O
commit que criou os dois botões devia ter trazido a linha de régua que os
cobre, e não trouxe. É esse commit que este arquivo aborda.

POR QUE ELE NÃO SE PRENDE À ÁRVORE `-dev`, e isso corrige o enunciado
=====================================================================

O pedido dela diz "o hook do **novo dev**", e a leitura natural seria: fale na
worktree `hefesto-dualsense4unix-dev` e cale na árvore dela. MEDIDO em
29/08/2026, essa leitura erra o alvo:

* o `src/hefesto_dualsense4unix/interface/controles_vivos.py` — o piloto que PROVA a ponte
  JS, o exemplo que o próprio pedido invoca — mora na árvore **dela**, não na
  `-dev`, e nem sequer está sob o git (`git ls-files --error-unmatch` recusa).
  Um gancho preso ao diretório `-dev` seria mudo justamente sobre o arquivo que
  motivou o pedido;
* e a árvore de uma leva é temporária por regra desta casa (`git worktree add`
  para integrar), enquanto `layout/` é permanente.

Então o discriminador é **o que o commit TOCA**, não em que árvore ele nasce. A
árvore só decide o TOM (ver `--diagnostico`), nunca o silêncio.

O BURACO QUE A MEDIÇÃO ABRIU NO CAMINHO, e ele é maior que este arquivo
=======================================================================

MEDIDO em 29/08/2026: **o gancho deste repositório nunca rodou em worktree
nenhuma.** Não é este gancho — é o gancho inteiro, com os quatro instrumentos
HTML, o contrato IPC, as citações `arquivo:linha` e o portão da foto.

A cadeia é: `core.hooksPath` global manda o git rodar só
`~/.config/git/hooks/pre-commit`, e esse global encadeia o gancho do repositório
por `LOCAL_HOOK="$REPO_ROOT/.git/hooks/pre-commit"`. Numa worktree ligada, o
`.git` é um **arquivo** (`gitdir: …/worktrees/<nome>`), não um diretório — logo
esse caminho não existe, `[ -x "$LOCAL_HOOK" ]` é falso, e a delegação não
acontece. Silenciosamente: nada avisa que o gancho não rodou.

O conserto é de UMA linha, e é decisão dela porque o arquivo é global e vale
para todo repositório dela — trocar `$REPO_ROOT/.git` por
`$(git rev-parse --path-format=absolute --git-common-dir)`, que devolve o mesmo
`.git` na árvore principal e o `.git` de origem na worktree. `--diagnostico`
imprime o estado desta árvore e o patch exato.

Enquanto isso não é decidido, este arquivo continua útil por dois caminhos que
não dependem de gancho: `python3 scripts/check_regua_de_tela.py` à mão, e o
`tests/unit/test_o_gancho_induz_a_regua_de_tela.py` na suíte.

A ESCADA, e o gatilho MEDIDO de cada degrau
===========================================

A razão de começar avisando está escrita nesta casa, no portão de colisão de
sprints: *"um portão que reprova as vinte e três de uma vez é um portão que
alguém desliga na segunda-feira, e a primeira reação seria `--no-verify`"*.

* **Grau 1 — AVISA** (o de hoje). Nomeia as abas que o commit tocou, lista as
  réguas que existem para elas, e devolve 0. Nunca segura um commit.
* **Grau 2 — LISTA O QUE FALTA**. Além de avisar, imprime o comando pronto de
  cada régua que cobre a aba tocada. *Gatilho:* toda aba do mockup tem ao menos
  uma régua que a nomeia — `--censo --abas` responde isso com um número. Antes
  disso, o grau 2 mandaria rodar régua que não existe.
* **Grau 3 — REPROVA**. *Gatilho:* `--censo` mostrar que, nos últimos 50
  commits, a maioria dos que tocam a tela **já traz régua**. Um portão que
  reprova a maioria dos commits é um portão que morre na segunda-feira; um que
  reprova a minoria é um que segura a exceção. O número que autoriza a subida
  sai do próprio `--censo`, não de uma data.

O grau mora na constante `GRAU`, logo abaixo: subir de degrau é um commit, com
o número do `--censo` na mensagem.

COMO ELE NÃO VIRA RUÍDO
=======================

Aviso que sai em todo commit deixa de ser lido em uma semana. Quatro coisas o
calam:

1. **Commit que não toca a tela** — a maioria. Cala inteiro.
2. **Commit que traz régua** — cala, e o `--verboso` diz a quem creditou (um
   crédito errado tem de ser visível, não silencioso).
3. **Commit só de prosa** — `.md` dentro de `layout/` não é desenho.
4. **Dívida repetida** — se o `HEAD` já levou o mesmo aviso pelas mesmas abas,
   sai UMA linha em vez do bloco. O bloco ensina; a repetição do bloco ensina a
   pular o bloco.

O QUE ELE **NÃO** MEDE — e a lista importa tanto quanto o que ele mede
======================================================================

* **Não prova que a régua RODOU.** Ele lê o índice, não um recibo. Um commit
  que edita uma régua sem rodá-la satisfaz este arquivo. É deliberado: o que
  ela pediu foi induzir a CONSTRUÇÃO, e um recibo obrigatório poria Chrome e
  Playwright dentro do `pre-commit` — que é como se ensina alguém a desligar
  gancho.
* **Não prova que a régua MORDE.** Régua desta casa já nasceu falsa duas vezes
  (as duas cicatrizes do `src/hefesto_dualsense4unix/interface/LEIA-ME.md`), e o remédio
  contra isso é a mordida da própria régua (`regua_popup.py --morde`), não este
  arquivo.
* **Não sabe se a régua cobre a MUDANÇA.** Ele vê que uma régua foi tocada, não
  que ela passou a visitar o botão novo. Era exatamente o defeito do
  `--prova-gesto`, e nenhum portão de índice o alcança.
* **Não vê `rebase`, `cherry-pick`, `merge` nem `--no-verify`**, onde o git
  pula ou não chama o `pre-commit`.
* **Não roda em worktree nenhuma hoje**, pelo motivo medido acima.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

#: O degrau em que este portão está. Ver "A ESCADA" no topo: subir é um commit,
#: e a mensagem dele carrega o número do `--censo` que autorizou a subida.
GRAU = 1

#: O que, mudando, é MEXER NA TELA.
#:
#: `novo-layout` é a interface nova (o mockup que virou produto dentro do
#: `WebKit2.WebView`); os outros três são a mesma lista `CODIGO_DA_TELA` do
#: `check_fotos_da_tela.py`, que é a interface GTK de hoje. As duas convivem
#: enquanto a migração corre, e as duas precisam de régua.
TELA = (
    "layout",
    "src/hefesto_dualsense4unix/app",
    "src/hefesto_dualsense4unix/gui",
    "scripts/gui-captura",
)

#: Dentro de `novo-layout`, o que NÃO é desenho: saída de ferramenta, não fonte.
NAO_E_DESENHO = (
    "layout/screenshots",
    "layout/uploads",
)

#: Como se reconhece uma RÉGUA DE TELA pelo nome. São PREFIXOS, e prefixo é
#: convenção — a desta pasta, escrita no `src/hefesto_dualsense4unix/interface/LEIA-ME.md`
#: ("conferidos por `regua.py`"). Não é inventário de arquivos, que apodreceria
#: no dia em que nascesse a próxima régua.
#:
#: A trava contra o apodrecimento é o
#: `test_a_convencao_de_nome_alcanca_as_reguas_do_disco`: ele varre as duas
#: pastas e reprova se existir régua que esta convenção não reconhece.
PREFIXOS_DE_REGUA = ("regua", "conferir", "olhar", "medir")

#: Onde uma régua de tela pode morar.
#:
#: `scripts/` entrou aqui em 29/08/2026 e não por simetria: o
#: `scripts/regua_de_tela.py` — a régua que dirige o `WebView` por dentro —
#: nasceu ali de propósito, porque `layout/` é `.gitignore:108` e um
#: instrumento permanente tem de ser versionado para viajar em worktree.
#:
#: **Sem esta linha o portão nasceria falso**, e do pior jeito possível: ele
#: cobraria régua exatamente de quem tivesse acabado de escrever uma. MEDIDO
#: na árvore de 29/08, com o arquivo já no disco.
#:
#: O próprio `check_regua_de_tela.py` NÃO é régua, e o prefixo `check` diz
#: isso: ele PERGUNTA pela medição, não mede.
PASTAS_DE_REGUA = ("src/hefesto_dualsense4unix/interface", "scripts")

#: A ponte JS — o piloto que dirige o `WebView` por dentro (`--prova-gesto`).
#: Nomeado à parte porque não segue a convenção de prefixo, e é a régua mais
#: importante da interface nova: é a única que exercita o MOTOR que ela vai
#: usar, com o daemon vivo.
A_PONTE_JS = "src/hefesto_dualsense4unix/interface/controles_vivos.py"

#: A pasta das ferramentas do mockup.
FERRAMENTAS = "src/hefesto_dualsense4unix/interface"

#: O INSTRUMENTO versionado: a biblioteca com que se escreve régua nova sobre a
#: interface que roda num `WebView`. Nomeado à parte da lista porque ele não é
#: um par das outras — as de `src/hefesto_dualsense4unix/interface/` são scripts que se
#: rodam à mão sobre o mockup no Chrome; esta se IMPORTA de dentro de um
#: `tests/unit/test_*.py` e dirige o motor do produto.
O_INSTRUMENTO = "scripts/regua_de_tela.py"

#: O manual — o vocabulário, os dois instrumentos e os sete defeitos de tela
#: que esta casa já pagou, cada um virando um caso de régua.
#:
#: Ele é citado aqui, e não só no documento, porque quem lê este aviso é
#: exatamente quem ainda não sabe por onde começar: uma lista de sete arquivos
#: sem porta de entrada é um enigma, não uma indução. O
#: `test_a_regua_e_o_gancho_se_conhecem.py` reprova se o caminho apodrecer.
O_MANUAL = "docs/process/2026-08-29-A-REGUA-DE-TELA-como-se-prova-a-interface.md"

#: O `git` responde por esta árvore vazia quando ainda não há `HEAD`.
ARVORE_VAZIA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

#: O código de saída de um VEREDITO — "o grau 3 reprovou este commit".
#:
#: Não é `1`, e a razão é o pior desfecho possível deste arquivo: um gancho
#: quebrado impede ELA de commitar na árvore que usa todo dia. `1` é o que o
#: Python devolve para traceback, `python3` ausente, import quebrado — acidente
#: do INSTRUMENTO. O gancho só propaga o `2`, então acidente de instrumento
#: nunca segura um commit dela, e veredito sempre segura.
#:
#: MEDIDO em 29/08/2026, na bancada deste arquivo: com `1` e o `|| true` que o
#: gancho precisa ter, o grau 3 saía INERTE — reprovava no script e passava no
#: gancho. Os dois números têm de ser diferentes para os dois quererem coisas
#: opostas ao mesmo tempo.
VEREDITO_REPROVA = 2

EM_BRANCO = "em-branco"
"""O commit não toca a tela. Nada a dizer, e é o caso da maioria."""

COM_REGUA = "com-regua"
"""Toca a tela e traz régua junto. O caminho bom; cala."""

SO_REGUA = "so-regua"
"""Só mexe em régua. É trabalho de régua, e ele não se cobra a si mesmo."""

SEM_REGUA = "sem-regua"
"""Toca a tela e não traz régua nenhuma. É aqui que ele fala."""

SEM_REGUA_DE_NOVO = "sem-regua-de-novo"
"""O mesmo, e o `HEAD` já levou o aviso pelas mesmas abas. Sai UMA linha."""


# --------------------------------------------------------------- o julgamento


def e_regua(caminho: str) -> bool:
    """Este caminho é uma RÉGUA DE TELA?

    Três formas, e as três são convenção desta casa — nenhuma é inventário:

    * um arquivo de `src/hefesto_dualsense4unix/interface/` cujo nome começa por um dos
      `PREFIXOS_DE_REGUA`;
    * a ponte JS, nomeada à parte porque não segue a convenção;
    * um `tests/unit/test_*.py` — construir validação aqui muitas vezes é
      escrever pytest, e recusar esse crédito seria cobrar régua de quem
      acabou de escrever uma.
    """
    if caminho == A_PONTE_JS:
        return True
    p = PurePosixPath(caminho)
    if p.match("tests/unit/test_*.py"):
        return True
    if str(p.parent) not in PASTAS_DE_REGUA:
        return False
    return any(p.name.startswith(pref) for pref in PREFIXOS_DE_REGUA)


def e_tela(caminho: str) -> bool:
    """Este caminho é DESENHO — o que, mudando, pede régua?

    Prosa não é: um `.md` dentro de `layout/` documenta a tela, não a
    muda. Saída de ferramenta também não (`screenshots/`, `uploads/`).
    """
    if caminho.endswith(".md"):
        return False
    if any(_sob(caminho, p) for p in NAO_E_DESENHO):
        return False
    return any(_sob(caminho, p) for p in TELA)


def _sob(caminho: str, prefixo: str) -> bool:
    return caminho == prefixo or caminho.startswith(prefixo + "/")


def aba_de(caminho: str) -> str | None:
    """O número da aba que este caminho mexe, ou `None`.

    Sai do PRÓPRIO nome do arquivo — `src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html` e
    `src/hefesto_dualsense4unix/interface/aba06.py` são os dois a aba `06`. Não há tabela
    de abas aqui, e é de propósito: tabela apodrece, nome de arquivo não.
    """
    p = PurePosixPath(caminho)
    if p.parent == PurePosixPath("layout") and p.suffix == ".html":
        cabeca = p.name[:2]
        return cabeca if cabeca.isdigit() else None
    if str(p.parent) == FERRAMENTAS and p.name.startswith("aba"):
        cabeca = p.stem[3:5]
        return cabeca if cabeca.isdigit() else None
    return None


def julgar(
    no_indice: Iterable[str],
    abas_ja_devendo: Iterable[str] = (),
) -> tuple[str, list[str], list[str], list[str]]:
    """O veredito, sem git nenhum: só caminhos.

    `abas_ja_devendo` são as abas pelas quais o `HEAD` já levou este aviso —
    é o que troca o bloco pela linha única, e o que impede o aviso de virar
    papel de parede.

    Devolve `(veredito, desenho, reguas, abas)`: o que motivou, o que creditou,
    e as abas envolvidas. A mensagem precisa dos três para ser acionável — um
    aviso que não nomeia o arquivo é um aviso que ninguém sabe atender.
    """
    caminhos = list(no_indice)
    reguas = sorted(c for c in caminhos if e_regua(c))
    desenho = sorted(c for c in caminhos if not e_regua(c) and e_tela(c))
    abas = sorted({a for c in desenho if (a := aba_de(c))})

    if not desenho:
        return (SO_REGUA if reguas else EM_BRANCO), [], reguas, []
    if reguas:
        return COM_REGUA, desenho, reguas, abas

    ja = set(abas_ja_devendo)
    if abas and set(abas) <= ja:
        return SEM_REGUA_DE_NOVO, desenho, [], abas
    return SEM_REGUA, desenho, [], abas


# ------------------------------------------------------------------- o git


def _git(raiz: Path, *args: str) -> str:
    saida = subprocess.run(["git", *args], cwd=str(raiz), capture_output=True, text=True)
    return saida.stdout.strip() if saida.returncode == 0 else ""


def caminhos_no_indice(raiz: Path) -> list[str]:
    """O que este commit vai carregar. Sem `HEAD`, compara com a árvore vazia."""
    contra = "HEAD" if _git(raiz, "rev-parse", "--verify", "HEAD") else ARVORE_VAZIA
    return [ln for ln in _git(raiz, "diff", "--cached", "--name-only", contra).splitlines() if ln]


def caminhos_do_commit(raiz: Path, sha: str) -> list[str]:
    """O que um commit já feito carregou. Vazio para merge, que não tem gancho."""
    if len(_git(raiz, "rev-list", "--parents", "-n", "1", sha).split()) > 2:
        return []
    return [ln for ln in _git(raiz, "show", "--name-only", "--format=", sha).splitlines() if ln]


def abas_devidas_pelo_head(raiz: Path) -> list[str]:
    """Pelas quais abas o `HEAD` já levou este aviso? É o que cala a repetição."""
    veredito, _, _, abas = julgar(caminhos_do_commit(raiz, "HEAD"))
    return abas if veredito in (SEM_REGUA, SEM_REGUA_DE_NOVO) else []


def reguas_no_disco(raiz: Path) -> list[str]:
    """As réguas que EXISTEM, descobertas por varredura — nunca por lista.

    É o que impede a mensagem de mandar rodar régua que não existe, e o que faz
    régua nova aparecer no aviso sem ninguém a cadastrar aqui.
    """
    achadas: list[str] = []
    for nome_da_pasta in PASTAS_DE_REGUA:
        pasta = raiz / nome_da_pasta
        if not pasta.is_dir():
            continue
        achadas += [
            f"{nome_da_pasta}/{f.name}"
            for f in sorted(pasta.iterdir())
            if f.is_file()
            and f.suffix == ".py"
            and any(f.name.startswith(p) for p in PREFIXOS_DE_REGUA)
        ]
    if (raiz / A_PONTE_JS).is_file():
        achadas.append(A_PONTE_JS)
    return achadas


def na_arvore_principal(raiz: Path) -> bool:
    """Árvore principal ou worktree ligada?

    Em worktree ligada o `--git-dir` aponta para `.git/worktrees/<nome>` e o
    `--git-common-dir` para o `.git` de origem. Mesma pergunta do
    `check_fotos_da_tela.py:167` — usada aqui só para o TOM do
    `--diagnostico`, nunca para decidir se fala.
    """
    proprio = _git(raiz, "rev-parse", "--absolute-git-dir")
    comum = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not proprio or not comum:
        return True
    return Path(proprio).resolve() == Path(comum).resolve()


# ------------------------------------------------------------------ a fala


def _bloco(raiz: Path, desenho: list[str], abas: list[str]) -> str:
    quais = ", ".join(abas) if abas else "—"
    linhas = [
        "",
        "régua de tela: este commit MEXE NA TELA e não traz régua nenhuma.",
        "",
    ]
    for c in desenho[:8]:
        linhas.append(f"    {c}")
    if len(desenho) > 8:
        linhas.append(f"    ... e mais {len(desenho) - 8}")
    linhas += [
        "",
        f"  Abas tocadas: {quais}",
        "",
        "  A pergunta, e ela é dela (29/08/2026): existe validação que prove que",
        "  isto ficou de pé — e que avise se amanhã alguém o desfizer?",
        "",
        "  A interface nova roda num `WebKit2.WebView`, então ela é DIRIGÍVEL por",
        "  dentro: `run_javascript` clica com `el.click()` (o mesmo caminho de",
        "  eventos de um clique real), lê o DOM e mede geometria; o",
        "  `register_script_message_handler` traz a resposta ao Python. Validar",
        "  comportamento é clicar e conferir, não fotografar.",
        "",
    ]
    if (raiz / O_MANUAL).is_file():
        linhas += [
            "  POR ONDE COMEÇAR — o vocabulário, os dois instrumentos e os sete",
            "  defeitos de tela que esta casa já pagou, cada um virando um caso:",
            f"    {O_MANUAL}",
            "",
        ]
    disco = reguas_no_disco(raiz)
    biblioteca = [r for r in disco if r == O_INSTRUMENTO]
    do_mockup = [r for r in disco if r != O_INSTRUMENTO]
    if biblioteca:
        linhas.append(
            "  A BIBLIOTECA — importe-a de um `tests/unit/test_*.py` e dirija o"
        )
        linhas.append("  motor que ela vai usar (`Tela.abrir`, `clicar_e_ouvir`):")
        linhas += [f"    {r}" for r in biblioteca]
        linhas.append("")
    if do_mockup:
        linhas.append(
            "  AS RÉGUAS DO MOCKUP — Playwright/Chrome sobre o desenho, para"
        )
        linhas.append("  layout e `:hover`. Não alcançam o WebView do produto:")
        linhas += [f"    {r}" for r in do_mockup]
    if not disco:
        linhas.append("  Não achei régua nenhuma em `src/hefesto_dualsense4unix/interface/`.")
    linhas += [
        "",
        "  E ela precisa MORDER: régua desta casa já nasceu falsa duas vezes (as",
        "  cicatrizes do `src/hefesto_dualsense4unix/interface/LEIA-ME.md`), e em 29/08 o",
        "  `--prova-gesto` deu VERDE sobre dois botões que nunca clicava. Arranque",
        "  a cura, veja a régua reprovar, devolva.",
        "",
        "  Este aviso NÃO segura o commit (grau 1). Ele volta calado no próximo",
        "  commit que trouxer régua.",
        "",
    ]
    return "\n".join(linhas)


def _o_ponto_cego(raiz: Path) -> None:
    """O que gancho NENHUM pode ver — e por que calar sobre isso seria mentir.

    MEDIDO em 29/08/2026: `layout/` é `.gitignore:108`. O `git` conhece
    ZERO arquivo lá dentro e ZERO commit de toda a história tocou a pasta. Logo
    o mockup, os dez geradores `abaNN.py`, as réguas do Playwright e o piloto
    da ponte JS **nunca aparecem num índice** — e um portão de `pre-commit`
    julga o índice.

    Isso não é defeito deste arquivo: nenhum gancho pode perguntar por uma
    mudança que o git não vê. Mas anunciar "o gancho cobre a interface nova"
    com esta pasta fora seria o instrumento falso que esta casa já pegou seis
    vezes em quinze horas. Então ele DIZ.

    O que sobra coberto, e é real: o lado versionado — `src/…/app`, `src/…/gui`,
    `scripts/gui-captura` e a régua `scripts/regua_de_tela.py`. Foi por essa
    razão que ela nasceu em `scripts/` e não em `layout/`.
    """
    ignorada = (
        subprocess.run(
            ["git", "check-ignore", "-q", "layout"],
            cwd=str(raiz),
            capture_output=True,
        ).returncode
        == 0
    )
    if not ignorada:
        return
    conhecidos = len([x for x in _git(raiz, "ls-files", "layout").splitlines() if x])
    if conhecidos:
        return
    print("PONTO CEGO, e ele é maior que este portão:")
    print("  `layout/` é `.gitignore:108` — o git conhece 0 arquivo lá e")
    print("  0 commit da história tocou a pasta. O mockup, os geradores `abaNN.py`,")
    print("  as réguas do Playwright e o piloto da ponte JS NUNCA entram num")
    print("  índice, e um `pre-commit` só julga o índice.")
    print()
    print("  Então este portão cobre o lado VERSIONADO da tela — `src/…/app`,")
    print("  `src/…/gui`, `scripts/gui-captura` — e credita a régua versionada")
    print("  `scripts/regua_de_tela.py`. Sobre o mockup ele é mudo, e nenhum")
    print("  gancho pode deixar de ser.")
    print()
    print("  A saída, se ela quiser cobertura ali, é DELA e é de versionamento,")
    print("  não de gancho: tirar `layout/` do `.gitignore`, ou mover para")
    print("  `scripts/` o que for instrumento permanente — que foi exatamente o")
    print("  argumento com que `scripts/regua_de_tela.py` nasceu fora da pasta.")
    print()


def _diagnostico(raiz: Path) -> int:
    """O gancho deste repositório RODA nesta árvore? A resposta costuma ser não."""
    principal = na_arvore_principal(raiz)
    comum = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    local = raiz / ".git" / "hooks" / "pre-commit"
    encadeado = local.is_file() and __import__("os").access(local, __import__("os").X_OK)

    print(f"árvore .......... {raiz}")
    print(f"tipo ............ {'principal' if principal else 'worktree ligada'}")
    print(f"git-common-dir .. {comum}")
    print(f"o global procura  {local}")
    print(f"e acha? ......... {'SIM' if encadeado else 'NÃO'}")
    print()
    _o_ponto_cego(raiz)
    if encadeado:
        print("O gancho do repositório RODA nesta árvore.")
        return 0
    print("O gancho do repositório NÃO RODA nesta árvore, e nada avisa disso.")
    print()
    print("  Numa worktree ligada o `.git` é um ARQUIVO (`gitdir: …`), então o")
    print("  caminho que o gancho global testa não pode existir. Cai fora TODO o")
    print("  gancho deste repositório: os quatro instrumentos HTML, o contrato")
    print("  IPC, as citações `arquivo:linha` e o portão da foto.")
    print()
    print("  O conserto é de UMA linha, e é DELA: o arquivo é global e vale para")
    print("  todo repositório dela. Em ~/.config/git/hooks/pre-commit:")
    print()
    print('    -LOCAL_HOOK="$REPO_ROOT/.git/hooks/pre-commit"')
    print('    +LOCAL_HOOK="$(git rev-parse --path-format=absolute'
          ' --git-common-dir)/hooks/pre-commit"')
    print()
    print("  Na árvore principal os dois dão o MESMO caminho — medido — então a")
    print("  troca não muda nada do que já funciona.")
    return 0


def _censo(raiz: Path, quantos: int = 50) -> int:
    """O número que autoriza subir de degrau. Ver "A ESCADA" no topo."""
    shas = [s for s in _git(raiz, "log", "--format=%H", f"-{quantos}").splitlines() if s]
    tocam = com = 0
    for sha in shas:
        veredito, _, _, _ = julgar(caminhos_do_commit(raiz, sha))
        if veredito == COM_REGUA:
            tocam += 1
            com += 1
        elif veredito in (SEM_REGUA, SEM_REGUA_DE_NOVO):
            tocam += 1
    print(f"últimos {len(shas)} commits (merges não contam: o git não lhes roda `pre-commit`)")
    print(f"  tocam a tela .......... {tocam}")
    print(f"  destes, com régua ..... {com}")
    if tocam:
        print(f"  proporção ............. {100 * com // tocam}%")
        print()
        print(f"  Grau atual: {GRAU}. O grau 3 (reprovar) pede que a MAIORIA já")
        print("  traga régua — reprovar a maioria é o portão que morre na segunda.")
    else:
        print("  nenhum commit da janela tocou a tela; sem número para decidir.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    raiz_texto = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if not raiz_texto:
        return 0  # fora de repositório não há índice para julgar
    raiz = Path(raiz_texto)

    if "--diagnostico" in args:
        return _diagnostico(raiz)
    if "--censo" in args:
        return _censo(raiz)

    verboso = "--verboso" in args
    veredito, desenho, reguas, abas = julgar(
        caminhos_no_indice(raiz), abas_devidas_pelo_head(raiz)
    )

    if veredito in (EM_BRANCO, SO_REGUA):
        return 0

    if veredito == COM_REGUA:
        if verboso:
            print(
                "régua de tela: o commit mexe na tela e traz régua — "
                + ", ".join(reguas[:3]),
                file=sys.stderr,
            )
        return 0

    if veredito == SEM_REGUA_DE_NOVO:
        print(
            "régua de tela: as abas "
            + ", ".join(abas)
            + " seguem sem régua (o aviso inteiro saiu no commit anterior).",
            file=sys.stderr,
        )
        return 0

    print(_bloco(raiz, desenho, abas), file=sys.stderr)
    return VEREDITO_REPROVA if GRAU >= 3 else 0


if __name__ == "__main__":
    raise SystemExit(main())
