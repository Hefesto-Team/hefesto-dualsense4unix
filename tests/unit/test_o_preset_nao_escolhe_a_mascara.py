"""MASCARA-QUE-GRUDA-01 — preset de gênero não tem opinião sobre máscara.

Decisão dela, 22/08/2026, literal:

    *"A máscara deve vir da escolha do user. Ele escolhe como quer que o jogo
    reconheça o controle conectado: se deve aparecer como Xbox ou DualSense."*

Preset é sobre gatilho, vibração e luz. Quem aplica "Ação" não pode descobrir
depois que ele também trocou o aparelho que o jogo enxerga — e desde `2b11172`
a máscara GRUDA no disco até ela mudar, então o efeito não se desfaz sozinho.

NOTA DATADA — 22/08/2026: ESTE ARQUIVO SUBSTITUI O `test_preset_flavor_migration`
--------------------------------------------------------------------------------
Aquele portão exigia o CONTRÁRIO — que todo preset de jogo shipasse `xbox` — e
citava como razão a H1 da auditoria pré-release:

    *"a máscara DualSense faz o jogo ignorar o gamepad virtual (rumble in-game
    morto + controle duplicado)."*

**A H1 não foi refutada: ela continua SEM remedição** (E1 da sprint, que precisa
de um jogo com vibração rodando e da mão dela). O que a derrubou como razão de
portão foi a decisão acima — nem a H1 de pé autoriza o produto a escrever
máscara no perfil de alguém. O que a H1 ganha, enquanto ninguém a remede, é uma
linha na tela dizendo que ela existe e que não foi reconferida
(`profiles_actions.TEXTO_MASCARA_DUALSENSE_VALIDADA`).

E `DEFAULT_FLAVOR = "xbox"` **fica**: ele é o piso do daemon quando ninguém
nunca escolheu, e não uma opinião gravada em arquivo nenhum. São duas perguntas
diferentes, e confundi-las foi o que fez o `xbox` viajar para dentro do disco
dela.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRESETS_DIR = _REPO_ROOT / "assets" / "profiles_default"


def test_nenhum_preset_shipado_escolhe_a_mascara() -> None:
    """Todo preset de fábrica com `mode.kind == "gamepad"` ship `flavor: null`.

    Mordida: pôr `"xbox"` (ou `"dualsense"`) de volta em qualquer um dos sete.
    """
    ofensores: list[str] = []
    gamepads: list[str] = []
    for path in sorted(_PRESETS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = data.get("mode")
        if not (isinstance(mode, dict) and mode.get("kind") == "gamepad"):
            continue
        gamepads.append(path.name)
        if mode.get("gamepad_flavor") is not None:
            ofensores.append(f"{path.name}: {mode.get('gamepad_flavor')!r}")

    # Régua contra o filtro errado: se o glob ou o `kind` mudarem de forma, a
    # lista de ofensores fica vazia por AUSÊNCIA de dado e o teste passaria sem
    # ter olhado nada. Os sete presets de jogo são contados em 22/08/2026.
    assert len(gamepads) >= 7, (
        "o portão não achou os presets de jogo — filtro errado, não aprovação. "
        f"achados: {gamepads}"
    )
    assert not ofensores, (
        "preset de gênero voltou a escolher a máscara por ela. A máscara vem "
        f"do gesto dela, e o preset shipa `null` (= mantém a atual): {ofensores}"
    )


def test_o_null_do_preset_atravessa_o_esquema_intacto() -> None:
    """`gamepad_flavor: null` sobrevive à carga — não vira default no caminho.

    Um portão só sobre o JSON passaria com um esquema que preenchesse `xbox` ao
    ler. Aqui o preset é carregado pelo `Profile` de produção.

    Mordida: dar um default a `ProfileModeConfig.gamepad_flavor`.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    for nome in ("acao", "coop_local", "sackboy_nativo"):  # (noqa-acento) arquivos
        bruto = json.loads((_PRESETS_DIR / f"{nome}.json").read_text(encoding="utf-8"))
        perfil = Profile.model_validate(bruto)
        assert perfil.mode is not None and perfil.mode.kind == "gamepad", nome
        assert perfil.mode.gamepad_flavor is None, (
            f"{nome}: o esquema inventou máscara onde o preset não tem opinião "
            f"({perfil.mode.gamepad_flavor!r})"
        )


def test_a_semeadura_nao_reescreve_a_mascara_de_quem_ja_tem_perfil() -> None:
    """Nenhuma migração one-shot escreve máscara em perfil que já existe.

    É o portão que impede alguém de "consertar" os perfis dela mais tarde. Os
    quatro que pedem `xbox` no disco dela (Ação, Aventura, Co-op local e
    Corrida, lidos em 22/08/2026) podem tê-lo ESCOLHIDO: o preset shipava
    `xbox` E o seletor grava `xbox`, e nada no arquivo separa os dois casos.
    Uma migração inversa desfaria em silêncio uma escolha real — o defeito
    desta sprint com o sinal trocado.

    Roda TODAS as migrações que o `_maybe_seed_presets` dispara, na ordem dele,
    contra um diretório de mentira. Mordida: chamar aqui qualquer função que
    escreva `gamepad_flavor`.
    """
    from hefesto_dualsense4unix.profiles import loader

    d = Path(tempfile.mkdtemp())
    # Um perfil por caso que importa: máscara dela, máscara oposta, sem opinião.
    casos = {
        "coop_local.json": "xbox",
        "sackboy_nativo.json": "dualsense",
        "acao.json": None,
    }
    for arquivo, mascara in casos.items():
        (d / arquivo).write_text(
            json.dumps(
                {
                    "name": arquivo[:-5],
                    "mode": {"kind": "gamepad", "gamepad_flavor": mascara},
                }
            ),
            encoding="utf-8",
        )

    migracoes = [
        loader.migrate_profiles_coop_default,
        loader.migrate_coop_local_match,
        loader.migrate_modo_jogo_nos_presets,
    ]
    for migracao in migracoes:
        migracao(d)

    for arquivo, mascara in casos.items():
        depois = json.loads((d / arquivo).read_text(encoding="utf-8"))
        assert depois["mode"]["gamepad_flavor"] == mascara, (
            f"{arquivo}: uma migração reescreveu a máscara "
            f"({mascara!r} -> {depois['mode']['gamepad_flavor']!r}). Máscara é "
            "escolha dela, e desde `2b11172` ela gruda"
        )


def test_a_migracao_que_impunha_xbox_nao_existe_mais() -> None:
    """A `migrate_game_presets_to_xbox` saiu, e não volta por engano.

    Ela era chamada pelo `_maybe_seed_presets` a cada primeira carga, e trocava
    `dualsense`->`xbox` no disco de quem ainda não tinha o marker. Manter a
    função sem chamador seria pior que apagá-la: esta casa já foi mordida pela
    cura escrita e nunca ligada, e pela cura ligada e nunca notada.

    Mordida: reintroduzir a função (ou qualquer nome novo que escreva máscara
    em disco a partir da semeadura).
    """
    import inspect

    from hefesto_dualsense4unix.profiles import loader

    assert not hasattr(loader, "migrate_game_presets_to_xbox"), (
        "a migração que impunha xbox voltou ao loader"
    )

    fonte = inspect.getsource(loader._maybe_seed_presets)
    assert "flavor" not in fonte.lower(), (
        "a semeadura voltou a mexer em máscara:\n" + fonte
    )
