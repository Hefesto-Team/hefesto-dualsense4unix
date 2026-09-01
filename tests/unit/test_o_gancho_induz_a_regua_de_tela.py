"""A mordida do `check_regua_de_tela.py` — REGUA-NO-GANCHO-01.

A PASTA MUDOU DE NOME E ESTE ARQUIVO FICOU PARA TRÁS — 31/08/2026.
O commit `48b4e1a2` ("o produto lê de `layout/`; `novo-layout/` volta a ser só
referência") migrou o `check_regua_de_tela.py`, mas as constantes daqui
continuaram apontando para `novo-layout/`. Resultado: **13 reprovações**, todas
do portão medindo um caminho que o produto não usa mais — e nenhuma delas era
defeito de produto. Migração pela metade é assim: a parte que ninguém roda no
dia seguinte é a que fica.

Pedido dela, 29/08/2026: *"temos que ter no nosso hook do novo dev algo que
induza a construção de validações via interface pra ver se tal problema foi
resolvido ou se tal coisa traz regressão."*

Este arquivo segura os QUATRO jeitos de esvaziar aquele portão:

* **não morder** — `test_fala_quando_a_tela_muda_sem_regua` e a família dela.
  É o defeito medido de 29/08: o `--prova-gesto` dava VERDE sobre dois botões
  que nunca clicava, e o commit que criou os botões não trouxe régua nenhuma;
* **falar sempre** — `test_cala_quando_o_commit_nao_toca_a_tela` e
  `test_cala_quando_o_commit_traz_regua`. É o pior lado dos dois: aviso que sai
  em todo commit deixa de ser lido em uma semana, e portão que reclama sem
  razão ensina a ignorar portão;
* **desligar** — `test_o_gancho_chama_o_portao` reprova se o `pre-commit`
  parar de invocá-lo;
* **apodrecer** — `test_a_convencao_de_nome_alcanca_as_reguas_do_disco` varre
  `src/hefesto_dualsense4unix/interface/` e reprova se nascer régua que a convenção de
  prefixo não reconhece. Sem ele, uma régua com nome novo passaria a não contar
  como régua, e o portão cobraria régua de quem acabou de escrever uma.

E `test_o_codigo_de_veredito_nao_e_o_do_traceback` tranca o contrato de saída
que a bancada de 29/08 revelou: com um número só, ou o grau 3 nasce inerte, ou
um traceback do instrumento trava a árvore dela.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_regua_de_tela.py"
GANCHO = RAIZ / "scripts" / "hooks" / "pre-commit"
FOTOS = RAIZ / "scripts" / "check_fotos_da_tela.py"


def _carregar(caminho: Path, nome: str):
    """Executa o FONTE, nunca o `__pycache__`. E isto é medido, não zelo.

    MEDIDO em 29/08/2026, na bancada de mordida deste arquivo. O padrão usual
    (`importlib.util.spec_from_file_location` + `exec_module`) valida o `.pyc`
    por **mtime em segundos inteiros + tamanho em bytes**. Arrancar uma cura
    para ver o teste reprovar costuma ser uma troca pequena — aqui foi
    `VEREDITO_REPROVA = 2` para `= 1`, que tem o MESMO tamanho — e devolver o
    arquivo logo em seguida cai no MESMO segundo. As duas chaves batem, o
    Python executa o bytecode velho, e o teste responde sobre uma versão que
    não está no disco.

    Foi o que aconteceu: a sabotagem ficou VERDE e a devolução ficou VERMELHA,
    as duas mentindo. Um banco de mordida que lê bytecode não é banco de
    mordida — é a régua confundindo o que está no disco com o que ela decorou.

    `compile()` do texto lido não consulta nem escreve `__pycache__`.
    """
    modulo = types.ModuleType(nome)
    modulo.__file__ = str(caminho)
    fonte = caminho.read_text(encoding="utf-8")
    exec(compile(fonte, str(caminho), "exec"), modulo.__dict__)
    return modulo


def _linhas_de_codigo(caminho: Path) -> list[str]:
    """As linhas do gancho que EXECUTAM, sem as que só falam.

    MEDIDO em 29/08/2026: `test_o_gancho_chama_o_portao` procurava o caminho do
    script no arquivo inteiro e por isso ficou VERDE com a chamada arrancada —
    o caminho continuava escrito no comentário do bloco, e num `[ -f ... ]`.
    É o defeito que esta casa já pegou onze vezes numa leva só: *a régua
    confunde a PALAVRA com o ATO*, e desliga exatamente quando alguém escreve
    bem o comentário.
    """
    return [
        linha
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


portao = _carregar(PORTAO, "check_regua_de_tela")

UMA_ABA = "src/hefesto_dualsense4unix/interface/aba06.py"
UMA_PAGINA = "src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html"
O_WIDGET = "src/hefesto_dualsense4unix/app/widgets/controller_card.py"
UMA_REGUA = "src/hefesto_dualsense4unix/interface/regua_popup.py"
A_PONTE = "src/hefesto_dualsense4unix/interface/controles_vivos.py"
UM_PYTEST = "tests/unit/test_o_gesto_chega.py"
UMA_PROSA = "src/hefesto_dualsense4unix/interface/CORRECOES-DELA.md"


# ------------------------------------------------------------- a mordida


@pytest.mark.parametrize("de_tela", [UMA_ABA, UMA_PAGINA, O_WIDGET])
def test_fala_quando_a_tela_muda_sem_regua(de_tela: str) -> None:
    """A MORDIDA: mexer na tela sem trazer régua tem de FALAR.

    Os três casos são as três formas de mexer na tela: o gerador de uma aba do
    mockup, a página gerada, e o widget GTK de hoje. É a situação exata do
    `--prova-gesto` de 29/08 — dois botões novos, nenhuma linha de régua.
    """
    veredito, desenho, reguas, _ = portao.julgar([de_tela, "docs/process/nota.md"])

    assert veredito == portao.SEM_REGUA, (
        f"o portão deixou passar calado um commit que mexe em `{de_tela}` sem "
        "régua nenhuma — que é o commit dos dois botões mortos de 29/08."
    )
    assert desenho == [de_tela], (
        "a mensagem precisa NOMEAR o arquivo de tela; um aviso que não diz "
        "qual arquivo é um aviso que ninguém sabe atender."
    )
    assert reguas == []


def test_nomeia_a_aba_que_o_commit_tocou() -> None:
    """Sem o número da aba o aviso não é acionável — foi o pedido dela."""
    _, _, _, abas = portao.julgar([UMA_ABA, UMA_PAGINA,
    "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"])
    assert abas == ["06", "08"]


# --------------------------------------------------- e o lado que cala


def test_cala_quando_o_commit_nao_toca_a_tela() -> None:
    """O pior defeito possível aqui: falar em commit que não é de tela.

    Aviso que sai em todo commit deixa de ser lido, e a primeira reação de quem
    o lê sem razão é `--no-verify`.
    """
    veredito, _, _, _ = portao.julgar(
        [
            "src/hefesto_dualsense4unix/daemon/sensor_hub.py",
            "docs/process/sprints/uma-sprint.md",
            "scripts/portoes.sh",
        ]
    )
    assert veredito == portao.EM_BRANCO


@pytest.mark.parametrize("a_regua", [UMA_REGUA, A_PONTE, UM_PYTEST])
def test_cala_quando_o_commit_traz_regua(a_regua: str) -> None:
    """As três formas de trazer régua: a da pasta, a ponte JS, e um pytest."""
    veredito, _, creditadas, _ = portao.julgar([UMA_ABA, a_regua])
    assert veredito == portao.COM_REGUA
    assert creditadas == [a_regua], (
        "o crédito tem de ser NOMEADO: um crédito errado precisa ser visível, "
        "não silencioso."
    )


def test_prosa_dentro_do_mockup_nao_e_desenho() -> None:
    """Um `.md` em `layout/` documenta a tela, não a muda."""
    veredito, _, _, _ = portao.julgar([UMA_PROSA, "layout/GUIA_IMPLEMENTACAO.md"])
    assert veredito == portao.EM_BRANCO


def test_commit_so_de_regua_nao_se_cobra_a_si_mesmo() -> None:
    veredito, _, _, _ = portao.julgar([UMA_REGUA])
    assert veredito == portao.SO_REGUA


def test_a_repeticao_vira_uma_linha() -> None:
    """O bloco ensina; o bloco repetido ensina a pular o bloco."""
    veredito, _, _, _ = portao.julgar([UMA_ABA], abas_ja_devendo=["06"])
    assert veredito == portao.SEM_REGUA_DE_NOVO


def test_aba_nova_traz_o_bloco_de_volta() -> None:
    """A dívida na 06 não pode comprar silêncio sobre a 08."""
    veredito, _, _, abas = portao.julgar(
        [UMA_ABA, "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"],
        abas_ja_devendo=["06"]
    )
    assert veredito == portao.SEM_REGUA
    assert "08" in abas


# ------------------------------------------------- contra o apodrecimento


def test_a_convencao_de_nome_alcanca_as_reguas_do_disco() -> None:
    """Nenhuma régua do disco pode ficar de fora da convenção de prefixo.

    O portão reconhece régua por PREFIXO (`regua`, `conferir`, `olhar`,
    `medir`), que é convenção desta casa e não inventário. A convenção só não
    apodrece se alguém a confrontar com o disco — é este teste.

    Se ele reprovar, a escolha é: renomear a régua nova para a convenção, ou
    acrescentar o prefixo em `PREFIXOS_DE_REGUA`. O que NÃO pode é a régua
    existir e não contar: o portão passaria a cobrar régua de quem acabou de
    escrever uma.
    """
    nao_reconhecidas = []
    for nome_da_pasta in portao.PASTAS_DE_REGUA:
        pasta = RAIZ / nome_da_pasta
        if not pasta.is_dir():
            continue
        for f in sorted(pasta.iterdir()):
            if not (f.is_file() and f.suffix == ".py"):
                continue
            # "parece régua" é uma pergunta DIFERENTE da convenção — de
            # propósito. Se as duas fossem a mesma pergunta o teste seria
            # tautológico, e tautologia é como uma régua desta casa já nasceu
            # falsa (a primeira `regua.py`, que comparava cada aba consigo
            # mesma).
            parece = ("regua" in f.name or "conferir" in f.name) and not f.name.startswith(
                "check_"
            )
            if parece and not portao.e_regua(f"{nome_da_pasta}/{f.name}"):
                nao_reconhecidas.append(f"{nome_da_pasta}/{f.name}")

    assert not nao_reconhecidas, (
        "estas parecem réguas e a convenção de nome não as reconhece: "
        f"{nao_reconhecidas}. Enquanto for assim, o portão COBRA régua de quem "
        "acabou de escrever uma. Renomeie-as para a convenção, ou amplie "
        "`PREFIXOS_DE_REGUA` / `PASTAS_DE_REGUA`."
    )


def test_a_regua_versionada_do_webview_conta_como_regua() -> None:
    """`scripts/regua_de_tela.py` é a régua da interface nova, e tem de contar.

    MEDIDO em 29/08/2026: a primeira versão deste portão só reconhecia régua
    dentro de `src/hefesto_dualsense4unix/interface/`, e a régua que dirige o `WebView` por
    dentro nasceu em `scripts/` DE PROPÓSITO — `layout/` é
    `.gitignore:108`, e instrumento permanente tem de ser versionado para
    viajar em worktree.

    Sem esta linha o portão nascia falso do pior jeito: mudo sobre o mockup
    (que o git não vê) e ranzinza com quem versiona a régua.
    """
    veredito, _, creditadas, _ = portao.julgar([O_WIDGET, "scripts/regua_de_tela.py"])
    assert veredito == portao.COM_REGUA, (
        "o portão cobrou régua de um commit que TRAZ a régua do WebView."
    )
    assert creditadas == ["scripts/regua_de_tela.py"]


def test_o_proprio_portao_nao_se_credita_como_regua() -> None:
    """`check_` PERGUNTA pela medição; `regua` MEDE. Confundir os dois esvazia.

    Se o portão contasse a si mesmo como régua, bastaria mexer nele para
    comprar silêncio sobre qualquer mudança de tela.
    """
    assert not portao.e_regua("scripts/check_regua_de_tela.py")
    assert not portao.e_regua("scripts/check_fotos_da_tela.py")


def test_a_tela_deste_portao_contem_a_do_portao_da_foto() -> None:
    """As duas listas de tela não podem divergir em silêncio.

    O `check_fotos_da_tela.py` pergunta se alguém OLHOU a tela; este pergunta
    se alguém a MEDE. São perguntas diferentes sobre o MESMO território, e um
    arquivo que conta como tela para a foto e não conta para a régua seria um
    buraco que ninguém veria — o mesmo defeito que
    `test_as_duas_listas_de_codigo_de_tela_sao_a_mesma` já tranca do outro lado.
    """
    if not FOTOS.is_file():
        pytest.skip("o portão da foto não existe nesta árvore")
    fotos = _carregar(FOTOS, "check_fotos_da_tela")
    faltando = [p for p in fotos.CODIGO_DA_TELA if p not in portao.TELA]
    assert not faltando, (
        f"{faltando} conta como tela para o portão da foto e não para o da "
        "régua. Uma mudança ali seria fotografada e nunca medida."
    )


# ------------------------------------------------- contra o desligamento


def test_o_gancho_chama_o_portao() -> None:
    """A CHAMADA, não a menção — ver `_linhas_de_codigo`.

    A primeira versão deste teste procurava o caminho no arquivo inteiro e
    ficou VERDE com a chamada arrancada, porque o caminho segue escrito no
    comentário do bloco e no `[ -f ... ]` que o guarda.
    """
    invoca = [
        linha
        for linha in _linhas_de_codigo(GANCHO)
        if "python3" in linha and "scripts/check_regua_de_tela.py" in linha
    ]
    assert invoca, (
        "o `pre-commit` parou de INVOCAR o portão da régua (mencioná-lo num "
        "comentário não basta). Sem a chamada, o pedido dela de 29/08 vira "
        "prosa — e prosa foi o que não impediu os nove branches de interface "
        "sem foto em 24/08."
    )


def test_o_codigo_de_veredito_nao_e_o_do_traceback() -> None:
    """O contrato de saída, medido na bancada de 29/08.

    Com um número só não dá para atender às duas exigências ao mesmo tempo:
    o grau 3 tem de SEGURAR o commit, e um instrumento quebrado NUNCA pode
    segurá-lo — um gancho quebrado impede ela de commitar na árvore que usa
    todo dia.
    """
    assert portao.VEREDITO_REPROVA != 1, (
        "o veredito não pode usar o mesmo código que o Python devolve para "
        "traceback, senão instrumento quebrado vira portão fechado."
    )
    codigo = "\n".join(_linhas_de_codigo(GANCHO))
    assert f'= "{portao.VEREDITO_REPROVA}"' in codigo, (
        "o gancho tem de propagar SÓ o código de veredito. Com `|| true` "
        "sozinho o grau 3 nasce inerte; com `|| falhou=1` sozinho, um "
        "traceback trava a árvore dela."
    )


def test_no_grau_de_hoje_ele_nao_segura_commit_nenhum() -> None:
    """O verbo dela é INDUZIR. Enquanto `GRAU < 3`, nada é reprovado.

    Se este teste reprovar, alguém subiu o degrau — e a subida tem gatilho
    medido, não data: `check_regua_de_tela.py --censo` tem de mostrar que a
    MAIORIA dos commits que tocam a tela já traz régua. Reprovar a maioria é o
    portão que alguém desliga na segunda-feira.
    """
    assert portao.GRAU < 3, (
        "o grau 3 reprova commits. Confirme o `--censo` antes de deixar isto "
        "passar, e escreva o número na mensagem do commit que subiu o degrau."
    )
