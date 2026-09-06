"""O OITAVO CONFLITO de 04/09/2026 — a proibição olhava o lugar errado.

Ela, 31/08/2026, sobre o aviso do Modo Nativo: *"qualquer coisa fora isso tá
incorreta"*. A regra que sobrou é **NENHUM ALARME SEM MEDIÇÃO**: as três frases
banidas alarmavam sobre número que ensaio nenhum deste repositório mede.

A PROIBIÇÃO EXISTIA, E MESMO ASSIM O CAMINHO ESTAVA ABERTO. Ela vivia dentro de
`aba01._conferir`, que lê o **HTML ESTÁTICO** da página gerada. A coluna Atenção
é escrita em **tempo de execução**, pelo `_json` do piloto. Um agente cumprindo
a decisão [01] ao pé da letra (*"o aviso do Modo Nativo na coluna Atenção"*)
poria a frase na tela dela **com o gerador VERDE** — e foi a frente da aba 01
que viu isso e RECUSOU escrever, em vez de cumprir a decisão e passar o portão.

É a mesma família dos sete conflitos do `O-PO-DECIDE`, e a decisão de PO é a
mesma: **a decisão dela de 31/08 vence a recomendação de 04/09**. A coluna
Atenção pode dizer o ESTADO MEDIDO; não pode profetizar consequência.

Esta régua tem as três metades que faltavam:
  1. a lista mora em UM lugar e as duas guardas a LEEM;
  2. a guarda de EXECUÇÃO existe e recusa;
  3. a guarda estática continua de pé.

**A TERCEIRA GUARDA ENTROU EM 06/09/2026 (ONDA5-01-02), e as duas de cima
paravam a frase na SAÍDA.** Faltava a que a impede de EXISTIR: as duas outras
leem o HTML gerado e o valor a caminho do WebView, e nenhuma delas lê o FONTE de
onde a frase vem. Foi por esse buraco que *"Alguns jogos derrubam o controle no
meio da partida"* sobreviveu uma semana em `app/actions/home_actions.py`, com as
duas guardas verdes — presa no lugar por uma lápide desta casa.

E ELA ACHOU UM SEGUNDO BURACO, este na própria lista: a comparação é por
substring literal, e o terceiro trecho (``"duros como no PS5"``) não casava com
a variante que o produto escrevia (*"duros de apertar, como no PS5"*). Um terço
da proibição era decorativo desde o primeiro dia. Ver
`test_o_buraco_do_terceiro_trecho_estava_aberto_e_fechou`.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    FRASES_BANIDAS,
    frase_banida_em,
)

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

#: ONDE A FRASE PODE NASCER. São as duas pastas que escrevem texto de tela: a
#: interface nova e o MOTOR que ela chama (`app/actions/`, que a janela antiga
#: também lê). `daemon/` e `integrations/` ficam de fora de propósito — eles
#: não escrevem frase para pessoa, e `integrations/ponte_escada.py` carrega
#: *"resultado é ZERO controles"* como fato MEDIDO em 06/08, num campo `porque`
#: de degrau que a tela não publica.
PASTAS_DE_FONTE = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions",
    INTERFACE,
)

#: ISENÇÃO 1 — o arquivo inteiro, e é o DONO da lista. Os trechos ali são o
#: DADO da proibição, não texto de tela; sem esta linha a régua reprovaria a
#: própria fonte que consulta.
ISENTOS_INTEIROS: dict[str, str] = {
    "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py": (
        "é o dono da lista: os trechos são o dado, não a frase"
    ),
}

#: ISENÇÃO 2 — só os COMENTÁRIOS deste arquivo, e a razão é a lápide. O
#: `INTERRUPTOR` do `aba01.py` guarda, em comentário, POR QUE as duas metades
#: caíram em 31/08. Esta casa não apaga decisão medida; e comentário não chega
#: a tela nenhuma. **A isenção é dos comentários, não do arquivo**: um literal
#: banido em `aba01.py` continua reprovando, que é o que a guarda estática já
#: cobra por outro caminho.
ISENTOS_EM_COMENTARIO: dict[str, str] = {
    "src/hefesto_dualsense4unix/interface/aba01.py": (
        "a lápide do INTERRUPTOR conta por que as duas metades saíram em 31/08"
    ),
}


def _ocorrencias_no_fonte(
    frases: tuple[str, ...] = FRASES_BANIDAS,
    isentos_inteiros: dict[str, str] | None = None,
    isentos_em_comentario: dict[str, str] | None = None,
) -> list[str]:
    """Toda ocorrência de ``frases`` no fonte das pastas que escrevem tela.

    OS DOIS CANAIS SÃO LIDOS SEPARADAMENTE, e não por texto cru, porque cada um
    engana de um jeito:

    * **os literais, pelo `ast`** — a frase viva estava PARTIDA em duas linhas
      do fonte (``"…duros de "`` / ``"apertar, como no PS5…"``), e um `grep` no
      texto cru não a via inteira. O parser junta a concatenação implícita antes
      de a régua olhar, então a quebra de linha deixa de ser esconderijo;
    * **os comentários, pelo `tokenize`** — é onde a lápide legítima mora, e é
      por isso que a isenção 2 precisa existir.

    Os parâmetros existem para a MORDIDA: as duas isenções e a própria lista
    entram por argumento, então o teste PROVA que tirá-las reprova, em vez de
    afirmar que reprovaria.
    """
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


def test_a_lista_tem_as_tres_e_a_busca_e_por_substring() -> None:
    """As três continuam banidas — o terceiro trecho é que passou a alcançar.

    **MUDOU EM 06/09/2026:** ``"duros como no PS5"`` virou
    ``"gatilhos ficam duros"``. Não é uma quarta frase nem uma a menos: é o
    MESMO alarme, escrito curto o bastante para casar com as duas grafias que
    esta casa já teve. A razão medida está no `frases_que_ela_baniu`.
    """
    assert set(FRASES_BANIDAS) == {
        "derrubam o controle",
        "resultado é ZERO",
        "gatilhos ficam duros",
    }
    assert frase_banida_em("Alguns jogos derrubam o controle no meio") == (
        "derrubam o controle"
    )
    assert frase_banida_em("Modo Nativo ligado · Ponte com o jogo desligada") is None


def test_o_funil_de_execucao_recusa_a_frase() -> None:
    """A METADE QUE FALTAVA: o caminho de RUNTIME, não o HTML estático."""
    import sys

    sys.path.insert(0, str(INTERFACE))
    import hefesto_vivo as hv

    assert hv._json({"mesa": {"aviso-texto": ["tudo certo"]}})
    with pytest.raises(ValueError) as erro:
        hv._json({"colunas": {"aviso-texto": ["Alguns jogos derrubam o controle"]}})
    assert "derrubam o controle" in str(erro.value)
    assert "NENHUM ALARME SEM MEDIÇÃO" in str(erro.value)


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


# ---------------------------------------------------------------------------
# A TERCEIRA GUARDA — a que lê o FONTE, e não a saída (ONDA5-01-02, 06/09/2026)
# ---------------------------------------------------------------------------
def test_nenhuma_banida_vive_no_fonte() -> None:
    """A frase não pode EXISTIR nas pastas que escrevem tela.

    AS DUAS GUARDAS DE CIMA PARAM A FRASE NA SAÍDA: a estática lê o HTML já
    gerado, a de execução lê o valor a caminho do WebView. Nenhuma das duas
    olha de onde a frase vem — e por isso *"Alguns jogos derrubam o controle no
    meio da partida"* viveu uma semana em `app/actions/home_actions.py` com as
    duas verdes, presa ali por uma lápide desta casa que exigia que ela ficasse.

    **Três réguas independentes é o desenho desta casa**, o mesmo dos dois
    portões de endereço de rádio: esta entra AO LADO das outras, não no lugar.

    A MORDIDA (passo 1 da sprint): devolva qualquer uma das duas metades ao
    `_MODE_DESCRIPTIONS["native"]` e este teste reprova nomeando arquivo, linha
    e canal.
    """
    achados = _ocorrencias_no_fonte()
    assert not achados, (
        "frase banida VIVA no fonte — NENHUM ALARME SEM MEDIÇÃO:\n  "
        + "\n  ".join(achados)
        + "\n\nAs duas isenções são declaradas no topo deste arquivo, com a "
        "razão de cada uma. Uma terceira precisa da palavra dela."
    )


def test_a_guarda_do_fonte_reprova_o_dono_da_lista_sem_a_isencao() -> None:
    """A MORDIDA da guarda nova, e ela é feita, não afirmada.

    Tire a isenção do `frases_que_ela_baniu.py` e a régua tem de reprovar o
    PRÓPRIO DONO da lista — que é o sinal de que ela está lendo mesmo, e não
    passando por cima das pastas em silêncio.
    """
    sem_isencao = _ocorrencias_no_fonte(isentos_inteiros={})
    dono = [a for a in sem_isencao if a.startswith(
        "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py:")]
    # A CONTAGEM NÃO SERVE DE RÉGUA AQUI, e foi assim que este teste reprovou
    # na primeira volta: o arquivo cita as frases na prosa que explica por que
    # elas caíram, então há mais ocorrências que trechos. O que prova a leitura
    # é cada um dos TRÊS aparecer como LITERAL — que é a tupla em si.
    achadas = {a.split(" literal ")[1] for a in dono if " literal " in a}
    assert achadas == {repr(f) for f in FRASES_BANIDAS}, (
        f"sem a isenção a régua achou {sorted(achadas)} como literal no dono "
        f"da lista, e a lista tem {list(FRASES_BANIDAS)}. Se ela não acha nem "
        f"o dono, ela não está lendo os literais de ninguém.\n  "
        + "\n  ".join(dono)
    )


def test_a_guarda_do_fonte_reprova_a_lapide_do_aba01_sem_a_isencao() -> None:
    """E a segunda isenção também é PROVADA, não declarada de graça.

    O comentário de `aba01.py` guarda as duas metades que caíram em 31/08. Sem
    a isenção, a régua o acha — o que prova as duas coisas de uma vez: que o
    canal dos COMENTÁRIOS é lido, e que a isenção não é decorativa.
    """
    sem_isencao = _ocorrencias_no_fonte(isentos_em_comentario={})
    lapide = [a for a in sem_isencao
              if a.startswith("src/hefesto_dualsense4unix/interface/aba01.py:")
              and "comentário" in a]
    assert lapide, (
        "sem a isenção a régua não achou a lápide de `aba01.py` — o canal dos "
        "comentários parou de ser lido, e uma frase banida escrita em "
        "comentário passaria por baixo dela."
    )


# ---------------------------------------------------------------------------
# O BURACO DO TERCEIRO TRECHO — medido, e é a razão de ele ter mudado
# ---------------------------------------------------------------------------
#: A frase VIVA da janela antiga até 06/09/2026, palavra por palavra
#: (`app/actions/home_actions.py`, `_MODE_DESCRIPTIONS["native"]`). Ela mora
#: aqui, num texto de TESTE, porque é o corpo de delito: a lista de banidas
#: passava por cima dela.
FRASE_VIVA_ATE_06_09 = (
    "Só para jogos feitos para o PlayStation 5: os gatilhos ficam duros de "
    "apertar, como no PS5. Alguns jogos derrubam o controle no meio da "
    "partida neste modo — se acontecer, volte para \"Jogar pelo Hefesto\"."
)

#: A grafia que o gerador da interface nova cita, e contra a qual a lista foi
#: escrita em 04/09 (`interface/aba01.py`, o comentário do `INTERRUPTOR`).
FRASE_DO_GERADOR = "os gatilhos ficam duros como no PS5."


def test_o_buraco_do_terceiro_trecho_estava_aberto_e_fechou() -> None:
    """A MORDIDA do passo 3, e ela mede o buraco em vez de contá-lo.

    A lista de 04/09 tinha ``"duros como no PS5"``: a grafia do GERADOR. O
    produto escrevia ``"duros de apertar, como no PS5"`` — a vírgula no meio —,
    e a comparação é por substring literal, sem normalizar. Logo **um terço da
    proibição nunca teve objeto**.

    Aqui a lista velha é remontada e passada pela busca. Se ela achasse a frase
    viva, este teste reprovaria — e o passo 3 seria trabalho inventado.
    """
    lista_velha = ("derrubam o controle", "resultado é ZERO", "duros como no PS5")

    def busca(frases: tuple[str, ...], texto: str) -> str | None:
        return next((f for f in frases if f in texto), None)

    # O BURACO ERA REAL: o terceiro trecho velho não via a frase viva...
    assert busca(("duros como no PS5",), FRASE_VIVA_ATE_06_09) is None, (
        "o trecho velho casava com a frase viva — então não havia buraco, e a "
        "razão do passo 3 cai junto."
    )
    # ...e via a do gerador, que é contra o que ele foi escrito.
    assert busca(("duros como no PS5",), FRASE_DO_GERADOR) == "duros como no PS5"

    # O BURACO FECHOU: o trecho de hoje casa com as DUAS grafias. A pergunta é
    # feita ao TERCEIRO trecho sozinho de propósito — a frase viva também
    # carrega a primeira metade, e perguntar à lista inteira devolveria
    # "derrubam o controle" e esconderia de novo qual metade está acendendo.
    # Foi exatamente esse acaso que deixou o buraco invisível por dois dias.
    novo = FRASES_BANIDAS[2]
    assert novo == "gatilhos ficam duros"
    assert busca((novo,), FRASE_VIVA_ATE_06_09) == novo
    assert busca((novo,), FRASE_DO_GERADOR) == novo

    # E A LISTA VELHA INTEIRA ainda pegaria a frase viva pela PRIMEIRA metade —
    # é isso que fazia o buraco passar despercebido: com as duas metades juntas
    # a régua acendia, e ninguém via que era só uma delas acendendo.
    assert busca(lista_velha, FRASE_VIVA_ATE_06_09) == "derrubam o controle"
    metade_que_sobra = FRASE_VIVA_ATE_06_09.split(". Alguns")[0] + "."
    assert busca(lista_velha, metade_que_sobra) is None, (
        "sem a segunda metade, a lista velha ficava CEGA sobre a frase viva — "
        "e é exatamente o estado em que um agente cumpriria a decisão [01] com "
        "a régua verde."
    )
    assert busca(FRASES_BANIDAS, metade_que_sobra) == "gatilhos ficam duros"


def test_o_trecho_curto_que_a_sprint_propunha_pegaria_frase_inocente() -> None:
    """POR QUE NÃO ``"como no PS5"``, que era o proposto — e é medição, não gosto.

    A sprint pedia o trecho ``"como no PS5"``, mais curto ainda. Ele casa com
    as duas grafias, e casa também com uma frase MEDIDA e VIVA: a dica do
    microfone pelo rádio, em `app/actions/config/secao_controles.py`.

    Duas consequências, e a segunda é a grave: a guarda de fonte reprovaria um
    arquivo inocente, e o **funil de execução recusaria a dica a caminho do
    WebView**. A régua contra o alarme sem medição viraria ela mesma um alarme
    sem medição — que é o defeito que este módulo inteiro existe para matar.
    """
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
    # E o trecho de hoje continua sabendo o que tem de saber.
    assert "gatilhos ficam duros" not in DICA_MIC_NO_RADIO
