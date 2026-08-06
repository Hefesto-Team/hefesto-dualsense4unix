"""REGRA-NAO-SE-PERDE-02 — o nome NOVO nascia sem regra nenhuma (05/08/2026).

A sprint 01 do mesmo dia fechou metade do buraco: quem JÁ EXISTE em disco herda
o próprio ``match`` no "Salvar Perfil" do rodapé. A outra metade continuou
aberta e é esta — **o nome NOVO nascia ``MatchAny()``**, por uma decisão de
23/07 que na época parecia conservadora: "o rodapé não tem campo de regra,
então o perfil nasce valendo sempre e a regra específica se define na aba
Perfis".

O que a medição de 05/08 mostrou é que ``MatchAny`` **não é neutro**. Ele é
catch-all, e catch-all nesta base tem duas propriedades opostas ao mesmo tempo:

- **invisível onde deveria valer** — a chave de seleção é
  ``(não é catch-all, prioridade)``, então ele perde para qualquer regra; e o
  veto R-21 recusa candidato catch-all numa janela ``steam_app_*``, devolvendo
  ``MOTIVO_JOGO_SEM_PERFIL_PROPRIO``. Ou seja: o perfil que ela acabou de
  salvar **com o jogo em foco** nunca ativa dentro do jogo;
- **soberano onde não deveria** — nasce com ``max(catch-all) + folga`` de
  prioridade e ganha o desktop INTEIRO, carregando junto o
  ``suppress_desktop_emulation``.

É exatamente a forma do ``sackboy_nativo`` dela em 05/08. A cura é a escada de
``footer_actions._regra_do_save``:

    1. o DISCO (``existente.match``) — já pago pela sprint 01;
    2. a ORIGEM (``draft.source_match``), **se for regra de verdade**;
    3. órfão -> ``MatchManual()``, e nunca ``MatchAny()``.

O degrau 2 pergunta ``e_catch_all`` e não ``isinstance(..., MatchAny)`` de
propósito: os três ``Match`` são classes irmãs e nenhuma herda da outra, e um
``MatchCriteria`` de campos vazios é catch-all na prática (foi assim que o
preset ``coop_local`` passou meses inalcançável). Herdar "vale sempre" não é
herdar regra.

AS MORDIDAS, medidas uma a uma arrancando a cura correspondente:

- degrau 2 fora -> ``test_nome_novo_herda_a_regra_do_perfil_de_origem``,
  ``test_o_perfil_do_rodape_nunca_nasce_catch_all`` (ramo da origem) e
  ``test_o_perfil_que_ela_acabou_de_salvar_vale_dentro_do_jogo`` reprovam;
- degrau 3 devolvido a ``MatchAny()`` -> ``test_sem_origem_nasce_so_manual``,
  ``test_a_origem_catch_all_nao_e_regra_a_herdar``,
  ``test_a_sanidade_nao_acusa_depois_de_tres_saves_pelo_rodape`` e o portão
  estático reprovam;
- degrau 1 fora (a cura da sprint 01) ->
  ``test_o_disco_vence_a_fotografia_quando_os_dois_tem_regra`` reprova, que é
  a guarda contra esta cura virar defeito novo;
- predicado trocado por ``isinstance(..., MatchAny)`` ->
  ``test_a_origem_catch_all_nao_e_regra_a_herdar`` continua verde, mas o
  ``MatchCriteria`` vazio passa: é por isso que o caso dele está lá dentro.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`, direto ou transitivo.
exigir_gi_real("herança de regra no rodapé (REGRA-NAO-SE-PERDE-02)")

import ast
from pathlib import Path

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles import sanidade
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import (
    MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    MOTIVO_SELECIONADO,
    ProfileManager,
)
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.testing import FakeController

# A aparelhagem é a MESMA da sprint 01, importada e não copiada: o gesto medido
# tem de ser um só. `_sync_run_in_thread` e `_disco_da_sprint_01` são FIXTURES e
# viajam pelo namespace do módulo — é assim que o pytest as enxerga.
from tests.unit.test_gravacao_de_perfil_passa_pelo_funil import (  # noqa: F401
    _janela_fake,
    _perfil_do_jogo,
    _perfil_em_disco,
    _salvar_pelo_rodape,
    _sync_run_in_thread,
)
from tests.unit.test_gravacao_de_perfil_passa_pelo_funil import (
    disco as _disco_da_sprint_01,
)

#: Reexportada por ATRIBUIÇÃO, e não pelo `import` direto: o nome de uma fixture
#: reaparece como PARÂMETRO em cada teste, e um binding de import sombreado
#: assim vira uma cascata de F811 no `ruff`. A ligação é a mesma função.
disco = _disco_da_sprint_01

#: Raiz do pacote, para o portão estático.
_SRC = Path(__file__).resolve().parents[2] / "src"
_FOOTER = _SRC / "hefesto_dualsense4unix" / "app" / "actions" / "footer_actions.py"

#: O jogo dela na fotografia do rascunho (`_perfil_do_jogo`) e o outro jogo, o
#: que já tem perfil em disco. Os dois números são os medidos no disco dela.
_WM_CLASS_DO_RASCUNHO = "steam_app_3357650"
_WM_CLASS_DO_SACKBOY = "steam_app_1599660"


def _gravado(disco: Path, slug: str) -> Profile:
    """O perfil como ele ficou NO DISCO, revalidado pelo esquema."""
    return Profile.model_validate(_perfil_em_disco(disco, slug))


# ---------------------------------------------------------------------------
# Degrau 2 — a herança nova
# ---------------------------------------------------------------------------


class TestNomeNovoHerdaARegraDaOrigem:
    def test_nome_novo_herda_a_regra_do_perfil_de_origem(self, disco: Path) -> None:
        """O gesto dela: jogo em foco, "Salvar Perfil", digita "MadJack".

        A regra de origem É a regra do jogo — é dela que o perfil novo tem de
        nascer. Antes nascia ``{"type": "any"}``, e o resultado está no
        ``test_o_perfil_que_ela_acabou_de_salvar_vale_dentro_do_jogo``.
        """
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")

        gravado = _gravado(disco, "madjack")
        assert gravado.match.type == "criteria", (
            "o perfil novo não herdou a regra da origem — nasce sem regra e "
            "não vale dentro do jogo em que ela o salvou"
        )
        assert isinstance(gravado.match, MatchCriteria)
        assert gravado.match.window_class == [_WM_CLASS_DO_RASCUNHO]

    def test_a_origem_catch_all_nao_e_regra_a_herdar(self, disco: Path) -> None:
        """Herdar "vale sempre" não é herdar regra — e o predicado é ESTRUTURAL.

        Dois casos no mesmo teste porque são a MESMA pergunta: o ``MatchAny``
        explícito e o ``MatchCriteria`` de campos vazios são as duas formas de
        catch-all (R-01). Um predicado por TIPO
        (``isinstance(..., MatchAny)``) deixaria o segundo passar, e o perfil
        novo nasceria com um critério que nunca casa — o acidente do
        ``coop_local`` de fábrica, agora fabricado pelo rodapé.
        """
        origens = {
            "vindo_do_any": Profile(name="vitoria", match=MatchAny(), priority=5),
            "vindo_do_vazio": Profile(
                name="coop_local", match=MatchCriteria(), priority=75
            ),
        }
        for nome_novo, origem in origens.items():
            janela = _janela_fake(DraftConfig.from_profile(origem), origem.name)

            _salvar_pelo_rodape(janela, nome_novo)

            gravado = _gravado(disco, nome_novo)
            assert gravado.match.type == "manual", (
                f"o perfil nascido de {origem.name!r} herdou um catch-all "
                f"({gravado.match.type}) — herdar 'vale sempre' é o mesmo que "
                "não herdar regra, e o ramo órfão é quem tem de responder"
            )
            assert gravado.e_catch_all is False


# ---------------------------------------------------------------------------
# Degrau 1 — a guarda contra a cura virar defeito novo
# ---------------------------------------------------------------------------


class TestODiscoVenceAFotografia:
    def test_o_disco_vence_a_fotografia_quando_os_dois_tem_regra(
        self, disco: Path
    ) -> None:
        """O caso em que a cura de cima PODERIA virar defeito novo.

        Ela está com o rascunho do Pragmata (regra ``steam_app_3357650``) e
        salva por cima do ``sackboy_nativo``, que em disco tem
        ``steam_app_1599660``. Se a herança da ORIGEM passasse na frente do
        DISCO, o perfil do Sackboy passaria a casar com o jogo errado — que é
        pior que o defeito original, porque agora tem cara de regra boa.

        MORDIDA: inverta os degraus 1 e 2 de ``_regra_do_save`` (ou apague o
        degrau 1) e este teste reprova com ``steam_app_3357650``.
        """
        save_profile(
            Profile(
                name="sackboy_nativo",
                match=MatchCriteria(window_class=[_WM_CLASS_DO_SACKBOY]),
                priority=80,
            )
        )
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "sackboy_nativo")

        gravado = _gravado(disco, "sackboy_nativo")
        assert isinstance(gravado.match, MatchCriteria)
        assert gravado.match.window_class == [_WM_CLASS_DO_SACKBOY], (
            "a fotografia do rascunho passou na frente do disco — o perfil do "
            "Sackboy ficou com a regra de OUTRO jogo"
        )


# ---------------------------------------------------------------------------
# Degrau 3 — o órfão
# ---------------------------------------------------------------------------


class TestOOrfaoNasceManual:
    def test_sem_origem_nasce_so_manual(self, disco: Path) -> None:
        """Sem disco e sem origem não há regra a herdar — e não se inventa uma.

        ``MatchManual`` é a tradução literal do que o diálogo do rodapé
        significa: *"guarde o que eu tenho agora; quando usar, eu digo"*. Ele
        nunca vira candidato (``matches()`` é sempre ``False``), não dispara o
        veto R-21 nem a reversão de modo, e a ``sanidade`` o isenta.

        MORDIDA: devolva ``MatchAny()`` ao degrau 3 e este teste reprova com
        ``any``.
        """
        janela = _janela_fake(DraftConfig.default())

        _salvar_pelo_rodape(janela, "Novo")

        gravado = _gravado(disco, "novo")
        assert gravado.match.type == "manual", (
            "o órfão nasceu catch-all — invisível no jogo e soberano no "
            "desktop, que é a forma do `sackboy_nativo` de 05/08"
        )
        assert gravado.matches({"wm_class": _WM_CLASS_DO_RASCUNHO}) is False

    def test_o_perfil_do_rodape_nunca_nasce_catch_all(self, disco: Path) -> None:
        """A invariante ESTRUTURAL, nos dois ramos, sem falar de tipo.

        É a asserção que sobrevive a uma quarta forma de ``Match``: seja qual
        for a regra escolhida, ela não pode ser a que perde para todo mundo
        dentro do jogo e ganha de todo mundo fora dele.
        """
        com_origem = _janela_fake(
            DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata"
        )
        _salvar_pelo_rodape(com_origem, "Com origem")

        orfao = _janela_fake(DraftConfig.default())
        _salvar_pelo_rodape(orfao, "Sem origem")

        for slug in ("com_origem", "sem_origem"):
            assert _gravado(disco, slug).e_catch_all is False, (
                f"{slug} nasceu catch-all pelo rodapé"
            )


# ---------------------------------------------------------------------------
# A RAZÃO da cura: o perfil vale dentro do jogo
# ---------------------------------------------------------------------------


class TestOPerfilValeDentroDoJogo:
    def test_o_perfil_que_ela_acabou_de_salvar_vale_dentro_do_jogo(
        self, disco: Path
    ) -> None:
        """A queixa dela, do começo ao fim, num teste só.

        Ela está no jogo, ajusta a cor e os gatilhos, salva como "MadJack" — e
        o daemon, com a janela do MESMO jogo em foco, tem de escolher esse
        perfil. Com ``MatchAny`` o daemon respondia
        ``MOTIVO_JOGO_SEM_PERFIL_PROPRIO``: o veto R-21 recusa candidato
        catch-all em janela de jogo, então o perfil recém-salvo era o ÚNICO no
        disco e ainda assim não valia.

        MORDIDA: sem o degrau 2, este teste reprova com
        ``jogo_sem_perfil_proprio`` e ``perfil is None``.
        """
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")

        controle = FakeController()
        controle.connect()
        perfil, motivo = ProfileManager(controller=controle).select_for_window_ex(
            {"wm_class": _WM_CLASS_DO_RASCUNHO}
        )

        assert motivo != MOTIVO_JOGO_SEM_PERFIL_PROPRIO, (
            "o daemon vetou o perfil que ela ACABOU de salvar dentro do jogo — "
            "é a queixa crônica ('a config que eu deixo nunca é respeitada')"
        )
        assert motivo == MOTIVO_SELECIONADO
        assert perfil is not None
        assert perfil.name == "MadJack"


# ---------------------------------------------------------------------------
# O disco depois de três gestos: a sanidade não acusa
# ---------------------------------------------------------------------------


class TestODiscoContinuaSao:
    def test_a_sanidade_nao_acusa_depois_de_tres_saves_pelo_rodape(
        self, disco: Path
    ) -> None:
        """Três "Salvar Perfil" e o verificador semântico continua calado.

        O antes é fácil de reproduzir: cada save com nome novo somava um
        catch-all e um degrau de prioridade, e ``profiles/sanidade.py``
        acusava ``catch_all_demais`` — perfis disputando a mesma vaga, com a
        vencedora saindo por sorteio. É o disco dela de 05/08, montado por
        três gestos.

        MORDIDA: devolva ``MatchAny()`` ao degrau 3 (ou apague o degrau 2) e
        ``catch_all_demais`` volta a aparecer.
        """
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")
        _salvar_pelo_rodape(janela, "MadJack")
        _salvar_pelo_rodape(janela, "Sackboy")

        achados = sanidade.verificar_perfis_do_disco()
        regras = sorted({a.regra for a in achados})

        assert "catch_all_demais" not in regras, (
            "os saves do rodapé encheram o disco de catch-all: "
            + "; ".join(a.mensagem for a in achados if a.regra == "catch_all_demais")
        )
        assert "prioridade_fora_da_faixa" not in regras, (
            "a prioridade saiu da faixa da janela: "
            + "; ".join(
                a.mensagem for a in achados if a.regra == "prioridade_fora_da_faixa"
            )
        )


# ---------------------------------------------------------------------------
# O PORTÃO: o rodapé não constrói catch-all, e não é por lembrança
# ---------------------------------------------------------------------------


def _chamadas_a(fonte: Path, nome: str) -> list[int]:
    """Linhas em que ``nome(...)`` é CONSTRUÍDO em ``fonte``.

    Pela árvore, e não por texto: as docstrings desta cura citam ``MatchAny()``
    dezenas de vezes ao explicar por que ele saiu — um portão textual acusaria
    justamente a explicação.
    """
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        chamado = (
            alvo.id
            if isinstance(alvo, ast.Name)
            else alvo.attr
            if isinstance(alvo, ast.Attribute)
            else None
        )
        if chamado == nome:
            linhas.append(no.lineno)
    return linhas


def test_o_rodape_nao_constroi_catch_all_por_conta_propria() -> None:
    """Nenhum ``MatchAny(`` dentro de ``footer_actions.py``.

    Irmão do portão de ``test_gravacao_de_perfil_passa_pelo_funil.py``, e pela
    mesma razão: a cura não pode depender de alguém LEMBRAR dela. Quem
    escrever o próximo caminho de gravação no rodapé — outro botão, outro
    ramo de fallback — não vai reler esta sprint; vai escrever o
    ``MatchAny()`` que parece o valor neutro, e a única coisa entre isso e o
    disco dela é este teste.

    O portão é deliberadamente estreito: veta a CONSTRUÇÃO no rodapé, não a
    existência do tipo. Quem precisa de catch-all de verdade tem a aba Perfis
    e o editor avançado, onde ela vê o que está escolhendo.
    """
    ofensoras = _chamadas_a(_FOOTER, "MatchAny")

    assert ofensoras == [], (
        f"footer_actions.py constrói MatchAny() nas linhas {ofensoras} — o "
        "rodapé não tem campo de regra, então um catch-all nascido aqui é "
        "sempre um perfil invisível dentro do jogo e soberano fora dele "
        "(REGRA-NAO-SE-PERDE-02). O ramo sem origem usa MatchManual()"
    )


def test_o_portao_enxerga_a_construcao_que_ele_veta(tmp_path: Path) -> None:
    """O portão acima morde? Um fonte-canário responde, sem tocar no produto.

    Sem esta prova, `ofensoras == []` também passaria se `_chamadas_a`
    estivesse quebrada — o modo de falha mais comum de portão estático.
    """
    canario = tmp_path / "canario.py"
    canario.write_text(
        "from x import MatchAny, schema\n"
        '"""Docstring que cita MatchAny() e NÃO pode acusar."""\n'
        "a = MatchAny()\n"
        "b = schema.MatchAny()\n",
        encoding="utf-8",
    )

    assert _chamadas_a(canario, "MatchAny") == [3, 4]


