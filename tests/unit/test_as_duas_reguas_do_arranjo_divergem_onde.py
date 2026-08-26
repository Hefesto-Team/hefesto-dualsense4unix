"""AS DUAS RÉGUAS DO ARRANJO, RODADAS LADO A LADO — e onde elas divergem.

Ela decidiu em 25/08/2026 (``docs/data/decisoes-dela.csv``,
``D-QUAL-REGUA-MANDA-NO-ARRANJO``): *"MEDIR AS DUAS ANTES DE ESCOLHER. Um teste
comparativo roda as duas sobre a mesma bancada e mostra onde divergem; a escolha
vem depois, com o caso na mão."* **Este arquivo é essa medição. A ESCOLHA é
dela, e não está aqui.**

AS DUAS RÉGUAS RESPONDEM À MESMA PERGUNTA — *"qual controle move para qual
adaptador"* — e nenhum arquivo da árvore as rodava juntas:

``plano_de_radio.ordem_de_redistribuicao``
    **Já está na tela**, publicada por ``app/actions/config/secao_orcamento.py``
    (a seção Desempenho). Manda mover **no máximo um** controle, e só quando as
    duas condições se juntam: um adaptador passou do corte da "Apertada"
    (``fracao_total > 0,85``) **e** existe outro adaptador que continua fora da
    "Cheia" depois de receber. Qual controle: o que carrega microfone, porque é
    o mais caro.

``arranjo_da_mesa.plano_dos_controles``
    Portada byte a byte do mockup dela em 25/08/2026, **sem tela nenhuma que a
    consuma**. Devolve o destino de **todos** os controles, e move quantos forem
    preciso enquanto isso **baixar o pico** do adaptador mais cheio. Corte
    nenhum: ela rebalanceia mesa folgada.

COMO LER A MEDIÇÃO, sem pytest e sem procurar traceback::

    .venv/bin/python tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py

Ela imprime as seis bancadas, caso a caso, com origem, destino e a razão de cada
régua. Sob pytest o mesmo relatório sai com ``-s``.

O QUE A MEDIÇÃO ACHOU. São QUATRO, e os quatro estão nas bancadas abaixo. **Os
três primeiros aparecem NA TELA DELA hoje**, e nenhum deles é opinião:

  1. **Na mesa cheia desta casa a régua da tela cala e a outra manda mover
     dois.** Quatro controles com microfone no mesmo adaptador somam 1.106,8 de
     1.600 fatias — fração 0,69, abaixo do corte 0,85 —, então
     ``ordem_de_redistribuicao`` não diz nada, e ``plano_dos_controles``
     redistribui os quatro pelos três dongles do hub dela (bancada 1).

  2. **A régua da tela não enxerga adaptador VAZIO, e a frase que ela publica
     nesse estado é FALSA.** ``plano_por_adaptador`` só produz um
     ``PlanoDoAdaptador`` para adaptador que TEM controle conectado: um dongle
     livre noutra controladora PCI simplesmente não existe para ela. Com o
     adaptador carregado acima do corte e nenhum candidato à vista, a seção cai
     no ``elif _algum_apertado(planos)`` de ``secao_orcamento.py:760`` e imprime
     ``FRASE_DO_ADAPTADOR_UNICO`` — *"Todos os controles estão no mesmo
     adaptador, e é o único que você tem"* — com um segundo adaptador vazio na
     mesa (bancada 4). A mesma frase sai com DOIS adaptadores cheios e os
     controles divididos entre eles (bancada 6), onde ela é falsa nas duas
     metades. **Isto é conserto de arquivo alheio: está relatado, não curado.**

  3. **A ordem de serviço manda mover de "Adaptador sem nome" para "Adaptador
     sem nome".** Com dois dongles que ela ainda não apelidou, os dois caem no
     mesmo :data:`plano_de_radio.ADAPTADOR_SEM_NOME`, e a frase de
     ``ganho_esperado`` nomeia origem e destino com a MESMA palavra — a tela
     manda mover um controle sem dizer para onde (bancada 3). Também relatado,
     não curado: a frase mora em ``plano_de_radio.py``.

  4. **As duas discordam da PALAVRA, não só do movimento.** Seis controles num
     adaptador dão 1.562,4 de 1.600: a régua da tela chama isso de "Cheia"
     (corte 85%) e ``PlanoDosControles.cabe`` responde ``True`` (corte 100%).
     Duas respostas para "cabe?" na mesma mesa, e é o caso da bancada 5.

O LIMITE DESTA RÉGUA, DECLARADO: as bancadas são SINTÉTICAS. O ``/sys/class/
hidraw`` é de mentira (``_sysfs_de_mentira``) justamente para o teste não medir
a bancada de quem o roda — é a armadilha "medir contra a biblioteca errada"
entrando pela porta do sysfs. Nenhum aparelho é tocado, nenhum daemon é ouvido.

---

E MAIS UM PORTÃO, no mesmo arquivo por posse de leva e não por assunto:
``test_o_achado_da_colisao_tem_linha_propria`` cobra a saída de
``scripts/check_colisao_de_sprints.py``. Ver o docstring dele.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import plano_de_radio
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    CORTE_APERTADA,
    SLOTS_POR_SEGUNDO,
)

RAIZ = Path(__file__).resolve().parents[2]

#: Endereços da FAIXA DA CASA (`e8:47:3a`, `aa:bb:cc`), octetos 4 e 5 zerados.
#: Nada de MAC real em arquivo versionado — há dois portões, e um pega por FORMA.
DONGLE_A = "e8:47:3a:00:00:09"
DONGLE_B = "e8:47:3a:00:00:15"
DONGLE_C = "e8:47:3a:00:00:21"
CONTROLES = tuple(f"aa:bb:cc:00:00:{n:02d}" for n in range(1, 11))


# ═══════════════════════════════════════════════════════════════════════════
# 1. A BANCADA SINTÉTICA — uma só, e as DUAS réguas comem dela
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Posto:
    """Um controle, o adaptador em que ele JÁ está, e se o microfone está de pé."""

    nome: str
    endereco: str
    onde: str
    mic: bool


@dataclass(frozen=True)
class Bancada:
    """Uma mesa de mentira, e o que se espera de cada régua sobre ela.

    Os dois campos de expectativa não são enfeite: são a MORDIDA. Uma régua
    neutralizada — que devolva "não mexo em nada" sempre — passaria num teste
    que só conferisse rótulos, e "régua que não vê nada passa sempre" é o
    defeito que esta casa já pagou três vezes.
    """

    id: str
    titulo: str
    adaptadores: tuple[str, ...]
    postos: tuple[Posto, ...]
    #: quantos controles a `ordem_de_redistribuicao` manda mover (ela move 0 ou 1)
    tela_move: int
    #: quantos controles o `plano_dos_controles` manda mover
    motor_move: int
    nota: str = ""


def _postos(quantos: int, onde: str, *, mic: bool, desde: int = 0) -> tuple[Posto, ...]:
    return tuple(
        Posto(nome=f"Jogador {i + 1}", endereco=CONTROLES[i], onde=onde, mic=mic)
        for i in range(desde, desde + quantos)
    )


#: As seis bancadas. As quatro que ela pediu são a 1, a 2, a 4 e a 5; a 3 e a 6
#: entraram porque sem elas a régua da tela nunca é vista MANDANDO mover, e um
#: teste em que ela cala em todas as bancadas passaria com ela arrancada.
BANCADAS: tuple[Bancada, ...] = (
    Bancada(
        id="1-a-mesa-dela",
        titulo=(
            "a mesa dela: três adaptadores no mesmo hub, quatro controles com "
            "microfone, todos no primeiro"
        ),
        adaptadores=(DONGLE_A, DONGLE_B, DONGLE_C),
        postos=_postos(4, DONGLE_A, mic=True),
        tela_move=0,
        motor_move=2,
        nota=(
            "a mesa cheia desta casa (co-op de quatro, microfone de pé em todos) "
            "dá 1.106,8 de 1.600 fatias, fração 0,69 — ABAIXO do corte 0,85"
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
        postos=_postos(6, DONGLE_A, mic=False) + _postos(1, DONGLE_B, mic=False, desde=6),
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
        postos=_postos(6, DONGLE_A, mic=False),
        tela_move=0,
        motor_move=3,
        nota=(
            "adaptador sem controle NÃO existe para a régua da tela — e é aqui "
            "que a tela publica a frase falsa do adaptador único"
        ),
    ),
    Bancada(
        id="5-sem-ordem-possivel",
        titulo="sem ordem possível: seis controles e um adaptador só na mesa",
        adaptadores=(DONGLE_A,),
        postos=_postos(6, DONGLE_A, mic=False),
        tela_move=0,
        motor_move=0,
        nota="as duas CONVERGEM: não há para onde mover, e as duas calam",
    ),
    Bancada(
        id="6-dois-cheios",
        titulo="dois adaptadores, ambos na Cheia: cinco controles com microfone em cada",
        adaptadores=(DONGLE_A, DONGLE_B),
        postos=_postos(5, DONGLE_A, mic=True) + _postos(5, DONGLE_B, mic=True, desde=5),
        tela_move=0,
        motor_move=0,
        nota=(
            "convergem no movimento — e a tela publica a frase do adaptador "
            "único com DEZ controles em DOIS adaptadores"
        ),
    ),
)


def _sysfs_de_mentira(postos: tuple[Posto, ...]) -> dict[str, Any]:
    """Um ``/sys/class/hidraw`` de papel: ``{uniq do controle: MAC do adaptador}``.

    Sem isto a régua da tela leria o sysfs da máquina de quem roda o teste, e a
    medição diria mais sobre a bancada de quem roda que sobre as duas réguas.
    """
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


# ═══════════════════════════════════════════════════════════════════════════
# 2. AS DUAS RÉGUAS, CADA UMA NO SEU VEREDITO
# ═══════════════════════════════════════════════════════════════════════════


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
    """A régua que JÁ está na tela — ``plano_de_radio.ordem_de_redistribuicao``.

    Nada de ``try``/``except`` aqui, e é de propósito: se a régua levantar, o
    teste tem de REPROVAR. Engolir a exceção transformaria "a régua quebrou" em
    "a régua não viu nada", que é exatamente a leitura que faz uma régua morta
    parecer uma régua calma.
    """
    estado = [
        {
            "transport": "bt",
            "connected": True,
            "uniq": _sem_dois_pontos(posto.endereco),
            "player_slot": i + 1,
        }
        for i, posto in enumerate(bancada.postos)
    ]
    planos = plano_de_radio.plano_por_adaptador(
        estado,
        com_ponte_de_mic=[
            _sem_dois_pontos(p.endereco) for p in bancada.postos if p.mic
        ],
        **_sysfs_de_mentira(bancada.postos),
    )
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)

    vistos = tuple(
        f'{_curto(e)}: {p.agora.controles} controle(s), '
        f"{_num(p.agora.slots_total)} de {p.agora.slots_teto} fatias "
        f"(fração {_num(p.agora.fracao_total * 100)}%, \"{p.agora.rotulo}\")"
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
        # É literalmente o `elif _algum_apertado(planos)` de secao_orcamento.py:760.
        vistos += (
            "A TELA IMPRIME: " + plano_de_radio.FRASE_DO_ADAPTADOR_UNICO,
        )

    if ordem is None:
        if not planos:
            razao = "nenhum controle no rádio: não há o que arranjar"
        elif not apertados:
            maior = max(p.agora.fracao_total for p in planos.values())
            razao = (
                f"nenhum adaptador passou do corte da \"Apertada\" "
                f"({_num(CORTE_APERTADA * 100)}%): o mais carregado está em "
                f"{_num(maior * 100)}%"
            )
        else:
            razao = (
                "há adaptador acima do corte, mas nenhum OUTRO adaptador "
                "conhecido continuaria fora da \"Cheia\" depois de receber"
            )
        return Veredito("régua da tela", (), razao, vistos)

    if ordem.origem_na_tela == ordem.destino_na_tela:
        # ACHADO 3: sem apelido, os dois adaptadores viram a mesma palavra, e a
        # ordem de serviço manda mover sem dizer para onde. Ver o cabeçalho.
        vistos += (
            "A TELA MANDA MOVER DE "
            f'"{ordem.origem_na_tela}" PARA "{ordem.destino_na_tela}" — o mesmo '
            "nome nas duas pontas, porque nenhum dos dois tem apelido dela",
        )

    return Veredito(
        regua="régua da tela",
        movimentos=(
            Movimento(
                quem=(
                    "um controle COM microfone (o mais caro)"
                    if ordem.move_com_microfone
                    else "um controle SEM microfone"
                ),
                origem=ordem.origem,
                destino=ordem.destino,
            ),
        ),
        razao=f"{ordem.por_que_importa} {ordem.ganho_esperado}",
        extras=(*vistos, f"o que ela viu: {ordem.o_que_eu_vi}"),
    )


def veredito_do_motor(bancada: Bancada) -> Veredito:
    """A régua portada do mockup — ``arranjo_da_mesa.plano_dos_controles``.

    Sem ``try``/``except``, pela mesma razão de :func:`veredito_da_tela`.
    """
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

    # O pico ANTES sai da bancada, não de uma segunda régua: é a soma dos custos
    # de cada controle no adaptador em que ele já estava.
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


# ═══════════════════════════════════════════════════════════════════════════
# 3. O RELATÓRIO — a divergência caso a caso, e em português
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# 4. A MORDIDA
# ═══════════════════════════════════════════════════════════════════════════


def test_a_divergencia_esta_nomeada() -> None:
    """MORDIDA. Cada bancada nomeia origem, destino e razão DE CADA RÉGUA.

    E as contagens de movimento são conferidas contra o que a bancada declara:
    é isso que impede uma régua neutralizada — a que devolve "não mexo em nada"
    sempre — de passar. Se qualquer uma das duas levantar exceção, o teste
    reprova aqui mesmo: :func:`veredito_da_tela` e :func:`veredito_do_motor`
    não têm ``except``.
    """
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


def test_a_regua_da_tela_nao_enxerga_adaptador_vazio() -> None:
    """O achado 2, isolado: um dongle livre não existe para a régua da tela.

    É o que faz a seção Desempenho publicar *"é o único que você tem"* com um
    segundo adaptador na mesa. Conserto é em ``plano_de_radio.py`` e em
    ``secao_orcamento.py``, que NÃO são posse desta frente: está relatado.
    """
    bancada = next(b for b in BANCADAS if b.id == "4-buraco-livre-noutra-controladora")
    tela = veredito_da_tela(bancada)
    arranjo = veredito_do_motor(bancada)

    assert tela.movimentos == (), (
        "a régua da tela passou a ver o adaptador vazio — se isso é conserto, "
        "atualize o achado 2 do cabeçalho em vez de apagar o teste"
    )
    assert any("ADAPTADOR QUE ELA NÃO VÊ" in e for e in tela.extras)
    assert any(plano_de_radio.FRASE_DO_ADAPTADOR_UNICO in e for e in tela.extras), (
        "a tela deixou de publicar a frase do adaptador único neste estado"
    )
    assert len(arranjo.movimentos) == 3, (
        "o motor do arranjo enxerga o dongle vazio e enche metade dele; se "
        "deixou de enxergar, a divergência mudou de forma"
    )


def test_na_mesa_dela_a_tela_cala_e_o_motor_manda_mover() -> None:
    """O achado 1, isolado: co-op de quatro com microfone não passa do corte."""
    bancada = next(b for b in BANCADAS if b.id == "1-a-mesa-dela")
    tela = veredito_da_tela(bancada)
    arranjo = veredito_do_motor(bancada)

    assert tela.movimentos == ()
    assert "corte" in tela.razao, tela.razao
    assert len(arranjo.movimentos) == 2
    assert {m.destino for m in arranjo.movimentos} == {DONGLE_B, DONGLE_C}, (
        "o motor espalha os quatro pelos três dongles do hub dela"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. O OUTRO PORTÃO DESTA FRENTE — a colisão de posse tem de ser LEGÍVEL
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DA_COLISAO = RAIZ / "scripts" / "check_colisao_de_sprints.py"


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


def test_o_achado_da_colisao_tem_linha_propria(tmp_path: Path) -> None:
    """MORDIDA. ``grep '^FALHA'`` tem de achar a colisão na saída do script.

    O DEFEITO, medido em 26/08/2026 na árvore de verdade: a lista de DÍVIDA ia
    para o ``stdout`` e o bloco de falha para o ``stderr``. Fundidos no mesmo
    destino (``> saída 2>&1``, que é o que o CI e o gancho fazem), o ``stdout``
    ganha buffer de bloco e o ``stderr`` não — o ``FALHA:`` era escrito no meio
    de uma descarga parcial e saía **colado no fim de um nome de arquivo**, na
    linha 269, no meio de 276 linhas de dívida. ``grep -c '^FALHA'`` devolvia
    **zero** sobre uma saída que reprovava com rc=1.

    A bancada reproduz o estado inteiro: duas sprints colidindo **mais** 300 de
    dívida, que é o que enche o buffer. O ``tmp_path`` do pytest não serve
    sozinho — ``carrega()`` faz ``relative_to(RAIZ)`` —, então a pasta de mentira
    nasce DENTRO da raiz e é apagada no ``finally``.
    """
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
        # A DÍVIDA, e sem ela o defeito não aparece: é ela que enche o buffer
        # do `stdout` a ponto de ele descarregar NO MEIO de uma linha. São
        # **276** porque 276 é o número que a árvore de verdade tinha em
        # 26/08/2026, quando o `FALHA:` saiu na linha 269 colado num nome de
        # arquivo. Os nomes têm comprimento variado pela mesma razão.
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
    # O par sai ordenado pelo CAMINHO do arquivo, não pelo nome da sprint: por
    # isso a régua cobra os dois nomes e o arquivo, nunca uma ordem.
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
