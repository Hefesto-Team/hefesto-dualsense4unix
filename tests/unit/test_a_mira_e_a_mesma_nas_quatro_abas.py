"""A Mira da Calibrar é a mesma das abas Navegação, Conexões e Perfis.

A-MIRA-DA-CALIBRAR-E-A-MESMA-DAS-OUTRAS-ABAS-01 (29/09/2026, ela: *«isso aqui tem que tá
sincronizado com a aba Conexões, Navegação. e Perfis»*). Os quatro ajustes da Mira de cada
controle têm UM dono (o `mira.set` e o `_merge_mira` do daemon) e UM leitor
(`a11.resumo_da_mira`); a Calibrar é o único lugar de MUDAR, e as outras três dizem os números.

A régua roda sobre o dono de verdade: o `IpcServer` real, o perfil num lar de mentira, e os
gestos da Calibrar chamando o `mira.set` do servidor. O esperado sai do que a régua MANDOU
(os rótulos, de `calibrar.py`), e nunca do que um pacote escreveu.

AS MORDIDAS (rodadas em 07/10/2026 e devolvidas):

* a 06 lendo a mira do perfil no lugar da entrada do daemon → a régua 1 reprova no P3;
* a 08 casando a entrada pela posição, e não pelo endereço (as entradas chegam em outra ordem
  que a mesa) → reprova no P3;
* uma memória no `resumo_da_mira` que ignora o argumento → reprova quando o segundo número muda;
* o selo da 08 afirmando «✓» no Nativo, e a 06 dizendo a linha no Nativo → a régua do Nativo
  reprova;
* o endereço do cartão da 06 tirado do gerador → a régua 5 reprova;
* um `definir_da_peca` por cima do mapa velho no lugar do `definir_por_peca` → a régua 6
  reprova (a peça do perfil A sobrevive à troca);
* o nome do perfil lido de `state["active_profile"]` cru → a régua 7 reprova.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.interface import mesa_viva
from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    a06_navegacao,
    a08_conexoes,
    a10_perfis,
    a11_calibrar_sensores,
    pacote_da_pagina,
    perfil,
)
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from tests.unit.test_a_mira_por_movimento_na_tela import (  # noqa: F401
    _P1,
    _P2,
    _P3,
    _P4,
    _mira_set,
    _mesa_de_verdade,
    _hub,
    _registro_limpo,
    _servidor_com_perfil,
    perfis,
)

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import calibrar

UNIQS = (_P1, _P2, _P3, _P4)
CHAVE = {u: u.replace(":", "") for u in UNIQS}
#: As entradas chegam do daemon em outra ordem que a da mesa (a mesa é por jogador).
ORDEM_DO_DAEMON = (_P3, _P1, _P4, _P2)


class _PonteDoServidor:
    """A ponte da tela, ligada ao `mira.set` do servidor de verdade."""

    def __init__(self, servidor: IpcServer) -> None:
        self.servidor = servidor
        self.respostas: list[dict[str, Any]] = []

    def mira_set_detalhado(self, **kw: Any) -> dict[str, Any]:
        corpo = _mira_set(self.servidor, **kw)
        self.respostas.append(corpo)
        return corpo


def _estado(servidor: IpcServer, transportes: tuple[str, ...] = ("usb", "bt", "bt", "bt"),
            *, nativo: bool = False) -> dict[str, Any]:
    """O `state_full` dos quatro, com o bloco `mira` do `_merge_mira` do servidor."""
    entradas: list[dict[str, Any]] = []
    for uniq in ORDEM_DO_DAEMON:
        n = UNIQS.index(uniq) + 1
        entradas.append({"uniq": uniq, "connected": True, "player": n, "player_slot": n,
                         "transport": transportes[n - 1], "battery_pct": 90,
                         "is_primary": n == 1, "inputs": {}})
    servidor._merge_mira(entradas)
    return {"active_profile": servidor.store.active_profile, "native_mode": nativo,
            "controllers": entradas}


def _ctx(state: dict[str, Any]) -> Contexto:
    mesa = mesa_viva.mesa_do_estado(state, {})
    conectados = [c for c in state["controllers"] if c.get("connected")]
    return Contexto(state=state, mesa=mesa, conectados=conectados, estados={})


@pytest.fixture(autouse=True)
def _a_pagina_publicada_tem_a_mira(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Calibrar publicada ainda não tem o bloco novo; a bancada tem (o publicar é da costura)"""
    monkeypatch.setattr(a11_calibrar_sensores, "_TEM_A_MIRA", True)


def _gestos_para_o_p3(servidor: IpcServer, uniq: str = _P3, *, anda: int = 9, tremor: int = 7,
                      segurar: str = "l2",
                      inverter: tuple[str, ...] = ("lado",)) -> _PonteDoServidor:
    """Os quatro gestos da Calibrar, chamados como o clique chama, sobre o `mira.set` real."""
    ponte = _PonteDoServidor(servidor)
    ctx = _ctx(_estado(servidor))
    a11_calibrar_sensores.mira_sensibilidade(ctx, {"uniq": uniq, "valor": str(anda)}, ponte)
    a11_calibrar_sensores.mira_tremor(ctx, {"uniq": uniq, "valor": str(tremor)}, ponte)
    a11_calibrar_sensores.mira_segurar(ctx, {"uniq": uniq, "valor": segurar}, ponte)
    for lado in inverter:
        ctx = _ctx(_estado(servidor))
        a11_calibrar_sensores.mira_inverter(ctx, {"uniq": uniq, "inverter": lado}, ponte)
    return ponte


# O QUE CADA ABA DIZ, lido pelo pacote dela sobre o MESMO contexto.

def _lado_a_lado(ctx: Contexto, uniq: str) -> dict[str, Any]:
    pref = next(m["pref"] for m in ctx.mesa if m["uniq"] == uniq)
    cal = (pacote_da_pagina(a11_calibrar_sensores.PAGINA, ctx) or {})["colunas"][pref]
    nav = (a06_navegacao.pacote(ctx))["colunas"][uniq]
    con = (a08_conexoes.pacote(ctx))["colunas"][uniq]
    return {"calibrar": cal, "navegacao": nav, "conexões": con}


def _a_perfis(ctx: Contexto, uniq: str) -> str:
    """A dica da célula dos «comandos virtuais» deste controle na coluna Status da 10."""
    a10_perfis._ESCOLHIDO = ""  # type: ignore[attr-defined]
    fora = a10_perfis.pacote(ctx)
    largura = len(a10_perfis.SECOES_DA_COLUNA)
    linhas = list(zip(*[iter(fora["guarda.dica"])] * largura, strict=False))
    posicao = [m["uniq"] for m in ctx.mesa].index(uniq)
    return str(linhas[posicao][a10_perfis.SECOES_DA_COLUNA.index("movimento")])


def _curto(anda: int, tremor: int, segurar: str) -> str:
    return " • ".join([str(anda), f"{tremor} {calibrar.UNIDADE_DO_TREMOR}", segurar])


def _inteiro(anda: int, tremor: int, segurar: str, lados: tuple[str, ...] = ()) -> str:
    partes = [f"{calibrar.ROTULO_SENSIBILIDADE}: {anda}",
              f"{calibrar.ROTULO_TREMOR}: {tremor} {calibrar.UNIDADE_DO_TREMOR}",
              f"{calibrar.ROTULO_SEGURAR}: {segurar}"]
    if lados:
        partes.append(f"{calibrar.ROTULO_INVERTER}: {', '.join(lados)}")
    return " • ".join(partes)


def _confere_as_quatro(ctx: Contexto, uniq: str, anda: int, tremor: int, segurar: str,
                       lados: tuple[str, ...] = (), gatilho: str | None = None,
                       *, acesa: bool = True) -> None:
    lido = _lado_a_lado(ctx, uniq)
    cal = lido["calibrar"]
    assert cal["mira-sensibilidade-num"] == str(anda), cal
    assert cal["mira-tremor-num"] == str(tremor), cal
    assert cal["mira-segurar"] == (gatilho or calibrar.SEMPRE), cal
    inteiro = _inteiro(anda, tremor, segurar, lados)
    # a Navegação só diz a linha com o chip aceso: apagado, os números existem (os três outros
    # os dizem) mas a Mira não anda, e afirmá-la seria chute
    assert lido["navegacao"]["mira-resumo"] == (_curto(anda, tremor, segurar) if acesa else "")
    assert lido["navegacao"]["mira-resumo-dica"] == (inteiro if acesa else "")
    assert f'title="{inteiro}"' in lido["conexões"]["est-mira"], lido["conexões"]["est-mira"]
    assert _a_perfis(ctx, uniq) == inteiro


@pytest.mark.parametrize("transportes", [("usb",) * 4, ("bt",) * 4, ("usb", "bt", "bt", "usb")])
def test_mudar_na_calibrar_e_ler_nas_outras_tres(
        perfis: Path, tmp_path: Path, transportes: tuple[str, ...]) -> None:  # noqa: F811
    """Réguas 1 e 3. Os quatro gestos para o P3: as quatro abas dizem 9, 7, L2 e o inverter, e
    os outros três ficam como estavam (a mira de nascença). MORDIDAS: a 06 ler a mira do perfil;
    a 08 casar a entrada pela posição (as entradas chegam em outra ordem que a mesa)."""
    servidor = _servidor_com_perfil(tmp_path)
    for uniq in UNIQS:
        _mira_set(servidor, uniq=uniq, ligada=True)
    _gestos_para_o_p3(servidor)
    ctx = _ctx(_estado(servidor, transportes))
    _confere_as_quatro(ctx, _P3, 9, 7, "L2", ("esquerda e direita",), gatilho="l2")
    for outro in (_P1, _P2, _P4):
        _confere_as_quatro(ctx, outro, calibrar.SENSIBILIDADE[2], calibrar.TREMOR[2],
                           calibrar.ROTULO_SEMPRE)


def test_cada_um_dos_quatro_lugares_diz_o_proprio(perfis: Path, tmp_path: Path) -> None:  # noqa: F811
    """Réguas 1 e 3. O gesto feito uma vez em CADA lugar, com números diferentes: nenhum
    controle diz o do vizinho. MORDIDA: casar a 08 pela posição."""
    servidor = _servidor_com_perfil(tmp_path)
    por_lugar = {_P1: (2, 11), _P2: (4, 13), _P3: (9, 7), _P4: (12, 40)}
    for uniq, (anda, tremor) in por_lugar.items():
        _mira_set(servidor, uniq=uniq, ligada=True)
        _gestos_para_o_p3(servidor, uniq, anda=anda, tremor=tremor, segurar=calibrar.SEMPRE,
                          inverter=())
    ctx = _ctx(_estado(servidor))
    for uniq, (anda, tremor) in por_lugar.items():
        _confere_as_quatro(ctx, uniq, anda, tremor, calibrar.ROTULO_SEMPRE)


def test_mudar_de_novo_chega_no_tique_seguinte_sem_reabrir(perfis: Path, tmp_path: Path) -> None:  # noqa: F811
    """Régua 2. Um segundo `mira.set` e um segundo tique: as quatro abas dizem 3.
    MORDIDA: um `lru_cache` no `resumo_da_mira` guarda o primeiro número."""
    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P3, ligada=True)
    _gestos_para_o_p3(servidor, inverter=())
    _confere_as_quatro(_ctx(_estado(servidor)), _P3, 9, 7, "L2", gatilho="l2")
    _mira_set(servidor, uniq=_P3, sensibilidade=3)
    _confere_as_quatro(_ctx(_estado(servidor)), _P3, 3, 7, "L2", gatilho="l2")


def test_o_chip_apagado_nao_afirma_a_mira_nas_outras_abas(perfis: Path, tmp_path: Path) -> None:  # noqa: F811
    """O número existe com o chip apagado (a Calibrar o mostra), mas a Navegação não diz a linha
    e a 08 diz «Apagado»: nenhuma aba afirma uma Mira que não anda."""
    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P3, ligada=False, sensibilidade=9)
    ctx = _ctx(_estado(servidor))
    lido = _lado_a_lado(ctx, _P3)
    assert lido["calibrar"]["mira-sensibilidade-num"] == "9"
    assert lido["navegacao"]["mira-resumo"] == ""
    assert "Apagado" in lido["conexões"]["est-mira"]
    assert "✓" not in lido["conexões"]["est-mira"]


def test_no_nativo_os_numeros_gravam_e_as_abas_dizem_o_chip_cinza(
        perfis: Path, tmp_path: Path) -> None:  # noqa: F811
    """Régua 4. No Nativo o `mira.set` grava os ajustes, a Calibrar mostra os números, a 08 diz a
    frase do chip cinza e a 06 não mostra a linha. MORDIDA: o selo da 08 afirmar «✓» no Nativo."""
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P3, ligada=True)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P3, sensibilidade=8)
    assert corpo["gravado"] is True
    ctx = _ctx(_estado(servidor, nativo=True))
    lido = _lado_a_lado(ctx, _P3)
    assert lido["calibrar"]["mira-sensibilidade-num"] == "8"
    assert lido["navegacao"]["mira-resumo"] == ""
    assert "✓" not in lido["conexões"]["est-mira"]
    assert "Nativo" in lido["conexões"]["est-mira"]
    assert a02_controles.MIRA_CINZA_NO_NATIVO in lido["conexões"]["est-mira"]


def _enderecos(pagina: str) -> set[str]:
    doc = (RAIZ / "mockup" / pagina).read_text(encoding="utf-8")
    return set(re.findall(r'data-(?:campo|hef)="([^"]+)"', doc))


def test_o_endereco_existe_dos_dois_lados(perfis: Path, tmp_path: Path) -> None:  # noqa: F811
    """Régua 5. Todo endereço novo que um pacote emite existe na bancada da página dele, e o
    inverso. MORDIDA: tirar o endereço do cartão da 06 do gerador."""
    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P3, ligada=True)
    ctx = _ctx(_estado(servidor))
    lido = _lado_a_lado(ctx, _P3)
    novos = {"06-navegacao.html": set(a06_navegacao.MIRA_VAZIA),
             "08-conexoes.html": {"est-mira"},
             "calibrar-sensores.html": {"perfil", "mira-sensibilidade-num", "mira-tremor-num"},
             "10-perfis.html": {"guarda.dica"}}
    for pagina, campos in novos.items():
        faltam = campos - _enderecos(pagina)
        assert not faltam, f"{pagina}: o pacote emite e a página não tem onde pintar: {faltam}"
    assert set(a06_navegacao.MIRA_VAZIA) <= set(lido["navegacao"])
    assert "est-mira" in lido["conexões"]


def _grava_perfil(nome: str, **sensibilidade_por_peca: int) -> Profile:
    """Um perfil no disco com a Mira acesa nas peças pedidas, cada uma com o seu «anda»."""
    perfil_novo = Profile(
        name=nome, match=MatchAny(type="any"),
        controllers={CHAVE[u]: ControllerOverrides(movimento=ProfileMovimentoConfig(
            destino="analogico_direito", sensibilidade=n))
            for u, n in ((_P3, sensibilidade_por_peca.get("p3")),
                         (_P4, sensibilidade_por_peca.get("p4"))) if n is not None})
    save_profile(perfil_novo)
    return perfil_novo


def _troca_para(servidor: IpcServer, nome: str) -> None:
    corpo = asyncio.run(servidor._handlers["profile.switch"]({"name": nome}))
    assert corpo.get("status", "ok") == "ok", corpo


def test_trocar_de_perfil_troca_os_numeros_nas_quatro(perfis: Path, tmp_path: Path) -> None:  # noqa: F811
    """Régua 6. Dois perfis no disco: o A com o P3 em 9, e o B com o P3 em 4 e o P4 em 11. O
    `profile.switch` para o B, um tique, e as quatro abas dizem 4 e 11; de volta ao A, dizem 9 e
    o P4 volta ao que o A diz dele (nada: Mira apagada, número de nascença). MORDIDA: um
    `definir_da_peca` por cima do mapa velho no lugar do `definir_por_peca` — o P4 do perfil B
    sobrevive à volta ao A."""
    servidor = _servidor_com_perfil(tmp_path)
    _grava_perfil("Perfil A", p3=9)
    _grava_perfil("Perfil B", p3=4, p4=11)
    tremor, anda0, sempre = calibrar.TREMOR[2], calibrar.SENSIBILIDADE[2], calibrar.ROTULO_SEMPRE
    for nome, p3, p4 in (("Perfil B", 4, 11), ("Perfil A", 9, None), ("Perfil B", 4, 11)):
        _troca_para(servidor, nome)
        ctx = _ctx(_estado(servidor))
        assert perfil.nome_do_ativo(ctx.state) == nome
        _confere_as_quatro(ctx, _P3, p3, tremor, sempre)
        _confere_as_quatro(ctx, _P4, p4 or anda0, tremor, sempre, acesa=p4 is not None)


def test_o_nome_do_perfil_na_calibrar_e_o_perfil_que_gravou(
        perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """Régua 7. O nome que o chip da Calibrar pinta (`pacotes.topo`, o dono do «Perfil ativo») é o
    `perfil` que o `mira.set` devolveu, e o `load_profile` desse nome, lido do disco, tem o 9 no P3.
    Com o daemon calado sobre o perfil e o marcador em disco valendo, o nome é o do marcador.
    MORDIDA: o `topo` ler o `state["active_profile"]` cru pinta o travessão enquanto o `mira.set`
    grava no perfil do marcador."""
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.utils import session

    servidor = _servidor_com_perfil(tmp_path)
    ponte = _PonteDoServidor(servidor)
    ctx = _ctx(_estado(servidor))
    a11_calibrar_sensores.mira_sensibilidade(ctx, {"uniq": _P3, "valor": "9"}, ponte)
    gravou_em = ponte.respostas[-1]["perfil"]
    assert gravou_em == "Bancada"
    assert pacotes.topo(ctx)["perfil"] == gravou_em
    assert load_profile(gravou_em).controllers[CHAVE[_P3]].movimento.sensibilidade == 9

    servidor.store.set_active_profile(None)
    monkeypatch.setattr(session, "resolve_boot_profile", lambda: "Bancada")
    calado = _ctx(_estado(servidor))
    assert calado.state["active_profile"] is None
    a11_calibrar_sensores.mira_sensibilidade(calado, {"uniq": _P3, "valor": "5"}, ponte)
    gravou_em = ponte.respostas[-1]["perfil"]
    assert gravou_em == "Bancada", "o marcador valia e o `mira.set` não gravou nele"
    assert pacotes.topo(calado)["perfil"] == gravou_em, (
        "o chip da Calibrar não diz o perfil em que a Mira acabou de gravar")
    assert load_profile(gravou_em).controllers[CHAVE[_P3]].movimento.sensibilidade == 5


def test_a_cena_dos_geradores_diz_o_mesmo_que_o_produto() -> None:
    """A cena (06, 08 e 10) escreve o bloco de nascença da Calibrar: o número vem de
    `calibrar.SENSIBILIDADE` e `calibrar.TREMOR`, e não digitado num gerador."""
    bloco = a11_calibrar_sensores.bloco_de_nascenca()
    assert bloco["sensibilidade"] == calibrar.SENSIBILIDADE[2]
    assert bloco["zona_morta_graus_s"] == calibrar.TREMOR[2]
    assert a11_calibrar_sensores.resumo_da_mira({}) is None
    assert a11_calibrar_sensores.resumo_da_mira({"ligada": True}) is None
    assert rot.DESTINO_NENHUM  # o dono do «apagado» existe e é o que a 02 lê


def test_a_linha_da_06_com_a_mira_apagada_fica_vazia_e_nao_com_travessao() -> None:
    """A Mira apagada é estado lido, e o cartão da 06 não diz «—» por ela.

    O piloto escreve `—` num `texto` vazio (`hefesto_vivo.escrever`) e escreve vazio num `html`
    vazio; o pacote emite `""` com a Mira apagada, e só o alvo `html` deixa a linha vazia na tela.
    MORDIDA: o `data-hef-alvo="texto"` de volta no `mira-resumo` do gerador da 06.
    """
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("06-navegacao.html", publicado=False).read_text(encoding="utf-8")
    alvos = re.findall(r'data-campo="mira-resumo" data-hef-alvo="([a-z]+)">([^<]*)<', html)
    assert len(alvos) == 4, alvos
    assert {a for a, _ in alvos} == {"html"}, alvos
    assert sorted(t for _, t in alvos)[:3] == ["", "", ""], alvos
