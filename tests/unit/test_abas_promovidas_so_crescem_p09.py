"""P-09 — o portão de fala cresce de "avisa" para "reprova", uma aba por vez.

Este arquivo é o que o docstring de ``ABAS_COM_FALA_DECLARADA``
(``scripts/validar-fala-de-tela.py``) nomeia como dono da catraca. Ele
existe por duas razões, e a segunda é a que decide:

1. **A trava por aba tem de MORDER hoje**, com o conjunto ainda vazio. Um
   mecanismo que só será exercitado no dia em que alguém promover a primeira
   aba nasce sem prova, e a promoção acontece meses depois, por outra pessoa,
   que vai acreditar nele. As mordidas abaixo promovem uma aba NUMA ÁRVORE DE
   MENTIRA e provam cada regra.
2. **O conjunto de referência da catraca é literal DESTE ARQUIVO**, nunca
   lido de ``scripts/``. É a lição que a ADR-016 pagou por um mês e que
   ``tests/unit/test_o_mapa_separa_divida_de_decisao.py`` deixou escrita: um
   teto lido da própria fonte passa sempre. Despromover uma aba exige editar
   este arquivo, e isso aparece no diff.

COMO A ÁRVORE DE MENTIRA PROMOVE UMA ABA
-----------------------------------------
``ABAS_COM_FALA_DECLARADA``, ``ARQUIVOS_DA_ABA`` e ``FRASES_SEM_FALA`` são
constantes de módulo do portão, não coisas que a árvore analisada carrega —
então ``--raiz`` sozinho não promove nada. ``_portao_com_promocao`` copia o
roteiro real para dentro da árvore de mentira trocando as três linhas, e
**afirma que trocou**: uma substituição que não casa devolveria um portão com
o conjunto vazio, que passa em tudo. Instrumento que falha calado é pior que
instrumento nenhum (a lição de ``portoes-em-serie-enganam``).
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from tests.unit.test_validar_fala_de_tela import FATOS_BASE, monta_arvore

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT_REAL = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"

#: O conjunto de abas promovidas de HOJE, escrito à mão aqui. Quando uma aba
#: for promovida em ``scripts/validar-fala-de-tela.py``, esta linha ganha o
#: nome dela junto — e nunca perde nenhum, porque
#: ``test_o_conjunto_de_abas_promovidas_so_cresce`` compara os dois conjuntos
#: nessa direção.
#:
#: **Nasce vazio**, e isso é o desenho da PAREAMENTO-01: no dia 1 o registro
#: tem uma ``Fala`` só, e promover uma aba agora exigiria editar arquivos de
#: outras frentes. As duas primeiras a promover estão nomeadas na sprint:
#: **Início** e **Status**.
ABAS_PROMOVIDAS_ATE_HOJE: frozenset[str] = frozenset()


def _portao_com_promocao(
    raiz: Path,
    *,
    abas: frozenset[str] | set[str],
    arquivos_da_aba: dict[str, tuple[str, ...]],
    frases_sem_fala: dict[str, str] | None = None,
) -> Path:
    """Copia o portão real para `raiz/scripts/`, promovendo as abas pedidas."""
    fonte = SCRIPT_REAL.read_text(encoding="utf-8")
    trocas = {
        "ABAS_COM_FALA_DECLARADA: frozenset[str] = frozenset()": (
            f"ABAS_COM_FALA_DECLARADA: frozenset[str] = frozenset({sorted(abas)!r})"
        ),
        "ARQUIVOS_DA_ABA: dict[str, tuple[str, ...]] = {}": (
            f"ARQUIVOS_DA_ABA: dict[str, tuple[str, ...]] = {arquivos_da_aba!r}"
        ),
        "FRASES_SEM_FALA: dict[str, str] = {}": (
            f"FRASES_SEM_FALA: dict[str, str] = {(frases_sem_fala or {})!r}"
        ),
    }
    for antigo, novo in trocas.items():
        assert fonte.count(antigo) == 1, (
            f"a linha {antigo!r} mudou de forma em {SCRIPT_REAL.name}: sem ela "
            "esta mordida rodaria com o conjunto VAZIO e passaria sempre"
        )
        fonte = fonte.replace(antigo, novo)
    destino = raiz / "scripts" / SCRIPT_REAL.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(fonte, encoding="utf-8")
    return destino


def _roda(portao: Path, raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(portao), "--raiz", str(raiz), *args],
        capture_output=True,
        text=True,
        check=False,
    )


#: Uma frase de tela que cita transporte e não declara nada. É a forma exata
#: do defeito de 17/08 e da dica da cor de 22/08: prosa que afirma o que o
#: aparelho faz, sem endereço no mapa.
FRASE_SOLTA = "Funciona igual no cabo e no rádio, sempre."

ARQUIVO_COM_FRASE_SOLTA = f'''\
"""Uma aba de mentira."""
from __future__ import annotations

DICA = {FRASE_SOLTA!r}
'''

ARQUIVO_COM_A_MESMA_FRASE_DECLARADA = f'''\
"""A mesma aba, com a frase declarada."""
from __future__ import annotations

from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_ACIONA, Fala

DICA = Fala(
    chave="audio.alto_falante@dualsense",
    lado="radio",
    aba="Início",
    texto={FRASE_SOLTA!r},
    afirma=AFIRMA_ACIONA,
)
'''


# ── a catraca ────────────────────────────────────────────────────────────


def _abas_promovidas_no_portao() -> frozenset[str]:
    """Lê `ABAS_COM_FALA_DECLARADA` por AST — nunca importando o roteiro.

    Importar o portão dentro da suíte funcionaria, e é justamente o que não se
    quer: uma catraca que lê o valor pelo mesmo caminho que ele é escrito
    aceita qualquer coisa que o roteiro decida chamar de conjunto. Aqui a
    forma tem de ser `frozenset({...})` com literal dentro, e qualquer outra
    coisa reprova em voz alta.
    """
    arvore = ast.parse(SCRIPT_REAL.read_text(encoding="utf-8"), filename=str(SCRIPT_REAL))
    for no in arvore.body:
        alvo = None
        if isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            alvo, valor = no.target.id, no.value
        elif (
            isinstance(no, ast.Assign)
            and len(no.targets) == 1
            and isinstance(no.targets[0], ast.Name)
        ):
            alvo, valor = no.targets[0].id, no.value
        if alvo != "ABAS_COM_FALA_DECLARADA":
            continue
        assert (
            isinstance(valor, ast.Call)
            and isinstance(valor.func, ast.Name)
            and valor.func.id == "frozenset"
        ), "`ABAS_COM_FALA_DECLARADA` deixou de ser um `frozenset(...)` literal"
        if not valor.args:
            return frozenset()
        return frozenset(ast.literal_eval(valor.args[0]))
    raise AssertionError("o portão perdeu `ABAS_COM_FALA_DECLARADA`")


def test_o_conjunto_de_abas_promovidas_so_cresce() -> None:
    """O conjunto do portão é superconjunto do literal deste arquivo."""
    perdidas = ABAS_PROMOVIDAS_ATE_HOJE - _abas_promovidas_no_portao()
    assert not perdidas, (
        f"as abas {sorted(perdidas)} estavam promovidas e saíram de "
        "`ABAS_COM_FALA_DECLARADA`. Despromover apaga cobertura em silêncio: "
        "se a decisão foi mesmo essa, ela tem de sair TAMBÉM da lista literal "
        "deste arquivo, com nota datada de por quê"
    )


# ── as mordidas da trava por aba ─────────────────────────────────────────


def test_aba_livre_com_frase_solta_passa(tmp_path: Path) -> None:
    """Aba FORA do conjunto é livre — é o que faz a migração ser de carona."""
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    portao = _portao_com_promocao(raiz, abas=frozenset(), arquivos_da_aba={})
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout


def test_aba_promovida_com_frase_solta_reprova_nomeando_a_frase(tmp_path: Path) -> None:
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    portao = _portao_com_promocao(
        raiz, abas={"Início"}, arquivos_da_aba={"Início": ("aba_inicio.py",)}
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "aba_inicio.py:4" in processo.stdout, processo.stdout
    assert FRASE_SOLTA[:40] in processo.stdout, processo.stdout


def test_declarar_a_fala_resolve_a_reprovacao(tmp_path: Path) -> None:
    """A saída do portão promete um conserto; este teste prova que ele conserta."""
    raiz = monta_arvore(
        tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_A_MESMA_FRASE_DECLARADA}
    )
    portao = _portao_com_promocao(
        raiz, abas={"Início"}, arquivos_da_aba={"Início": ("aba_inicio.py",)}
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout


def test_isencao_com_razao_escrita_passa(tmp_path: Path) -> None:
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    portao = _portao_com_promocao(
        raiz,
        abas={"Início"},
        arquivos_da_aba={"Início": ("aba_inicio.py",)},
        frases_sem_fala={FRASE_SOLTA: "é rótulo de botão, não afirma capacidade"},
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout


def test_isencao_sem_razao_escrita_reprova(tmp_path: Path) -> None:
    """Isenção com razão vazia é o mesmo que não ter portão, e é dito assim."""
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    portao = _portao_com_promocao(
        raiz,
        abas={"Início"},
        arquivos_da_aba={"Início": ("aba_inicio.py",)},
        frases_sem_fala={FRASE_SOLTA: "   "},
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "razão VAZIA" in processo.stdout, processo.stdout


def test_isencao_que_nao_casa_mais_com_frase_nenhuma_reprova(tmp_path: Path) -> None:
    """A lápide que sobrevive à própria cura.

    Medido em 25/08/2026 no ``portao_a_casa_sabe_e_o_produto_nao_faz``: duas
    notas datadas seguiram dizendo "nada de produção chama" sobre funções que
    a produção passou a chamar. Uma lista de isenções sem esta regra vira
    exatamente isso — texto que descreve uma árvore que não existe mais.
    """
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    portao = _portao_com_promocao(
        raiz,
        abas={"Início"},
        arquivos_da_aba={"Início": ("aba_inicio.py",)},
        frases_sem_fala={
            FRASE_SOLTA: "é rótulo de botão",
            "Esta frase sobre o cabo não existe mais na tela": "isenta desde nunca",
        },
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "APAGUE" in processo.stdout, processo.stdout


def test_aba_promovida_sem_arquivos_declarados_reprova_alto(tmp_path: Path) -> None:
    """Promover sem dizer quais arquivos são da aba desligaria a trava calada.

    É a mesma razão que ``anonymity-check.yml``:67-70 escreveu: um portão que
    se desliga por omissão de configuração é a forma silenciosa de portão
    nenhum.
    """
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    portao = _portao_com_promocao(raiz, abas={"Início"}, arquivos_da_aba={})
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "ARQUIVOS_DA_ABA" in processo.stdout, processo.stdout


def test_arquivo_declarado_que_sumiu_reprova(tmp_path: Path) -> None:
    """Renomear o arquivo da aba tirava a cobertura sem ninguém notar."""
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    portao = _portao_com_promocao(
        raiz, abas={"Início"}, arquivos_da_aba={"Início": ("aba_que_foi_renomeada.py",)}
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "não existe" in processo.stdout, processo.stdout


# ── a régua, e onde ela declara que mente ────────────────────────────────


def test_a_palavra_de_transporte_tem_fronteira_de_palavra(tmp_path: Path) -> None:
    """Sem a fronteira, `cabo` casa dentro de `acabou` e o portão grita falso.

    Portão que grita falso é desligado na semana seguinte — é o motivo escrito
    na própria PAREAMENTO-01 para a trava ser por aba.
    """
    arquivo = '''\
"""Uma aba de mentira, sem uma palavra de transporte."""
from __future__ import annotations

DICA = "O ajuste acabou de ser gravado no perfil."
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": arquivo})
    portao = _portao_com_promocao(
        raiz, abas={"Início"}, arquivos_da_aba={"Início": ("aba_inicio.py",)}
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout


def test_docstring_nao_entra_no_censo(tmp_path: Path) -> None:
    """Docstring é prosa para quem lê o código, não fala de tela.

    Contá-la levaria o censo de 38 para bem acima de cem — a PAREAMENTO-01
    mediu 31 de piso e 135 de teto justamente por causa disto.
    """
    arquivo = '''\
"""Este módulo desenha a aba, e explica o cabo e o rádio para quem o lê."""
from __future__ import annotations


def desenha() -> None:
    """Vale igual no cabo e no rádio, sempre."""
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": arquivo})
    portao = _portao_com_promocao(
        raiz, abas={"Início"}, arquivos_da_aba={"Início": ("aba_inicio.py",)}
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout


def test_censo_de_transporte_conta_a_arvore_viva(tmp_path: Path) -> None:
    """`--censo-de-transporte` é o único lugar de onde o número sai.

    O docstring de `descobre_falas` publica um número de 25/08/2026, e diz na
    própria linha que ele envelhece. Este teste prova que existe instrumento
    para o de hoje — sem ele, o número do docstring viraria a única fonte, que
    é como um fato errado se instala.
    """
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": ARQUIVO_COM_FRASE_SOLTA})
    processo = _roda(SCRIPT_REAL, raiz, "--censo-de-transporte")
    assert processo.returncode == 0, processo.stdout
    assert "1 frase(s) de transporte em 1 arquivo(s)." in processo.stdout, processo.stdout
    assert FRASE_SOLTA in processo.stdout, processo.stdout
