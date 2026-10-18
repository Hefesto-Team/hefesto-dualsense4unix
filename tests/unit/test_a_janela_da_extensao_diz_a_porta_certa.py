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

import pathlib
import re
import sys

import pytest

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
