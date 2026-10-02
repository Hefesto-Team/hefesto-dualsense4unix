#!/usr/bin/env python3
"""A COR DA PÍLULA DO CHECK-UP É DO ACHADO, e não da posição no desenho."""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"


def _pacote():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _regua():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface import regua_do_mockup

    return regua_do_mockup


def _estados() -> list[str]:
    from hefesto_dualsense4unix.interface.conexoes import SELO_DO_ESTADO

    return list(SELO_DO_ESTADO)


def test_o_pacote_so_responde_a_pergunta_do_elemento() -> None:
    """Cada lista traz o SEU estado ou o vazio — nunca o de outro endereço."""
    p = _pacote()
    itens = [{"estado": e} for e in _estados()]
    listas = p._selos_por_estado(itens)

    assert set(listas) == set(p.ENDERECO_DO_ESTADO.values()), (
        "faltou (ou sobrou) um endereço de estado no que o pacote emite")

    for estado, endereco in p.ENDERECO_DO_ESTADO.items():
        for i, valor in enumerate(listas[endereco]):
            esperado = estado if itens[i]["estado"] == estado else ""
            assert valor == esperado, (
                f"`{endereco}` pergunta se o estado é `{estado}` e recebeu "
                f"{valor!r} para a linha {i}, cujo estado é "
                f"{itens[i]['estado']!r}. Um elemento pergunta UMA coisa; "
                f"responder com o token de outra pergunta é o que fazia a "
                f"régua acusar endereço morto sobre a tela certa.")


def _ctx():  # type: ignore[no-untyped-def]
    """Uma mesa de dois — o bastante para `pacote()` correr inteiro."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": "galactic-purple",
         "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
         "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_o_pacote_liga_os_quatro_enderecos() -> None:
    """A METADE QUE FALTAVA NESTE ARQUIVO, e ela é a que morde."""
    p = _pacote()
    saiu = p.pacote(_ctx())
    for endereco in p.ENDERECO_DO_ESTADO.values():
        assert endereco in saiu, (
            f"o `pacote()` não emite `{endereco}` — o desenho tem o endereço e "
            f"ninguém escreve nele")
    estados = set(_estados())
    for estado, endereco in p.ENDERECO_DO_ESTADO.items():
        for valor in saiu[endereco]:
            assert valor in ("", estado), (
                f"`{endereco}` pergunta se o estado é `{estado}` e o "
                f"`pacote()` emitiu {valor!r}. Todo token de "
                f"{sorted(estados - {estado})} é resposta de outra pergunta, e "
                f"é o que fazia a régua acusar endereço morto.")


def test_um_achado_certo_nao_acende_o_vermelho_de_problema() -> None:
    """Os três `certo` da mesa dela deixam a pílula do `problema` APAGADA."""
    p = _pacote()
    listas = p._selos_por_estado([{"estado": "certo"}] * 3)
    assert listas["selo-estado"] == ["", "", ""], (
        "a pílula do `problema` recebeu um token que não é o dela")
    assert listas["selo-certo"] == ["certo"] * 3, (
        "o interruptor do `certo` não acendeu com três achados `certo`")


def _pilula(quando: str, classe: str = "on", aceso: bool = False):  # type: ignore[no-untyped-def]
    r = _regua()
    return r._Campo(chave="selo-x", dono="", alvo="classe",
                    valor=(quando if aceso else ""), quando=quando)


def test_o_estado_cru_num_elemento_de_um_estado_so_e_endereco_morto() -> None:
    """O veredito com o token errado, e o veredito com o certo. Lado a lado."""
    r = _regua()
    campo = _pilula("problema")

    cru = r._classificar([campo], [""], {("", "selo-x"): ["certo"]}, [True])
    assert cru[0].classe == r.MOCKUP, (
        "emitir `certo` num elemento que só sabe dizer `problema` TEM de ser "
        "acusado — é a régua fazendo o trabalho dela")
    assert "ENDEREÇO MORTO" in cru[0].nota

    curado = r._classificar([campo], [""], {("", "selo-x"): [""]}, [True])
    assert curado[0].classe == r.PRODUTO, (
        "com o vazio — o `não` desta pergunta — o campo é do produto: o piloto "
        "esteve nele e a tela mostra exatamente o que ele escreveu")


def test_o_interruptor_aceso_e_produto() -> None:
    """E o `sim` também: o elemento do estado que casa acende, e isso é produto."""
    r = _regua()
    campo = _pilula("certo")
    fora = r._classificar([campo], ["certo"], {("", "selo-x"): ["certo"]}, [True])
    assert fora[0].classe == r.PRODUTO


def test_a_regua_le_o_html_declarado_como_a_tela_o_mostra() -> None:
    """Uma declaração com `<b>` chega à comparação SEM as tags, como o DOM."""
    r = _regua()
    campo = r._Campo(chave="teto-explica", dono="p1", alvo="html",
                     valor="hoje segue o global")
    assert r._declarado_neste_elemento(campo, "hoje <b>segue o global</b>") == (
        "hoje segue o global"), (
        "a régua lê o alvo `html` pelo TEXTO (ver `_campo` e o `LER_CAMPOS` do "
        "piloto). Comparar a declaração COM as tags contra a tela SEM elas "
        "acusa endereço morto sobre a pintura que acertou.")


def test_o_teto_da_vibracao_nao_e_endereco_morto_quando_o_produto_o_pinta() -> None:
    """O caso medido em 03/09: o produto pinta o `?` e a régua o acusava."""
    r = _regua()
    texto = ("O teto da vibração deste controle. O global manda e o do controle "
             "sobrepõe: hoje este controle segue o global.")
    marcado = ("O teto da vibração <b>deste controle</b>. O global manda e o do "
               "controle sobrepõe: hoje este controle <b>segue o global</b>.")
    campo = r._Campo(chave="teto-explica", dono="p1", alvo="html", valor=texto)
    fora = r._classificar([campo], [texto], {("p1", "teto-explica"): marcado},
                          [True])
    assert fora[0].classe == r.PRODUTO, (
        f"o `?` do teto voltou a ser acusado: {fora[0].nota}")


def test_o_html_que_o_produto_nao_pintou_continua_acusado() -> None:
    """A cura do `html` NÃO pode cegar a régua: texto diferente segue acusado."""
    r = _regua()
    campo = r._Campo(chave="achado-explica", dono="", alvo="html",
                     valor="o desenho")
    fora = r._classificar([campo], ["o desenho"],
                          {("", "achado-explica"): "<b>o produto</b>"}, [True])
    assert fora[0].classe == r.MOCKUP, (
        "um endereço em que o produto declara UMA coisa e a tela mostra OUTRA "
        "continua sendo endereço morto — tirar as tags é normalizar a forma, "
        "nunca perdoar a diferença")


def test_o_desenho_tem_um_interruptor_por_estado() -> None:
    """Toda linha do exame sabe mostrar os QUATRO estados, e um só de cada vez."""
    p = _pacote()
    html = BANCADA.read_text(encoding="utf-8")
    linhas = re.findall(r'<div class="exame"[^>]*>.*?</div>', html, re.S)
    assert linhas, "a bancada da 08 não tem uma linha de exame"

    for i, linha in enumerate(linhas):
        for estado, endereco in p.ENDERECO_DO_ESTADO.items():
            marca = f'data-campo="{endereco}"'
            assert marca in linha, (
                f"a linha {i} do exame não tem onde mostrar o estado "
                f"`{estado}`: falta `{marca}`")
            tag = re.search(rf"<[a-z]+[^>]*{re.escape(marca)}[^>]*>", linha)
            assert tag and f'data-hef-quando="{estado}"' in tag.group(0), (
                f"o endereço `{endereco}` da linha {i} não pergunta pelo "
                f"estado `{estado}`")
            assert tag and 'data-hef-alvo="classe"' in tag.group(0), (
                f"o endereço `{endereco}` da linha {i} não usa o alvo `classe`")
        acesos = len(re.findall(r'<i class="est [a-z-]+ on"', linha))
        assert acesos <= 1, (
            f"a linha {i} do exame nasce com {acesos} interruptores acesos")


def test_a_folha_de_estilo_le_a_cor_do_irmao() -> None:
    """As regras que fazem o interruptor invisível pintar a pílula ao lado."""
    html = BANCADA.read_text(encoding="utf-8")
    for regra in (".exame .est{display:none}",
                  ".exame .est-ok.on ~ .selo{",
                  ".exame .est-warn.on ~ .selo{",
                  ".exame .est-info.on ~ .selo{",
                  ".exame .est.on ~ .selo.grave{"):
        assert regra in html, (
            f"sumiu do desenho a regra `{regra}` — sem ela o interruptor acende "
            f"e a pílula não muda de cor, que é endereço sem efeito")
