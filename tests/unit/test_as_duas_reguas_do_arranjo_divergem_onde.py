"""AS DUAS RÉGUAS DO ARRANJO, RODADAS LADO A LADO — e onde elas divergem."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import plano_de_radio
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    CORTE_APERTADA,
    SLOTS_POR_SEGUNDO,
)

RAIZ = Path(__file__).resolve().parents[2]

DONGLE_A = "e8:47:3a:00:00:09"
DONGLE_B = "e8:47:3a:00:00:15"
DONGLE_C = "e8:47:3a:00:00:21"
CONTROLES = tuple(f"aa:bb:cc:00:00:{n:02d}" for n in range(1, 11))


@dataclass(frozen=True)
class Posto:
    """Um controle, o adaptador em que ele JÁ está, se o microfone está de pé e"""

    nome: str
    endereco: str
    onde: str
    mic: bool
    ponte: bool = False


@dataclass(frozen=True)
class Bancada:
    """Uma mesa de mentira, e o que se espera de cada régua sobre ela."""

    id: str
    titulo: str
    adaptadores: tuple[str, ...]
    postos: tuple[Posto, ...]
    tela_move: int
    motor_move: int
    nota: str = ""


def _postos(
    quantos: int, onde: str, *, mic: bool, desde: int = 0, ponte: bool = False
) -> tuple[Posto, ...]:
    return tuple(
        Posto(nome=f"Jogador {i + 1}", endereco=CONTROLES[i], onde=onde, mic=mic, ponte=ponte)
        for i in range(desde, desde + quantos)
    )


BANCADAS: tuple[Bancada, ...] = (
    Bancada(
        id="1-a-mesa-dela",
        titulo=(
            "a mesa dela: três adaptadores no mesmo hub, quatro controles com "
            "microfone, todos no primeiro"
        ),
        adaptadores=(DONGLE_A, DONGLE_B, DONGLE_C),
        postos=_postos(4, DONGLE_A, mic=True, ponte=True),
        tela_move=1,
        motor_move=2,
        nota=(
            "a mesa cheia desta casa (co-op de quatro, microfone e som de pé em "
            "todos): quatro pontes num adaptador que comporta duas, e a tela "
            "propõe UM movimento de cada vez (R12)"
        ),
    ),
    Bancada(
        id="2-mesa-vazia",
        titulo="a mesa vazia: nenhum adaptador, nenhum controle",
        adaptadores=(),
        postos=(),
        tela_move=0,
        motor_move=0,
        nota=(
            "o estado real dela às 02h36 de 25/08/2026, quando o hub saiu do "
            "barramento levando os três dongles"
        ),
    ),
    Bancada(
        id="3-vizinho-com-folga",
        titulo=(
            "adaptador estourando e um vizinho com UM controle: seis sem "
            "microfone no primeiro, um no segundo"
        ),
        adaptadores=(DONGLE_A, DONGLE_B),
        postos=(
            _postos(3, DONGLE_A, mic=False, ponte=True)
            + _postos(3, DONGLE_A, mic=False, desde=3)
            + _postos(1, DONGLE_B, mic=False, desde=6)
        ),
        tela_move=1,
        motor_move=2,
        nota="a única bancada em que a régua da tela MANDA mover — e manda menos",
    ),
    Bancada(
        id="4-buraco-livre-noutra-controladora",
        titulo=(
            "buraco livre noutra controladora PCI: seis controles no primeiro "
            "adaptador, o segundo VAZIO"
        ),
        adaptadores=(DONGLE_A, DONGLE_B),
        postos=(
            _postos(3, DONGLE_A, mic=False, ponte=True)
            + _postos(3, DONGLE_A, mic=False, desde=3)
        ),
        tela_move=1,
        motor_move=3,
        nota=(
            "até 23/09 o adaptador sem controle NÃO existia para a régua da tela; "
            "desde a MOVER-UM-POR-VEZ-01 ele é destino"
        ),
    ),
    Bancada(
        id="5-sem-ordem-possivel",
        titulo="sem ordem possível: seis controles e um adaptador só na mesa",
        adaptadores=(DONGLE_A,),
        postos=(
            _postos(3, DONGLE_A, mic=False, ponte=True)
            + _postos(3, DONGLE_A, mic=False, desde=3)
        ),
        tela_move=0,
        motor_move=0,
        nota="as duas CONVERGEM: não há para onde mover, e as duas calam",
    ),
    Bancada(
        id="6-dois-cheios",
        titulo="dois adaptadores, ambos na Cheia: cinco controles com microfone em cada",
        adaptadores=(DONGLE_A, DONGLE_B),
        postos=(
            _postos(3, DONGLE_A, mic=True, ponte=True)
            + _postos(2, DONGLE_A, mic=True, desde=3)
            + _postos(3, DONGLE_B, mic=True, desde=5, ponte=True)
            + _postos(2, DONGLE_B, mic=True, desde=8)
        ),
        tela_move=0,
        motor_move=0,
        nota=(
            "convergem no movimento — e a tela publica a frase do adaptador "
            "único com DEZ controles em DOIS adaptadores"
        ),
    ),
)


def _sysfs_de_mentira(postos: tuple[Posto, ...]) -> dict[str, Any]:
    """Um ``/sys/class/hidraw`` de papel: ``{uniq do controle: MAC do adaptador}``."""
    nos = {
        f"hidraw{i}": (posto.endereco, posto.onde) for i, posto in enumerate(postos)
    }
    textos = {
        os.path.join("/sys/class/hidraw", no, "device", "uevent"): (
            f"HID_UNIQ={uniq}\nHID_PHYS={phys}\n"
        )
        for no, (uniq, phys) in nos.items()
    }
    return {
        "listar": lambda _raiz: sorted(nos),
        "ler": lambda caminho: textos.get(caminho, ""),
    }


def _sem_dois_pontos(mac: str) -> str:
    """Como o ``uniq`` do estado do daemon chega: 12 hex, sem separador."""
    return mac.replace(":", "")


@dataclass(frozen=True)
class Movimento:
    quem: str
    origem: str
    destino: str


@dataclass(frozen=True)
class Veredito:
    """O que UMA régua respondeu sobre UMA bancada, já em português."""

    regua: str
    movimentos: tuple[Movimento, ...]
    razao: str
    extras: tuple[str, ...] = field(default_factory=tuple)


def _curto(endereco: str) -> str:
    """O adaptador como a pessoa o distingue na mesa, sem publicar o MAC inteiro."""
    return f"…{endereco[-5:]}" if endereco else "(sem adaptador)"


def _num(valor: float) -> str:
    """Número em português: vírgula decimal, uma casa."""
    return f"{valor:.1f}".replace(".", ",")


def veredito_da_tela(bancada: Bancada) -> Veredito:
    """A régua que JÁ está na tela — ``plano_de_radio.ordem_de_redistribuicao``."""
    estado = [
        {
            "transport": "bt",
            "connected": True,
            "uniq": _sem_dois_pontos(posto.endereco),
            "player_slot": i + 1,
            "ponte_do_radio": "som" if posto.ponte else None,
        }
        for i, posto in enumerate(bancada.postos)
    ]
    planos = plano_de_radio.plano_por_adaptador(
        estado,
        com_ponte_de_mic=[
            _sem_dois_pontos(p.endereco) for p in bancada.postos if p.mic
        ],
        adaptadores=bancada.adaptadores,
        **_sysfs_de_mentira(bancada.postos),
    )
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)

    vistos = tuple(
        f"{_curto(e)}: {p.no_ar} controle(s), {p.pontes} de {p.n_max} pontes "
        f'("{p.rotulo_das_pontes}")'
        for e, p in sorted(planos.items())
    )
    invisiveis = tuple(a for a in bancada.adaptadores if a not in planos)
    if invisiveis:
        vistos += (
            "ADAPTADOR QUE ELA NÃO VÊ: "
            + ", ".join(_curto(a) for a in invisiveis)
            + " — sem controle conectado, `plano_por_adaptador` não produz plano",
        )

    apertados = [
        e for e, p in planos.items() if p.agora.fracao_total > CORTE_APERTADA
    ]
    if apertados and ordem is None:
        vistos += (
            "A TELA IMPRIME: " + plano_de_radio.FRASE_DO_ADAPTADOR_UNICO,
        )

    if ordem is None:
        alem = [p for p in planos.values() if p.pontes > p.n_max]
        if not planos:
            razao = "nenhum controle no rádio: não há o que arranjar"
        elif not alem:
            maior = max(p.pontes for p in planos.values())
            razao = (
                f"nenhum adaptador passou do limite de pontes: o mais carregado "
                f"tem {maior}"
            )
        else:
            razao = (
                "há adaptador além do limite de pontes, mas nenhum OUTRO "
                "adaptador conhecido tem vaga para mais uma"
            )
        return Veredito("régua da tela", (), razao, vistos)

    if ordem.origem_na_tela == ordem.destino_na_tela:
        vistos += (
            "A TELA MANDA MOVER DE "
            f'"{ordem.origem_na_tela}" PARA "{ordem.destino_na_tela}" — o mesmo '
            "nome nas duas pontas, porque nenhum dos dois tem apelido dela",
        )

    return Veredito(
        regua="régua da tela",
        movimentos=(
            Movimento(
                quem=f"um controle com ponte de {ordem.modo} (é a ponte que transborda)",
                origem=ordem.origem,
                destino=ordem.destino,
            ),
        ),
        razao=f"{ordem.por_que_importa} {ordem.ganho_esperado}",
        extras=(*vistos, f"o que ela viu: {ordem.o_que_eu_vi}"),
    )


def veredito_do_motor(bancada: Bancada) -> Veredito:
    """A régua portada do mockup — ``arranjo_da_mesa.plano_dos_controles``."""
    adaptadores = tuple(
        motor.Adaptador(id=endereco, entrada=str(i + 1), rotulo=f"entrada {i + 1}")
        for i, endereco in enumerate(bancada.adaptadores)
    )
    controles = tuple(
        motor.Controle(nome=p.nome, mic=p.mic, onde=p.onde) for p in bancada.postos
    )
    plano = motor.plano_dos_controles(controles, adaptadores)

    movimentos = tuple(
        Movimento(quem=c.nome, origem=c.onde, destino=plano.destino[c.nome])
        for c in controles
        if plano.destino.get(c.nome) != c.onde
    )

    antes: dict[str, float] = {a.id: 0.0 for a in adaptadores}
    for c in controles:
        if c.onde in antes:
            antes[c.onde] += motor.CUSTO_COM_MIC if c.mic else motor.CUSTO_SEM_MIC
    pico_antes = max(antes.values()) if antes else 0.0
    pico_depois = max(plano.carga.values()) if plano.carga else 0.0

    if movimentos:
        razao = (
            f"a regra é mover só enquanto isso BAIXAR o pico: ele caiu de "
            f"{_num(pico_antes)} para {_num(pico_depois)} fatias "
            f"(teto {motor.SLOTS})"
        )
    elif not adaptadores:
        razao = "sem adaptador nenhum, nada cabe — e não há destino a propor"
    else:
        razao = (
            f"nenhuma troca baixaria o pico, que fica em {_num(pico_depois)} de "
            f"{motor.SLOTS} fatias"
        )

    extras = (
        *(
            f"{_curto(a.id)}: {_num(plano.carga[a.id])} fatias depois do plano"
            for a in adaptadores
        ),
        f"cabe? {'sim' if plano.cabe else 'não'}; "
        f"ainda caberiam {plano.sobra} controle(s) com microfone",
    )
    return Veredito("motor do arranjo", movimentos, razao, extras)


def _bloco_do_veredito(veredito: Veredito) -> list[str]:
    linhas = [f"  {veredito.regua.upper()}"]
    if veredito.movimentos:
        for mov in veredito.movimentos:
            linhas.append(f"    quem   : {mov.quem}")
            linhas.append(f"    origem : {_curto(mov.origem)}")
            linhas.append(f"    destino: {_curto(mov.destino)}")
    else:
        linhas.append("    quem   : ninguém — ela não manda mover controle nenhum")
        linhas.append("    origem : (nenhuma)")
        linhas.append("    destino: (nenhum)")
    linhas.append(f"    razão  : {veredito.razao}")
    for extra in veredito.extras:
        linhas.append(f"      · {extra}")
    return linhas


def relatorio_de(bancada: Bancada) -> str:
    """O laudo de UMA bancada, com as duas réguas lado a lado."""
    tela = veredito_da_tela(bancada)
    arranjo = veredito_do_motor(bancada)

    linhas = [
        f"BANCADA {bancada.id} — {bancada.titulo}",
        f"  na mesa: {len(bancada.adaptadores)} adaptador(es), "
        f"{len(bancada.postos)} controle(s)",
    ]
    if bancada.nota:
        linhas.append(f"  nota: {bancada.nota}")
    linhas += _bloco_do_veredito(tela)
    linhas += _bloco_do_veredito(arranjo)

    n_tela, n_motor = len(tela.movimentos), len(arranjo.movimentos)
    if n_tela == n_motor == 0:
        linhas.append("  VEREDITO: CONVERGEM — as duas calam.")
    elif n_tela == 0:
        linhas.append(
            f"  VEREDITO: DIVERGEM — a régua da tela cala e o motor manda mover "
            f"{n_motor} controle(s)."
        )
    elif n_motor == 0:
        linhas.append(
            "  VEREDITO: DIVERGEM — a régua da tela manda mover e o motor cala."
        )
    elif n_tela != n_motor:
        linhas.append(
            f"  VEREDITO: DIVERGEM NO TAMANHO — a tela manda mover {n_tela} e o "
            f"motor manda mover {n_motor}."
        )
    else:
        linhas.append(
            f"  VEREDITO: as duas mandam mover {n_tela} controle(s) — confira "
            "origem e destino acima."
        )
    return "\n".join(linhas)


def relatorio_completo() -> str:
    cabeca = [
        "AS DUAS RÉGUAS DO ARRANJO, SOBRE A MESMA BANCADA",
        f"teto do rádio: {SLOTS_POR_SEGUNDO} fatias/s por adaptador · "
        f"corte da \"Apertada\": {_num(CORTE_APERTADA * 100)}% · "
        f"um controle custa {_num(motor.CUSTO_SEM_MIC)} sem microfone e "
        f"{_num(motor.CUSTO_COM_MIC)} com",
        "",
    ]
    return "\n\n".join(cabeca[:2] + [relatorio_de(b) for b in BANCADAS])


def test_a_divergencia_esta_nomeada() -> None:
    """MORDIDA. Cada bancada nomeia origem, destino e razão DE CADA RÉGUA."""
    laudo = relatorio_completo()
    print("\n" + laudo)

    assert BANCADAS, "sem bancada não há medição"
    diverge_alguma = False

    for bancada in BANCADAS:
        tela = veredito_da_tela(bancada)
        arranjo = veredito_do_motor(bancada)
        bloco = relatorio_de(bancada)

        for veredito in (tela, arranjo):
            assert veredito.razao.strip(), (
                f"[{bancada.id}] a {veredito.regua} não deu razão nenhuma — "
                "régua muda não é régua medida"
            )
            for mov in veredito.movimentos:
                assert mov.origem and mov.destino, (
                    f"[{bancada.id}] a {veredito.regua} mandou mover sem nomear "
                    f"origem e destino: {mov}"
                )
                assert mov.origem != mov.destino, (
                    f"[{bancada.id}] a {veredito.regua} mandou mover um controle "
                    "para o adaptador em que ele já está"
                )
                assert _curto(mov.origem) in bloco and _curto(mov.destino) in bloco, (
                    f"[{bancada.id}] o relatório não imprime origem e destino da "
                    f"{veredito.regua}:\n{bloco}"
                )

        assert len(tela.movimentos) == bancada.tela_move, (
            f"[{bancada.id}] a régua da tela mandou mover "
            f"{len(tela.movimentos)}, e a bancada esperava {bancada.tela_move}."
            f"\n{bloco}"
        )
        assert len(arranjo.movimentos) == bancada.motor_move, (
            f"[{bancada.id}] o motor do arranjo mandou mover "
            f"{len(arranjo.movimentos)}, e a bancada esperava "
            f"{bancada.motor_move}.\n{bloco}"
        )
        for rotulo in ("origem :", "destino:", "razão  :"):
            assert bloco.count(rotulo) >= 2, (
                f"[{bancada.id}] o relatório tem de trazer '{rotulo}' das DUAS "
                f"réguas, e trouxe {bloco.count(rotulo)}:\n{bloco}"
            )
        if len(tela.movimentos) != len(arranjo.movimentos):
            diverge_alguma = True

    assert diverge_alguma, (
        "nenhuma das bancadas divergiu — ou as duas réguas são a mesma coisa "
        "(e aí a D-QUAL-REGUA-MANDA-NO-ARRANJO não tinha caso), ou a bancada "
        "não exercita a diferença. As duas leituras pedem outra bancada, não "
        "um teste verde."
    )


def test_a_regua_da_tela_enxerga_o_adaptador_vazio() -> None:
    """O achado 2, CURADO em 23/09/2026 (MOVER-UM-POR-VEZ-01)."""
    bancada = next(b for b in BANCADAS if b.id == "4-buraco-livre-noutra-controladora")
    tela = veredito_da_tela(bancada)
    arranjo = veredito_do_motor(bancada)

    assert len(tela.movimentos) == 1, "o dongle livre voltou a não existir para a tela"
    assert tela.movimentos[0].destino == DONGLE_B
    assert not any("ADAPTADOR QUE ELA NÃO VÊ" in e for e in tela.extras)
    assert len(arranjo.movimentos) == 3, (
        "o motor do arranjo enxerga o dongle vazio e enche metade dele; se "
        "deixou de enxergar, a divergência mudou de forma"
    )


def test_na_mesa_dela_a_tela_propoe_um_e_o_motor_manda_mover_dois() -> None:
    """O achado 1, remedido em 23/09/2026: quatro pontes num adaptador de duas."""
    bancada = next(b for b in BANCADAS if b.id == "1-a-mesa-dela")
    tela = veredito_da_tela(bancada)
    arranjo = veredito_do_motor(bancada)

    assert len(tela.movimentos) == 1, tela.razao
    assert tela.movimentos[0].origem == DONGLE_A
    assert len(arranjo.movimentos) == 2
    assert {m.destino for m in arranjo.movimentos} == {DONGLE_B, DONGLE_C}, (
        "o motor espalha os quatro pelos três dongles do hub dela"
    )


SCRIPT_DA_COLISAO = RAIZ / "scripts" / "check_colisao_de_sprints.py"

_SEM_O_SCRIPT_DA_COLISAO = pytest.mark.insumo_fora_do_git(
    "scripts/check_colisao_de_sprints.py"
)


def _sprint_de_papel(nome: str, arquivo: str) -> str:
    return "\n".join(
        [
            "---",
            f"sprint: {nome}",
            "posse:",
            "  A:",
            f"    - {arquivo}",
            "cria:",
            "bancada: false",
            "depois_de:",
            "nao_toca:",
            "---",
            "",
            "# o corpo, que a régua nunca lê",
            "",
        ]
    )


@_SEM_O_SCRIPT_DA_COLISAO
def test_o_achado_da_colisao_tem_linha_propria(tmp_path: Path) -> None:
    """MORDIDA. ``grep '^FALHA'`` tem de achar a colisão na saída do script."""
    assert SCRIPT_DA_COLISAO.exists(), SCRIPT_DA_COLISAO

    pasta = Path(tempfile.mkdtemp(dir=RAIZ, prefix=".colisao-de-mentira-"))
    saida = tmp_path / "saida.txt"
    try:
        (pasta / "2026-08-26-UMA-01-a-primeira.md").write_text(
            _sprint_de_papel("UMA-01", "src/hefesto_dualsense4unix/app/disputado.py"),
            encoding="utf-8",
        )
        (pasta / "2026-08-26-OUTRA-01-a-segunda.md").write_text(
            _sprint_de_papel("OUTRA-01", "src/hefesto_dualsense4unix/app/disputado.py"),
            encoding="utf-8",
        )
        for i in range(276):
            nome = f"2026-08-2{i % 10}-DIVIDA-{i:03d}-" + "e" * (10 + i % 37) + ".md"
            (pasta / nome).write_text(
                f"# uma sprint sem frontmatter, a de número {i}\n", encoding="utf-8"
            )

        with saida.open("w", encoding="utf-8") as arquivo:
            rc = subprocess.run(
                [sys.executable, str(SCRIPT_DA_COLISAO), "--pasta", str(pasta)],
                stdout=arquivo,
                stderr=arquivo,
                cwd=str(RAIZ),
                check=False,
            ).returncode
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

    texto = saida.read_text(encoding="utf-8")
    assert rc == 1, f"a colisão plantada tinha de reprovar; rc={rc}\n{texto[:2000]}"

    comecos = [linha for linha in texto.splitlines() if linha.startswith("FALHA")]
    assert len(comecos) >= 1, (
        "`grep -c '^FALHA'` devolveu ZERO numa saída que reprova com rc=1 — o "
        "achado saiu colado no fim de outra linha, e quem lê a saída não o "
        "encontra. As linhas que CONTÊM 'FALHA':\n"
        + "\n".join(
            repr(linha) for linha in texto.splitlines() if "FALHA" in linha
        )[:2000]
    )
    acusacao = next(
        (linha for linha in texto.splitlines() if " x " in linha and "UMA-01" in linha),
        "",
    )
    assert "OUTRA-01" in acusacao and "UMA-01" in acusacao, (
        "a falha não nomeia o par que colidiu:\n" + texto[:2000]
    )
    assert "disputado.py" in acusacao, "a falha não nomeia o arquivo disputado"

    indice_falha = texto.index("\nFALHA")
    indice_divida = texto.index("DÍVIDA —")
    assert indice_falha < indice_divida, (
        "a dívida foi impressa EM VOLTA da falha: o achado ficou no fim de 300 "
        "linhas de contexto, que é o mesmo defeito por outro caminho"
    )


@_SEM_O_SCRIPT_DA_COLISAO
def test_o_script_da_colisao_nao_engole_a_falha_quando_nao_ha_divida(
    tmp_path: Path,
) -> None:
    """Sem dívida nenhuma, o bloco de falha continua começando linha."""
    pasta = Path(tempfile.mkdtemp(dir=RAIZ, prefix=".colisao-de-mentira-"))
    saida = tmp_path / "saida.txt"
    try:
        (pasta / "2026-08-26-UMA-01-a-primeira.md").write_text(
            _sprint_de_papel("UMA-01", "src/hefesto_dualsense4unix/app/disputado.py"),
            encoding="utf-8",
        )
        (pasta / "2026-08-26-OUTRA-01-a-segunda.md").write_text(
            _sprint_de_papel("OUTRA-01", "src/hefesto_dualsense4unix/app/disputado.py"),
            encoding="utf-8",
        )
        with saida.open("w", encoding="utf-8") as arquivo:
            rc = subprocess.run(
                [sys.executable, str(SCRIPT_DA_COLISAO), "--pasta", str(pasta)],
                stdout=arquivo,
                stderr=arquivo,
                cwd=str(RAIZ),
                check=False,
            ).returncode
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

    texto = saida.read_text(encoding="utf-8")
    assert rc == 1, texto[:2000]
    assert any(linha.startswith("FALHA") for linha in texto.splitlines()), texto[:2000]


if __name__ == "__main__":  # pragma: no cover — a medição, sem pytest
    print(relatorio_completo())
