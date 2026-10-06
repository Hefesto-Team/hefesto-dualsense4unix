"""A mordida do `check_regua_de_tela.py` — REGUA-NO-GANCHO-01."""

from __future__ import annotations

import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_regua_de_tela.py"
GANCHO = RAIZ / "scripts" / "hooks" / "pre-commit"
FOTOS = RAIZ / "scripts" / "check_fotos_da_tela.py"


def _carregar(caminho: Path, nome: str):
    """Executa o FONTE, nunca o `__pycache__`. E isto é medido, não zelo."""
    modulo = types.ModuleType(nome)
    modulo.__file__ = str(caminho)
    fonte = caminho.read_text(encoding="utf-8")
    exec(compile(fonte, str(caminho), "exec"), modulo.__dict__)
    return modulo


def _linhas_de_codigo(caminho: Path) -> list[str]:
    """As linhas do gancho que EXECUTAM, sem as que só falam."""
    return [
        linha
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


portao = _carregar(PORTAO, "check_regua_de_tela")

UMA_ABA = "src/hefesto_dualsense4unix/interface/aba06.py"
UMA_PAGINA = "src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html"
O_WIDGET = "src/hefesto_dualsense4unix/interface/cartao_do_controle.py"
UMA_REGUA = "src/hefesto_dualsense4unix/interface/regua_popup.py"
A_PONTE = "src/hefesto_dualsense4unix/interface/controles_vivos.py"
UM_PYTEST = "tests/unit/test_o_gesto_chega.py"
UMA_PROSA = "src/hefesto_dualsense4unix/interface/CORRECOES.md"


@pytest.mark.parametrize("de_tela", [UMA_ABA, UMA_PAGINA, O_WIDGET])
def test_fala_quando_a_tela_muda_sem_regua(de_tela: str) -> None:
    """A MORDIDA: mexer na tela sem trazer régua tem de FALAR."""
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


def test_cala_quando_o_commit_nao_toca_a_tela() -> None:
    """O pior defeito possível aqui: falar em commit que não é de tela."""
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


def test_a_convencao_de_nome_alcanca_as_reguas_do_disco() -> None:
    """Nenhuma régua do disco pode ficar de fora da convenção de prefixo."""
    nao_reconhecidas = []
    for nome_da_pasta in portao.PASTAS_DE_REGUA:
        pasta = RAIZ / nome_da_pasta
        if not pasta.is_dir():
            continue
        for f in sorted(pasta.iterdir()):
            if not (f.is_file() and f.suffix == ".py"):
                continue
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
    """`scripts/regua_de_tela.py` é a régua da interface nova, e tem de contar."""
    veredito, _, creditadas, _ = portao.julgar([O_WIDGET, "scripts/regua_de_tela.py"])
    assert veredito == portao.COM_REGUA, (
        "o portão cobrou régua de um commit que TRAZ a régua do WebView."
    )
    assert creditadas == ["scripts/regua_de_tela.py"]


def test_o_proprio_portao_nao_se_credita_como_regua() -> None:
    """`check_` PERGUNTA pela medição; `regua` MEDE. Confundir os dois esvazia."""
    assert not portao.e_regua("scripts/check_regua_de_tela.py")
    assert not portao.e_regua("scripts/check_fotos_da_tela.py")


def test_a_tela_deste_portao_contem_a_do_portao_da_foto() -> None:
    """As duas listas de tela não podem divergir em silêncio."""
    if not FOTOS.is_file():
        pytest.skip("o portão da foto não existe nesta árvore")
    fotos = _carregar(FOTOS, "check_fotos_da_tela")
    faltando = [p for p in fotos.CODIGO_DA_TELA if p not in portao.TELA]
    assert not faltando, (
        f"{faltando} conta como tela para o portão da foto e não para o da "
        "régua. Uma mudança ali seria fotografada e nunca medida."
    )


def test_o_gancho_chama_o_portao() -> None:
    """A CHAMADA, não a menção — ver `_linhas_de_codigo`."""
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
    """O contrato de saída, medido na bancada de 29/08."""
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
    """O verbo dela é INDUZIR. Enquanto `GRAU < 3`, nada é reprovado."""
    assert portao.GRAU < 3, (
        "o grau 3 reprova commits. Confirme o `--censo` antes de deixar isto "
        "passar, e escreva o número na mensagem do commit que subiu o degrau."
    )
