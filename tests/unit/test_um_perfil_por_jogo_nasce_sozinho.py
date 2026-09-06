"""UM-PERFIL-POR-JOGO-01 (22/08/2026) — o perfil do jogo nasce sozinho.

Decisão dela, literal: *"acho que por default já deveria ter um perfil por jogo
instalado. Por default na nossa lista, e lá eu só ativaria o perfil do jogo,
sairia modificando as abas pra setar o perfil, salvaria e aplicaria, e todas as
próximas vezes esse jogo automaticamente abriria com o perfil aplicado pra
todos os controles."*

**A biblioteca destes testes é FALSA, sempre.** Nenhum deles lê a `steamapps`
dela nem escreve no diretório de perfis dela: ou o `dest_dir` é `tmp_path`, ou
o `home` é `tmp_path`, ou os dois. O cuidado é medido — 15 perfis na pasta dela
em 06/08, e apagar perfil é o estrago que a leva de 05/08 passou uma semana
consertando.
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import jogos_locais
from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.profiles import loader


def _jogo(appid: str, nome: str) -> JogoLocal:
    return JogoLocal(appid=appid, nome=nome, fonte="steam")


#: A biblioteca falsa padrão. Nomes inventados, appids sintéticos.
TRES_JOGOS = (
    _jogo("910001", "Ilha de Vidro"),
    _jogo("910002", "Corrida Sem Fim"),
    _jogo("910003", "O Jardim Fechado"),
)


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


# =============================================================================
# O perfil nasce — e nasce com o quê
# =============================================================================

def test_cada_jogo_da_biblioteca_ganha_um_perfil(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    assert sorted(resultado.criados) == [
        "corrida_sem_fim.json",
        "ilha_de_vidro.json",
        "o_jardim_fechado.json",
    ]
    for arquivo in resultado.criados:
        assert (destino / arquivo).is_file()


def test_o_perfil_nasce_com_nome_appid_e_prioridade_e_nada_mais(
    tmp_path: Path,
) -> None:
    """Nome do jogo, `match` pelo appid, prioridade 80 — e SEM opinião no resto.

    "Um perfil semeado que já venha com cor e gatilho decididos seria o produto
    escolhendo por ela": o fluxo dela é ativar e sair mexendo nas abas.
    """
    destino = tmp_path / "perfis"

    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")])

    dados = json.loads((destino / "ilha_de_vidro.json").read_text(encoding="utf-8"))
    assert dados["name"] == "Ilha de Vidro"
    assert dados["match"] == {
        "type": "criteria",
        "window_class": ["steam_app_910001"],
        "window_title_regex": None,
        "process_name": [],
    }
    assert dados["priority"] == loader.PRIORIDADE_DO_PERFIL_DE_JOGO == 80
    # "E NADA MAIS" passou a ser LITERAL em 06/09/2026 (PERFIS-SAO-PERFIS-01).
    # Ela, sobre os 24 que já estavam no disco: *"mantemos só o nome e o id pra
    # eu reconfigurar um a um"*. O que saiu daqui eram cinco chaves repetindo o
    # DEFAULT DO ESQUEMA por extenso — e era isso que fazia um perfil sem
    # nenhuma escolha dela parecer configurado.
    assert list(dados) == list(loader.CHAVES_DO_PERFIL_DE_JOGO), dados

    # E o que o produto CARREGA continua sendo o default do esquema, chave a
    # chave: enxugar o arquivo não mudou o comportamento de nada.
    from hefesto_dualsense4unix.profiles.schema import Profile

    perfil = Profile.model_validate(dados)
    assert perfil.leds.lightbar == (0, 0, 0)
    assert perfil.leds.auto_player_colors is True
    assert perfil.triggers.left.mode == "Off"
    assert perfil.triggers.right.mode == "Off"
    assert perfil.suppress_desktop_emulation is False
    assert perfil.mode is None
    assert perfil.mic is None
    assert perfil.speaker is None
    assert perfil.mouse is None
    assert perfil.key_bindings is None


def test_o_perfil_semeado_e_valido_para_o_schema(tmp_path: Path) -> None:
    """Não basta gravar JSON: `load_all_profiles` tem de aceitá-lo."""
    destino = tmp_path / "perfis"
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    from hefesto_dualsense4unix.profiles.schema import Profile

    for arquivo in sorted(destino.glob("*.json")):
        perfil = Profile.model_validate(
            json.loads(arquivo.read_text(encoding="utf-8"))
        )
        assert perfil.matches({"wm_class": f"steam_app_{arquivo.stem[-1]}"}) in (
            True,
            False,
        )
    # E o casamento REAL: a janela do jogo ativa o perfil do jogo.
    perfil = Profile.model_validate(
        json.loads((destino / "ilha_de_vidro.json").read_text(encoding="utf-8"))
    )
    assert perfil.matches({"wm_class": "steam_app_910001"}) is True
    assert perfil.matches({"wm_class": "steam_app_910002"}) is False


# =============================================================================
# NUNCA sobrescrever — a regra mais cara desta frente
# =============================================================================

def test_colisao_de_nome_e_recusa_e_o_arquivo_dela_fica_intacto(
    tmp_path: Path,
) -> None:
    destino = tmp_path / "perfis"
    dela = _perfil_dela(
        destino,
        "ilha_de_vidro.json",
        {"name": "Ilha de Vidro", "match": {"type": "manual"}, "priority": 7},
    )

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")]
    )

    assert resultado.criados == ()
    recusa = resultado.por_desfecho("nome_ocupado")
    assert [(r.appid, r.arquivo) for r in recusa] == [("910001", "ilha_de_vidro.json")]
    # Byte a byte: a recusa não tocou no arquivo dela.
    assert (destino / "ilha_de_vidro.json").read_bytes() == dela


def test_a_recusa_por_nome_nao_vira_marca_e_e_reavaliada(tmp_path: Path) -> None:
    """Ela renomeia o perfil que ocupava o nome; a próxima varredura semeia."""
    destino = tmp_path / "perfis"
    _perfil_dela(
        destino,
        "ilha_de_vidro.json",
        {"name": "Ilha de Vidro", "match": {"type": "manual"}},
    )
    jogos = [_jogo("910001", "Ilha de Vidro")]

    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)
    assert _linhas_da_marca(destino) == []

    (destino / "ilha_de_vidro.json").rename(destino / "minha_ilha.json")
    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=jogos)

    assert resultado.criados == ("ilha_de_vidro.json",)


def test_o_jogo_que_ja_tem_perfil_pelo_appid_nao_ganha_um_segundo(
    tmp_path: Path,
) -> None:
    """O caso real do disco dela: o preset se chama `sackboy_nativo`.

    Uma conferência por nome de arquivo NÃO acharia o dono — o preset de
    fábrica mira `steam_app_1599660` e se chama `sackboy_nativo`, não
    "Sackboy: A Big Adventure". Sem a conferência por appid, o produto criaria
    um SEGUNDO perfil para o mesmo jogo, empatado na prioridade 80.
    """
    destino = tmp_path / "perfis"
    _perfil_dela(
        destino,
        "sackboy_nativo.json",
        {
            "name": "sackboy_nativo",
            "match": {"type": "criteria", "window_class": ["steam_app_910001"]},
            "priority": 80,
        },
    )

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")]
    )

    assert resultado.criados == ()
    assert not (destino / "ilha_de_vidro.json").exists()
    ja_tinha = resultado.por_desfecho("ja_tinha_perfil")
    assert [(r.appid, r.arquivo) for r in ja_tinha] == [
        ("910001", "sackboy_nativo.json")
    ]


def test_o_dono_do_appid_e_achado_mesmo_com_caixa_trocada(tmp_path: Path) -> None:
    """`Steam_App_910001` é a MESMA janela — o predicado da casa é sem caixa."""
    destino = tmp_path / "perfis"
    _perfil_dela(
        destino,
        "meu_jogo.json",
        {
            "name": "Meu jogo",
            "match": {"type": "criteria", "window_class": ["Steam_App_910001"]},
        },
    )

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")]
    )

    assert resultado.criados == ()
    assert resultado.por_desfecho("ja_tinha_perfil")[0].arquivo == "meu_jogo.json"


def test_perfil_corrompido_que_ocupa_o_nome_tambem_e_respeitado(
    tmp_path: Path,
) -> None:
    """O que o schema rejeita continua OCUPANDO o nome do arquivo."""
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    (destino / "ilha_de_vidro.json").write_text("{ isto não é json", encoding="utf-8")

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")]
    )

    assert resultado.criados == ()
    assert (destino / "ilha_de_vidro.json").read_text(encoding="utf-8") == (
        "{ isto não é json"
    )


def test_nenhuma_varredura_apaga_arquivo_nenhum(tmp_path: Path) -> None:
    """Nada nesta entrega apaga nada, em nenhum caminho — inclusive repetida."""
    destino = tmp_path / "perfis"
    _perfil_dela(destino, "meu_perfil.json", {"name": "meu_perfil", "match": {"type": "any"}})
    _perfil_dela(
        destino,
        "ilha_de_vidro.json",
        {"name": "Ilha de Vidro", "match": {"type": "manual"}},
    )
    antes = {p.name: p.read_bytes() for p in destino.glob("*.json")}

    for _ in range(3):
        loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    depois = {p.name: p.read_bytes() for p in destino.glob("*.json")}
    for nome, bruto in antes.items():
        assert nome in depois, f"a varredura sumiu com {nome}"
        assert depois[nome] == bruto, f"a varredura mexeu em {nome}"


def test_gravar_sem_pisar_recusa_arquivo_existente(tmp_path: Path) -> None:
    """A recusa é do KERNEL, não de um `if` — sem janela entre olhar e escrever."""
    pasta = tmp_path / "perfis"
    pasta.mkdir()
    alvo = pasta / "ja_existe.json"
    alvo.write_text("meu conteúdo", encoding="utf-8")

    assert loader._gravar_sem_pisar(alvo, {"name": "outro"}) is False
    assert alvo.read_text(encoding="utf-8") == "meu conteúdo"
    # E não deixou lixo de tmpfile para trás.
    assert sorted(p.name for p in pasta.iterdir()) == ["ja_existe.json"]


# =============================================================================
# A marca de semeadura — o que é do produto e o que é dela
# =============================================================================

def test_a_marca_separa_o_que_o_produto_criou_do_que_e_dela(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"
    _perfil_dela(
        destino,
        "sackboy_nativo.json",
        {
            "name": "sackboy_nativo",
            "match": {"type": "criteria", "window_class": ["steam_app_910002"]},
        },
    )

    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    semeados = loader.perfis_de_jogo_semeados(dest_dir=destino)
    # O que o produto criou tem arquivo…
    assert semeados == {
        "910001": "ilha_de_vidro.json",
        "910003": "o_jardim_fechado.json",
    }
    # …e o jogo que já era dela ficou registrado SEM arquivo (o produto sabe
    # que tratou o jogo, e sabe que o arquivo não é dele).
    assert "910002\t" in _linhas_da_marca(destino)
    assert "910002" not in semeados


def test_perfil_semeado_que_ela_apagou_nao_ressuscita(tmp_path: Path) -> None:
    """Mesmo contrato do `.seeded_presets`: deleção proposital é decisão dela."""
    destino = tmp_path / "perfis"
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)
    (destino / "ilha_de_vidro.json").unlink()

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    assert resultado.criados == ()
    assert not (destino / "ilha_de_vidro.json").exists()
    assert [r.appid for r in resultado.por_desfecho("ja_semeado")] == [
        "910002",
        "910001",
        "910003",
    ]


def test_a_segunda_varredura_so_semeia_o_jogo_novo(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    novo = _jogo("910004", "Chuva de Prata")
    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[*TRES_JOGOS, novo]
    )

    assert resultado.criados == ("chuva_de_prata.json",)
    assert len(list(destino.glob("*.json"))) == 4


def test_a_marca_sobrevive_a_linha_estragada(tmp_path: Path) -> None:
    """Marca meio escrita não pode virar semeadura em dobro nem exceção."""
    destino = tmp_path / "perfis"
    destino.mkdir(parents=True)
    (destino / loader.MARCA_DE_SEMEADURA_DE_JOGOS).write_text(
        "910001\tilha_de_vidro.json\nlixo sem tab\n\t\n910002\n",
        encoding="utf-8",
    )

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    assert resultado.criados == ("o_jardim_fechado.json",)


# =============================================================================
# O nome do jogo que não vira arquivo
# =============================================================================

def test_jogo_cujo_nome_nao_produz_slug_e_recusado_sem_explodir(
    tmp_path: Path,
) -> None:
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_jogo("910009", "!!!"), _jogo("910001", "Ilha de Vidro")]
    )

    assert resultado.criados == ("ilha_de_vidro.json",)
    assert [r.appid for r in resultado.por_desfecho("sem_slug")] == ["910009"]


def test_dois_jogos_com_o_mesmo_slug_o_segundo_e_recusado(tmp_path: Path) -> None:
    """Colisão entre DOIS semeados também é recusa — nunca sobrescrita."""
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino,
        jogos=[_jogo("910001", "Ilha de Vidro"), _jogo("910002", "ilha-de-vidro")],
    )

    assert len(resultado.criados) == 1
    assert len(resultado.por_desfecho("nome_ocupado")) == 1
    assert len(list(destino.glob("*.json"))) == 1


# =============================================================================
# O defeito irmão: o perfil que casa com a LOJA
# =============================================================================

def test_o_produto_avisa_quando_um_perfil_dela_casa_com_a_loja(
    tmp_path: Path,
) -> None:
    """Treze trocas de perfil em 54 minutos por causa do `steamwebhelper`.

    O arquivo é dela e o produto não o edita — mas passa a DIZER.
    """
    destino = tmp_path / "perfis"
    _perfil_dela(
        destino,
        "navegacao.json",
        {
            "name": "Navegação",
            "match": {
                "type": "criteria",
                "window_class": ["firefox", "steam", "Steam"],
            },
        },
    )

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=TRES_JOGOS)

    assert resultado.avisos_da_loja == (
        ("navegacao.json", "Navegação", ("steam", "Steam")),
    )
    # E o arquivo dela continua exatamente como estava.
    dados = json.loads((destino / "navegacao.json").read_text(encoding="utf-8"))
    assert dados["match"]["window_class"] == ["firefox", "steam", "Steam"]


def test_o_aviso_pega_o_steamwebhelper_e_nao_pega_o_jogo(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"
    _perfil_dela(
        destino,
        "webhelper.json",
        {"name": "helper", "match": {"type": "criteria", "window_class": ["steamwebhelper"]}},
    )
    _perfil_dela(
        destino,
        "so_jogo.json",
        {"name": "jogo", "match": {"type": "criteria", "window_class": ["steam_app_77"]}},
    )

    avisos = loader.perfis_que_casam_com_o_cliente_steam(dest_dir=destino)

    assert [a[0] for a in avisos] == ["webhelper.json"]


def test_a_semeadura_recusa_um_match_que_casaria_com_a_loja(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guarda de invariante: se o `match` do semeado virar a loja, ele NÃO nasce.

    O `match` que sai daqui hoje é sempre `steam_app_<n>`, que nunca é o
    cliente Steam. Esta guarda existe para que uma mudança futura em
    `classes_do_perfil_do_jogo` recuse em vez de plantar treze cópias do
    defeito que custou 54 minutos de partida a ela.
    """
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "classes_do_perfil_do_jogo", lambda appid: ["steam"])

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")]
    )

    assert resultado.criados == ()
    assert not (destino / "ilha_de_vidro.json").exists()
    assert [r.appid for r in resultado.por_desfecho("casa_com_a_loja")] == ["910001"]


# =============================================================================
# O gatilho automático — e o freio que o faz caber no alt-tab
# =============================================================================

@pytest.fixture()
def gatilho_armado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura automática e zera o estado por processo."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)
    monkeypatch.setattr(
        loader, "_assinatura_da_biblioteca_vista", None, raising=False
    )


def test_a_primeira_carga_do_processo_semeia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gatilho_armado: None
) -> None:
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    monkeypatch.setattr(
        jogos_locais, "assinatura_da_biblioteca", lambda home=None: (("/x", 1),)
    )
    monkeypatch.setattr(
        jogos_locais, "jogos_da_biblioteca_steam", lambda home=None: list(TRES_JOGOS)
    )

    loader._talvez_semear_jogos()

    assert sorted(p.name for p in destino.glob("*.json")) == [
        "corrida_sem_fim.json",
        "ilha_de_vidro.json",
        "o_jardim_fechado.json",
    ]


def test_o_piso_de_tempo_impede_varrer_a_cada_alt_tab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gatilho_armado: None
) -> None:
    """`load_all_profiles` é chamado a cada troca de janela — o freio é aqui."""
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    chamadas: list[int] = []

    def _assinatura(home: Path | None = None) -> tuple[tuple[str, int], ...]:
        chamadas.append(1)
        return (("/x", len(chamadas)),)

    monkeypatch.setattr(jogos_locais, "assinatura_da_biblioteca", _assinatura)
    monkeypatch.setattr(
        jogos_locais, "jogos_da_biblioteca_steam", lambda home=None: list(TRES_JOGOS)
    )

    for _ in range(20):
        loader._talvez_semear_jogos()

    assert chamadas == [1], "a segunda carga passou do piso de tempo"


def test_o_jogo_instalado_amanha_e_semeado_sem_reiniciar_o_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gatilho_armado: None
) -> None:
    """O daemon dela fica dias de pé. Varrer só no boot deixaria o jogo de fora."""
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    biblioteca = [_jogo("910001", "Ilha de Vidro")]
    assinatura = [(("/x", 1),)]
    monkeypatch.setattr(
        jogos_locais, "assinatura_da_biblioteca", lambda home=None: assinatura[0]
    )
    monkeypatch.setattr(
        jogos_locais, "jogos_da_biblioteca_steam", lambda home=None: list(biblioteca)
    )

    loader._talvez_semear_jogos()
    assert sorted(p.name for p in destino.glob("*.json")) == ["ilha_de_vidro.json"]

    # Amanhã: ela instala um jogo. O `mtime` da steamapps muda, e o piso de
    # tempo já passou.
    biblioteca.append(_jogo("910004", "Chuva de Prata"))
    assinatura[0] = (("/x", 2),)
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)

    loader._talvez_semear_jogos()

    assert sorted(p.name for p in destino.glob("*.json")) == [
        "chuva_de_prata.json",
        "ilha_de_vidro.json",
    ]


def test_biblioteca_inalterada_nao_abre_arquivo_nenhum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gatilho_armado: None
) -> None:
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    monkeypatch.setattr(
        jogos_locais, "assinatura_da_biblioteca", lambda home=None: (("/x", 1),)
    )
    leituras: list[int] = []

    def _jogos(home: Path | None = None) -> list[JogoLocal]:
        leituras.append(1)
        return list(TRES_JOGOS)

    monkeypatch.setattr(jogos_locais, "jogos_da_biblioteca_steam", _jogos)

    loader._talvez_semear_jogos()
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)
    loader._talvez_semear_jogos()

    assert leituras == [1], "varreu a biblioteca de novo sem nada ter mudado"


def test_a_suite_e_a_maquina_dela_ficam_de_fora_pelo_opt_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`SKIP_PRESET_SEED=1` (que a conftest põe em TODO teste) desliga isto.

    Sem este respeito, qualquer teste que carregasse perfis leria a
    `steamapps` REAL dela — `jogos_da_biblioteca_steam(None)` cai em
    `Path.home()`, que a isolação de XDG não cobre.
    """
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)
    monkeypatch.setattr(loader, "_assinatura_da_biblioteca_vista", None, raising=False)
    olhadas: list[int] = []

    # A régua NÃO pode ser um `raise`: `_talvez_semear_jogos` engole toda
    # exceção por contrato (best-effort), inclusive o `AssertionError` do
    # próprio teste — medido, o teste passava com a cura arrancada.
    def _espiao(home: Path | None = None) -> tuple[tuple[str, int], ...]:
        olhadas.append(1)
        return ()

    monkeypatch.setattr(jogos_locais, "assinatura_da_biblioteca", _espiao)

    loader._talvez_semear_jogos()

    assert olhadas == [], "olhou a biblioteca dela com o opt-out ligado"


def test_falha_na_varredura_nao_derruba_a_carga_de_perfis(
    monkeypatch: pytest.MonkeyPatch, gatilho_armado: None
) -> None:
    def _explode(home: Path | None = None) -> tuple[tuple[str, int], ...]:
        raise OSError("disco cheio")

    monkeypatch.setattr(jogos_locais, "assinatura_da_biblioteca", _explode)

    loader._talvez_semear_jogos()  # não levanta


# =============================================================================
# A biblioteca FALSA no disco — o caminho inteiro, sem dublê
# =============================================================================

def _biblioteca_falsa(home: Path, entradas: list[tuple[str, str]]) -> Path:
    """Uma `~/.steam/steam/steamapps` de mentira com os `.acf` pedidos."""
    steamapps = home / ".steam" / "steam" / "steamapps"
    steamapps.mkdir(parents=True, exist_ok=True)
    for appid, nome in entradas:
        (steamapps / f"appmanifest_{appid}.acf").write_text(
            '"AppState"\n{\n'
            f'\t"appid"\t\t"{appid}"\n'
            f'\t"name"\t\t"{nome}"\n'
            "}\n",
            encoding="utf-8",
        )
    return steamapps


def test_do_acf_ao_perfil_sem_dubles(tmp_path: Path) -> None:
    """O caminho de ponta a ponta com uma `steamapps` de verdade em `tmp_path`."""
    casa = tmp_path / "casa"
    _biblioteca_falsa(
        casa,
        [
            ("910001", "Ilha de Vidro"),
            ("910002", "Corrida Sem Fim"),
            ("2805730", "Proton Experimental"),
            ("1391110", "Steam Linux Runtime 3.0 (sniper)"),
        ],
    )
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)

    assert sorted(resultado.criados) == ["corrida_sem_fim.json", "ilha_de_vidro.json"]
    assert not (destino / "proton_experimental.json").exists()
    assert not (destino / "steam_linux_runtime_30_sniper.json").exists()


def test_maquina_sem_steam_nao_semeia_nem_reclama(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, home=tmp_path / "vazia")

    assert resultado.criados == ()
    assert resultado.linhas == ()


# =============================================================================
# A assinatura da biblioteca — o freio de dois `stat()`
# =============================================================================

def test_a_assinatura_muda_quando_um_jogo_e_instalado(tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    steamapps = _biblioteca_falsa(casa, [("910001", "Ilha de Vidro")])

    antes = jogos_locais.assinatura_da_biblioteca(casa)
    (steamapps / "appmanifest_910004.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"910004"\n\t"name"\t\t"Chuva"\n}\n',
        encoding="utf-8",
    )
    depois = jogos_locais.assinatura_da_biblioteca(casa)

    assert antes != depois


def test_a_assinatura_nao_muda_a_toa(tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    _biblioteca_falsa(casa, [("910001", "Ilha de Vidro")])

    assert jogos_locais.assinatura_da_biblioteca(casa) == (
        jogos_locais.assinatura_da_biblioteca(casa)
    )


def test_a_assinatura_de_maquina_sem_steam_nao_levanta(tmp_path: Path) -> None:
    assinatura = jogos_locais.assinatura_da_biblioteca(tmp_path / "sem_steam")

    assert all(mtime == -1 for _, mtime in assinatura)


# =============================================================================
# A extração que faz o semeado e o salvo terem UM formato só
# =============================================================================

def test_o_save_e_a_semeadura_gravam_o_mesmo_formato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_payload_do_perfil` é compartilhado — dois formatos seriam dois bugs.

    A regra de omissão das seções opcionais é requisito de COMPATIBILIDADE
    (binário antigo tem `extra="forbid"` e rejeitaria TODO perfil no
    downgrade). MEDIDO em 22/08/2026: arrancar a omissão de `_payload_do_perfil`
    não fazia UM teste do caminho do `save_profile` ficar vermelho — a regra
    estava sem portão dos dois lados.

    O QUE MUDOU EM 06/09/2026 (PERFIS-SAO-PERFIS-01): o perfil de jogo nasce
    com TRÊS chaves, e o save continua gravando o payload inteiro. Os dois
    formatos não divergiram — o da semeadura é um SUBCONJUNTO EXATO do outro,
    porque `_payload_do_perfil_de_jogo` chama `_payload_do_perfil` e só então
    corta. É isso que esta régua passou a medir, e é a mesma propriedade de
    antes: as regras de omissão continuam tendo um dono só.
    """
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")])
    semeado = json.loads((destino / "ilha_de_vidro.json").read_text(encoding="utf-8"))

    from hefesto_dualsense4unix.profiles.schema import Profile

    perfil = Profile.model_validate(semeado)
    caminho = loader.save_profile(perfil, origem="teste")
    salvo = json.loads(caminho.read_text(encoding="utf-8"))

    # Subconjunto EXATO: o que a semeadura gravou, o save regrava igual.
    assert {k: salvo[k] for k in semeado} == semeado
    assert list(semeado) == list(loader.CHAVES_DO_PERFIL_DE_JOGO)
    for secao in ("mode", "mic", "speaker", "mouse", "key_bindings", "controllers"):
        assert secao not in salvo, f"o save gravou {secao} como null (quebra downgrade)"


# ---------------------------------------------------------------------------
# A FIAÇÃO — a decisão dela inteira mora em três linhas, e elas não tinham régua
# ---------------------------------------------------------------------------
#
# Medido pelo conferente em 22/08/2026, e é o buraco desta frente: arrancar as
# três chamadas de `_talvez_semear_jogos()` e pôr `pass` no lugar deixava
# **2034 testes verdes** — os 31 deste arquivo e toda a vizinhança de perfis.
# Nenhum teste chamava `load_profile`, `load_all_profiles` ou `audit_profiles`;
# os nomes só apareciam em docstring.
#
# A decisão dela é *"por default já deveria ter um perfil por jogo instalado"* —
# AUTOMÁTICO, e não um botão. O que faz isso ser automático são exatamente essas
# três linhas. Testar a semeadura sem testar quem a chama é testar a cura e
# deixar o gatilho solto, que é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma
# mais pura.


def test_as_tres_cargas_de_perfil_disparam_a_semeadura(monkeypatch, tmp_path):
    """`load_profile`, `load_all_profiles` e `audit_profiles` semeiam.

    A régua é a CHAMADA, não o efeito: o efeito depende do disco dela, e um
    teste que dependesse dele mediria a biblioteca Steam desta bancada. Aqui o
    gatilho é espionado e o corpo dele é substituído — o que se cobra é que as
    três portas de entrada passem por ele.

    Mordida (a do conferente): trocar as três chamadas por `pass`.
    """
    from hefesto_dualsense4unix.profiles import loader as ld

    chamadas: list[str] = []
    monkeypatch.setattr(ld, "_talvez_semear_jogos", lambda: chamadas.append("x"))
    monkeypatch.setattr(ld, "profiles_dir", lambda ensure=False: tmp_path)

    for nome, fn in (
        ("load_all_profiles", lambda: ld.load_all_profiles()),
        ("audit_profiles", lambda: ld.audit_profiles()),
    ):
        chamadas.clear()
        # A carga pode falhar (disco vazio, perfil inválido); o GATILHO não
        # pode deixar de ser chamado por isso — é o que se cobra aqui.
        with contextlib.suppress(Exception):
            fn()
        assert chamadas, (
            f"`{nome}` não dispara a semeadura. A decisão dela — o perfil nasce "
            "sozinho, sem clique — mora nesta chamada e em mais duas."
        )

    # `load_profile` exige um perfil no disco para não levantar antes da hora.
    (tmp_path / "vazio.json").write_text(
        '{"name": "vazio", "version": 1}', encoding="utf-8"
    )
    chamadas.clear()
    with contextlib.suppress(Exception):
        ld.load_profile("vazio")
    assert chamadas, "`load_profile` não dispara a semeadura"


def test_a_regua_da_fiacao_pega_a_chamada_arrancada(monkeypatch, tmp_path):
    """A anticircularidade: sem as chamadas, o teste acima TEM de reprovar.

    Um portão de fiação que passa com a fiação cortada não vale nada — e é
    exatamente o estado em que este arquivo estava. Aqui a prova é mecânica: o
    corpo das três funções é lido da árvore de sintaxe e a chamada é procurada
    pelo NOME, então apagá-la reprova sem depender de execução.
    """
    import ast
    import inspect

    from hefesto_dualsense4unix.profiles import loader as ld

    fonte = ast.parse(inspect.getsource(ld))
    portas = {"load_profile", "load_all_profiles", "audit_profiles"}
    sem_gatilho = []
    for no in ast.walk(fonte):
        if not isinstance(no, ast.FunctionDef) or no.name not in portas:
            continue
        chama = any(
            isinstance(c, ast.Call)
            and isinstance(c.func, ast.Name)
            and c.func.id == "_talvez_semear_jogos"
            for c in ast.walk(no)
        )
        if not chama:
            sem_gatilho.append(no.name)

    assert not sem_gatilho, (
        f"estas portas de carga não chamam `_talvez_semear_jogos`: {sem_gatilho}. "
        "Sem elas o perfil por jogo volta a ser um gesto, e a decisão dela era "
        "que ele NÃO fosse."
    )
