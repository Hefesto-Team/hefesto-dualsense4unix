"""Verificador SEMÂNTICO dos perfis — o que o schema aceita mas machuca.

PERFIL-NASCE-CERTO-01, entrega 4 ("Um detector de armadilha, rodando sozinho"),
que nunca foi feita. O `Profile` do pydantic responde uma pergunta só: *este
JSON tem os campos certos?* Todo arranjo que quebrou a máquina dela passou por
essa validação sem um arranhão — um ``{"type": "any"}`` é um match perfeitamente
válido, e ``priority: 191`` é um inteiro perfeitamente válido. O que falta é a
pergunta seguinte: *este CONJUNTO de perfis se comporta como ela espera?*

Cada regra daqui tem um caso REAL no disco dela (medido em 04/08/2026):

- ``vitoria`` (catch-all, prioridade 100) vencendo ``pragmata``, o perfil do
  jogo — o defeito que abriu a sprint;
- ``pragmata`` com ``match`` de jogo trocado por ``{"type": "any"}`` pela
  janela — perdeu a regra e virou catch-all;
- prioridades escalando até 191, e empatando entre si;
- quatro catch-all no mesmo diretório disputando a mesma vaga.

Duas decisões de projeto, ambas contra o alarme que se aprende a ignorar:

1. **``fallback`` é catch-all LEGÍTIMO** e tem dispensa NOMEADA
   (`CATCH_ALL_LEGITIMOS`). Um perfil que existe para valer quando nada mais
   vale não pode ser acusado de existir. A dispensa vale enquanto ele estiver
   no piso da escala — um "fallback" que SOBE deixa de ser fundo e passa a
   competir, e aí é exatamente o defeito que se quer ver.
2. **Todo achado diz o que FAZER.** "Está errado" sem "faça isto" transfere o
   trabalho para quem menos pode fazê-lo.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from hefesto_dualsense4unix.profiles.schema import (
    PRIORIDADE_MAXIMA,
    PRIORIDADE_MINIMA,
    MatchManual,
    Profile,
)
from hefesto_dualsense4unix.profiles.slug import slugify

# PRIORIDADE_MINIMA / PRIORIDADE_MAXIMA: a faixa que a JANELA oferece no
# controle de prioridade. Um número fora dela NÃO veio da janela — veio de
# edição à mão ou de algo somando sozinho, e é essa a informação que o achado
# `prioridade_fora_da_faixa` entrega. Reexportadas no `__all__` deste módulo
# porque fazem parte do vocabulário público do verificador.
#
# NOTA DE 05/08/2026 (UNIFICA-CONSTANTE-01). Até aqui as duas eram cópia
# DELIBERADA dos números de `app/actions/profiles_actions.py`, com a
# justificativa: *"repetida aqui de propósito, e não importada: `profiles/` não
# pode depender de `app/` (a GUI importa o loader, nunca o contrário), e o CLI
# carregaria GTK atrás dela."* **Essa justificativa continua CERTA e continua
# valendo** — nada aqui importa `app/`, e nenhum caminho de CLI carrega GTK. O
# que caducou foi só a conclusão de que a cópia era a única saída: a constante
# DESCEU para `profiles/schema.py` (stdlib + pydantic), em vez de subir para
# `app/`. `profiles/` continua sem depender de `app/`, e agora existe um número
# só, com portão (`tests/unit/test_teto_da_prioridade_tem_uma_fonte_so.py`).

#: Catch-all com dispensa nomeada (ver docstring do módulo). Comparado por
#: SLUG, então "Fallback" e "fallback" são o mesmo perfil.
CATCH_ALL_LEGITIMOS: frozenset[str] = frozenset({"fallback"})

#: A dispensa do `fallback` vale só no PISO da escala. Acima disso ele deixou
#: de ser fundo de escala e passou a disputar — foi assim que a corrupção
#: apareceu (prioridades subindo sozinhas até 191).
PRIORIDADE_DE_FUNDO = 0

#: Quantos catch-all SEM dispensa o diretório tolera. Um é o "perfil de
#: desktop" de quem não quer regra nenhuma; a partir do segundo eles disputam
#: entre si por prioridade, e quem chega ao controle vira sorteio.
MAX_CATCH_ALL_TOLERADOS = 1

#: Vocabulário de perfil GENÉRICO — nomes que dizem "vale para tudo" e por isso
#: não levantam suspeita de serem um jogo que perdeu a regra. Fora desta lista,
#: um catch-all com nome próprio é o padrão exato do `pragmata`: alguém criou
#: para UM programa e o `match` foi embora.
VOCABULARIO_GENERICO: frozenset[str] = frozenset(
    {
        "fallback",
        "padrao",  # (noqa-acento): slug, sempre ASCII
        "default",
        "geral",
        "generico",
        "tudo",
        "todos",
        "desktop",
        "navegacao",
        "trabalho",
        "escritorio",
        "leitura",
        "video",
        "filme",
        "musica",  # (noqa-acento): slug, sempre ASCII
        "meu_perfil",  # nome antigo do padrão, ainda vivo em disco velho
        "personalizado",  # o nome do padrão de 05/09 a 24/09/2026
        "freestyle",  # o padrão desde 24/09/2026 (O-MODO-FREESTYLE-02)
        "perfil_padrao",
        "teste",
    }
)


@dataclass(frozen=True)
class Achado:
    """Um problema semântico, com o conserto junto.

    `gravidade` é ``"erro"`` (configuração que já está machucando hoje) ou
    ``"aviso"`` (armadilha armada, ainda sem vítima).
    """

    regra: str
    gravidade: str
    mensagem: str
    cura: str
    perfis: tuple[str, ...] = field(default=())

    def linha(self) -> str:
        """Uma linha de terminal: o problema e o que fazer, nesta ordem.

        O rótulo "Cura:" não é enfeite — várias mensagens já contêm um
        travessão, e sem ele os dois textos viram um parágrafo só na tela.
        """
        return f"{self.mensagem} — Cura: {self.cura}"


def _slug(profile: Profile) -> str:
    try:
        return slugify(profile.name)
    except ValueError:  # pragma: no cover — o schema já recusa nome sem slug
        return profile.name.strip().lower()


def _e_catch_all(profile: Profile) -> bool:
    """Catch-all pelo predicado do próprio schema (`MatchAny` ou criteria vazio)."""
    return bool(profile.e_catch_all)


def _e_manual(profile: Profile) -> bool:
    """Perfil só-manual: nunca é candidato do autoswitch, nunca disputa."""
    return isinstance(profile.match, MatchManual)


def _tem_dispensa(profile: Profile) -> bool:
    """True para o catch-all legítimo AINDA no fundo da escala.

    A dispensa é do arranjo, não do nome: `fallback` em 0 é o fundo que o
    projeto recomenda; `fallback` em 100 é um competidor com nome de fundo, e
    justamente o que a corrupção produziu.
    """
    return (
        _slug(profile) in CATCH_ALL_LEGITIMOS
        and profile.priority <= PRIORIDADE_DE_FUNDO
    )


def _catch_all_vence_especifico(perfis: Sequence[Profile]) -> list[Achado]:
    """PERFIL-NASCE-CERTO-01/E4: catch-all com prioridade >= a de um específico.

    É a armadilha que abriu a sprint: `vitoria` (any, 100) tem prioridade maior
    que `pragmata` (o perfil do jogo), então abrir o jogo entrega o perfil de
    desktop. Empate conta — no empate o desempate é acidental (ordem de leitura
    do diretório), e "às vezes vale o certo" é pior de diagnosticar do que
    "nunca vale".
    """
    catch_all = [p for p in perfis if _e_catch_all(p) and not _tem_dispensa(p)]
    especificos = [
        p for p in perfis if not _e_catch_all(p) and not _e_manual(p)
    ]
    achados: list[Achado] = []
    for coringa in catch_all:
        perdedores = [e for e in especificos if e.priority <= coringa.priority]
        if not perdedores:
            continue
        nomes = ", ".join(sorted(f"{e.name} ({e.priority})" for e in perdedores))
        achados.append(
            Achado(
                regra="catch_all_vence_especifico",
                gravidade="erro",
                mensagem=(
                    f"'{coringa.name}' vale para QUALQUER janela e está em "
                    f"prioridade {coringa.priority} — igual ou acima de perfis "
                    f"que têm alvo próprio: {nomes}"
                ),
                cura=(
                    f"baixe a prioridade de '{coringa.name}' para 0 (é o fundo "
                    "de escala, o lugar de quem vale quando nada mais vale), ou "
                    "dê um alvo a ele na aba Perfis"
                ),
                perfis=(coringa.name, *sorted(e.name for e in perdedores)),
            )
        )
    return achados


def _catch_all_com_cara_de_jogo(perfis: Sequence[Profile]) -> list[Achado]:
    """Perfil com nome de jogo (ou modo de jogo) e ``match.type == "any"``.

    Dois sinais, e basta um:

    - **declarado**: o perfil pede modo ``gamepad`` ou suprime a emulação de
      desktop — ele SABE que é de jogo, e mesmo assim casa com tudo;
    - **pelo nome**: o nome está fora do `VOCABULARIO_GENERICO`, isto é, é nome
      próprio. Foi o caso do `pragmata`: criado para um jogo, com o `match`
      perdido depois.

    A heurística de nome é declaradamente heurística — por isso a gravidade é
    "aviso" e a cura diz como silenciá-la de propósito (``manual``).
    """
    achados: list[Achado] = []
    for p in perfis:
        if not _e_catch_all(p) or _tem_dispensa(p):
            continue
        modo = getattr(p, "mode", None)
        declarado = bool(p.suppress_desktop_emulation) or bool(
            modo is not None and getattr(modo, "kind", None) == "gamepad"
        )
        # O sinal de NOME só vale acima do fundo da escala, e a razão é o
        # direito de silenciar: um catch-all parado na prioridade 0 se comporta
        # como fundo de escala qualquer que seja o nome dele — só entra quando
        # nada mais entrou, e não tira a vez de ninguém. Sem esta condição, o
        # perfil de desktop com nome próprio (o caso dela) receberia um aviso
        # perpétuo que nenhuma ação dela apagaria, e o alarme inteiro perderia
        # o crédito. O sinal DECLARADO não tem essa folga: um perfil que pede
        # modo de jogo casando com tudo empurra o modo no desktop mesmo em 0.
        nome_proprio = (
            _slug(p) not in VOCABULARIO_GENERICO and p.priority > PRIORIDADE_DE_FUNDO
        )
        if not (declarado or nome_proprio):
            continue
        if declarado:
            motivo = "ele pede modo de jogo (gamepad/supressão de desktop)"
            cura = (
                f"abra a aba Perfis com o jogo aberto e dê o alvo de volta a "
                f"'{p.name}'; se ele é mesmo só para ativar na mão, declare "
                '`"match": {"type": "manual"}` e o aviso some'
            )
        else:
            motivo = "o nome dele é de um programa, não de um perfil genérico"
            cura = (
                f"se '{p.name}' é o perfil de um programa, abra a aba Perfis "
                "com ele aberto e dê o alvo de volta; se é o seu perfil de "
                f"desktop, o lugar dele é a prioridade 0 (hoje está em "
                f"{p.priority}), e ali o aviso some"
            )
        achados.append(
            Achado(
                regra="catch_all_com_cara_de_jogo",
                gravidade="aviso",
                mensagem=(
                    f"'{p.name}' casa com QUALQUER janela, mas {motivo} — "
                    "é o retrato de um perfil que PERDEU a regra dele"
                ),
                cura=cura,
                perfis=(p.name,),
            )
        )
    return achados


def _alvos(perfil: Profile) -> tuple[frozenset[str], frozenset[str], bool] | None:
    """Os endereços de janela de um perfil: `(classes, processos, tem_regex)`.

    ``None`` para quem não casa por critério (manual, catch-all) — esses têm
    regras próprias neste arquivo e não entram na conta de empate.

    A caixa é ignorada porque o produto a ignora: `MatchCriteria.matches` casa
    com `re.IGNORECASE` e `_casa_sem_caixa`. Uma régua com regra de caixa
    diferente da do produto responde sobre outra coisa — que é o defeito que
    esta casa mais caçou.
    """
    match = perfil.match
    classes = getattr(match, "window_class", None)
    processos = getattr(match, "process_name", None)
    if classes is None and processos is None:
        return None
    regex = getattr(match, "window_title_regex", None)
    return (
        frozenset(c.casefold() for c in (classes or [])),
        frozenset(p.casefold() for p in (processos or [])),
        bool(regex),
    )


def _podem_disputar(a: Profile, b: Profile) -> bool:
    """Existe alguma janela do mundo que case com os DOIS?

    A resposta é conservadora de propósito: só devolve ``False`` quando é
    IMPOSSÍVEL colidirem. `MatchCriteria` é AND entre os campos preenchidos e
    OR dentro de cada lista — então basta um campo preenchido nos dois **sem
    interseção** para que nenhuma janela case com ambos. O `window_title_regex`
    nunca prova impossibilidade (dois regexes podem casar com o mesmo título),
    e por isso não é usado para calar nada.
    """
    alvo_a, alvo_b = _alvos(a), _alvos(b)
    if alvo_a is None or alvo_b is None:
        return True
    classes_a, processos_a, _ = alvo_a
    classes_b, processos_b, _ = alvo_b
    if classes_a and classes_b and not (classes_a & classes_b):
        return False
    return not (processos_a and processos_b and not (processos_a & processos_b))


def _prioridades_empatadas(perfis: Sequence[Profile]) -> list[Achado]:
    """Perfis que DISPUTAM A MESMA JANELA na mesma prioridade.

    Perfis só-manuais ficam de fora: eles nunca são candidatos do autoswitch,
    então empatar não decide nada.

    E DESDE 21/09/2026 O ALVO ENTRA NA CONTA — antes desta data a regra
    agrupava só por número, e isso a tornava um alarme que o próprio produto
    fabricava. Medido no disco dela naquele dia: **28 dos 29 perfis em
    `priority: 80`**, porque `PRIORIDADE_DO_PERFIL_DE_JOGO = 80` é o que o
    semeador escreve em todo perfil de jogo que ele cria. Os 28 têm
    `window_class` próprio — `steam_app_1088850`, `steam_app_1245620`… — e
    portanto **nenhum par deles podia disputar coisa nenhuma**.

    O preço do alarme falso era duplo: a cura que ele imprimia mandava dar 28
    números diferentes à mão (trabalho sem efeito, e ninguém o faria), e um
    aviso permanente que não tem ação é o que ensina a ignorar os avisos que
    têm. *O produto gerava o empate, avisava sobre ele, e a cura era
    impossível.*

    O QUE NÃO SE FEZ, e é decisão registrada: dar um passo de prioridade ao
    semeador. Perfis de jogo não competem entre si — inventar hierarquia entre
    o Elden Ring e o Stray seria dado novo que ninguém pediu, e um número por
    jogo tem de acabar em algum lugar (`PRIORIDADE_MAXIMA`). O empate entre
    endereços disjuntos não é defeito; é a forma certa.
    """
    disputantes = [p for p in perfis if not _e_manual(p)]
    por_prioridade: dict[int, list[Profile]] = {}
    for p in disputantes:
        por_prioridade.setdefault(p.priority, []).append(p)
    achados: list[Achado] = []
    for prioridade, grupo in sorted(por_prioridade.items()):
        if len(grupo) < 2:
            continue
        # Só entra no achado quem tem PELO MENOS UM par que pode casar com a
        # mesma janela. Um perfil sozinho no grupo, depois deste filtro, não
        # disputa com ninguém.
        em_disputa: set[str] = set()
        for i, um in enumerate(grupo):
            for outro in grupo[i + 1 :]:
                if _podem_disputar(um, outro):
                    em_disputa.add(um.name)
                    em_disputa.add(outro.name)
        if len(em_disputa) < 2:
            continue
        nomes = sorted(em_disputa)
        achados.append(
            Achado(
                regra="prioridades_empatadas",
                gravidade="aviso",
                mensagem=(
                    f"{len(nomes)} perfis empatados na prioridade {prioridade} "
                    "e disputando as mesmas janelas: "
                    + ", ".join(f"'{n}'" for n in nomes)
                ),
                cura=(
                    "dê números diferentes a eles — no empate o perfil que já "
                    "está ativo continua (EMPATE-01), e quando nenhum deles é o "
                    "ativo quem vence é o primeiro da ordem de carga, que é "
                    "alfabética por nome de arquivo e não é critério de ninguém"
                ),
                perfis=tuple(nomes),
            )
        )
    return achados


def _prioridade_fora_da_faixa(perfis: Sequence[Profile]) -> list[Achado]:
    """`priority` fora de 0-200, a faixa que a própria janela oferece.

    Um 191 não sai do slider por acidente, e um 250 não sai dele de jeito
    nenhum. Achado aqui = o número não veio de onde ela pensa que veio.
    """
    achados: list[Achado] = []
    for p in perfis:
        if PRIORIDADE_MINIMA <= p.priority <= PRIORIDADE_MAXIMA:
            continue
        achados.append(
            Achado(
                regra="prioridade_fora_da_faixa",
                gravidade="erro",
                mensagem=(
                    f"'{p.name}' está na prioridade {p.priority}, fora da faixa "
                    f"{PRIORIDADE_MINIMA}-{PRIORIDADE_MAXIMA} que a janela "
                    "oferece — este número NÃO veio do controle de prioridade"
                ),
                cura=(
                    f"reabra '{p.name}' na aba Perfis e escolha a prioridade de "
                    "novo; se você não editou o JSON à mão, confira o histórico "
                    f"com `hefesto-dualsense4unix profile historico {_slug(p)}`"  # (noqa-acento)
                ),
                perfis=(p.name,),
            )
        )
    return achados


def _catch_all_demais(perfis: Sequence[Profile]) -> list[Achado]:
    """Mais de `MAX_CATCH_ALL_TOLERADOS` catch-all sem dispensa no diretório."""
    coringas = [p for p in perfis if _e_catch_all(p) and not _tem_dispensa(p)]
    if len(coringas) <= MAX_CATCH_ALL_TOLERADOS:
        return []
    nomes = sorted(f"{p.name} ({p.priority})" for p in coringas)
    return [
        Achado(
            regra="catch_all_demais",
            gravidade="aviso",
            mensagem=(
                f"{len(coringas)} perfis casam com QUALQUER janela: "
                + ", ".join(nomes)
                + " — eles disputam entre si a mesma vaga"
            ),
            cura=(
                "guarde UM perfil sem alvo (o de desktop, na prioridade 0) e dê "
                "alvo aos demais, ou declare os que só usa na mão com "
                '`"match": {"type": "manual"}`'
            ),
            perfis=tuple(sorted(p.name for p in coringas)),
        )
    ]


#: As regras, na ordem em que aparecem no relatório: primeiro o que já está
#: machucando, depois a armadilha ainda sem vítima.
REGRAS: tuple[Callable[[Sequence[Profile]], list[Achado]], ...] = (
    _catch_all_vence_especifico,
    _prioridade_fora_da_faixa,
    _catch_all_com_cara_de_jogo,
    _prioridades_empatadas,
    _catch_all_demais,
)


def verificar_perfis(perfis: Sequence[Profile]) -> list[Achado]:
    """Roda TODAS as regras sobre um conjunto de perfis já carregados."""
    achados: list[Achado] = []
    for regra in REGRAS:
        achados.extend(regra(perfis))
    return achados


def verificar_perfis_do_disco() -> list[Achado]:
    """Conveniência: carrega o diretório de perfis do XDG e verifica.

    Import local do loader para manter este módulo importável em contexto de
    teste sem tocar disco algum.

    NOTA DATADA — 26/08/2026. Esta função NÃO deve ganhar chamador de produção,
    e a razão substitui a que estava escrita no portão de lápides (que a
    chamava de *"a lacuna mais barata desta lista de fechar — uma chamada"*).
    MEDIDO: o `doctor` já faz o trabalho inteiro, e faz MELHOR —
    `cli/cmd_doctor.py::_linhas_perfis` chama `load_all_profiles()` dentro de um
    `try/except OSError` e só então roda `verificar_perfis` e
    `linhas_de_relatorio`. Esta conveniência **não tem** o `except OSError`:
    fiá-la no doctor trocaria a linha *"não deu para ler os perfis: <erro>"* por
    um traceback na cara de quem foi justamente pedir diagnóstico. Seria piorar
    o produto para fechar uma lápide.
    Ela fica de pé como atalho de teste (é assim que
    `test_regra_nao_se_perde_02_o_nome_novo_nascia_sem_regra.py:319` a usa) — e
    quem precisar da corrente em produção usa as duas metades separadas, como o
    doctor usa.
    """
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles

    return verificar_perfis(load_all_profiles())


def linhas_de_relatorio(
    achados: Sequence[Achado], *, total_perfis: int | None = None
) -> list[tuple[str, str]]:
    """Formata os achados no par ``(tag, mensagem)`` que o doctor imprime.

    Mesma gramática dos outros blocos (`[ OK ]`, `[WARN]`, `[FAIL]`), para a
    saída continuar legível de cima a baixo.
    """
    if not achados:
        quantos = "" if total_perfis is None else f" ({total_perfis} no disco)"
        return [("[ OK ]", f"perfis coerentes entre si{quantos}")]
    linhas: list[tuple[str, str]] = []
    for achado in achados:
        tag = "[FAIL]" if achado.gravidade == "erro" else "[WARN]"
        linhas.append((tag, achado.linha()))
    return linhas


__all__ = [
    "CATCH_ALL_LEGITIMOS",
    "MAX_CATCH_ALL_TOLERADOS",
    "PRIORIDADE_MAXIMA",
    "PRIORIDADE_MINIMA",
    "REGRAS",
    "VOCABULARIO_GENERICO",
    "Achado",
    "linhas_de_relatorio",
    "verificar_perfis",
    "verificar_perfis_do_disco",
]
