#!/usr/bin/env python3
"""LANCADORES-ZERO-01, itens 3 e 4 — a cura por estrada e a caixa do Flatpak.

**O QUE ESTA RÉGUA COBRA**, e cada item é uma forma de recaída medida:

1. **a caixa do Flatpak se LÊ, não se supõe.** `devices=all` no `metadata` do
   pacote, mais o que ela mudou nos `overrides` — inclusive a negação com `!`,
   que é a única forma de a resposta ficar negativa numa máquina em que o
   pacote pediu tudo;
2. **um cartão pode ser DOIS programas.** O «Dolphin · mGBA» é achado pelo
   `.desktop` de um só, e a conta do cartão «Flatpak» tem de somar os dois —
   foi assim que ele disse *"4 lançadores"* numa máquina com CINCO, medido em
   09/09/2026 antes desta régua existir;
3. **a cura nunca inventa o ambiente.** Sem o `default.env` do daemon ela
   RECUSA dizendo; e o que ela escreve é filtrado pela allowlist do wrapper,
   nunca o que estiver no arquivo;
4. **a cura nunca apaga o que é dela.** As duas estradas leem, fundem e
   regravam: o `MANGOHUD` que ela pôs no Heroic e a seção `[Context]` que ela
   pôs no override continuam lá depois do clique;
5. **o formato é o do dono do arquivo.** O override sai `chave=valor`, sem
   espaço em volta do `=` — que é como o `flatpak override` o escreve e como o
   `GKeyFile` o lê.

**O LAR É DE MENTIRA em todos os casos**, e é o que permite medir as duas
estradas sem tocar num arquivo de configuração dela. A ÚNICA leitura feita no
disco real desta máquina foi a medição de 09/09/2026 que está escrita nos dois
módulos — e ela é `read_text`, nunca escrita.
"""
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

#: OS ATALHOS DO CARTÃO DUPLO, copiados de `desenho.SEM_FONTE` — dois `app-id`
#: e três nomes nativos. É a forma que o item 2 desta régua mede.
ATALHOS_EMULADORES = (DOLPHIN, "dolphin-emu", MGBA, "mgba-qt", "mgba")

#: O `default.env` do daemon, com o cabeçalho e os valores MEDIDOS no disco
#: dela em 09/09/2026 — mais uma linha fora da allowlist, que é o que o item 3
#: cobra. Os pares VID/PID são de aparelho (Sony e Valve), não de endereço de
#: rádio: não há máscara a aplicar aqui.
DEFAULT_ENV = """\
# Materializado pelo daemon do Hefesto (DEDUP-04). Não edite:
# é regravado a cada transição de estado do gamepad virtual.
PROTON_DISABLE_HIDRAW=0x054C/0x0CE6
SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x28de/0x11ff
__GL_SHADER_DISK_CACHE=1
LD_PRELOAD=/tmp/algo-que-o-wrapper-nao-exporta.so
"""


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


# ---------------------------------------------------------------------------
# 1. A CAIXA SE LÊ — o item 4 da sprint
# ---------------------------------------------------------------------------
def test_a_caixa_com_devices_all_deixa_o_controle_entrar(tmp_path) -> None:
    """Os cinco lançadores dela trazem `devices=all` — medido em 09/09/2026.

    **A MORDIDA:** troque o `metadata` por `devices=dri;` e o estado vira
    `NAO_ENTRA` — o cartão passa a dizer que o controle não atravessa.
    """
    _instalar(tmp_path, HEROIC)

    p = caixa.permissao_de(HEROIC, lar=tmp_path)

    assert p.estado == caixa.ENTRA
    assert p.dispositivos == ("all",)
    assert p.onde is not None


def test_a_caixa_sem_dispositivo_nenhum_recusa(tmp_path) -> None:
    """Sem `all` e sem `input`, nenhum controle atravessa — e a tela o diz."""
    _instalar(tmp_path, HEROIC, devices="dri")

    p = caixa.permissao_de(HEROIC, lar=tmp_path)

    assert p.estado == caixa.NAO_ENTRA
    assert not p.entra


def test_a_permissao_estreita_basta_para_o_controle(tmp_path) -> None:
    """`--device=input` abre `/dev/input`, que é onde o controle virtual vive.

    Reprovar esta caixa seria o produto dizendo *"não chega"* sobre um jogo em
    que ele chega — o defeito que esta aba inteira existe para matar.
    """
    _instalar(tmp_path, HEROIC, devices="input")

    assert caixa.permissao_de(HEROIC, lar=tmp_path).entra


def test_o_override_dela_soma_e_o_com_exclamacao_tira(tmp_path) -> None:
    """O que ELA mudou é a resposta mais nova, e o `!` é a única que fecha.

    **MEDIDO NO DISCO DELA, 09/09/2026:** `org.bleachbit.BleachBit` traz
    `filesystems=!xdg-data/applications;` — é a forma que o `flatpak override
    --nodevice` grava, e ignorá-la daria verde sobre uma caixa fechada à mão.

    **A MORDIDA, E ELA NASCEU FRACA — 09/09/2026.** A primeira versão desta
    régua punha `devices=dri` no pacote nos DOIS casos: com o ramo do `!`
    arrancado, o `!all` entrava na lista como texto literal, `all` continuava
    fora, e o teste passava com a cura no chão. **O caso da negação só morde
    com o pacote pedindo `all`** — é ele que a negação tem de TIRAR. Com a base
    certa, arrancar o ramo do `!` reprova.
    """
    _instalar(tmp_path, DOLPHIN, devices="dri")
    _override(tmp_path, DOLPHIN, "[Context]\ndevices=all;\n")
    assert caixa.permissao_de(DOLPHIN, lar=tmp_path).entra, (
        "o override dela ACRESCENTA, e o `all` que ela pôs não chegou")

    _instalar(tmp_path, DOLPHIN, devices="all")
    _override(tmp_path, DOLPHIN, "[Context]\ndevices=!all;\n")
    fechada = caixa.permissao_de(DOLPHIN, lar=tmp_path)
    assert fechada.estado == caixa.NAO_ENTRA, (
        "o pacote pede `all`, ela fechou com `!all`, e o produto ainda diz "
        "que o controle entra — verde sobre uma caixa fechada à mão")
    assert "all" not in fechada.dispositivos


def test_quem_nao_e_flatpak_nao_e_caixa_fechada(tmp_path) -> None:
    """`NAO_INSTALADO` não é reprovação — é *"este não roda numa caixa"*.

    Contá-lo como fechado baixaria a conta do cartão «Flatpak» por um lançador
    NATIVO, que não tem caixa nenhuma a abrir.
    """
    p = caixa.permissao_de("net.lutris.Lutris", lar=tmp_path)

    assert p.estado == caixa.NAO_INSTALADO
    assert caixa.RespostaDoFlatpak((p,)).dentro == ()
    assert caixa.RespostaDoFlatpak((p,)).resumo == ""


def test_o_app_id_sai_do_caminho_e_nao_do_nome(tmp_path) -> None:
    """O mesmo nome de `.desktop` em dois lugares responde coisas diferentes.

    Em `…/flatpak/exports/…` ele é de um flatpak; em `/usr/share/applications`
    é do pacote da distribuição, que não tem caixa. Derivar o `app-id` do
    rótulo do cartão diria "caixa fechada" sobre um programa que não está numa.
    """
    do_flatpak = ("/lar/.local/share/flatpak/exports/share/applications/"
                  f"{MGBA}.desktop")

    assert caixa.app_id_do_atalho(do_flatpak) == MGBA
    assert caixa.app_id_do_atalho("/usr/share/applications/mgba.desktop") == ""
    assert caixa.app_id_do_atalho(None) == ""


def test_um_cartao_pode_ser_dois_programas_e_os_dois_contam(tmp_path) -> None:
    """**O DEFEITO MEDIDO EM 09/09/2026, e é o item 2 desta régua.**

    O cartão «Dolphin · mGBA» é achado pelo `.desktop` de UM deles, e o cartão
    «Flatpak» respondeu *"4 lançadores por aqui"* numa máquina com cinco: o
    mGBA existia, tinha caixa e não entrava na conta porque ninguém perguntou
    por ele.

    **A MORDIDA:** faça `app_ids_do_cartao` devolver só o `app_id_do_atalho` e
    a lista volta a UM — a conta do cartão cai de 2 para 1 aqui, e de 5 para 4
    na máquina dela.
    """
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)
    achado = ("/lar/.local/share/flatpak/exports/share/applications/"
              f"{DOLPHIN}.desktop")

    ids = caixa.app_ids_do_cartao(ATALHOS_EMULADORES, achado, lar=tmp_path)

    assert ids == (DOLPHIN, MGBA), (
        "o cartão duplo entrou com um programa só — a conta do «Flatpak» "
        "mente por baixo, que é como ela disse 4 numa máquina com 5")


def test_a_frase_do_cartao_flatpak_conta_e_nomeia(tmp_path) -> None:
    """A linha do cartão: todos, ou quantos de quantos. Uma montadora só."""
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA, devices="dri")
    _instalar(tmp_path, HEROIC)

    r = caixa.resposta_do_flatpak((DOLPHIN, MGBA, HEROIC), lar=tmp_path)

    assert len(r.dentro) == 3
    assert r.resumo == "2 de 3 deixam o controle entrar"

    todos = caixa.resposta_do_flatpak((DOLPHIN, HEROIC), lar=tmp_path)
    assert todos.resumo == "2 lançadores por aqui, e o controle entra em todos"


# ---------------------------------------------------------------------------
# 2. O AMBIENTE VEM DO DAEMON — nunca de uma segunda conta
# ---------------------------------------------------------------------------
def test_o_ambiente_e_o_do_daemon_filtrado_pela_allowlist(tmp_path) -> None:
    """O `default.env` é lido, e a allowlist do wrapper filtra o que sai.

    O `LD_PRELOAD` do arquivo de mentira é exatamente o que o wrapper `sh`
    recusa exportar — e a cura, que escreve na configuração DELA, não pode ser
    mais permissiva que o wrapper.

    **A MORDIDA:** tire o `if nome in ENV_ALLOWLIST` e o `LD_PRELOAD` vai parar
    no `config.json` do Heroic.
    """
    env = cura.ambiente_da_ponte(_ambiente(tmp_path))

    assert env["PROTON_DISABLE_HIDRAW"] == "0x054C/0x0CE6"
    assert env["__GL_SHADER_DISK_CACHE"] == "1"
    assert "LD_PRELOAD" not in env, (
        "a cura escreveria na configuração dela uma variável que o próprio "
        "wrapper recusa exportar")


def test_sem_ambiente_publicado_a_cura_recusa_dizendo(tmp_path) -> None:
    """Sem o daemon, a cura RECUSA — não deduz a conta nem escreve vazio.

    **A MORDIDA:** faça `ambiente_da_ponte` devolver a allowlist com valores
    inventados e esta régua passa a aceitar um arquivo escrito sem medição
    nenhuma; faça `escrever_a_estrada` devolver frase em vez de levantar e a
    tela dá piscada verde sobre um arquivo que ninguém tocou.
    """
    _instalar(tmp_path, DOLPHIN)
    vazio = tmp_path / "sem-daemon"
    vazio.mkdir()

    plano = cura.planejar("emuladores", ATALHOS_EMULADORES, lar=tmp_path,
                          pasta_do_ambiente=vazio)

    assert plano.ambiente == {}
    assert plano.impedimento == cura.SEM_AMBIENTE
    with pytest.raises(RuntimeError, match="serviço"):
        cura.escrever_a_estrada(plano)
    assert not (tmp_path / ".local/share/flatpak/overrides" / DOLPHIN).exists()


# ---------------------------------------------------------------------------
# 3. AS ESTRADAS — quem recebe a cura, e por onde
# ---------------------------------------------------------------------------
def test_o_heroic_tem_estrada_propria_e_nao_ganha_override(tmp_path) -> None:
    """O Heroic MONTA o ambiente do jogo a partir do `enviromentOptions`.

    Escrever nos dois lugares poria a mesma variável em duas listas que
    envelhecem separadas, e a próxima pessoa não saberia qual manda.
    """
    _instalar(tmp_path, HEROIC)
    (tmp_path / ".var/app" / HEROIC / "config/heroic").mkdir(parents=True)

    estradas = cura.estradas_do_cartao("heroic", (HEROIC, "heroic"),
                                       lar=tmp_path)

    assert [e.tipo for e in estradas] == [cura.HEROIC_CONFIG]
    assert estradas[0].arquivo.name == "config.json"


def test_o_cartao_duplo_ganha_uma_estrada_por_programa(tmp_path) -> None:
    """«Dolphin · mGBA» são dois flatpaks, e cada um tem o override dele."""
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)

    estradas = cura.estradas_do_cartao("emuladores", ATALHOS_EMULADORES,
                                       lar=tmp_path)

    assert [e.app_id for e in estradas] == [DOLPHIN, MGBA]
    assert {e.tipo for e in estradas} == {cura.FLATPAK_OVERRIDE}


@pytest.mark.parametrize("chave", ["flatpak", "steam"])
def test_quem_nao_tem_estrada_nao_ganha_botao(chave, tmp_path) -> None:
    """O «Flatpak» é o runtime dos outros e a Steam tem o atalho dela.

    Um botão «Consertar» em qualquer dos dois seria o botão que finge — a
    regra desta aba desde que ela nasceu.
    """
    assert cura.estradas_do_cartao(chave, ("flatpak",), lar=tmp_path) == ()
    assert not cura.tem_estrada(chave, ("flatpak",), lar=tmp_path)


# ---------------------------------------------------------------------------
# 4. A ESCRITA — e o que ela NÃO pode apagar
# ---------------------------------------------------------------------------
def test_a_cura_do_heroic_escreve_e_preserva_o_que_e_dela(tmp_path) -> None:
    """As nossas entram; o `MANGOHUD` dela fica; o resto do arquivo fica.

    **A MORDIDA:** troque a fusão por uma lista só com as nossas — sem as que
    já estavam lá — e o `MANGOHUD` some: a cura apaga a configuração dela em
    silêncio, com uma piscada verde por cima.
    """
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

    plano = cura.planejar("heroic", (HEROIC,), lar=tmp_path,
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
    """`chave=valor`, sem espaço — e a seção `[Context]` dela fica intacta.

    O arquivo é lido pelo `GKeyFile` do Flatpak. Escrever num formato que o
    dono do arquivo não emite é convidar o dia em que ele deixa de ler, num
    arquivo de configuração dela e sem aviso.

    **A MORDIDA:** troque `_render_ini` por `ConfigParser.write` e as linhas
    saem `chave = valor`; apague a leitura do arquivo existente e a
    `[Context]` dela desaparece.
    """
    _instalar(tmp_path, DOLPHIN)
    alvo = _override(tmp_path, DOLPHIN,
                     "[Context]\ndevices=all;\nfilesystems=host;\n\n"
                     "[Environment]\nMANGOHUD=1\n")

    cura.escrever_a_estrada(cura.planejar(
        "emuladores", (DOLPHIN,), lar=tmp_path,
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
        "emuladores", (MGBA,), lar=tmp_path,
        pasta_do_ambiente=_ambiente(tmp_path)))

    novo = tmp_path / ".local/share/flatpak/overrides" / MGBA
    corpo = novo.read_text(encoding="utf-8")
    assert corpo.startswith("[Environment]")
    assert "SDL_GAMECONTROLLER_USE_BUTTON_LABELS" not in corpo, (
        "o `default.env` de mentira não traz esta variável, e a cura escreveu "
        "uma que ninguém publicou")


def test_o_recibo_diz_o_nome_do_cartao_e_nao_a_chave(tmp_path) -> None:
    """**MEDIDO NA TELA VIVA, 09/09/2026**, e é o que esta régua guarda.

    A tarja verde dizia *"Ajustei o ambiente de heroic"* — a chave do
    `data-lancador` na frente dela, que é a língua de dentro num recado de
    tela. E dizia *"(5): 5 ajustes"*, a mesma contagem duas vezes.

    A frase também não leva ARTIGO antes do nome: ele vem do cartão, inclusive
    de um que ELA acrescentou, e adivinhar o gênero de um nome que ainda não
    existe é palpite na tela dela — a razão já medida em
    `desenho_dos_lancadores.NOVO_PARA_O_CARTAO`.

    **A MORDIDA:** troque `plano.rotulo` por `plano.cartao` em `frase_do_feito`
    e a chave interna volta para a tarja.
    """
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)
    _instalar(tmp_path, HEROIC)
    (tmp_path / ".var/app" / HEROIC / "config/heroic").mkdir(parents=True)

    um = cura.frase_do_feito(cura.planejar(
        "heroic", (HEROIC,), lar=tmp_path, nome="Heroic (Epic · GOG)",
        pasta_do_ambiente=_ambiente(tmp_path)))
    assert um.startswith("Heroic (Epic · GOG): ajustei para o jogo"), um
    assert "programas" not in um, (
        f"um programa só, e a frase fala no plural: {um}")

    plano = cura.planejar("emuladores", ATALHOS_EMULADORES, lar=tmp_path,
                          pasta_do_ambiente=_ambiente(tmp_path),
                          nome="Dolphin · mGBA")
    frase = cura.frase_do_feito(plano)

    assert frase.startswith("Dolphin · mGBA: "), frase
    assert "emuladores" not in frase, (
        f"a chave interna do cartão foi para a tarja dela: {frase}")
    assert "os 2 programas" in frase and "em cada" in frase, frase
    assert frase.count("3") <= 1, f"a contagem saiu duas vezes: {frase}"


def test_arquivo_ilegivel_recusa_e_nao_e_reescrito(tmp_path) -> None:
    """**QUEM NÃO SABE LER NÃO ESCREVE**, e sem isto a cura APAGA o que é dela.

    Um `config.json` truncado (o Heroic morreu no meio de um `write`) ou um
    override que não abre continuam tendo a configuração DELA lá dentro.
    Reescrevê-los com `{}` mais o nosso ambiente jogaria fora a biblioteca, o
    caminho do Wine, a `[Context]` que ela deu à mão — em silêncio, e com uma
    piscada verde por cima.

    **A MORDIDA:** faça `_ler_heroic` devolver `{}` no ramo do `ValueError` (ou
    tire a conferência de :func:`escrever_a_estrada`) e o arquivo truncado é
    substituído pelo nosso — o `assert` do conteúdo intacto reprova.
    """
    _instalar(tmp_path, HEROIC)
    pasta = tmp_path / ".var/app" / HEROIC / "config/heroic"
    pasta.mkdir(parents=True)
    truncado = '{"defaultSettings": {"language": "pt", "wineVersion":'
    (pasta / "config.json").write_text(truncado, encoding="utf-8")

    with pytest.raises(RuntimeError, match=re.escape("config.json")):
        cura.escrever_a_estrada(cura.planejar(
            "heroic", (HEROIC,), lar=tmp_path,
            pasta_do_ambiente=_ambiente(tmp_path)))

    assert (pasta / "config.json").read_text(encoding="utf-8") == truncado, (
        "a cura reescreveu um arquivo que ela não conseguiu ler — a "
        "configuração dela foi para o lixo com uma piscada verde por cima")


def test_a_recusa_de_um_programa_nao_deixa_o_outro_escrito(tmp_path) -> None:
    """UM cartão, DUAS estradas: ou as duas, ou nenhuma.

    Recusar no meio do laço deixaria o Dolphin ajustado, o mGBA não, e a tela
    mostrando só a recusa — o pior dos dois mundos, e impossível de diagnosticar
    depois.

    **A MORDIDA:** tire o laço de conferência de `escrever_a_estrada` e o
    override do Dolphin nasce mesmo com o do mGBA ilegível.
    """
    _instalar(tmp_path, DOLPHIN)
    _instalar(tmp_path, MGBA)
    _override(tmp_path, MGBA, "[Context\nisto não é um arquivo de override\n")
    dolphin = tmp_path / ".local/share/flatpak/overrides" / DOLPHIN

    with pytest.raises(RuntimeError, match=re.escape(MGBA)):
        cura.escrever_a_estrada(cura.planejar(
            "emuladores", ATALHOS_EMULADORES, lar=tmp_path,
            pasta_do_ambiente=_ambiente(tmp_path)))

    assert not dolphin.exists(), (
        "o Dolphin foi ajustado e o mGBA não — meio cartão consertado, e a "
        "tela dizendo só que falhou")


# ---------------------------------------------------------------------------
# 5. O CARTÃO — a régua olha o que a tela recebe
# ---------------------------------------------------------------------------
def test_o_cartao_localizado_ganha_o_consertar_e_o_flatpak_muda_de_pergunta(
    tmp_path, monkeypatch,
) -> None:
    """Os dois itens juntos, do lado de quem olha a tela.

    **A MORDIDA:** apague o ramo do `consertar` em `cartao_sem_censo` e o
    primeiro `assert` reprova nomeando o cartão; devolva `biblioteca.resumo or
    "—"` e o cartão «Flatpak» volta ao travessão.
    """
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

    cartoes = {c.chave: c for c in d.cartoes(d.Leitura(onde_estao=onde))}

    gestos = [a.gesto for a in cartoes["emuladores"].acoes]
    assert d.CONSERTAR_LANCADOR in gestos, (
        f"o cartão «Dolphin · mGBA» está LOCALIZADO, tem por onde receber o "
        f"ambiente e não oferece o Consertar: {gestos}")
    assert cartoes["flatpak"].jogos == (
        "3 lançadores por aqui, e o controle entra em todos"), (
        f"o cartão «Flatpak» não mudou de pergunta: {cartoes['flatpak'].jogos!r}")
    assert d.CONSERTAR_LANCADOR not in [a.gesto for a in cartoes["flatpak"].acoes]


def test_o_gesto_sem_data_v_recusa_e_nao_escreve(tmp_path, monkeypatch) -> None:
    """Um clique sem `data-v` escreveria na configuração de um lançador ao acaso.

    É a mesma mordida que o `abrir-lancador` e o `tirar-daqui` já têm, e pela
    mesma razão: o botão é o mesmo nos seis cartões.
    """
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores  # noqa: F401

    monkeypatch.setenv("HOME", str(tmp_path))
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    gesto = pacotes.GESTOS[("07-lancadores.html", d.CONSERTAR_LANCADOR)]

    with pytest.raises(ValueError, match="qual lançador"):
        gesto(ctx, {}, None)


def test_o_gesto_da_cura_declara_que_mexe_na_maquina_dela() -> None:
    """Ele escreve arquivo DE OUTRO PROGRAMA — a prova automática não o clica.

    `pacotes.perigosos()` é DERIVADO do `grava=` do próprio gesto desde
    06/09/2026, e é o que impede a lista de chegar um commit atrasada. Sem esta
    linha, a `--prova-gesto` escreveria no `config.json` do Heroic dela.
    """
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as d
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores  # noqa: F401

    assert ("07-lancadores.html", d.CONSERTAR_LANCADOR) in pacotes.perigosos()
