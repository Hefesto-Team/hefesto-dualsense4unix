#!/usr/bin/env python3
"""LANCADORES-ZERO-01, itens 3 e 4 — a cura por estrada e a caixa do Flatpak."""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import cura_por_estrada as cura
from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as caixa

HEROIC = "com.heroicgameslauncher.hgl"
DOLPHIN = "org.DolphinEmu.dolphin-emu"
MGBA = "io.mgba.mGBA"

ATALHOS_EMULADORES = (DOLPHIN, "dolphin-emu", MGBA, "mgba-qt", "mgba")

DEFAULT_ENV = """\
# Materializado pelo daemon do Hefesto (DEDUP-04). Não edite:
# é regravado a cada transição de estado do gamepad virtual.
PROTON_DISABLE_HIDRAW=0x054C/0x0CE6
SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x28de/0x11ff
__GL_SHADER_DISK_CACHE=1
LD_PRELOAD=/tmp/algo-que-o-wrapper-nao-exporta.so
"""


def _lar_de_mentira(tmp: pathlib.Path) -> dict[str, pathlib.Path]:
    """O PAR que mantém a medição inteira dentro do `tmp` — lar e sistema."""
    return {"lar": tmp, "raiz_sistema": tmp / "instalacao-do-sistema"}


def _instalar(lar: pathlib.Path, app_id: str, devices: str = "all") -> None:
    """Um flatpak de mentira: o `metadata` que o pacote publica."""
    meta = lar / ".local/share/flatpak/app" / app_id / "current/active/metadata"
    meta.parent.mkdir(parents=True, exist_ok=True)
    linha = f"devices={devices};\n" if devices else ""
    meta.write_text(f"[Application]\nname={app_id}\n\n"
                    f"[Context]\nshared=network;ipc;\n{linha}",
                    encoding="utf-8")


def _override(lar: pathlib.Path, nome: str, corpo: str) -> pathlib.Path:
    alvo = lar / ".local/share/flatpak/overrides" / nome
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(corpo, encoding="utf-8")
    return alvo


def _ambiente(tmp: pathlib.Path, corpo: str = DEFAULT_ENV) -> pathlib.Path:
    """A pasta `launch_env` de mentira, com o `default.env` do daemon."""
    pasta = tmp / "launch_env"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "default.env").write_text(corpo, encoding="utf-8")
    return pasta


def test_a_caixa_com_devices_all_deixa_o_controle_entrar(tmp_path) -> None:
    """Os cinco lançadores do usuário trazem `devices=all` — medido em 09/09/2026."""
    _instalar(tmp_path, HEROIC)

    p = caixa.permissao_de(HEROIC, **_lar_de_mentira(tmp_path))

    assert p.estado == caixa.ENTRA
    assert p.dispositivos == ("all",)
    assert p.onde is not None


def test_a_caixa_sem_dispositivo_nenhum_recusa(tmp_path) -> None:
    """Sem `all` e sem `input`, nenhum controle atravessa — e a tela o diz."""
    _instalar(tmp_path, HEROIC, devices="dri")

    p = caixa.permissao_de(HEROIC, **_lar_de_mentira(tmp_path))

    assert p.estado == caixa.NAO_ENTRA
    assert not p.entra


def test_a_permissao_estreita_basta_para_o_controle(tmp_path) -> None:
    """`--device=input` abre `/dev/input`, que é onde o controle virtual vive."""
    _instalar(tmp_path, HEROIC, devices="input")

    assert caixa.permissao_de(HEROIC, **_lar_de_mentira(tmp_path)).entra


def test_o_override_dela_soma_e_o_com_exclamacao_tira(tmp_path) -> None:
    """O que ELA mudou é a resposta mais nova, e o `!` é a única que fecha."""
    _instalar(tmp_path, DOLPHIN, devices="dri")
    _override(tmp_path, DOLPHIN, "[Context]\ndevices=all;\n")
    assert caixa.permissao_de(DOLPHIN, **_lar_de_mentira(tmp_path)).entra, (
        "o override dela ACRESCENTA, e o `all` que ela pôs não chegou")

    _instalar(tmp_path, DOLPHIN, devices="all")
    _override(tmp_path, DOLPHIN, "[Context]\ndevices=!all;\n")
    fechada = caixa.permissao_de(DOLPHIN, **_lar_de_mentira(tmp_path))
    assert fechada.estado == caixa.NAO_ENTRA, (
        "o pacote pede `all`, ela fechou com `!all`, e o produto ainda diz "
        "que o controle entra — verde sobre uma caixa fechada à mão")
    assert "all" not in fechada.dispositivos


def test_quem_nao_e_flatpak_nao_e_caixa_fechada(tmp_path) -> None:
    """`NAO_INSTALADO` não é reprovação — é *"este não roda numa caixa"*."""
    p = caixa.permissao_de("net.lutris.Lutris", **_lar_de_mentira(tmp_path))

    assert p.estado == caixa.NAO_INSTALADO
    assert caixa.RespostaDoFlatpak((p,)).dentro == ()
    assert caixa.RespostaDoFlatpak((p,)).resumo == ""


def test_o_app_id_sai_do_caminho_e_nao_do_nome(tmp_path) -> None:
    """O mesmo nome de `.desktop` em dois lugares responde coisas diferentes."""
    do_flatpak = ("/lar/.local/share/flatpak/exports/share/applications/"
                  f"{MGBA}.desktop")

    assert caixa.app_id_do_atalho(do_flatpak) == MGBA
    assert caixa.app_id_do_atalho("/usr/share/applications/mgba.desktop") == ""
    assert caixa.app_id_do_atalho(None) == ""


def test_um_cartao_pode_ser_dois_programas_e_os_dois_contam(tmp_path) -> None:
    """**O DEFEITO MEDIDO EM 09/09/2026, e é o item 2 desta régua.**"""
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)
    achado = ("/lar/.local/share/flatpak/exports/share/applications/"
              f"{DOLPHIN}.desktop")

    ids = caixa.app_ids_do_cartao(ATALHOS_EMULADORES, achado, **_lar_de_mentira(tmp_path))

    assert ids == (DOLPHIN, MGBA), (
        "o cartão duplo entrou com um programa só — a conta do «Flatpak» "
        "mente por baixo, que é como ela disse 4 numa máquina com 5")


def test_a_frase_do_cartao_flatpak_conta_e_nomeia(tmp_path) -> None:
    """A linha do cartão: todos, ou quantos de quantos. Uma montadora só."""
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA, devices="dri")
    _instalar(tmp_path, HEROIC)

    r = caixa.resposta_do_flatpak((DOLPHIN, MGBA, HEROIC), **_lar_de_mentira(tmp_path))

    assert len(r.dentro) == 3
    assert r.resumo == "2 de 3 deixam o controle entrar"

    todos = caixa.resposta_do_flatpak((DOLPHIN, HEROIC), **_lar_de_mentira(tmp_path))
    assert todos.resumo == "2 lançadores por aqui, e o controle entra em todos"


def test_o_ambiente_e_o_do_daemon_filtrado_pela_allowlist(tmp_path) -> None:
    """O `default.env` é lido, e a allowlist do wrapper filtra o que sai."""
    env = cura.ambiente_da_ponte(_ambiente(tmp_path))

    assert env["PROTON_DISABLE_HIDRAW"] == "0x054C/0x0CE6"
    assert env["__GL_SHADER_DISK_CACHE"] == "1"
    assert "LD_PRELOAD" not in env, (
        "a cura escreveria na configuração dela uma variável que o próprio "
        "wrapper recusa exportar")


def test_sem_ambiente_publicado_a_cura_recusa_dizendo(tmp_path) -> None:
    """Sem o daemon, a cura RECUSA — não deduz a conta nem escreve vazio."""
    _instalar(tmp_path, DOLPHIN)
    vazio = tmp_path / "sem-daemon"
    vazio.mkdir()

    plano = cura.planejar("emuladores", ATALHOS_EMULADORES, **_lar_de_mentira(tmp_path),
                          pasta_do_ambiente=vazio)

    assert plano.ambiente == {}
    assert plano.impedimento == cura.SEM_AMBIENTE
    with pytest.raises(RuntimeError, match="serviço"):
        cura.escrever_a_estrada(plano)
    assert not (tmp_path / ".local/share/flatpak/overrides" / DOLPHIN).exists()


def test_o_heroic_tem_estrada_propria_e_nao_ganha_override(tmp_path) -> None:
    """O Heroic MONTA o ambiente do jogo a partir do `enviromentOptions`."""
    _instalar(tmp_path, HEROIC)
    (tmp_path / ".var/app" / HEROIC / "config/heroic").mkdir(parents=True)

    estradas = cura.estradas_do_cartao("heroic", (HEROIC, "heroic"),
                                       **_lar_de_mentira(tmp_path))

    assert [e.tipo for e in estradas] == [cura.HEROIC_CONFIG]
    assert estradas[0].arquivo.name == "config.json"


def test_o_cartao_duplo_ganha_uma_estrada_por_programa(tmp_path) -> None:
    """«Dolphin · mGBA» são dois flatpaks, e cada um tem o override dele."""
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)

    estradas = cura.estradas_do_cartao("emuladores", ATALHOS_EMULADORES,
                                       **_lar_de_mentira(tmp_path))

    assert [e.app_id for e in estradas] == [DOLPHIN, MGBA]
    assert {e.tipo for e in estradas} == {cura.FLATPAK_OVERRIDE}


@pytest.mark.parametrize("chave", ["flatpak", "steam"])
def test_quem_nao_tem_estrada_nao_ganha_botao(chave, tmp_path) -> None:
    """O «Flatpak» é o runtime dos outros e a Steam tem o atalho dela."""
    assert cura.estradas_do_cartao(chave, ("flatpak",), **_lar_de_mentira(tmp_path)) == ()


def test_a_cura_do_heroic_escreve_e_preserva_o_que_e_dela(tmp_path) -> None:
    """As nossas entram; o `MANGOHUD` dela fica; o resto do arquivo fica."""
    _instalar(tmp_path, HEROIC)
    pasta = tmp_path / ".var/app" / HEROIC / "config/heroic"
    pasta.mkdir(parents=True)
    (pasta / "config.json").write_text(json.dumps({
        "version": "v0",
        "defaultSettings": {
            "language": "pt",
            "enviromentOptions": [{"key": "MANGOHUD", "value": "1"}],
        },
    }), encoding="utf-8")

    plano = cura.planejar("heroic", (HEROIC,), **_lar_de_mentira(tmp_path),
                          pasta_do_ambiente=_ambiente(tmp_path))
    frase = cura.escrever_a_estrada(plano)

    escrito = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    opcoes = {x["key"]: x["value"]
              for x in escrito["defaultSettings"][cura.CHAVE_DO_HEROIC]}
    assert opcoes["MANGOHUD"] == "1", "a cura apagou a configuração dela"
    assert opcoes["SDL_GAMECONTROLLER_IGNORE_DEVICES"] == (
        "0x054c/0x0ce6,0x28de/0x11ff")
    assert "LD_PRELOAD" not in opcoes
    assert escrito["version"] == "v0"
    assert escrito["defaultSettings"]["language"] == "pt"
    assert "Feche e abra" in frase


def test_a_cura_do_override_escreve_no_formato_do_flatpak(tmp_path) -> None:
    """`chave=valor`, sem espaço — e a seção `[Context]` dela fica intacta."""
    _instalar(tmp_path, DOLPHIN)
    alvo = _override(tmp_path, DOLPHIN,
                     "[Context]\ndevices=all;\nfilesystems=host;\n\n"
                     "[Environment]\nMANGOHUD=1\n")

    cura.escrever_a_estrada(cura.planejar(
        "emuladores", (DOLPHIN,), **_lar_de_mentira(tmp_path),
        pasta_do_ambiente=_ambiente(tmp_path)))

    linhas = alvo.read_text(encoding="utf-8").splitlines()
    assert "[Context]" in linhas and "devices=all;" in linhas
    assert "filesystems=host;" in linhas
    assert "MANGOHUD=1" in linhas
    assert "__GL_SHADER_DISK_CACHE=1" in linhas
    assert not any(" = " in x for x in linhas), (
        f"o override saiu num formato que o Flatpak não escreve: {linhas}")


def test_a_cura_nasce_onde_nao_havia_override(tmp_path) -> None:
    """Sem arquivo, ele nasce — com a seção `[Environment]` e mais nada."""
    _instalar(tmp_path, MGBA)

    cura.escrever_a_estrada(cura.planejar(
        "emuladores", (MGBA,), **_lar_de_mentira(tmp_path),
        pasta_do_ambiente=_ambiente(tmp_path)))

    novo = tmp_path / ".local/share/flatpak/overrides" / MGBA
    corpo = novo.read_text(encoding="utf-8")
    assert corpo.startswith("[Environment]")
    assert "SDL_GAMECONTROLLER_USE_BUTTON_LABELS" not in corpo, (
        "o `default.env` de mentira não traz esta variável, e a cura escreveu "
        "uma que ninguém publicou")


def test_a_cura_devolve_a_permissao_do_arquivo_dela(tmp_path) -> None:
    """**MEDIDO PELO CONFERENTE EM 09/09/2026: o clique fechava o arquivo dela.**"""
    import os
    import stat as _stat

    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)
    dela = _override(tmp_path, DOLPHIN, "[Context]\ndevices=all;\n")
    os.chmod(dela, 0o644)
    pasta = tmp_path / ".local/share/flatpak/overrides"
    os.chmod(pasta, 0o755)
    nasce = pasta / MGBA

    cura.escrever_a_estrada(cura.planejar(
        "emuladores", ATALHOS_EMULADORES, **_lar_de_mentira(tmp_path),
        pasta_do_ambiente=_ambiente(tmp_path)))

    assert _stat.S_IMODE(dela.stat().st_mode) == 0o644, (
        "a cura fechou um arquivo de configuração DELA ao escrever nele")
    assert dela.stat().st_uid == os.getuid()
    assert _stat.S_IMODE(nasce.stat().st_mode) == 0o644, (
        "o override que NASCEU herdou o 0600 do arquivo temporário em vez da "
        "pasta em que ele mora")


def test_o_recibo_diz_o_nome_do_cartao_e_nao_a_chave(tmp_path) -> None:
    """**MEDIDO NA TELA VIVA, 09/09/2026**, e é o que esta régua guarda."""
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)
    _instalar(tmp_path, HEROIC)
    (tmp_path / ".var/app" / HEROIC / "config/heroic").mkdir(parents=True)

    um = cura.frase_do_feito(cura.planejar(
        "heroic", (HEROIC,), **_lar_de_mentira(tmp_path), nome="Heroic (Epic · GOG)",
        pasta_do_ambiente=_ambiente(tmp_path)))
    assert um.startswith("Heroic (Epic · GOG): ajustei para o jogo"), um
    assert "programas" not in um, (
        f"um programa só, e a frase fala no plural: {um}")

    plano = cura.planejar("emuladores", ATALHOS_EMULADORES, **_lar_de_mentira(tmp_path),
                          pasta_do_ambiente=_ambiente(tmp_path),
                          nome="Dolphin · mGBA")
    frase = cura.frase_do_feito(plano)

    assert frase.startswith("Dolphin · mGBA: "), frase
    assert "emuladores" not in frase, (
        f"a chave interna do cartão foi para a tarja dela: {frase}")
    assert "os 2 programas" in frase and "em cada" in frase, frase
    assert frase.count("3") <= 1, f"a contagem saiu duas vezes: {frase}"


def test_arquivo_ilegivel_recusa_e_nao_e_reescrito(tmp_path) -> None:
    """**QUEM NÃO SABE LER NÃO ESCREVE**, e sem isto a cura APAGA o que é do usuário."""
    _instalar(tmp_path, HEROIC)
    pasta = tmp_path / ".var/app" / HEROIC / "config/heroic"
    pasta.mkdir(parents=True)
    truncado = '{"defaultSettings": {"language": "pt", "wineVersion":'
    (pasta / "config.json").write_text(truncado, encoding="utf-8")

    with pytest.raises(RuntimeError, match=re.escape("config.json")):
        cura.escrever_a_estrada(cura.planejar(
            "heroic", (HEROIC,), **_lar_de_mentira(tmp_path),
            pasta_do_ambiente=_ambiente(tmp_path)))

    assert (pasta / "config.json").read_text(encoding="utf-8") == truncado, (
        "a cura reescreveu um arquivo que ela não conseguiu ler — a "
        "configuração dela foi para o lixo com uma piscada verde por cima")


def test_a_recusa_de_um_programa_nao_deixa_o_outro_escrito(tmp_path) -> None:
    """UM cartão, DUAS estradas: ou as duas, ou nenhuma."""
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)
    _override(tmp_path, MGBA, "[Context\nisto não é um arquivo de override\n")
    dolphin = tmp_path / ".local/share/flatpak/overrides" / DOLPHIN

    with pytest.raises(RuntimeError, match=re.escape(MGBA)):
        cura.escrever_a_estrada(cura.planejar(
            "emuladores", ATALHOS_EMULADORES, **_lar_de_mentira(tmp_path),
            pasta_do_ambiente=_ambiente(tmp_path)))

    assert not dolphin.exists(), (
        "o Dolphin foi ajustado e o mGBA não — meio cartão consertado, e a "
        "tela dizendo só que falhou")


def test_o_cartao_localizado_nao_oferece_conserto_e_o_flatpak_muda_de_pergunta(
    tmp_path, monkeypatch,
) -> None:
    """O cartão que ACHOU não oferece conserto, e o «Flatpak» conta as caixas."""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    for app in (HEROIC, DOLPHIN, MGBA):
        _instalar(tmp_path, app)
    exports = tmp_path / ".local/share/flatpak/exports/share/applications"
    exports.mkdir(parents=True, exist_ok=True)
    onde = (("heroic", str(exports / f"{HEROIC}.desktop")),
            ("emuladores", str(exports / f"{DOLPHIN}.desktop")),
            ("flatpak", "/usr/bin/flatpak"))

    do_disco = d.medir_no_disco(onde, **_lar_de_mentira(tmp_path))
    cartoes = {c.chave: c
               for c in d.cartoes(d.Leitura(onde_estao=onde,
                                            do_disco=do_disco))}

    emuladores = cartoes["emuladores"]
    rotulos = [a.rotulo for a in emuladores.acoes]
    assert emuladores.selo == "localizado", (
        f"o cartão «Dolphin · mGBA» deixou de sair LOCALIZADO com os dois "
        f"emuladores no disco: selo {emuladores.selo!r}")
    assert not [r for r in rotulos if r.startswith("Consertar")], (
        f"o cartão «Dolphin · mGBA» tem selo {emuladores.selo!r} — a tela diz "
        f"que está tudo no lugar — e oferece {rotulos}. Uma cura oferecida onde "
        f"a tela não declarou defeito nenhum lê-se como cura de coisa nenhuma.")
    assert d.APONTAR_ROTULO in rotulos, (
        f"o cartão achado não oferece «{d.APONTAR_ROTULO}»: {rotulos}")
    assert cartoes["flatpak"].jogos == (
        "3 lançadores por aqui, e o controle entra em todos"), (
        f"o cartão «Flatpak» não mudou de pergunta: {cartoes['flatpak'].jogos!r}")


_PORTAS_DO_DISCO = ("is_file", "is_dir", "exists", "read_text", "stat",
                    "iterdir", "glob")


def _espiar_o_disco(monkeypatch) -> list[str]:
    """Grava TODO caminho que alguém consultar daqui para a frente."""
    tocados: list[str] = []

    def espiao(nome: str, original):
        def dentro(self, *a, **k):
            tocados.append(f"{nome} {self}")
            return original(self, *a, **k)
        return dentro

    for nome in _PORTAS_DO_DISCO:
        monkeypatch.setattr(pathlib.Path, nome,
                            espiao(nome, getattr(pathlib.Path, nome)))
    return tocados


def test_a_pintura_do_tique_nao_abre_arquivo(tmp_path, monkeypatch) -> None:
    """**O DEFEITO DE 09/09/2026, e ele é do tamanho do tique.**"""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d

    for app in (HEROIC, DOLPHIN, MGBA):
        _instalar(tmp_path, app)
    exports = tmp_path / ".local/share/flatpak/exports/share/applications"
    exports.mkdir(parents=True, exist_ok=True)
    onde = (("heroic", str(exports / f"{HEROIC}.desktop")),
            ("emuladores", str(exports / f"{DOLPHIN}.desktop")),
            ("flatpak", "/usr/bin/flatpak"))
    lida = d.Leitura(onde_estao=onde,
                     do_disco=d.medir_no_disco(onde,
                                               **_lar_de_mentira(tmp_path)))

    tocados = _espiar_o_disco(monkeypatch)
    cartoes = {c.chave: c for c in d.cartoes(lida)}

    assert not tocados, (
        f"a pintura do tique abriu {len(tocados)} caminho(s) — dez vezes por "
        f"segundo, dentro dos 100 ms da janela: {tocados[:8]}")
    assert cartoes["flatpak"].jogos == (
        "3 lançadores por aqui, e o controle entra em todos"), (
        "a pintura parou de ler o disco E parou de dizer o que ele disse — "
        "verde por vacuidade")


def test_a_regua_nao_sai_do_lar_de_mentira(tmp_path, monkeypatch) -> None:
    """**O ESCAPE MEDIDO PELO CONFERENTE, 09/09/2026.**"""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d

    _instalar(tmp_path, DOLPHIN)
    onde = (("emuladores", "/qualquer/exports/nao-flatpak.desktop"),)

    tocados = _espiar_o_disco(monkeypatch)
    d.medir_no_disco(onde, **_lar_de_mentira(tmp_path))
    caixa.permissao_de(DOLPHIN, **_lar_de_mentira(tmp_path))

    fora = [x for x in tocados if str(tmp_path) not in x]
    assert not fora, (
        f"a medição saiu do lar de mentira e foi ao disco desta máquina: "
        f"{sorted(set(fora))[:8]}")

# `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`, com o endereço da
