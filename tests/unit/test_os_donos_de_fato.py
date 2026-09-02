"""ROTA-A + ROTA-C — os donos de fato, e as cinco réguas que têm de morder.

O defeito que estas réguas guardam foi medido em 02/09/2026 com DOIS controles
na mesa dela:

* **o nome vinha da POSIÇÃO.** Com um controle, o do cabo chamava-se "Starlight
  Blue"; com dois, o MESMO cabo virou "Cosmic Red". O daemon publicava `uniq`,
  `transport`, `battery_pct`, `player`, `player_slot`, `lightbar_*`, `inputs`,
  `audio`, `speaker` e `vpad_*` — e NADA que dissesse qual aparelho é aquele;
* **o HTML lia UMA chave onde a GTK lia DUAS.** `player_slot` aparece 6 vezes
  em `app/` e UMA em `interface/pacotes/`; `vpad_motivo`, 1 e ZERO.

FIXTURES: faixa sintética `02:fe:00` da casa e endereços com os octetos 4 e 5
zerados. Nenhum endereço real entra em arquivo versionado, e há dois portões
que reprovam.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pacotes

#: Os dois da mesa dela, com a máscara da casa. O `AZUL` está no RÁDIO e é o
#: primário; o `VERMELHO` está no CABO e NÃO é jogador do co-op — é a
#: configuração exata que derrubou o fato "no rádio o player volta None".
AZUL = "aabbcc000001"
VERMELHO = "aabbcc000002"


def _controle(
    uniq: str,
    **extras: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {"uniq": uniq, "connected": True, "transport": "usb"}
    base.update(extras)
    return base


# ---------------------------------------------------------------------------
# RÉGUA 3 — o caso que motivou tudo, escrito SOZINHO
# ---------------------------------------------------------------------------
def test_o_controle_que_nao_e_jogador_ainda_tem_numero() -> None:
    """`{"player": None, "player_slot": 2}` é jogador **2**.

    Fora de qualquer `parametrize` de propósito: é o caso medido na mesa dela e
    ele não pode se perder numa lista de tuplas onde ninguém o lê.

    **E O FATO QUE ELE DERRUBA:** o MAPA e a ROTA-C diziam *"no rádio o `player`
    volta None"*. Não é o transporte — este dicionário é o do controle no CABO.
    Ver `daemon/subsystems/coop.CoopManager.player_indexes`: só entra quem o
    jogo enxerga, e um secundário aguardando o grab não é jogador nenhum.
    """
    assert pacotes.jogador_de({"player": None, "player_slot": 2}) == 2


def test_o_primario_no_radio_tem_as_duas_chaves_e_elas_coincidem() -> None:
    """A outra metade da mesma medição, para o par ficar completo no arquivo."""
    assert pacotes.jogador_de({"player": 1, "player_slot": 1}) == 1


class TestJogadorDe:
    def test_sem_chave_nenhuma_cala(self) -> None:
        assert pacotes.jogador_de({}) is None

    def test_as_duas_none_calam(self) -> None:
        assert pacotes.jogador_de({"player": None, "player_slot": None}) is None

    def test_zero_nao_e_jogador(self) -> None:
        """Slot zero é ausência escrita como número, e numerar "P0" é mentir."""
        assert pacotes.jogador_de({"player_slot": 0, "player": 0}) is None

    def test_o_slot_vence_o_player(self) -> None:
        """A ordem é a da GTK, e ela importa quando os dois existem e divergem."""
        assert pacotes.jogador_de({"player_slot": 3, "player": 1}) == 3

    def test_lixo_no_slot_cai_para_o_player_em_vez_de_estourar(self) -> None:
        assert pacotes.jogador_de({"player_slot": "não sei", "player": 2}) == 2

    def test_nao_olha_a_posicao(self) -> None:
        """`index` é POSIÇÃO. A GTK cai nele; esta função NUNCA.

        `app/actions/base.numero_do_controle` devolve `index + 1` quando não há
        slot — e é essa queda que fez o mesmo controle mudar de nome quando o
        segundo entrou na mesa. Aqui a resposta honesta é `None`.
        """
        assert pacotes.jogador_de({"index": 1}) is None


def test_a_ordem_das_chaves_e_a_mesma_da_gtk() -> None:
    """Se a GTK mudar a ordem dela, ESTA régua reprova — as duas mudam juntas.

    `base.numero_do_controle` é o dono da regra do outro lado. Ele lê
    `player_slot` PRIMEIRO; se alguém inverter lá e não aqui, a mesma mesa
    passa a ter dois números para o mesmo controle — que é o defeito que
    aquela função nasceu para curar.
    """
    from hefesto_dualsense4unix.app.actions.base import numero_do_controle

    assert numero_do_controle({"player_slot": 3, "player": 1, "index": 9}) == 3
    assert pacotes.jogador_de({"player_slot": 3, "player": 1, "index": 9}) == 3


# ---------------------------------------------------------------------------
# RÉGUAS 1 e 2 — a identidade não olha a posição, e `None` vira travessão
# ---------------------------------------------------------------------------
class TestIdentidadeDe:
    def test_o_nome_acompanha_o_uniq_e_nao_o_indice(self) -> None:
        """RÉGUA 1: dois controles em ordem TROCADA, e o nome não troca.

        É a reprodução direta do que ela viu: com um controle o do cabo era
        "Starlight Blue"; com dois, o MESMO cabo virou "Cosmic Red".
        """
        azul = _controle(AZUL, modelo="Starlight Blue", transport="bt", index=0)
        vermelho = _controle(VERMELHO, modelo="Cosmic Red", index=1)

        na_ordem = [pacotes.identidade_de(c) for c in (azul, vermelho)]
        trocados = [pacotes.identidade_de(c) for c in (vermelho, azul)]

        assert na_ordem == ["Starlight Blue", "Cosmic Red"]
        assert trocados == ["Cosmic Red", "Starlight Blue"]

    def test_o_que_ela_nomeou_vence_o_modelo(self) -> None:
        assert (
            pacotes.identidade_de(
                _controle(AZUL, nome_declarado="O do sofá", modelo="Cosmic Red")
            )
            == "O do sofá"
        )

    def test_sem_modelo_sobra_o_transporte_e_nunca_um_padrao(self) -> None:
        """RÉGUA 2: `None` não vira nome de outro aparelho.

        A tabela `NOMES_DE_FABRICA` tem vinte e uma entradas e a Sony fabrica
        edições novas sem avisar. "White" como default poria na tela um aparelho
        que ninguém mediu.
        """
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            NOMES_DE_FABRICA,
        )

        dito = pacotes.identidade_de(_controle(AZUL, modelo=None, transport="bt"))
        assert dito == "BT"
        assert dito not in set(NOMES_DE_FABRICA.values())

    def test_sem_nada_e_travessao(self) -> None:
        assert pacotes.identidade_de({"uniq": AZUL}) == "—"

    def test_a_mesa_e_a_terceira_porta_do_mesmo_fato(self) -> None:
        """O caminho que funciona HOJE, antes de o daemon dela ser reiniciado."""
        assert (
            pacotes.identidade_de(
                _controle(AZUL, transport="bt"),
                [{"uniq": AZUL, "nome": "Starlight Blue"}],
            )
            == "Starlight Blue"
        )

    def test_o_nao_sei_da_mesa_nao_vira_nome(self) -> None:
        """"Não sei" é ausência de leitura. "Não sei · USB" seria pior que "USB"."""
        assert (
            pacotes.identidade_de(_controle(AZUL), [{"uniq": AZUL, "nome": "Não sei"}])
            == "USB"
        )

    def test_a_mesa_do_vizinho_nao_respinga(self) -> None:
        assert (
            pacotes.identidade_de(
                _controle(AZUL), [{"uniq": VERMELHO, "nome": "Cosmic Red"}]
            )
            == "USB"
        )


def test_o_nao_sei_da_mesa_e_o_mesmo_texto_das_duas_bandas() -> None:
    """A literal repetida em `pacotes` tem de ser a MESMA do `mesa_viva`.

    Duas cópias de uma string de comparação é o defeito clássico desta casa: uma
    delas muda, a comparação para de casar em silêncio, e "Não sei" volta a
    passar por nome de aparelho.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    assert pacotes.NOME_SEM_LEITURA == mesa_viva.COR_DESCONHECIDA


# ---------------------------------------------------------------------------
# A leitura de DUAS chaves que o HTML tinha perdido inteira
# ---------------------------------------------------------------------------
class TestDegradacaoDe:
    def test_uinput_com_motivo_acende_a_frase_leiga(self) -> None:
        dito = pacotes.degradacao_de(
            {"vpad_backend": "uinput", "vpad_motivo": "uhid_indisponivel"}
        )
        assert dito == (
            "Emulação degradada (uinput): o modo completo não está disponível "
            "neste sistema"
        )

    def test_uinput_sem_motivo_e_a_mascara_xbox_e_nao_defeito(self) -> None:
        assert pacotes.degradacao_de({"vpad_backend": "uinput", "vpad_motivo": None}) == ""

    def test_uhid_nao_diz_nada(self) -> None:
        assert pacotes.degradacao_de({"vpad_backend": "uhid", "vpad_motivo": "sem_uhid"}) == ""

    def test_delega_e_nao_copia_a_tabela_de_motivos(self) -> None:
        """Se a GTK trocar a frase, esta função tem de trocar junto.

        Uma cópia da tabela aqui seria uma segunda lista de motivos, que
        envelheceria calada no primeiro motivo novo do daemon.
        """
        from hefesto_dualsense4unix.app.widgets import controller_card

        entrada = {"vpad_backend": "uinput", "vpad_motivo": "sem_uhid"}
        assert pacotes.degradacao_de(entrada) == controller_card.texto_degradacao(entrada)


# ---------------------------------------------------------------------------
# RÉGUA 4 — nenhum pacote lê `.get("player")` cru
# ---------------------------------------------------------------------------
#: AS EXCEÇÕES, DATADAS (02/09/2026) E COM A RAZÃO. Esta lista existe para a
#: próxima leva ZERÁ-LA: os donos nasceram hoje e as abas ainda não migraram —
#: dez frentes estão dentro dos `aNN_*.py` neste momento e mudá-los aqui seria
#: conflito garantido.
#:
#: `a05_vibracao.py:52` é diferente das outras TRÊS e não se resolve com
#: `jogador_de`: ali o dicionário não é um controle, é uma entrada de
#: `rumble_ff.per_vpad`, cuja chave `player` é o número do GAMEPAD VIRTUAL.
#: Trocá-la por `player_slot` casaria o vpad errado.
#: ATUALIZADA NA INTEGRAÇÃO DE 02/09/2026, e a dívida CAIU de sete para três.
#: As quatro que morreram (`a01_jogar.py:48`, `a04_iluminacao.py:89`, `:90` e
#: `:221`) morreram porque as frentes das abas 01 e 04 migraram para os donos na
#: MESMA leva — o `or 1` do `:221`, que era POSIÇÃO disfarçada de default, foi
#: junto. As três que sobram mudaram só de LINHA, e as razões são as mesmas.
#:
#: A ÂNCORA POR `arquivo:linha` É FRÁGIL DE PROPÓSITO: uma exceção que se mexe
#: tem de ser reconferida, e foi assim que esta lista revelou, no merge, que
#: metade dela já não existia. O preço é reescrevê-la a cada leva que toca os
#: pacotes; o ganho é que ela não guarda fantasma.
EXCECOES_DATADAS: dict[str, str] = {
    "a05_vibracao.py:82": (
        "NÃO é controle: casa a entrada de `rumble_ff.per_vpad` pelo número do vpad"
    ),
    "a05_vibracao.py:376": "lê o `player` do controle para casar com o vpad acima; migra junto",
    # A LINHA ANDOU DE 413 PARA 638 e DE 638 PARA 768 em 02/09/2026 — o pacote
    # ganhou `_tinta`, `TIRA_APAGADA`, `desenho_da_luz`, `_so_abriu_o_seletor`,
    # `o_coop_manda` e `dica_da_luz`. A leitura continua sendo a mesma: o
    # `player` do CLIQUE.
    #
    # ESTA LISTA COBRA ARQUIVO:LINHA, e por isso ela reprova toda vez que um
    # pacote CRESCE — sem que uma linha de leitura crua tenha nascido. É o preço
    # do endereço exato, e o endereço exato é o que impede a lista de virar uma
    # contagem que ninguém confere. RELATO para quem coordena: uma âncora por
    # NOME DE FUNÇÃO em vez de número de linha custaria a mesma precisão sem o
    # aluguel — hoje ela cai em toda leva que toca um pacote.
    "a04_iluminacao.py:768": "lê o `player` do CLIQUE (`o`), não do controle — não é state_full",
}

#: A leitura crua a caçar. `player_slot` está de fora: ele é a chave que a GTK lê
#: PRIMEIRO, e lê-lo sozinho não é o defeito — o defeito é ler `player` sozinho.
_CRU = re.compile(r'\.get\(\s*["\']player["\']')


def _pacotes() -> list[pathlib.Path]:
    return sorted((pathlib.Path(pacotes.__file__).parent).glob("*.py"))


def test_nenhum_pacote_le_player_cru_fora_da_lista_datada() -> None:
    """RÉGUA 4, e ela NOMEIA arquivo e linha — uma contagem não serviria.

    Quando a lista datada esvaziar, apague-a e este teste passa a ser absoluto.
    """
    achados: list[str] = []
    for arquivo in _pacotes():
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue
            if _CRU.search(linha):
                achados.append(f"{arquivo.name}:{n}")
    novos = [a for a in achados if a not in EXCECOES_DATADAS]
    assert not novos, (
        f"leitura crua de `player` sem dono: {novos}. Use `pacotes.jogador_de`, "
        "que lê `player_slot` antes — a mesma ordem da GTK"
    )


def test_a_lista_datada_nao_guarda_fantasma() -> None:
    """Exceção que já não existe é lista que mente sobre o tamanho da dívida."""
    achados = set()
    for arquivo in _pacotes():
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if not linha.lstrip().startswith("#") and _CRU.search(linha):
                achados.add(f"{arquivo.name}:{n}")
    mortas = sorted(set(EXCECOES_DATADAS) - achados)
    assert not mortas, (
        f"a lista datada guarda exceção que já morreu: {mortas}. Apague a linha "
        "— a dívida é menor do que ela diz"
    )


# ---------------------------------------------------------------------------
# RÉGUA 5 — se a chave sumir do `state_full`, reprova
# ---------------------------------------------------------------------------
class _Vazio:
    """Um daemon sem `maquina.json` declarado."""

    _maquina = None


class _Handler:
    """O mixin com o mínimo que `_enrich_controllers_per_controller` toca.

    Os auxiliares que NÃO são o assunto desta régua são substituídos por
    respostas fixas — o que sobra medindo é a fiação da identidade.
    """

    def __init__(self, daemon: Any = None) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        self._mixin = IpcHandlersMixin
        self.daemon = daemon
        self.controller = _Vazio()
        self._identidade_de_fabrica_cache: dict[str, Any] | None = None
        self._identidade_em_voo: set[str] | None = None
        self._perguntas: list[str] = []

    # --- os auxiliares fora do assunto ---
    def _player_slot_for(self, uniq: Any) -> None:
        return None

    def _lightbar_for_uniq(self, *_a: Any) -> tuple[None, bool, str]:
        return (None, False, "desconhecida")

    def _lightbar_disputada(self, *_a: Any) -> bool:
        return False

    def _nascimento_para(self, *_a: Any) -> None:
        return None

    def _coop_live_snapshots(self) -> dict[str, Any]:
        return {}

    def _coop_vpads_by_uniq(self) -> dict[str, Any]:
        return {}

    def _merge_sensores(self, *_a: Any) -> None:
        return None

    def _merge_audio(self, *_a: Any) -> None:
        return None

    # --- o assunto: a leitura de aparelho NÃO acontece no tique ---
    def _perguntar_identidade(self, uniq: str) -> None:
        self._perguntas.append(uniq)
        cache = self._identidade_de_fabrica_cache
        if cache is None:
            cache = {}
            self._identidade_de_fabrica_cache = cache
        cache[uniq] = {"serial": None, "modelo": "Cosmic Red"}
        voo = self._identidade_em_voo
        if voo is not None:
            voo.discard(uniq)

    def enriquecer(self, entradas: list[dict[str, Any]]) -> None:
        self._mixin._enrich_controllers_per_controller(self, entradas, None)  # type: ignore[arg-type]

    # os métodos de verdade, tomados emprestados do mixin
    def __getattr__(self, nome: str) -> Any:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        atributo = getattr(IpcHandlersMixin, nome)
        return atributo.__get__(self, type(self))


@pytest.mark.parametrize("chave", ["serial", "modelo", "nome_declarado"])
def test_o_state_full_carrega_a_identidade_de_cada_controle(chave: str) -> None:
    """Se a chave sumir do payload, a tela volta a inventar o nome pela posição."""
    handler = _Handler()
    entradas = [_controle(AZUL), _controle(VERMELHO)]
    handler.enriquecer(entradas)
    for entrada in entradas:
        assert chave in entrada, (
            f"`{chave}` sumiu de `controllers[]`. Sem ela, `identidade_de` cai no "
            "transporte e o HTML volta a cravar 'Cosmic Red'"
        )


def test_o_que_ela_declarou_sai_no_payload_sem_tocar_o_disco() -> None:
    """Vem de `daemon._maquina`, que o daemon já carrega no boot e rebinda."""
    from hefesto_dualsense4unix.utils.maquina import ControleDeclarado, MaquinaConfig

    class _Daemon:
        _maquina = MaquinaConfig(
            controles={AZUL: ControleDeclarado(cor="Starlight Blue")}
        )

    handler = _Handler(_Daemon())
    entradas = [_controle(AZUL), _controle(VERMELHO)]
    handler.enriquecer(entradas)
    assert entradas[0]["nome_declarado"] == "Starlight Blue"
    assert entradas[1]["nome_declarado"] is None


def test_o_tique_pergunta_uma_vez_so_por_endereco() -> None:
    """O `state_full` roda a 10 Hz e o pedido é um `SET_FEATURE` da família 0x80.

    A MESMA família em que `(1, 1)` RESETA o controle. Uma pergunta por tique
    seriam dez por segundo, para sempre, num aparelho sem reposição.
    """
    handler = _Handler()
    for _ in range(30):
        entradas = [_controle(AZUL), _controle(VERMELHO)]
        handler.enriquecer(entradas)
    assert sorted(handler._perguntas) == sorted([AZUL, VERMELHO]), handler._perguntas


def test_o_controle_desconectado_nao_e_perguntado() -> None:
    handler = _Handler()
    entradas = [_controle(AZUL, connected=False)]
    handler.enriquecer(entradas)
    assert handler._perguntas == []
    assert entradas[0]["serial"] is None
    assert entradas[0]["modelo"] is None


def test_o_modelo_lido_chega_ao_payload_no_tique_seguinte() -> None:
    """A leitura é assíncrona: o primeiro tique sai `None`, e isso é honesto."""
    handler = _Handler()
    primeiro = [_controle(AZUL)]
    handler.enriquecer(primeiro)
    assert primeiro[0]["modelo"] is None

    segundo = [_controle(AZUL)]
    handler.enriquecer(segundo)
    assert segundo[0]["modelo"] == "Cosmic Red"


# ---------------------------------------------------------------------------
# O transporte do serial — sem encostar em aparelho nenhum
# ---------------------------------------------------------------------------
def _resposta(serial: str) -> bytes:
    from hefesto_dualsense4unix.integrations import cor_do_plastico as cp

    buf = bytearray(cp.TAMANHO_DO_FEATURE)
    buf[0] = cp.FEATURE_RESPOSTA
    buf[1] = cp.BASE_DO_SERIAL
    buf[2] = cp.NUM_DO_SERIAL
    buf[3] = cp.MARCA_DE_RESPOSTA_BOA
    buf[4 : 4 + cp.TAMANHO_DO_SERIAL] = serial.encode("ascii")
    return bytes(buf)


class TestSerialDe:
    def test_o_serial_deixa_de_ser_descartado(self) -> None:
        from hefesto_dualsense4unix.integrations.cor_do_plastico import serial_de

        assert serial_de(_resposta("P5A002XXXXXXXXXXX")) == "P5A002XXXXXXXXXXX"

    def test_o_eco_errado_nao_vira_serial(self) -> None:
        from hefesto_dualsense4unix.integrations.cor_do_plastico import serial_de

        ruim = bytearray(_resposta("P5A002XXXXXXXXXXX"))
        ruim[3] = 0
        assert serial_de(bytes(ruim)) is None

    def test_o_decodificar_continua_devolvendo_a_cor(self) -> None:
        """O embrulho antigo não pode ter mudado de contrato."""
        from hefesto_dualsense4unix.integrations.cor_do_plastico import decodificar

        cor = decodificar(_resposta("P5A002XXXXXXXXXXX"))
        assert cor is not None and cor.nome == "Cosmic Red"


class TestLerIdentidadePeloCabo:
    def test_serial_e_cor_saem_do_mesmo_pedido(self) -> None:
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            ler_identidade_pelo_cabo,
        )

        pedidos: list[bytes] = []

        def _falar(caminho: str, pedido: bytes) -> bytes:
            pedidos.append(pedido)
            return _resposta("P5A005XXXXXXXXXXX")

        achado = ler_identidade_pelo_cabo(
            AZUL,
            raiz="/lugar-nenhum",
            listar=lambda _r: ["hidraw9"],
            ler=lambda _c: (
                f"HID_UNIQ={AZUL}\nHID_ID=0003:0000054C:00000CE6\nHID_PHYS=x\n"
            ),
            perguntar=_falar,
        )
        assert achado.serial == "P5A005XXXXXXXXXXX"
        assert achado.cor is not None and achado.cor.nome == "Starlight Blue"
        assert len(pedidos) == 1, "duas idas ao aparelho para o mesmo fato"

    def test_serial_legivel_com_codigo_fora_da_tabela_nao_inventa_cor(self) -> None:
        """"Sei qual aparelho é" e "sei a cor dele" são respostas diferentes."""
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            ler_identidade_pelo_cabo,
        )

        achado = ler_identidade_pelo_cabo(
            AZUL,
            raiz="/lugar-nenhum",
            listar=lambda _r: ["hidraw9"],
            ler=lambda _c: (
                f"HID_UNIQ={AZUL}\nHID_ID=0003:0000054C:00000CE6\nHID_PHYS=x\n"
            ),
            perguntar=lambda _c, _p: _resposta("P5A099XXXXXXXXXXX"),
        )
        assert achado.serial == "P5A099XXXXXXXXXXX"
        assert achado.cor is None

    def test_sem_aparelho_os_dois_campos_calam(self) -> None:
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            ler_identidade_pelo_cabo,
        )

        achado = ler_identidade_pelo_cabo(
            AZUL, raiz="/lugar-nenhum", listar=lambda _r: [], ler=lambda _c: ""
        )
        assert achado.serial is None and achado.cor is None

    def test_o_ler_pelo_cabo_antigo_continua_devolvendo_so_a_cor(self) -> None:
        from hefesto_dualsense4unix.integrations.cor_do_plastico import ler_pelo_cabo

        cor = ler_pelo_cabo(
            AZUL,
            raiz="/lugar-nenhum",
            listar=lambda _r: ["hidraw9"],
            ler=lambda _c: (
                f"HID_UNIQ={AZUL}\nHID_ID=0003:0000054C:00000CE6\nHID_PHYS=x\n"
            ),
            perguntar=lambda _c, _p: _resposta("P5A002XXXXXXXXXXX"),
        )
        assert cor is not None and cor.nome == "Cosmic Red"
