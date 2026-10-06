"""QUEM-SEGURA-O-NOSSO-NÓ-03 — a régua do log do Proton, e onde ela mente.

O instrumento sob ensaio é `scripts/ensaios/o_jogo_no_log_do_proton.py`, a
SEGUNDA régua do degrau `O JOGO RECEBEU`. A primeira é a do inode
(`o_jogo_segura_o_nosso_no.py`); esta lê o que o próprio Wine escreveu sobre si
mesmo enquanto rodava dentro do contêiner.

Duas réguas existem porque **portão em série engana** (19/08/2026): consertar um
deixa o sintoma idêntico, e uma régua que olha para o lugar errado jura com a
mesma cara de quem olha para o certo.

AS MORDIDAS, uma por teste, ditas na docstring de cada um. As três que mais
importam:

1. `NENHUM` é AFIRMAÇÃO POSITIVA — "o censo fechou e não havia nada". Um log
   que não pôde responder tem de sair `NÃO SONDADO`, nunca `NENHUM`;
2. **um `uniq` nosso que atravessa a fronteira do Wine sem o lado unix ter
   publicado o carimbo é DISCORDÂNCIA**, não confirmação. Sem essa conferência
   um log truncado no começo vira `RECEBEU DO NOSSO NÓ`;
3. **vid/pid não é identidade.** O vpad forja `054c:0df2` (DualSense Edge) de
   propósito, e o Edge existe de verdade. Casar por vid/pid transformaria um
   Edge dela no nosso vpad.

ENDEREÇOS: nada de MAC real aqui. Os físicos usam a faixa forjada da casa
(`aa:bb:cc:`), que os portões de anonimato reconhecem como sintética; os vpads
usam `02:fe:`, que é o que o próprio produto carimba (`uhid_gamepad.player_mac`)
e não colide com endereço de fábrica por definição.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "o_jogo_no_log_do_proton.py"

_CHAMADAS_QUE_ESCREVEM = frozenset(
    {
        "write_text",
        "write_bytes",
        "writelines",
        "mkdir",
        "makedirs",
        "touch",
        "unlink",
        "chmod",
    }
)


def _carregar_o_instrumento() -> Any:
    """Carrega pelo caminho: `scripts/ensaios/` não é pacote."""
    pasta = str(_INSTRUMENTO.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    especificacao = importlib.util.spec_from_file_location(
        "o_jogo_no_log_do_proton_sob_ensaio", _INSTRUMENTO
    )
    if especificacao is None or especificacao.loader is None:
        raise AssertionError(f"não consegui carregar {_INSTRUMENTO}")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


LOG = _carregar_o_instrumento()

MAC_DO_FISICO = "aa:bb:cc:dd:ee:07"
MAC_DO_FISICO_MASCARADO = "aa:bb:cc:00:00:07"

UNIQ_P1 = "02:fe:00:00:00:01"
UNIQ_P2 = "02:fe:00:00:00:02"

WINEDEBUG_BOM = "+hid,+xinput,+plugplay"


def _cabecalho(*, appid: str = "123456", winedebug: str = WINEDEBUG_BOM) -> list[str]:
    return [
        "======================",
        "Proton: 1774238111 GE-Proton10-34",
        f"SteamGameId: {appid}",
        "Command: ['/jogo/Jogo.exe']",
        f"System WINEDEBUG: {winedebug}",
        f"Effective WINEDEBUG: {winedebug}",
        "======================",
    ]


def _enumeracao() -> list[str]:
    return [
        "00b4:trace:hid:udev_bus_init args 0x6fffff238340",
        "00b4:trace:hid:build_initial_deviceset_direct Initial enumeration of /dev/hidraw*",
    ]


def _bloco(
    no: str,
    *,
    hid_phys: str,
    hid_uniq: str,
    hid_id: str,
    destino: str,
) -> list[str]:
    """Um nó considerado pelo winebus, com o `uevent` que o kernel publicou."""
    syspath = f"/sys/devices/virtual/misc/uhid/0003:054C:0DF2.000D/{Path(no).name}"
    linhas = [f'00b4:trace:hid:udev_add_device udev "{no}" syspath {syspath}']
    for chave, valor in (
        ("DRIVER", "playstation"),
        ("HID_ID", hid_id),
        ("HID_NAME", "DualSense Wireless Controller"),
        ("HID_PHYS", hid_phys),
        ("HID_UNIQ", hid_uniq),
    ):
        linhas.append(
            f'00b4:trace:hid:get_device_subsystem_info hid uevent "{chave}={valor}"'
        )
    if destino == "hidraw":
        linhas.append(
            f'00b4:trace:hid:hidraw_device_create dev 0x77e518009cd0, node "{no}", '
            "desc {vid 054c, pid 0df2, version 0000, input -1, uid 00000000, "
            "is_gamepad 0, is_hidraw 1, bus_type 1}."
        )
    else:
        linhas.append(f'00b4:trace:hid:udev_add_device evdev "{no}": {destino}')
    return linhas


IGNORADO = (
    "ignoring {vid 054c, pid 0ce6, version 0100, input 3, uid 00000000, "
    "is_gamepad 0, is_hidraw 0, bus_type 1}, in SDL ignore list"
)
ADIADO = (
    "deferring {vid 054c, pid 0df2, version 8100, input -1, uid 00000000, "
    "is_gamepad 0, is_hidraw 0, bus_type 1} to a different backend"
)


def _pdo(handle: str, *, vidpid: str = "VID_054C&PID_0DF2", uniq: str) -> list[str]:
    """O device do lado Windows. O `\\\\` é literal no log — não é escape meu."""
    return [
        f"00b4:trace:hid:bus_create_hid_device created device {handle}/0x77e51800ade0",
        f"00b4:trace:hid:driver_add_device Adding device to PDO {handle}, "
        rf'id L"USB\\{vidpid}"\L"0&{uniq}&0&0&0".',
    ]


def _reports(handle: str, quantos: int, *, thread: str = "00b4") -> list[str]:
    linhas: list[str] = []
    for _ in range(quantos):
        linhas.append(
            f"00b4:trace:hid:process_hid_report device {handle} "
            "report_buf 0000000000C2CEF2 (0x1), report_len 0x40"
        )
        linhas.append(
            f"{thread}:trace:hid:deliver_next_report device {handle}/0x77e51800ade0 "
            "input report length 64:"
        )
        linhas.append(
            f"{thread}:trace:hid:deliver_next_report 00000000  "
            "01 80 81 80 7f 00 00 ff 08 00 00 00 00 00 00 00"
        )
    return linhas


def _escrever(tmp_path: Path, linhas: list[str], nome: str = "steam-123456.log") -> str:
    alvo = tmp_path / nome
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return str(alvo)


def _log_completo_e_saudavel(tmp_path: Path) -> str:
    """A mesa que o log real de 18/08 mostrou: o vpad adotado, o físico ignorado."""
    linhas = _cabecalho() + _enumeracao()
    linhas += _bloco(
        "/dev/hidraw5",
        hid_phys="hefesto-vpad",
        hid_uniq=UNIQ_P1,
        hid_id="0003:0000054C:00000DF2",
        destino="hidraw",
    )
    linhas += _bloco(
        "/dev/input/event30",
        hid_phys="hefesto-vpad",
        hid_uniq=UNIQ_P1,
        hid_id="0003:0000054C:00000DF2",
        destino=ADIADO,
    )
    linhas += _bloco(
        "/dev/input/event24",
        hid_phys="usb-0000:0c:00.3-3/input3",
        hid_uniq=MAC_DO_FISICO,
        hid_id="0003:0000054C:00000CE6",
        destino=IGNORADO,
    )
    linhas += _pdo("0000000000C51210", uniq=UNIQ_P1)
    linhas += _reports("0000000000C51210", 3)
    linhas.append(
        "00b4:trace:hid:deliver_next_report device 0000000000C51210/0x77e51800ade0 "
        "input report length 64:"
    )
    linhas.append(
        "00bc:trace:hid:deliver_next_report device 0000000000C51210/0x77e51800ade0 "
        "input report length 64:"
    )
    return _escrever(tmp_path, linhas)


def test_o_log_saudavel_diz_que_o_nosso_no_atravessou(tmp_path: Path) -> None:
    """As duas rotas concordam, os reports atravessaram: `RECEBEU DO NOSSO NÓ`."""
    log = LOG.ler_log(_log_completo_e_saudavel(tmp_path))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_RECEBEU
    assert razoes
    assert [no.no for no in LOG.nossos_nos(log)] == ["/dev/hidraw5", "/dev/input/event30"]
    nossos = LOG.nossos_devices(log)
    assert len(nossos) == 1
    assert nossos[0].uniq == UNIQ_P1
    assert nossos[0].processou == 3
    assert nossos[0].entregou == 5
    assert nossos[0].threads == {"00b4", "00bc"}
    # E o primeiro report, com o id 0x01 do DualSense no primeiro byte.
    assert nossos[0].primeiro_report[0].startswith("01 80 81 80")


def test_o_fisico_ignorado_pela_sdl_aparece_e_nao_e_nosso(tmp_path: Path) -> None:
    """O DualSense FÍSICO cai na SDL ignore list, e o instrumento não o adota.

    MORDIDA: fazer `e_nosso` aceitar `DRIVER=playstation` (que o físico também
    traz) reprova aqui — o físico viraria "nosso".
    """
    log = LOG.ler_log(_log_completo_e_saudavel(tmp_path))
    fisico = next(no for no in log.nos if no.no == "/dev/input/event24")

    assert fisico.e_nosso is False
    assert fisico.destino_curto == "ignorado (SDL ignore list)"
    assert fisico.vidpid == "054c:0ce6"


def test_log_sem_o_canal_de_hid_nao_sonda_e_diz_por_que(tmp_path: Path) -> None:
    """Sem `+hid` no WINEDEBUG o log não pode responder — e tem de dizer isso."""
    caminho = _escrever(tmp_path, _cabecalho(winedebug="+xinput,+plugplay"))
    log = LOG.ler_log(caminho)
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NAO_SONDADO
    assert any("WINEDEBUG" in razao for razao in razoes), razoes
    assert log.canal_hid_ligado is False


def test_log_com_o_canal_ligado_mas_sem_censo_nao_diz_nenhum(tmp_path: Path) -> None:
    """Canal ligado, winebus nunca varreu: `NÃO SONDADO`, jamais `NENHUM`."""
    linhas = [
        *_cabecalho(),
        "009c:trace:hid:DriverEntry (0000000000C133E0, L\"...winebus\")",
    ]
    log = LOG.ler_log(_escrever(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NAO_SONDADO
    assert decisao != LOG.V_NENHUM
    assert any("enumeração" in razao for razao in razoes), razoes


def test_log_que_nao_existe_nao_sonda(tmp_path: Path) -> None:
    """Arquivo ausente é `NÃO SONDADO` com o erro do sistema junto."""
    log = LOG.ler_log(str(tmp_path / "nao-existe.log"))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NAO_SONDADO
    assert log.existe is False
    assert any("não consegui ler" in razao for razao in razoes), razoes


def test_nenhum_so_sai_quando_o_censo_fechou(tmp_path: Path) -> None:
    """O caso em que `NENHUM` É a resposta certa — o censo rodou e nada entregou."""
    linhas = _cabecalho() + _enumeracao()
    linhas += _bloco(
        "/dev/input/event3",
        hid_phys="usb-0000:02:00.0-3/input1",
        hid_uniq="",
        hid_id="0003:00003554:0000FA09",
        destino=ADIADO,
    )
    log = LOG.ler_log(_escrever(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NENHUM
    assert any("censo fechou" in razao for razao in razoes), razoes


def test_uniq_que_atravessa_sem_carimbo_e_discordancia(tmp_path: Path) -> None:
    """Rota B tem o nosso `uniq`, rota A nunca publicou o carimbo: `NÃO SONDADO`."""
    linhas = _cabecalho() + _enumeracao()
    linhas += _pdo("0000000000C51210", uniq=UNIQ_P1)
    linhas += _reports("0000000000C51210", 900)
    log = LOG.ler_log(_escrever(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NAO_SONDADO
    assert any("discordam" in razao for razao in razoes), razoes
    assert log.devices["0000000000C51210"].processou == 900


def test_carimbo_sem_o_lado_windows_e_nao_sondado(tmp_path: Path) -> None:
    """O contrário: rota A viu o carimbo e o log acaba antes da resposta."""
    linhas = _cabecalho() + _enumeracao()
    linhas += _bloco(
        "/dev/hidraw5",
        hid_phys="hefesto-vpad",
        hid_uniq=UNIQ_P1,
        hid_id="0003:0000054C:00000DF2",
        destino="hidraw",
    )
    log = LOG.ler_log(_escrever(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NAO_SONDADO
    assert any("acaba antes" in razao for razao in razoes), razoes


def test_enumerou_e_nao_leu_e_so_enumerou(tmp_path: Path) -> None:
    """As duas rotas concordam e ZERO report atravessou: `VIU O NOSSO NÓ, NÃO RECEBEU`."""
    linhas = _cabecalho() + _enumeracao()
    linhas += _bloco(
        "/dev/hidraw5",
        hid_phys="hefesto-vpad",
        hid_uniq=UNIQ_P1,
        hid_id="0003:0000054C:00000DF2",
        destino="hidraw",
    )
    linhas += _pdo("0000000000C51210", uniq=UNIQ_P1)
    log = LOG.ler_log(_escrever(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_SO_VIU
    assert any("NENHUM report atravessou" in razao for razao in razoes), razoes


def test_um_dualsense_edge_de_verdade_nao_e_o_nosso_vpad(tmp_path: Path) -> None:
    """`054c:0df2` com carimbo de aparelho REAL não é nosso.

    O vpad forja o PID do DualSense Edge de propósito, e o Edge existe de
    verdade — este é o mesmo buraco que a VPAD-NO-ESPELHO-01 fechou em
    12/08/2026, agora do lado do log.

    MORDIDA, e as duas metades foram medidas separadamente porque o resultado
    de cada uma é diferente:

    - troque só `NoDoLog.e_nosso` por `self.vidpid == "054c:0df2"` e o
      veredicto cai de `RECEBEU DE OUTRO NÓ, NÃO DO NOSSO` para `VIU O NOSSO
      NÓ, NÃO RECEBEU` — o instrumento já para de dizer que o aparelho é de
      outro;
    - troque TAMBÉM `DeviceDoWine.e_nosso` para casar pelo `devid` do PDO
      (`VID_054C&PID_0DF2`) e o veredicto vira `RECEBEU DO NOSSO NÓ`, com os 500
      reports do controle do usuário contados como nossos.

    Arrancadas as duas, vistas reprovar as duas, devolvidas.
    """
    linhas = _cabecalho() + _enumeracao()
    linhas += _bloco(
        "/dev/hidraw6",
        hid_phys="usb-0000:0c:00.3-4/input0",
        hid_uniq=MAC_DO_FISICO,
        hid_id="0003:0000054C:00000DF2",
        destino="hidraw",
    )
    linhas += _pdo("0000000000C99999", uniq=MAC_DO_FISICO)
    linhas += _reports("0000000000C99999", 500)
    log = LOG.ler_log(_escrever(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_OUTRO
    assert LOG.nossos_nos(log) == []
    assert LOG.nossos_devices(log) == []
    assert log.nos[0].vidpid == "054c:0df2"
    assert any("outro(s)" in razao for razao in razoes), razoes


def test_dois_vpads_nao_se_confundem(tmp_path: Path) -> None:
    """P1 e P2 têm vid/pid, nome e desc IDÊNTICOS. Só o `uniq` os separa."""
    linhas = _cabecalho() + _enumeracao()
    for no, uniq in (("/dev/hidraw5", UNIQ_P1), ("/dev/hidraw6", UNIQ_P2)):
        linhas += _bloco(
            no,
            hid_phys="hefesto-vpad",
            hid_uniq=uniq,
            hid_id="0003:0000054C:00000DF2",
            destino="hidraw",
        )
    linhas += _pdo("0000000000C51210", uniq=UNIQ_P1)
    linhas += _pdo("0000000000C52220", uniq=UNIQ_P2)
    linhas += _reports("0000000000C52220", 700)
    log = LOG.ler_log(_escrever(tmp_path, linhas))
    decisao, _ = LOG.veredicto(log)

    assert decisao == LOG.V_RECEBEU
    por_uniq = {dev.uniq: dev for dev in LOG.nossos_devices(log)}
    assert set(por_uniq) == {UNIQ_P1, UNIQ_P2}
    assert por_uniq[UNIQ_P1].processou == 0
    assert por_uniq[UNIQ_P2].processou == 700


def test_regua_velha_recusa_medir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Se o produto trocar o carimbo, o instrumento fica cego BARULHENTO."""
    monkeypatch.setattr(LOG, "_CARIMBO_DO_PRODUTO", "hefesto-vpad-v2")
    log = LOG.ler_log(_log_completo_e_saudavel(tmp_path))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NAO_SONDADO
    assert any("a régua está velha" in razao for razao in razoes), razoes


def test_o_carimbo_procurado_e_o_que_o_produto_escreve() -> None:
    """Hoje, nesta árvore, as duas metades da régua dizem a mesma palavra."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import VPAD_HID_PHYS

    assert LOG.VPAD_HID_PHYS == VPAD_HID_PHYS == "hefesto-vpad"
    assert LOG._CARIMBO_DO_PRODUTO == VPAD_HID_PHYS


def test_o_mac_do_fisico_sai_mascarado_na_tela(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O log do Proton traz o `HID_UNIQ` dos controles FÍSICOS — MAC de fábrica."""
    log = LOG.ler_log(_log_completo_e_saudavel(tmp_path))
    decisao, razoes = LOG.veredicto(log)
    LOG.imprimir(log, decisao, razoes)
    saida = capsys.readouterr().out

    assert MAC_DO_FISICO not in saida
    assert MAC_DO_FISICO_MASCARADO in saida
    assert UNIQ_P1 in saida


def test_a_mascara_preserva_o_uniq_do_vpad() -> None:
    """A máscara zera os octetos 4 e 5, e o `02:fe:` já os tem zerados."""
    assert LOG.mascarar(MAC_DO_FISICO) == MAC_DO_FISICO_MASCARADO
    assert LOG.mascarar(UNIQ_P1) == UNIQ_P1
    assert LOG.mascarar(UNIQ_P2) == UNIQ_P2
    assert LOG.mascarar(UNIQ_P1) != LOG.mascarar(UNIQ_P2)


def test_todo_caminho_devolve_um_dos_cinco_vereditos(tmp_path: Path) -> None:
    """Cinco vereditos, e nenhum sexto escapa por uma borda."""
    casos = [
        _log_completo_e_saudavel(tmp_path),
        str(tmp_path / "ausente.log"),
        _escrever(tmp_path, _cabecalho(winedebug="+xinput"), "sem-hid.log"),
        _escrever(tmp_path, _cabecalho() + _enumeracao(), "vazio.log"),
    ]
    for caminho in casos:
        decisao, razoes = LOG.veredicto(LOG.ler_log(caminho))
        assert decisao in LOG.VEREDICTOS, (caminho, decisao)
        assert razoes, caminho

    assert len(LOG.VEREDICTOS) == 5
    assert len(set(LOG.VEREDICTOS)) == 5


def test_o_instrumento_nao_escreve_em_lugar_nenhum() -> None:
    """Ele não grava arquivo. Nem no caderno, nem em `/dev`, nem em cache."""
    arvore = ast.parse(_INSTRUMENTO.read_text(encoding="utf-8"))

    importados: set[str] = set()
    escritas: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
        elif isinstance(no, ast.Call):
            alvo = no.func
            nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")
            if nome in _CHAMADAS_QUE_ESCREVEM:
                escritas.append(f"{nome} (linha {no.lineno})")
            if nome == "open":
                modos = [
                    a.value
                    for a in [*no.args[1:], *(k.value for k in no.keywords if k.arg == "mode")]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)
                ]
                if any(set(m) & set("wxa+") for m in modos):
                    escritas.append(f"open em modo de escrita (linha {no.lineno})")

    assert escritas == [], escritas
    assert "csv" not in importados
    assert "shutil" not in importados
    assert "subprocess" not in importados


def test_o_json_declara_o_degrau_que_mediu(tmp_path: Path) -> None:
    """A saída de máquina carrega `degrau`, como o caderno passou a exigir."""
    log = LOG.ler_log(_log_completo_e_saudavel(tmp_path))
    decisao, razoes = LOG.veredicto(log)
    payload = LOG._para_json(log, decisao, razoes)

    assert payload["degrau"] == "O JOGO RECEBEU"
    assert payload["veredicto"] == LOG.V_RECEBEU
    assert payload["reports_nossos"] == 3
    assert MAC_DO_FISICO not in str(payload)
