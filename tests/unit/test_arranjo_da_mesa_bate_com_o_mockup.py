"""A prova de que o porte não mudou o cálculo."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from tests.unit import mesa_do_mockup as mock

RAIZ = Path(__file__).resolve().parents[2]
ORACULO = RAIZ / "tests" / "fixtures" / "motor_do_arranjo_do_mockup.js"
OURO = RAIZ / "tests" / "fixtures" / "motor_do_arranjo_do_mockup.json"

OPCOES = {v.id: v.opcoes for v in motor.VARIANTES}


def _mesa(**kw: Any) -> motor.Mesa:
    """A mesa com as faces da página viva: o ouro vem do `EXEMPLO` dela."""
    return mock.mesa(faces=mock.FACES_DA_PAGINA_VIVA, **kw)


def _mesa_sem_hub() -> motor.Mesa:
    return mock.mesa_sem_hub(faces=mock.FACES_DA_PAGINA_VIVA)


def _js(v: object) -> str:
    """A chave do cenário como o JavaScript a escreveu: ``null``, não ``None``."""
    return "null" if v is None else str(v)


PAGINA_VIVA = RAIZ / "mockup" / "mapa-das-portas.html"

#: O que o porte em Python ainda diz diferente da página viva, medido em 23/10/2026: a caixa alta
#: dos vereditos («Ocupada», «Vale evitar»), o título «Bluetooth → Entrada 13» da receita e duas
#: frases que a página monta «entrada » + número à mão. A cura é a sprint
#: `O-PORTE-E-A-PAGINA-DO-ARRANJO-DIZEM-O-MESMO-TEXTO-01`. O xfail é estrito: no dia em que o
#: texto bater, o teste reprova e a marca sai daqui, em vez de mentir que ainda diverge.
_DIVERGE = pytest.mark.xfail(
    strict=True,
    reason="o texto do porte diverge da página viva: sprint "
           "O-PORTE-E-A-PAGINA-DO-ARRANJO-DIZEM-O-MESMO-TEXTO-01",
)

#: Os únicos julgamentos cujo texto o porte já diz igual à página viva (sem aparelho na mão).
JULGAMENTOS_QUE_JA_BATEM = {(None, n) for n in ("2", "3", "7", "10", "13")}


def ouro(chave: str) -> Any:
    """O que o mockup respondeu neste cenário, com ``Infinity`` de volta."""
    dados = json.loads(OURO.read_text(encoding="utf-8"))
    assert chave in dados, f"cenário ausente no oráculo: {chave}"
    return _numeros(dados[chave])


def _numeros(v: Any) -> Any:
    if v == "Infinity":
        return math.inf
    if v == "-Infinity":
        return -math.inf
    if isinstance(v, list):
        return [_numeros(x) for x in v]
    if isinstance(v, dict):
        return {k: _numeros(x) for k, x in v.items()}
    return v


def _razoes(razoes: tuple[motor.Razao, ...]) -> list[dict[str, str]]:
    return [{"selo": r.selo, "txt": r.texto} for r in razoes]


def _motivo(m: motor.Motivo) -> dict[str, Any]:
    return {"razoes": _razoes(m.razoes), "peso": m.peso, "ganho": m.ganho,
            "forcado": m.forcado, "essencial": m.essencial}


def como_o_mockup_planeja(p: motor.Plano) -> dict[str, Any]:
    return {"plano": dict(p.plano), "motivo": {k: _motivo(v) for k, v in p.motivo.items()}}


def como_o_mockup_receita(movs: list[motor.Movimento]) -> list[dict[str, Any]]:
    return [{"titulo": m.titulo,
             "linhas": [{"s": ln.selo, "t": ln.texto} for ln in m.linhas],
             "essencial": m.essencial, "ganho": m.ganho, "semNumero": m.sem_numero}
            for m in movs]


def _receita_do_ouro(chave: str) -> list[dict[str, Any]]:
    return [{"titulo": m["titulo"],
             "linhas": [{"s": ln["s"], "t": ln["t"]} for ln in m["linhas"]],
             "essencial": bool(m.get("essencial", False)),
             "ganho": m.get("ganho", 0), "semNumero": bool(m.get("semNumero", False))}
            for m in ouro(chave)]


def _veredito(v: motor.Veredito | None) -> dict[str, str] | None:
    return None if v is None else {"v": v.v, "txt": v.texto, "porque": v.porque}


def _controles(p: motor.PlanoDosControles) -> dict[str, Any]:
    return {"ads": [{"id": a.id, "entrada": a.entrada, "rotulo": a.rotulo}
                    for a in p.adaptadores],
            "carga": dict(p.carga), "destino": dict(p.destino),
            "cabe": p.cabe, "sobra": p.sobra}


def _plano_dos_controles(mesa: motor.Mesa, quantos: int = 4,
                         controles: tuple[motor.Controle, ...] | None = None) -> dict[str, Any]:
    vivos = (mock.CONTROLES if controles is None else controles)[:quantos]
    return _controles(motor.plano_dos_controles(vivos, motor.adaptadores_da_mesa(mesa)))


@pytest.mark.skipif(shutil.which("node") is None, reason="node não está nesta máquina")
def test_o_ouro_ainda_e_o_que_o_mockup_diz_hoje() -> None:
    """O JSON gravado é o que a página viva do mapa produz HOJE — não uma cópia velha."""
    saida = subprocess.run(
        [shutil.which("node") or "node", str(ORACULO)],
        capture_output=True, text=True, check=True, cwd=RAIZ, timeout=120,
    )
    assert json.loads(saida.stdout) == json.loads(OURO.read_text(encoding="utf-8"))


def test_a_alocacao_derivada_e_a_mesma() -> None:
    """A prova da D-2110-O-MOTOR-DIZ-A-ENTRADA-PELO-DONO."""
    assert motor.alocacao(mock.MAPA, mock.LEITURA_AGORA) == ouro("alocacao/agora")
    assert motor.alocacao(mock.MAPA, mock.LEITURA_ANTES) == ouro("alocacao/antes")


def test_o_mapa_vazio_e_o_mapa_com_entrada_que_nao_existe() -> None:
    assert motor.alocacao({}, mock.LEITURA_AGORA) == ouro("mapa-vazio/alocacao")
    assert motor.alocacao({"99": "9-9"}, mock.LEITURA_AGORA) == ouro("mapa-inexistente/alocacao")


@pytest.mark.parametrize(
    "caminho",
    ["3-1.2", "3-1.1.1", "4-1.1.2", "4-2", "1-3", "1-6", "1-4", "3-1", None],
)
def test_a_regiao_sai_do_barramento(caminho: str | None) -> None:
    mesa = _mesa()
    esperado = ouro(f"regiao/{_js(caminho)}")
    assert motor.regiao_do_caminho(caminho, motor.caminho_do_hub(mesa)) == esperado


def test_quem_o_mapa_nao_conhece_ainda_diz_de_que_lado_esta() -> None:
    achado = [{"id": s.aparelho.id, "caminho": s.caminho, "regiao": s.regiao}
              for s in motor.sem_entrada(_mesa())]
    assert achado == ouro("semEntrada/agora")
    antes = [{"id": s.aparelho.id, "caminho": s.caminho, "regiao": s.regiao}
             for s in motor.sem_entrada(_mesa(leitura=mock.LEITURA_ANTES))]
    assert antes == ouro("semEntrada/antes")


def test_as_candidatas_saem_de_dezesseis_para_quatro() -> None:
    mesa = _mesa()
    assert [e.n for e in motor.candidatas(mesa, "pc")] == ouro("candidatas/pc")
    assert [e.n for e in motor.candidatas(mesa, "hub")] == ouro("candidatas/hub")
    assert [e.n for e in motor.todas_as_entradas(mesa.faces)] == ouro("todasPortas")


@pytest.mark.parametrize("variante", [
    "melhor", "poucos",
    pytest.param("sem-ext", marks=_DIVERGE), pytest.param("so-pc", marks=_DIVERGE)])
def test_o_plano_e_o_mesmo_do_javascript(variante: str) -> None:
    plano = motor.planejar(_mesa(), OPCOES[variante])
    assert como_o_mockup_planeja(plano) == ouro(f"planejar/{variante}")


@_DIVERGE
@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext", "so-pc"])
def test_a_receita_e_a_mesma_do_javascript(variante: str) -> None:
    movs = motor.receita(_mesa(), OPCOES[variante])
    assert como_o_mockup_receita(movs) == _receita_do_ouro(f"receita/{variante}")


@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext", "so-pc"])
def test_o_que_se_perde_e_a_mesma_frase(variante: str) -> None:
    assert motor.consequencias(_mesa(), OPCOES[variante]) == ouro(f"consequencias/{variante}")
    assert motor.qualidade(_mesa(), OPCOES[variante]) == ouro(f"qualidade/{variante}")


@_DIVERGE
def test_a_receita_sem_o_bonus_de_ficar_parado_bate_tambem() -> None:
    """A regra é PARÂMETRO, e o porte tem de reproduzir os dois valores dela."""
    op = motor.Opcoes(bonus_parado=0)
    plano = como_o_mockup_planeja(motor.planejar(_mesa(), op))
    assert plano == ouro("planejar/sem-bonus-parado")
    assert como_o_mockup_receita(motor.receita(_mesa(), op)) == _receita_do_ouro(
        "receita/sem-bonus-parado")


@_DIVERGE
def test_a_receita_do_mapa_vazio_e_do_mapa_torto() -> None:
    vazio = _mesa(mapa={})
    assert como_o_mockup_planeja(motor.planejar(vazio)) == ouro("mapa-vazio/planejar")
    assert como_o_mockup_receita(motor.receita(vazio)) == _receita_do_ouro("mapa-vazio/receita")
    assert [e.n for e in motor.candidatas(vazio, "pc")] == ouro("mapa-vazio/candidatas-pc")
    torto = _mesa(mapa={"99": "9-9"})
    assert como_o_mockup_receita(motor.receita(torto)) == _receita_do_ouro(
        "mapa-inexistente/receita")


@pytest.mark.parametrize("n, na_mao", [
    pytest.param(n, na_mao, id=f"{na_mao}-{n}",
                 marks=() if (na_mao, n) in JULGAMENTOS_QUE_JA_BATEM else (_DIVERGE,))
    for na_mao in ("bt", "wifi", "teclado", "mouse", "webcam", None)
    for n in ("1", "2", "3", "7", "9", "10", "13", "15", "15a")])
def test_o_julgamento_de_cada_entrada_e_o_mesmo(n: str, na_mao: str | None) -> None:
    mesa = _mesa()
    entrada = motor.por_num(mesa.faces, n)
    assert entrada is not None
    assert _veredito(motor.julgar(entrada, na_mao, mesa)) == ouro(f"julgar/{n}/{_js(na_mao)}")


@_DIVERGE
@pytest.mark.parametrize("n", ["1", "2", "10", "15a"])
def test_segurando_um_dongle_do_hub_a_outra_regiao_se_recusa(n: str) -> None:
    mesa = _mesa()
    entrada = motor.por_num(mesa.faces, n)
    assert entrada is not None
    veredito = motor.julgar(entrada, "bt", mesa, segurando="bt-c")
    assert _veredito(veredito) == ouro(f"julgar-segurando/bt-c/{n}")


def test_o_reexame_reconhece_quem_mudou_de_lugar() -> None:
    mudou = motor.reexame(_mesa(), mock.LEITURA_ANTES, mock.LEITURA_AGORA)
    achado = [{"id": m.aparelho.id, "antes": m.antes, "agora": m.agora,
               "entradaAntes": m.entrada_antes, "entradaAgora": m.entrada_agora}
              for m in mudou]
    assert achado == ouro("reexame/antes-agora")
    assert motor.reexame(_mesa(), mock.LEITURA_AGORA, mock.LEITURA_AGORA) == []


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_a_distribuicao_dos_controles_e_a_mesma(quantos: int) -> None:
    assert _plano_dos_controles(_mesa(), quantos) == ouro(f"controles/quantos={quantos}")


def test_o_microfone_e_o_unico_que_muda_a_conta() -> None:
    sem_mic = tuple(motor.Controle(c.nome, mic=False, onde=c.onde) for c in mock.CONTROLES)
    assert _plano_dos_controles(_mesa(), 4, sem_mic) == ouro("controles/sem-mic")


def test_os_quatro_no_mesmo_dongle_e_o_adaptador_que_sumiu() -> None:
    juntos = tuple(motor.Controle(c.nome, c.mic, onde="bt-a") for c in mock.CONTROLES)
    assert _plano_dos_controles(_mesa(), 4, juntos) == ouro("controles/todos-no-bt-a")
    orfaos = tuple(motor.Controle(c.nome, c.mic, onde="sumiu") for c in mock.CONTROLES)
    assert _plano_dos_controles(_mesa(), 4, orfaos) == ouro("controles/adaptador-sumiu")


@_DIVERGE
def test_sem_o_hub_o_motor_responde_e_nao_inventa() -> None:
    mesa = _mesa_sem_hub()
    assert motor.alocacao(mesa.mapa, mesa.leitura) == ouro("sem-hub/alocacao")
    assert motor.caminho_do_hub(mesa) is None
    assert motor.regiao_do_caminho("1-3", motor.caminho_do_hub(mesa)) == ouro("sem-hub/regiao-1-3")
    assert motor.regiao_do_caminho("4-4", motor.caminho_do_hub(mesa)) == ouro("sem-hub/regiao-4-4")
    achado = [{"id": s.aparelho.id, "caminho": s.caminho, "regiao": s.regiao}
              for s in motor.sem_entrada(mesa)]
    assert achado == ouro("sem-hub/semEntrada")
    assert como_o_mockup_planeja(motor.planejar(mesa)) == ouro("sem-hub/planejar")
    assert como_o_mockup_receita(motor.receita(mesa)) == _receita_do_ouro("sem-hub/receita")
    assert motor.consequencias(mesa) == ouro("sem-hub/consequencias")


def test_sem_adaptador_nenhum_controle_cabe_e_o_motor_diz_isso() -> None:
    """Estado de primeira classe: o hub saiu às 02h36 e levou os três dongles."""
    mesa = _mesa_sem_hub()
    assert motor.adaptadores_da_mesa(mesa) == ()
    assert _plano_dos_controles(mesa, 4) == ouro("sem-hub/controles")
    plano = motor.plano_dos_controles(mock.CONTROLES, motor.adaptadores_da_mesa(mesa))
    assert plano.cabe is False
    assert plano.sobra == 0
    assert plano.destino == {}


#: Duas entradas com nome, como o mapa dela guarda (o ``nome`` da porta declarada).
_NOMES = {"9": "Atrás", "15a": "Ponta"}


def _com_os_nomes(v: Any) -> Any:
    """O ouro com cada «Entrada N» nomeada trocada pelo sintagma do dono («entrada Atrás»)."""
    import re

    if isinstance(v, str):
        for numero, nome in _NOMES.items():
            v = re.sub(rf"\bEntrada {re.escape(numero)}(?![0-9a-z])", f"entrada {nome}", v)
        return v
    if isinstance(v, list):
        return [_com_os_nomes(x) for x in v]
    if isinstance(v, dict):
        return {k: _com_os_nomes(x) for k, x in v.items()}
    return v


def _mesa_com_nomes(**kw: Any) -> motor.Mesa:
    from dataclasses import replace

    return replace(_mesa(**kw), nomes=_NOMES)


@_DIVERGE
@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext", "so-pc"])
def test_o_nome_que_ela_deu_entra_em_toda_frase_da_receita(variante: str) -> None:
    """A frase do motor diz a entrada pelo dono: com nome, «na entrada Atrás»; sem, «na Entrada 9».

    MORDIDA: uma frase da receita que volte a montar «entrada » + número à mão reprova aqui
    (e na régua do dono único, `test_a_costura_da_onda_2::test_o_nome_da_porta_tem_um_dono_so`)."""
    movs = motor.receita(_mesa_com_nomes(), OPCOES[variante])
    esperado = _com_os_nomes(_receita_do_ouro(f"receita/{variante}"))
    assert como_o_mockup_receita(movs) == esperado


@_DIVERGE
@pytest.mark.parametrize("n", ["1", "2", "10", "15a"])
@pytest.mark.parametrize("na_mao", ["bt", "teclado", "mouse"])
def test_o_nome_que_ela_deu_entra_no_porque_do_julgamento(n: str, na_mao: str) -> None:
    mesa = _mesa_com_nomes()
    entrada = motor.por_num(mesa.faces, n)
    assert entrada is not None
    esperado = _com_os_nomes(ouro(f"julgar/{n}/{na_mao}"))
    assert _veredito(motor.julgar(entrada, na_mao, mesa)) == esperado


def test_o_nome_que_ela_deu_entra_no_rotulo_do_adaptador() -> None:
    plano = _controles(motor.plano_dos_controles(
        mock.CONTROLES[:4], motor.adaptadores_da_mesa(_mesa_com_nomes())))
    assert plano == _com_os_nomes(ouro("controles/padrao"))
    assert {a["rotulo"] for a in plano["ads"]} >= {"entrada Atrás", "entrada Ponta"}


@_DIVERGE
def test_a_prova_dos_nomes_nao_e_vazia() -> None:
    """Os cenários acima passam por frases com a Entrada 9 e a 15a: a troca muda o ouro."""
    receitas = [f"receita/{v}" for v in ("melhor", "poucos", "sem-ext", "so-pc")]
    julgados = [f"julgar/{n}/{m}" for n in ("1", "2", "10", "15a")
                for m in ("bt", "teclado", "mouse")]
    assert sum(_com_os_nomes(ouro(k)) != ouro(k) for k in receitas) >= 2
    assert sum(_com_os_nomes(ouro(k)) != ouro(k) for k in julgados) >= 2


def _oraculo_numa_arvore_so_com(pagina: str) -> subprocess.CompletedProcess[str]:
    """Roda o oráculo numa árvore de mentira que tem SÓ esta página viva e nenhum congelado."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="orac-") as raiz:
        tests = Path(raiz) / "tests" / "fixtures"
        tests.mkdir(parents=True)
        (Path(raiz) / "mockup").mkdir()
        shutil.copy(ORACULO, tests / ORACULO.name)
        (Path(raiz) / "mockup" / "mapa-das-portas.html").write_text(pagina, encoding="utf-8")
        return subprocess.run(
            [shutil.which("node") or "node", str(tests / ORACULO.name)],
            capture_output=True, text=True, timeout=120, cwd=raiz,
        )


@pytest.mark.skipif(shutil.which("node") is None, reason="node não está nesta máquina")
def test_o_oraculo_le_a_pagina_viva_e_nao_o_congelado() -> None:
    """O oráculo segue a página que o gerador escreve: sem o congelado por perto, e com um
    veredito mudado SÓ nela, a resposta muda. O oráculo velho lia o congelado e não via isto."""
    viva = PAGINA_VIVA.read_text(encoding="utf-8")
    assert viva.count('txt: "Ocupada"') >= 2, "o veredito da prova saiu da página viva"
    limpo = _oraculo_numa_arvore_so_com(viva)
    assert limpo.returncode == 0, limpo.stderr
    assert json.loads(limpo.stdout) == json.loads(OURO.read_text(encoding="utf-8"))

    mexida = _oraculo_numa_arvore_so_com(viva.replace('txt: "Ocupada"', 'txt: "OcupadaNaViva"'))
    assert mexida.returncode == 0, mexida.stderr
    assert "OcupadaNaViva" in mexida.stdout, "o oráculo não leu a página viva"
    assert "OcupadaNaViva" not in OURO.read_text(encoding="utf-8")


def test_o_oraculo_nao_remenda_a_grafia_da_pagina() -> None:
    """A página viva diz a entrada pelo `naFraseDe` do dono; o oráculo não troca frase à mão."""
    fonte = ORACULO.read_text(encoding="utf-8")
    assert "GRAFIA" not in fonte and "congelados" not in fonte
    assert "mapa-das-portas.html" in fonte
    assert "function naFraseDe" in PAGINA_VIVA.read_text(encoding="utf-8")


# A divergência que o `_DIVERGE` declara é só de TEXTO (a frase do porquê e o título do
# movimento). A regra embaixo dele (o veredito, o plano, o selo de cada razão, a entrada de
# destino) tem de bater com a página viva sem exceção: sem estas réguas, um erro de regra no
# porte se esconderia atrás do xfail do texto.
def _entrada(titulo: str) -> str | None:
    achou = re.findall(r"[Ee]ntrada (\w+)", titulo)
    return achou[-1] if achou else None


def _regra_da_receita(movs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"para": _entrada(m["titulo"]), "selos": [linha["s"] for linha in m["linhas"]],
             "essencial": m["essencial"], "ganho": m["ganho"], "semNumero": m["semNumero"]}
            for m in movs]


def _regra_do_plano(p: dict[str, Any]) -> dict[str, Any]:
    return {"plano": p["plano"], "motivo": {
        quem: {**{k: v for k, v in m.items() if k != "razoes"},
               "selos": [r["selo"] for r in m["razoes"]]}
        for quem, m in p["motivo"].items()}}


def _regra_do_veredito(v: dict[str, str] | None) -> str | None:
    return v["v"] if v else None


@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext", "so-pc"])
def test_a_regra_do_plano_e_da_receita_bate_sem_o_texto(variante: str) -> None:
    mesa = _mesa()
    assert _regra_do_plano(como_o_mockup_planeja(motor.planejar(mesa, OPCOES[variante]))) == \
        _regra_do_plano(ouro(f"planejar/{variante}"))
    assert _regra_da_receita(como_o_mockup_receita(motor.receita(mesa, OPCOES[variante]))) == \
        _regra_da_receita(_receita_do_ouro(f"receita/{variante}"))


def test_a_regra_sem_o_bonus_do_mapa_vazio_e_do_torto_bate_sem_o_texto() -> None:
    sem_bonus = motor.Opcoes(bonus_parado=0)
    assert _regra_do_plano(como_o_mockup_planeja(motor.planejar(_mesa(), sem_bonus))) == \
        _regra_do_plano(ouro("planejar/sem-bonus-parado"))
    assert _regra_da_receita(como_o_mockup_receita(motor.receita(_mesa(), sem_bonus))) == \
        _regra_da_receita(_receita_do_ouro("receita/sem-bonus-parado"))
    vazio = _mesa(mapa={})
    assert _regra_do_plano(como_o_mockup_planeja(motor.planejar(vazio))) == \
        _regra_do_plano(ouro("mapa-vazio/planejar"))
    assert _regra_da_receita(como_o_mockup_receita(motor.receita(vazio))) == \
        _regra_da_receita(_receita_do_ouro("mapa-vazio/receita"))
    assert [e.n for e in motor.candidatas(vazio, "pc")] == ouro("mapa-vazio/candidatas-pc")
    assert _regra_da_receita(como_o_mockup_receita(motor.receita(_mesa(mapa={"99": "9-9"})))) == \
        _regra_da_receita(_receita_do_ouro("mapa-inexistente/receita"))


@pytest.mark.parametrize("n", ["1", "2", "3", "7", "9", "10", "13", "15", "15a"])
@pytest.mark.parametrize("na_mao", ["bt", "wifi", "teclado", "mouse", "webcam", None])
def test_o_veredito_de_cada_entrada_bate_sem_o_texto(n: str, na_mao: str | None) -> None:
    mesa = _mesa()
    e = motor.por_num(mesa.faces, n)
    assert e is not None
    assert _regra_do_veredito(_veredito(motor.julgar(e, na_mao, mesa))) == \
        _regra_do_veredito(ouro(f"julgar/{n}/{_js(na_mao)}"))


@pytest.mark.parametrize("n", ["1", "2", "10", "15a"])
def test_o_veredito_segurando_um_dongle_do_hub_bate_sem_o_texto(n: str) -> None:
    mesa = _mesa()
    e = motor.por_num(mesa.faces, n)
    assert e is not None
    assert _regra_do_veredito(_veredito(motor.julgar(e, "bt", mesa, segurando="bt-c"))) == \
        _regra_do_veredito(ouro(f"julgar-segurando/bt-c/{n}"))


def test_sem_o_hub_a_regra_bate_sem_o_texto() -> None:
    mesa = _mesa_sem_hub()
    assert motor.alocacao(mesa.mapa, mesa.leitura) == ouro("sem-hub/alocacao")
    assert motor.caminho_do_hub(mesa) is None
    assert motor.regiao_do_caminho("1-3", None) == ouro("sem-hub/regiao-1-3")
    assert motor.regiao_do_caminho("4-4", None) == ouro("sem-hub/regiao-4-4")
    achado = [{"id": s.aparelho.id, "caminho": s.caminho, "regiao": s.regiao}
              for s in motor.sem_entrada(mesa)]
    assert achado == ouro("sem-hub/semEntrada")
    assert motor.consequencias(mesa) == ouro("sem-hub/consequencias")
    assert _regra_do_plano(como_o_mockup_planeja(motor.planejar(mesa))) == \
        _regra_do_plano(ouro("sem-hub/planejar"))
    assert _regra_da_receita(como_o_mockup_receita(motor.receita(mesa))) == \
        _regra_da_receita(_receita_do_ouro("sem-hub/receita"))
