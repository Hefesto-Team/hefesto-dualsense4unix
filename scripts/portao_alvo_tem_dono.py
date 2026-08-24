#!/usr/bin/env python3
"""O portão do ALVO-GANHA-DONO — duas réguas, um comando.

24/08/2026, sprint ONDA0-Z2. O defeito de forma que ele impede de voltar
(F3, medido em 23/08): o alvo de edição por controle morava num atributo
com *default de classe* (``_edit_target_uniq``), lido por sete pontos da
janela via ``getattr(self, "_edit_target_uniq", None)`` — e o ``None`` do
``getattr`` nunca entrava em ação, porque o atributo da classe já respondia
``None`` primeiro. A cura, ``app/alvo_de_edicao.py``, só vale enquanto
ninguém reabrir o atalho antigo — e é ISSO que a régua 1 vigia.

RÉGUA 1 — O CAMPO VELHO NÃO VOLTA (Z2-6)
-----------------------------------------
Reprova ``_edit_target_uniq`` em QUALQUER arquivo de ``src/`` que não seja
``app/alvo_de_edicao.py`` (o dono) ou este próprio portão — **inclusive em
comentário**. Onze das dezenove ocorrências fora do dono, medidas em
23/08/2026, eram comentário — e são elas que ensinam o próximo agente a
escrever o ``getattr`` de novo. ``tests/`` fica de fora de propósito: dublês
ainda escrevem o atributo antigo direto (é a ponte que
``app/alvo_de_edicao.py`` documenta), e não é ela quem ensina o hábito ruim
em produção.

Duas exceções, e nenhuma allowlist além destas:

* ``app/alvo_de_edicao.py`` — o dono, onde o nome do atributo tem de existir;
* este arquivo — porque ele PRECISA citar o nome para procurá-lo.

Não há exceção para a antiga anotação de classe
(``status_actions.py:448``): a Z2-0a mediu que nada em ``src/`` atribui a
ela direto (``self._edit_target_uniq = ...``) — os leitores usavam
``getattr`` e os escritores passavam por ``app/alvo_de_edicao.py`` — então a
anotação era só para o mypy dos leitores não migrados. Migrados os sete, a
anotação virou vestígio morto e SAIU (Z2-10/Z2-11), em vez de virar exceção
permanente.

RÉGUA 2 — A MOLDURA VIRA LEI (Z2-9)
-------------------------------------
O contrato do §5 da sprint: toda aba está ou entre as LEITORAS do alvo, ou
DECLARADA inerte com motivo — nunca omissa. Quem guarda essa declaração é
``HefestoApp._ALVO_POR_ABA`` (``app/app.py``): ``None`` = lê o alvo, a fita
fica sensível; um texto = inerte, o motivo que ``set_alvo_inativo`` guarda
(nunca pintado — decisão dela de 23/08/2026). A régua valida o mapa contra
as ONZE abas conhecidas — as QUATRO que hoje leem e as SETE que não —
porque uma régua que não separa essas duas listas exatamente assim é a
régua que está errada (A5 do COMO-REGER-AGENTES), não o produto.

Uso (CI e pre-commit):
    python scripts/portao_alvo_tem_dono.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

#: Régua 1 — o literal do campo velho, e as duas exceções declaradas.
_CAMPO_VELHO = "_edit_target_uniq"
_ARQUIVO_DONO = SRC / "hefesto_dualsense4unix" / "app" / "alvo_de_edicao.py"
_ESTE_ARQUIVO = Path(__file__).resolve()

#: Régua 2 — as onze abas conhecidas, pelo id de Glade que
#: ``HefestoApp._ALVO_POR_ABA`` usa como chave. Separadas nas duas listas que
#: a sprint mediu (§2.2/M3): as QUATRO leitoras de hoje e as SETE inertes —
#: a Configurações por desenho, as outras seis por ainda não terem ligado um
#: leitor. Uma aba nova em ``app/actions/`` entra numa das duas, nunca fica
#: de fora — é o mesmo formato do ``_REFRESH_POR_ABA`` da Z5.
ABAS_LEITORAS = frozenset(
    {
        "tab_status_box",
        "tab_triggers_box",
        "tab_lightbar_box",
        "tab_rumble_box",
    }
)
ABAS_INERTES = frozenset(
    {
        "tab_home_box",
        "tab_no_jogo_box",
        "profiles_paned",
        "daemon_box",
        "emulation_box",
        "tab_navegacao_dsx",
        "tab_config_box",
    }
)


def _regua_1_campo_velho_nao_volta() -> list[str]:
    achados: list[str] = []
    for caminho in sorted(SRC.rglob("*.py")):
        if caminho.resolve() in (_ARQUIVO_DONO.resolve(), _ESTE_ARQUIVO):
            continue
        texto = caminho.read_text(encoding="utf-8")
        if _CAMPO_VELHO not in texto:
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if _CAMPO_VELHO in linha:
                relpath = caminho.relative_to(ROOT)
                achados.append(f"  {relpath}:{numero}: {linha.strip()}")
    return achados


def _regua_2_moldura_vira_lei() -> list[str]:
    falhas: list[str] = []
    try:
        from hefesto_dualsense4unix.app.app import HefestoApp
    except Exception as exc:  # pragma: no cover — falha de import é FAIL, não crash
        return [f"  não consegui importar HefestoApp para conferir o mapa: {exc}"]

    mapa = getattr(HefestoApp, "_ALVO_POR_ABA", None)
    if not isinstance(mapa, dict):
        return ["  HefestoApp._ALVO_POR_ABA não existe (ou não é dict) — Z2-8 caiu"]

    todas = ABAS_LEITORAS | ABAS_INERTES
    faltando = todas - set(mapa)
    for aba in sorted(faltando):
        falhas.append(f"  {aba}: fora de _ALVO_POR_ABA — nem leitora, nem inerte")

    for aba in sorted(ABAS_LEITORAS):
        if aba in mapa and mapa[aba] is not None:
            falhas.append(
                f"  {aba}: deveria LER o alvo (None) e está inerte ({mapa[aba]!r})"
            )
    for aba in sorted(ABAS_INERTES):
        if aba in mapa and not mapa[aba]:
            falhas.append(
                f"  {aba}: deveria estar INERTE com motivo, e não tem motivo nenhum"
            )

    extras = set(mapa) - todas
    for aba in sorted(extras):
        falhas.append(
            f"  {aba}: está em _ALVO_POR_ABA mas fora do censo deste portão — "
            "acrescente-a em ABAS_LEITORAS/ABAS_INERTES aqui também"
        )
    return falhas


def main() -> int:
    falhas_1 = _regua_1_campo_velho_nao_volta()
    falhas_2 = _regua_2_moldura_vira_lei()

    if falhas_1:
        print(
            f"FAIL (régua 1 — o campo velho voltou): "
            f"{len(falhas_1)} ocorrência(s) de {_CAMPO_VELHO!r} fora do dono:"
        )
        print("\n".join(falhas_1))
    if falhas_2:
        print("FAIL (régua 2 — a moldura não é lei): _ALVO_POR_ABA incompleto:")
        print("\n".join(falhas_2))

    if falhas_1 or falhas_2:
        print(
            "\nQuem lê o alvo chama alvo_de_edicao(self) — nunca getattr. "
            "Aba que não lê declara-se inerte em HefestoApp._ALVO_POR_ABA, "
            "com motivo. Ver app/alvo_de_edicao.py (o contrato está na "
            "docstring do módulo)."
        )
        return 1

    print(
        f"OK: zero ocorrências de {_CAMPO_VELHO!r} fora do dono; "
        f"_ALVO_POR_ABA cobre as {len(ABAS_LEITORAS)} leitoras e as "
        f"{len(ABAS_INERTES)} inertes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
