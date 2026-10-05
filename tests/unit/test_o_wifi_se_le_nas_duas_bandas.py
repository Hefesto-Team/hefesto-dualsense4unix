# ruff: noqa: RUF001
"""O Wi-Fi se lê nas duas bandas — O-WIFI-SE-LE-NAS-DUAS-BANDAS-01 (04/10/2026).

Tudo com fixture: sysfs de mentira, NetworkManager de mentira, diário de mentira. Nada aqui
abre rede, módulo, evdev nem barramento de verdade.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import faixa_do_wifi as fw
from hefesto_dualsense4unix.integrations import faixas_do_ar as fa
from hefesto_dualsense4unix.integrations import queda_do_wifi as qw
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    ESPECIE_DESCONHECIDA,
    GRAU_LIDO,
    ler_o_barramento,
)
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.unit.test_a_faixa_do_wifi_se_le_do_networkmanager import (
    NetworkManagerDeMentira,
    _rede,
)
from tests.unit.test_o_censo_le_o_barramento_inteiro import (
    RAIZ_USB,
    USB4,
    Bancada,
)

INTERFACE_USB = "wlxaabbcc000102"
NO_DA_PLACA = f"{USB4}/4-1"
INTERFACE_DA_PLACA = f"{NO_DA_PLACA}/4-1:1.0"


# ---------- o censo lê o que o kernel ligou ------------------------------------------------


def _censo_com(filhos: dict[str, list[str]], conteudo: dict[str, str] | None = None) -> Any:
    banca = Bancada(listar=lambda raiz: (
        Bancada().listagem if raiz == RAIZ_USB else list(filhos.get(raiz, ()))))
    banca.conteudo.update(conteudo or {})
    achados = {a.nome_do_kernel: a for a in ler_o_barramento(**banca.fontes()).aparelhos}
    return achados["4-1"]


def test_a_placa_ff_com_ieee80211_pendurado_e_wifi_de_qualquer_chip() -> None:
    placa = _censo_com({INTERFACE_DA_PLACA: ["ieee80211", "net"],
                        f"{INTERFACE_DA_PLACA}/net": ["wlan0"]})
    assert placa.classe == "ff"
    assert (placa.especie, placa.grau, placa.ligado_como) == ("Wi-Fi", GRAU_LIDO, "wifi")
    assert placa.origem_da_classe == "o que o kernel ligou"


def test_a_interface_com_wireless_na_rede_tambem_e_wifi() -> None:
    placa = _censo_com({INTERFACE_DA_PLACA: ["net"], f"{INTERFACE_DA_PLACA}/net": ["wlan0"],
                        f"{INTERFACE_DA_PLACA}/net/wlan0": ["wireless"]})
    assert placa.ligado_como == "wifi"


def test_rede_sem_fio_nenhum_e_rede_e_o_resto_continua_nao_identificado() -> None:
    cabo = _censo_com({INTERFACE_DA_PLACA: ["net"], f"{INTERFACE_DA_PLACA}/net": ["eth1"],
                       f"{INTERFACE_DA_PLACA}/net/eth1": ["statistics"]})
    assert (cabo.especie, cabo.ligado_como) == ("Rede", "rede")
    mudo = _censo_com({})
    assert (mudo.especie, mudo.ligado_como) == (ESPECIE_DESCONHECIDA, "")


def test_o_controle_se_conhece_pelo_botao_sul_do_input() -> None:
    entrada = f"{INTERFACE_DA_PLACA}/input"
    caps = f"{entrada}/input9/capabilities/key"
    com = _censo_com({INTERFACE_DA_PLACA: ["input"], entrada: ["input9"]},
                     {caps: "1 0 0 0 0 0 0 0 0 0\n"})
    # BTN_SOUTH = 0x130 = bit 304 = palavra 4 (de 64 bits), bit 48
    assert com.ligado_como == ""
    com = _censo_com({INTERFACE_DA_PLACA: ["input"], entrada: ["input9"]},
                     {caps: f"{1 << 48:x} 0 0 0 0\n"})
    assert (com.especie, com.ligado_como) == ("Controle", "controle")


def test_a_classe_que_o_descritor_diz_vence_o_kernel_quando_ela_diz_algo() -> None:
    """Um mouse (classe 03) cuja interface pendura `net` continua Mouse: a classe vale."""
    mouse = "/mentira/devices/pci0000:00/0000:aa:00.0/usb1/1-3/1-3:1.0"
    banca = Bancada(listar=lambda raiz: (
        Bancada().listagem if raiz == RAIZ_USB else ["net"] if raiz == mouse else []))
    achados = {a.nome_do_kernel: a for a in ler_o_barramento(**banca.fontes()).aparelhos}
    assert achados["1-3"].especie == "Mouse"


def _leitura_do_censo(filhos: dict[str, list[str]]) -> Any:
    from hefesto_dualsense4unix.integrations import ordens_da_mesa as om

    banca = Bancada(listar=lambda raiz: (
        Bancada().listagem if raiz == RAIZ_USB else list(filhos.get(raiz, ()))))
    return om.Leitura(censo=ler_o_barramento(**banca.fontes()),
                      ocupante_da_entrada={"1": "4-1"})


def test_o_wifi_lido_pelo_kernel_conta_como_irradiando_na_ordem_da_mesa() -> None:
    from hefesto_dualsense4unix.integrations import ordens_da_mesa as om

    assert om._irradia(_leitura_do_censo({INTERFACE_DA_PLACA: ["ieee80211"]}), "1") is True
    assert om._irradia(_leitura_do_censo({}), "1") is False


# ---------- o NetworkManager: duas bandas, a mesma placa -----------------------------------


def _sys_com_usb(raiz: Path, vid: str = "2357", pid: str = "012d",
                 interface: str = INTERFACE_USB, porta: str = "4-1.2") -> tuple[str, str]:
    no = raiz / f"usb{porta[0]}" / porta.split(".")[0] / porta
    (no / f"{porta}:1.0").mkdir(parents=True)
    (no / "idVendor").write_text(vid + "\n")
    (no / "idProduct").write_text(pid + "\n")
    rede = raiz / "net"
    (rede / interface).mkdir(parents=True)
    (rede / interface / "device").symlink_to(no / f"{porta}:1.0")
    return str(rede), str(no.resolve())


@pytest.mark.parametrize(("mhz", "largura", "como"), [(5805, 80, fw.FORA), (2462, 20, fw.PROVAVEL)])
def test_as_duas_bandas_se_leem_e_a_chave_e_o_vid_pid(
    tmp_path: Path, mhz: int, largura: int, como: str
) -> None:
    raiz_net, no = _sys_com_usb(tmp_path)
    r = _rede(INTERFACE_USB, mhz, largura)
    nm = NetworkManagerDeMentira({"/dev/0": r["dispositivo"], "/ponto": r["ponto"]})
    redes = fw.ler_as_redes(nm, raiz_net=raiz_net, memoria={})
    assert redes and (redes[0].no, redes[0].chave) == (no, "usb:2357:012d")
    assert fw.faixa_no_bluetooth(redes[0]).como == como


def test_a_chave_nunca_leva_o_nome_da_interface(tmp_path: Path) -> None:
    raiz_net, _ = _sys_com_usb(tmp_path)
    for vid in ("2357", ""):
        (Path(raiz_net).parent / "usb4" / "4-1" / "4-1.2" / "idVendor").write_text(vid)
        r = _rede(INTERFACE_USB, 2437, 20)
        nm = NetworkManagerDeMentira({"/dev/0": r["dispositivo"], "/ponto": r["ponto"]})
        redes = fw.ler_as_redes(nm, raiz_net=raiz_net, memoria={})
        assert redes
        assert "wlx" not in repr(redes) and "aabbcc" not in repr(redes).lower()


class Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_ponto_ativo_vira_barra_por_dois_segundos_a_linha_nao_some(tmp_path: Path) -> None:
    raiz_net, _ = _sys_com_usb(tmp_path)
    r = _rede(INTERFACE_USB, 5805, 80)
    nm = NetworkManagerDeMentira({"/dev/0": r["dispositivo"], "/ponto": r["ponto"]})
    memoria: dict[str, Any] = {}
    relogio = Relogio()
    bom = fw.ler_as_redes(nm, raiz_net=raiz_net, memoria=memoria, agora=relogio)
    assert bom
    r["dispositivo"][fw.INTERFACE_SEM_FIO]["ActiveAccessPoint"] = fw.SEM_PONTO_ATIVO
    relogio.t += 2.0
    assert fw.ler_as_redes(nm, raiz_net=raiz_net, memoria=memoria, agora=relogio) == bom
    relogio.t += fw.SEGURA_O_ULTIMO_VALOR_S
    assert fw.ler_as_redes(nm, raiz_net=raiz_net, memoria=memoria, agora=relogio) is None


def test_a_placa_que_some_do_networkmanager_e_volta_em_outro_no_e_a_mesma(
    tmp_path: Path,
) -> None:
    raiz_net, no_velho = _sys_com_usb(tmp_path / "a")
    r = _rede(INTERFACE_USB, 2462, 20)
    nm = NetworkManagerDeMentira({"/dev/0": r["dispositivo"], "/ponto": r["ponto"]})
    memoria: dict[str, Any] = {}
    relogio = Relogio()
    antes = fw.ler_as_redes(nm, raiz_net=raiz_net, memoria=memoria, agora=relogio)
    # a placa cai: o NM não lista nada
    vazio = NetworkManagerDeMentira({"/outro": {}})
    relogio.t += 3.0
    segurada = fw.ler_as_redes(vazio, raiz_net=raiz_net, memoria=memoria, agora=relogio)
    assert segurada == antes
    # volta no outro barramento, com outro nome, sem ponto ativo ainda
    raiz_net2, no_novo = _sys_com_usb(tmp_path / "b", interface="wlan0", porta="3-1.2")
    r2 = _rede("wlan0", 2462, 20)
    r2["dispositivo"][fw.INTERFACE_SEM_FIO]["ActiveAccessPoint"] = fw.SEM_PONTO_ATIVO
    nm2 = NetworkManagerDeMentira({"/dev/9": r2["dispositivo"]})
    relogio.t += 2.0
    volta = fw.ler_as_redes(nm2, raiz_net=raiz_net2, memoria=memoria, agora=relogio)
    assert volta and len(volta) == 1
    assert volta[0].chave == "usb:2357:012d"
    assert volta[0].no == no_novo != no_velho
    assert volta[0].frequencia_mhz == 2462


def test_um_dubl_injetado_nunca_herda_a_rede_de_outro(tmp_path: Path) -> None:
    raiz_net, _ = _sys_com_usb(tmp_path)
    r = _rede(INTERFACE_USB, 2437, 20)
    nm = NetworkManagerDeMentira({"/dev/0": r["dispositivo"], "/ponto": r["ponto"]})
    assert fw.ler_as_redes(nm, raiz_net=raiz_net)
    assert fw.ler_as_redes(NetworkManagerDeMentira({}), raiz_net=raiz_net) is None


# ---------- as quedas: o diário do kernel ---------------------------------------------------


def _diario(*eventos: tuple[float, str, str, str]) -> str:
    """`(t, 'sumiu'|'nasceu', nó, vid:pid)` no formato do journalctl short-monotonic."""
    linhas = []
    for t, o_que, no, vidpid in eventos:
        vid, _, pid = vidpid.partition(":")
        texto = (f"usb {no}: USB disconnect, device number 5" if o_que == "sumiu" else
                 f"usb {no}: New USB device found, idVendor={vid}, idProduct={pid}, "
                 "bcdDevice= 3.00")
        linhas.append(f"[{t:12.6f}] Maquina kernel: {texto}")
    return "\n".join(linhas) + "\n"


PLACA = "2357:012d"


def test_disconnect_seguido_da_volta_do_mesmo_vid_pid_e_uma_queda() -> None:
    texto = _diario((10.0, "nasceu", "4-1.2", PLACA), (100.0, "sumiu", "4-1.2", PLACA),
                    (100.5, "nasceu", "3-1.2", PLACA), (300.0, "sumiu", "3-1.2", PLACA),
                    (301.0, "nasceu", "4-1.2", PLACA))
    quedas = qw.quedas_do_diario(texto, agora_s=1540.0)
    assert quedas["usb:2357:012d"] == qw.Quedas(n=2, minutos=24)
    assert qw.em_palavras(quedas["usb:2357:012d"]) == "caiu 2× em 24 min"


def test_tirar_da_porta_e_nunca_voltar_nao_e_queda() -> None:
    texto = _diario((10.0, "nasceu", "4-1.2", PLACA), (100.0, "sumiu", "4-1.2", PLACA))
    assert qw.quedas_do_diario(texto, 200.0) == {}
    texto += _diario((200.0, "nasceu", "4-1.2", PLACA))
    assert qw.quedas_do_diario(texto, 300.0) == {}  # voltou 100 s depois: replug dela


def test_quedas_coladas_valem_uma_e_a_outra_placa_nao_entra_na_conta() -> None:
    outra = "046d:c52b"
    texto = _diario(
        (10.0, "nasceu", "4-1.2", PLACA), (11.0, "nasceu", "1-2", outra),
        (50.0, "sumiu", "4-1.2", PLACA), (50.2, "nasceu", "4-1.2", PLACA),
        (52.0, "sumiu", "4-1.2", PLACA), (52.4, "nasceu", "4-1.2", PLACA),
        (80.0, "sumiu", "1-2", outra), (95.0, "nasceu", "1-2", outra))
    quedas = qw.quedas_do_diario(texto, 110.0)
    assert quedas["usb:2357:012d"].n == 1
    assert "usb:046d:c52b" not in quedas


def test_horas_a_partir_de_duas_e_o_nivel_pelo_numero() -> None:
    assert qw.em_palavras(qw.Quedas(2, 600)) == "caiu 2× em 10 h"
    assert qw.em_palavras(qw.Quedas(1, 119)) == "caiu 1× em 119 min"
    assert qw.nivel(qw.Quedas(2, 5)) == "apertada"
    assert qw.nivel(qw.Quedas(3, 5)) == "sofrendo"


def test_o_diario_vem_por_executor_e_sob_a_suite_sem_executor_nada_roda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pedidos: list[list[str]] = []

    def executor(comando: list[str]) -> str | None:
        pedidos.append(comando)
        return _diario((10.0, "nasceu", "4-1", PLACA), (20.0, "sumiu", "4-1", PLACA),
                       (21.0, "nasceu", "4-1", PLACA))

    lidas = qw.ler_as_quedas(executor, agora=lambda: 100.0)
    assert lidas and lidas["usb:2357:012d"].n == 1
    assert pedidos == [qw.COMANDO] and "-k" in pedidos[0] and "-b" in pedidos[0]
    chamou = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: chamou.append(a))
    assert qw.ler_as_quedas() is None and not chamou
    assert qw.ler_as_quedas(lambda _c: None) is None


# ---------- a tela: 5 GHz, 2.4 GHz e as quedas ---------------------------------------------


def _cena(rede: dict[str, Any], usb: str = "3.0", viz: bool = True) -> dict[str, Any]:
    vid_pid = "2357:012d"
    return {
        "lugares": [{"id": "AA:BB:CC:00:00:01", "nome": "Adaptador", "cor": "azul"}],
        "aparelhos": [],
        "wifi": [rede],
        "vizinhos": ([{"id": vid_pid, "tipo": "", "nome": "", "sugestao": "wifi",
                       "sugestao_tipo": "wifi", "no": "/sys/velho/4-1.2", "lido": "wifi",
                       "produto": "802.11ac NIC"}] if viz else []),
        "portas": [{"id": f"porta-{vid_pid}", "caminho": "x", "usb": usb, "ocupa": vid_pid}],
        "evitados": {}, "canais_medidos": {}, "enlaces": {},
    }


def _linhas(cena: dict[str, Any]) -> dict[str, Any]:
    ocupantes = [o for o, _r in a08._os_outros_radios(cena)]
    regua = fa.montar([], ocupantes)
    return {ln.id: ln for ln in regua.outros}


def test_em_5_ghz_a_linha_diz_fora_da_faixa_e_nunca_nao_identificado() -> None:
    rede = {"no": "/sys/novo/3-1.2", "mhz": 5805, "largura": 80, "chave": "usb:2357:012d"}
    linhas = _linhas(_cena(rede))
    assert list(linhas) == ["2357:012d"]  # a MESMA linha, mesmo com o nó trocado
    ln = linhas["2357:012d"]
    assert ln.sem_faixa == fa.FORA_DA_FAIXA and ln.sub.startswith("5 GHz · canal 161")
    html = a08.html_dos_canais(_cena(rede))
    assert ESPECIE_DESCONHECIDA not in html and "Não identificado" not in html
    # fora da faixa dos controles, ele não atrapalha: sem linha (desenho aprovado de 05/10/2026)
    assert 'data-id="2357:012d"' not in html


def test_em_2_4_ghz_a_faixa_se_pinta_nos_canais_da_banda_e_o_usb3_e_dito() -> None:
    rede = {"no": "", "mhz": 2462, "largura": 20, "chave": "usb:2357:012d"}
    ln = _linhas(_cena(rede))["2357:012d"]
    assert ln.celulas and any(c.estado == fa.OCUPADO for c in ln.celulas)
    assert ln.sub == "2,4 GHz · canal 11"
    assert ln.nota == "USB 3.0 + 2,4 GHz"
    assert "USB 3.0 e 2,4 GHz" in ln.dica and "5 GHz" in ln.dica
    assert _linhas(_cena(rede, usb="2.0"))["2357:012d"].nota == ""
    assert _linhas(_cena({**rede, "mhz": 5805}))["2357:012d"].nota == ""


def test_o_selo_diz_quantas_vezes_a_placa_caiu_e_a_ausencia_nao_inventa() -> None:
    rede = {"no": "", "mhz": 2462, "largura": 20, "chave": "usb:2357:012d"}
    sem = _linhas(_cena(rede))["2357:012d"]
    assert "caiu" not in (sem.selo.texto if sem.selo else "")
    com = _linhas(_cena({**rede, "quedas": {"n": 12, "min": 24}}))["2357:012d"]
    assert com.selo
    assert (com.selo.nivel, com.selo.texto) == ("sofrendo", "caiu 12× em 24 min")
    pouca = _linhas(_cena({**rede, "quedas": {"n": 1, "min": 40}}))["2357:012d"]
    assert pouca.selo and pouca.selo.nivel == "apertada"
    html = a08.html_dos_canais(_cena({**rede, "quedas": {"n": 12, "min": 24}}))
    assert "Caiu 12× em 24 min" in html and "USB 3.0 e 2,4 GHz" in html
    assert "USB 3.0 + 2,4 GHz" in html, "a nota do USB 3.0 saiu do tooltip do ponto"


def test_a_rede_sem_vizinho_ganha_id_pela_chave_e_nunca_pelo_nome_da_interface() -> None:
    rede = {"no": "", "mhz": 2437, "largura": 20, "chave": "usb:2357:012d"}
    assert list(_linhas(_cena(rede, viz=False))) == ["wifi-usb-2357-012d"]
    sem_chave = {"no": "", "mhz": 2437, "largura": 20}
    assert list(_linhas(_cena(sem_chave, viz=False))) == ["wifi-0"]


def test_o_vizinho_que_e_a_rede_nao_ganha_outra_linha_com_botao() -> None:
    rede = {"no": "/sys/novo/3-1.2", "mhz": 5805, "largura": 80, "chave": "usb:2357:012d"}
    cena = _cena(rede)
    assert a08._vizinhos_sem_rede(cena) == []
    assert 'data-gesto="vizinho-o-que-e"' not in a08.html_dos_canais(cena)


def test_o_leitor_das_quedas_roda_em_fundo_e_junta_na_rede(monkeypatch: pytest.MonkeyPatch) -> None:
    redes = [{"no": "", "mhz": 2462, "largura": 20, "chave": "usb:2357:012d"},
             {"no": "", "mhz": 2437, "largura": None, "chave": "pci:0000:03:00.0"}]
    juntas = a08._o_wifi_com_as_quedas(redes, {"usb:2357:012d": qw.Quedas(3, 7)})
    assert juntas[0]["quedas"] == {"n": 3, "min": 7} and "quedas" not in juntas[1]
    assert a08._o_wifi_com_as_quedas(redes, None) == redes
    assert os.environ.get("PYTEST_CURRENT_TEST")  # a guarda da suíte está de pé
    assert a08._ler_as_quedas() is None
