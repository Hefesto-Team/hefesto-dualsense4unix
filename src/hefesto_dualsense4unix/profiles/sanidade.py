"""Verificador SEMÂNTICO dos perfis — o que o schema aceita mas machuca."""
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

CATCH_ALL_LEGITIMOS: frozenset[str] = frozenset({"fallback"})

PRIORIDADE_DE_FUNDO = 0

MAX_CATCH_ALL_TOLERADOS = 1

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
        "meu_perfil",
        "personalizado", "freestyle",
        "perfil_padrao",
        "teste",
    }
)


@dataclass(frozen=True)
class Achado:
    """Um problema semântico, com o conserto junto."""

    regra: str
    gravidade: str
    mensagem: str
    cura: str
    perfis: tuple[str, ...] = field(default=())

    def linha(self) -> str:
        """Uma linha de terminal: o problema e o que fazer, nesta ordem."""
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
    """True para o catch-all legítimo AINDA no fundo da escala."""
    return (
        _slug(profile) in CATCH_ALL_LEGITIMOS
        and profile.priority <= PRIORIDADE_DE_FUNDO
    )


def _catch_all_vence_especifico(perfis: Sequence[Profile]) -> list[Achado]:
    """PERFIL-NASCE-CERTO-01/E4: catch-all com prioridade >= a de um específico."""
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
                    f"'{coringa.name}' vale para QUALQUER janela e está na "
                    f"preferência {coringa.priority} — igual ou acima de perfis "
                    f"que têm alvo próprio: {nomes}"
                ),
                cura=(
                    f"baixe a preferência de '{coringa.name}' para 0 (é o fundo "
                    "de escala, o lugar de quem vale quando nada mais vale), ou "
                    "dê um alvo a ele na aba Perfis"
                ),
                perfis=(coringa.name, *sorted(e.name for e in perdedores)),
            )
        )
    return achados


def _catch_all_com_cara_de_jogo(perfis: Sequence[Profile]) -> list[Achado]:
    """Perfil com nome de jogo (ou modo de jogo) e ``match.type == "any"``."""
    achados: list[Achado] = []
    for p in perfis:
        if not _e_catch_all(p) or _tem_dispensa(p):
            continue
        modo = getattr(p, "mode", None)
        declarado = bool(p.suppress_desktop_emulation) or bool(
            modo is not None and getattr(modo, "kind", None) == "gamepad"
        )
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
                f"desktop, o lugar dele é a preferência 0 (hoje está em "
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
    """Os endereços de janela de um perfil: `(classes, processos, tem_regex)`."""
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
    """Existe alguma janela do mundo que case com os DOIS?"""
    alvo_a, alvo_b = _alvos(a), _alvos(b)
    if alvo_a is None or alvo_b is None:
        return True
    classes_a, processos_a, _ = alvo_a
    classes_b, processos_b, _ = alvo_b
    if classes_a and classes_b and not (classes_a & classes_b):
        return False
    return not (processos_a and processos_b and not (processos_a & processos_b))


def _prioridades_empatadas(perfis: Sequence[Profile]) -> list[Achado]:
    """Perfis que DISPUTAM A MESMA JANELA na mesma prioridade."""
    disputantes = [p for p in perfis if not _e_manual(p)]
    por_prioridade: dict[int, list[Profile]] = {}
    for p in disputantes:
        por_prioridade.setdefault(p.priority, []).append(p)
    achados: list[Achado] = []
    for prioridade, grupo in sorted(por_prioridade.items()):
        if len(grupo) < 2:
            continue
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
                    f"{len(nomes)} perfis empatados na preferência {prioridade} "
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
    """`priority` fora de 0-200, a faixa que a própria janela oferece."""
    achados: list[Achado] = []
    for p in perfis:
        if PRIORIDADE_MINIMA <= p.priority <= PRIORIDADE_MAXIMA:
            continue
        achados.append(
            Achado(
                regra="prioridade_fora_da_faixa",
                gravidade="erro",
                mensagem=(
                    f"'{p.name}' está na preferência {p.priority}, fora da faixa "
                    f"{PRIORIDADE_MINIMA}-{PRIORIDADE_MAXIMA} que a janela "
                    "oferece — este número NÃO veio do controle de preferência"
                ),
                cura=(
                    f"reabra '{p.name}' na aba Perfis e escolha a preferência de "
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
                "guarde UM perfil sem alvo (o de desktop, na preferência 0) e dê "
                "alvo aos demais, ou declare os que só usa na mão com "
                '`"match": {"type": "manual"}`'
            ),
            perfis=tuple(sorted(p.name for p in coringas)),
        )
    ]


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
    Ela fica de pé como atalho de teste — e quem precisar da corrente em
    produção usa as duas metades separadas, como o doctor usa.

    NOTA DATADA — 28/09/2026 (A-TELA-PERGUNTA-AO-DONO-01): o que caducou é o
    "não deve ganhar chamador de produção". A razão era o traceback no lugar da
    linha do doctor, e ela vale para um chamador SEM guarda. O exame da aba
    Sistema (`interface/pacotes/a09_sistema.linhas_dos_perfis`) a chama com o
    `except OSError` do lado de quem chama, como o doctor faz com as duas
    metades, e a frase de leitura que falhou continua sendo uma linha do exame.
    """
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles

    return verificar_perfis(load_all_profiles())


def linhas_de_relatorio(
    achados: Sequence[Achado], *, total_perfis: int | None = None
) -> list[tuple[str, str]]:
    """Formata os achados no par ``(tag, mensagem)`` que o doctor imprime."""
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
