"""REGRA-NAO-SE-PERDE-02 — o nome NOVO nascia sem regra nenhuma (05/08/2026)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

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

disco = _disco_da_sprint_01

_SRC = Path(__file__).resolve().parents[2] / "src"
_FOOTER = _SRC / "hefesto_dualsense4unix" / "app" / "actions" / "footer_actions.py"

_WM_CLASS_DO_RASCUNHO = "steam_app_3357650"
_WM_CLASS_DO_SACKBOY = "steam_app_1599660"


def _gravado(disco: Path, slug: str) -> Profile:
    """O perfil como ele ficou NO DISCO, revalidado pelo esquema."""
    return Profile.model_validate(_perfil_em_disco(disco, slug))


class TestNomeNovoHerdaARegraDaOrigem:
    def test_nome_novo_herda_a_regra_do_perfil_de_origem(self, disco: Path) -> None:
        """O gesto dela: jogo em foco, "Salvar Perfil", digita "MadJack"."""
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
        """Herdar "vale sempre" não é herdar regra — e o predicado é ESTRUTURAL."""
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


class TestODiscoVenceAFotografia:
    def test_o_disco_vence_a_fotografia_quando_os_dois_tem_regra(
        self, disco: Path
    ) -> None:
        """O caso em que a cura de cima PODERIA virar defeito novo."""
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


class TestOOrfaoNasceManual:
    def test_sem_origem_nasce_so_manual(self, disco: Path) -> None:
        """Sem disco e sem origem não há regra a herdar — e não se inventa uma."""
        janela = _janela_fake(DraftConfig.default())

        _salvar_pelo_rodape(janela, "Novo")

        gravado = _gravado(disco, "novo")
        assert gravado.match.type == "manual", (
            "o órfão nasceu catch-all — invisível no jogo e soberano no "
            "desktop, que é a forma do `sackboy_nativo` de 05/08"
        )
        assert gravado.matches({"wm_class": _WM_CLASS_DO_RASCUNHO}) is False

    def test_o_perfil_do_rodape_nunca_nasce_catch_all(self, disco: Path) -> None:
        """A invariante ESTRUTURAL, nos dois ramos, sem falar de tipo."""
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


class TestOPerfilValeDentroDoJogo:
    def test_o_perfil_que_ela_acabou_de_salvar_vale_dentro_do_jogo(
        self, disco: Path
    ) -> None:
        """A queixa dela, do começo ao fim, num teste só."""
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


class TestODiscoContinuaSao:
    def test_a_sanidade_nao_acusa_depois_de_tres_saves_pelo_rodape(
        self, disco: Path
    ) -> None:
        """Três "Salvar Perfil" e o verificador semântico continua calado."""
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


def _chamadas_a(fonte: Path, nome: str) -> list[int]:
    """Linhas em que ``nome(...)`` é CONSTRUÍDO em ``fonte``."""
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
    """Nenhum ``MatchAny(`` dentro de ``footer_actions.py``."""
    ofensoras = _chamadas_a(_FOOTER, "MatchAny")

    assert ofensoras == [], (
        f"footer_actions.py constrói MatchAny() nas linhas {ofensoras} — o "
        "rodapé não tem campo de regra, então um catch-all nascido aqui é "
        "sempre um perfil invisível dentro do jogo e soberano fora dele "
        "(REGRA-NAO-SE-PERDE-02). O ramo sem origem usa MatchManual()"
    )


def test_o_portao_enxerga_a_construcao_que_ele_veta(tmp_path: Path) -> None:
    """O portão acima morde? Um fonte-canário responde, sem tocar no produto."""
    canario = tmp_path / "canario.py"
    canario.write_text(
        "from x import MatchAny, schema\n"
        '"""Docstring que cita MatchAny() e NÃO pode acusar."""\n'
        "a = MatchAny()\n"
        "b = schema.MatchAny()\n",
        encoding="utf-8",
    )

    assert _chamadas_a(canario, "MatchAny") == [3, 4]


