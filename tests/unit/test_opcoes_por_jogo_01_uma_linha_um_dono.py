#!/usr/bin/env python3
"""OPCOES-POR-JOGO-01 — a linha de inicialização tem UM dono.

O DEFEITO MEDIDO, 21/09/2026, no diário da máquina dela: o PRAGMATA perdia o
atalho `hefesto-launch` **de hora em hora**, das 04:31 às 22:00, e o vigia o
repunha em seguida. A causa não era a Steam (fechada desde as 02:49) nem este
produto: era uma tabela declarativa dela, fora do Hefesto, que reescrevia as
`LaunchOptions` daquele jogo com as variáveis de vídeo — e apagava o atalho ao
fazê-lo. Entre uma volta e outra, quem abrisse o jogo jogava sem controle no
rádio.

A ORDEM DELA: *"PODE CORRIGIR E INTEGRAR ELE AO NOSSO APP. DESATIVA O ORIGINAL
ENTÃO."*  <!-- noqa-acento: citação literal dela -->

O QUE ESTA RÉGUA COBRA, e cada item tem a sua mordida na docstring:

    a tabela é lida e escrita com um dono     `opcoes_por_jogo.ler`/`gravar`
    a linha final é atalho + opções dela      `linha_desejada`
    o jogo que ela tirou do atalho fica fora  `ler_jogos_sem_wrapper`
    o vdf recebe a linha na árvore CANÔNICA   `definir_opcoes_vdf_text`
    aplicar de novo não escreve nada          idempotência
    Steam aberta ADIA, jogo aberto recusa     os portões
    o vigia chama o quarto passo              o asset e o `install.sh`

NADA AQUI TOCA A MÁQUINA DELA: a tabela vai num `tmp_path`, o vdf é de
mentira, e os dois portões de processo são dublados em TODO teste que escreve
— um teste que perguntasse ao `/proc` real mediria se ela está jogando agora.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import opcoes_por_jogo as opj
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

RAIZ = Path(__file__).resolve().parents[2]

#: Um appid SINTÉTICO — um real faria a régua falar de um jogo que pode estar
#: na biblioteca de quem roda a suíte.
APPID = "990000021"
OPCOES = "VKD3D_CONFIG=no_upload_hvv %command%"

def _vdf_texto(appid: str = APPID) -> str:
    """Um `localconfig.vdf` de mentira com as DUAS árvores `apps`.

    A de baixo é a da Steam (ARVORE-ERRADA-01) e existe aqui para a régua
    poder cobrar que nada seja escrito nela.
    """
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
def _a_steam_esta_fechada(monkeypatch: pytest.MonkeyPatch):
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


# --------------------------------------------------------------------------
# a tabela
# --------------------------------------------------------------------------
def test_a_tabela_vai_e_volta_do_disco(tmp_path: Path) -> None:
    """ARRANQUE o `parse` do `ler` e este teste reprova: escrever uma tabela
    que não se relê é guardar a escolha dela num lugar que ninguém abre."""
    caminho = _tabela(tmp_path, **{APPID: OPCOES})
    assert caminho.name == "opcoes_por_jogo.txt"
    assert opj.ler(tmp_path) == {APPID: OPCOES}
    # O cabeçalho vai junto, e é ele que explica o arquivo para quem o abrir.
    assert "Formato:" in caminho.read_text(encoding="utf-8")


def test_a_linha_torta_nao_derruba_as_outras() -> None:
    """Um erro de digitação dela custa UMA linha, nunca a tabela inteira.

    ARRANQUE os `continue` do `parse` e este teste reprova com exceção — e o
    vigia morreria no meio, deixando os outros jogos sem as opções.
    """
    texto = (
        "# comentário\n"
        "\n"
        "sem-appid\tX=1 %command%\n"
        "12ab\tX=1 %command%\n"
        f"{APPID}\t{OPCOES}\n"
        "990000022\t\n"
        "990000023 MANGOHUD=1 %command%\n"  # espaço em vez de TAB: vale
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


# --------------------------------------------------------------------------
# a linha composta
# --------------------------------------------------------------------------
def test_a_linha_final_e_o_atalho_na_frente() -> None:
    """ARRANQUE o `WRAPPER_PREFIX` de `linha_desejada` e este teste reprova.

    A ordem é o ponto: o atalho é o programa que RECEBE o resto. Invertê-lo
    faria a linha inteira virar argumento das variáveis dela, e o jogo abriria
    sem o Hefesto no caminho.
    """
    linha = opj.linha_desejada(OPCOES, com_atalho=True)
    assert linha.startswith(slo.WRAPPER_PREFIX)
    assert linha.endswith(OPCOES)
    assert opj.linha_desejada(OPCOES, com_atalho=False) == OPCOES


def test_o_jogo_que_ela_tirou_do_atalho_nao_o_recebe_de_volta(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A escolha dela ganha do automatismo — a regra do `excluir` do irmão.

    ARRANQUE o `ler_jogos_sem_wrapper` do `aplicar` e este teste reprova: o
    «Não usar neste jogo» voltaria a ser desfeito a cada meia hora.
    """
    monkeypatch.setattr(opj, "ler_jogos_sem_wrapper", lambda: [APPID])
    vdf = _vdf_de_mentira(tmp_path)
    _tabela(tmp_path, **{APPID: OPCOES})
    opj.aplicar(vdfs=[vdf], config_home=tmp_path)
    # LIDO PELO LEITOR DO PRODUTO, e não pelo texto cru: o vdf escapa as
    # aspas, e uma régua que casasse a string crua daria vermelho sobre o
    # arranjo certo — foi o que aconteceu na primeira volta desta régua.
    lido = slo.read_launch_options_by_appid(vdf.read_text(encoding="utf-8"))
    assert lido[APPID] == OPCOES, lido


# --------------------------------------------------------------------------
# o vdf
# --------------------------------------------------------------------------
def test_a_linha_entra_na_arvore_canonica_e_so_nela(tmp_path: Path) -> None:
    """ARVORE-ERRADA-01 continua valendo: o `apps` da raiz é da Steam.

    ARRANQUE o `e_a_arvore_canonica` de `definir_opcoes_vdf_text` e este teste
    reprova — o bloco de baixo ganharia um `LaunchOptions` que ninguém lê.
    """
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
    """Idempotência: sem ela, o vigia deixaria um backup a cada meia hora.

    ARRANQUE o ramo `ja_e_o_desejado` e este teste reprova nos dois: o relato
    diria «aplicado» e um segundo backup nasceria.
    """
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
    """Sem tabela não há o que aplicar — e um vdf reescrito «igual» seria um
    backup por meia hora e uma janela de risco por nada."""
    vdf = _vdf_de_mentira(tmp_path)
    antes = vdf.read_text(encoding="utf-8")
    assert opj.aplicar(vdfs=[vdf], config_home=tmp_path)["status"] == opj.NADA
    assert vdf.read_text(encoding="utf-8") == antes


# --------------------------------------------------------------------------
# os portões
# --------------------------------------------------------------------------
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
    """ARRANQUE qualquer um dos dois portões e este teste reprova.

    A Steam viva regrava o vdf ao sair e engole a edição; com jogo aberto, o
    estrago não se desfaz. «Adiei» não é falha — é o que o `-` da unidade do
    vigia existe para dizer.
    """
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


# --------------------------------------------------------------------------
# o vigia chama o quarto passo
# --------------------------------------------------------------------------
def test_o_vigia_aplica_a_tabela_e_o_install_resolve_o_caminho() -> None:
    """Sem estas duas linhas o módulo seria uma promessa sem chamador.

    A MORDIDA: tire o `ExecStart` do asset e a primeira reprova; tire a
    substituição do `install.sh` e a segunda reprova — a unidade instalada
    ficaria com o `__OPCOES_POR_JOGO__` cru, e o vigia morreria no passo 4.
    """
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
