"""PERFIL-PADRAO-PERSONALIZADO-01 — o padrão deixa de se chamar `meu_perfil`.

Decisão dela, 05/09/2026, literal:

    *"Meu_perfil como perfil default nao deveria existir. Deixa ou Meu Perfil  noqa-acento
    ou Personalizado. acho esse melhor. fora que ao abrir o programa ele deve
    iniciar com o ultimo perfil ativado. ate eu alterar novamente e ativar  noqa-acento
    outro perfil"*

Este arquivo cobre a PRIMEIRA metade (o nome). A segunda vive em
`test_perfil_padrao_personalizado_02.py`.

O CENTRO DO RISCO É O DISCO DELA, e o número que o define foi medido na
máquina dela em 05/09: **33 perfis, e só DOIS são catch-all** — `fallback`
(prioridade 0) e `meu_perfil` (prioridade 1). O `meu_perfil.json` dela não é o
asset de fábrica: carrega os ajustes por controle (lightbar vermelha num, azul
no outro, políticas de rumble diferentes). Semear o `personalizado.json` de
fábrica por cima disso daria a ela DOIS padrões disputando o controle — que é
o que `profiles.sanidade` (`MAX_CATCH_ALL_TOLERADOS = 1`) chama de
configuração já machucando.

Por isso o teste central aqui não é "o nome mudou": é **o conteúdo dela
sobreviveu à mudança de nome, e não nasceu um segundo catch-all**.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.loader import (
    ARQUIVO_ANTIGO_DO_PADRAO,
    ARQUIVO_DO_PADRAO,
    BACKUP_DO_PADRAO,
    NOME_DO_PADRAO,
    SEED_MARKER_NAME,
    migrate_default_profile_name,
    seed_default_presets,
)

#: O `meu_perfil.json` DELA, reduzido ao que importa aqui: ele não é o asset de
#: fábrica. Os ajustes por controle são o dado que a migração tem de preservar
#: byte a byte — os uniq vão mascarados (regra da casa: nada de MAC real).
PERFIL_DELA: dict = {
    "name": "meu_perfil",
    "version": 1,
    "match": {"type": "any"},
    "priority": 1,
    "triggers": {
        "left": {"mode": "Off", "params": []},
        "right": {"mode": "Off", "params": []},
    },
    "leds": {
        "lightbar": [40, 80, 180],
        "player_leds": [False, False, True, False, False],
        "lightbar_brightness": 1.0,
        "auto_player_colors": True,
    },
    "rumble": {"passthrough": True, "policy": None, "custom_mult": None},
    "suppress_desktop_emulation": False,
    "controllers": {
        "d42f4b000000": {
            "leds": {"lightbar": [255, 0, 0]},
            "rumble": {"policy": "balanceado"},
        },
        "444648000000": {
            "leds": {"lightbar": [0, 0, 255]},
            "rumble": {"policy": "max"},
        },
    },
}


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """Um diretório de perfis vazio, isolado do disco de qualquer pessoa."""
    d = tmp_path / "profiles"
    d.mkdir()
    return d


def _grava(directory: Path, nome: str, dados: dict) -> Path:
    caminho = directory / nome
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return caminho


def _fonte_de_fabrica(tmp_path: Path) -> Path:
    """O `assets/profiles_default/` de fábrica, com o preset novo dentro."""
    fonte = tmp_path / "fabrica"
    fonte.mkdir()
    _grava(
        fonte,
        ARQUIVO_DO_PADRAO,
        {
            "name": NOME_DO_PADRAO,
            "version": 1,
            "match": {"type": "any"},
            "priority": 1,
        },
    )
    return fonte


# ---------------------------------------------------------------------------
# O que ela ganha: o nome muda e o conteúdo NÃO
# ---------------------------------------------------------------------------


def test_o_perfil_dela_muda_de_nome_sem_perder_uma_linha(disco: Path) -> None:
    """O caso dela, fim a fim: renomeia e o conteúdo sai idêntico.

    A comparação é do dicionário INTEIRO menos a chave `name` — não de um par
    de campos escolhidos a dedo. Uma migração que reescrevesse o perfil a
    partir do asset de fábrica (o caminho errado óbvio) passaria num teste que
    só olhasse `name` e `priority`, e apagaria os ajustes por controle dela.
    """
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)

    assert migrate_default_profile_name(disco) == NOME_DO_PADRAO

    novo = json.loads((disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8"))
    assert novo["name"] == NOME_DO_PADRAO
    esperado = {k: v for k, v in PERFIL_DELA.items() if k != "name"}
    assert {k: v for k, v in novo.items() if k != "name"} == esperado


def test_o_arquivo_antigo_fica_no_disco_e_some_da_lista(disco: Path) -> None:
    """"Guardando o antigo" — e guardado onde leitor nenhum tropece nele.

    O backup não pode terminar em `.json`: todo leitor de perfil desta casa
    varre `glob("*.json")`, e um backup visível seria justamente o segundo
    catch-all que a migração existe para evitar.
    """
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)

    migrate_default_profile_name(disco)

    backup = disco / BACKUP_DO_PADRAO
    assert backup.is_file(), "o perfil antigo dela não pode simplesmente sumir"
    assert json.loads(backup.read_text(encoding="utf-8")) == PERFIL_DELA
    assert not (disco / ARQUIVO_ANTIGO_DO_PADRAO).exists()
    assert sorted(p.name for p in disco.glob("*.json")) == [ARQUIVO_DO_PADRAO]


def test_a_sessao_segue_o_nome_novo(
    disco: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A metade A não pode quebrar a metade B.

    `session.json` e `active_profile.txt` guardam o NOME do último perfil que
    ela ativou na mão, e é por esse nome que o daemon restaura no boot. Sem
    repontar os dois, renomear o perfil deixaria o boot procurando um arquivo
    que não existe mais — e ela abriria o programa SEM perfil nenhum.
    """
    from hefesto_dualsense4unix.utils import session, xdg_paths

    lar = tmp_path / "config"
    lar.mkdir()
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: lar)
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: lar)

    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    session.save_last_profile("meu_perfil")
    session.save_active_marker("meu_perfil")

    migrate_default_profile_name(disco)

    assert session.load_last_profile() == NOME_DO_PADRAO
    assert session.read_active_marker() == NOME_DO_PADRAO
    assert session.resolve_boot_profile() == NOME_DO_PADRAO


def test_a_sessao_que_aponta_outro_perfil_nao_e_tocada(
    disco: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Repontar é só para quem apontava o nome antigo — nada além disso."""
    from hefesto_dualsense4unix.utils import session, xdg_paths

    lar = tmp_path / "config"
    lar.mkdir()
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: lar)
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: lar)

    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    session.save_last_profile("Black Myth: Wukong")
    session.save_active_marker("Black Myth: Wukong")

    migrate_default_profile_name(disco)

    assert session.load_last_profile() == "Black Myth: Wukong"
    assert session.read_active_marker() == "Black Myth: Wukong"


# ---------------------------------------------------------------------------
# As quatro recusas — cada uma protege um disco que já existe
# ---------------------------------------------------------------------------


def test_recusa_quando_ela_ja_tem_um_perfil_personalizado(disco: Path) -> None:
    """Ela mesma criou um "Personalizado". Sobrescrever seria destruir dado."""
    dela = {"name": "Personalizado", "version": 1, "match": {"type": "any"},
            "priority": 42}
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    _grava(disco, ARQUIVO_DO_PADRAO, dela)

    assert migrate_default_profile_name(disco) is None

    assert json.loads(
        (disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")
    ) == dela
    assert (disco / ARQUIVO_ANTIGO_DO_PADRAO).is_file()


def test_recusa_quando_ela_ja_renomeou_o_perfil_na_mao(disco: Path) -> None:
    """O arquivo é `meu_perfil.json` mas o NOME lá dentro é dela.

    Caso real desta casa: `load_profile` acha por slug E por varredura, então
    um arquivo cujo filename não acompanhou o `name` é normal. Trocar o nome
    dele aqui seria renomear um perfil que ela já batizou.
    """
    dela = dict(PERFIL_DELA, name="Meu jeito")
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, dela)

    assert migrate_default_profile_name(disco) is None

    assert json.loads(
        (disco / ARQUIVO_ANTIGO_DO_PADRAO).read_text(encoding="utf-8")
    ) == dela
    assert not (disco / ARQUIVO_DO_PADRAO).exists()


def test_recusa_em_json_ilegivel_sem_explodir(disco: Path) -> None:
    """Perfil corrompido não pode derrubar a carga de perfil de ninguém."""
    (disco / ARQUIVO_ANTIGO_DO_PADRAO).write_text("{ não é json", encoding="utf-8")

    assert migrate_default_profile_name(disco) is None
    assert (disco / ARQUIVO_ANTIGO_DO_PADRAO).is_file()


def test_e_one_shot(disco: Path) -> None:
    """Rodou uma vez, não roda de novo — nem se o nome antigo reaparecer.

    Vale para o caso em que ela restaura um backup velho: a migração não pode
    ficar renomeando o disco dela a cada carga de perfil.
    """
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    assert migrate_default_profile_name(disco) == NOME_DO_PADRAO

    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    assert migrate_default_profile_name(disco) is None
    assert (disco / ARQUIVO_ANTIGO_DO_PADRAO).is_file()


def test_maquina_nova_nao_tem_o_que_migrar(disco: Path) -> None:
    """Sem `meu_perfil.json`, a migração é no-op e o semeador faz o trabalho."""
    assert migrate_default_profile_name(disco) is None
    assert not (disco / ARQUIVO_DO_PADRAO).exists()


# ---------------------------------------------------------------------------
# A rede embaixo da migração: o semeador não pode criar o segundo catch-all
# ---------------------------------------------------------------------------


def test_o_semeador_nao_entrega_o_segundo_catch_all(
    disco: Path, tmp_path: Path
) -> None:
    """A rede: `install.sh` semeia ANTES de qualquer Python carregar perfil.

    Sem esta recusa, quem atualizasse o produto pelo caminho normal ganharia
    `personalizado.json` de fábrica AO LADO do `meu_perfil.json` dela: dois
    catch-all com a mesma prioridade 1, e quem chega ao controle vira sorteio
    (é a descrição literal de `profiles.sanidade`).
    """
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)

    copiados = seed_default_presets(
        dest_dir=disco, source_dirs=(_fonte_de_fabrica(tmp_path),)
    )

    assert copiados == []
    assert sorted(p.name for p in disco.glob("*.json")) == [
        ARQUIVO_ANTIGO_DO_PADRAO
    ]
    # E fica registrado, senão a próxima semeadura tentaria de novo.
    marker = (disco / SEED_MARKER_NAME).read_text(encoding="utf-8").splitlines()
    assert ARQUIVO_DO_PADRAO in marker


def test_maquina_nova_recebe_o_preset_de_fabrica(
    disco: Path, tmp_path: Path
) -> None:
    """Par da recusa acima: sem o arquivo antigo, o preset novo É semeado.

    Esta é a metade que a recusa poderia matar por engano — um `continue`
    largo demais deixaria toda máquina nova sem perfil padrão nenhum.
    """
    copiados = seed_default_presets(
        dest_dir=disco, source_dirs=(_fonte_de_fabrica(tmp_path),)
    )

    assert copiados == [ARQUIVO_DO_PADRAO]
    semeado = json.loads(
        (disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")
    )
    assert semeado["name"] == NOME_DO_PADRAO


def test_depois_da_migracao_o_semeador_nao_sobrescreve_o_dela(
    disco: Path, tmp_path: Path
) -> None:
    """A ordem de `_maybe_seed_presets`: migra e SÓ ENTÃO semeia.

    Depois da renomeação o `personalizado.json` do destino é o arquivo DELA. O
    semeador tem de cair no ramo "presente na 1ª execução" e registrar sem
    copiar — o asset nu de fábrica não pode encostar nele.
    """
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    migrate_default_profile_name(disco)

    copiados = seed_default_presets(
        dest_dir=disco, source_dirs=(_fonte_de_fabrica(tmp_path),)
    )

    assert copiados == []
    depois = json.loads((disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8"))
    assert depois["controllers"] == PERFIL_DELA["controllers"]


# ---------------------------------------------------------------------------
# O asset de fábrica: o nome que ela lê na lista
# ---------------------------------------------------------------------------


def test_o_asset_versionado_nao_carrega_mais_o_slug() -> None:
    """O que uma instalação nova entrega: nome de gente, não slug.

    O portão que fecha a decisão dela do lado do repositório — não adianta a
    migração se o asset voltar a nascer com `meu_perfil`.
    """
    raiz = Path(__file__).resolve().parents[2]
    fabrica = raiz / "assets" / "profiles_default"

    assert not (fabrica / ARQUIVO_ANTIGO_DO_PADRAO).exists()
    dados = json.loads(
        (fabrica / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")
    )
    assert dados["name"] == NOME_DO_PADRAO

    # E continua sendo UM catch-all só entre os presets: o `fallback` (0) e o
    # padrão (1). Um terceiro `any` aqui reabriria a disputa por sorteio.
    catch_all = []
    for caminho in sorted(fabrica.glob("*.json")):
        dado = json.loads(caminho.read_text(encoding="utf-8"))
        if dado.get("match", {}).get("type") == "any":
            catch_all.append((caminho.name, dado.get("priority")))
    assert catch_all == [("fallback.json", 0), (ARQUIVO_DO_PADRAO, 1)]
