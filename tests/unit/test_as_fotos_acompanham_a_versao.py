"""As fotos da documentação defasaram em silêncio — FOTOS-DA-VERSAO-01.

O `CLAUDE.md` manda, com todas as letras: *"Antes de gerar release, rode de
novo: as imagens acompanham a versão"*. Não havia portão nenhum segurando isso,
e o resultado, medido em 13/08/2026 sobre a tag `v0.9.4.2`:

* último commit que tocou `docs/usage/assets/`: `0c4164e`, 12/08 00:38:35;
* commits que tocaram `app/` ou `gui/` DEPOIS dele: `f1279a1` (12/08 00:49),
  `0b010bd` (13/08 00:41) e `973c92c` (13/08 02:00);
* e a tag saiu às 02:26.

Ou seja: a release foi publicada com fotos anteriores a três levas de
interface. Ninguém percebeu porque nada mede isto — o script grava dez PNGs e
não reclama de nada.

O QUE ESTE TESTE **NÃO** AFIRMA
-------------------------------

Ele não diz que a foto está errada — diz que ela não foi **conferida** depois da
última mexida na interface. É medida de PROCEDÊNCIA, não de conteúdo: as duas
coisas se separam, e a diferença foi medida no mesmo dia. Regeradas com o
código de `cc768d4`, NOVE das dez imagens saíram **byte a byte idênticas** às
commitadas — os três commits acima não mudaram um pixel de aba nenhuma. A
defasagem era real e o dano, nenhum. Mas isso só se sabe **depois** de rodar o
script, que é exatamente o gesto que este teste cobra.

Comparar o conteúdo em vez da procedência não serve como portão, e a razão
original está corrigida abaixo — mas a conclusão não mudou. O que um portão de
bytes mediria é o RENDER (fonte, tema, versão do GTK da máquina de quem rodar),
e não a pergunta que este arquivo faz, que é *"alguém conferiu depois da última
mexida na interface?"*.

**O número e a causa que estavam aqui eram errados, e foram medidos em
14/08/2026** (fato errado se substitui): dizia-se que a `readme_inicio.png` saía
com ~45 mil pixels diferentes entre duas execuções seguidas por *"ruído de
gradiente nos botões segmentados"*. A diferença real entre duas execuções eram
**~3 mil pixels, delta 1 a 2**, e a causa não é gradiente: é a **transição de
CSS** do estado `:checked` dos dois botões segmentados selecionados, que a foto
pegava no meio — em que ponto dela dependia do relógio. Os ~45 mil pixels são a
distância entre a foto no meio da animação e a foto ASSENTADA, que é a que o
script passou a produzir.

Desde `retratar_abas.py` desligar as animações do GTK
(`gtk-enable-animations = False`), duas execuções seguidas saem **byte a byte
idênticas** nas dez abas. O portão continua sendo de procedência mesmo assim,
pelo motivo do parágrafo acima.

O ESTADO SEM SAÍDA, e a segunda porta — 03/09/2026
---------------------------------------------------

O portão pede um COMMIT em `docs/usage/assets/` como prova de um GESTO ("alguém
rodou o retratista"). Quando o gesto não produz bytes, não há o que commitar, e
o portão fica vermelho **para sempre**: é a régua confundindo a PALAVRA com o
ATO, que é o defeito mais caro desta casa.

Ele apareceu com o commit `2899ef0d` (03/09, "as celulas mudas caem de 148 para
47"), cujo único arquivo sob `app/` é `fatos_do_mapa.py` — a tabela de fatos do
mapa, que a aba Emulação e a seção Controles LEEM. Suspeito com razão, então.
Medido, e este é o número que decide:

* retratista rodado com o `fatos_do_mapa.py` ANTES e DEPOIS de `2899ef0d`,
  mesma máquina, mesma mesa, um minuto de intervalo: **as 14 fotos byte a byte
  IDÊNTICAS**. O commit acusado moveu ZERO pixel.

E "refotografar e commitar assim mesmo" não é saída inocente — é a segunda coisa
medida no mesmo dia: **a foto carrega estado VIVO da máquina de quem a tira**.
Comparadas com as commitadas, 10 das 14 saíram byte a byte idênticas (o render é
reprodutível) e as 4 restantes diferiam só onde o aparelho fala — a linha
"Controles detectados" (2 controles físicos na mesa dela, 1 na minha) e a cor do
plástico LIDA de cada controle. Commitar a minha teria trocado a mesa dela pela
minha, calado, para satisfazer um portão.

Então o portão ganhou uma SEGUNDA PORTA, e ela não afrouxa a primeira: uma
declaração em `docs/usage/assets/CONFERIDO-EM.txt` nomeando o SHA do commit de
tela que foi conferido. Rodou e as imagens mudaram? Commite as imagens, como
sempre. Rodou e não mudou nada? Declare o commit. Qualquer outra mexida na tela
gera um SHA novo, a declaração fica velha sozinha e o portão reabre — que é
exatamente a propriedade que se quer.

A SEGUNDA FAMÍLIA DE FOTO, E O BURACO QUE ELA ABRIU — 11/09/2026
-----------------------------------------------------------------

`docs/usage/assets/maximizada/` nasceu na PRINTS-DAS-DEZ-01 (as dez abas na
vista maximizada dela) e **caía dentro de `docs/usage/assets` em toda pergunta
deste arquivo**, porque as três casavam por PREFIXO. Medido pelo conferente no
mesmo dia: um commit que gravasse só na pasta nova devolvia `em-dia`, e a
dívida das dez do README ficava paga por foto que não é delas.

A cura é medir POR FAMÍLIA — `familias_sob`, `_pathspec`, `uma_familia_em_dia`
— e ela alcança as TRÊS perguntas, não só a primeira: a topologia, o perdão de
`fotos_sendo_refeitas_agora`, e a mensagem, que agora nomeia a pasta devedora e
o comando daquela pasta. Uma família atrasada reprova por todas; uma família
que não dá para medir continua se calando.

A MORDIDA
---------

São cinco, e todas em repositório de mentira em `tmp_path`:

* `test_a_foto_da_vista_nao_paga_a_divida_das_dez_do_readme` — a mordida da
  família nova. Tire o `:(exclude)` de `_pathspec` e ela reprova.

* `test_o_portao_acusa_foto_atrasada` — a ordem errada tem de reprovar.
  Arrancando a comparação (fazendo-a devolver sempre "em dia"), reprova.
* `test_o_portao_acusa_retrato_mexido_depois_da_foto` — o INSTRUMENTO conta.
* `test_a_declaracao_so_vale_para_o_commit_que_ela_nomeia` — a segunda porta com
  o SHA de OUTRO commit não abre nada. É a mordida da porta nova: sem ela,
  bastaria criar o arquivo com qualquer conteúdo para calar o portão.
* `test_a_declaracao_fecha_o_portao_quando_a_foto_nao_muda` — e o outro lado,
  senão "recusar sempre" satisfaria a de cima.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: As fotos que o `interface/olhar.py --todas --publicado --doc` grava.
FOTOS = "docs/usage/assets"

#: A SEGUNDA FAMÍLIA DE FOTO, e o buraco que ela abriu — 11/09/2026.
#:
#: `docs/usage/assets/maximizada/` nasceu na PRINTS-DAS-DEZ-01 com as dez abas
#: na vista maximizada dela (`--vista dela`, 1918x840). As duas famílias
#: respondem perguntas diferentes — o recorte da `.janela` é a miniatura do
#: README, a vista é a TV dela — e moram em pastas separadas por isso.
#:
#: **O DEFEITO QUE A PASTA NOVA INTRODUZIU, medido pelo conferente no mesmo
#: dia:** este portão casava `docs/usage/assets` por PREFIXO, e a subpasta cai
#: dentro dele. `julgar(['src/.../aba01.py', 'docs/usage/assets/maximizada/
#: aba-01-jogar.png'])` devolvia `em-dia` — ou seja, **gravar só na pasta nova
#: QUITAVA a dívida das dez do README**, que podiam apodrecer caladas. É o
#: defeito que esta própria sprint ACHOU (as dez do README paradas em 08/09 sem
#: régua acusar), reaberto um nível acima e numa família ainda menos coberta.
#:
#: A cura é medir POR FAMÍLIA: cada uma responde por si, e foto de uma nunca
#: paga a dívida da outra. Ver `familias_sob` e `_pathspec`.
SUBPASTA_DA_VISTA = "maximizada"
FOTOS_DA_VISTA = f"{FOTOS}/{SUBPASTA_DA_VISTA}"

#: Toda família de foto desta casa, da mais externa para a mais interna. Quem
#: criar uma terceira pasta de foto acrescenta a linha AQUI e no irmão
#: `scripts/check_fotos_da_tela.py` — `test_as_duas_listas_de_codigo_de_tela_sao_a_mesma`
#: tranca as duas juntas.
FAMILIAS_DE_FOTO = (FOTOS, FOTOS_DA_VISTA)

#: O que, mudando, torna as fotos suspeitas. `interface/` é a tela de hoje —
#: as dez páginas e o retratista delas; `app/` é o motor que elas chamam;
#: `gui/` é o `theme.css`, de onde saem as cores da casa.
#:
#: Z0-1 (24/08/2026), §2.2/M1 da sprint Z0-01: até aquele dia o portão era CEGO
#: ao próprio programa que tira a foto — uma mudança de +645 linhas em
#: `retratar_abas.py` (o commit `3de95ff`, os cinco hosts) não tornava foto
#: nenhuma suspeita. Ver `test_o_portao_acusa_retrato_mexido_depois_da_foto`
#: para a mordida.
#:
#: `"scripts/gui-captura"` SAIU em 06/09/2026 (`GTK-3`): a pasta inteira era o
#: retratista da JANELA GTK, aposentada por decisão dela
#: (`D-0609-GTK-LEVA-INTEIRA`). **A regra do Z0-1 não caiu junto** — o
#: retratista de hoje é `interface/olhar.py --todas --publicado --doc`, e ele
#: mora DENTRO da primeira entrada. A mordida foi reapontada para ele.
CODIGO_DA_TELA = (
    # A INTERFACE NOVA ENTROU EM 05/09/2026, e a ausência dela estava medida:
    # mexer nas dez abas que o lançador abre não tornava foto nenhuma suspeita,
    # e mexer no motor VELHO obrigava a refotografar a janela velha — o portão
    # cobrava a foto errada e era cego à certa. O irmão que cobra RÉGUA de tela
    # (`scripts/check_regua_de_tela.py`) recebeu esta mesma linha em 03/09 com a
    # mesma razão; o da FOTO não tinha ido junto.
    #
    # Quem tira a foto das dez é `interface/olhar.py --todas --publicado --doc`,
    # e ele mora DENTRO desta pasta: mudar o retratista torna as fotos suspeitas
    # sem precisar de uma quinta entrada.
    "src/hefesto_dualsense4unix/interface",
    "src/hefesto_dualsense4unix/app",
    "src/hefesto_dualsense4unix/gui",
)

#: A DECLARAÇÃO DE CONFERÊNCIA — a segunda porta, 03/09/2026. Uma linha por
#: conferência, o primeiro campo é o SHA completo do commit de `CODIGO_DA_TELA`
#: contra o qual o retratista foi rodado; `#` começa comentário. Ela mora
#: DENTRO de `FOTOS` de propósito: quem a escreve mexe na pasta das fotos, e a
#: topologia da primeira porta enxerga o commit sem precisar saber que ela
#: existe. Ver a seção "O ESTADO SEM SAÍDA" no cabeçalho.
CONFERIDO = f"{FOTOS}/CONFERIDO-EM.txt"

#: UM COMANDO POR FAMÍLIA, e a segunda linha é a razão de esta constante
#: existir — 11/09/2026. Enquanto a mensagem citava só o primeiro comando, quem
#: apanhasse pela pasta da vista rodaria o retratista, veria a foto certa não
#: mudar, e concluiria que o portão estava quebrado. Portão que não diz o gesto
#: exato é portão que se aprende a ignorar.
RETRATISTA = "src/hefesto_dualsense4unix/interface/olhar.py"
COMANDOS_DE_CURA = (
    f"    {RETRATISTA} --todas --publicado --doc                 # {FOTOS}\n"
    f"    {RETRATISTA} --todas --publicado --doc --vista dela    # {FOTOS_DA_VISTA}"
)


def _git(raiz: Path, *args: str) -> str:
    saida = subprocess.run(
        ["git", *args],
        cwd=str(raiz),
        capture_output=True,
        text=True,
    )
    if saida.returncode != 0:
        return ""
    return saida.stdout.strip()


def _ultimo_commit(raiz: Path, *caminhos: str) -> str:
    return _git(raiz, "log", "-1", "--format=%H", "--", *caminhos)


def familias_sob(fotos: str) -> tuple[str, ...]:
    """As famílias de foto que moram em `fotos`, ela inclusive.

    `docs/usage/assets` devolve as duas; `docs/usage/assets/maximizada`
    devolve só ela mesma. É o que permite a este arquivo continuar sendo
    chamado com `FOTOS` e ainda assim perguntar por família.
    """
    return tuple(
        f for f in FAMILIAS_DE_FOTO if f == fotos or f.startswith(fotos + "/")
    )


def _pathspec(familia: str) -> list[str]:
    """Os caminhos que são DESTA família e de nenhuma outra.

    A pasta externa é ela MENOS as internas, e quem faz isso é o `:(exclude)`
    do git — não um filtro escrito à mão, que seria uma segunda régua a
    divergir. Sem esta exclusão, `git log -- docs/usage/assets` responde com o
    commit que tocou `docs/usage/assets/maximizada/`, e a dívida das dez do
    README fica quitada por foto que não é delas.
    """
    return [familia] + [
        f":(exclude){outra}"
        for outra in FAMILIAS_DE_FOTO
        if outra != familia and outra.startswith(familia + "/")
    ]


def uma_familia_em_dia(
    raiz: Path, familia: str, codigo: tuple[str, ...]
) -> bool | None:
    """A pergunta da topologia, para UMA família de foto.

    `True` = a foto veio depois; `False` = não; `None` = não dá para saber aqui
    (sem git, num clone raso, ou porque um dos dois lados nunca foi commitado).

    O critério é a TOPOLOGIA, não o relógio: `merge-base --is-ancestor` responde
    "o commit do código é ancestral do commit das fotos?". Data de commit
    mentiria — um `rebase` reescreve a ordem sem reescrever os carimbos, e dois
    commits podem carregar o mesmo segundo.
    """
    commit_das_fotos = _ultimo_commit(raiz, *_pathspec(familia))
    commit_do_codigo = _ultimo_commit(raiz, *codigo)
    if not commit_das_fotos or not commit_do_codigo:
        return None
    if commit_das_fotos == commit_do_codigo:
        # A mesma leva mexeu na tela e refotografou. É o caminho bom.
        return True
    pergunta = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_do_codigo, commit_das_fotos],
        cwd=str(raiz),
        capture_output=True,
    )
    return pergunta.returncode == 0


def fotos_em_dia(raiz: Path, fotos: str, codigo: tuple[str, ...]) -> bool | None:
    """TODAS as famílias sob `fotos` foram refeitas depois da mexida na tela?

    Uma família atrasada reprova por todas — é o ponto inteiro da cura de
    11/09/2026. Uma família que não dá para medir (`None`) se cala, e não
    arrasta o veredito: é a mesma prudência que o `None` sempre teve, agora
    aplicada uma vez por pasta.
    """
    vereditos = [uma_familia_em_dia(raiz, f, codigo) for f in familias_sob(fotos)]
    if any(v is False for v in vereditos):
        return False
    if all(v is None for v in vereditos):
        return None
    return True


def familias_atrasadas(
    raiz: Path, fotos: str, codigo: tuple[str, ...]
) -> list[str]:
    """Quais famílias estão devendo foto — o que a mensagem precisa nomear."""
    return [
        f
        for f in familias_sob(fotos)
        if uma_familia_em_dia(raiz, f, codigo) is False
    ]


def fotos_sendo_refeitas_agora(raiz: Path, fotos: str) -> bool:
    """As fotos estão MODIFICADAS na árvore de trabalho ou no índice?

    Refotografar é o conserto deste portão, e o conserto acontece **antes** do
    commit. Enquanto as imagens estiverem sujas, a cura está em curso e a
    topologia ainda não pode enxergá-la — o commit que as carrega não existe.

    Medido em 13/08/2026: a leva que refez as fotos deixava
    `test_as_fotos_nao_ficam_atras_do_codigo_da_tela` vermelho até o instante do
    commit, ou seja, a suíte reprovava **por causa da própria cura**. O
    `--porcelain` responde por CONTEÚDO, não por relógio, então tocar o mtime de
    um PNG não engana esta pergunta.

    Isto não afrouxa a regra: mexer só no código da tela e **não** refotografar
    continua reprovando, porque aqui só a sujeira das FOTOS conta. E a mordida
    do portão não passa por aqui — `test_o_portao_acusa_foto_atrasada` chama
    `fotos_em_dia` direto, num repositório de mentira.

    **O PERDÃO TAMBÉM É POR FAMÍLIA desde 11/09/2026** (ver `familias_sujas`):
    imagem suja em `maximizada/` não podia continuar perdoando a dívida das dez
    do README, que é o buraco que a pasta nova abriu em toda pergunta que
    casava por prefixo.
    """
    return bool(_git(raiz, "status", "--porcelain", "--", *_pathspec(fotos)))


def familias_sujas(raiz: Path, fotos: str) -> set[str]:
    """As famílias que estão sendo refeitas AGORA — o perdão, uma pasta por vez.

    Perdoar em bloco é o mesmo defeito de casar por prefixo: quem refaz só a
    foto da vista teria a dívida das dez do README perdoada junto, sem ter
    tirado nenhuma delas.
    """
    return {f for f in familias_sob(fotos) if fotos_sendo_refeitas_agora(raiz, f)}


def conferencia_declarada(raiz: Path, conferido: str) -> set[str]:
    """Os commits de tela que alguém declarou ter conferido, lidos do arquivo.

    Devolve o conjunto de SHAs completos. Linha em branco e linha que só tem
    comentário não contam; um campo que não seja SHA de 40 hexadecimais é
    ignorado, de modo que prosa no arquivo não vira declaração por acidente.
    """
    try:
        texto = (raiz / conferido).read_text(encoding="utf-8")
    except OSError:
        return set()

    achados: set[str] = set()
    for linha in texto.splitlines():
        campos = linha.split("#", 1)[0].split()
        if not campos:
            continue
        primeiro = campos[0].lower()
        if len(primeiro) == 40 and all(c in "0123456789abcdef" for c in primeiro):
            achados.add(primeiro)
    return achados


def portao_fechado(
    raiz: Path, fotos: str, codigo: tuple[str, ...], conferido: str
) -> bool | None:
    """As DUAS portas, na ordem: a topologia primeiro, a declaração depois.

    `None` continua querendo dizer "não dá para medir aqui" — a segunda porta
    não inventa veredito onde a primeira se cala.
    """
    veredito = fotos_em_dia(raiz, fotos, codigo)
    if veredito is not False:
        return veredito

    commit_do_codigo = _ultimo_commit(raiz, *codigo)
    return bool(commit_do_codigo) and commit_do_codigo in conferencia_declarada(
        raiz, conferido
    )


def _sem_historico(raiz: Path) -> bool:
    """Clone raso ou pasta sem git: aqui não há o que medir, e não há defeito."""
    if not (raiz / ".git").exists():
        return True
    if (raiz / ".git" / "shallow").exists():
        return True
    return not _git(raiz, "rev-parse", "HEAD")


def test_as_fotos_nao_ficam_atras_do_codigo_da_tela() -> None:
    """As imagens do README acompanham a versão — a regra escrita no `CLAUDE.md`."""
    if _sem_historico(RAIZ):
        pytest.skip("sem histórico git completo (clone raso ou pasta sem git)")

    sujas = familias_sujas(RAIZ, FOTOS)
    a_medir = [f for f in familias_sob(FOTOS) if f not in sujas]
    if not a_medir:
        return  # a cura está em curso: as imagens novas ainda não têm commit

    vereditos = [portao_fechado(RAIZ, f, CODIGO_DA_TELA, CONFERIDO) for f in a_medir]
    if all(v is None for v in vereditos):
        pytest.skip("as fotos ou o código da tela ainda não têm commit próprio")
    veredito = not any(v is False for v in vereditos)

    atrasadas = [f for f, v in zip(a_medir, vereditos, strict=True) if v is False]
    commit_das_fotos = (
        _ultimo_commit(RAIZ, *_pathspec(atrasadas[0]))[:7] if atrasadas else ""
    )
    commit_do_codigo = _ultimo_commit(RAIZ, *CODIGO_DA_TELA)

    assert veredito, (
        f"a interface mudou em {commit_do_codigo[:7]} e as fotos de "
        f"`{'`, `'.join(atrasadas)}` "
        f"são de {commit_das_fotos}, que veio ANTES. As imagens do `README.md` "
        "e do `docs/usage/interface.md` documentam uma tela que pode não "
        "existir mais.\n\n"
        f"{COMANDOS_DE_CURA}\n\n"
        "Uma execução, nenhum clique. Se as imagens saírem DIFERENTES, olhe-as "
        "antes de commitar: mudança de DESENHO é palavra dela "
        "(PROVA-DE-TELA-01), não de quem tirou a foto.\n\n"
        "Se saírem IGUAIS não há o que commitar, e aí é a segunda porta — "
        f"acrescente a `{CONFERIDO}` a linha\n\n"
        f"    {commit_do_codigo}  <data>  <o que você mediu>\n\n"
        "NÃO refotografe só para gerar bytes: a foto carrega o estado VIVO da "
        "máquina de quem a tira (quantos controles na mesa, a cor lida de cada "
        "um), e commitar a sua troca a mesa dela pela sua, calada."
    )


def _repo_de_mentira(tmp_path: Path, fotos_por_ultimo: bool) -> Path:
    """Um repositório com dois commits, na ordem pedida."""
    raiz = tmp_path / ("em_dia" if fotos_por_ultimo else "atrasado")
    (raiz / FOTOS).mkdir(parents=True)
    (raiz / CODIGO_DA_TELA[0]).mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    subprocess.run(
        ["git", "config", "user.email", "portao@exemplo.invalido"],
        cwd=str(raiz),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Portão"], cwd=str(raiz), check=True
    )
    # O sandbox não pode herdar os hooks da MÁQUINA. Nesta aqui há um
    # `core.hooksPath` global que recusa commit com identidade diferente da
    # dela — e o commit deste repositório de mentira é justamente com outra.
    # Medido em 13/08/2026: sem esta linha, `git commit` sai com
    # "[BLOQUEIO] Identidade incorreta" e o teste reprova por motivo nenhum.
    sem_hooks = tmp_path / "sem_hooks"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)],
        cwd=str(raiz),
        check=True,
    )

    def _commitar(caminho: str, conteudo: str, mensagem: str) -> None:
        (raiz / caminho).write_text(conteudo, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", mensagem], cwd=str(raiz), check=True
        )

    primeiro = (
        (f"{CODIGO_DA_TELA[0]}/home_actions.py", "a aba mudou")
        if fotos_por_ultimo
        else (f"{FOTOS}/readme_inicio.png", "a foto")
    )
    segundo = (
        (f"{FOTOS}/readme_inicio.png", "a foto nova")
        if fotos_por_ultimo
        else (f"{CODIGO_DA_TELA[0]}/home_actions.py", "a aba mudou depois")
    )
    _commitar(primeiro[0], primeiro[1], "primeiro")
    _commitar(segundo[0], segundo[1], "segundo")
    return raiz


def test_o_portao_acusa_foto_atrasada(tmp_path: Path) -> None:
    """A MORDIDA: com a tela mexida depois da foto, o comparador tem de reprovar."""
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=False)

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "o comparador aceitou um repositório em que a interface mudou DEPOIS "
        "da última foto. É a situação exata de 13/08/2026, com três commits de "
        "`app/`/`gui/` entre a foto e a tag — e é o que este arquivo existe "
        "para não deixar acontecer de novo."
    )


def test_o_portao_acusa_retrato_mexido_depois_da_foto(tmp_path: Path) -> None:
    """A MORDIDA do Z0-1 (§2.2/M1): o INSTRUMENTO conta como código da tela.

    Repositório de dois commits: primeiro a foto, segundo **só** o retratista —
    nenhum outro arquivo. Se `CODIGO_DA_TELA` não alcançasse o instrumento, o
    segundo commit não tocaria nada que o comparador olha, `_ultimo_commit`
    sairia vazio e `fotos_em_dia` devolveria `None` — que vira `pytest.skip`,
    verde, sem acusar nada.

    O ALVO MUDOU DE ARQUIVO EM 06/09/2026 (`GTK-3`), e a regra não. O
    instrumento era `scripts/gui-captura/retratar_abas.py`, o retratista da
    JANELA GTK, apagado com ela; hoje é
    `src/hefesto_dualsense4unix/interface/olhar.py`, que tira as DEZ. Ele mora
    dentro da primeira entrada de `CODIGO_DA_TELA`, e por isso a tupla encolheu
    de quatro para três sem perder o alcance — é o que este teste PROVA.

    Para morder: comente a primeira entrada de `CODIGO_DA_TELA` (a linha
    `"src/hefesto_dualsense4unix/interface"`) e rode este teste — ele reprova
    com `assert None is False`, porque o comparador volta a ficar cego ao
    instrumento.
    """
    raiz = tmp_path / "so_retrato_mexido"
    (raiz / FOTOS).mkdir(parents=True)
    (raiz / "src" / "hefesto_dualsense4unix" / "interface").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    subprocess.run(
        ["git", "config", "user.email", "portao@exemplo.invalido"],
        cwd=str(raiz),
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Portão"], cwd=str(raiz), check=True)
    sem_hooks = tmp_path / "sem_hooks_retrato"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)],
        cwd=str(raiz),
        check=True,
    )

    def _commitar(caminho: str, conteudo: str, mensagem: str) -> None:
        (raiz / caminho).write_text(conteudo, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", mensagem], cwd=str(raiz), check=True
        )

    _commitar(f"{FOTOS}/readme_inicio.png", "a foto", "primeiro")
    _commitar(
        "src/hefesto_dualsense4unix/interface/olhar.py",
        "o retratista das dez, mexido",
        "segundo — só o instrumento",
    )

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "o comparador não acusou uma mudança em `interface/olhar.py` "
        "posterior à foto. É o buraco exato do F14: o instrumento que decide "
        "o que a foto mostra mudou +645 linhas no commit `3de95ff` e nada "
        "acusou, porque `CODIGO_DA_TELA` não o citava."
    )


def test_a_foto_da_vista_nao_paga_a_divida_das_dez_do_readme(tmp_path: Path) -> None:
    """A MORDIDA DA PASTA NOVA: cada família de foto responde por si.

    O DEFEITO, simulado pelo conferente em 11/09/2026 sobre a régua velha:
    `docs/usage/assets/maximizada/` cai DENTRO de `docs/usage/assets` quando a
    pergunta casa por prefixo, então um commit que gravasse só a foto da vista
    devolvia `em-dia` e a dívida das dez do README ficava quitada por foto que
    não é delas. As dez podiam apodrecer caladas — que é exatamente o defeito
    que a PRINTS-DAS-DEZ-01 tinha acabado de ACHAR (as do README paradas em
    08/09), reaberto numa segunda família ainda menos coberta.

    Três commits, nesta ordem: a foto do README, o código da tela, e a foto da
    VISTA. A família do README está atrasada e a da vista está em dia.

    **Para morder:** troque `_pathspec(familia)` por `[familia]` (tirando o
    `:(exclude)`) e este teste reprova com `assert True is False` — o
    `git log -- docs/usage/assets` volta a responder com o commit da subpasta.
    """
    raiz = tmp_path / "so_a_vista_refeita"
    (raiz / FOTOS_DA_VISTA).mkdir(parents=True)
    (raiz / CODIGO_DA_TELA[0]).mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    for chave, valor in (
        ("user.email", "portao@exemplo.invalido"),
        ("user.name", "Portão"),
    ):
        subprocess.run(["git", "config", chave, valor], cwd=str(raiz), check=True)
    sem_hooks = tmp_path / "sem_hooks_vista"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)], cwd=str(raiz), check=True
    )

    def _commitar(caminho: str, conteudo: str, mensagem: str) -> None:
        (raiz / caminho).write_text(conteudo, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", mensagem], cwd=str(raiz), check=True
        )

    _commitar(f"{FOTOS}/aba-01-jogar.png", "a foto do README", "primeiro")
    _commitar(f"{CODIGO_DA_TELA[0]}/aba01.py", "a aba mudou", "segundo — a tela")
    _commitar(
        f"{FOTOS_DA_VISTA}/aba-01-jogar.png",
        "a foto da vista, refeita",
        "terceiro — só a pasta nova",
    )

    assert uma_familia_em_dia(raiz, FOTOS_DA_VISTA, CODIGO_DA_TELA) is True, (
        "a família da VISTA foi refeita depois da mudança de tela e mesmo "
        "assim não passou — a régua ficaria reprovando quem fez o certo."
    )
    assert uma_familia_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "as dez fotos do README são anteriores à mudança de tela e a régua "
        "disse que estavam em dia. A foto da pasta `maximizada/` pagou a "
        "dívida delas — o buraco medido em 11/09/2026."
    )
    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "uma família atrasada tem de reprovar por todas: a pergunta do portão "
        "é 'a tela de hoje está fotografada?', e meia resposta é não."
    )
    assert familias_atrasadas(raiz, FOTOS, CODIGO_DA_TELA) == [FOTOS], (
        "a mensagem precisa NOMEAR a pasta que está devendo — sem isso quem "
        "apanha roda o comando da outra família e conclui que o portão quebrou."
    )


def test_o_portao_aprova_foto_em_dia(tmp_path: Path) -> None:
    """E o outro lado: fotografar depois de mexer na tela tem de passar.

    Sem este, "reprovar sempre" satisfaria o teste de cima — e um portão que
    reprova sempre é desligado na primeira semana.
    """
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=True)

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is True, (
        "o comparador reprovou um repositório em que a foto veio DEPOIS da "
        "mudança de tela, que é o caminho bom."
    )


def _declarar(raiz: Path, texto: str) -> None:
    """Escreve a declaração de conferência, sem commitar.

    Não precisa de commit: a segunda porta lê o arquivo do DISCO, e é assim que
    ela tem de funcionar — quem acabou de rodar o retratista está escrevendo a
    linha agora, antes de commitar, exatamente como `fotos_sendo_refeitas_agora`
    já trata a foto suja.
    """
    (raiz / CONFERIDO).write_text(texto, encoding="utf-8")


def test_a_declaracao_so_vale_para_o_commit_que_ela_nomeia(tmp_path: Path) -> None:
    """A MORDIDA da segunda porta: SHA de outro commit não abre nada.

    Sem esta, bastaria CRIAR `CONFERIDO-EM.txt` com qualquer conteúdo para calar
    o portão para sempre — que é o defeito que a porta nova poderia introduzir.
    """
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=False)

    # Prosa, comentário e um SHA que não é o do commit de tela deste repositório.
    _declarar(
        raiz,
        "# conferido por ninguém\n"
        "0123456789abcdef0123456789abcdef01234567  03/09/2026  outro commit\n"
        "rodei o retratista, juro\n",
    )

    assert portao_fechado(raiz, FOTOS, CODIGO_DA_TELA, CONFERIDO) is False, (
        "a segunda porta abriu com uma declaração que NÃO nomeia o commit de "
        "tela deste repositório. Assim ela deixaria de ser a prova de um gesto "
        "e viraria um arquivo que, uma vez criado, cala o portão para sempre."
    )


def test_a_declaracao_fecha_o_portao_quando_a_foto_nao_muda(tmp_path: Path) -> None:
    """E o outro lado: declarando o commit CERTO, o portão fecha.

    É o caso medido em 03/09/2026 — o commit `2899ef0d` mexeu em `app/` e as 14
    fotos saíram byte a byte idênticas, de modo que não havia imagem para
    commitar. Sem este teste, "recusar sempre" satisfaria a mordida de cima e a
    porta nasceria emperrada.
    """
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=False)
    commit_do_codigo = _ultimo_commit(raiz, *CODIGO_DA_TELA)

    _declarar(
        raiz,
        f"{commit_do_codigo}  03/09/2026  rodei o retratista, 14 fotos idênticas\n",
    )

    assert portao_fechado(raiz, FOTOS, CODIGO_DA_TELA, CONFERIDO) is True, (
        "o portão recusou uma declaração que nomeia exatamente o commit de tela "
        "atual. Nesse estado ele fica vermelho para sempre quando a mudança de "
        "tela não move pixel — e a única saída vira refotografar por bytes, "
        "que escreve o estado da máquina de quem rodou dentro da documentação."
    )


def test_sem_historico_o_portao_se_cala(tmp_path: Path) -> None:
    """Clone raso não é defeito de foto — e não pode virar vermelho no CI."""
    assert _sem_historico(tmp_path), (
        "uma pasta sem `.git` foi tratada como repositório com histórico. No "
        "CI, com `actions/checkout` raso, isto viraria um vermelho que não "
        "aponta defeito nenhum."
    )
