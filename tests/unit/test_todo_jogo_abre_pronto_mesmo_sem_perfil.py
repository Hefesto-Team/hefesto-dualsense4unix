"""TROCA-DENTRO-DO-JOGO-01 — a regra vale para TODO jogo, não só o que tem perfil.

Ela leu a PS-L3-MASCARA-01 e cobrou, em 14/09/2026, com a grafia dela:

    *"inclusive nao pode ter sido feita pensando  (noqa-acento: citação literal)
    so num dos jogos. ele é o sintoma de algo maior não?"*

Estava certa. O conserto de 14/09 alcançava só o `steam_app_<appid>.env`, e na
máquina dela UM perfil tem `mode` (o do Future Knight): os outros 29 jogos leem o
`default.env`, que copiava o estado VIVO e, sem vpad de pé, saía sem
`SDL_GAMECONTROLLER_IGNORE_DEVICES`. O jogo aberto assim vê o DualSense de
plástico; ao subir um modo de jogo com o PS + R3 lá dentro, o físico morre
grabado e o vpad chega como segundo controle. A env é lida UMA vez, no `exec`
(`assets/hefesto-launch.sh`), e nada do que o daemon regrave depois a alcança.

DECISÃO DELA — D-1409-FORA-DO-NATIVO-O-JOGO-VE-SO-O-VIRTUAL: fora do Modo Nativo
o jogo vê só o controle virtual, com perfil ou sem perfil. O preço que ela leu
antes de escolher: na Navegação o jogo fica sem gamepad até ela subir um modo.

MORDE, e são quatro curas independentes:

* o `default.env` voltar a copiar o estado vivo (`compose_env` direto, sem
  `modo_do_estado_vivo`) — o jogo sem perfil reabre o defeito;
* o `desktop` voltar para `_nativos_fora_da_antecipacao` — um perfil de Navegação
  casado por processo derruba o IGNORE de todo jogo;
* `_vpads_previstos` prometer sempre um vpad — a mesa de dois com co-op ligado
  perde o IGNORE, e a de dois com co-op desligado ganha um IGNORE que esconde o
  controle do jogador 2;
* `pronto_para_troca` sair do `como_estado()` — a linha `# estado:` do arquivo
  volta a dizer o contrário do que a env faz.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.integrations import cura_por_estrada

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
_DISABLE = "PROTON_DISABLE_HIDRAW"
P1 = "aabbcc000001"


def _env(path: Path) -> dict[str, str]:
    return dict(
        linha.split("=", 1)
        for linha in path.read_text(encoding="utf-8").splitlines()
        if linha and not linha.startswith("#") and "=" in linha
    )


def _estado(path: Path) -> str:
    return next(
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.startswith("# estado:")
    )


def _daemon(
    *,
    mascara: str = "dualsense",
    caminho: str = "dualsense",
    ligado: bool = False,
    native: bool = False,
    vpad: Any = None,
    fisicos: int = 1,
    coop: bool = True,
) -> SimpleNamespace:
    """A mesa dela sem perfil nenhum: o que o `default.env` descreve."""
    return SimpleNamespace(
        is_native_mode=lambda: native,
        config=SimpleNamespace(
            gamepad_emulation_enabled=ligado,
            gamepad_flavor=mascara,
            gamepad_caminho=caminho,
            coop_enabled=coop,
        ),
        _gamepad_device=vpad,
        _coop_manager=None,
        controller=SimpleNamespace(
            primary_uniq=P1,
            describe_controllers=lambda: [
                {"uniq": f"mac{i}", "connected": True} for i in range(fisicos)
            ],
        ),
        store=SimpleNamespace(window_detect_current_class=None),
    )


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    return tmp_path


def test_todo_jogo_abre_pronto_mesmo_sem_perfil(pasta: Path) -> None:
    """O caso dela: Navegação, jogo sem perfil próprio, nenhum vpad de pé."""
    le.materialize_launch_env(_daemon())

    env = _env(pasta / "default.env")
    assert _IGNORE in env, (
        "o jogo sem perfil abria vendo o DualSense de plástico, e o PS + R3 lá "
        "dentro não alcança a env — ela é lida uma vez, no exec"
    )
    assert _DISABLE in env
    assert "pronto_para_troca=True" in _estado(pasta / "default.env")


def test_o_modo_nativo_e_a_excecao_e_continua_entregando_o_fisico(pasta: Path) -> None:
    le.materialize_launch_env(_daemon(native=True))

    env = _env(pasta / "default.env")
    assert _IGNORE not in env and _DISABLE not in env
    assert "pronto_para_troca" not in _estado(pasta / "default.env")


def test_com_vpad_de_pe_a_env_continua_sendo_a_do_aparelho(pasta: Path) -> None:
    """Com vpad vivo nada de prognóstico: o estado é o próprio aparelho."""
    vpad = SimpleNamespace(backend="uhid", flavor="dualsense")
    le.materialize_launch_env(_daemon(ligado=True, vpad=vpad))

    estado = _estado(pasta / "default.env")
    assert _IGNORE in _env(pasta / "default.env")
    assert "emulacao=True" in estado and "backends=['uhid']" in estado
    assert "pronto_para_troca" not in estado


def test_emulacao_ligada_sem_vpad_e_falha_e_deixa_o_fisico_a_vista(pasta: Path) -> None:
    """O único estado sem vpad que NÃO promete a troca.

    Emulação ligada e nenhum vpad é falha de subida (`vpad_ausente`), não a
    Navegação. Esconder o físico aí seria abrir o jogo sem controle nenhum — e
    ela escolheu "só o virtual", não "nenhum".

    MORDE: tirar o ramo `if enabled:` de `modo_do_estado_vivo`.
    """
    le.materialize_launch_env(_daemon(ligado=True))

    env = _env(pasta / "default.env")
    assert _IGNORE not in env and _DISABLE not in env
    assert "pronto_para_troca" not in _estado(pasta / "default.env")


def test_o_perfil_nativo_fora_da_antecipacao_ainda_arranca_o_ignore(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O guarda de 09/08 continua valendo para o NATIVO — lá o vpad não existe
    de propósito, e esconder o físico seria o jogo sem controle nenhum."""
    nativo = SimpleNamespace(
        name="rdr2",
        mode=SimpleNamespace(kind="native"),
        match=SimpleNamespace(
            window_class=[], window_title_regex="RDR", process_name=[]
        ),
    )
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [nativo])

    le.materialize_launch_env(_daemon())

    assert _IGNORE not in _env(pasta / "default.env")
    assert "ignore_omitido=perfil_nativo_sem_appid" in _estado(pasta / "default.env")


def test_um_perfil_de_navegacao_nao_derruba_o_ignore_de_todo_jogo(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O outro lado do guarda: a Navegação SAIU da lista de arriscados.

    Enquanto ela contava, um perfil `desktop` casado por processo — e é o PS + R3
    que grava `desktop` no perfil ativo ao parar na Navegação — deixava o
    `default.env` de TODO jogo sem IGNORE, em qualquer modo.
    """
    navegacao = SimpleNamespace(
        name="navegacao",
        mode=SimpleNamespace(kind="desktop"),
        match=SimpleNamespace(
            window_class=[], window_title_regex=None, process_name=["firefox"]
        ),
    )
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [navegacao])

    le.materialize_launch_env(_daemon())

    assert _IGNORE in _env(pasta / "default.env")


@pytest.mark.parametrize(
    ("coop", "tem_ignore", "caso"),
    [
        (True, True, "co-op ligado: um vpad por físico quando ela subir o modo"),
        (False, False, "co-op desligado: um vpad só, e o segundo físico ficaria escondido"),
    ],
)
def test_a_mesa_de_dois_promete_a_cobertura_que_o_coop_entrega(
    pasta: Path, coop: bool, tem_ignore: bool, caso: str
) -> None:
    le.materialize_launch_env(_daemon(fisicos=2, coop=coop))

    assert (_IGNORE in _env(pasta / "default.env")) is tem_ignore, caso


def test_a_cura_por_estrada_herda_a_regra(pasta: Path) -> None:
    """Heroic, Lutris e os outros lançadores copiam o `default.env`.

    Eles nunca têm `steam_app_<id>`, então é este arquivo que a cura por estrada
    grava no config deles — a mesma conta, num lugar só.
    """
    le.materialize_launch_env(_daemon())

    ambiente = cura_por_estrada.ambiente_da_ponte(pasta)
    assert _IGNORE in ambiente and _DISABLE in ambiente
