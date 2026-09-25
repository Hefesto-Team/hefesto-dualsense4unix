"""O diário da vigia diz o que mede: a escrita, e não a lâmpada.

O-FISICO-NASCE-ESCONDIDO-EM-QUALQUER-MAQUINA-01 (25/09/2026). Às 09:32 o
daemon carimbou `nascimento_condenado` para P2, P3 e P4 — e, no mesmo tique,
`sequestro_corrigido resultado={…: True}` para os três. O `True` quer dizer só
que o write(2) do report voltou inteiro; pelo rádio, que o BlueZ o pôs na
fila. As barras do P3 e do P4 estavam apagadas.

E ELA VIU A OUTRA METADE, às 09h50: *«o p2 tá ligado. com um verde claro ou
azul ciano»* — a cor que o Hefesto dá ao P2. O P2 também foi carimbado
condenado, com a Steam segurando o físico dele. Então o carimbo diz a
CONDIÇÃO do nascimento, e não a lâmpada; e a reescrita de cada segundo é o que
segura o P2 com a cor do Hefesto contra a Steam. Tirar o condenado da vigia
(como uma das medições recomendou) apagaria justamente o P2.

O que esta régua cobra:

1. o evento se chama `sequestro_reescrito`, a medida se chama
   `escrita_aceita`, e o nascimento condenado vai junto — nunca «corrigido»;
2. o controle condenado CONTINUA sendo reescrito, como os outros;
3. os endereços saem mascarados (as duas grafias: com e sem dois-pontos);
4. o sequestro longo deixa prova no diário (`sequestro_segue`, em 10, 100,
   1000… reescritas) — em 25/09 não havia uma linha entre 09:35 e 09:44;
5. a razão do carimbo condenado diz que a barra PODE não obedecer, pelas
   duas portas que a escrevem.

AS MORDIDAS, medidas: devolver o nome `sequestro_corrigido` reprova a 1; tirar
o condenado do `reafirmar` reprova a 2; tirar o `_endereco_mascarado` das
chaves reprova a 3; tirar o laço dos marcos reprova a 4; devolver a frase de
antes a qualquer das duas portas reprova a 5.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import structlog

from hefesto_dualsense4unix.core import escritor_cru as ec
from hefesto_dualsense4unix.daemon import connection as conn
from hefesto_dualsense4unix.integrations import sinal_da_barra as sdb
from hefesto_dualsense4unix.integrations.sinal_da_barra import (
    CONFIANCA_LIMPA,
    CONFIANCA_SUSPEITA,
    CartorioDoNascimento,
    Instancia,
    Leitura,
)

NO_2 = "/dev/hidraw6"
NO_3 = "/dev/hidraw8"
STEAM = 44275

#: Faixa forjada (aa:bb:cc), com os octetos 4 e 5 DIFERENTES de zero: é o que
#: prova a máscara — eles têm de sair zerados.
MAC_2 = "aa:bb:cc:12:34:02"
UNIQ_2 = "aabbcc123402"
MAC_3 = "aa:bb:cc:12:34:03"
UNIQ_3 = "aabbcc123403"


class _Mesa:
    """O /proc e o /dev de mentira: a Steam segura os dois físicos."""

    def __init__(self) -> None:
        self.donos = {NO_2: [STEAM], NO_3: [STEAM]}

    def sonda(self, nos: Any) -> dict[str, list[int]]:
        return {n: list(p) for n, p in self.donos.items() if n in set(nos)}

    @staticmethod
    def alcancavel(_no: str) -> bool:
        return False

    @staticmethod
    def vivo(pid: int) -> bool:
        return pid == STEAM

    @staticmethod
    def firma(no: str) -> tuple[int, int]:
        return (int(no.rsplit("hidraw", 1)[-1]), 0)


class _Controle:
    """Como o backend responde: a chave é a DELE (com dois-pontos), e o valor é
    o que a escrita devolveu — não um `True` de fábrica por uniq pedido."""

    def __init__(self) -> None:
        self.reescritos: list[list[str]] = []

    @staticmethod
    def nos_hidraw_por_uniq() -> dict[str, str]:
        return {UNIQ_2: NO_2, UNIQ_3: NO_3}

    def reafirmar_barra_e_numero(self, uniqs: list[str]) -> dict[str, bool]:
        self.reescritos.append(list(uniqs))
        chaves = {UNIQ_2: MAC_2, UNIQ_3: MAC_3}
        return {chaves[u]: True for u in uniqs}


def _cartorio(*condenados: str) -> CartorioDoNascimento:
    cartorio = CartorioDoNascimento()
    leituras = []
    for uniq, mac, inst in ((UNIQ_2, MAC_2, "000C"), (UNIQ_3, MAC_3, "000E")):
        alvo = Instancia(
            instancia=inst, uniq=mac, adaptador="aa:bb:cc:00:00:ce", hw_version="0x0811",
            input_n=None, hidraw=NO_2 if uniq == UNIQ_2 else NO_3, transporte="bt",
        )
        condenado = uniq in condenados
        leituras.append(
            Leitura(
                alvo=alvo,
                confianca=CONFIANCA_SUSPEITA if condenado else CONFIANCA_LIMPA,
                porque="teste",
                pids_do_escritor=(STEAM,) if condenado else (),
            )
        )
    cartorio.observar([leitura.alvo for leitura in leituras], 0.0)
    cartorio.carimbar(leituras, 0.0)
    return cartorio


def _daemon(controle: _Controle, cartorio: CartorioDoNascimento) -> SimpleNamespace:
    async def _run_blocking(fn: Any, *args: Any) -> Any:
        return fn(*args)

    mesa = _Mesa()
    daemon = SimpleNamespace(
        controller=controle,
        _run_blocking=_run_blocking,
        is_native_mode=lambda: False,
        _cartorio_do_nascimento=cartorio,
    )
    daemon._vigia_do_sequestro = ec.VigiaDoSequestro(
        sonda=mesa.sonda, alcancavel=mesa.alcancavel, vivo=mesa.vivo, firma=mesa.firma
    )
    return daemon


def _rodar(daemon: SimpleNamespace, passos: int) -> list[dict[str, Any]]:
    async def _roteiro() -> list[dict[str, Any]]:
        with structlog.testing.capture_logs() as registros:
            for i in range(passos):
                await conn.vigiar_o_sequestro(daemon, agora=float(i))
        return registros

    return asyncio.run(_roteiro())


def test_o_diario_diz_escrita_aceita_e_o_nascimento_condenado() -> None:
    """A mesa das 09:32, com um condenado (o P3 aqui)."""
    daemon = _daemon(_Controle(), _cartorio(UNIQ_3))
    registros = _rodar(daemon, 1)
    eventos = [r["event"] for r in registros]
    assert "sequestro_corrigido" not in eventos, eventos
    linha = next(r for r in registros if r["event"] == "sequestro_reescrito")
    assert linha["escrita_aceita"] == {"aa:bb:cc:00:00:02": True, "aa:bb:cc:00:00:03": True}
    assert linha["nascimento_condenado"] == ["aa:bb:cc:00:00:03"]


def test_sem_condenado_o_campo_nao_aparece() -> None:
    daemon = _daemon(_Controle(), _cartorio())
    linha = next(r for r in _rodar(daemon, 1) if r["event"] == "sequestro_reescrito")
    assert "nascimento_condenado" not in linha, linha


def test_o_condenado_continua_sendo_reescrito() -> None:
    """O P2 de 25/09: condenado, e com a barra na cor do Hefesto.

    É a reescrita de cada segundo que o segura ali contra a Steam; um
    condenado fora da vigia seria entregue a ela.
    """
    controle = _Controle()
    _rodar(_daemon(controle, _cartorio(UNIQ_2, UNIQ_3)), 3)
    assert controle.reescritos == [[UNIQ_2, UNIQ_3]] * 3


def test_nenhum_endereco_inteiro_no_diario() -> None:
    """As duas grafias do mesmo controle saíam inteiras; a máscara zera 4 e 5."""
    daemon = _daemon(_Controle(), _cartorio(UNIQ_3))
    texto = repr(_rodar(daemon, 1))
    for inteiro in ("12:34", "1234", UNIQ_2, UNIQ_3):
        assert inteiro not in texto, texto
    linha = next(r for r in _rodar(_daemon(_Controle(), _cartorio()), 1)
                 if r["event"] == "sequestro_reescrito")
    assert linha["uniqs"] == ["aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03"]


def test_o_sequestro_longo_deixa_prova_nos_marcos() -> None:
    """Doze segundos de Steam segurando: UMA linha aos dez, por nó."""
    registros = _rodar(_daemon(_Controle(), _cartorio()), 12)
    segue = [r for r in registros if r["event"] == "sequestro_segue"]
    assert sorted(r["no"] for r in segue) == [NO_2, NO_3], segue
    assert all(r["reescritas"] == 10 and r["pids"] == [STEAM] for r in segue), segue
    assert conn.MARCOS_DA_REESCRITA[:3] == (10, 100, 1_000)


def _alvo_do_radio() -> Instancia:
    return Instancia(
        instancia="000E", uniq=MAC_3, adaptador="aa:bb:cc:00:00:ce", hw_version="0x0811",
        input_n=None, hidraw=NO_3, transporte="bt",
    )


def test_o_carimbo_nao_afirma_a_lampada_pelas_duas_portas() -> None:
    """A razão do condenado dizia «a barra não obedece, e só a reconexão devolve».

    O P2 de 25/09 desmentiu as duas metades: condenado, e com a barra na cor
    do Hefesto, sem reconectar. As duas portas que escrevem a razão — o diário
    lido (`veredito_do_nascimento`) e a sonda do próprio daemon (`carimbar`
    com `nos_segurados`) — passam a dizer que PODE não obedecer.
    """
    alvo = _alvo_do_radio()
    pelo_diario = sdb.veredito_do_nascimento(
        instancias=[alvo],
        nascimentos={
            "000e": sdb.Nascimento(
                instancia="000E", quando=0.0, no=NO_3, transporte="bt",
                escritor=(STEAM,), sujo=True,
            )
        },
    )[0]
    cartorio = CartorioDoNascimento()
    cartorio.observar([], 0.0)
    cartorio.observar([alvo], 1.0)
    pela_sonda = cartorio.carimbar(
        [Leitura(alvo=alvo, confianca=CONFIANCA_LIMPA, porque="limpa")], 1.2,
        nos_segurados={NO_3},
    )[0].leitura
    for leitura in (pelo_diario, pela_sonda):
        assert leitura.pede_reconexao, leitura
        assert "pode não obedecer" in leitura.porque, leitura.porque
        assert "a barra não obedece" not in leitura.porque, leitura.porque
        assert "só a reconexão" not in leitura.porque, leitura.porque
