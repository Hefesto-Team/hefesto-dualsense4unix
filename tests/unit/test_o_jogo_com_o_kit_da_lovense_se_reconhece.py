"""O jogo com o kit da Lovense se reconhece pela pasta e diz se a escolha salva alcança a ponte.

Biblioteca de mentira em `tmp_path`: nada da Steam do usuário é lido. O endereço que o jogo guardou
(IP de documentação, faixa 192.0.2.0/24 e 198.51.100.0/24) vira só uma classe: não sai no veredito,
no `repr`, no JSON do prontuário, no terminal nem em log.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import kits_de_brinquedo as kdb
from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj

_IP_DE_FORA = "192.0.2.10"
_IP_DO_JJ = "198.51.100.7"


def _manifesto(biblioteca: Path, appid: str, produto: str) -> Path:
    apps = biblioteca / "steamapps"
    raiz = apps / "common" / produto
    raiz.mkdir(parents=True)
    (apps / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{produto}"\n'
        f'\t"installdir"\t\t"{produto}"\n}}\n',
        encoding="utf-8",
    )
    return raiz


def _prefixo(biblioteca: Path, appid: str) -> Path:
    return (
        biblioteca / "steamapps" / "compatdata" / appid / "pfx" / "drive_c" / "users"
        / "steamuser" / "AppData"
    )


def _unity(
    biblioteca: Path,
    appid: str,
    *,
    produto: str = "Jogo Unity",
    salvo: dict[str, object] | None = None,
    com_o_kit: bool = True,
) -> Path:
    """Um jogo Unity de mentira: o kit em `Managed`, o `app.info` e, se for o caso, o save."""
    raiz = _manifesto(biblioteca, appid, produto)
    dados = raiz / f"{produto}_Data"
    (dados / "Managed").mkdir(parents=True)
    (raiz / f"{produto}.exe").write_bytes(b"MZ" + b"\0" * 64)
    if com_o_kit:
        (dados / "Managed" / "LovenseRemote.dll").write_bytes(b"MZ")
    (dados / "app.info").write_text(f"Empresa Teste\n{produto}", encoding="utf-8")
    if salvo is not None:
        pasta = _prefixo(biblioteca, appid) / "LocalLow" / "Empresa Teste" / produto
        pasta.mkdir(parents=True)
        (pasta / "Settings.sav").write_text(json.dumps(salvo), encoding="utf-8")
    return raiz


def _salvo(
    ip: str = "127.0.0.1", porta: str = "20010", http: int = 0, ligado: int = 1
) -> dict[str, object]:
    return {
        "Master Volume": 0.7,
        "Lovense: Enabled": ligado,
        "Lovense: Local IP": ip,
        "Lovense: Port": porta,
        "Lovense: Use HTTP": http,
    }


def _jj(
    biblioteca: Path,
    appid: str,
    *,
    dll: bytes = b"MZ....https://x.lovense.club:%d/command",
    config: str | None = None,
) -> Path:
    produto = f"Planet {appid}"
    raiz = _manifesto(biblioteca, appid, produto)
    (raiz / "Lust.exe").write_bytes(b"MZ" + b"\0" * 64)
    (raiz / "lust_script.dll").write_bytes(dll)
    if config is not None:
        pasta = _prefixo(biblioteca, appid) / "Roaming" / "Skullgear" / produto
        pasta.mkdir(parents=True)
        (pasta / "CONFIG.xml").write_text(config, encoding="utf-8")
    return raiz


def _xml(*customs: tuple[str, str]) -> str:
    itens = "".join(f'\t\t<custom name="{n}" value="{v}"/>\n' for n, v in customs)
    cabeca = '<?xml version="1.0" encoding="utf-8"?>\n<config>\n\t<customs>\n'
    return f"{cabeca}{itens}\t</customs>\n</config>\n"


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    biblioteca = casa / ".local" / "share" / "Steam"
    (biblioteca / "steamapps").mkdir(parents=True)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(casa))
    return biblioteca


# --- a tabela -------------------------------------------------------------------------------


def test_a_tabela_traz_as_tres_formas_sem_appid_embarcado() -> None:
    tabela = {k.kit: k for k in kdb.carregar_tabela()}
    assert set(tabela) == {"lovense-unity", "lovense-jj", "lovense-rpgmaker"}
    assert tabela["lovense-unity"].sinais == ("*_Data/Managed/LovenseRemote.dll",)
    assert tabela["lovense-jj"].contem == "lovense.club"
    assert tabela["lovense-rpgmaker"].config == kdb.NENHUMA
    dados = [
        ln for ln in kdb.TABELA.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    assert not [ln for ln in dados if any(p.isdigit() and len(p) >= 5 for p in ln.split(","))]


def test_a_linha_fora_da_regra_nao_entra(tmp_path: Path) -> None:
    csv = tmp_path / "t.csv"
    csv.write_text(
        "kit,sinais,contem,config,fonte\n"
        "ok,a/*.dll,,nenhuma,x\n"
        "config-fora,a.dll,,inventada,x\n"
        "sem-sinal,,,nenhuma,x\n"
        "ok,b.dll,,nenhuma,x\n",
        encoding="utf-8",
    )
    assert [k.kit for k in kdb.carregar_tabela(csv)] == ["ok"]
    assert kdb.carregar_tabela(tmp_path / "nao-existe.csv") == ()


# --- o reconhecimento pela pasta ------------------------------------------------------------


def test_a_pasta_unity_com_o_kit_se_reconhece_pelo_curinga_e_sem_linha_nova(lar: Path) -> None:
    raiz = _unity(lar, "720001", produto="Qualquer Nome")
    achado = kdb.reconhecer(raiz)
    assert achado is not None and achado[0].kit == "lovense-unity"
    sem = _unity(lar, "720002", produto="Sem Kit", com_o_kit=False)
    assert kdb.reconhecer(sem) is None and kdb.kit_do_jogo(sem, "720002") is None
    assert kdb.kit_do_jogo(None, "720003") is None


def test_o_script_sem_a_cadeia_lovense_club_nao_e_kit(lar: Path) -> None:
    sem = _jj(lar, "720004", dll=b"MZ....nada de brinquedo aqui")
    assert kdb.kit_do_jogo(sem, "720004") is None
    com = _jj(lar, "720005", dll=b"MZ....HTTPS://x.Lovense.Club:30010/command")
    kit = kdb.kit_do_jogo(com, "720005")
    assert kit is not None and kit.kit == "lovense-jj"


def test_a_cadeia_que_cai_na_emenda_de_duas_fatias_ainda_e_achada(
    lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(kdb, "_FATIA", 7)
    raiz = _jj(lar, "720006", dll=b"1234567890lovense.club")
    assert kdb.kit_do_jogo(raiz, "720006") is not None


def test_o_kit_do_rpgmaker_se_reconhece_e_a_escolha_nao_se_le(lar: Path) -> None:
    raiz = _manifesto(lar, "720007", "Mon de Mentira")
    (raiz / "www" / "js" / "plugins").mkdir(parents=True)
    (raiz / "www" / "js" / "plugins" / "Lovense.js").write_text("//", encoding="utf-8")
    kit = kdb.kit_do_jogo(raiz, "720007")
    assert kit is not None and kit.kit == "lovense-rpgmaker" and kit.veredito == kdb.NAO_LIDO


# --- o veredito da escolha salva ------------------------------------------------------------


@pytest.mark.parametrize(
    ("ip", "porta", "http", "veredito", "esquema"),
    [
        ("127.0.0.1", "20010", 0, kdb.ALCANCA_A_PONTE, "http"),
        ("localhost", "20010", 0, kdb.ALCANCA_A_PONTE, "http"),
        ("127.0.0.1", "30010", 1, kdb.ALCANCA_A_PONTE, "https"),
        ("127.0.0.1", "20010", 1, kdb.ALCANCA_A_PONTE, "https"),
        ("127.0.0.1", "20100", 1, kdb.PORTA_QUE_NADA_ATENDE, "https"),
        ("127.0.0.1", "3", 0, kdb.PORTA_QUE_NADA_ATENDE, "http"),
        (_IP_DE_FORA, "20010", 0, kdb.APONTA_PARA_OUTRA_MAQUINA, "http"),
        (_IP_DE_FORA, "20100", 1, kdb.APONTA_PARA_OUTRA_MAQUINA, "https"),
    ],
)
def test_a_escolha_do_unity_vira_a_classe_certa(
    lar: Path, ip: str, porta: str, http: int, veredito: str, esquema: str
) -> None:
    raiz = _unity(lar, "720010", salvo=_salvo(ip=ip, porta=porta, http=http))
    kit = kdb.kit_do_jogo(raiz, "720010")
    assert kit is not None
    assert (kit.veredito, kit.esquema) == (veredito, esquema)
    assert kit.porta == int(porta)


def test_o_use_http_do_jogo_e_invertido_ligado_e_https(lar: Path) -> None:
    ligado = kdb.kit_do_jogo(_unity(lar, "720011", salvo=_salvo(porta="30010", http=1)), "720011")
    desligado = kdb.kit_do_jogo(
        _unity(lar, "720012", produto="Outro", salvo=_salvo(porta="20010", http=0)), "720012"
    )
    assert ligado is not None and ligado.esquema == "https"
    assert desligado is not None and desligado.esquema == "http"


def test_o_jogo_desligado_nao_e_classificado_por_endereco(lar: Path) -> None:
    raiz = _unity(lar, "720013", salvo=_salvo(ip=_IP_DE_FORA, ligado=0))
    kit = kdb.kit_do_jogo(raiz, "720013")
    assert kit is not None and kit.veredito == kdb.DESLIGADO


def test_sem_arquivo_salvo_ou_com_arquivo_ilegivel_e_nao_lido(lar: Path) -> None:
    sem = _unity(lar, "720014", produto="Nunca Abriu")
    quebrado = _unity(lar, "720015", produto="Quebrado")
    pasta = _prefixo(lar, "720015") / "LocalLow" / "Empresa Teste" / "Quebrado"
    pasta.mkdir(parents=True)
    (pasta / "Settings.sav").write_text("{não é json", encoding="utf-8")
    sem_lovense = _unity(lar, "720016", produto="Sem Opção", salvo={"Master Volume": 1})
    for raiz, appid in ((sem, "720014"), (quebrado, "720015"), (sem_lovense, "720016")):
        kit = kdb.kit_do_jogo(raiz, appid)
        assert kit is not None and kit.veredito == kdb.NAO_LIDO, appid


@pytest.mark.parametrize(
    "salvo",
    [
        _salvo(ip=""),
        _salvo(porta="abc"),
        _salvo(porta="99999"),
        {**_salvo(), "Lovense: Enabled": "talvez"},
        {k: v for k, v in _salvo().items() if k != "Lovense: Port"},
        {k: v for k, v in _salvo().items() if k != "Lovense: Local IP"},
    ],
)
def test_a_escolha_incompleta_e_nao_lido_e_nunca_outra_maquina(
    lar: Path, salvo: dict[str, object]
) -> None:
    """O «não sei» fica «não sei»: nada do que falta vira classe de endereço."""
    kit = kdb.kit_do_jogo(_unity(lar, "720018", salvo=salvo), "720018")
    assert kit is not None and kit.veredito == kdb.NAO_LIDO
    sem_ip = _xml(("lovense_enabled", "true"))
    kit = kdb.kit_do_jogo(_jj(lar, "720019", config=sem_ip), "720019")
    assert kit is not None and kit.veredito == kdb.NAO_LIDO


@pytest.mark.parametrize("ip", ["127.0.0.2", "::1", "[::1]"])
def test_o_endereco_local_que_nao_e_a_ponte_e_porta_que_nada_atende(lar: Path, ip: str) -> None:
    """A ponte só escuta em 127.0.0.1: o resto do próprio computador não é «outra máquina»."""
    kit = kdb.kit_do_jogo(_unity(lar, "720026", salvo=_salvo(ip=ip)), "720026")
    assert kit is not None and kit.veredito == kdb.PORTA_QUE_NADA_ATENDE


def test_o_app_info_que_sobe_de_pasta_nao_leva_a_lugar_nenhum(lar: Path) -> None:
    raiz = _unity(lar, "720017", produto="Traicao")
    (raiz / "Traicao_Data" / "app.info").write_text("../../..\nx", encoding="utf-8")
    # A isca: um Settings.sav válido exatamente onde o nome que sobe levaria a leitura.
    (_prefixo(lar, "720017") / "LocalLow").mkdir(parents=True)
    isca = _prefixo(lar, "720017").parent.parent / "x"
    isca.mkdir(parents=True)
    (isca / "Settings.sav").write_text(json.dumps(_salvo()), encoding="utf-8")
    kit = kdb.kit_do_jogo(raiz, "720017")
    assert kit is not None and kit.veredito == kdb.NAO_LIDO


def test_o_config_do_jj_so_com_enabled_e_ip_vale_https_e_30010(lar: Path) -> None:
    config = _xml(("lovense_enabled", "true"), ("lovense_ip", "127.0.0.1"))
    kit = kdb.kit_do_jogo(_jj(lar, "720020", config=config), "720020")
    assert kit is not None
    assert (kit.veredito, kit.porta, kit.esquema) == (kdb.ALCANCA_A_PONTE, 30010, "https")


def test_o_jj_com_http_e_20010_gravados_e_com_o_ip_de_outra_maquina(lar: Path) -> None:
    http = _xml(
        ("lovense_enabled", "true"), ("lovense_ip", "127.0.0.1"),
        ("lovense_port", "20010"), ("lovense_connection", "http"),
    )
    kit = kdb.kit_do_jogo(_jj(lar, "720021", config=http), "720021")
    assert kit is not None
    assert (kit.veredito, kit.porta, kit.esquema) == (kdb.ALCANCA_A_PONTE, 20010, "http")
    fora = _xml(("lovense_enabled", "true"), ("lovense_ip", _IP_DO_JJ))
    kit = kdb.kit_do_jogo(_jj(lar, "720022", config=fora), "720022")
    assert kit is not None and kit.veredito == kdb.APONTA_PARA_OUTRA_MAQUINA


def test_o_jj_desligado_e_o_sem_config_e_o_xml_quebrado(lar: Path) -> None:
    off = _xml(("lovense_enabled", "false"), ("lovense_ip", _IP_DO_JJ))
    quebrado = "<config><customs><custom name="
    esperados = {"720023": (off, kdb.DESLIGADO), "720024": (None, kdb.NAO_LIDO),
                 "720025": (quebrado, kdb.NAO_LIDO)}
    for appid, (config, veredito) in esperados.items():
        kit = kdb.kit_do_jogo(_jj(lar, appid, config=config), appid)
        assert kit is not None and kit.veredito == veredito, appid


# --- o endereço nunca sai -------------------------------------------------------------------


def test_o_endereco_do_jogo_nao_sai_no_veredito_no_repr_no_json_nem_no_log(
    lar: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    _unity(lar, "720030", produto="Com Ip", salvo=_salvo(ip=_IP_DE_FORA, porta="20100", http=1))
    _jj(lar, "720031", config=_xml(("lovense_enabled", "true"), ("lovense_ip", _IP_DO_JJ)))
    censo = pdj.levantar_censo(allowlist=[], pontes={})
    em_json = json.dumps(censo.como_dicionario(), ensure_ascii=False)
    textos = [repr(censo), em_json, pdj._tabela(censo)]
    for ficha in censo.jogos:
        textos += [repr(ficha), str(ficha.kit), repr(ficha.kit)]
    textos += [r.getMessage() for r in caplog.records] + list(capsys.readouterr())
    for texto in textos:
        assert _IP_DE_FORA not in texto and _IP_DO_JJ not in texto
    (ficha,) = [j for j in censo.jogos if j.appid == "720030"]
    assert ficha.kit is not None and ficha.kit.veredito == kdb.APONTA_PARA_OUTRA_MAQUINA


# --- o prontuário ---------------------------------------------------------------------------


def test_o_prontuario_traz_o_campo_kit_e_o_veredito_do_controle_nao_muda(lar: Path) -> None:
    # D-1610-O-KIT-DE-BRINQUEDO-SE-RECONHECE-PELA-PASTA
    """O jogo com o kit e o jogo sem ele, iguais no resto, têm o mesmo veredito e estorvos."""
    _unity(lar, "720040", produto="Com Kit", salvo=_salvo())
    _unity(lar, "720041", produto="Sem Kit", com_o_kit=False)
    censo = pdj.levantar_censo(allowlist=[], pontes={})
    (com,) = [j for j in censo.jogos if j.appid == "720040"]
    (sem,) = [j for j in censo.jogos if j.appid == "720041"]
    assert com.kit is not None and com.kit.veredito == kdb.ALCANCA_A_PONTE
    assert sem.kit is None
    assert com.veredito == sem.veredito
    assert [e.chave for e in com.estorvos] == [e.chave for e in sem.estorvos]
    dicionario = com.como_dicionario()
    assert dicionario["kit"] == {
        "kit": "lovense-unity", "veredito": kdb.ALCANCA_A_PONTE, "porta": 20010, "esquema": "http",
    }
    assert sem.como_dicionario()["kit"] is None


def test_o_censo_rapido_tambem_traz_o_kit(lar: Path) -> None:
    """O kit é leitura da pasta, não da varredura de executável: o `examinar=False` o traz."""
    _unity(lar, "720042", salvo=_salvo(porta="20100"))
    censo = pdj.levantar_censo(allowlist=[], pontes={}, examinar=False)
    (ficha,) = [j for j in censo.jogos if j.appid == "720042"]
    assert ficha.kit is not None and ficha.kit.veredito == kdb.PORTA_QUE_NADA_ATENDE
