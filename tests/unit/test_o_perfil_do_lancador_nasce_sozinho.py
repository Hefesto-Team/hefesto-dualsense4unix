"""PERFIL-DOS-LANCADORES-E1 (11/09/2026) — todo jogo instalado ganha perfil.

**A QUEIXA DELA, com a foto junto:** digitou ``guar`` na lupa da aba Perfis
procurando *Marvel's Guardians of the Galaxy* — instalado, pelo Heroic — e a
lista voltou vazia, *"27 fora da busca"*.  # noqa-acento: citação literal dela

**A DECISÃO DELA**, posta a escolha entre semear todos, semear ao abrir o jogo
e deixar como estava:

    "2-a e se por algum motivo não encontrar eu posso criar ou criar um perfil
     duplicado do mesmo jogo."  # noqa-acento: citação literal dela

A segunda metade é REQUISITO e não ressalva: criar à mão o que a semeadura não
achou não pode ser recusado nem ser sobrescrito na varredura seguinte.

**A BIBLIOTECA DESTES TESTES É FALSA, SEMPRE.** Nenhum deles lê o Heroic dela
nem escreve no diretório de perfis dela: ou o `dest_dir` é `tmp_path`, ou o
`home` é `tmp_path`, ou os dois. Nenhum abre o piloto nem fala com o daemon
vivo — rodar o piloto dispara as migrações one-shot no `~/.config` REAL dela.
"""
from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import schema as schema_mod
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    e_endereco_de_jogo,
    perfil_e_regra_de_jogo,
)
from hefesto_dualsense4unix.testing import FakeController

#: O jogo REAL do disco dela, medido em 11/09/2026 com o censo:
#: `legendary_library.json` traz `install.executable = "retail/gotg.exe"`, e o
#: basename disso é a `wm_class` que o perfil mira.
GOTG_CHAVE = "gotg.exe"
GOTG_NOME = "Marvel's Guardians of the Galaxy"


def _do_heroic(chave: str, nome: str) -> JogoLocal:
    """Um jogo de lançador como `jogos_dos_lancadores` o entrega: SEM appid."""
    return JogoLocal(
        appid="", nome=nome, fonte="heroic", lancador="Heroic", chave=chave
    )


def _da_steam(appid: str, nome: str) -> JogoLocal:
    return JogoLocal(appid=appid, nome=nome, fonte="steam")


def _perfil_dela(directory: Path, arquivo: str, dados: dict[str, object]) -> bytes:
    """Escreve um perfil "dela" no diretório e devolve os bytes gravados."""
    directory.mkdir(parents=True, exist_ok=True)
    bruto = (json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (directory / arquivo).write_bytes(bruto)
    return bruto


def _linhas_da_marca(directory: Path) -> list[str]:
    marca = directory / loader.MARCA_DE_SEMEADURA_DE_JOGOS
    if not marca.exists():
        return []
    return [ln for ln in marca.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.fixture(autouse=True)
def cadastro_limpo() -> Iterator[None]:
    """O cadastro de classes de jogo é POR PROCESSO — devolve como estava.

    `schema._CLASSES_DE_JOGO_CONHECIDAS` é estado de módulo, e estado de módulo
    que vaza entre testes é a armadilha que esta casa já pagou (*"o dublê
    envenenava outro arquivo por ordem de teste"*). Aqui ele é fotografado
    antes e reposto depois, então a ordem dos testes deixa de importar.
    """
    antes = schema_mod.classes_de_jogo_conhecidas()
    try:
        yield
    finally:
        schema_mod.registrar_classes_de_jogo(antes)


# =============================================================================
# 1. A semeadura passa a ler os outros lançadores
# =============================================================================

def test_o_jogo_do_heroic_ganha_perfil_com_a_classe_da_janela(
    tmp_path: Path,
) -> None:
    """A PROVA É O BYTE: o `.json` no disco, lido com `json.load`."""
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )

    assert resultado.criados == ("marvels_guardians_of_the_galaxy.json",)
    with (destino / "marvels_guardians_of_the_galaxy.json").open(
        encoding="utf-8"
    ) as fh:
        dados = json.load(fh)
    assert dados["name"] == GOTG_NOME
    assert dados["match"] == {
        "type": "criteria",
        "window_class": [GOTG_CHAVE],
        "window_title_regex": None,
        "process_name": [],
    }
    assert dados["priority"] == loader.PRIORIDADE_DO_PERFIL_DE_JOGO == 80
    # O mesmo contrato do perfil da Steam (PERFIS-SAO-PERFIS-01): nome, match e
    # prioridade, e NADA mais — nem cor, nem gatilho, nem modo.
    assert list(dados) == list(loader.CHAVES_DO_PERFIL_DE_JOGO), dados


def test_o_perfil_do_lancador_casa_com_a_janela_do_jogo(tmp_path: Path) -> None:
    """Não basta gravar JSON: o perfil tem de CASAR com a janela — e sem caixa."""
    destino = tmp_path / "perfis"
    loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )

    perfil = Profile.model_validate(
        json.loads(
            (destino / "marvels_guardians_of_the_galaxy.json").read_text(
                encoding="utf-8"
            )
        )
    )

    assert perfil.matches({"wm_class": "gotg.exe"}) is True
    # O `pga.db` do Lutris guarda `GOTG.exe`; a janela pelo Heroic anuncia
    # `gotg.exe`. O matcher do esquema dobra a caixa, e é ele que decide.
    assert perfil.matches({"wm_class": "GOTG.exe"}) is True
    assert perfil.matches({"wm_class": "firefox"}) is False


def test_as_duas_origens_convivem_na_mesma_varredura(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino,
        jogos=[_da_steam("910001", "Ilha de Vidro"), _do_heroic(GOTG_CHAVE, GOTG_NOME)],
    )

    assert sorted(resultado.criados) == [
        "ilha_de_vidro.json",
        "marvels_guardians_of_the_galaxy.json",
    ]
    da_steam = json.loads((destino / "ilha_de_vidro.json").read_text(encoding="utf-8"))
    do_heroic = json.loads(
        (destino / "marvels_guardians_of_the_galaxy.json").read_text(encoding="utf-8")
    )
    assert da_steam["match"]["window_class"] == ["steam_app_910001"]
    assert do_heroic["match"]["window_class"] == [GOTG_CHAVE]


def test_jogo_sem_appid_e_sem_chave_nao_vira_perfil_mudo(tmp_path: Path) -> None:
    """Perfil sem endereço nunca casa com janela nenhuma — é o defeito R-12."""
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino,
        jogos=[JogoLocal(appid="", nome="ROM sem janela", fonte="retroarch")],
    )

    assert resultado.criados == ()
    assert list(destino.glob("*.json")) == []
    assert [r.jogo for r in resultado.por_desfecho("sem_endereco")] == [
        "ROM sem janela"
    ]
    # E a recusa NÃO vira marca: ela pode deixar de valer.
    assert _linhas_da_marca(destino) == []


# =============================================================================
# 2. A marca distingue appid de chave de janela
# =============================================================================

def test_a_marca_escreve_a_chave_de_janela_com_prefixo(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"

    loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )

    assert _linhas_da_marca(destino) == [
        f"{loader.PREFIXO_DA_CHAVE_DE_JANELA}gotg.exe\t"
        "marvels_guardians_of_the_galaxy.json"
    ]
    assert loader.perfis_de_jogo_semeados(dest_dir=destino) == {
        f"{loader.PREFIXO_DA_CHAVE_DE_JANELA}gotg.exe": (
            "marvels_guardians_of_the_galaxy.json"
        )
    }


def test_um_appid_e_uma_chave_iguais_nao_disputam_a_mesma_linha(
    tmp_path: Path,
) -> None:
    """O caso que a sprint nomeia: sem prefixo, os dois viram a MESMA marca.

    Um lançador é livre para usar um número como chave de janela. Sem o
    `janela:` na frente, o jogo da Steam de appid ``910001`` e o jogo de
    lançador cuja janela se chama ``910001`` ocupariam a mesma linha — e o
    segundo sairia como `ja_semeado` sem nunca ter nascido.
    """
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino,
        jogos=[_da_steam("910001", "Da Steam"), _do_heroic("910001", "Do Heroic")],
    )

    assert sorted(resultado.criados) == ["da_steam.json", "do_heroic.json"]
    assert sorted(_linhas_da_marca(destino)) == [
        "910001\tda_steam.json",
        f"{loader.PREFIXO_DA_CHAVE_DE_JANELA}910001\tdo_heroic.json",
    ]


def test_o_perfil_do_lancador_que_ela_apagou_nao_ressuscita(tmp_path: Path) -> None:
    """Mesmo contrato do `.seeded_presets` — e ele só vale se a marca RELER.

    Sem o prefixo, `_linhas_da_marca` descartava a linha (não é dígito), a
    varredura seguinte não via nada tratado e o perfil renascia. É a metade
    silenciosa do defeito: o arquivo voltava depois de ela o apagar.
    """
    destino = tmp_path / "perfis"
    jogos = [_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)
    (destino / "marvels_guardians_of_the_galaxy.json").unlink()

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)

    assert resultado.criados == ()
    assert not (destino / "marvels_guardians_of_the_galaxy.json").exists()
    assert [r.jogo for r in resultado.por_desfecho("ja_semeado")] == [GOTG_NOME]


def test_a_chave_de_janela_na_marca_nao_depende_da_caixa(tmp_path: Path) -> None:
    """`GOTG.exe` (Lutris) e `gotg.exe` (Heroic) são o MESMO jogo."""
    destino = tmp_path / "perfis"
    loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic("GOTG.exe", GOTG_NOME)]
    )

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic("gotg.exe", GOTG_NOME)]
    )

    assert resultado.criados == ()
    assert [r.desfecho for r in resultado.linhas] == ["ja_semeado"]
    assert len(list(destino.glob("*.json"))) == 1


def test_a_marca_do_lancador_sobrevive_a_linha_estragada(tmp_path: Path) -> None:
    """Um `janela:` sozinho não é identidade — e não pode calar o jogo."""
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    (destino / loader.MARCA_DE_SEMEADURA_DE_JOGOS).write_text(
        f"{loader.PREFIXO_DA_CHAVE_DE_JANELA}\tlixo.json\nsem tab nenhum\n",
        encoding="utf-8",
    )

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )

    assert resultado.criados == ("marvels_guardians_of_the_galaxy.json",)


# =============================================================================
# 3. A troca automática aceita perfil de jogo que não é da Steam
# =============================================================================

def test_sem_cadastro_o_predicado_e_exatamente_o_de_antes() -> None:
    """VAZIO = comportamento histórico. É o fail-safe da mudança."""
    schema_mod.registrar_classes_de_jogo([])

    assert e_endereco_de_jogo("steam_app_2111190") is True
    assert e_endereco_de_jogo("gotg.exe") is False
    assert e_endereco_de_jogo("firefox") is False
    assert e_endereco_de_jogo(None) is False


def test_o_perfil_do_heroic_vira_regra_de_jogo_depois_de_declarado() -> None:
    """O ELO DA E1: sem isto o perfil nasce, aparece na lista e não faz nada."""
    perfil = Profile(
        name=GOTG_NOME,
        match=MatchCriteria(window_class=[GOTG_CHAVE]),
        priority=80,
    )
    janela = {"wm_class": GOTG_CHAVE}

    schema_mod.registrar_classes_de_jogo([])
    assert perfil_e_regra_de_jogo(perfil, janela) is False

    schema_mod.registrar_classes_de_jogo([GOTG_CHAVE])
    assert perfil_e_regra_de_jogo(perfil, janela) is True
    # E sem caixa, como o matcher (a janela pode anunciar `GOTG.exe`).
    assert perfil_e_regra_de_jogo(perfil, {"wm_class": "GOTG.exe"}) is True


def test_a_janela_do_proprio_hefesto_nunca_e_regra_de_jogo() -> None:
    """O QUE A LINHA 1799 PROTEGIA — medido no disco dela em 11/09/2026.

    O `personalizado.json` dela mira ``Hefesto-Dualsense4Unix`` com prioridade
    1: a janela DO PRODUTO, gravada ali pelo «Detectar». Afrouxar o predicado
    para "qualquer `window_class` que case" faria focar a janela do Hefesto
    valer como *a regra própria do jogo* — o cadeado cederia e o
    `manual_trigger_active` seria LIMPO em `AutoSwitcher._activate`, pisando no
    gatilho que ela acabou de aplicar na aba que está olhando.

    Foi o ÚNICO perfil do disco dela cujo veredito mudava com a linha solta —
    os outros 26 são todos `steam_app_<id>` e não mudam.
    """
    personalizado = Profile(
        name="Personalizado",
        match=MatchCriteria(window_class=["Hefesto-Dualsense4Unix"]),
        priority=1,
    )
    # Com o cadastro CHEIO — o pior caso, porque é quando o predicado tem a
    # porta aberta para a segunda resposta.
    schema_mod.registrar_classes_de_jogo([GOTG_CHAVE])

    assert e_endereco_de_jogo("Hefesto-Dualsense4Unix") is False
    assert (
        perfil_e_regra_de_jogo(
            personalizado, {"wm_class": "Hefesto-Dualsense4Unix"}
        )
        is False
    )


def test_catch_all_continua_nao_sendo_regra_de_jogo_com_o_cadastro_cheio() -> None:
    """A R-01 inteira: um genérico NUNCA fura, venha a janela de onde vier."""
    schema_mod.registrar_classes_de_jogo([GOTG_CHAVE])
    generico = Profile(name="vitoria", match=MatchAny(), priority=5)
    por_titulo = Profile(
        name="fps",
        match=MatchCriteria(window_title_regex="(Doom|Control)"),
        priority=60,
    )

    assert perfil_e_regra_de_jogo(generico, {"wm_class": GOTG_CHAVE}) is False
    assert perfil_e_regra_de_jogo(por_titulo, {"wm_class": GOTG_CHAVE}) is False


def test_a_semeadura_declara_as_classes_ao_esquema(tmp_path: Path) -> None:
    """Quem responde *"esta janela é de jogo?"* é o censo, e ele responde AQUI."""
    destino = tmp_path / "perfis"
    schema_mod.registrar_classes_de_jogo([])

    loader.semear_perfis_dos_jogos(
        dest_dir=destino,
        jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME), _da_steam("910001", "Ilha")],
    )

    assert GOTG_CHAVE in schema_mod.classes_de_jogo_conhecidas()
    # O jogo da Steam NÃO entra no cadastro: ele tem carimbo próprio, e uma
    # segunda resposta para o mesmo endereço é a duplicata que esta casa paga.
    assert schema_mod.classes_de_jogo_conhecidas() == frozenset({GOTG_CHAVE})


def test_a_classe_declarada_sobrevive_ao_jogo_ja_semeado(tmp_path: Path) -> None:
    """A segunda varredura não cria nada — e ainda assim tem de DECLARAR.

    Sem a metade que lê a MARCA, um daemon que sobe com tudo já semeado
    declararia o conjunto certo só enquanto a biblioteca fosse legível; e o
    jogo recusado por colisão de nome (que continua sendo jogo) nunca entraria.
    """
    destino = tmp_path / "perfis"
    jogos = [_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)

    schema_mod.registrar_classes_de_jogo([])
    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=[])

    assert resultado.criados == ()
    assert schema_mod.classes_de_jogo_conhecidas() == frozenset({GOTG_CHAVE})


# =============================================================================
# 4. Criar à mão o que a semeadura não achou — a segunda metade da frase dela
# =============================================================================

def test_criar_a_mao_um_segundo_perfil_para_o_mesmo_jogo_nao_e_recusado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*"eu posso criar ou criar um perfil duplicado do mesmo jogo"*.

    A prova é em BYTE dos dois lados: o perfil dela nasce no disco com o que
    ela pediu, e o perfil semeado continua com os bytes que tinha.
    """
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )
    semeado = destino / "marvels_guardians_of_the_galaxy.json"
    bytes_do_semeado = semeado.read_bytes()

    caminho = loader.save_profile(
        Profile(
            name="Guardiões do meu jeito",
            match=MatchCriteria(window_class=[GOTG_CHAVE]),
            priority=90,
        ),
        origem="teste",
    )

    assert caminho.is_file(), "criar à mão foi recusado"
    with caminho.open(encoding="utf-8") as fh:
        dela = json.load(fh)
    assert dela["match"]["window_class"] == [GOTG_CHAVE]
    assert dela["priority"] == 90
    # O semeado não foi tocado.
    assert semeado.read_bytes() == bytes_do_semeado
    # E os dois convivem no disco.
    assert sorted(p.name for p in destino.glob("*.json")) == [
        "guardioes_do_meu_jeito.json",
        "marvels_guardians_of_the_galaxy.json",
    ]


def test_a_varredura_seguinte_nao_pisa_no_perfil_que_ela_criou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PROVA EM BYTE: os dois arquivos idênticos depois de três varreduras."""
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    jogos = [_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)
    loader.save_profile(
        Profile(
            name="Guardiões do meu jeito",
            match=MatchCriteria(window_class=[GOTG_CHAVE]),
            priority=90,
        ),
        origem="teste",
    )
    antes = {p.name: p.read_bytes() for p in destino.glob("*.json")}

    for _ in range(3):
        loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)

    depois = {p.name: p.read_bytes() for p in destino.glob("*.json")}
    assert depois == antes


def test_o_perfil_dela_feito_antes_impede_o_semeado_e_fica_intacto(
    tmp_path: Path,
) -> None:
    """Ela criou primeiro: o produto registra que TRATOU e não cria o segundo."""
    destino = tmp_path / "perfis"
    dela = _perfil_dela(
        destino,
        "o_meu_guardioes.json",
        {
            "name": "O meu Guardiões",
            "match": {"type": "criteria", "window_class": ["GOTG.exe"]},
            "priority": 90,
        },
    )

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )

    assert resultado.criados == ()
    assert (destino / "o_meu_guardioes.json").read_bytes() == dela
    ja_tinha = resultado.por_desfecho("ja_tinha_perfil")
    assert [(r.jogo, r.arquivo) for r in ja_tinha] == [
        (GOTG_NOME, "o_meu_guardioes.json")
    ]
    # Registrado na marca SEM arquivo: o produto sabe que tratou, e sabe que o
    # arquivo não é dele.
    assert _linhas_da_marca(destino) == [
        f"{loader.PREFIXO_DA_CHAVE_DE_JANELA}gotg.exe\t"
    ]
    assert loader.perfis_de_jogo_semeados(dest_dir=destino) == {}


def test_a_colisao_de_nome_com_o_perfil_dela_e_recusa_e_nao_sobrescrita(
    tmp_path: Path,
) -> None:
    destino = tmp_path / "perfis"
    dela = _perfil_dela(
        destino,
        "marvels_guardians_of_the_galaxy.json",
        {"name": GOTG_NOME, "match": {"type": "manual"}, "priority": 7},
    )

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )

    assert resultado.criados == ()
    assert (destino / "marvels_guardians_of_the_galaxy.json").read_bytes() == dela
    assert [r.jogo for r in resultado.por_desfecho("nome_ocupado")] == [GOTG_NOME]


def test_a_prioridade_decide_entre_o_dela_e_o_semeado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*"os dois convivem e a prioridade decide qual vence"* — pelo seletor REAL."""
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_do_heroic(GOTG_CHAVE, GOTG_NOME)]
    )
    loader.save_profile(
        Profile(
            name="Guardiões do meu jeito",
            match=MatchCriteria(window_class=[GOTG_CHAVE]),
            priority=90,
        ),
        origem="teste",
    )

    fc = FakeController()
    fc.connect()
    escolhido = ProfileManager(controller=fc).select_for_window(
        {"wm_class": GOTG_CHAVE}
    )

    assert escolhido is not None
    assert escolhido.name == "Guardiões do meu jeito"


# =============================================================================
# A BIBLIOTECA FALSA NO DISCO — o caminho inteiro, sem um dublê
# =============================================================================

def _heroic_de_mentira(casa: Path, itens: list[dict[str, object]]) -> Path:
    """Um `~/.config/heroic/store_cache/legendary_library.json` de mentira."""
    cache = casa / ".config" / "heroic" / "store_cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "legendary_library.json").write_text(
        json.dumps({"library": itens}, ensure_ascii=False), encoding="utf-8"
    )
    return cache


def test_o_jogo_do_heroic_ganha_perfil_sem_dubles(tmp_path: Path) -> None:
    """DO `legendary_library.json` AO `.json` NO DISCO — e é aqui que se morde.

    **A MORDIDA DESTA ENTREGA:** arrancar `jogos_dos_lancadores(home)` da soma
    de `semear_perfis_dos_jogos` faz este teste reprovar, porque ele não injeta
    `jogos` — ele põe a biblioteca no disco e deixa o produto achá-la.

    Este é também o teste das EXCLUSÕES, e cada uma tem razão escrita na
    sprint: o jogo que não está no disco (a biblioteca dela tem 29 e 1
    baixado), o DLC (`install.is_dlc`) e o jogo sem executável — as ROMs dos
    emuladores, que rodam todas no MESMO processo.
    """
    casa = tmp_path / "casa"
    _heroic_de_mentira(
        casa,
        [
            {
                "app_name": "63a665088eb1480298f1e57943b225d8",
                "title": GOTG_NOME,
                "is_installed": True,
                "install": {
                    "executable": "retail/gotg.exe",
                    "install_path": "/jogos/gotg",
                },
            },
            {
                "app_name": "naobaixado",
                "title": "Jogo Não Baixado",
                "is_installed": False,
                "install": {},
            },
            {
                "app_name": "trilha",
                "title": "Trilha Sonora",
                "is_installed": True,
                "install": {"executable": "x/trilha.exe", "is_dlc": True},
            },
            {
                "app_name": "semexe",
                "title": "Jogo Sem Executável",
                "is_installed": True,
                "install": {"install_path": "/jogos/semexe"},
            },
        ],
    )
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)

    assert resultado.criados == ("marvels_guardians_of_the_galaxy.json",)
    assert sorted(p.name for p in destino.glob("*.json")) == [
        "marvels_guardians_of_the_galaxy.json"
    ]
    with (destino / "marvels_guardians_of_the_galaxy.json").open(
        encoding="utf-8"
    ) as fh:
        assert json.load(fh)["match"]["window_class"] == ["gotg.exe"]
    # E o cadastro do esquema saiu declarado pelo mesmo caminho.
    assert schema_mod.classes_de_jogo_conhecidas() == frozenset({"gotg.exe"})


def test_maquina_sem_lancador_nenhum_nao_semeia_nem_reclama(tmp_path: Path) -> None:
    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=tmp_path / "perfis", home=tmp_path / "vazia"
    )

    assert resultado.criados == ()
    assert resultado.linhas == ()


# =============================================================================
# A FIAÇÃO — as três chamadas que fazem isto ser AUTOMÁTICO, e não um botão
# =============================================================================
#
# Palavra dela sobre a semeadura da Steam, e vale igual aqui: *"é automático, e
# não um botão"*. O que faz isto ser automático são três nomes dentro de duas
# funções, e nenhum deles tem efeito observável numa régua hermética — arrancar
# qualquer um deixa a suíte verde e o produto mudo. Então a régua lê a ÁRVORE
# DE SINTAXE e cobra o nome, que é o mesmo idioma de
# `test_a_regua_da_fiacao_pega_a_chamada_arrancada`.


def _chamados_por(alvo: str) -> set[str]:
    """Os nomes CHAMADOS dentro de `alvo`, lidos da árvore de sintaxe.

    Chamados, e não citados: um `from … import jogos_dos_lancadores` que ficou
    para trás depois de alguém apagar a chamada continuaria "citando" o nome, e
    a régua daria verde sobre uma fiação cortada.
    """
    arvore = ast.parse(inspect.getsource(loader))
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == alvo:
            return {
                filho.func.id
                for filho in ast.walk(no)
                if isinstance(filho, ast.Call) and isinstance(filho.func, ast.Name)
            }
    raise AssertionError(f"`{alvo}` sumiu de `loader.py`")


def test_a_semeadura_le_os_lancadores_e_declara_as_classes() -> None:
    chamados = _chamados_por("semear_perfis_dos_jogos")

    assert "jogos_dos_lancadores" in chamados, (
        "a semeadura voltou a ler SÓ a Steam. A decisão dela é que todo jogo "
        "instalado de um lançador que o produto lê ganhe perfil sozinho."
    )
    assert "_declarar_as_classes_de_jogo" in chamados, (
        "a semeadura parou de declarar as classes ao esquema. Sem isso o "
        "perfil do Heroic nasce, aparece na lista e NÃO ENTRA quando ela abre "
        "o jogo — o pior dos dois mundos."
    )


def test_o_gatilho_automatico_assina_as_duas_bibliotecas() -> None:
    chamados = _chamados_por("_talvez_semear_jogos")

    assert "assinatura_da_biblioteca" in chamados
    assert "assinatura_das_bibliotecas" in chamados, (
        "o freio voltou a assinar só a Steam: o jogo que ela baixa pelo Heroic "
        "não ganharia perfil enquanto o daemon estivesse de pé, e o daemon "
        "dela fica dias de pé."
    )


def test_o_jogo_do_heroic_instalado_amanha_e_semeado_sem_reiniciar_o_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O daemon dela fica DIAS de pé — e a biblioteca que muda é a do Heroic.

    **ESTE É O DEFEITO QUE A ASSINATURA SOZINHA DA STEAM DEIXAVA PASSAR:** ela
    baixa um jogo pelo Heroic, o `mtime` da `steamapps` não muda, a assinatura
    dá igual e a varredura volta sem olhar. O jogo só ganharia perfil no
    próximo arranque do daemon.

    A biblioteca falsa mora no `$HOME` do teste — que a `tests/conftest.py`
    desvia para um lar de mentira —, então o caminho inteiro roda sem dublê do
    lado dos lançadores: `_talvez_semear_jogos` chama `assinatura_das_bibliotecas`
    e `jogos_dos_lancadores` de verdade.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais

    casa = Path.home()
    destino = tmp_path / "perfis"
    _heroic_de_mentira(casa, [])
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)
    monkeypatch.setattr(loader, "_assinatura_da_biblioteca_vista", None, raising=False)
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    # A metade da STEAM fica CONGELADA de propósito: se a varredura acontecer,
    # foi a assinatura do Heroic que a acordou.
    monkeypatch.setattr(
        jogos_locais, "assinatura_da_biblioteca", lambda home=None: (("/x", 1),)
    )
    monkeypatch.setattr(jogos_locais, "jogos_da_biblioteca_steam", lambda home=None: [])

    loader._talvez_semear_jogos()
    assert list(destino.glob("*.json")) == []

    # Amanhã: ela baixa o jogo pelo Heroic.
    _heroic_de_mentira(
        casa,
        [
            {
                "app_name": "gotg",
                "title": GOTG_NOME,
                "is_installed": True,
                "install": {"executable": "retail/gotg.exe"},
            }
        ],
    )
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)

    loader._talvez_semear_jogos()

    assert sorted(p.name for p in destino.glob("*.json")) == [
        "marvels_guardians_of_the_galaxy.json"
    ], "a assinatura do Heroic não acordou a varredura"
