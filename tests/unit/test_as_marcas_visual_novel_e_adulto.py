"""As marcas Visual novel e Adulto se somam ao estilo — 09/10/2026.

O perfil tinha um estilo só, e ele é receita, não etiqueta: o Maid Life SS é visual
novel E adulto, e nenhum dos dois é estilo. `Profile.marcas` guarda as chaves de
`profiles/marcas_do_jogo.py`. E a tela dizia «o campo volta ao travessão» com
`"estilo": None` sempre, enquanto o perfil guarda a chave do estilo desde o motor do
tato.

MORDIDAS: devolva `"estilo": None` em `perfis_web._pacote_do_editor` e a régua do
rótulo reprova; faça `molde_dos_botoes` responder à «Adulto» e a régua da Adulto
reprova.
"""
from __future__ import annotations

import json
from typing import Any

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.profiles import loader, marcas_do_jogo
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchCriteria,
    Profile,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController

NOME = "Maid Life"
P2 = "aabbcc000002"


def _perfil(**extra: Any) -> Profile:
    lado = TriggerConfig(mode="Rigid", params=[5, 200])
    return Profile(
        name=NOME,
        match=MatchCriteria(window_class=["maidlife"]),
        triggers=TriggersConfig(left=lado, right=lado),
        rumble=RumbleConfig(policy="economia"),
        leds=LedsConfig(lightbar=(200, 40, 90)),
        controllers={P2: ControllerOverrides(leds=LedsConfig(lightbar=(1, 2, 3)))},
        estilo="point_and_click",
        **extra,
    )


def test_as_marcas_carregam_exportam_e_importam_iguais() -> None:
    """Gravar, ler, exportar (o arquivo) e importar (`model_validate`) levam as duas."""
    marcas = ["visual_novel", "adulto"]
    loader.save_profile(_perfil(marcas=marcas), origem="régua")

    lido = loader.load_profile(NOME)
    assert lido.marcas == marcas

    exportado = json.loads(loader.arquivo_do_perfil(NOME).read_text(encoding="utf-8"))
    assert exportado["marcas"] == marcas, "o arquivo exportado perdeu as marcas"
    importado = Profile.model_validate(exportado)
    assert importado == lido


def test_a_marca_desconhecida_nao_recusa_o_perfil() -> None:
    """Uma marca que saiu do produto fica no arquivo e some só da tela."""
    loader.save_profile(_perfil(marcas=["adulto", "que_saiu"]), origem="régua")

    lido = loader.load_profile(NOME)
    assert lido.marcas == ["adulto", "que_saiu"]
    assert marcas_do_jogo.rotulos(lido.marcas) == ["Adulto"]


def test_o_perfil_sem_marca_grava_igual_ao_de_antes() -> None:
    """Sem marca, a chave nem aparece: o perfil de ontem sai do dump idêntico."""
    assert "marcas" not in _perfil().model_dump()


def test_o_editor_mostra_o_estilo_guardado_e_as_marcas() -> None:
    """`perfis_web` devolve «Point-and-click» e as marcas, e não o travessão."""
    perfil = _perfil(marcas=["adulto", "visual_novel"])
    editor = perfis_web.pacote_da_aba([perfil], editado=perfil)["editor"]

    assert editor["estilo"] == "Point-and-click", (
        f"o editor esconde o estilo que o perfil guarda: {editor['estilo']!r}")
    assert editor["marcas"] == ["Visual novel", "Adulto"]
    assert "travessão" not in editor["estilo_recado"], editor["estilo_recado"]
    assert "não apaga o estilo" in editor["estilo_recado"]


def test_o_estilo_que_saiu_do_produto_fica_sem_rotulo() -> None:
    """Chave de estilo desconhecida: o campo não inventa rótulo."""
    perfil = _perfil().model_copy(update={"estilo": "coop_local"})
    assert perfis_web.pacote_da_aba([perfil], editado=perfil)["editor"]["estilo"] is None


class _Gravador(FakeController):
    """O backend de mentira: grava as duas camadas que a ativação publica."""

    def __init__(self) -> None:
        super().__init__()
        self.padrao = OutputSpec()
        self.do_perfil: dict[str, Any] = {}

    def apply_output_defaults(self, spec: Any) -> Any:
        self.padrao = spec
        return "escreveu"

    def reset_profile_overrides(self, overrides: Any, procedencias: Any = None) -> None:
        self.do_perfil = dict(overrides or {})


def _aplicado(perfil: Profile) -> tuple[Any, dict[str, Any]]:
    gravador = _Gravador()
    ProfileManager(controller=gravador).apply(perfil, origin="auto", relatorio={})
    return gravador.padrao, gravador.do_perfil


def test_a_marca_adulto_nao_muda_o_controle() -> None:
    """A «Adulto» sozinha: o que chega ao controle e os botões são os mesmos."""
    sem, com = _perfil(), _perfil(marcas=["adulto"])

    assert _aplicado(com) == _aplicado(sem)
    for campo in ("button_actions", "triggers", "leds", "rumble", "controllers"):
        assert getattr(com, campo) == getattr(sem, campo), campo
    assert marcas_do_jogo.molde_dos_botoes(com.estilo, com.marcas) is None, (
        "a marca «Adulto» escolheu molde de botões")


def test_a_visual_novel_so_escolhe_molde_no_point_and_click() -> None:
    """Com Point-and-click, o molde «Visual novel»; com outro estilo, o do jogo."""
    vn = [marcas_do_jogo.VISUAL_NOVEL.chave]
    assert marcas_do_jogo.molde_dos_botoes("point_and_click", vn) == "visual_novel"
    assert marcas_do_jogo.molde_dos_botoes("fps", vn) is None
    assert marcas_do_jogo.molde_dos_botoes("point_and_click", []) is None
