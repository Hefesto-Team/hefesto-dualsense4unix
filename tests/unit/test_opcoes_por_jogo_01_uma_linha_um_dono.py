#!/usr/bin/env python3
"""OPCOES-POR-JOGO-01 — a linha de inicialização tem UM dono."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import opcoes_por_jogo as opj
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

RAIZ = Path(__file__).resolve().parents[2]

APPID = "990000021"
OPCOES = "VKD3D_CONFIG=no_upload_hvv %command%"

def _vdf_texto(appid: str = APPID) -> str:
    """Um `localconfig.vdf` de mentira com as DUAS árvores `apps`."""
    return (
        '"UserLocalConfigStore"\n{\n'
        '\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
        '\t\t\t\t"apps"\n\t\t\t\t{\n'
        f'\t\t\t\t\t"{appid}"\n\t\t\t\t\t{{\n'
        '\t\t\t\t\t\t"LaunchOptions"\t\t"algo velho %command%"\n'
        '\t\t\t\t\t}\n'
        '\t\t\t\t\t"990000022"\n\t\t\t\t\t{\n'
        '\t\t\t\t\t\t"Playtime"\t\t"12"\n'
        '\t\t\t\t\t}\n'
        '\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n'
        '\t"apps"\n\t{\n'
        f'\t\t"{appid}"\n\t\t{{\n'
        '\t\t\t"UseSteamControllerConfig"\t\t"2"\n'
        '\t\t}\n\t}\n}\n'
    )


@pytest.fixture(autouse=True)
def _a_steam_esta_fechada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Os dois portões de processo, dublados — ver o cabeçalho."""
    monkeypatch.setattr(opj, "steam_running", lambda: False)
    monkeypatch.setattr(opj, "steam_game_running", lambda: False)
    monkeypatch.setattr(opj, "ler_jogos_sem_wrapper", list)


def _tabela(tmp_path: Path, **jogos: str) -> Path:
    opj.gravar(dict(jogos), config_home=tmp_path)
    return opj.tabela_path(tmp_path)


def _vdf_de_mentira(tmp_path: Path) -> Path:
    alvo = tmp_path / "userdata" / "1" / "config" / "localconfig.vdf"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(_vdf_texto(), encoding="utf-8")
    return alvo


def test_a_tabela_vai_e_volta_do_disco(tmp_path: Path) -> None:
    """ARRANQUE o `parse` do `ler` e este teste reprova: escrever uma tabela"""
    caminho = _tabela(tmp_path, **{APPID: OPCOES})
    assert caminho.name == "opcoes_por_jogo.txt"
    assert opj.ler(tmp_path) == {APPID: OPCOES}
    assert "Formato:" in caminho.read_text(encoding="utf-8")


def test_a_linha_torta_nao_derruba_as_outras() -> None:
    """Um erro de digitação dela custa UMA linha, nunca a tabela inteira."""
    texto = (
        "# comentário\n"
        "\n"
        "sem-appid\tX=1 %command%\n"
        "12ab\tX=1 %command%\n"
        f"{APPID}\t{OPCOES}\n"
        "990000022\t\n"
        "990000023 MANGOHUD=1 %command%\n"
    )
    assert opj.parse(texto) == {APPID: OPCOES, "990000023": "MANGOHUD=1 %command%"}


def test_definir_e_tirar_mexem_num_jogo_so(tmp_path: Path) -> None:
    """O par completo, e o segundo jogo fica onde estava."""
    opj.definir(APPID, OPCOES, config_home=tmp_path)
    opj.definir("990000023", "MANGOHUD=1 %command%", config_home=tmp_path)
    assert opj.tirar(APPID, config_home=tmp_path) is True
    assert opj.ler(tmp_path) == {"990000023": "MANGOHUD=1 %command%"}
    assert opj.tirar(APPID, config_home=tmp_path) is False
    with pytest.raises(ValueError):
        opj.definir("não-é-appid", OPCOES, config_home=tmp_path)


def test_a_linha_final_e_o_atalho_na_frente() -> None:
    """ARRANQUE o `WRAPPER_PREFIX` de `linha_desejada` e este teste reprova."""
    linha = opj.linha_desejada(OPCOES, com_atalho=True)
    assert linha.startswith(slo.WRAPPER_PREFIX)
    assert linha.endswith(OPCOES)
    assert opj.linha_desejada(OPCOES, com_atalho=False) == OPCOES


def test_o_jogo_que_ela_tirou_do_atalho_nao_o_recebe_de_volta(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A escolha do usuário ganha do automatismo — a regra do `excluir` do irmão."""
    monkeypatch.setattr(opj, "ler_jogos_sem_wrapper", lambda: [APPID])
    vdf = _vdf_de_mentira(tmp_path)
    _tabela(tmp_path, **{APPID: OPCOES})
    opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    lido = slo.read_launch_options_by_appid(vdf.read_text(encoding="utf-8"))
    assert lido[APPID] == OPCOES, lido


def test_a_linha_entra_na_arvore_canonica_e_so_nela(tmp_path: Path) -> None:
    """ARVORE-ERRADA-01 continua valendo: o `apps` da raiz é da Steam."""
    vdf = _vdf_de_mentira(tmp_path)
    _tabela(tmp_path, **{APPID: OPCOES})
    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    texto = vdf.read_text(encoding="utf-8")

    assert relato["status"] == opj.APLICADO
    assert texto.count('"LaunchOptions"') == 1
    assert (slo.read_launch_options_by_appid(texto)[APPID]
            == opj.linha_desejada(OPCOES, com_atalho=True))
    assert '"UseSteamControllerConfig"\t\t"2"' in texto, "o bloco da Steam mudou"
    assert list(vdf.parent.glob("*.bak.hefesto-opcoes-*")), "escreveu sem backup"


def test_o_jogo_sem_a_linha_ganha_a_linha(tmp_path: Path) -> None:
    """O segundo jogo do vdf não tem `LaunchOptions` — e passa a ter."""
    vdf = _vdf_de_mentira(tmp_path)
    _tabela(tmp_path, **{"990000022": "MANGOHUD=1 %command%"})
    opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    texto = vdf.read_text(encoding="utf-8")
    assert texto.count('"LaunchOptions"') == 2
    assert "MANGOHUD=1" in texto


def test_aplicar_de_novo_nao_escreve_nada(tmp_path: Path) -> None:
    """Idempotência: sem ela, o vigia deixaria um backup a cada meia hora."""
    vdf = _vdf_de_mentira(tmp_path)
    _tabela(tmp_path, **{APPID: OPCOES})
    opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    antes = vdf.read_text(encoding="utf-8")
    quantos = len(list(vdf.parent.glob("*.bak.hefesto-opcoes-*")))

    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    assert relato["status"] == opj.NADA
    assert vdf.read_text(encoding="utf-8") == antes
    assert len(list(vdf.parent.glob("*.bak.hefesto-opcoes-*"))) == quantos


def test_a_tabela_vazia_nao_toca_no_vdf(tmp_path: Path) -> None:
    """Sem tabela não há o que aplicar — e um vdf reescrito «igual» seria um"""
    vdf = _vdf_de_mentira(tmp_path)
    antes = vdf.read_text(encoding="utf-8")
    assert opj.aplicar(vdfs=[vdf], config_home=tmp_path)["status"] == opj.NADA
    assert vdf.read_text(encoding="utf-8") == antes


@pytest.mark.parametrize(
    ("qual", "dublê", "status"),
    [
        ("jogo aberto", "steam_game_running", opj.ADIADO_JOGO),
        ("Steam aberta", "steam_running", opj.ADIADO_STEAM),
    ],
)
def test_com_a_steam_viva_ele_adia_sem_escrever(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qual: str,
        dublê: str, status: str) -> None:
    """ARRANQUE qualquer um dos dois portões e este teste reprova."""
    monkeypatch.setattr(opj, dublê, lambda: True)
    vdf = _vdf_de_mentira(tmp_path)
    antes = vdf.read_text(encoding="utf-8")
    _tabela(tmp_path, **{APPID: OPCOES})

    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    assert relato["status"] == status, qual
    assert vdf.read_text(encoding="utf-8") == antes
    assert not list(vdf.parent.glob("*.bak.hefesto-opcoes-*"))


def test_o_dry_run_diz_o_que_faria_e_nao_faz(tmp_path: Path) -> None:
    vdf = _vdf_de_mentira(tmp_path)
    antes = vdf.read_text(encoding="utf-8")
    _tabela(tmp_path, **{APPID: OPCOES})
    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path, dry_run=True)
    assert relato["status"] == opj.APLICADO
    assert vdf.read_text(encoding="utf-8") == antes


def test_o_vigia_aplica_a_tabela_e_o_install_resolve_o_caminho() -> None:
    """Sem estas duas linhas o módulo seria uma promessa sem chamador."""
    unidade = (RAIZ / "assets" / "hefesto-steam-input-guard.service").read_text(
        encoding="utf-8")
    assert "ExecStart=-/usr/bin/env python3 __OPCOES_POR_JOGO__ --aplicar" in unidade
    instalador = (RAIZ / "install.sh").read_text(encoding="utf-8")
    assert "__OPCOES_POR_JOGO__#${OPCOES_POR_JOGO_PY}" in instalador
    assert "integrations/opcoes_por_jogo.py" in instalador


def test_o_cli_lista_define_e_tira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    """O caminho que ELA usa no terminal, com o `XDG_CONFIG_HOME` desviado."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert opj.main(["--definir", APPID, OPCOES]) == 0
    assert opj.main(["--listar"]) == 0
    saida = capsys.readouterr().out
    assert APPID in saida and OPCOES in saida
    assert opj.main(["--tirar", APPID]) == 0
    assert opj.ler(tmp_path) == {}


# --- A-OPCAO-POR-JOGO-CHEGA-AO-LANCAMENTO-01 (08/10/2026) -------------------

BASE_DO_STEAMID64 = 76561197960265728


def _vdf_com_bloco_filho(appid: str = APPID) -> str:
    """O jogo do Sackboy: o bloco `cloud` vem ANTES da `LaunchOptions` dele.

    Medido na `localconfig.vdf` dela em 08/10: 36 dos 73 jogos têm bloco filho
    antes da linha (ou ainda não têm linha). O escritor antigo fechava o jogo no
    `}` do filho e escrevia a opção lá dentro.
    """
    return (
        '"UserLocalConfigStore"\n{\n'
        '\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
        '\t\t\t\t"apps"\n\t\t\t\t{\n'
        f'\t\t\t\t\t"{appid}"\n\t\t\t\t\t{{\n'
        '\t\t\t\t\t\t"LastPlayed"\t\t"1791398598"\n'
        '\t\t\t\t\t\t"cloud"\n\t\t\t\t\t\t{\n'
        '\t\t\t\t\t\t\t"last_sync_state"\t\t"synchronized"\n'
        '\t\t\t\t\t\t}\n'
        '\t\t\t\t\t\t"LaunchOptions"\t\t"algo velho %command%"\n'
        '\t\t\t\t\t}\n'
        '\t\t\t\t\t"990000022"\n\t\t\t\t\t{\n'
        '\t\t\t\t\t\t"autocloud"\n\t\t\t\t\t\t{\n'
        '\t\t\t\t\t\t\t"lastexit"\t\t"1"\n'
        '\t\t\t\t\t\t}\n'
        '\t\t\t\t\t}\n'
        '\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n'
    )


def test_a_opcao_entra_na_linha_do_jogo_e_nao_no_bloco_filho(tmp_path: Path) -> None:
    """O defeito de 06/10: o relato dizia `aplicado` e a linha do jogo ficava velha.

    ARRANQUE a profundidade do quadro (o `}` do filho voltar a fechar o jogo) e
    este teste reprova: a opção vai para dentro do `cloud` e o leitor do
    produto ainda vê `algo velho`.
    """
    vdf = tmp_path / "userdata" / "1" / "config" / "localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(_vdf_com_bloco_filho(), encoding="utf-8")
    _tabela(tmp_path, **{APPID: OPCOES, "990000022": "MANGOHUD=1 %command%"})

    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    texto = vdf.read_text(encoding="utf-8")
    lido = slo.read_launch_options_by_appid(texto)

    assert relato["status"] == opj.APLICADO, relato
    assert lido[APPID] == opj.linha_desejada(OPCOES, com_atalho=True), lido
    assert lido["990000022"] == opj.linha_desejada("MANGOHUD=1 %command%", com_atalho=True)
    # o bloco filho segue só com o que a Steam pôs nele
    assert opj.opcoes_lidas_do_jogo(texto, APPID) == [_valor_escapado(OPCOES)]
    assert opj.opcoes_lidas_do_jogo(texto, "990000022") == [
        _valor_escapado("MANGOHUD=1 %command%")]
    assert texto.count('"LaunchOptions"') == 2, texto


def _valor_escapado(opcoes: str) -> str:
    return opj._valor_do_vdf(opj.linha_desejada(opcoes, com_atalho=True))


def test_a_linha_perdida_no_bloco_filho_pela_versao_velha_e_alinhada(
        tmp_path: Path) -> None:
    """O vdf dela JÁ tem a sujeira de 06/10 (`cloud/LaunchOptions`): fica igual à do jogo."""
    sujo = _vdf_com_bloco_filho().replace(
        '\t\t\t\t\t\t\t"last_sync_state"\t\t"synchronized"\n',
        '\t\t\t\t\t\t\t"last_sync_state"\t\t"synchronized"\n'
        '\t\t\t\t\t\t\t"LaunchOptions"\t\t"MANGOHUD=1 %command%"\n',
    )
    vdf = tmp_path / "userdata" / "1" / "config" / "localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(sujo, encoding="utf-8")
    _tabela(tmp_path, **{APPID: OPCOES})

    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path)

    assert relato["status"] == opj.APLICADO, relato
    todas = opj.opcoes_lidas_do_jogo(vdf.read_text(encoding="utf-8"), APPID)
    assert todas == [_valor_escapado(OPCOES)] * 2, todas


def _duas_contas(home: Path, com_marca: bool) -> tuple[Path, Path]:
    """Uma Steam com duas contas: a 111 (a antiga) e a 222 (a que está logada)."""
    raiz = home / ".steam" / "steam"
    pastas = []
    for conta in ("111", "222"):
        vdf = raiz / "userdata" / conta / "config" / "localconfig.vdf"
        vdf.parent.mkdir(parents=True)
        vdf.write_text(_vdf_texto(), encoding="utf-8")
        pastas.append(vdf)
    # com a marca, a logada é a de Timestamp MENOR: só a marca a distingue
    marca = '\t\t"MostRecent"\t\t"1"\n' if com_marca else ""
    quando = "1600000000" if com_marca else "1790000000"
    (raiz / "config").mkdir()
    (raiz / "config" / "loginusers.vdf").write_text(
        '"users"\n{\n'
        f'\t"{BASE_DO_STEAMID64 + 111}"\n\t{{\n\t\t"AccountName"\t\t"velha"\n'
        '\t\t"Timestamp"\t\t"1700000000"\n\t}\n'
        f'\t"{BASE_DO_STEAMID64 + 222}"\n\t{{\n\t\t"AccountName"\t\t"nova"\n'
        f'{marca}\t\t"Timestamp"\t\t"{quando}"\n\t}}\n}}\n',
        encoding="utf-8",
    )
    return pastas[0], pastas[1]


@pytest.mark.parametrize("com_marca", [True, False], ids=["MostRecent", "Timestamp"])
def test_so_a_conta_logada_recebe_a_linha(tmp_path: Path, com_marca: bool) -> None:
    """Duas contas, o `loginusers.vdf` diz qual é a logada: só a dela é escrita.

    ARRANQUE o filtro `so_a_conta_logada` do `aplicar` (escrever em todos) e
    este teste reprova: a conta 111 ganha a linha.
    """
    velha, logada = _duas_contas(tmp_path, com_marca)
    antes_da_velha = velha.read_text(encoding="utf-8")
    _tabela(tmp_path, **{APPID: OPCOES})

    relato = opj.aplicar(home=tmp_path, config_home=tmp_path)

    assert relato["status"] == opj.APLICADO, relato
    assert opj.linha_desejada(OPCOES, com_atalho=True) in slo.read_launch_options_by_appid(
        logada.read_text(encoding="utf-8"))[APPID]
    assert velha.read_text(encoding="utf-8") == antes_da_velha
    assert not list(velha.parent.glob("*.bak.hefesto-opcoes-*"))
    assert [p["reason"] for p in relato["pulados"] if p["vdf"] == str(velha.resolve())] == [
        "conta_nao_logada"]


def test_sem_resposta_do_loginusers_duas_contas_nao_se_adivinha(tmp_path: Path) -> None:
    """Sem saber qual é a logada, escrever em uma das duas é escrever na errada."""
    velha, logada = _duas_contas(tmp_path, com_marca=False)
    (tmp_path / ".steam" / "steam" / "config" / "loginusers.vdf").unlink()
    antes = [velha.read_text(encoding="utf-8"), logada.read_text(encoding="utf-8")]
    _tabela(tmp_path, **{APPID: OPCOES})

    relato = opj.aplicar(home=tmp_path, config_home=tmp_path)

    assert relato["status"] == opj.NADA, relato
    assert [velha.read_text(encoding="utf-8"), logada.read_text(encoding="utf-8")] == antes
    assert {p["reason"] for p in relato["pulados"]} == {"conta_logada_desconhecida"}


def test_vdf_que_a_steam_regravou_depois_da_escrita_nao_e_aplicado(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """O relato só diz `aplicado` depois de ler a opção onde a Steam a lê.

    A Steam «regravou» o arquivo logo depois da escrita (o dublê devolve o texto
    de antes). ARRANQUE a releitura (aceitar o que o escritor disse que fez) e
    este teste reprova: o status volta a ser `aplicado`.
    """
    vdf = _vdf_de_mentira(tmp_path)
    antes = vdf.read_text(encoding="utf-8")
    _tabela(tmp_path, **{APPID: OPCOES})
    escreve = Path.write_text

    def steam_regrava(self: Path, dados: str, *args: object, **kw: object) -> int:
        feito = escreve(self, dados, *args, **kw)  # type: ignore[arg-type]
        if self.name == "localconfig.vdf":
            escreve(self, antes, encoding="utf-8")
        return feito

    monkeypatch.setattr(Path, "write_text", steam_regrava)
    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    monkeypatch.undo()

    assert relato["status"] == opj.DESFEITO == "desfeito_pela_steam", relato
    assert relato["aplicados"] == []
    assert [d["appid"] for d in relato["desfeitos"]] == [APPID]
    assert "LaunchOptions" in relato["desfeitos"][0]["reason"]
    assert opj._imprimir(relato) == 1
    saida = capsys.readouterr()
    assert "aplicado" not in saida.out.replace("desfeito", "")
    assert "desfeito_pela_steam" in saida.err
