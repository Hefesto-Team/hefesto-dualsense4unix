"""O canal de captura tem o nome do CONTROLE, e não o do transporte.

ONDA5-MIC-VIRTUAL-01. A decisão é dela, 05/09/2026:

    *"se o Mic do dualsense passa a ser lido a parte via Mic virtual. Usaríamos
    essa feature do controle mesmo no Xbox. Mesmo problema BT."*

O DEFEITO QUE ESTA RÉGUA GUARDA é de NOME: hoje o microfone do mesmo controle se
chama ``hefesto_dualsense_bt_<hex6>`` no rádio e um nó ALSA com desempate
posicional (``-00``, ``-00.2``) no cabo. Troque o transporte e o microfone muda
de nome; um app que fixou o device perde a fonte.

A MORDIDA, e ela é a do enunciado da sprint: apague o sufixo do nome (deixe
``hefesto_mic``) e ponha DOIS controles. `test_dois_controles_nao_dividem_o_nome`
reprova, porque os dois nós disputariam um nome só — e o segundo sobrescreveria
o primeiro em silêncio, que é pior que não ter canal.

NADA AQUI TOCA O PIPEWIRE DA MÁQUINA. O mecanismo entra por `fabrica`, que é o
parâmetro que existe para isto: a régua troca o `SourceVirtualPipeWire` por um
dublê e mede o CICLO DE VIDA, que é o que este módulo possui. Uma régua que
carregasse `module-pipe-source` de verdade mexeria no áudio dela.
"""

from __future__ import annotations

import io
import time
from typing import ClassVar

import pytest

from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    PRIORIDADE_SESSAO_DA_PONTE,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    PREFIXO_SOURCE_PONTE_BT,
    CasamentoUSB,
    escolher_fonte,
    fontes_dualsense,
    sufixo_da_ponte_bt,
    sufixo_do_canal_do_mic,
)
from hefesto_dualsense4unix.integrations.quem_ouve_o_microfone import (
    PREFIXO_PROPRIEDADE_HEFESTO,
    StreamDeCaptura,
    e_stream_do_hefesto,
    ouvintes_por_fonte,
)

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

#: Os nós ALSA dos dois controles no cabo. O ``-00``/``-00.2`` é desempate
#: posicional do PipeWire, e não número de série — é o defeito que o canal por
#: controle existe para curar.
_ALSA = "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller"
CABO_1 = f"{_ALSA}-00.iec958-stereo"
CABO_2 = f"{_ALSA}-00.2.iec958-stereo"


def _pactl(*nomes: str) -> str:
    """Uma saída de ``pactl list sources short`` com estes nomes."""
    return "\n".join(
        f"{600 + i}\t{nome}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED"
        for i, nome in enumerate(nomes)
    )


def _usb_do_cabo() -> CasamentoUSB:
    """Os dois controles no cabo, cada um com a sua placa — a regra 3."""
    return CasamentoUSB(
        por_uniq={P1: "usb-1", P2: "usb-2"},
        por_no={CABO_1: "usb-1", CABO_2: "usb-2"},
    )


class SourceDeMentira:
    """O mecanismo, sem PipeWire. Conta o que foi pedido e o que foi desfeito."""

    vivas: ClassVar[list[SourceDeMentira]] = []

    def __init__(self, *, nome: str, descricao: str, **_: object) -> None:
        self.nome = nome
        self.descricao = descricao
        self.iniciou = 0
        self.parou = 0
        SourceDeMentira.vivas.append(self)

    def iniciar(self) -> bool:
        self.iniciou += 1
        return True

    def parar(self) -> None:
        self.parou += 1


class SourceQueRecusa(SourceDeMentira):
    """O mecanismo que não sobe — e o contrato diz que nada fica pela metade."""

    def iniciar(self) -> bool:
        self.iniciou += 1
        return False


#: O `pactl` que esta régua deixa acontecer: NENHUM. Guarda o que foi pedido.
PACTL_PEDIDO: list[list[str]] = []


@pytest.fixture(autouse=True)
def _mesa_limpa(monkeypatch):
    """Mesa limpa E BOCA FECHADA — nenhum teste fala com o PipeWire dela.

    O `_rodar_pactl` é trocado por um dublê em TODOS os testes deste arquivo, e
    não só nos que se importam com ele: um único `abrir` que escapasse mandaria
    um `set-source-mute` para o servidor de som da máquina em que a suíte roda.
    """
    PACTL_PEDIDO.clear()
    SourceDeMentira.vivas = []
    monkeypatch.setattr(canal, "_rodar_pactl", lambda argv: PACTL_PEDIDO.append(argv) or True)
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)
    yield
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)


# ---------------------------------------------------------------------------
# 1. O NOME
# ---------------------------------------------------------------------------
def test_o_nome_carrega_a_identidade_do_controle() -> None:
    assert canal.nome_do_canal(P1) == "hefesto_mic_000001"
    assert canal.nome_do_canal(P2) == "hefesto_mic_000002"


def test_dois_controles_nao_dividem_o_nome() -> None:
    """A régua da mordida do enunciado: sem sufixo, os dois nós colidem."""
    assert canal.nome_do_canal(P1) != canal.nome_do_canal(P2), (
        "dois controles na mesa geraram o MESMO nome de source — o segundo "
        "sobrescreveria o primeiro em silêncio")


def test_o_separador_do_endereco_nao_muda_o_nome() -> None:
    """O mesmo aparelho, escrito de três jeitos, é o mesmo canal."""
    nomes = {canal.nome_do_canal(f) for f in (P1, P1.upper(), P1.replace(":", "-"))}
    assert len(nomes) == 1, nomes


def test_sem_endereco_nao_ha_canal() -> None:
    """Sem identidade não se batiza um canal — e hex POR ACASO não vale.

    Medido em 05/09/2026: `so_hex("sem-identidade")` devolve `"emdedade"`,
    porque `e`, `d` e `a` são dígitos hex. Sem esta régua o canal nasceria
    `hefesto_mic_dedade` sobre uma string que não é endereço nenhum.
    """
    for lixo in ("sem-identidade", "", "abc", "DualSense Wireless Controller"):
        assert canal.nome_do_canal(lixo) == "", lixo


def test_o_caminho_de_volta_reconhece_so_o_nosso() -> None:
    """De que controle é este nó — e o prefixo do rádio NÃO é este.

    O caminho de volta MOROU no `canal_do_microfone` e desceu para
    `fontes_de_captura` em 06/09/2026, quando a regra 0 de `escolher_fonte`
    passou a precisar dele. Não foi copiado: lá não existe mais.
    """
    assert sufixo_do_canal_do_mic(canal.nome_do_canal(P1)) == "000001"
    assert sufixo_do_canal_do_mic(f"{PREFIXO_SOURCE_PONTE_BT}000001") == ""
    assert sufixo_do_canal_do_mic("alsa_input.usb-Sony_DualSense-00") == ""
    assert not hasattr(canal, "sufixo_do_canal"), (
        "o caminho de volta voltou a ter DOIS donos — é assim que esta casa "
        "fabrica divergência silenciosa")


def test_os_dois_prefixos_convivem_e_nao_se_confundem() -> None:
    """Enquanto o rádio publicar o nome velho, os dois leitores discriminam.

    Dois prefixos vivos é o preço declarado da transição, e a MIC-VIRTUAL-02 é
    quem o paga. O que não pode é um leitor achar que o nó do outro é seu.
    """
    do_radio = f"{PREFIXO_SOURCE_PONTE_BT}000001"
    do_canal = canal.nome_do_canal(P1)
    assert sufixo_da_ponte_bt(do_radio) == "000001"
    assert sufixo_da_ponte_bt(do_canal) == ""
    assert sufixo_do_canal_do_mic(do_canal) == "000001"
    assert sufixo_do_canal_do_mic(do_radio) == ""


# ---------------------------------------------------------------------------
# 2. O QUE NÃO SE DIGITA DUAS VEZES
# ---------------------------------------------------------------------------
def test_a_prioridade_vem_do_dono_e_nao_de_um_literal() -> None:
    """A faixa do cabo, com a medição de 03/09 na máquina dela por trás.

    Um literal aqui repetiria, na íntegra, o defeito que
    `PRIORIDADE_SESSAO_DA_PONTE` registra: um número catorze dias atrás da
    doutrina que ele espelhava.
    """
    assert canal.prioridade() == PRIORIDADE_SESSAO_DA_PONTE


def test_as_propriedades_ficam_no_espaco_de_nome_do_hefesto() -> None:
    """Não se combina nome com a peça que reconhece — reconhece-se o PREFIXO.

    `quem_ouve_o_microfone` conta ouvintes e **não pode contar o Hefesto**: se
    contar, a luz vermelha do microfone dela acende sozinha e a peça inteira
    mente. A junta entre os dois é o espaço de nome, lido do dono.
    """
    props = canal.propriedades_do_canal(P1)
    assert props, "o nó subiria sem marca nenhuma do Hefesto"
    assert all(k.startswith(PREFIXO_PROPRIEDADE_HEFESTO) for k in props), props
    assert props[f"{PREFIXO_PROPRIEDADE_HEFESTO}uniq"] == P1


# ---------------------------------------------------------------------------
# 3. O CICLO DE VIDA — o que este módulo POSSUI
# ---------------------------------------------------------------------------
def test_pedir_duas_vezes_sobe_um_no_so() -> None:
    """Duas abas, dois cliques: é o caminho normal, não o excepcional.

    Dois `module-pipe-source` com o mesmo `source_name` publicariam dois nós
    disputando um nome só.
    """
    a = canal.abrir(P1, "Microfone do P1", fabrica=SourceDeMentira)
    b = canal.abrir(P1, "Microfone do P1", fabrica=SourceDeMentira)
    assert a is not None and a is b
    assert len(SourceDeMentira.vivas) == 1, SourceDeMentira.vivas
    assert canal.de_pe() == {P1: "hefesto_mic_000001"}


def test_dois_controles_sobem_dois_nos() -> None:
    canal.abrir(P1, "P1", fabrica=SourceDeMentira)
    canal.abrir(P2, "P2", fabrica=SourceDeMentira)
    assert canal.de_pe() == {
        P1: "hefesto_mic_000001",
        P2: "hefesto_mic_000002",
    }


def test_fechar_derruba_so_o_pedido() -> None:
    canal.abrir(P1, "P1", fabrica=SourceDeMentira)
    canal.abrir(P2, "P2", fabrica=SourceDeMentira)
    assert canal.fechar(P1) is True
    assert canal.fechar(P1) is False, "fechar o que não está de pé disse que fechou"
    assert list(canal.de_pe()) == [P2]


def test_o_que_nao_subiu_nao_fica_pela_metade() -> None:
    """`None` e a tabela vazia — o contrato do `iniciar` que devolve False."""
    assert canal.abrir(P1, "P1", fabrica=SourceQueRecusa) is None
    assert canal.de_pe() == {}


def test_o_gesto_dela_nunca_vira_traceback() -> None:
    """O caminho até aqui é o botão do microfone. Uma recusa, nunca um erro."""

    class SourceQueExplode(SourceDeMentira):
        def iniciar(self) -> bool:
            raise RuntimeError("o pactl não estava lá")

    assert canal.abrir(P1, "P1", fabrica=SourceQueExplode) is None
    assert canal.de_pe() == {}


def test_sem_identidade_nao_sobe_no_nenhum() -> None:
    assert canal.abrir("sem-identidade", "?", fabrica=SourceDeMentira) is None
    assert SourceDeMentira.vivas == [], "subiu um nó sem nome de controle"


# ---------------------------------------------------------------------------
# 4. O CABO ENTRA NO NÓ — Passo 2, e a medição veio antes do código
#
# MEDIDO na máquina dela em 06/09/2026, com um `module-pipe-source` de mentira
# de pé e desmontado no fim (PipeWire 1.6.8):
#
#     pw-link -i | grep <o nó>  →  (NENHUMA PORTA DE ENTRADA)
#     pw-link -o | grep <o nó>  →  <o nó>:capture_FL / :capture_FR
#
# Um `module-pipe-source` não tem porta de ENTRADA: não há no grafo nada a que
# ligar o nó do cabo, e `pw-link` não tem alvo. A única entrada é o fifo — logo
# **é preciso um LEITOR**, e é ele que estas réguas medem. Nada aqui toca o
# PipeWire nem lança processo: o mecanismo entra por `fabrica` e o processo por
# `lancar`.
# ---------------------------------------------------------------------------
class ProcessoDeMentira:
    """Um `parec` que não existe: devolve um punhado de PCM e termina."""

    lancados: ClassVar[list[list[str]]] = []

    def __init__(self, argv: list[str], pcm: bytes = b"\x01\x02" * 64) -> None:
        self.argv = argv
        self.stdout = io.BytesIO(pcm)
        self.terminou = 0
        self.matou = 0
        ProcessoDeMentira.lancados.append(argv)

    def terminate(self) -> None:
        self.terminou += 1

    def kill(self) -> None:
        self.matou += 1

    def wait(self, timeout: float | None = None) -> int:
        return 0


class SourceQueGuardaOPcm(SourceDeMentira):
    """O nó que conta o que entrou por `escrever` — a porta pública do mecanismo."""

    def __init__(self, *, nome: str, descricao: str, **kw: object) -> None:
        super().__init__(nome=nome, descricao=descricao, **kw)
        self.recebido = bytearray()
        self.taxa_hz = 48000
        self.canais = 1

    def escrever(self, pcm: bytes) -> bool:
        self.recebido += pcm
        return True


@pytest.fixture(autouse=True)
def _sem_processos_de_mentira():
    ProcessoDeMentira.lancados = []
    yield


def test_sem_fonte_o_no_sobe_mudo() -> None:
    """Publicar o canal e alimentá-lo são duas coisas — o rádio prova isso.

    O canal do rádio nasce sem `fonte`: quem o enche é a ponte, pela mesma
    `escrever`, e é a MIC-VIRTUAL-02 que a liga. Colapsar os dois faria "o nó
    existe" parecer "o microfone está entrando".
    """
    canal.abrir(P1, "P1", fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira)
    assert canal.de_pe() == {P1: "hefesto_mic_000001"}
    assert canal.alimentando() == {}
    assert ProcessoDeMentira.lancados == []


def test_o_cabo_entra_no_no_pela_porta_publica_do_mecanismo() -> None:
    """O PCM do leitor chega ao nó por `escrever` — a mesma porta do rádio.

    É o que faz o microfone daquele controle ter UM nome e duas entradas. Se um
    dia isto virar escrita direta no fifo, a MIC-VIRTUAL-02 terá de reabrir esta
    peça para ligar o rádio.
    """
    source = canal.abrir(
        P1, "P1", fonte=CABO_1, fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira
    )
    assert source is not None
    for _ in range(200):
        if source.recebido:
            break
        time.sleep(0.005)
    assert bytes(source.recebido) == b"\x01\x02" * 64, "o cabo não entrou no nó"
    assert canal.alimentando() == {P1: CABO_1}


def test_o_leitor_pergunta_o_formato_ao_no_e_nao_a_uma_constante() -> None:
    """Formato errado no fifo não dá erro: dá áudio em velocidade errada.

    Quem sabe com que formato o `module-pipe-source` foi carregado é a source.
    Um literal aqui seria um segundo dono do mesmo número.
    """
    argv = canal.argv_do_alimentador(P1, CABO_1, taxa_hz=48000, canais=1)
    assert "--rate=48000" in argv and "--channels=1" in argv
    assert "--format=s16le" in argv and "--raw" in argv
    assert f"--device={CABO_1}" in argv
    assert argv[0] == "parec"


def test_o_leitor_pede_latencia_curta_e_o_numero_e_medido() -> None:
    """Sem isto o primeiro byte demora DOIS SEGUNDOS — medido em 06/09/2026.

    O `parec` nasce com `pulse.attr.fragsize = 384000`: quase quatro segundos de
    áudio a 48 kHz mono s16. Do lado dela são dois segundos de silêncio depois de
    apertar o botão do microfone, que se leem como *"não funcionou"*; e o
    fragmento gigante chegaria de uma vez a um fifo de 8 KiB, onde quase tudo
    viraria descarte::

        sem --latency-msec    → primeiro byte aos 1,98 s
        com --latency-msec=40 → primeiro byte aos 0,088 s

    ARRANQUE PARA VER VERMELHO: tire o `--latency-msec` do argv.
    """
    argv = canal.argv_do_alimentador(P1, CABO_1, taxa_hz=48000, canais=1)
    pedidos = [a for a in argv if a.startswith("--latency-msec=")]
    assert pedidos, f"o leitor voltou a aceitar o fragmento de 4 s do parec: {argv}"
    assert 0 < int(pedidos[0].split("=")[1]) <= 85, (
        "a latência pedida passou do fifo de 8 KiB (~85 ms mono) — o fragmento "
        "deixa de caber e a mangueira estoura no leitor")


def test_o_leitor_leva_as_propriedades_uma_por_argv() -> None:
    """A medição de 06/09 que decidiu o desenho, virada régua.

    `source_properties` do `load-module` perde tudo depois do primeiro espaço
    quando não vem entre aspas duplas — medido nesta máquina, e é por isso que a
    prioridade da ponte de rádio não chega ao nó dela hoje. `--property=K=V` é
    um argv por propriedade e não tem esse buraco. Se alguém juntar as duas
    numa string só, esta régua reprova.
    """
    argv = canal.argv_do_alimentador(P1, CABO_1, taxa_hz=48000, canais=1)
    props = [a for a in argv if a.startswith("--property=")]
    assert len(props) == len(canal.propriedades_do_canal(P1)) >= 2, argv
    for pedaco in argv:
        assert " " not in pedaco, (
            f"um argv com espaço dentro: {pedaco!r} — é assim que o "
            "source_properties perde metade das propriedades")


def test_fechar_mata_o_leitor_antes_de_derrubar_o_no() -> None:
    """A ordem: um `parec` vivo sem nó para onde mandar continua gravando ela."""
    canal.abrir(P1, "P1", fonte=CABO_1, fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira)
    assert canal.fechar(P1) is True
    assert canal.alimentando() == {}
    assert canal.de_pe() == {}


def test_o_leitor_que_nao_lanca_nao_derruba_o_canal() -> None:
    """Sem `parec` na máquina o nó fica de pé e MUDO, não morre.

    Derrubar o nó tiraria dela o canal inteiro por causa de um binário ausente —
    e o rádio ainda poderia enchê-lo pela mesma porta.
    """

    def nao_lanca(_argv: list[str]) -> object:
        raise OSError("parec não está instalado")

    source = canal.abrir(
        P1, "P1", fonte=CABO_1, fabrica=SourceQueGuardaOPcm, lancar=nao_lanca
    )
    assert source is not None
    assert canal.de_pe() == {P1: "hefesto_mic_000001"}
    assert canal.alimentando() == {}


# ---------------------------------------------------------------------------
# 5. O HEFESTO NÃO CONTA COMO OUVINTE — a armadilha herdada, com a mordida
# ---------------------------------------------------------------------------
def _bloco(indice: int, fonte: int, props: dict[str, str]) -> str:
    corpo = "\n".join(f'\t\t{k} = "{v}"' for k, v in props.items())
    return (
        f"Source Output #{indice}\n"
        f"\tSource: {fonte}\n"
        f"\tCorked: no\n"
        f"\tProperties:\n{corpo}\n"
    )


def test_o_alimentador_nao_conta_como_ouvinte() -> None:
    """A MORDIDA DO PASSO 2: o nó de pé, ninguém gravando, e a luz apagada.

    O alimentador é um stream de captura no nó do CABO. Se ele contar, a luz
    vermelha do microfone dela acende sozinha e para sempre — *"o medidor do
    próprio Hefesto não pode contar como ouvinte"*.

    ARRANQUE PARA VER VERMELHO: tire o laço do espaço de nome de
    `quem_ouve_o_microfone.e_stream_do_hefesto` (a regra 1) e esta régua reprova
    com o Hefesto listado como ouvinte de si mesmo.

    **E ELA MEDE O ESPAÇO DE NOME SOZINHO, de propósito.** A primeira versão
    punha o `application.name` junto e ficava VERDE com a regra 1 arrancada —
    quem respondia era a regra do nome, e a régua dava verde sobre nada. A junta
    DECLARADA entre as duas peças é o espaço de nome (*"não é um nome combinado
    — é um espaço de nome"*); é ele que tem de estar medido sozinho, porque é
    ele o único que sobrevive à PEÇA B trocar de forma, como já trocou duas
    vezes num dia.
    """
    so_o_espaco = dict(canal.propriedades_do_canal(P1))
    so_o_espaco["application.name"] = "gravador-qualquer"
    completo = dict(canal.propriedades_do_canal(P1))
    completo["application.name"] = canal.NOME_DO_CLIENTE_ALIMENTADOR
    casos = (("só o espaço de nome", so_o_espaco), ("o alimentador inteiro", completo))
    for rotulo, props in casos:
        ouvindo, pausados = ouvintes_por_fonte(
            _bloco(1, 600, props), _pactl(CABO_1), raiz_proc="/proc/nao-existe"
        )
        assert ouvindo == {}, f"o Hefesto virou ouvinte de si mesmo ({rotulo}): {ouvindo}"
        assert pausados == {}, rotulo


def test_as_propriedades_do_alimentador_sao_as_que_a_outra_peca_reconhece() -> None:
    """O encontro das duas peças, sem nome combinado entre os arquivos.

    Uma escreve `hefesto.papel`/`hefesto.uniq`; a outra reconhece o PREFIXO. Se
    as duas se afastarem, é aqui que aparece.
    """
    stream = StreamDeCaptura(
        indice=1, fonte=600, corked=False, props=dict(canal.propriedades_do_canal(P1))
    )
    assert e_stream_do_hefesto(stream, raiz_proc="/proc/nao-existe") is True


def test_o_app_dela_no_canal_novo_continua_contando_como_ouvinte(tmp_path) -> None:
    """A REGRESSÃO QUE O NOME NOVO CRIOU, medida em 06/09/2026 e curada.

    O nó se chama `hefesto_mic_<hex6>`, e todo app que grave dele carrega a
    palavra `hefesto` na PRÓPRIA linha de comando —
    `obs --record --device=hefesto_mic_000001`. Sem a poda,
    `descende_do_hefesto` diz que o OBS é nosso, o ouvinte de verdade sai da
    conta e **a luz nunca acende para o canal que esta sprint construiu**.

    ARRANQUE PARA VER VERMELHO: tire o `_sem_os_nossos_nomes_de_no` de
    `descende_do_hefesto`.
    """
    for pid, cmd, ppid in (
        (4242, f"obs --record --device={canal.nome_do_canal(P1)}", 4000),
        (4000, "/usr/bin/bash", 1),
    ):
        d = tmp_path / str(pid)
        d.mkdir()
        (d / "cmdline").write_bytes(cmd.replace(" ", "\0").encode() + b"\0")
        (d / "stat").write_text(f"{pid} (x) S {ppid} 0 0 0")

    stream = StreamDeCaptura(
        indice=1,
        fonte=600,
        corked=False,
        props={"application.name": "OBS Studio", "application.process.id": "4242"},
    )
    assert e_stream_do_hefesto(stream, tmp_path) is False, (
        "o Hefesto confundiu o app DELA consigo mesmo, porque o nome do NÓ tem "
        "a palavra hefesto dentro — a luz do microfone nunca acenderia")


# ---------------------------------------------------------------------------
# 6. A REGRA 0 — o nó com identidade vence, e as outras quatro FICAM
# ---------------------------------------------------------------------------
def test_o_no_com_identidade_chega_a_lista_de_fontes() -> None:
    """MEDIDO em 06/09/2026, e sem isto a regra 0 seria código morto.

    `hefesto_mic_000001` não contém NENHUM dos marcadores de DualSense — o da
    ponte de rádio contém, porque tem a palavra `dualsense` dentro. Sem a
    entrada por identidade o nó nunca chegava a `escolher_fonte`, e a regra 0
    dava verde sobre nada.
    """
    saida = _pactl(CABO_1, canal.nome_do_canal(P1))
    assert canal.nome_do_canal(P1) in fontes_dualsense(saida)


def test_a_regra_0_vence_o_no_do_transporte() -> None:
    """A MORDIDA DO PASSO 3: arranque a regra 0 e esta régua reprova.

    Sem ela as quatro regras antigas respondem — e respondem o nó ALSA, cujo
    `-00`/`-00.2` é desempate posicional do PipeWire. É a resposta do
    TRANSPORTE, e é ela que muda quando o controle troca de cabo para rádio.
    """
    fontes = fontes_dualsense(
        _pactl(CABO_1, CABO_2, canal.nome_do_canal(P1), canal.nome_do_canal(P2))
    )
    usb = _usb_do_cabo()
    assert escolher_fonte(fontes, P1, [P1, P2], usb) == canal.nome_do_canal(P1)
    assert escolher_fonte(fontes, P2, [P1, P2], usb) == canal.nome_do_canal(P2)


def test_a_regra_0_nao_entrega_o_no_do_vizinho() -> None:
    """Com o canal de UM só no ar, o outro cai nas quatro regras — não no dele.

    Devolver o nó do controle errado é pior que devolver `None`, e é a regra
    que `fontes_de_captura` já escreve com todas as letras.
    """
    fontes = fontes_dualsense(_pactl(CABO_1, CABO_2, canal.nome_do_canal(P1)))
    usb = _usb_do_cabo()
    assert escolher_fonte(fontes, P1, [P1, P2], usb) == canal.nome_do_canal(P1)
    assert escolher_fonte(fontes, P2, [P1, P2], usb) == CABO_2


def test_as_quatro_regras_antigas_continuam_vivas() -> None:
    """A regra 0 ACRESCENTA. Sem canal no ar, tudo responde como respondia.

    O nó com nome só existe depois que alguém pede o canal; antes disso as
    quatro são o único caminho — inclusive o da janela estável, que abre esta
    mesma função.
    """
    fontes = fontes_dualsense(_pactl(CABO_1, CABO_2))
    usb = _usb_do_cabo()
    assert escolher_fonte(fontes, P1, [P1, P2], usb) == CABO_1
    assert escolher_fonte(fontes, P2, [P1, P2], usb) == CABO_2
    ponte = f"{PREFIXO_SOURCE_PONTE_BT}000001"
    assert escolher_fonte([ponte], P1, [P1, P2], None) == ponte


def test_a_regra_0_cobre_os_quatro_chamadores_de_uma_vez() -> None:
    """A cura está DENTRO da função que os quatro chamam, não em um deles.

    *"Quando a cura conhece a causa, ela cobre TODOS os chamadores."* Curar um
    deixaria a próxima pessoa remedindo o mesmo defeito — aconteceu duas vezes
    em 05/09. Esta régua entra pela porta de OUTRO chamador (a luz) e mede que a
    regra 0 já está lá.
    """
    fontes = fontes_dualsense(_pactl(CABO_1, CABO_2, canal.nome_do_canal(P1)))
    ouvindo, _ = ouvintes_por_fonte(
        _bloco(1, 602, {"application.name": "Google Chrome input"}),
        _pactl(CABO_1, CABO_2, canal.nome_do_canal(P1)),
        raiz_proc="/proc/nao-existe",
    )
    assert ouvindo == {canal.nome_do_canal(P1): ["Google Chrome input"]}
    assert escolher_fonte(fontes, P1, [P1, P2], _usb_do_cabo()) in ouvindo


# ---------------------------------------------------------------------------
# 7. O MUDO DE FÁBRICA — o defeito que calava o canal inteiro
# ---------------------------------------------------------------------------
def test_o_canal_nasce_mudo_e_o_produto_desmuta() -> None:
    """MEDIDO na máquina dela em 06/09/2026, com PipeWire 1.6.8::

        module-pipe-source recém-carregado, nome NUNCA visto → Mute: yes
        app gravando, com o mudo de fábrica                  → 192000 B, pico 0
        o MESMO canal, depois de set-source-mute … 0         → 192000 B, pico 20000

    Todo `module-pipe-source` nasce mudo, e não é estado restaurado: um nome
    sorteado, que nunca existiu, nasce mudo igual. Mudo ele entrega BYTES, não
    silêncio — 192 KB de zeros —, e quem conta bytes vê a ponte funcionando.

    ARRANQUE PARA VER VERMELHO: tire a chamada de `desmutar` do `abrir`.
    """
    source = canal.abrir(P1, "P1", fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira)
    assert source is not None
    assert ["pactl", "set-source-mute", "hefesto_mic_000001", "0"] in PACTL_PEDIDO, (
        "o canal subiu com o mudo de fábrica: ele entrega 192 KB de ZEROS, e o "
        "sintoma se lê como 'a ponte não está entregando áudio'")


def test_desmutar_nao_levanta_quando_nao_ha_pactl() -> None:
    """O gesto dela nunca vira traceback — nem quando o servidor de som sumiu."""

    def explode(_argv: list[str]) -> bool:
        raise OSError("pactl não está lá")

    assert canal.desmutar("hefesto_mic_000001", rodar=explode) is False


def test_o_canal_sobe_mesmo_que_o_desmute_falhe() -> None:
    """Nó mudo é recuperável à mão; nó ausente não é."""
    source = canal.abrir(
        P1, "P1", fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira,
        rodar=lambda _argv: False,
    )
    assert source is not None
    assert canal.de_pe() == {P1: "hefesto_mic_000001"}
