"""PERFIS-SAO-PERFIS-01 — gênero não é perfil, e perfil de jogo tem nome e id.

Decisão dela, 06/09/2026, literal:

    *"os perfis que voltaram não fazem sentido. ação, aventura, corrida. Isso
    não é perfil, isso é estilo de jogo."*

    Sobre os gêneros: **"somem da lista e da semeadura"** — os arquivos ficam.
    Sobre os 24 por jogo: *"ficam se o sistema antigo tiver sido adaptado pro
    novo sistema de perfis. caso contrário mantemos só o nome e o id pra eu
    reconfigurar um a um."*

O CENTRO DO RISCO É O DISCO DELA, e o número que o define foi medido em
06/09: **33 perfis** — 8 de gênero, o `personalizado` e 24 por jogo, todos de
29/08 23:02. Esta sprint MOVE coisa de lugar nesse disco, então a pergunta que
cada régua abaixo responde não é *"a lista encolheu?"* e sim **"o que ela tinha
continua no disco e continua abrindo?"**.

TUDO HERMÉTICO: destino sempre injetado por `dest_dir`/`tmp_path`, e o
`conftest` já desvia `HOME` e os quatro `XDG_*`. Nenhuma linha aqui escreve no
`~/.config` real — a única leitura do repositório é dos assets versionados.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile

REPO = Path(__file__).resolve().parents[2]
FABRICA = REPO / "assets" / "profiles_default"
ESTILOS = REPO / "assets" / "estilos_de_jogo"


def _molde_de_jogo(nome: str, appid: str, **extra: object) -> dict:
    """O perfil de jogo COMO ELE ESTÁ no disco dela hoje — o molde de 29/08.

    Reconstruído pelo produto (`_perfil_do_jogo` + `_payload_do_perfil`) em vez
    de digitado: uma cópia à mão do molde envelheceria calada no dia em que o
    esquema ganhasse um campo, e a régua passaria a medir o mundo de ontem.
    """
    perfil = Profile(
        name=nome,
        match={"type": "criteria", "window_class": [f"steam_app_{appid}"]},
        priority=loader.PRIORIDADE_DO_PERFIL_DE_JOGO,
    )
    dados = loader._payload_do_perfil(perfil)
    dados.update(extra)
    return dados


def _escrever(path: Path, dados: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", "utf-8")


# =============================================================================
# PASSO 1 — a semeadura só conhece o Personalizado
# =============================================================================

def test_a_semeadura_so_conhece_o_personalizado(tmp_path: Path) -> None:
    """Semear num diretório vazio, com a fábrica de hoje, produz UM arquivo.

    MORDE: devolver qualquer um dos oito gêneros a `assets/profiles_default/`.
    """
    destino = tmp_path / "perfis"

    copiados = loader.seed_default_presets(dest_dir=destino, source_dirs=[FABRICA])

    assert copiados == ["personalizado.json"], (
        "a semeadura de fábrica entregou mais que o Personalizado: "
        f"{copiados} — gênero não é perfil (decisão dela, 06/09/2026)"
    )
    assert sorted(p.name for p in destino.glob("*.json")) == ["personalizado.json"]


def test_os_oito_estilos_sairam_da_fabrica_e_moram_na_casa_deles() -> None:
    """Os arquivos FICAM — mudaram de pasta, não sumiram da árvore."""
    assert sorted(p.name for p in ESTILOS.glob("*.json")) == sorted(
        loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO
    ), "assets/estilos_de_jogo/ não tem os oito gêneros que a fábrica perdeu"
    for arquivo in loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO:
        assert not (FABRICA / arquivo).exists(), (
            f"{arquivo} voltou para a semeadura — ele é Estilo de Jogo, não perfil"
        )


# =============================================================================
# PASSO 2 — o gênero intocado sai da LISTA; o que ela editou fica
# =============================================================================

def test_o_genero_intocado_sai_da_lista_e_o_que_ela_editou_fica(
    tmp_path: Path,
) -> None:
    """As duas réguas no mesmo teste, que é onde a diferença aparece.

    `acao.json` intocado (byte a byte o de fábrica) vai para a subpasta;
    `fps.json` com a cor dela dentro FICA na lista, inteiro.

    MORDE: fazer a migração mover pelo NOME em vez de comparar com a fábrica —
    o `fps` dela iria junto, e ela perderia a configuração sem um aviso.
    """
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    (destino / "acao.json").write_bytes((ESTILOS / "acao.json").read_bytes())
    fps_dela = json.loads((ESTILOS / "fps.json").read_text(encoding="utf-8"))
    fps_dela["leds"]["lightbar"] = [10, 20, 30]
    _escrever(destino / "fps.json", fps_dela)

    resultado = loader.migrar_generos_para_estilos_de_jogo(dest_dir=destino)

    assert resultado.movidos == ("acao.json",), resultado
    assert resultado.dela == ("fps.json",), (
        "a migração não nomeou o arquivo que ela editou — mexer calado num "
        f"perfil dela é o defeito que esta régua existe para pegar: {resultado}"
    )
    # A lista da aba Perfis é o `glob("*.json")` do diretório, sem recursão.
    na_lista = sorted(p.name for p in destino.glob("*.json"))
    assert na_lista == ["fps.json"], na_lista
    # E o dela continua com a cor que ela escolheu.
    guardado = json.loads((destino / "fps.json").read_text(encoding="utf-8"))
    assert guardado["leds"]["lightbar"] == [10, 20, 30]


def test_nenhum_byte_sai_do_disco_e_o_estilo_continua_carregavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nada se perdeu: o arquivo está na subpasta, e `load_profile` o abre.

    A segunda metade é a que importa de verdade. O `session.json` e o
    `active_profile.txt` dela guardam o NOME do último perfil ativado; se ela
    tinha `navegacao` ativo, um `load_profile` que não olhasse a subpasta faria
    o boot cair sem perfil.

    MORDE: arrancar a última camada de busca de `load_profile`.
    """
    destino = loader.profiles_dir(ensure=True)
    original = (ESTILOS / "navegacao.json").read_bytes()
    (destino / "navegacao.json").write_bytes(original)

    resultado = loader.migrar_generos_para_estilos_de_jogo(dest_dir=destino)

    assert resultado.movidos == ("navegacao.json",)
    guardado = destino / loader.ESTILOS_DE_JOGO_DIR_NAME / "navegacao.json"
    assert guardado.is_file(), "o arquivo foi APAGADO — a migração é irreversível"
    assert guardado.read_bytes() == original, "o arquivo mudou ao mudar de pasta"
    assert not (destino / "navegacao.json").exists()
    # Fora da lista…
    assert [p.name for p in destino.glob("*.json")] == []
    assert loader.load_all_profiles() == []
    # …e ainda assim carregável pelo nome que ela ativou.
    perfil = loader.load_profile("navegacao")
    assert perfil.name == json.loads(original.decode("utf-8"))["name"]


def test_o_genero_que_o_produto_reformatou_ainda_conta_como_de_fabrica(
    tmp_path: Path,
) -> None:
    """Bytes diferentes, JSON igual: quem reformatou foi o PRODUTO, não ela.

    `migrate_modo_jogo_nos_presets` regrava os cinco de gênero com
    `json.dumps(indent=2)` ao levar-lhes o `mode`. Uma régua byte a byte
    marcaria esses arquivos como "editados por ela" e os oito ficariam na lista
    para sempre justamente na máquina de quem instalou o produto mais cedo.
    """
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    dados = json.loads((ESTILOS / "corrida.json").read_text(encoding="utf-8"))
    # Mesmos valores, formatação de outro escritor.
    (destino / "corrida.json").write_text(json.dumps(dados), encoding="utf-8")
    assert (destino / "corrida.json").read_bytes() != (
        ESTILOS / "corrida.json"
    ).read_bytes()

    resultado = loader.migrar_generos_para_estilos_de_jogo(dest_dir=destino)

    assert resultado.movidos == ("corrida.json",), resultado


def test_sem_o_asset_de_fabrica_a_migracao_recua_e_diz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem com o que comparar, não se mexe — e o journal fica sabendo.

    É o mesmo contrato de `migracao_aposentada_sem_asset` das duas migrações
    vizinhas: adivinhar se ela editou seria mover perfil dela no escuro.
    """
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    (destino / "acao.json").write_bytes((ESTILOS / "acao.json").read_bytes())
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", ())
    monkeypatch.setattr(loader, "_ESTILO_DE_JOGO_SOURCE_DIRS", ())

    resultado = loader.migrar_generos_para_estilos_de_jogo(dest_dir=destino)

    assert resultado.movidos == ()
    assert resultado.sem_fabrica == ("acao.json",), resultado
    assert (destino / "acao.json").is_file()


def test_a_migracao_dos_generos_e_one_shot(tmp_path: Path) -> None:
    """Ela devolveu o `acao.json` à lista: a migração não o leva de novo.

    (noqa-acento: `acao` é nome literal de arquivo.)
    """
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    (destino / "acao.json").write_bytes((ESTILOS / "acao.json").read_bytes())
    assert loader.migrar_generos_para_estilos_de_jogo(dest_dir=destino).movidos == (
        "acao.json",
    )

    (destino / "acao.json").write_bytes((ESTILOS / "acao.json").read_bytes())
    segunda = loader.migrar_generos_para_estilos_de_jogo(dest_dir=destino)

    assert segunda.movidos == (), "a migração não é one-shot — ela roda para sempre"
    assert (destino / "acao.json").is_file()


# =============================================================================
# PASSO 3 — o perfil de jogo intocado fica só com nome, id e prioridade
# =============================================================================

def test_o_perfil_de_jogo_enxuga_so_quando_e_o_molde(tmp_path: Path) -> None:
    """As duas réguas no mesmo teste, como manda a sprint.

    `stray` é o molde de 29/08 → vira três chaves. `peak` tem um `leds`
    diferente do molde → não é tocado, byte a byte.

    MORDE: tirar a comparação com o molde de `_e_perfil_de_jogo_intocado` — o
    `peak` perderia a cor que ela escolheu.
    """
    destino = tmp_path / "perfis"
    _escrever(destino / "stray.json", _molde_de_jogo("Stray", "1332010"))
    dela = _molde_de_jogo("PEAK", "3527290")
    dela["leds"] = {**dela["leds"], "lightbar": [200, 0, 40]}
    _escrever(destino / "peak.json", dela)
    peak_antes = (destino / "peak.json").read_bytes()

    enxutos = loader.enxugar_perfis_de_jogo(dest_dir=destino)

    assert enxutos == ["stray.json"], enxutos
    stray = json.loads((destino / "stray.json").read_text(encoding="utf-8"))
    assert list(stray) == list(loader.CHAVES_DO_PERFIL_DE_JOGO), stray
    assert stray["name"] == "Stray"
    assert stray["match"]["window_class"] == ["steam_app_1332010"]
    assert stray["priority"] == loader.PRIORIDADE_DO_PERFIL_DE_JOGO
    assert (destino / "peak.json").read_bytes() == peak_antes, (
        "o perfil com a cor DELA foi reescrito — é exatamente o que ela pediu "
        "para não acontecer: *'ficam se o sistema antigo tiver sido adaptado'*"
    )


def test_o_arquivo_enxuto_carrega_o_mesmo_perfil_de_antes(tmp_path: Path) -> None:
    """Nada muda de comportamento: o que saiu era o default do esquema.

    Esta é a régua que autoriza a migração a existir. Se enxugar mudasse UM
    campo do `Profile` carregado, seria perda de configuração disfarçada de
    limpeza.
    """
    destino = tmp_path / "perfis"
    _escrever(destino / "stray.json", _molde_de_jogo("Stray", "1332010"))
    antes = Profile.model_validate(
        json.loads((destino / "stray.json").read_text(encoding="utf-8"))
    )

    loader.enxugar_perfis_de_jogo(dest_dir=destino)

    depois = Profile.model_validate(
        json.loads((destino / "stray.json").read_text(encoding="utf-8"))
    )
    assert depois == antes, "o perfil carregado mudou — isto não é enxugar, é perder"


def test_o_perfil_que_nao_e_de_jogo_nao_e_tocado(tmp_path: Path) -> None:
    """O `match` decide, e ele tem de ser UM `steam_app_<n>` e nada mais.

    O `personalizado` (catch-all) e um perfil com `process_name` junto ficam
    inteiros: o segundo é regra que ela escreveu à mão.
    """
    destino = tmp_path / "perfis"
    _escrever(destino / "personalizado.json", json.loads(
        (FABRICA / "personalizado.json").read_text(encoding="utf-8")
    ))
    dela = _molde_de_jogo("Faith", "1179080")
    dela["match"] = {**dela["match"], "process_name": ["faith.exe"]}
    _escrever(destino / "faith.json", dela)
    antes = {p.name: p.read_bytes() for p in destino.glob("*.json")}

    assert loader.enxugar_perfis_de_jogo(dest_dir=destino) == []

    assert {p.name: p.read_bytes() for p in destino.glob("*.json")} == antes


# =============================================================================
# PASSO 4 — quem semeia jogo passa a semear só nome e id
# =============================================================================

def test_o_perfil_de_jogo_novo_nasce_so_com_nome_e_id(tmp_path: Path) -> None:
    """O mesmo contrato do Passo 3 aplicado ao futuro.

    MORDE: devolver `_payload_do_perfil` a `_semear_um_jogo` — o perfil volta a
    nascer com cinco chaves copiadas do default do esquema, que é o que fazia
    os 24 dela parecerem configurados sem nenhuma escolha dela dentro.
    """
    destino = tmp_path / "perfis"
    jogos = [JogoLocal(appid="1332010", nome="Stray", fonte="steam")]

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)

    assert resultado.criados == ("stray.json",), resultado
    gravado = json.loads((destino / "stray.json").read_text(encoding="utf-8"))
    assert list(gravado) == list(loader.CHAVES_DO_PERFIL_DE_JOGO), gravado
    # E continua sendo um perfil válido, com o id do jogo dentro.
    perfil = Profile.model_validate(gravado)
    assert perfil.name == "Stray"
    assert perfil.match.window_class == ["steam_app_1332010"]
    assert perfil.priority == loader.PRIORIDADE_DO_PERFIL_DE_JOGO


def test_o_perfil_novo_ja_nasce_enxuto_e_a_migracao_nao_o_reescreve(
    tmp_path: Path,
) -> None:
    """Passo 3 e Passo 4 são o MESMO contrato — a régua prova que fecham."""
    destino = tmp_path / "perfis"
    loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[JogoLocal(appid="851100", nome="Touhou", fonte="steam")]
    )
    antes = (destino / "touhou.json").read_bytes()

    loader.enxugar_perfis_de_jogo(dest_dir=destino)

    assert (destino / "touhou.json").read_bytes() == antes
