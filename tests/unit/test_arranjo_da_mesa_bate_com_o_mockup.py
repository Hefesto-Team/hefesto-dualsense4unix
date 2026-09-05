"""A prova de que o porte não mudou o cálculo.

O motor do arranjo existia só em JavaScript, dentro de um mockup, e **já estava
testado em 29 estados**. Portar sem provar equivalência jogaria fora esses 29
estados e deixaria a promessa *"é a mesma lógica"* sem régua.

COMO A PROVA FUNCIONA
----------------------

``tests/fixtures/motor_do_arranjo_do_mockup.js`` **extrai** o motor do HTML (não
o copia), roda 120 cenários em ``node`` e imprime a saída em JSON. Esse JSON está
gravado em ``motor_do_arranjo_do_mockup.json``, e cada teste daqui monta o MESMO
cenário em Python e afirma a MESMA saída.

Dois testes, duas coisas diferentes:

* ``test_o_ouro_ainda_e_o_que_o_mockup_diz_hoje`` roda o ``node`` de verdade e
  confere que o JSON gravado continua sendo o que o mockup produz. É o que
  impede o ouro de envelhecer em silêncio quando o mockup mudar;
* todos os outros comparam Python contra o ouro, e **rodam sem ``node``**.

Sem o primeiro, o ouro vira cópia velha; sem os outros, a suíte fica refém de
haver ``node`` na máquina. As duas réguas são independentes de propósito — é
regra desta casa.
"""

from __future__ import annotations

import json
import math
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


def _js(v: object) -> str:
    """A chave do cenário como o JavaScript a escreveu: ``null``, não ``None``."""
    return "null" if v is None else str(v)


# ── as duas beiras da mesma forma ────────────────────────────────────────


#: AS PALAVRAS QUE DIVERGIRAM DO ORÁCULO, e a razão de cada uma.
#:
#: O oráculo é o mockup CONGELADO de 24/08/2026
#: (``docs/process/sprints/2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html``),
#: e ele não se reescreve: é o registro de como o motor pensava naquele dia. Em
#: 05/09/2026 ela mandou tirar a palavra "mesa" da interface —  *"muda o termo
#: pra objeto e sinônimos nesses casos"* — e as duas frases abaixo mudaram no
#: produto. O oráculo continua dizendo a palavra velha, e está certo em dizê-la.
#:
#: POR QUE UMA TABELA, E NÃO UM `!=` AFROUXADO: a régua tem de continuar
#: comparando a frase INTEIRA. Se ela passasse a ignorar `porque` e `texto`,
#: pararia de medir justamente o que o porte promete reproduzir — e um dia
#: alguém trocaria a frase por outra sem que nada reprovasse. Aqui a única
#: liberdade é esta: DUAS traduções, escritas com nome e data, e um portão logo
#: abaixo que exige que as duas ainda DISPAREM. Tradução que não dispara mais é
#: tradução morta, e sai.
DIVERGENCIA_DA_PALAVRA_MESA: dict[str, str] = {
    "entrada direta, mas na altura da mesa":
        "entrada direta, mas na altura da escrivaninha",
    "os dongles ficam na altura da mesa, não no alto do rack":
        "os dongles ficam na altura da escrivaninha, não no alto do rack",
}

#: Quantas vezes cada tradução foi usada nesta rodada. O
#: ``test_as_traducoes_da_palavra_mesa_ainda_disparam`` lê daqui.
_TRADUZIDAS: dict[str, int] = {frase: 0 for frase in DIVERGENCIA_DA_PALAVRA_MESA}


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
    if isinstance(v, str) and v in DIVERGENCIA_DA_PALAVRA_MESA:
        _TRADUZIDAS[v] += 1
        return DIVERGENCIA_DA_PALAVRA_MESA[v]
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


# ── o oráculo, e o ouro que ele produziu ─────────────────────────────────


@pytest.mark.skipif(shutil.which("node") is None, reason="node não está nesta máquina")
def test_o_ouro_ainda_e_o_que_o_mockup_diz_hoje() -> None:
    """O JSON gravado é o que o mockup de HOJE produz — não uma cópia velha."""
    saida = subprocess.run(
        [shutil.which("node") or "node", str(ORACULO)],
        capture_output=True, text=True, check=True, cwd=RAIZ, timeout=120,
    )
    assert json.loads(saida.stdout) == json.loads(OURO.read_text(encoding="utf-8"))


# ── o modelo: mapa + leitura = alocação ──────────────────────────────────


def test_a_alocacao_derivada_e_a_mesma() -> None:
    assert motor.alocacao(mock.MAPA, mock.LEITURA_AGORA) == ouro("alocacao/agora")
    assert motor.alocacao(mock.MAPA, mock.LEITURA_ANTES) == ouro("alocacao/antes")


def test_o_mapa_vazio_e_o_mapa_com_entrada_que_nao_existe() -> None:
    assert motor.alocacao({}, mock.LEITURA_AGORA) == ouro("mapa-vazio/alocacao")
    assert motor.alocacao({"99": "9-9"}, mock.LEITURA_AGORA) == ouro("mapa-inexistente/alocacao")


# ── a dedução de região pelo barramento ──────────────────────────────────


@pytest.mark.parametrize(
    "caminho",
    ["3-1.2", "3-1.1.1", "4-1.1.2", "4-2", "1-3", "1-6", "1-4", "3-1", None],
)
def test_a_regiao_sai_do_barramento(caminho: str | None) -> None:
    mesa = mock.mesa()
    esperado = ouro(f"regiao/{_js(caminho)}")
    assert motor.regiao_do_caminho(caminho, motor.caminho_do_hub(mesa)) == esperado


def test_quem_o_mapa_nao_conhece_ainda_diz_de_que_lado_esta() -> None:
    achado = [{"id": s.aparelho.id, "caminho": s.caminho, "regiao": s.regiao}
              for s in motor.sem_entrada(mock.mesa())]
    assert achado == ouro("semEntrada/agora")
    antes = [{"id": s.aparelho.id, "caminho": s.caminho, "regiao": s.regiao}
             for s in motor.sem_entrada(mock.mesa(leitura=mock.LEITURA_ANTES))]
    assert antes == ouro("semEntrada/antes")


def test_as_candidatas_saem_de_dezesseis_para_quatro() -> None:
    mesa = mock.mesa()
    assert [e.n for e in motor.candidatas(mesa, "pc")] == ouro("candidatas/pc")
    assert [e.n for e in motor.candidatas(mesa, "hub")] == ouro("candidatas/hub")
    assert [e.n for e in motor.todas_as_entradas(mesa.faces)] == ouro("todasPortas")


# ── o planejador e a receita, nas quatro variantes ───────────────────────


@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext", "so-pc"])
def test_o_plano_e_o_mesmo_do_javascript(variante: str) -> None:
    plano = motor.planejar(mock.mesa(), OPCOES[variante])
    assert como_o_mockup_planeja(plano) == ouro(f"planejar/{variante}")


@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext", "so-pc"])
def test_a_receita_e_a_mesma_do_javascript(variante: str) -> None:
    movs = motor.receita(mock.mesa(), OPCOES[variante])
    assert como_o_mockup_receita(movs) == _receita_do_ouro(f"receita/{variante}")


@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext", "so-pc"])
def test_o_que_se_perde_e_a_mesma_frase(variante: str) -> None:
    assert motor.consequencias(mock.mesa(), OPCOES[variante]) == ouro(f"consequencias/{variante}")
    assert motor.qualidade(mock.mesa(), OPCOES[variante]) == ouro(f"qualidade/{variante}")


def test_a_receita_sem_o_bonus_de_ficar_parado_bate_tambem() -> None:
    """A regra é PARÂMETRO, e o porte tem de reproduzir os dois valores dela."""
    op = motor.Opcoes(bonus_parado=0)
    plano = como_o_mockup_planeja(motor.planejar(mock.mesa(), op))
    assert plano == ouro("planejar/sem-bonus-parado")
    assert como_o_mockup_receita(motor.receita(mock.mesa(), op)) == _receita_do_ouro(
        "receita/sem-bonus-parado")


def test_a_receita_do_mapa_vazio_e_do_mapa_torto() -> None:
    vazio = mock.mesa(mapa={})
    assert como_o_mockup_planeja(motor.planejar(vazio)) == ouro("mapa-vazio/planejar")
    assert como_o_mockup_receita(motor.receita(vazio)) == _receita_do_ouro("mapa-vazio/receita")
    assert [e.n for e in motor.candidatas(vazio, "pc")] == ouro("mapa-vazio/candidatas-pc")
    torto = mock.mesa(mapa={"99": "9-9"})
    assert como_o_mockup_receita(motor.receita(torto)) == _receita_do_ouro(
        "mapa-inexistente/receita")


# ── o julgamento por entrada ─────────────────────────────────────────────


@pytest.mark.parametrize("n", ["1", "2", "3", "7", "9", "10", "13", "15", "15a"])
@pytest.mark.parametrize("na_mao", ["bt", "wifi", "teclado", "mouse", "webcam", None])
def test_o_julgamento_de_cada_entrada_e_o_mesmo(n: str, na_mao: str | None) -> None:
    mesa = mock.mesa()
    entrada = motor.por_num(mesa.faces, n)
    assert entrada is not None
    assert _veredito(motor.julgar(entrada, na_mao, mesa)) == ouro(f"julgar/{n}/{_js(na_mao)}")


@pytest.mark.parametrize("n", ["1", "2", "10", "15a"])
def test_segurando_um_dongle_do_hub_a_outra_regiao_se_recusa(n: str) -> None:
    mesa = mock.mesa()
    entrada = motor.por_num(mesa.faces, n)
    assert entrada is not None
    veredito = motor.julgar(entrada, "bt", mesa, segurando="bt-c")
    assert _veredito(veredito) == ouro(f"julgar-segurando/bt-c/{n}")


# ── a re-identificação por serial ────────────────────────────────────────


def test_o_reexame_reconhece_quem_mudou_de_lugar() -> None:
    mudou = motor.reexame(mock.mesa(), mock.LEITURA_ANTES, mock.LEITURA_AGORA)
    achado = [{"id": m.aparelho.id, "antes": m.antes, "agora": m.agora,
               "entradaAntes": m.entrada_antes, "entradaAgora": m.entrada_agora}
              for m in mudou]
    assert achado == ouro("reexame/antes-agora")
    assert motor.reexame(mock.mesa(), mock.LEITURA_AGORA, mock.LEITURA_AGORA) == []


# ── os controles por adaptador ───────────────────────────────────────────


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_a_distribuicao_dos_controles_e_a_mesma(quantos: int) -> None:
    assert _plano_dos_controles(mock.mesa(), quantos) == ouro(f"controles/quantos={quantos}")


def test_o_microfone_e_o_unico_que_muda_a_conta() -> None:
    sem_mic = tuple(motor.Controle(c.nome, mic=False, onde=c.onde) for c in mock.CONTROLES)
    assert _plano_dos_controles(mock.mesa(), 4, sem_mic) == ouro("controles/sem-mic")


def test_os_quatro_no_mesmo_dongle_e_o_adaptador_que_sumiu() -> None:
    juntos = tuple(motor.Controle(c.nome, c.mic, onde="bt-a") for c in mock.CONTROLES)
    assert _plano_dos_controles(mock.mesa(), 4, juntos) == ouro("controles/todos-no-bt-a")
    orfaos = tuple(motor.Controle(c.nome, c.mic, onde="sumiu") for c in mock.CONTROLES)
    assert _plano_dos_controles(mock.mesa(), 4, orfaos) == ouro("controles/adaptador-sumiu")


# ── A MESA DELA DE AGORA: o hub sumiu, e levou os três dongles ───────────


def test_sem_o_hub_o_motor_responde_e_nao_inventa() -> None:
    mesa = mock.mesa_sem_hub()
    assert motor.alocacao(mesa.mapa, mesa.leitura) == ouro("sem-hub/alocacao")
    # sem hub na leitura não há topologia de hub: a resposta honesta é None
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
    mesa = mock.mesa_sem_hub()
    assert motor.adaptadores_da_mesa(mesa) == ()
    assert _plano_dos_controles(mesa, 4) == ouro("sem-hub/controles")
    plano = motor.plano_dos_controles(mock.CONTROLES, motor.adaptadores_da_mesa(mesa))
    assert plano.cabe is False
    assert plano.sobra == 0
    assert plano.destino == {}


# ── a divergência de palavra, e o portão que a segura ────────────────────


def test_as_traducoes_da_palavra_mesa_ainda_disparam() -> None:
    """Toda tradução declarada tem de ser USADA, e nenhuma pode sobrar.

    A MORDIDA QUE ESTE TESTE É: ``DIVERGENCIA_DA_PALAVRA_MESA`` é a única
    liberdade que a comparação com o oráculo tem, e liberdade que ninguém
    confere vira armário. Se o produto voltar a dizer "mesa", a tradução deixa
    de ser necessária e **esta linha reprova** — obrigando quem a tornou inútil
    a apagá-la, em vez de deixá-la de pé perdoando uma frase que já não existe.

    Ele roda depois dos outros de propósito: ``_TRADUZIDAS`` conta o que a
    leitura do ouro traduziu ao longo do arquivo.
    """
    ouro("julgar/3/bt")
    ouro("consequencias/so-pc")

    mortas = [frase for frase, vezes in _TRADUZIDAS.items() if vezes == 0]
    assert not mortas, (
        "tradução declarada que nunca disparou — o oráculo já não diz esta "
        f"frase, então APAGUE a entrada: {mortas}"
    )


def test_nenhuma_traducao_muda_mais_do_que_a_palavra() -> None:
    """Uma tradução só pode trocar a PALAVRA, nunca o que a frase diz.

    Sem esta régua a tabela viraria a porta dos fundos do oráculo: bastaria
    declarar ``"x" -> "y"`` para qualquer frase divergente passar. Aqui o resto
    da frase — tudo menos a palavra trocada — tem de ficar idêntico.
    """
    for antes, depois in DIVERGENCIA_DA_PALAVRA_MESA.items():
        assert "mesa" in antes, f"tradução que não é sobre a palavra: {antes!r}"
        assert "mesa" not in depois, f"a tradução mantém a palavra: {depois!r}"
        assert antes.replace("mesa", "escrivaninha") == depois, (
            "a tradução mudou mais do que a palavra — o oráculo é o juiz do "
            f"resto da frase:\n  antes:  {antes!r}\n  depois: {depois!r}"
        )
