"""O OITAVO CONFLITO de 04/09/2026 — a proibição olhava o lugar errado."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    FRASES_BANIDAS,
    frase_banida_em,
)
from tests.conftest import skip_sem_gi_real

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

PASTAS_DE_FONTE = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions",
    INTERFACE,
)

ISENTOS_INTEIROS: dict[str, str] = {
    "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py": (
        "é o dono da lista: os trechos são o dado, não a frase"
    ),
}

ISENTOS_EM_COMENTARIO: dict[str, str] = {}


def _ocorrencias_no_fonte(
    frases: tuple[str, ...] = FRASES_BANIDAS,
    isentos_inteiros: dict[str, str] | None = None,
    isentos_em_comentario: dict[str, str] | None = None,
) -> list[str]:
    """Toda ocorrência de ``frases`` no fonte das pastas que escrevem tela."""
    isentos_inteiros = (
        ISENTOS_INTEIROS if isentos_inteiros is None else isentos_inteiros
    )
    isentos_em_comentario = (
        ISENTOS_EM_COMENTARIO
        if isentos_em_comentario is None
        else isentos_em_comentario
    )

    def achada_em(texto: str) -> str | None:
        for frase in frases:
            if frase in texto:
                return frase
        return None

    achados: list[str] = []
    for pasta in PASTAS_DE_FONTE:
        for fonte in sorted(pasta.rglob("*.py")):
            rel = fonte.relative_to(RAIZ).as_posix()
            if rel in isentos_inteiros:
                continue
            texto = fonte.read_text(encoding="utf-8")
            for no in ast.walk(ast.parse(texto, filename=str(fonte))):
                if isinstance(no, ast.Constant) and isinstance(no.value, str):
                    frase = achada_em(no.value)
                    if frase:
                        achados.append(f"{rel}:{no.lineno} literal {frase!r}")
            if rel in isentos_em_comentario:
                continue
            fita = tokenize.generate_tokens(io.StringIO(texto).readline)
            for tok in fita:
                if tok.type == tokenize.COMMENT:
                    frase = achada_em(tok.string)
                    if frase:
                        achados.append(
                            f"{rel}:{tok.start[0]} comentário {frase!r}"
                        )
    return sorted(achados)


def test_a_lista_tem_as_quatro_e_a_busca_e_por_substring() -> None:
    """As três de 04/09 continuam banidas, e a quarta entrou em 24/09/2026."""
    assert set(FRASES_BANIDAS) == {
        "derrubam o controle",
        "resultado é ZERO",
        "gatilhos ficam duros",
        "foram renumerados",
    }
    assert frase_banida_em("Alguns jogos derrubam o controle no meio") == (
        "derrubam o controle"
    )
    assert frase_banida_em("Modo Nativo ligado · Ponte com o jogo desligada") is None


@skip_sem_gi_real
def test_o_funil_de_execucao_denuncia_a_frase_e_nao_mata_a_janela(capsys) -> None:
    """O caminho de RUNTIME DENUNCIA e pinta — 13/09/2026."""
    import sys

    sys.path.insert(0, str(INTERFACE))
    import hefesto_vivo as hv

    hv._BANIDAS_JA_DENUNCIADAS.clear()
    assert hv._json({"mesa": {"aviso-texto": ["tudo certo"]}})
    capsys.readouterr()
    saida = hv._json({"colunas": {"aviso-texto": ["Alguns jogos derrubam o controle"]}})
    assert "derrubam o controle" in saida
    assert "derrubam o controle" in capsys.readouterr().err


def test_a_trava_da_pintura_so_sobe_depois_da_carga_serializada() -> None:
    """A outra metade do congelamento: a ORDEM dentro do `_tique`."""
    arvore = ast.parse((INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8"))
    sobe: list[int] = []
    serializa: list[int] = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.FunctionDef) and no.name == "_tique"):
            continue
        sobe = [n.lineno for n in ast.walk(no)
                if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Constant) and n.value.value is True
                and any(isinstance(t, ast.Attribute) and t.attr == "_pintura_no_ar"
                        for t in n.targets)]
        serializa = [n.lineno for n in ast.walk(no)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                     and n.func.id == "_json"]
        if sobe:
            break
    assert sobe and serializa, (
        "o `_tique` perdeu a trava ou o `_json` — a régua mediria o nada")
    assert max(serializa) < min(sobe), (
        f"a trava sobe na linha {min(sobe)} e a carga serializa na "
        f"{max(serializa)}: uma falha ao serializar congela a janela")


def test_a_guarda_estatica_continua_de_pe_e_le_a_lista() -> None:
    """E ela não pode voltar a DIGITAR a lista — foi assim que divergiu."""
    fonte = (INTERFACE / "aba01.py").read_text(encoding="utf-8")
    assert "for frase in FRASES_BANIDAS:" in fonte, (
        "o `_conferir` voltou a digitar as frases; com duas cópias, uma "
        "quarta frase banida entraria só numa delas."
    )
    for frase in FRASES_BANIDAS:
        assert re.search(rf'"{re.escape(frase)}"[,)]', fonte) is None, (
            f"a frase {frase!r} está DIGITADA em aba01.py — a lista é uma só."
        )


def test_nenhuma_aba_publicada_carrega_a_frase() -> None:
    """E o estático de verdade: as dez páginas do produto e as dez do mockup."""
    sujas = []
    for pasta in (INTERFACE / "paginas", RAIZ / "mockup"):  # (noqa-acento) diretório
        for pagina in sorted(pasta.glob("*.html")):
            achada = frase_banida_em(pagina.read_text(encoding="utf-8"))
            if achada:
                sujas.append(f"{pagina.relative_to(RAIZ)}: {achada!r}")
    assert not sujas, "frase banida numa página:\n  " + "\n  ".join(sujas)


def test_nenhuma_banida_vive_no_fonte() -> None:
    """A frase não pode EXISTIR nas pastas que escrevem tela."""
    achados = _ocorrencias_no_fonte()
    assert not achados, (
        "frase banida VIVA no fonte — NENHUM ALARME SEM MEDIÇÃO:\n  "
        + "\n  ".join(achados)
        + "\n\nAs duas isenções são declaradas no topo deste arquivo, com a "
        "razão de cada uma. Uma terceira precisa da palavra dela."
    )


def test_a_guarda_do_fonte_reprova_o_dono_da_lista_sem_a_isencao() -> None:
    """A MORDIDA da guarda nova, e ela é feita, não afirmada."""
    sem_isencao = _ocorrencias_no_fonte(isentos_inteiros={})
    dono = [a for a in sem_isencao if a.startswith(
        "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py:")]
    achadas = {a.split(" literal ")[1] for a in dono if " literal " in a}
    assert achadas == {repr(f) for f in FRASES_BANIDAS}, (
        f"sem a isenção a régua achou {sorted(achadas)} como literal no dono "
        f"da lista, e a lista tem {list(FRASES_BANIDAS)}. Se ela não acha nem "
        f"o dono, ela não está lendo os literais de ninguém.\n  "
        + "\n  ".join(dono)
    )


FRASE_VIVA_ATE_06_09 = (
    "Só para jogos feitos para o PlayStation 5: os gatilhos ficam duros de "
    "apertar, como no PS5. Alguns jogos derrubam o controle no meio da "
    "partida neste modo — se acontecer, volte para \"Jogar pelo Hefesto\"."
)

FRASE_DO_GERADOR = "os gatilhos ficam duros como no PS5."


def test_o_buraco_do_terceiro_trecho_estava_aberto_e_fechou() -> None:
    """A MORDIDA do passo 3, e ela mede o buraco em vez de contá-lo."""
    lista_velha = ("derrubam o controle", "resultado é ZERO", "duros como no PS5")

    def busca(frases: tuple[str, ...], texto: str) -> str | None:
        return next((f for f in frases if f in texto), None)

    assert busca(("duros como no PS5",), FRASE_VIVA_ATE_06_09) is None, (
        "o trecho velho casava com a frase viva — então não havia buraco, e a "
        "razão do passo 3 cai junto."
    )
    assert busca(("duros como no PS5",), FRASE_DO_GERADOR) == "duros como no PS5"

    novo = FRASES_BANIDAS[2]
    assert novo == "gatilhos ficam duros"
    assert busca((novo,), FRASE_VIVA_ATE_06_09) == novo
    assert busca((novo,), FRASE_DO_GERADOR) == novo

    assert busca(lista_velha, FRASE_VIVA_ATE_06_09) == "derrubam o controle"
    metade_que_sobra = FRASE_VIVA_ATE_06_09.split(". Alguns")[0] + "."
    assert busca(lista_velha, metade_que_sobra) is None, (
        "sem a segunda metade, a lista velha ficava CEGA sobre a frase viva — "
        "e é exatamente o estado em que um agente cumpriria a decisão [01] com "
        "a régua verde."
    )
    assert busca(FRASES_BANIDAS, metade_que_sobra) == "gatilhos ficam duros"


@skip_sem_gi_real
def test_o_trecho_curto_que_a_sprint_propunha_pegaria_frase_inocente() -> None:
    """POR QUE NÃO ``"como no PS5"``, que era o proposto — e é medição, não gosto."""
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        DICA_MIC_NO_RADIO,
    )

    assert "como no PS5" in DICA_MIC_NO_RADIO, (
        "a dica do microfone mudou de texto — remeça esta escolha antes de "
        "encurtar o trecho, porque a razão dela era ESTA frase."
    )
    assert frase_banida_em(DICA_MIC_NO_RADIO) is None, (
        "a lista de banidas passou a pegar a dica do microfone, que é frase "
        "medida: o funil de execução vai recusá-la a caminho da tela."
    )
    assert "gatilhos ficam duros" not in DICA_MIC_NO_RADIO
