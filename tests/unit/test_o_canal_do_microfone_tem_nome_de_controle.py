"""O canal de captura tem o nome do CONTROLE, e não o do transporte."""

from __future__ import annotations

import fcntl
import io
import os
import time
from typing import ClassVar

import pytest

from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as canal_bt
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


PACTL_PEDIDO: list[list[str]] = []


@pytest.fixture(autouse=True)
def _mesa_limpa(monkeypatch):
    """Mesa limpa E BOCA FECHADA — nenhum teste fala com o PipeWire dela."""
    PACTL_PEDIDO.clear()
    SourceDeMentira.vivas = []
    monkeypatch.setattr(canal, "_rodar_pactl", lambda argv: PACTL_PEDIDO.append(argv) or True)
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)
    yield
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)


def test_o_nome_carrega_a_identidade_do_controle() -> None:
    """A marca do aparelho, e não o rabo do endereço (OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01)."""
    assert canal.nome_do_canal(P1) == f"hefesto_mic_{canal_bt.marca_do_aparelho(P1)}"
    assert canal.nome_do_canal(P2) == f"hefesto_mic_{canal_bt.marca_do_aparelho(P2)}"
    assert "000001" not in canal.nome_do_canal(P1)


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
    """Sem identidade não se batiza um canal — e hex POR ACASO não vale."""
    for lixo in ("sem-identidade", "", "abc", "DualSense Wireless Controller"):
        assert canal.nome_do_canal(lixo) == "", lixo


def test_o_caminho_de_volta_reconhece_so_o_nosso() -> None:
    """De que controle é este nó — e o prefixo do rádio NÃO é este."""
    assert sufixo_do_canal_do_mic(canal.nome_do_canal(P1)) == canal_bt.marca_do_aparelho(P1)
    assert sufixo_do_canal_do_mic(f"{PREFIXO_SOURCE_PONTE_BT}000001") == ""
    assert sufixo_do_canal_do_mic("alsa_input.usb-Sony_DualSense-00") == ""
    assert not hasattr(canal, "sufixo_do_canal"), (
        "o caminho de volta voltou a ter DOIS donos — é assim que esta casa "
        "fabrica divergência silenciosa")


def test_os_dois_prefixos_convivem_e_nao_se_confundem() -> None:
    """Enquanto o rádio publicar o nome velho, os dois leitores discriminam."""
    do_radio = f"{PREFIXO_SOURCE_PONTE_BT}000001"
    do_canal = canal.nome_do_canal(P1)
    assert sufixo_da_ponte_bt(do_radio) == "000001"
    assert sufixo_da_ponte_bt(do_canal) == ""
    assert sufixo_do_canal_do_mic(do_canal) == canal_bt.marca_do_aparelho(P1)
    assert sufixo_do_canal_do_mic(do_radio) == ""


def test_a_prioridade_vem_do_dono_e_nao_de_um_literal() -> None:
    """A faixa do cabo, com a medição de 03/09 na máquina do usuário por trás."""
    assert canal.prioridade() == PRIORIDADE_SESSAO_DA_PONTE


def test_as_propriedades_ficam_no_espaco_de_nome_do_hefesto() -> None:
    """Não se combina nome com a peça que reconhece — reconhece-se o PREFIXO."""
    props = canal.propriedades_do_canal(P1)
    assert props, "o nó subiria sem marca nenhuma do Hefesto"
    assert all(k.startswith(PREFIXO_PROPRIEDADE_HEFESTO) for k in props), props
    assert props[f"{PREFIXO_PROPRIEDADE_HEFESTO}uniq"] == P1


def test_pedir_duas_vezes_sobe_um_no_so() -> None:
    """Duas abas, dois cliques: é o caminho normal, não o excepcional."""
    a = canal.abrir(P1, "Microfone do P1", fabrica=SourceDeMentira)
    b = canal.abrir(P1, "Microfone do P1", fabrica=SourceDeMentira)
    assert a is not None and a is b
    assert len(SourceDeMentira.vivas) == 1, SourceDeMentira.vivas
    assert canal.de_pe() == {P1: canal.nome_do_canal(P1)}


def test_dois_controles_sobem_dois_nos() -> None:
    canal.abrir(P1, "P1", fabrica=SourceDeMentira)
    canal.abrir(P2, "P2", fabrica=SourceDeMentira)
    assert canal.de_pe() == {
        P1: canal.nome_do_canal(P1),
        P2: canal.nome_do_canal(P2),
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
    """Publicar o canal e alimentá-lo são duas coisas — o rádio prova isso."""
    source = canal.abrir(P1, "P1", fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira)
    assert canal.de_pe() == {P1: canal.nome_do_canal(P1)}
    assert ProcessoDeMentira.lancados == []
    assert source is not None and bytes(source.recebido) == b""


def test_o_cabo_entra_no_no_pela_porta_publica_do_mecanismo() -> None:
    """O PCM do leitor chega ao nó por `escrever` — a mesma porta do rádio."""
    source = canal.abrir(
        P1, "P1", fonte=CABO_1, fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira
    )
    assert source is not None
    for _ in range(200):
        if source.recebido:
            break
        time.sleep(0.005)
    assert bytes(source.recebido) == b"\x01\x02" * 64, "o cabo não entrou no nó"
    assert len(ProcessoDeMentira.lancados) == 1
    assert f"--device={CABO_1}" in ProcessoDeMentira.lancados[0], (
        "o leitor que encheu o nó não leu o nó ALSA do cabo deste controle"
    )


def test_o_leitor_pergunta_o_formato_ao_no_e_nao_a_uma_constante() -> None:
    """Formato errado no fifo não dá erro: dá áudio em velocidade errada."""
    argv = canal.argv_do_alimentador(P1, CABO_1, taxa_hz=48000, canais=1)
    assert "--rate=48000" in argv and "--channels=1" in argv
    assert "--format=s16le" in argv and "--raw" in argv
    assert f"--device={CABO_1}" in argv
    assert argv[0] == "parec"


def test_o_leitor_pede_latencia_curta_e_o_numero_e_medido() -> None:
    """Sem isto o primeiro byte demora DOIS SEGUNDOS — medido em 06/09/2026."""
    argv = canal.argv_do_alimentador(P1, CABO_1, taxa_hz=48000, canais=1)
    pedidos = [a for a in argv if a.startswith("--latency-msec=")]
    assert pedidos, f"o leitor voltou a aceitar o fragmento de 4 s do parec: {argv}"
    assert 0 < int(pedidos[0].split("=")[1]) <= 85, (
        "a latência pedida passou do fifo de 8 KiB (~85 ms mono) — o fragmento "
        "deixa de caber e a mangueira estoura no leitor")


def test_o_leitor_leva_as_propriedades_uma_por_argv() -> None:
    """A medição de 06/09 que decidiu o desenho, virada régua."""
    argv = canal.argv_do_alimentador(P1, CABO_1, taxa_hz=48000, canais=1)
    props = [a for a in argv if a.startswith("--property=")]
    assert len(props) == len(canal.propriedades_do_canal(P1)) >= 2, argv
    for pedaco in argv:
        assert " " not in pedaco, (
            f"um argv com espaço dentro: {pedaco!r} — é assim que o "
            "source_properties perde metade das propriedades")


def test_fechar_mata_o_leitor_antes_de_derrubar_o_no() -> None:
    """A ordem: um `parec` vivo sem nó para onde mandar continua gravando ela."""
    vivos: list[ProcessoDeMentira] = []

    def lancar(argv: list[str]) -> ProcessoDeMentira:
        processo = ProcessoDeMentira(argv)
        vivos.append(processo)
        return processo

    source = canal.abrir(
        P1, "P1", fonte=CABO_1, fabrica=SourceQueGuardaOPcm, lancar=lancar
    )
    assert canal.fechar(P1) is True
    assert vivos and vivos[0].terminou + vivos[0].matou >= 1, (
        "o canal fechou e o leitor do cabo continuou vivo"
    )
    assert source is not None and source.parou == 1
    assert canal.de_pe() == {}


def test_o_leitor_que_nao_lanca_nao_derruba_o_canal() -> None:
    """Sem `parec` na máquina o nó fica de pé e MUDO, não morre."""

    def nao_lanca(_argv: list[str]) -> object:
        raise OSError("parec não está instalado")

    source = canal.abrir(
        P1, "P1", fonte=CABO_1, fabrica=SourceQueGuardaOPcm, lancar=nao_lanca
    )
    assert source is not None
    assert canal.de_pe() == {P1: canal.nome_do_canal(P1)}
    assert bytes(source.recebido) == b"", "entrou áudio num canal sem leitor"


def _fifo_com_livre(caminho: str, livre: int) -> tuple[int, int]:
    """Um fifo de VERDADE, de `_FIFO_BYTES`, com só `livre` bytes de espaço."""
    os.mkfifo(caminho)
    r = os.open(caminho, os.O_RDONLY | os.O_NONBLOCK)
    w = os.open(caminho, os.O_WRONLY | os.O_NONBLOCK)
    tamanho = fcntl.fcntl(w, canal_bt._F_SETPIPE_SZ, canal_bt._FIFO_BYTES)
    os.write(w, b"\x00" * (tamanho - livre))
    return r, w


def _quanto_entra(caminho: str, *, pedaco: int, livre: int) -> tuple[int, int]:
    """Oferece voz em pedaços de `pedaco` até o fifo recusar."""
    r, w = _fifo_com_livre(caminho, livre)
    entrou = perdido = 0
    bloco = b"\x01" * pedaco
    try:
        while True:
            try:
                n = os.write(w, bloco)
            except BlockingIOError:
                perdido = pedaco
                break
            entrou += n
            if n != pedaco:
                perdido = pedaco - n
                break
    finally:
        os.close(r)
        os.close(w)
    return entrou, perdido


def test_o_pedaco_do_cabo_tem_a_duracao_do_quadro_do_radio() -> None:
    """Os dois transportes perdem voz no MESMO tamanho — lido dos dois donos."""
    assert canal.pedaco_do_bombeador(
        taxa_hz=canal_bt.MIC_TAXA_HZ, canais=canal_bt.MIC_CANAIS
    ) == canal_bt.MIC_BYTES_POR_QUADRO


def test_o_pedaco_acompanha_o_formato_do_no_e_nunca_desalinha_a_amostra() -> None:
    """Meia amostra s16 no fifo desalinha tudo o que vem depois dela."""
    quadro = canal_bt.MIC_BYTES_POR_AMOSTRA
    for taxa, canais in ((48000, 1), (48000, 2), (16000, 1), (44100, 2)):
        pedaco = canal.pedaco_do_bombeador(taxa_hz=taxa, canais=canais)
        assert pedaco % (quadro * canais) == 0, (taxa, canais, pedaco)
        ms = pedaco / (taxa * canais * quadro) * 1000
        alvo = canal_bt.MIC_AMOSTRAS_POR_QUADRO / canal_bt.MIC_TAXA_HZ * 1000
        assert abs(ms - alvo) < 1.0, (taxa, canais, ms, alvo)


def test_um_descarte_no_cabo_nao_custa_mais_voz_que_um_no_radio(tmp_path) -> None:
    """A MORDIDA, num fifo de verdade e sem aparelho nenhum na mesa."""
    pedaco = canal.pedaco_do_bombeador(
        taxa_hz=canal_bt.MIC_TAXA_HZ, canais=canal_bt.MIC_CANAIS
    )
    livre = canal_bt._FIFO_BYTES // 4
    entrou, perdido = _quanto_entra(
        str(tmp_path / "cabo.fifo"), pedaco=pedaco, livre=livre
    )
    assert entrou > 0, (
        f"com {livre} B livres no fifo, um pedaço de {pedaco} B não entregou "
        "UM BYTE de voz — o cabo descarta o que caberia")
    assert perdido <= canal_bt.MIC_BYTES_POR_QUADRO, (
        f"um descarte no CABO levou {perdido} B de voz, e no rádio leva "
        f"{canal_bt.MIC_BYTES_POR_QUADRO} B — é a assimetria que a frase dela "
        "«ficar limpo igual o do mic no bt» aponta")


def test_o_bombeador_le_o_pedaco_do_no_e_nao_de_um_literal() -> None:
    """Quem decide o tamanho é o formato do nó, atravessando o `_Alimentador`."""

    no = SourceQueGuardaOPcm(nome=canal.nome_do_canal(P1), descricao="P1")
    no.canais = 2
    alim = canal._Alimentador(P1, CABO_1, no, lancar=ProcessoDeMentira)
    assert alim.iniciar() is True
    alim.parar()

    esperado = canal.pedaco_do_bombeador(taxa_hz=no.taxa_hz, canais=no.canais)
    assert alim._pedaco == esperado, (
        "o `_Alimentador` não releu o formato do nó — um literal voltou ao laço")
    assert esperado != canal.pedaco_do_bombeador(
        taxa_hz=canal_bt.MIC_TAXA_HZ, canais=canal_bt.MIC_CANAIS
    ), "o nó estéreo e o mono deram o mesmo pedaço: o número parou de acompanhar"
    assert "--channels=2" in ProcessoDeMentira.lancados[-1], (
        "o `parec` e o laço deixaram de falar do MESMO formato")


def _bloco(indice: int, fonte: int, props: dict[str, str]) -> str:
    corpo = "\n".join(f'\t\t{k} = "{v}"' for k, v in props.items())
    return (
        f"Source Output #{indice}\n"
        f"\tSource: {fonte}\n"
        f"\tCorked: no\n"
        f"\tProperties:\n{corpo}\n"
    )


def test_o_alimentador_nao_conta_como_ouvinte() -> None:
    """A MORDIDA DO PASSO 2: o nó de pé, ninguém gravando, e a luz apagada."""
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
    """O encontro das duas peças, sem nome combinado entre os arquivos."""
    stream = StreamDeCaptura(
        indice=1, fonte=600, corked=False, props=dict(canal.propriedades_do_canal(P1))
    )
    assert e_stream_do_hefesto(stream, raiz_proc="/proc/nao-existe") is True


def test_o_app_dela_no_canal_novo_continua_contando_como_ouvinte(tmp_path) -> None:
    """A REGRESSÃO QUE O NOME NOVO CRIOU, medida em 06/09/2026 e curada."""
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


def test_o_no_com_identidade_chega_a_lista_de_fontes() -> None:
    """MEDIDO em 06/09/2026, e sem isto a regra 0 seria código morto.

    `hefesto_mic_<marca>` não contém NENHUM dos marcadores de DualSense — o da
    ponte de rádio contém, porque tem a palavra `dualsense` dentro. Sem a
    entrada por identidade o nó nunca chegava a `escolher_fonte`, e a regra 0
    dava verde sobre nada.
    """
    saida = _pactl(CABO_1, canal.nome_do_canal(P1))
    assert canal.nome_do_canal(P1) in fontes_dualsense(saida)


def test_a_regra_0_vence_o_no_do_transporte() -> None:
    """A MORDIDA DO PASSO 3: arranque a regra 0 e esta régua reprova."""
    fontes = fontes_dualsense(
        _pactl(CABO_1, CABO_2, canal.nome_do_canal(P1), canal.nome_do_canal(P2))
    )
    usb = _usb_do_cabo()
    assert escolher_fonte(fontes, P1, [P1, P2], usb) == canal.nome_do_canal(P1)
    assert escolher_fonte(fontes, P2, [P1, P2], usb) == canal.nome_do_canal(P2)


def test_a_regra_0_nao_entrega_o_no_do_vizinho() -> None:
    """Com o canal de UM só no ar, o outro cai nas quatro regras — não no dele."""
    fontes = fontes_dualsense(_pactl(CABO_1, CABO_2, canal.nome_do_canal(P1)))
    usb = _usb_do_cabo()
    assert escolher_fonte(fontes, P1, [P1, P2], usb) == canal.nome_do_canal(P1)
    assert escolher_fonte(fontes, P2, [P1, P2], usb) == CABO_2


def test_as_quatro_regras_antigas_continuam_vivas() -> None:
    """A regra 0 ACRESCENTA. Sem canal no ar, tudo responde como respondia."""
    fontes = fontes_dualsense(_pactl(CABO_1, CABO_2))
    usb = _usb_do_cabo()
    assert escolher_fonte(fontes, P1, [P1, P2], usb) == CABO_1
    assert escolher_fonte(fontes, P2, [P1, P2], usb) == CABO_2
    ponte = f"{PREFIXO_SOURCE_PONTE_BT}000001"
    assert escolher_fonte([ponte], P1, [P1, P2], None) == ponte


def test_a_regra_0_cobre_os_quatro_chamadores_de_uma_vez() -> None:
    """A cura está DENTRO da função que os quatro chamam, não em um deles."""
    fontes = fontes_dualsense(_pactl(CABO_1, CABO_2, canal.nome_do_canal(P1)))
    ouvindo, _ = ouvintes_por_fonte(
        _bloco(1, 602, {"application.name": "Google Chrome input"}),
        _pactl(CABO_1, CABO_2, canal.nome_do_canal(P1)),
        raiz_proc="/proc/nao-existe",
    )
    assert ouvindo == {canal.nome_do_canal(P1): ["Google Chrome input"]}
    assert escolher_fonte(fontes, P1, [P1, P2], _usb_do_cabo()) in ouvindo


def test_o_canal_nasce_mudo_e_o_produto_desmuta() -> None:
    """MEDIDO na bancada em 06/09/2026, com PipeWire 1.6.8::"""
    source = canal.abrir(P1, "P1", fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira)
    assert source is not None
    assert ["pactl", "set-source-mute", canal.nome_do_canal(P1), "0"] in PACTL_PEDIDO, (
        "o canal subiu com o mudo de fábrica: ele entrega 192 KB de ZEROS, e o "
        "sintoma se lê como 'a ponte não está entregando áudio'")


def test_desmutar_nao_levanta_quando_nao_ha_pactl() -> None:
    """O gesto do usuário nunca vira traceback — nem quando o servidor de som sumiu."""

    def explode(_argv: list[str]) -> bool:
        raise OSError("pactl não está lá")

    assert canal.desmutar(canal.nome_do_canal(P1), rodar=explode) is False


def test_o_canal_sobe_mesmo_que_o_desmute_falhe() -> None:
    """Nó mudo é recuperável à mão; nó ausente não é."""
    source = canal.abrir(
        P1, "P1", fabrica=SourceQueGuardaOPcm, lancar=ProcessoDeMentira,
        rodar=lambda _argv: False,
    )
    assert source is not None
    assert canal.de_pe() == {P1: canal.nome_do_canal(P1)}
