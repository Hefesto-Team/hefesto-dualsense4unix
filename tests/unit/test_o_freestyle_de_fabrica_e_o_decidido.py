"""O Freestyle de fábrica é o decidido — o item 1 da O-FREESTYLE-E-UMA-CAMADA-SO-01.

Veio da O-PRODUTO-EM-QUALQUER-MAQUINA-01 (o B6, «L9» do estudo
`2026-09-27-o-basico-e-os-jogos/03-qualquer-maquina.md`): quem chega ganhava o
Freestyle de 24/09, com a vibração sem opinião, o microfone sem seção e as luzes
de número no Fraco. O conteúdo de fábrica é o item 1 da sprint, e um dono só
evita dois «de fábrica».

O QUE O USUÁRIO DISSE, e em que ordem. Nas palavras que abrem a sprint: *«no freestyle a ideia
é tudo estar no ultra até vibração e afins.»* — e o item 1 da sprint o escreveu
campo a campo: vibração no Máximo com o jogo passando, alto-falante no teto,
microfone aberto com o ganho no teto, as luzes no brilho mais forte, os sensores
ligados. Na noite de 27/09 (a resposta 12):  — o Freestyle tem
o que ela configurar, e o «ultra» vale **só como fábrica do arquivo novo**. Esta
régua mede o arquivo novo.

O TETO DE CADA ESCALA É O DA CASA, perguntado ao dono de cada uma — nunca o topo
do `Field`: o alto-falante nasce em `VOLUME_PADRAO_DO_SOM` (onde a curva medida
satura, e não 255), a vibração no degrau «Máximo» da escada
(`RUMBLE_POLICY_MULT`, e não o fim do deslizador), o ganho em
`GANHO_PADRAO_PCT`.

O MODO FICA DE FORA DE PROPÓSITO: o de fábrica é o DualSense da máquina
(`DaemonConfig`), e um `mode` no asset faria o Freestyle, desligado, ligar o pad
no desktop de quem usa o mouse emulado. O Xbox dela é o arquivo dela, e não o
asset (O-PRODUTO, B6).

MORDIDA: devolva ao `assets/profiles_default/freestyle.json` a versão de 24/09
(é a sexta de `loader._FABRICAS_ANTERIORES_DO_FREESTYLE`) e as duas primeiras
réguas reprovam; a terceira prova a mesma coisa sem mexer no disco.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import VOLUME_PADRAO_DO_SOM
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
from hefesto_dualsense4unix.integrations.ganho_do_microfone import GANHO_PADRAO_PCT
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import schema as esquema
from hefesto_dualsense4unix.profiles.schema import Profile

RAIZ = Path(__file__).resolve().parents[2]
FABRICA = RAIZ / "assets" / "profiles_default"
ASSET = FABRICA / "freestyle.json"


def _o_que_falta(perfil: Profile) -> list[str]:
    """O que o perfil tem de diferente do «ultra» decidido. Vazio = é o decidido."""
    falta: list[str] = []
    degrau_maximo = max(RUMBLE_POLICY_MULT, key=lambda nome: RUMBLE_POLICY_MULT[nome])
    if perfil.rumble.policy != degrau_maximo:
        falta.append(f"vibração em {perfil.rumble.policy!r}, e não {degrau_maximo!r}")
    if not perfil.rumble.passthrough:
        falta.append("a vibração do jogo não passa")
    mic = perfil.mic
    if mic is None:
        falta.append("sem a seção do microfone")
    else:
        if mic.muted is not False:
            falta.append(f"microfone mudo={mic.muted!r}, e não aberto")
        if mic.gain != GANHO_PADRAO_PCT:
            falta.append(f"ganho {mic.gain!r}, e não {GANHO_PADRAO_PCT}")
        if mic.volume != 100:
            falta.append(f"volume do microfone {mic.volume!r}, e não 100")
    fala = perfil.speaker
    if fala is None or fala.muted or fala.volume != VOLUME_PADRAO_DO_SOM:
        falta.append(f"alto-falante {fala!r}, e não {VOLUME_PADRAO_DO_SOM} com voz")
    if perfil.leds.lightbar_brightness != 1.0:
        falta.append(f"barra em {perfil.leds.lightbar_brightness}, e não no teto")
    if perfil.leds.player_led_brightness != "forte":
        falta.append(f"luzes de número no {perfil.leds.player_led_brightness!r}")
    for peca, dela in (perfil.controllers or {}).items():
        sensores = dela.sensores
        if sensores is not None and False in (sensores.giroscopio, sensores.acelerometro):
            falta.append(f"sensor desligado em {peca}")
    nascimento = esquema.MODO_DE_NASCIMENTO_DO_GATILHO
    if (perfil.triggers.left.mode, perfil.triggers.right.mode) != (nascimento, nascimento):
        falta.append("os gatilhos não nascem no modo de nascimento do produto")
    return falta


def test_o_asset_e_o_ultra_decidido() -> None:
    """O arquivo que o install e o semeador copiam — lido como o produto o lê."""
    perfil = Profile.model_validate(json.loads(ASSET.read_text(encoding="utf-8")))

    assert _o_que_falta(perfil) == []
    assert perfil.name == loader.NOME_DO_PADRAO
    assert perfil.mode is None, "o modo de fábrica é o da máquina, e não do asset"


def test_o_freestyle_de_um_lar_vazio_nasce_no_ultra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem chega: a semeadura num lar vazio entrega o Freestyle decidido."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)

    nomes = [p.name for p in loader.load_all_profiles()]

    assert nomes == [loader.NOME_DO_PADRAO]
    assert _o_que_falta(loader.load_profile(loader.NOME_DO_PADRAO)) == []


@pytest.mark.parametrize("n", range(6))
def test_nenhuma_fabrica_de_antes_era_o_decidido(n: int) -> None:
    """A mordida sem mexer no disco: a régua reprova cada fábrica de antes."""
    antiga: dict[str, Any] = loader._FABRICAS_ANTERIORES_DO_FREESTYLE[n]

    assert _o_que_falta(Profile.model_validate(antiga)) != []


def test_a_maquina_que_ja_levou_a_fabrica_de_24_09_recebe_o_decidido_uma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O disco de quem já atualizou: a cópia de fábrica de 24/09 e a marca `done`."""
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)
    pasta = profiles_dir(ensure=True)
    de_24_09 = json.dumps(loader._FABRICAS_ANTERIORES_DO_FREESTYLE[5], indent=2)
    (pasta / loader.ARQUIVO_DO_PADRAO).write_text(de_24_09, encoding="utf-8")
    (pasta / loader.SEED_MARKER_NAME).write_text("freestyle.json\n", encoding="utf-8")
    marca = pasta / loader._FREESTYLE_DE_FABRICA_NASCE_LIGADO_MARKER
    marca.write_text("done\n", encoding="utf-8")

    loader.load_all_profiles()

    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == ASSET.read_bytes()
    assert marca.read_text(encoding="utf-8").strip() not in ("", "done")
    assert loader.o_freestyle_de_fabrica_nasce_ligado() is None, "não é one-shot"
