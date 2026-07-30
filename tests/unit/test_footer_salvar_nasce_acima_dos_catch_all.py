"""O "Salvar Perfil" do rodapé nasce ACIMA dos "vale sempre" dela.

PERFIL-NASCE-CERTO-01, a meia-entrega que faltava ao caminho do rodapé. Medido em
30/07/2026: a aba Perfis já calculava a prioridade
(`_prioridade_acima_dos_catch_all`), mas o `_persist_profile_async` do rodapé
chamava `draft.to_profile(nome)` sem prioridade. Quando o `to_profile` passou a
delegar ao default do ESQUEMA para "chamador sem opinião", esse default é `0`
(`profiles/schema.py`) — e o perfil recém-salvo passou a nascer ABAIXO dos
catch-all que ela tem em disco.

O disco dela em 30/07, medido: `fallback` 0, `vitoria` 0, `meu_perfil` 1,
`Pragmata` 5, `Pragmata2` 5. Com prioridade 0 o perfil novo perde para três
deles; e o desempate final é a ordem alfabética do nome do arquivo, então nem o
empate salvava. Isso é literalmente a queixa crônica dela — "a config que eu
deixo nunca é respeitada" — reaparecendo num caminho que antes funcionava (o
default anterior era 5, que empatava no topo e vencia pelo alfabeto).

O módulo NÃO importa a GUI no topo, de propósito. `app.actions.profiles_actions`
puxa `gi` na primeira linha útil, e importar isso aqui derrubava a COLETA inteira
no CI headless — foi exatamente o que reprovou o `ci.yml` da tag v0.4.0 e, com
ele, o guarda que impede publicar em cima de CI vermelho. A guarda
`exigir_gi_real()` de módulo resolveria o erro e custaria caro: ela pula o
arquivo TODO, e metade destes testes (os que leem o fonte) não precisa de GTK
nenhum e é justamente a que protege a regressão.

Então: o que precisa do mixin importa DENTRO do teste, atrás da guarda; o que lê
o fonte roda em qualquer lugar.
"""
from __future__ import annotations

from typing import Any


from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile


def _mixin_e_folga() -> tuple[Any, int]:
    """Importa a GUI só depois de exigir o PyGObject real (GUARDA-GI-REAL-01)."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("prioridade do Salvar do rodapé")
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        _FOLGA_ACIMA_DO_CATCH_ALL,
        ProfilesActionsMixin,
    )

    return ProfilesActionsMixin, _FOLGA_ACIMA_DO_CATCH_ALL


def _app_fake(cache: list[Profile]) -> Any:
    """Dublê com só o que o cálculo de prioridade toca."""
    base, _ = _mixin_e_folga()

    class _AppFake(base):  # type: ignore[misc, valid-type]
        def __init__(self, c: list[Profile]) -> None:
            self._profiles_cache = c

    return _AppFake(cache)


def _catch_all(nome: str, prioridade: int) -> Profile:
    return Profile(name=nome, match=MatchAny(type="any"), priority=prioridade)


def _regra(nome: str, prioridade: int) -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(type="criteria", window_class=["steam_app_1"]),
        priority=prioridade,
    )


# O disco dela, medido em 30/07/2026.
DISCO_DELA = [
    _catch_all("fallback", 0),
    _catch_all("vitoria", 0),
    _catch_all("meu_perfil", 1),
    _catch_all("Pragmata", 5),
    _catch_all("Pragmata2", 5),
    _regra("Navegação", 50),
    _regra("coop_local", 75),
    _regra("sackboy_nativo", 80),
]


def test_prioridade_calculada_vence_todo_catch_all_do_disco_dela() -> None:
    app = _app_fake(list(DISCO_DELA))
    prioridade = app._prioridade_acima_dos_catch_all()

    catch_alls = [p.priority for p in DISCO_DELA if p.e_catch_all]
    assert prioridade > max(catch_alls), (
        f"perfil novo nasceria em {prioridade} e o maior catch-all dela é "
        f"{max(catch_alls)} — ele perderia a disputa que deveria ganhar"
    )
    _, folga = _mixin_e_folga()
    assert prioridade == max(catch_alls) + folga


def test_o_default_do_esquema_seria_pior_que_o_calculo() -> None:
    """Trava a razão de existir do cálculo, para ninguém "simplificar" de volta.

    Se alguém devolver `to_profile(nome)` sem prioridade, o valor que chega ao
    disco é o default do esquema — e este teste diz, com número, por que isso é
    uma regressão e não uma neutralidade.
    """
    default_do_esquema = int(Profile.model_fields["priority"].default)
    catch_alls = [p.priority for p in DISCO_DELA if p.e_catch_all]

    assert default_do_esquema <= max(catch_alls), (
        "este teste pressupõe que o default do esquema NÃO vence os catch-all "
        "dela; se o esquema mudou, o cálculo do rodapé precisa ser revisto"
    )
    perdedores = [p.name for p in DISCO_DELA if p.e_catch_all and p.priority > default_do_esquema]
    assert perdedores, "o default do esquema deveria perder para algum catch-all dela"


def test_sem_cache_o_calculo_nao_explode_e_da_a_folga() -> None:
    """Primeiro save da sessão, antes de a lista carregar: não pode estourar."""
    app = _app_fake([])
    _, folga = _mixin_e_folga()
    assert app._prioridade_acima_dos_catch_all() == folga


def test_regra_especifica_alta_nao_infla_a_prioridade_do_novo() -> None:
    """Só catch-all entra na conta — senão o `sackboy_nativo` (80) puxaria o novo
    perfil para 90 e ele passaria a vencer regras de jogo que não são dele."""
    app = _app_fake(list(DISCO_DELA))
    prioridade = app._prioridade_acima_dos_catch_all()
    regras = [p.priority for p in DISCO_DELA if not p.e_catch_all]
    assert prioridade < min(regras), (
        f"perfil novo nasceu em {prioridade}, acima da regra mais baixa "
        f"({min(regras)}) — passaria a vencer regra de jogo alheia"
    )


def test_o_rodape_passa_a_prioridade_calculada_ao_to_profile() -> None:
    """O contrato do call site: `_persist_profile_async` não pode voltar a chamar
    `to_profile(nome)` sem prioridade. Lê o fonte porque o caminho real é
    assíncrono (worker + thread GTK) e montar isso num teste unitário custaria
    mais do que o valor que ele protege."""
    from pathlib import Path

    fonte = Path(
        __file__
    ).resolve().parents[2] / "src/hefesto_dualsense4unix/app/actions/footer_actions.py"
    texto = fonte.read_text(encoding="utf-8")

    assert "_prioridade_acima_dos_catch_all" in texto, (
        "o rodapé voltou a salvar sem calcular a prioridade — o perfil novo "
        "nasce no default do esquema (0) e perde para os catch-all dela"
    )
    assert "to_profile(nome, priority=" in texto, (
        "o `to_profile` do rodapé precisa receber a prioridade explicitamente"
    )


def test_o_piso_do_fallback_nao_pode_ser_zero() -> None:
    """O fallback do `getattr` existe para dublê de teste e composição degradada.

    Se alguém o baixar para 0, o defeito volta pela porta de trás — e volta
    SILENCIOSO, porque nenhum caminho de erro é percorrido. O piso tem de vencer
    todo catch-all dela e perder para a regra de jogo mais baixa de fábrica.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("piso do rodapé")
    from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin

    piso = FooterActionsMixin._PISO_ACIMA_DOS_CATCH_ALL
    catch_alls = [p.priority for p in DISCO_DELA if p.e_catch_all]
    regras = [p.priority for p in DISCO_DELA if not p.e_catch_all]

    assert piso > max(catch_alls), (
        f"piso {piso} não vence o maior catch-all dela ({max(catch_alls)})"
    )
    assert piso < min(regras), (
        f"piso {piso} atropelaria a regra de jogo mais baixa ({min(regras)})"
    )


def _tem_atributo_publico(obj: Any, nome: str) -> bool:
    return hasattr(obj, nome)


def test_o_metodo_de_calculo_segue_alcancavel_pelo_mixin_do_rodape() -> None:
    """`FooterActionsMixin` e `ProfilesActionsMixin` são irmãos no `HefestoApp`.
    Se alguém separar os dois, o rodapé perde o método em runtime — e o defeito
    só apareceria com a janela aberta, no gesto dela."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("composição dos mixins")
    from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
    from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin

    class _Composto(ProfilesActionsMixin, FooterActionsMixin):
        pass

    assert _tem_atributo_publico(_Composto, "_prioridade_acima_dos_catch_all")
    assert _tem_atributo_publico(_Composto, "_persist_profile_async")
