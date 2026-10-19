"""A janela da extensão diz a porta certa de cada jogo com o kit da Lovense.

Na lista de jogos da janela, o jogo com o kit ganha a marca «Fala com a Lovense» e, abaixo, UMA
linha pelo veredito da pasta: `alcanca_a_ponte` não diz nada; `porta_que_nada_atende`, `nao_lido` e
`desligado` dizem o que pôr no menu do jogo (a 20010 em HTTP, que não consulta nome nenhum); e
`aponta_para_outra_maquina` diz que o jogo fala direto com o app do celular. Nenhum endereço da
rede aparece na tela.

O DESENHO vem de `desenho_da_experimental.linha_do_kit`, que lê o `KitDoJogo` do produto; a
segunda passagem pinta a janela com os prontuários vivos.

MORDIDAS (executadas aqui): o kit Unity com «Use HTTP» ligado e a linha desenhada no veredito
`alcanca_a_ponte` reprovam; um IP de rede no HTML também.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "07-lancadores.html"
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

NO_MENU = "No menu Lovense do jogo: IP 127.0.0.1, porta 20010"


@pytest.fixture(scope="module")
def exp():
    from hefesto_dualsense4unix.interface import desenho_da_experimental

    return desenho_da_experimental


@pytest.fixture(scope="module")
def kits():
    from hefesto_dualsense4unix.integrations import kits_de_brinquedo

    return kits_de_brinquedo


def test_a_linha_de_cada_veredito(exp, kits) -> None:
    kit = kits.KitDoJogo
    assert exp.linha_do_kit(None) == ""
    assert exp.linha_do_kit(kit("lovense-unity", kits.ALCANCA_A_PONTE, 20010, "http")) == ""
    assert exp.linha_do_kit(kit("lovense-unity", kits.PORTA_QUE_NADA_ATENDE, 20100, "http")) == (
        f"{NO_MENU}, «Use HTTP» desligado")
    assert exp.linha_do_kit(kit("lovense-jj", kits.NAO_LIDO)) == (
        f"{NO_MENU}, «Conexão HTTP (20010)»")
    assert exp.linha_do_kit(kit("lovense-rpgmaker", kits.DESLIGADO)) == f"{NO_MENU}, «Mobile»"
    assert exp.linha_do_kit(kit("lovense-unity", kits.APONTA_PARA_OUTRA_MAQUINA)) == (
        "O jogo fala direto com o app do celular")


def test_o_unity_nunca_manda_ligar_o_use_http(exp, kits) -> None:
    """A MORDIDA do caso do Neon Nights: a opção do menu dele é invertida (medido, 15/10/2026)."""
    linha = exp.linha_do_kit(
        kits.KitDoJogo("lovense-unity", kits.PORTA_QUE_NADA_ATENDE, 20100, "http"))
    assert "desligado" in linha and "ligado" not in linha.replace("desligado", "")


def test_a_marca_e_a_linha_vao_ao_desenho_so_para_quem_tem_o_kit() -> None:
    doc = MOCKUP.read_text(encoding="utf-8")
    jogos = re.findall(r'<label class="jg-l">(.*?)</label>', doc, flags=re.S)
    por_nome = {re.search(r'jg-n">([^<]+)<', j).group(1): j for j in jogos}
    for sem_kit in ("Mortal Kombat", "Elden Ring"):
        assert "Fala com a Lovense" not in por_nome[sem_kit], sem_kit
    for com_kit in ("Neon Nights", "Planet Lust", "MonGirl Conquest", "Third Crisis", "Orpheus"):
        assert "Fala com a Lovense" in por_nome[com_kit], com_kit
    assert "jg-porta" not in por_nome["Third Crisis"], "o que alcança a ponte não leva linha"
    assert NO_MENU in por_nome["Neon Nights"] and "«Use HTTP» desligado" in por_nome["Neon Nights"]
    assert "app do celular" in por_nome["Orpheus"]


def test_nenhum_endereco_de_rede_chega_ao_html() -> None:
    """Só o 127.0.0.1 do menu do jogo; o IP da rede de casa nunca entra (e nem existe no kit)."""
    doc = MOCKUP.read_text(encoding="utf-8")
    ips = set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", doc))
    assert ips <= {"127.0.0.1"}, ips


def test_a_regua_morde_o_ip_de_mentira_e_a_linha_no_alcanca_a_ponte(exp, kits) -> None:
    com_ip = MOCKUP.read_text(encoding="utf-8").replace("<body", "<body data-ip='192.168.7.9'", 1)
    assert set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", com_ip)) - {"127.0.0.1"}
    assert exp.linha_do_kit(kits.KitDoJogo("lovense-unity", kits.PORTA_QUE_NADA_ATENDE, 20100,
                                           "http")) != ""


# --- O produto: a janela de verdade lê o kit de cada jogo da pasta dele -------------------------

_IP_DE_FORA = "192.0.2.10"


def _unity(biblioteca: Path, appid: str, produto: str, *, ip: str, porta: str) -> None:
    apps = biblioteca / "steamapps"
    raiz = apps / "common" / produto
    (raiz / f"{produto}_Data" / "Managed").mkdir(parents=True, exist_ok=True)
    (raiz / f"{produto}_Data" / "Managed" / "LovenseRemote.dll").write_bytes(b"MZ")
    (raiz / f"{produto}_Data" / "app.info").write_text(f"Empresa\n{produto}", encoding="utf-8")
    salvo = (apps / "compatdata" / appid / "pfx" / "drive_c" / "users" / "steamuser" / "AppData"
             / "LocalLow" / "Empresa" / produto)
    salvo.mkdir(parents=True, exist_ok=True)
    (salvo / "Settings.sav").write_text(json.dumps({
        "Lovense: Enabled": 1, "Lovense: Local IP": ip, "Lovense: Port": porta,
        "Lovense: Use HTTP": 0}), encoding="utf-8")
    _manifesto(biblioteca, appid, produto)


def _manifesto(biblioteca: Path, appid: str, produto: str) -> None:
    (biblioteca / "steamapps" / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{produto}"\n'
        f'\t"installdir"\t\t"{produto}"\n}}\n', encoding="utf-8")


@pytest.fixture
def biblioteca(tmp_path, monkeypatch):
    """Steam de mentira em casa de mentira, com um jogo em cada situação e um perfil por jogo."""
    from hefesto_dualsense4unix.mods.instalador import Lugares

    casa = tmp_path / "casa"
    steam = casa / ".local" / "share" / "Steam"
    (steam / "steamapps" / "common").mkdir(parents=True)
    assert not str(casa).startswith("/home/"), "a casa de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(casa))
    lg = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # noqa-acento: campo
                 registro=tmp_path / "config" / "mods.json",
                 estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lg))
    _unity(steam, "1001", "Neon Nights", ip="127.0.0.1", porta="20100")
    _unity(steam, "1002", "Third Crisis", ip="127.0.0.1", porta="20010")
    _unity(steam, "1003", "Orpheus", ip=_IP_DE_FORA, porta="20010")
    (steam / "steamapps" / "common" / "Elden Ring").mkdir()
    _manifesto(steam, "1004", "Elden Ring")
    for appid, nome in (("1001", "Neon Nights"), ("1002", "Third Crisis"), ("1003", "Orpheus"),
                        ("1004", "Elden Ring")):
        save_profile(Profile(name=nome, priority=5,
                             match=MatchCriteria(window_class=[f"steam_app_{appid}"])))
    return steam


def _a07():
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


class _Ponte:
    def escolher_arquivo(self, titulo: str, padrao: str = "", sugestao: str = "") -> str | None:
        return None


def _janela_da_extensao(tmp_path) -> str:
    import pacotes

    a07 = _a07()
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    pasta = tmp_path / "fonte" / "acess"
    if not pasta.exists():
        pasta.mkdir(parents=True)
        (pasta / "hefesto-mod.json").write_text(json.dumps({
            "id": "acess", "nome": "Acess", "versao": "0.1", "api": ">=1,<3",  # noqa-acento: chave do contrato
            "licenca": "MIT", "tipos": ["tema"], "tema": {},  # noqa-acento: chave do contrato
            "opcoes": [{"id": "jogos", "rotulo": "Jogos que seguem", "tipo": "jogos"}],  # noqa-acento: chave do contrato
        }), encoding="utf-8")
        a07.instalar_modificacao(ctx, {"forma": {"mod-endereco": str(pasta)}}, _Ponte())
    return a07.configurar_modificacao(ctx, {"v": "acess"}, _Ponte())["blocos"]["#mod-janela"]


def _caixa_de(janela: str, appid: str) -> str:
    for rotulo in re.findall(r'<label class="jg-l">(.*?)</label>', janela, flags=re.S):
        if f":steam_app_{appid}\"" in rotulo:
            return rotulo
    raise AssertionError(f"o jogo {appid} não está na lista da janela")


def test_a_janela_do_produto_diz_a_porta_certa_de_cada_jogo_pela_pasta(
        biblioteca, tmp_path) -> None:
    janela = _janela_da_extensao(tmp_path)

    errada = _caixa_de(janela, "1001")
    assert "Fala com a Lovense" in errada
    assert f"{NO_MENU}, «Use HTTP» desligado" in errada

    certa = _caixa_de(janela, "1002")
    assert "Fala com a Lovense" in certa and "jg-porta" not in certa, (
        "o jogo que alcança a ponte leva a marca e nenhuma linha")

    celular = _caixa_de(janela, "1003")
    assert "app do celular" in celular and "Fala com a Lovense" in celular

    sem_kit = _caixa_de(janela, "1004")
    assert "Fala com a Lovense" not in sem_kit and "jg-porta" not in sem_kit


def test_o_ip_que_o_jogo_guardou_nunca_chega_a_tela(biblioteca, tmp_path) -> None:
    # D-1810-A-JANELA-DA-EXTENSAO-LE-O-KIT-PELA-PASTA-E-NUNCA-MOSTRA-O-IP
    janela = _janela_da_extensao(tmp_path)
    assert _IP_DE_FORA not in janela
    assert set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", janela)) <= {"127.0.0.1"}


def test_a_linha_some_quando_o_jogo_passa_a_alcancar_a_ponte_e_reabrir_a_janela_rele(
        biblioteca, tmp_path) -> None:
    assert "jg-porta" in _caixa_de(_janela_da_extensao(tmp_path), "1001")
    _unity(biblioteca, "1001", "Neon Nights", ip="127.0.0.1", porta="20010")
    depois = _caixa_de(_janela_da_extensao(tmp_path), "1001")
    assert "Fala com a Lovense" in depois and "jg-porta" not in depois


def test_o_jogo_sem_pasta_na_biblioteca_aparece_sem_marca_e_sem_erro(
        biblioteca, tmp_path) -> None:
    save_profile(Profile(name="Fora da Steam", priority=5,
                         match=MatchCriteria(window_class=["steam_app_1999"])))
    caixa = _caixa_de(_janela_da_extensao(tmp_path), "1999")
    assert "Fala com a Lovense" not in caixa
