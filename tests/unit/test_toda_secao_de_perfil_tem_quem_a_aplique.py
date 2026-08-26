"""BG-07 — nenhuma seção de perfil pode ficar SEM QUEM A APLIQUE.

O DEFEITO DE FORMA, EM UMA LINHA
--------------------------------
**Applier ausente não levanta: a seção é ignorada em silêncio.** Não há
exceção, não há linha no journal, não há chave no relatório — a ativação
responde sucesso e uma parte do perfil dela fica como o jogo a deixou. É a
família ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ`` casada com a ``ELO-MUDO-01``: o
produto responde pelo TRANSPORTE ("o perfil foi reaplicado") e nunca pelo
EFEITO.

O caso que pagou por este arquivo: ela desliga o Modo Nativo e a vibração não
volta ao que o perfil manda. A rota da volta monta o gerente com 6 dos 7
appliers, e o que falta é o de ``rumble.passthrough``.

POR QUE ESTE PORTÃO E NÃO O QUE JÁ EXISTIA
-------------------------------------------
``test_a_fabrica_do_gerente_e_a_unica_lista_de_appliers`` (22/08/2026) já
vigia duas coisas, e as duas continuam sendo dele: a FORMA de cada construção
de ``ProfileManager`` em ``src/`` (quem monta à mão precisa de razão escrita) e
a igualdade entre ``APPLIERS_DO_DAEMON`` e os parâmetros do construtor.

O buraco que sobra é o de **fora para dentro**: as duas réguas de lá são
internas ao par contrato/construtor. Apagar o ``rumble_passthrough_applier``
dos DOIS ao mesmo tempo deixa as duas verdes — elas voltam a bater — e a seção
``rumble.passthrough`` do arquivo de perfil dela simplesmente deixa de ter
dono, sem uma linha vermelha em lugar nenhum. **MEDIDO em 25/08/2026**, é o
segundo caso do mesmo formato que este dia mede: *régua que se confere contra
ela mesma não é régua*.

A contagem independente aqui é o **esquema do perfil** — ``Profile``, o que é
gravado no disco dela. Cada campo é classificado em :data:`_CLASSIFICACAO`
como *aplicado por applier injetado* ou *escrito direto no controle*, e a
classificação é EXAUSTIVA nos dois sentidos: campo novo sem classificação
reprova, e classificação que sobrou (campo removido do esquema) reprova
também. Ninguém acrescenta seção ao perfil dela sem passar por aqui.

O QUE CADA TESTE VIGIA
-----------------------
1. a classificação bate com ``Profile.model_fields``, nos dois sentidos;
2. toda seção que depende de applier tem um applier que EXISTE no construtor;
3. ``SECAO_DO_APPLIER`` cobre exatamente ``APPLIERS_DO_DAEMON`` — o mapa não
   envelhece calado;
4. **a fábrica entrega, de fato, um applier para cada seção** — e a prova é
   pelo EFEITO: um daemon completo (montado a partir da CLASSIFICAÇÃO, nunca
   de ``APPLIERS_DO_DAEMON``) entra em ``gerente_do_daemon``, e o gerente que
   sai tem de ter dono para cada seção. É este que morde quando um par sai da
   lista da fábrica, e a mensagem dele diz **a seção**, não o parâmetro;
5. a régua sabe RECUSAR: daemon a que falte UM método é apontado, nomeando a
   seção órfã. Régua que só sabe passar não é régua;
6. o gerente consome exatamente os appliers classificados — derivado por AST
   sobre o corpo da classe, para que um applier novo no ``apply_emulation``
   sem entrada aqui reprove.

PREÇO DECLARADO DESTA RÉGUA, e ele é real: ela mede a FÁBRICA, não as rotas.
Uma rota que monte o ``ProfileManager`` à mão sem passar por
``gerente_do_daemon`` continua invisível daqui — quem a pega é o portão da
classe do arquivo vizinho, e é por isso que os dois existem. Portão que finge
ver o que não vê é pior que portão nenhum.
"""
from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import (
    APPLIERS_DO_DAEMON,
    SECAO_DO_APPLIER,
    ProfileManager,
    gerente_do_daemon,
)
from hefesto_dualsense4unix.profiles.schema import Profile

_FONTE_DO_GERENTE = Path(
    inspect.getsourcefile(ProfileManager) or ""
).resolve()


@dataclass(frozen=True)
class SecaoPorApplier:
    """Um campo do perfil que só chega ao controle por applier INJETADO."""

    #: o nome da seção como ela aparece no aviso e no relatório — o caminho no
    #: arquivo de perfil, que é o vocabulário de quem lê o defeito, e não o
    #: nome do parâmetro do construtor.
    secao: str
    #: o parâmetro de `ProfileManager` que a aplica.
    applier: str
    #: o método do daemon de onde a fábrica o tira. Escrito à MÃO aqui de
    #: propósito: se viesse de `APPLIERS_DO_DAEMON`, arrancar um par de lá
    #: arrancaria junto o método do daemon-dublê, e o teste da fábrica passaria
    #: com a seção órfã. Foi assim que a primeira versão daquele portão vizinho
    #: (`62d092a`) conferia a tupla contra ela mesma.
    atributo_do_daemon: str


@dataclass(frozen=True)
class SecaoDireta:
    """Um campo do perfil que NÃO passa por applier — e por que não passa."""

    razao: str


#: A CLASSIFICAÇÃO EXAUSTIVA dos campos de `Profile`. Campo novo que não esteja
#: aqui reprova por estar SEM CLASSIFICAÇÃO — nunca por estar numa denylist.
#:
#: `rumble` aparece DUAS vezes, e não é engano: um campo do esquema, duas
#: seções, dois appliers, dois contratos (`policy` reverte o que outro perfil
#: ligou; `passthrough` só solta o que a GUI fixou). Classificar por campo em
#: vez de por seção esconderia exatamente o par que faltava.
_CLASSIFICACAO: dict[str, SecaoPorApplier | SecaoDireta] = {
    "mouse": SecaoPorApplier(
        secao="mouse",
        applier="mouse_applier",
        atributo_do_daemon="apply_profile_mouse",
    ),
    "suppress_desktop_emulation": SecaoPorApplier(
        secao="suppress_desktop_emulation",
        applier="suppression_applier",
        atributo_do_daemon="apply_profile_suppression",
    ),
    "mode": SecaoPorApplier(
        secao="mode",
        applier="mode_applier",
        atributo_do_daemon="apply_profile_mode",
    ),
    "rumble.policy": SecaoPorApplier(
        secao="rumble.policy",
        applier="rumble_policy_applier",
        atributo_do_daemon="apply_profile_rumble_policy",
    ),
    "rumble.passthrough": SecaoPorApplier(
        secao="rumble.passthrough",
        applier="rumble_passthrough_applier",
        atributo_do_daemon="apply_profile_rumble_passthrough",
    ),
    "speaker": SecaoPorApplier(
        secao="speaker",
        applier="speaker_applier",
        atributo_do_daemon="apply_profile_speaker",
    ),
    "mic": SecaoPorApplier(
        secao="mic",
        applier="mic_applier",
        atributo_do_daemon="apply_profile_mic",
    ),
    "triggers": SecaoDireta(
        razao=(
            "`ProfileManager.apply` escreve os gatilhos DIRETO no controller "
            "(`set_trigger`/`apply_output_specs`), sem applier injetado — o "
            "gerente já tem o controller, e não há política de lock a "
            "consultar."
        )
    ),
    "leds": SecaoDireta(
        razao=(
            "Mesma rota dos gatilhos: `apply` monta o `LedSettings` e escreve "
            "no controller. Sem applier."
        )
    ),
    "key_bindings": SecaoDireta(
        razao=(
            "`apply_keyboard` resolve os bindings e os empurra ao device "
            "virtual pelo `keyboard_device_provider` — que é um `lambda` "
            "resolvido a cada ativação, e por isso NÃO está em "
            "`APPLIERS_DO_DAEMON` (o manager nasce antes de o teclado subir; "
            "capturar a referência agora congelaria `None` para sempre)."
        )
    ),
    "controllers": SecaoDireta(
        razao=(
            "Mapa ADITIVO de overrides por controle físico: `apply` o resolve "
            "por uniq e escreve gatilhos/luzes direto; a metade de áudio "
            "reusa o `speaker_applier` já classificado acima "
            "(`apply_controller_speakers`)."
        )
    ),
    "teclado_emulado": SecaoDireta(
        razao=(
            "Z4/T14 (24/08/2026), PROVISÓRIO: o campo e a régua "
            "(`schema.resolver_teclado_emulado`) existem, e NENHUM caminho de "
            "ativação os chama ainda — a decisão dela sobre a frase de tela "
            "está em aberto. Quando o fio for ligado, esta entrada vira "
            "`SecaoPorApplier` e ganha applier na fábrica; até lá, classificar "
            "como applier faltante seria acusar de defeito uma decisão em "
            "aberto."
        )
    ),
    "match": SecaoDireta(
        razao="Critério de SELEÇÃO do perfil, não estado do controle."
    ),
    "priority": SecaoDireta(
        razao="Desempate entre perfis na seleção. Nada chega ao controle."
    ),
    "name": SecaoDireta(razao="Identidade do perfil. Nada chega ao controle."),
    "version": SecaoDireta(razao="Versão do esquema. Nada chega ao controle."),
    "ponte": SecaoDireta(
        razao=(
            "PONTE-CONFIRMADA-01: memória de qual ponte já funcionou NESTE "
            "jogo. É consumida pelo lançamento (`launch_env`), não pela "
            "ativação — nada é escrito no controle."
        )
    ),
}


def _por_applier() -> dict[str, SecaoPorApplier]:
    """As seções que dependem de applier, indexadas pela seção."""
    return {
        chave: valor
        for chave, valor in _CLASSIFICACAO.items()
        if isinstance(valor, SecaoPorApplier)
    }


def _campos_do_esquema() -> set[str]:
    """Os campos de `Profile`, com `rumble` expandido nas suas duas seções.

    A expansão é escrita aqui e não derivada porque é uma decisão: `rumble` é
    um campo com DOIS appliers, e é justamente o par que faltava.
    """
    campos = set(Profile.model_fields)
    if "rumble" in campos:
        campos.discard("rumble")
        campos |= {"rumble.policy", "rumble.passthrough"}
    return campos


def _daemon_completo() -> Any:
    """Um daemon-dublê com TODOS os métodos que a classificação exige.

    Os nomes vêm da CLASSIFICAÇÃO, nunca de `APPLIERS_DO_DAEMON` — é esse
    detalhe que faz o teste da fábrica morder quando um par sai da lista.
    """
    daemon = SimpleNamespace(
        controller=SimpleNamespace(),
        store=StateStore(),
        _keyboard_device=None,
    )
    for entrada in _por_applier().values():
        setattr(daemon, entrada.atributo_do_daemon, lambda *a, **k: None)
    return daemon


def _secoes_orfas(gerente: ProfileManager) -> list[str]:
    """As seções deste gerente que ficaram SEM QUEM AS APLIQUE."""
    return sorted(
        entrada.secao
        for entrada in _por_applier().values()
        if getattr(gerente, entrada.applier, None) is None
    )


def _appliers_lidos_pelo_gerente() -> set[str]:
    """Todo `self.<nome>_applier` LIDO dentro do corpo de `ProfileManager`.

    Contagem independente da classificação e do contrato: é o que o código de
    ativação de fato consulta. Applier novo em `apply_emulation` sem entrada na
    classificação reprova aqui.
    """
    arvore = ast.parse(_FONTE_DO_GERENTE.read_text(encoding="utf-8"))
    lidos: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.ClassDef) or no.name != "ProfileManager":
            continue
        for filho in ast.walk(no):
            if (
                isinstance(filho, ast.Attribute)
                and isinstance(filho.ctx, ast.Load)
                and isinstance(filho.value, ast.Name)
                and filho.value.id == "self"
                and filho.attr.endswith("_applier")
            ):
                lidos.add(filho.attr)
    return lidos


# ===========================================================================
# 1 — a classificação é exaustiva, nos DOIS sentidos
# ===========================================================================


def test_todo_campo_do_perfil_esta_classificado() -> None:
    """Seção nova no perfil dela não entra sem dizer QUEM a aplica.

    Mordida: acrescentar um campo a `Profile` — ou apagar uma entrada daqui.
    """
    do_esquema = _campos_do_esquema()
    classificados = set(_CLASSIFICACAO)
    sem_classificacao = sorted(do_esquema - classificados)
    sobrando = sorted(classificados - do_esquema)
    assert not sem_classificacao and not sobrando, (
        "a classificação e o esquema do perfil discordam.\n"
        f"SEM CLASSIFICAÇÃO (campo novo em `Profile`): {sem_classificacao} — "
        "diga quem aplica cada um: um applier injetado (`SecaoPorApplier`) ou "
        "escrita direta no controle (`SecaoDireta`, com a razão). Enquanto "
        "não estiver aqui, uma seção do arquivo dela pode ficar sem dono e "
        "ninguém vê.\n"
        f"SOBRANDO (não existe mais em `Profile`): {sobrando} — apague a "
        "entrada."
    )


def test_toda_razao_de_secao_direta_e_razao() -> None:
    """Isenção fingindo ser decisão reprova: razão vazia não é razão.

    Mordida: trocar uma `razao` por `""` ou por "não precisa".
    """
    curtas = sorted(
        chave
        for chave, valor in _CLASSIFICACAO.items()
        if isinstance(valor, SecaoDireta) and len(valor.razao.strip()) < 40
    )
    assert not curtas, (
        f"estas seções foram declaradas SEM applier sem dizer por quê: {curtas}. "
        "Escreva por onde a seção chega ao controle (ou por que ela não chega)."
    )


# ===========================================================================
# 2 e 3 — o applier existe, e o mapa de seções não envelhece calado
# ===========================================================================


def test_toda_secao_por_applier_tem_applier_no_construtor() -> None:
    """A seção aponta para um parâmetro que EXISTE.

    Mordida: renomear `rumble_passthrough_applier` no dataclass sem mexer aqui.
    """
    do_construtor = set(inspect.signature(ProfileManager).parameters)
    inexistentes = sorted(
        f"{entrada.secao} -> {entrada.applier}"
        for entrada in _por_applier().values()
        if entrada.applier not in do_construtor
    )
    assert not inexistentes, (
        "estas seções apontam para um applier que o `ProfileManager` não "
        f"tem: {inexistentes}. A seção não seria aplicada por ninguém."
    )


def test_o_mapa_de_secoes_cobre_a_fabrica_nos_dois_sentidos() -> None:
    """`SECAO_DO_APPLIER` e `APPLIERS_DO_DAEMON` falam do MESMO conjunto.

    Sem isto, o aviso de ausência da fábrica cairia no fallback e diria o nome
    do parâmetro — e o nome do parâmetro não é o nome do que ela deixa de
    sentir.

    Mordida: apagar uma linha de `SECAO_DO_APPLIER`.
    """
    da_fabrica = {parametro for parametro, _ in APPLIERS_DO_DAEMON}
    do_mapa = set(SECAO_DO_APPLIER)
    assert da_fabrica == do_mapa, (
        f"só na fábrica: {sorted(da_fabrica - do_mapa)}; "
        f"só no mapa de seções: {sorted(do_mapa - da_fabrica)}."
    )
    divergentes = sorted(
        f"{entrada.applier}: a classificação diz {entrada.secao!r}, "
        f"o mapa diz {SECAO_DO_APPLIER.get(entrada.applier)!r}"
        for entrada in _por_applier().values()
        if SECAO_DO_APPLIER.get(entrada.applier) != entrada.secao
    )
    assert not divergentes, (
        "o mapa de seções do produto e a classificação deste portão dão nomes "
        f"diferentes à mesma seção: {divergentes}."
    )


# ===========================================================================
# 4 — A MORDIDA: a fábrica entrega um applier para CADA seção
# ===========================================================================


def test_a_fabrica_entrega_dono_para_toda_secao_do_perfil() -> None:
    """Nenhuma seção do perfil sai da fábrica órfã — e o erro NOMEIA a seção.

    É a prova pelo EFEITO: monta um daemon completo (os métodos vêm da
    CLASSIFICAÇÃO, não da lista da fábrica), pede o gerente à fábrica e olha
    quem ficou sem dono.

    MORDIDA MEDIDA em 25/08/2026 — arrancar o par
    `("rumble_passthrough_applier", "apply_profile_rumble_passthrough")` de
    `APPLIERS_DO_DAEMON` faz este caso reprovar dizendo
    `['rumble.passthrough']`, que é a seção, e não "falhou".
    """
    gerente = gerente_do_daemon(_daemon_completo())
    orfas = _secoes_orfas(gerente)
    assert not orfas, (
        f"a fábrica montou um gerente com seções SEM QUEM AS APLIQUE: {orfas}.\n"
        "Applier ausente NÃO levanta — a seção é ignorada em silêncio, a "
        "ativação responde sucesso, e a parte do perfil dela fica como o jogo "
        "a deixou. Acrescente o par que falta a `APPLIERS_DO_DAEMON` "
        "(profiles/manager.py) ou, se a seção deixou de ter applier, mude a "
        "entrada da classificação deste portão para `SecaoDireta` com a razão."
    )


def test_a_regua_sabe_recusar_um_daemon_pela_metade() -> None:
    """Dublê que só sabe passar não é dublê: daemon incompleto é APONTADO.

    Sem este caso, o de cima poderia estar medindo o dublê em vez do produto —
    a armadilha 1 da casa (medir contra a régua errada produz verde
    convincente e falso).
    """
    daemon = _daemon_completo()
    delattr(daemon, "apply_profile_rumble_passthrough")
    gerente = gerente_do_daemon(daemon)
    assert _secoes_orfas(gerente) == ["rumble.passthrough"], (
        "a régua não viu a seção órfã de um daemon a que falta o método — "
        "ela estaria medindo a si mesma."
    )


def test_o_desvio_declarado_nao_conta_como_ausencia() -> None:
    """`mode_applier=None` é escolha medida, não descuido — e não vira alarme.

    A fábrica aceita o desvio nomeado (allowlist do Steam Input, saída do Modo
    Nativo). Contá-lo como ausência transformaria uma decisão escrita em
    vermelho — o defeito `O-PORTAO-QUE-NAO-MEDE-O-QUE-PROMETE`.
    """
    from hefesto_dualsense4unix.profiles.manager import _avisa_secoes_sem_applier

    argumentos = {
        parametro: (None if parametro == "mode_applier" else (lambda *a, **k: None))
        for parametro, _ in APPLIERS_DO_DAEMON
    }
    assert _avisa_secoes_sem_applier(argumentos, declarados=("mode_applier",)) == []
    assert _avisa_secoes_sem_applier(argumentos) == ["mode"]


def test_daemon_nenhum_segue_calado() -> None:
    """Zero applier é CONTRATO (CLI e dublês), não defeito — e não faz barulho.

    Mordida: trocar a guarda `len(ausentes) < len(considerados)` por um `if
    ausentes` — este caso passa a acusar toda rota de CLI.
    """
    from hefesto_dualsense4unix.profiles.manager import _avisa_secoes_sem_applier

    vazio = {parametro: None for parametro, _ in APPLIERS_DO_DAEMON}
    assert _avisa_secoes_sem_applier(vazio) == sorted(SECAO_DO_APPLIER.values())


# ===========================================================================
# 6 — o gerente consome exatamente o que foi classificado
# ===========================================================================


def test_o_gerente_consome_exatamente_os_appliers_classificados() -> None:
    """Applier novo no `apply_emulation` sem entrada na classificação reprova.

    Contagem independente por AST sobre o corpo da classe: é o que o código de
    ativação de fato consulta, e não o que alguma lista diz que ele consulta.

    Mordida: acrescentar um `self.xpto_applier` ao `apply_emulation`.
    """
    lidos = _appliers_lidos_pelo_gerente()
    classificados = {entrada.applier for entrada in _por_applier().values()}
    sem_classificacao = sorted(lidos - classificados)
    nunca_lidos = sorted(classificados - lidos)
    assert not sem_classificacao, (
        f"o `ProfileManager` consulta appliers sem seção declarada: "
        f"{sem_classificacao}. Classifique-os aqui — senão a ausência deles é "
        "silenciosa como a do `rumble_passthrough_applier` foi de 05/08 a "
        "25/08."
    )
    assert not nunca_lidos, (
        f"estes appliers estão classificados e NINGUÉM os consulta: "
        f"{nunca_lidos}. Ou o consumo sumiu (e a seção parou de ser aplicada), "
        "ou a entrada sobrou — apague-a."
    )
