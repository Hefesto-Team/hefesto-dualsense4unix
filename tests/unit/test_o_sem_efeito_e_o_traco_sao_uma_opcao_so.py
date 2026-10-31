"""O «—» e o nome velho do nenhum efeito são uma opção só.

Sprint O-SEM-EFEITO-E-O-TRACO-SAO-UMA-OPCAO-SO-01.

Medido em 31/10/2026: a lista do gatilho tinha o «—» escondido e desligado (o lugar vazio) ao lado
do nenhum efeito com outro nome, e o WebKitGTK mostra os dois no menu; a luz e a vibração tinham o
mesmo nenhum efeito com valores diferentes (`nenhum`, `sem-efeito`, `sem_efeito`). Hoje um dono só,
`profiles/sem_efeito.py`, dá o valor, o rótulo e a `<option>` às quatro listas (Gatilhos,
Iluminação, Efeito háptico e Padrão dos motores), e o nome velho que chega de página de antes se lê
uma vez, no clique.

MORDIDAS:

* devolva o rótulo antigo em `sem_efeito.ROTULO` → `test_toda_lista_de_efeito_tem_um_traco_so`
  reprova nas três abas; escrito à mão num gerador, `test_o_nome_velho_nao_volta_ao_codigo_da_tela`;
* devolva o «—» escondido à lista do gatilho → `test_nenhuma_lista_de_efeito_esconde_opcao`;
* tire `"sem-efeito"` de `NOMES_VELHOS` → `test_a_luz_le_o_nome_velho_e_apaga_a_barra` e a vibração.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos as a03
from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05
from hefesto_dualsense4unix.profiles import formas_de_haptica, sem_efeito
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
MOCKUP = RAIZ / "mockup"
UNIQ = "aa:bb:cc:00:00:01"
NOME_VELHO = "Sem" + " efeito"

LISTAS = (
    ("03-gatilhos.html", "g2-imersao", 8),
    ("04-iluminacao.html", "g4-efeito", 4),
    ("05-vibracao.html", "vib-efeito", 8),
)
_SELECT = re.compile(r"<select\b(?P<attrs>[^>]*)>(?P<dentro>.*?)</select>", re.S)
_OPCAO = re.compile(r"<option\b(?P<attrs>[^>]*)>(?P<texto>[^<]*)</option>")


def _listas(arquivo: str, classe: str) -> list[str]:
    doc = (MOCKUP / arquivo).read_text(encoding="utf-8")
    return [m.group("dentro") for m in _SELECT.finditer(doc)
            if re.search(rf'class="[^"]*\b{classe}\b', m.group("attrs"))]


@pytest.mark.parametrize("arquivo,classe,quantas", LISTAS)
def test_toda_lista_de_efeito_tem_um_traco_so(arquivo: str, classe: str, quantas: int) -> None:
    listas = _listas(arquivo, classe)
    assert len(listas) == quantas, (arquivo, len(listas))
    for dentro in listas:
        opcoes = [(m.group("attrs"), m.group("texto").strip()) for m in _OPCAO.finditer(dentro)]
        tracos = [a for a, t in opcoes if t == sem_efeito.ROTULO]
        assert len(tracos) == 1, (arquivo, [t for _a, t in opcoes][:4])
        assert f'value="{sem_efeito.VALOR}"' in tracos[0], (arquivo, tracos[0])
        assert NOME_VELHO not in [t for _a, t in opcoes], arquivo
        valores = re.findall(r'value="([^"]*)"', dentro)
        assert not set(valores) & (sem_efeito.NOMES_VELHOS - {sem_efeito.VALOR}), (arquivo, valores)


@pytest.mark.parametrize("arquivo,classe,quantas", LISTAS)
def test_nenhuma_lista_de_efeito_esconde_opcao(arquivo: str, classe: str, quantas: int) -> None:
    """O WebKitGTK mostra no menu a opção `hidden` ou `disabled`: escondida, sai duplicada."""
    for dentro in _listas(arquivo, classe):
        for m in _OPCAO.finditer(dentro):
            assert not re.search(r"\b(hidden|disabled)\b", m.group("attrs")), (arquivo, m.group(0))


def test_os_geradores_montam_a_opcao_do_mesmo_dono() -> None:
    assert sem_efeito.opcao() in a03.html_das_opcoes_de_imersao().replace(
        f' title="{a03.DICA_DO_SEM_IMERSAO}"', "")
    assert a03.SEM_IMERSAO == a04.SEM_EFEITO == sem_efeito.VALOR
    assert formas_de_haptica.SEM_EFEITO == padroes_de_vibracao.SEM_EFEITO == sem_efeito.VALOR
    assert formas_de_haptica.ROTULOS[sem_efeito.VALOR] == sem_efeito.ROTULO
    assert a03.ROTULO_DO_SEM_IMERSAO == a04.rotulo_da_opcao(a04.SEM_EFEITO) == sem_efeito.ROTULO


def test_o_nome_velho_nao_volta_ao_codigo_da_tela() -> None:
    caminhos = [*(SRC / "interface").glob("aba*.py"),
                *(SRC / "interface" / "pacotes").glob("a0*.py"),
                SRC / "profiles" / "formas_de_haptica.py",
                SRC / "daemon" / "subsystems" / "padroes_de_vibracao.py"]
    assert len(caminhos) > 10
    com = [c.relative_to(RAIZ).as_posix() for c in caminhos
           if NOME_VELHO in c.read_text(encoding="utf-8")]
    assert com == [], com


@pytest.mark.parametrize("velho", sorted(sem_efeito.NOMES_VELHOS | {sem_efeito.VALOR}))
def test_o_nome_velho_se_le_uma_vez(velho: str) -> None:
    assert sem_efeito.do_clique(velho) == sem_efeito.VALOR
    assert sem_efeito.do_clique(f" {velho} ") == sem_efeito.VALOR
    assert sem_efeito.e_sem_efeito(velho)


@pytest.mark.parametrize("outro", ["", "do_estilo", "luz-fixa", "golpe-leve", None, 3])
def test_o_resto_passa_como_veio(outro: Any) -> None:
    assert sem_efeito.do_clique(outro) == outro
    assert not sem_efeito.e_sem_efeito(outro)


class _PonteDoGatilho:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def trigger_set_detalhado(self, *_a: Any, **_k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append("set")
        return True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}

    def trigger_reset_detalhado(self, *_a: Any, **_k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append("reset")
        return True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}


def _ctx_do_gatilho() -> Any:
    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
             "cor": "starlight-blue", "mascara": "DualSense"}]
    falso = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
             "inputs": {"l2_raw": 0, "r2_raw": 0}}
    return pacotes.Contexto(state={"active_profile": ""}, mesa=mesa, conectados=[falso], estados={})


@pytest.mark.parametrize("valor", ["nenhum", "—", NOME_VELHO, sem_efeito.VALOR])
def test_o_gatilho_le_o_nome_velho_e_solta(valor: str, tmp_path: pathlib.Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ponte = _PonteDoGatilho()
    a03.imersao_escolhida(_ctx_do_gatilho(), {"uniq": UNIQ, "lado": "d", "valor": valor}, ponte)
    assert ponte.chamadas == ["reset"], (valor, ponte.chamadas)


@pytest.mark.parametrize("valor", ["sem-efeito", NOME_VELHO, sem_efeito.VALOR])
def test_a_luz_le_o_nome_velho_e_apaga_a_barra(valor: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador

    gravado: list[Any] = []
    escrito: list[tuple[Any, ...]] = []
    monkeypatch.setattr(a04, "_nao_no_automatico", lambda _ctx: None)
    monkeypatch.setattr(a04.perfil, "nome_do_ativo", lambda _s: "")
    monkeypatch.setattr(a04.perfil, "_com_o_src", lambda: None)
    monkeypatch.setattr(a04.perfil, "ativo_que_vale", lambda _n: {})
    monkeypatch.setattr(o_padrao_do_computador, "gravar_pelo_gesto",
                        lambda *a, **k: gravado.append((a, k)) or ("", None))
    monkeypatch.setattr(a04, "_escrever_a_cor",
                        lambda _ctx, _p, uniq, cor, **k: escrito.append((uniq, cor, k)))
    a04.efeito_da_luz(_ctx_do_gatilho(), {"uniq": UNIQ, "valor": valor}, object())
    assert len(gravado) == 1
    assert escrito == [(UNIQ, (0, 0, 0), {"apagando": True, "brilho": 0.0})], (valor, escrito)


class _PonteDaVibracao:
    def __init__(self) -> None:
        self.gravados: list[dict[str, Any]] = []

    def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, Any]]:
        self.gravados.append(k)
        return True, {"status": "ok"}

    def haptica_testar(self, _uniq: str, _ligado: bool) -> tuple[bool, dict[str, Any]]:
        return True, {"status": "ok"}

    def __getattr__(self, nome: str) -> Any:
        return lambda *a, **k: (True, None) if nome.endswith("_checked") else True


@pytest.mark.parametrize("gesto", [a05.GESTO_DO_EFEITO_IMERSAO, a05.GESTO_DO_EFEITO_HAPTICO])
@pytest.mark.parametrize("valor", ["nenhum", "sem-efeito", NOME_VELHO, sem_efeito.VALOR])
def test_a_vibracao_le_o_nome_velho_e_grava_o_de_hoje(gesto: str, valor: str,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a05, "_segurar", lambda _s: None)
    monkeypatch.setattr(a05, "_perfil_ativo", lambda _ctx: {})
    feito = pacotes.gesto_da_pagina("05-vibracao.html", gesto)
    assert feito is not None
    ponte = _PonteDaVibracao()
    try:
        feito(_ctx_do_gatilho(), {"uniq": UNIQ, "valor": valor}, ponte)
    finally:
        a05.parar_o_teste()
        a05.parar_o_teste_da_haptica()
    assert len(ponte.gravados) == 1
    assert sem_efeito.VALOR in ponte.gravados[0].values(), ponte.gravados
