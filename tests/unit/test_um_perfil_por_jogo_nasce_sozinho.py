"""UM-PERFIL-POR-JOGO-01 (22/08/2026) — o perfil do jogo nasce sozinho."""
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
    """Nome do jogo, `match` pelo appid, prioridade 80 — e NADA MAIS NO ARQUIVO."""
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
    assert list(dados) == list(loader.CHAVES_DO_PERFIL_DE_JOGO), dados

    from hefesto_dualsense4unix.profiles.schema import Profile, TriggersConfig

    perfil = Profile.model_validate(dados)
    assert perfil.leds.lightbar == (0, 0, 0)
    assert perfil.leds.auto_player_colors is True
    assert perfil.triggers == TriggersConfig()
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
    perfil = Profile.model_validate(
        json.loads((destino / "ilha_de_vidro.json").read_text(encoding="utf-8"))
    )
    assert perfil.matches({"wm_class": "steam_app_910001"}) is True
    assert perfil.matches({"wm_class": "steam_app_910002"}) is False


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
    """O caso real do disco do usuário: o preset se chama `sackboy_nativo`."""
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
    assert sorted(p.name for p in pasta.iterdir()) == ["ja_existe.json"]


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
    assert semeados == {
        "910001": "ilha_de_vidro.json",
        "910003": "o_jardim_fechado.json",
    }
    assert "910002\t" in _linhas_da_marca(destino)
    assert "910002" not in semeados


def test_perfil_semeado_que_ela_apagou_nao_ressuscita(tmp_path: Path) -> None:
    """Mesmo contrato do `.seeded_presets`: deleção proposital é decisão de produto."""
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


def test_o_produto_avisa_quando_um_perfil_dela_casa_com_a_loja(
    tmp_path: Path,
) -> None:
    """Treze trocas de perfil em 54 minutos por causa do `steamwebhelper`."""
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
    """Guarda de invariante: se o `match` do semeado virar a loja, ele NÃO nasce."""
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "classes_do_perfil_do_jogo", lambda appid: ["steam"])

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")]
    )

    assert resultado.criados == ()
    assert not (destino / "ilha_de_vidro.json").exists()
    assert [r.appid for r in resultado.por_desfecho("casa_com_a_loja")] == ["910001"]


@pytest.fixture()
def gatilho_armado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura automática e zera o estado por processo."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)
    monkeypatch.setattr(
        loader, "_assinatura_da_biblioteca_vista", None, raising=False
    )
    # O jogo instalado aqui (o `.desktop`) é a terceira origem da semeadura: sem
    # isto o teste leria os atalhos REAIS da máquina que o roda.
    monkeypatch.setattr(jogos_locais, "pastas_de_atalhos", lambda: [])


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
    """O daemon do usuário fica dias de pé. Varrer só no boot deixaria o jogo de fora."""
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
    """`SKIP_PRESET_SEED=1` (que a conftest põe em TODO teste) desliga isto."""
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)
    monkeypatch.setattr(loader, "_assinatura_da_biblioteca_vista", None, raising=False)
    olhadas: list[int] = []

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

    loader._talvez_semear_jogos()


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


def test_o_save_e_a_semeadura_gravam_o_mesmo_formato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_payload_do_perfil` é compartilhado — dois formatos seriam dois bugs."""
    destino = tmp_path / "perfis"
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=[_jogo("910001", "Ilha de Vidro")])
    semeado = json.loads((destino / "ilha_de_vidro.json").read_text(encoding="utf-8"))

    from hefesto_dualsense4unix.profiles.schema import Profile

    perfil = Profile.model_validate(semeado)
    caminho = loader.save_profile(perfil, origem="teste")
    salvo = json.loads(caminho.read_text(encoding="utf-8"))

    assert {k: salvo[k] for k in semeado} == semeado
    assert list(semeado) == list(loader.CHAVES_DO_PERFIL_DE_JOGO)
    for secao in ("mode", "mic", "speaker", "mouse", "key_bindings", "controllers"):
        assert secao not in salvo, f"o save gravou {secao} como null (quebra downgrade)"


def test_as_tres_cargas_de_perfil_disparam_a_semeadura(monkeypatch, tmp_path):
    """`load_profile`, `load_all_profiles` e `audit_profiles` semeiam."""
    from hefesto_dualsense4unix.profiles import loader as ld

    chamadas: list[str] = []
    monkeypatch.setattr(ld, "_talvez_semear_jogos", lambda: chamadas.append("x"))
    monkeypatch.setattr(ld, "profiles_dir", lambda ensure=False: tmp_path)

    for nome, fn in (
        ("load_all_profiles", lambda: ld.load_all_profiles()),
        ("audit_profiles", lambda: ld.audit_profiles()),
    ):
        chamadas.clear()
        with contextlib.suppress(Exception):
            fn()
        assert chamadas, (
            f"`{nome}` não dispara a semeadura. A decisão dela — o perfil nasce "
            "sozinho, sem clique — mora nesta chamada e em mais duas."
        )

    (tmp_path / "vazio.json").write_text(
        '{"name": "vazio", "version": 1}', encoding="utf-8"
    )
    chamadas.clear()
    with contextlib.suppress(Exception):
        ld.load_profile("vazio")
    assert chamadas, "`load_profile` não dispara a semeadura"


def test_a_regua_da_fiacao_pega_a_chamada_arrancada(monkeypatch, tmp_path):
    """A anticircularidade: sem as chamadas, o teste acima TEM de reprovar."""
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
