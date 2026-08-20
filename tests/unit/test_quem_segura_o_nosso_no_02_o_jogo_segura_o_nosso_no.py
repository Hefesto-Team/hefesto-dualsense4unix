"""QUEM-SEGURA-O-NOSSO-NO-01/PEÇA 2 — o instrumento que sustenta O JOGO RECEBEU.

O QUE ESTE ARQUIVO GUARDA
--------------------------
`scripts/ensaios/o_jogo_segura_o_nosso_no.py` é a régua do primeiro degrau da
direção de ENTRADA. Até 20/08/2026 aquela direção tinha ZERO células no mapa
de canais porque não havia instrumento; assim que houver, tudo o que ele
afirmar vira afirmação forte no `docs/data/mapa-controles.csv`. Um instrumento
nessa posição tem de ser guardado por testes que MORDEM — a lição desta casa é
que *"o instrumento mente mais que o produto"*, e três medições falsas num só
dia já saíram de régua que ninguém conferia.

NENHUM TESTE DAQUI TOCA O `/sys` OU O `/proc` VIVOS
----------------------------------------------------
Todas as árvores são forjadas em `tmp_path`, e os "nós de /dev" são arquivos
comuns. É a disciplina da TEMPESTADE-DE-TECLADOS-01 aplicada ao lado dos
scripts: nada é criado em `/dev/input`, nada é aberto, e nenhum teste depende
do que estava plugado na máquina dela na hora.

AS OITO MORDIDAS — arrancadas uma a uma, vistas reprovar, devolvidas
--------------------------------------------------------------------
1. arrancar `e_vpad_do_hefesto` e casar por vid/pid, que é o que uma pessoa de
   boa-fé faria: `test_o_vpad_e_o_carimbo_e_nunca_o_vidpid` reprova, porque um
   DualSense **Edge de verdade** (054c:0df2, o mesmo par que o vpad forja)
   passa a ser aceito como nosso;
2. trocar o casamento EXATO do nome do uinput por `startswith("Microsoft X-Box
   360 pad")`: `test_o_espelho_xbox_do_steam_nao_e_o_nosso_vpad` reprova — o
   espelho que o Steam Input publica de cada controle entra como se fosse o
   nosso vpad;
3. arrancar a exigência de `HID_ID` no `uevent` do candidato a device HID pai:
   `test_o_no_de_uinput_nao_inventa_um_device_hid_pai` reprova, porque
   `/sys/devices/virtual/input/inputN` tem um pai chamado `input` e a subida
   de dois níveis entrega `/sys/devices/virtual` como se fosse device;
4. casar por `os.readlink` do fd (o que o `quem_o_jogo_abre.py` faz):
   `test_o_censo_casa_por_inode_e_nao_por_caminho` reprova;
5. casar só por `st_ino`, sem o `st_dev` — no dicionário E na consulta, senão
   a mordida sai degenerada e reprova o teste errado:
   `test_inode_igual_em_outro_sistema_de_arquivos_nao_casa` reprova;
6. trocar `os.stat` por `open()` em `_chave`: `test_o_censo_nao_abre_o_no`
   reprova (a thread fica presa no FIFO sem escritor e não termina);
7. arrancar a âncora `SteamAppId`:
   `test_processo_que_so_menciona_exe_nao_entra_na_arvore` reprova — é o caso
   REAL medido em 20/08/2026 com nenhum jogo aberto, em que o `earlyoom` e o
   binário de outro programa casaram com a palavra do padrão. O IRMÃO dele,
   `test_arvore_so_de_recusados_diz_nao_sondado`, guarda a outra metade: que
   uma árvore feita só de recusados não vire `NENHUM` lá no veredito. São dois
   testes porque são dois defeitos, e a mordida de um não é a do outro;
8. fazer `NENHUM` sair sem conferir o censo da árvore:
   `test_nenhum_exige_o_censo_da_arvore_fechado` reprova.

E uma nona, invertida, que fica registrada porque é o erro simétrico: exigir o
censo do MUNDO para poder dizer `NENHUM`. Nesta máquina `(sd-pam)` e dois
`ssh-agent` zeram o `PR_SET_DUMPABLE` e nunca se deixam ler — o censo global
não fecha nunca, e `NENHUM` viraria um veredito decorativo que jamais sai.
`test_ilegivel_fora_da_arvore_nao_impede_o_nenhum` prende essa distinção.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "o_jogo_segura_o_nosso_no.py"


def _carregar_o_instrumento() -> Any:
    """Carrega o instrumento pelo caminho — `scripts/ensaios/` não é pacote.

    Mesmo precedente do `test_giro_e_buraco_a_regua_sai_do_aparelho`: o nome
    sob o qual ele entra em `sys.modules` é OUTRO, para que este arquivo nunca
    roube o módulo de quem o importe pelo nome real.
    """
    pasta = str(_INSTRUMENTO.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    especificacao = importlib.util.spec_from_file_location(
        "o_jogo_segura_o_nosso_no_sob_ensaio", _INSTRUMENTO
    )
    if especificacao is None or especificacao.loader is None:
        raise AssertionError(f"não consegui carregar {_INSTRUMENTO}")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


INS = _carregar_o_instrumento()

#: O `uniq` que o produto forja por jogador. Faixa localmente administrada:
#: por definição não colide com endereço de fábrica, e é faixa permitida em
#: `tests/` (ver `test_anonimato_de_fixtures`).
UNIQ_DO_VPAD = "02:fe:00:00:00:01"

#: O placeholder canônico de fixture desta casa para um controle FÍSICO.
UNIQ_FORJADO_DE_FISICO = "aa:bb:cc:00:00:11"


# ---------------------------------------------------------------------------
# Forja de árvores — nada aqui existe fora do `tmp_path`
# ---------------------------------------------------------------------------


def _escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")


def _forjar_no_hid(
    raiz: Path,
    *,
    evento: str,
    nome: str,
    uniq: str,
    uevent: str,
    bustype: str = "0003",
    hidraw: str | None = None,
    marca_do_dir: str = "0003:054C:0DF2.0001",
) -> Path:
    """Um nó de entrada pendurado num device HID, como o sysfs o publica.

    `/sys/class/input/eventN` é diretório; `eventN/device` é link para
    `<device HID>/input/inputM`. É essa forma — e não o caminho absoluto — que
    o instrumento navega.
    """
    dir_hid = raiz / "devices" / marca_do_dir
    dir_input = dir_hid / "input" / f"input{evento[len('event'):]}"
    _escrever(dir_hid / "uevent", uevent)
    _escrever(dir_input / "name", nome + "\n")
    if uniq:
        _escrever(dir_input / "uniq", uniq + "\n")
    _escrever(dir_input / "id" / "bustype", bustype + "\n")
    if hidraw:
        (dir_hid / "hidraw" / hidraw).mkdir(parents=True, exist_ok=True)
    classe = raiz / "class" / "input" / evento
    classe.mkdir(parents=True, exist_ok=True)
    (classe / "device").symlink_to(dir_input, target_is_directory=True)
    return dir_input


def _forjar_no_de_uinput(
    raiz: Path, *, evento: str, nome: str, uevent_do_avo: str = ""
) -> Path:
    """O vpad de uinput: `/sys/devices/virtual/input/inputN`, sem device HID.

    O pai dele TAMBÉM se chama `input` — é essa a armadilha que a exigência de
    `HID_ID` desarma. `uevent_do_avo` existe para o teste poder pôr conteúdo
    em `/sys/devices/virtual/uevent` e provar que ele não é aceito.
    """
    dir_input = raiz / "devices" / "virtual" / "input" / f"input{evento[5:]}"
    _escrever(dir_input / "name", nome + "\n")
    _escrever(dir_input / "id" / "bustype", "0003\n")
    if uevent_do_avo:
        _escrever(raiz / "devices" / "virtual" / "uevent", uevent_do_avo)
    classe = raiz / "class" / "input" / evento
    classe.mkdir(parents=True, exist_ok=True)
    (classe / "device").symlink_to(dir_input, target_is_directory=True)
    return dir_input


def _uevent_do_vpad(uniq: str = UNIQ_DO_VPAD) -> str:
    return (
        "DRIVER=playstation\n"
        "HID_ID=0003:0000054C:00000DF2\n"
        "HID_NAME=DualSense Wireless Controller (Hefesto P1)\n"
        f"HID_PHYS={INS.VPAD_HID_PHYS}\n"
        f"HID_UNIQ={uniq}\n"
    )


def _uevent_do_edge_de_verdade() -> str:
    """Um DualSense **Edge** físico: o MESMO vid/pid que o vpad forja.

    Nada aqui é nosso: `HID_PHYS` é um caminho USB e o `HID_UNIQ` é endereço
    de fábrica forjado. Quem casar por `054c:0df2` mede este aparelho achando
    que mediu o vpad.
    """
    return (
        "DRIVER=playstation\n"
        "HID_ID=0003:0000054C:00000DF2\n"
        "HID_NAME=Sony Interactive Entertainment DualSense Edge Controller\n"
        "HID_PHYS=usb-0000:0c:00.3-4/input3\n"
        f"HID_UNIQ={UNIQ_FORJADO_DE_FISICO}\n"
    )


def _forjar_processo(
    raiz: Path,
    pid: int,
    *,
    cmdline: str = "jogo.exe",
    environ: str = "",
    fds: dict[str, Path] | None = None,
) -> Path:
    """Um `/proc/<pid>` de mentira, com `fd/` de links para arquivos comuns."""
    dir_pid = raiz / str(pid)
    (dir_pid / "fd").mkdir(parents=True, exist_ok=True)
    (dir_pid / "cmdline").write_bytes(cmdline.encode("utf-8").replace(b" ", b"\0"))
    (dir_pid / "environ").write_bytes(environ.encode("utf-8"))
    for numero, alvo in (fds or {}).items():
        (dir_pid / "fd" / numero).symlink_to(alvo)
    return dir_pid


def _alvo_do_arquivo(arquivo: Path, *, classe: str = "nosso", papel: str = "gamepad") -> Any:
    st = arquivo.stat()
    return INS.Alvo(
        classe=classe,
        rotulo="P1" if classe == "nosso" else UNIQ_FORJADO_DE_FISICO,
        papel=papel,
        caminho=str(arquivo),
        chave=(st.st_dev, st.st_ino),
        reguas="B (sysfs)",
    )


# ---------------------------------------------------------------------------
# A identidade: o carimbo, e nunca o vid/pid
# ---------------------------------------------------------------------------


def test_o_vpad_e_o_carimbo_e_nunca_o_vidpid(tmp_path: Path) -> None:
    """O vpad entra pelo `HID_PHYS`; um Edge de verdade, com o MESMO par
    `054c:0df2`, fica de fora.

    MORDIDA 1: casar por vid/pid faz o Edge entrar, e o instrumento passa a
    medir o controle de outra pessoa achando que mediu o nosso.
    """
    _forjar_no_hid(
        tmp_path,
        evento="event22",
        nome="DualSense Wireless Controller (Hefesto P1)",
        uniq=UNIQ_DO_VPAD,
        uevent=_uevent_do_vpad(),
        hidraw="hidraw9",
    )
    _forjar_no_hid(
        tmp_path,
        evento="event30",
        nome="Sony Interactive Entertainment DualSense Edge Controller",
        uniq=UNIQ_FORJADO_DE_FISICO,
        uevent=_uevent_do_edge_de_verdade(),
        hidraw="hidraw7",
        marca_do_dir="0003:054C:0DF2.0009",
    )

    achados = INS.vpads_do_sysfs(raiz=str(tmp_path / "class" / "input"))

    assert [n.evento for n in achados] == ["event22"]
    assert achados[0].hidraw == "/dev/hidraw9"
    assert INS.VPAD_HID_PHYS in achados[0].marca


def test_o_espelho_xbox_do_steam_nao_e_o_nosso_vpad(tmp_path: Path) -> None:
    """O casamento do nome do uinput é EXATO, e é por causa do Steam Input.

    O Steam publica um espelho Xbox de CADA controle que enxerga — o nosso
    vpad inclusive —, e esses espelhos se chamam `Microsoft X-Box 360 pad 0`.

    MORDIDA 2: trocar o `==` por `startswith("Microsoft X-Box 360 pad")` faz o
    espelho entrar como se fosse nosso, e o instrumento mede o reflexo.
    """
    _forjar_no_de_uinput(tmp_path, evento="event10", nome=INS.XBOX360_NAME)
    _forjar_no_de_uinput(tmp_path, evento="event21", nome="Microsoft X-Box 360 pad 0")
    _forjar_no_de_uinput(tmp_path, evento="event23", nome="Microsoft X-Box 360 pad 1")

    achados = INS.vpads_do_sysfs(raiz=str(tmp_path / "class" / "input"))

    assert [n.evento for n in achados] == ["event10"]
    assert "EXATO" in achados[0].marca


def test_o_no_de_uinput_nao_inventa_um_device_hid_pai(tmp_path: Path) -> None:
    """`/sys/devices/virtual/input/inputN` tem um pai chamado `input` — e ali
    não há device HID nenhum.

    MORDIDA 3: sem a exigência de `HID_ID` no `uevent` do candidato, a subida
    de dois níveis devolve `/sys/devices/virtual`, e o instrumento passa a
    acreditar no `uevent` de um diretório que não descreve aparelho algum.
    """
    _forjar_no_de_uinput(
        tmp_path,
        evento="event10",
        nome=INS.XBOX360_NAME,
        uevent_do_avo="MAJOR=13\nMINOR=64\nDEVNAME=input/event10\n",
    )

    achados = INS.vpads_do_sysfs(raiz=str(tmp_path / "class" / "input"))

    assert len(achados) == 1
    assert achados[0].dir_hid == ""
    assert achados[0].hidraw is None


def test_os_tres_nos_do_mesmo_vpad_entram_todos(tmp_path: Path) -> None:
    """Um DualSense publica gamepad, touchpad e sensores com o MESMO `uniq`.

    O jogo pode segurar qualquer um deles, e segurar o `Motion Sensors` é ter
    recebido o nosso vpad tanto quanto segurar o gamepad. Parar no primeiro nó
    do aparelho perderia dois terços da resposta.
    """
    for evento, sufixo in (
        ("event22", ""),
        ("event23", " Touchpad"),
        ("event24", " Motion Sensors"),
    ):
        _forjar_no_hid(
            tmp_path,
            evento=evento,
            nome=f"DualSense Wireless Controller (Hefesto P1){sufixo}",
            uniq=UNIQ_DO_VPAD,
            uevent=_uevent_do_vpad(),
            marca_do_dir=f"0003:054C:0DF2.000{evento[-1]}",
        )

    achados = INS.vpads_do_sysfs(raiz=str(tmp_path / "class" / "input"))

    assert sorted(n.papel for n in achados) == ["gamepad", "movimento", "touchpad"]


# ---------------------------------------------------------------------------
# As duas réguas do alvo
# ---------------------------------------------------------------------------


def _vpad_do_produto(**campos: Any) -> Any:
    base: dict[str, Any] = {
        "player": 1,
        "uniq": UNIQ_DO_VPAD,
        "nome": "DualSense Wireless Controller (Hefesto P1)",
        "backend": "uhid",
        "evdev": None,
        "hidraw": None,
        "ino": None,
        "hidraw_ino": None,
        "game_open": False,
        "campos_ausentes": (),
    }
    base.update(campos)
    return INS.VpadDoProduto(**base)


def _no_do_sysfs(caminho: Path, **campos: Any) -> Any:
    base: dict[str, Any] = {
        "evento": os.path.basename(str(caminho)),
        "caminho": str(caminho),
        "nome": "DualSense Wireless Controller (Hefesto P1)",
        "uniq": UNIQ_DO_VPAD,
        "papel": "gamepad",
        "marca": "HID_PHYS=hefesto-vpad",
        "dir_hid": "",
        "hidraw": None,
    }
    base.update(campos)
    return INS.NoDeEntrada(**base)


def test_as_duas_reguas_concordando_ficam_registradas(tmp_path: Path) -> None:
    """Quando o produto e o sysfs apontam o MESMO inode, o alvo diz as duas."""
    no = tmp_path / "event22"
    no.write_text("", encoding="utf-8")
    vpad = _vpad_do_produto(evdev=str(no), ino=no.stat().st_ino)

    alvos, avisos = INS.montar_alvos([vpad], [_no_do_sysfs(no)])

    assert avisos == []
    assert alvos[0].reguas == "A (produto) + B (sysfs)"
    assert alvos[0].rotulo == "P1"
    assert alvos[0].sondado is True


def test_ino_diferente_do_publicado_vira_nao_sondado(tmp_path: Path) -> None:
    """O produto publicou um inode e o `stat` de agora lê outro: o nó foi
    renumerado entre uma leitura e a outra.

    MORDIDA: acreditar no bloco publicado sem reconferir faz este alvo sair
    `sondado`, e o instrumento passa a procurar em `/proc` por um inode que
    já é de outro aparelho — a renumeração é exatamente o que o degrau proíbe.
    """
    no = tmp_path / "event22"
    no.write_text("", encoding="utf-8")
    vpad = _vpad_do_produto(evdev=str(no), ino=no.stat().st_ino + 4096)

    alvos, _avisos = INS.montar_alvos([vpad], [_no_do_sysfs(no)])

    assert alvos[0].reguas == "A e B DISCORDAM"
    assert alvos[0].sondado is False
    assert alvos[0].nota.startswith("NÃO SONDADO")


def test_no_que_so_a_regua_do_produto_enxerga_nao_e_afirmado(tmp_path: Path) -> None:
    """O produto publica um caminho que a varredura de `/sys` não reconhece
    como nosso. Duas réguas discordando sobre a EXISTÊNCIA do nó não viram
    veredito — viram aviso e um alvo marcado `NÃO SONDADO`."""
    no = tmp_path / "event42"
    no.write_text("", encoding="utf-8")
    vpad = _vpad_do_produto(evdev=str(no), ino=no.stat().st_ino)

    alvos, avisos = INS.montar_alvos([vpad], [])

    assert any("discordam sobre a EXISTÊNCIA" in aviso for aviso in avisos)
    assert [a.sondado for a in alvos] == [False]


def test_campo_ausente_e_campo_none_nao_sao_a_mesma_coisa() -> None:
    """Daemon VELHO e daemon que não resolveu o nó chegam diferentes.

    O `install` editable desta casa faz o daemon vivo ser mais velho que o
    código o tempo todo — a cura só vale no próximo start. Se "o campo não
    existe" e "o campo é None" saíssem iguais, o instrumento diria "o produto
    não sabe onde está o nó" sobre um produto que sabe e ainda não foi
    reiniciado.

    MORDIDA: trocar `c not in bloco` por `bloco.get(c) is None` funde os dois
    silêncios e este teste reprova nas duas metades.
    """
    velho = {"player": 1, "vpad_uniq": UNIQ_DO_VPAD, "vpad_nome": "x"}
    novo_sem_resolver = {
        "player": 2,
        "vpad_uniq": None,
        "vpad_nome": "y",
        "evdev": None,
        "hidraw": None,
        "ino": None,
        "hidraw_ino": None,
        "game_open": False,
    }

    lidos = INS.vpads_do_produto(
        {"rumble_ff": {"per_vpad": [velho, novo_sem_resolver]}}
    )

    assert lidos[0].campos_ausentes == INS.CAMPOS_DO_NO
    assert lidos[1].campos_ausentes == ()
    assert lidos[0].declara_o_no is False
    assert lidos[1].declara_o_no is False


def test_game_open_viaja_e_nao_e_evidencia_de_jogo() -> None:
    """`game_open` sai do payload como está — e o veto da NUMA-02 continua
    valendo: sessão uhid aberta é `alguém segura este nó`, nunca `o jogo
    recebeu`. Quem responde pelo degrau é o censo de `/proc`, não este campo.
    """
    lidos = INS.vpads_do_produto(
        {"rumble_ff": {"per_vpad": [
            {"player": 1, "evdev": None, "hidraw": None, "ino": None,
             "hidraw_ino": None, "game_open": True},
        ]}}
    )
    assert lidos[0].game_open is True
    assert lidos[0].declara_o_no is False


# ---------------------------------------------------------------------------
# O transporte: duas rotas, e discordância vira NÃO SONDADO
# ---------------------------------------------------------------------------


def _aparelho(transporte: str) -> Any:
    return INS.Aparelho(
        hidraw="hidraw1",
        caminho_hidraw="/dev/hidraw1",
        dir_device="/nao/importa",
        mac=UNIQ_FORJADO_DE_FISICO,
        nome="Sony Interactive Entertainment DualSense Wireless Controller",
        transporte=transporte,
        e_vpad=False,
        rotulo="",
    )


@pytest.mark.parametrize(
    ("bustype", "rota1", "esperado"),
    [
        ("0003", INS.CABO, INS.CABO),
        ("0005", INS.RADIO, INS.RADIO),
        ("0005", INS.CABO, INS.V_NAO_SONDADO),
        ("0003", INS.RADIO, INS.V_NAO_SONDADO),
    ],
)
def test_transporte_sai_das_duas_rotas(
    tmp_path: Path, bustype: str, rota1: str, esperado: str
) -> None:
    """`HID_ID` (rota 1) e `id/bustype` do nó (rota 2) têm de concordar.

    O `ps_allocate_input_dev` copia o `bustype` do `hdev` para o `input_dev`,
    então elas concordam sempre — a não ser que uma delas esteja olhando para
    outro aparelho, que é justamente o que se quer saber ANTES de escrever
    `cabo` ou `rádio` numa célula do mapa.

    MORDIDA: devolver `rota1` sem conferir a rota 2 faz os dois casos de
    discordância virarem afirmação, e as duas últimas linhas reprovam.
    """
    raiz = tmp_path / "class" / "input"
    _escrever(raiz / "event2" / "device" / "id" / "bustype", bustype + "\n")

    veredito, saiu1, saiu2 = INS.transporte_por_duas_rotas(
        _aparelho(rota1),
        [("DualSense", "/dev/input/event2")],
        raiz_class_input=str(raiz),
    )

    assert veredito == esperado
    assert saiu1 == rota1
    assert saiu2 in (INS.CABO, INS.RADIO)


def test_topologia_de_sysfs_nao_transforma_radio_em_cabo(tmp_path: Path) -> None:
    """A armadilha paga em 11/08/2026, em forma de teste.

    Com BlueZ >= 5.73 o `bluetoothd` cria o HID dos DualSense FÍSICOS de rádio
    por `/dev/uhid`, sob `/devices/virtual/misc/uhid/` — no mesmíssimo lugar do
    nosso vpad. Quem decidisse transporte por "mora em virtual, logo é vpad, e
    vpad forja USB, logo é cabo" trocaria a coluna inteira do ensaio.
    """
    raiz = tmp_path / "class" / "input"
    _escrever(raiz / "event2" / "device" / "id" / "bustype", "0005\n")
    aparelho = _aparelho(INS.RADIO)
    object.__setattr__(
        aparelho, "dir_device", "/sys/devices/virtual/misc/uhid/0005:054C:0CE6.0003"
    )

    veredito, _r1, _r2 = INS.transporte_por_duas_rotas(
        aparelho, [("DualSense", "/dev/input/event2")], raiz_class_input=str(raiz)
    )

    assert veredito == INS.RADIO


# ---------------------------------------------------------------------------
# O censo: por inode, sem abrir nada
# ---------------------------------------------------------------------------


def test_o_censo_casa_por_inode_e_nao_por_caminho(tmp_path: Path) -> None:
    """O fd aponta para UM caminho e o alvo é OUTRO — o mesmo inode.

    É o critério do degrau, ao pé da letra: o minor é reciclado, e `event22`
    já foi vpad DualSense às 01:40 e vpad Xbox às 01:50 na máquina dela.

    MORDIDA 4: casar por `os.readlink` (o que o `quem_o_jogo_abre.py` faz)
    reprova aqui, porque os dois caminhos são textos diferentes.
    """
    no = tmp_path / "dev" / "input" / "event22"
    no.parent.mkdir(parents=True)
    no.write_text("", encoding="utf-8")
    outro_nome = tmp_path / "dev" / "input" / "event22-renumerado"
    os.link(no, outro_nome)
    assert no.stat().st_ino == outro_nome.stat().st_ino

    proc = tmp_path / "proc"
    _forjar_processo(proc, 4242, fds={"3": outro_nome})

    censo = INS.censo_de_posse([_alvo_do_arquivo(no)], raiz_proc=str(proc))

    assert [(p.pid, p.alvo.caminho) for p in censo.posses] == [(4242, str(no))]


def test_inode_igual_em_outro_sistema_de_arquivos_nao_casa(tmp_path: Path) -> None:
    """Número de inode só é único DENTRO de um sistema de arquivos.

    MORDIDA 5: casar só por `st_ino` faz este alvo — mesmo inode, `st_dev`
    diferente — ser dado como aberto, e o falso positivo sai convincente.
    """
    no = tmp_path / "event22"
    no.write_text("", encoding="utf-8")
    st = no.stat()
    alvo_de_outro_fs = INS.Alvo(
        classe="nosso",
        rotulo="P1",
        papel="gamepad",
        caminho="/dev/input/event22",
        chave=(st.st_dev + 1, st.st_ino),
        reguas="B (sysfs)",
    )
    proc = tmp_path / "proc"
    _forjar_processo(proc, 4242, fds={"3": no})

    censo = INS.censo_de_posse([alvo_de_outro_fs], raiz_proc=str(proc))

    assert censo.posses == []


def test_o_censo_nao_abre_o_no(tmp_path: Path) -> None:
    """`_chave` faz `os.stat`, e `os.stat` NÃO abre o arquivo.

    Não é preciosismo: abrir o `/dev/hidraw` do vpad dispara `UHID_OPEN` e
    arma o modo jogo, e fechá-lo por último deixa o controle vibrando, porque
    o `_silence_rumble()` não roda. Um instrumento que abrisse para medir
    estragaria a medição que está tentando fazer.

    MORDIDA 6: trocar `os.stat` por `open()` prende a thread para sempre num
    FIFO sem escritor — ela não termina, e o `assert` reprova. A thread é
    `daemon` de propósito: mesmo presa, ela não segura o fim do processo.
    """
    fifo = tmp_path / "cano"
    os.mkfifo(fifo)
    resultado: list[Any] = []

    def _medir() -> None:
        resultado.append(INS._chave(str(fifo)))

    trabalho = threading.Thread(target=_medir, daemon=True)
    trabalho.start()
    trabalho.join(timeout=5.0)

    assert not trabalho.is_alive(), (
        "`_chave` ficou presa num FIFO sem escritor: alguém trocou o `os.stat` "
        "por um `open()`, e este instrumento passou a ABRIR o que mede"
    )
    assert resultado and resultado[0] is not None


def test_o_mesmo_no_aberto_duas_vezes_conta_uma(tmp_path: Path) -> None:
    """`dup()` de um fd não é uma segunda posse."""
    no = tmp_path / "event22"
    no.write_text("", encoding="utf-8")
    proc = tmp_path / "proc"
    _forjar_processo(proc, 77, fds={"3": no, "9": no, "12": no})

    censo = INS.censo_de_posse([_alvo_do_arquivo(no)], raiz_proc=str(proc))

    assert len(censo.posses) == 1


def test_processo_que_nao_se_deixa_ler_entra_na_lista_de_cegos(
    tmp_path: Path,
) -> None:
    """`fd/` ilegível não vira "não achei nada": vira buraco declarado."""
    no = tmp_path / "event22"
    no.write_text("", encoding="utf-8")
    proc = tmp_path / "proc"
    dir_pid = _forjar_processo(proc, 99, fds={"3": no})
    (dir_pid / "fd").chmod(0o000)
    try:
        censo = INS.censo_de_posse([_alvo_do_arquivo(no)], raiz_proc=str(proc))
    finally:
        (dir_pid / "fd").chmod(0o700)

    assert censo.ilegiveis == {99}
    assert censo.posses == []
    assert censo.fechou_sobre([99]) is False
    assert censo.fechou_sobre([1234]) is True


# ---------------------------------------------------------------------------
# A âncora do jogo
# ---------------------------------------------------------------------------


def test_processo_que_so_menciona_exe_nao_entra_na_arvore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso REAL, medido em 20/08/2026 sem nenhum jogo aberto.

    `arvore_do_jogo(r"\\.exe|Shipping")` devolveu o `earlyoom` — a palavra
    `.exe` mora na lista de `--avoid` dele — e o binário de outro programa
    desta máquina, cujo nome termina em `.exe`. Sem a âncora, o instrumento
    afirmaria "a árvore do jogo existe e não segura nada" sobre um jogo que
    não estava aberto.

    MORDIDA 7: arrancar a peneira do `SteamAppId` faz os dois entrarem.
    """
    proc = tmp_path / "proc"
    _forjar_processo(proc, 1017, cmdline="/usr/bin/earlyoom --avoid jogo.exe")
    _forjar_processo(proc, 3087833, cmdline="/opt/coisa/ferramenta.exe")
    _forjar_processo(
        proc, 5000, cmdline="Z:\\jogo\\jogo.exe", environ="SteamAppId=2497900\0"
    )
    monkeypatch.setattr(INS, "arvore_do_jogo", lambda _p: [1017, 3087833, 5000])

    dentro, fora = INS.arvore_ancorada("qualquer", raiz_proc=str(proc))

    assert dentro == [5000]
    assert fora == [1017, 3087833]


def test_sem_ancora_o_falso_positivo_volta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A escape hatch existe e não esconde o que faz.

    Um jogo que não veio da Steam não carrega `SteamAppId`, e para ele
    `--sem-ancora` é a única saída. O preço é este: tudo o que casar pelo
    cmdline volta a entrar — e o relatório avisa em voz alta quando a bandeira
    está ligada.
    """
    proc = tmp_path / "proc"
    _forjar_processo(proc, 1017, cmdline="/usr/bin/earlyoom --avoid jogo.exe")
    monkeypatch.setattr(INS, "arvore_do_jogo", lambda _p: [1017])

    dentro, fora = INS.arvore_ancorada("x", ancora=False, raiz_proc=str(proc))

    assert dentro == [1017]
    assert fora == []


# ---------------------------------------------------------------------------
# A decisão: os cinco vereditos
# ---------------------------------------------------------------------------


def _alvo(classe: str, chave: tuple[int, int] = (1, 1)) -> Any:
    return INS.Alvo(
        classe=classe,
        rotulo="P1" if classe == "nosso" else UNIQ_FORJADO_DE_FISICO,
        papel="gamepad",
        caminho=f"/dev/input/{classe}",
        chave=chave,
        reguas="B (sysfs)",
    )


def _censo(posses: list[tuple[int, str]], ilegiveis: set[int] | None = None) -> Any:
    censo = INS.Censo(ilegiveis=set(ilegiveis or ()))
    censo.posses = [
        INS.Posse(pid=pid, cmdline="jogo.exe", alvo=_alvo(classe))
        for pid, classe in posses
    ]
    return censo


def test_sem_alvo_nao_ha_o_que_procurar() -> None:
    veredito, motivo = INS.decidir([], _censo([]), [5000], [])
    assert veredito == INS.V_NAO_SONDADO
    assert "nenhum nó NOSSO se resolveu" in motivo


def test_arvore_so_de_recusados_diz_nao_sondado() -> None:
    """Recusados pela âncora não são `NENHUM` — são a ausência de sujeito.

    MORDIDA 7 (outro lado): sem a âncora, `recusados` chega vazio e `arvore`
    chega com os dois falsos positivos; o veredito vira `NENHUM`, que é uma
    afirmação sobre um jogo que não está aberto.
    """
    veredito, motivo = INS.decidir([_alvo("nosso")], _censo([]), [], [1017, 3087833])
    assert veredito == INS.V_NAO_SONDADO
    assert "SteamAppId" in motivo


def test_sem_jogo_nenhum_o_veredito_e_nao_sondado() -> None:
    veredito, motivo = INS.decidir([_alvo("nosso")], _censo([]), [], [])
    assert veredito == INS.V_NAO_SONDADO
    assert "não há árvore" in motivo


def test_nenhum_exige_o_censo_da_arvore_fechado() -> None:
    """`NENHUM` é afirmação positiva, e só sai com o censo da árvore fechado.

    MORDIDA 8: fazer `fechou_sobre` devolver `True` sempre faz o primeiro caso
    virar `NENHUM` — o instrumento afirmando sobre um processo cujo `fd/` ele
    não conseguiu ler.
    """
    cego = INS.decidir([_alvo("nosso")], _censo([], ilegiveis={5000}), [5000], [])
    assert cego[0] == INS.V_NAO_SONDADO
    assert "ÁRVORE DO JOGO" in cego[1]

    limpo = INS.decidir([_alvo("nosso")], _censo([]), [5000], [])
    assert limpo[0] == INS.V_NENHUM


def test_ilegivel_fora_da_arvore_nao_impede_o_nenhum() -> None:
    """A nona mordida, invertida: exigir o censo do MUNDO nunca fecharia.

    `(sd-pam)` e `ssh-agent` zeram o `PR_SET_DUMPABLE` e não se deixam ler em
    máquina nenhuma. Se `NENHUM` dependesse deles, ele jamais sairia — e um
    veredito que nunca sai é pior que não existir, porque parece prudência.
    """
    veredito, _motivo = INS.decidir(
        [_alvo("nosso")], _censo([], ilegiveis={1480, 3692}), [5000], []
    )
    assert veredito == INS.V_NENHUM


def test_achar_vale_mesmo_com_o_censo_aberto() -> None:
    """Achar é observação positiva; não achar, com processo cego, não é.

    MORDIDA: conferir o censo ANTES dos ramos de "achou" transforma uma posse
    observada em `NÃO SONDADO`, e o instrumento passa a esconder o que viu.
    """
    veredito, _motivo = INS.decidir(
        [_alvo("nosso")],
        _censo([(5000, "nosso")], ilegiveis={5001}),
        [5000, 5001],
        [],
    )
    assert veredito == INS.V_NOSSO


def test_segura_o_fisico_e_segura_os_dois_sao_vereditos_diferentes() -> None:
    """Os dois casos que o `quem_o_jogo_abre.py` não separava.

    `SEGURA O FÍSICO` quer dizer que o jogo passou por fora do produto;
    `SEGURA OS DOIS` é o sintoma do controle em dobro, que tem outra cura.
    """
    so_fisico = INS.decidir(
        [_alvo("nosso"), _alvo("físico", (1, 2))],
        _censo([(5000, "físico")]),
        [5000],
        [],
    )
    assert so_fisico[0] == INS.V_FISICO

    os_dois = INS.decidir(
        [_alvo("nosso"), _alvo("físico", (1, 2))],
        _censo([(5000, "nosso"), (5000, "físico")]),
        [5000],
        [],
    )
    assert os_dois[0] == INS.V_DOIS


def test_posse_de_quem_nao_e_o_jogo_nao_fecha_o_degrau() -> None:
    """O veto da NUMA-02, em forma de teste.

    O cliente Steam abre o nó do vpad, e sessão aberta NÃO é evidência de
    jogo — foi o mecanismo do incidente das 14:42. Uma posse fora da árvore do
    jogo aparece na tabela e não muda o veredito.
    """
    veredito, _motivo = INS.decidir(
        [_alvo("nosso")], _censo([(2113, "nosso")]), [5000], []
    )
    assert veredito == INS.V_NENHUM


# ---------------------------------------------------------------------------
# As duas cópias do carimbo
# ---------------------------------------------------------------------------


def test_a_copia_do_carimbo_em_scripts_e_a_do_produto_sao_a_mesma_palavra() -> None:
    """`src/` não pode importar de `scripts/`, então a palavra está escrita em
    dois lugares. Duas cópias da mesma régua é como uma delas envelhece
    calada; este teste é o alarme, e o instrumento imprime o mesmo aviso em
    tempo de execução.
    """
    assert INS.VPAD_HID_PHYS == INS.PHYS_DO_PRODUTO


def test_os_cinco_vereditos_sao_cinco_e_distintos() -> None:
    """Um veredito que colidisse com outro apagaria a diferença entre `o jogo
    não abriu nada` e `eu não consegui olhar` — que é a distinção inteira."""
    vereditos = {
        INS.V_NOSSO,
        INS.V_FISICO,
        INS.V_DOIS,
        INS.V_NENHUM,
        INS.V_NAO_SONDADO,
    }
    assert len(vereditos) == 5
