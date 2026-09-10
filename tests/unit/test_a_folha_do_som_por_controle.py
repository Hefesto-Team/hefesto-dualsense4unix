"""A FOLHA DO SOM POR CONTROLE — o positivo, o negativo e a porta que não abre.

`scripts/ensaios/a_folha_do_som_por_controle.py` é o instrumento que ELA dirige
para decidir o ensaio 13 do índice do rádio: *o som do PC chega ao alto-falante
do controle pelo RÁDIO?* A medição é da orelha dela, com os controles na mão —
o que se prova AQUI é a parte que já enganou esta casa antes de a orelha entrar.

O QUE ESTA RÉGUA MEDE, e por que cada peça
-------------------------------------------
1. **O tom é UM SÓ.** O WAV que o cabo toca tem de ser byte a byte o PCM que o
   rádio codifica. Dois tons gerados lado a lado poriam uma variável escondida
   DENTRO do controle positivo: ela ouviria o do cabo, não ouviria o do rádio, e
   ninguém saberia dizer se a diferença é o transporte ou a amplitude.
2. **As linhas de rádio nascem das tabelas do PRODUTO.** Arranjo novo em
   `af.ARRANJO_POR_NOME` tem de virar linha nova sem que ninguém lembre — foi
   digitando a lista de ontem que réguas desta casa passaram a medir o mundo de
   ontem.
3. **Todo positivo tem o negativo AO LADO.** Botão de tocar sem o par de CRC
   errado é medição sem controle negativo.
4. **A CONDIÇÃO é o `common` do produto**, e nenhum offset mora na folha.
5. **A recusa é DITA.** Coluna que não serve à pergunta não pode ficar muda: um
   painel calado lê-se como *"não fizeram nada"*.
6. **`--listar` e `--oculta` não abrem nó nem escrevem byte.** A folha roda com
   ela na frente, DEPOIS; um instrumento que tocasse o aparelho só de ser
   listado já teria mexido no controle dela antes da primeira pergunta.

AS MORDIDAS (arrancadas e conferidas em 09/09/2026, uma a uma)
---------------------------------------------------------------
* trocar `quadros_de_pcm` por um tom próprio no `wav_do_tom` → cai (1);
* montar `LINHAS` com dois arranjos digitados → cai (2), e é exatamente o que
  `montar_pelos_dois_arranjos` alcança;
* apagar o botão de CRC errado de uma linha → cai (3);
* escrever `common[5] = volume` à mão em vez de `af.common_de_audio` → cai (4);
* deixar a coluna do cabo sem a frase de recusa nos cruzamentos → cai (5);
* abrir a porta no construtor da `Coluna` em vez de na primeira escrita → cai (6).
"""

from __future__ import annotations

import os

from tests.conftest import exigir_gi_real

exigir_gi_real("a folha do som por controle abre uma Gtk.Window de verdade")

import importlib.util
import sys
import wave
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"


def _instrumento(nome: str):
    """Carrega um instrumento de `scripts/ensaios/` pelo caminho, como os irmãos.

    A SUÍTE JÁ CORRE SOB A TELA DE MENTIRA do TELA-DELA-01, e o
    `HEFESTO_NA_TELA=1` daqui só declara isso: sem ele o import da folha subiria
    um SEGUNDO Xvfb por cima do da suíte. A variável é devolvida depois — quem
    a declara assume a tela, e este arquivo não pode assumi-la pelos outros.
    """
    antes = os.environ.get("HEFESTO_NA_TELA")
    os.environ["HEFESTO_NA_TELA"] = "1"
    try:
        if str(ENSAIOS) not in sys.path:
            sys.path.insert(0, str(ENSAIOS))
        caminho = ENSAIOS / f"{nome}.py"
        apelido = f"instrumento_{nome}"
        spec = importlib.util.spec_from_file_location(apelido, caminho)
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[apelido] = modulo  # os dataclasses resolvem anotações por aqui
        spec.loader.exec_module(modulo)
        return modulo
    finally:
        if antes is None:
            os.environ.pop("HEFESTO_NA_TELA", None)
        else:
            os.environ["HEFESTO_NA_TELA"] = antes


@pytest.fixture(scope="module")
def folha():
    return _instrumento("a_folha_do_som_por_controle")


@pytest.fixture(scope="module")
def rep():
    from hefesto_dualsense4unix.core import ds_output_report

    return ds_output_report


def _aparelho(folha, transporte: str, hidraw: str, mac: str):
    """Um DualSense de mentira da mesa. Nenhum MAC real entra em arquivo versionado."""
    from comum import Aparelho

    return Aparelho(
        hidraw=hidraw,
        caminho_hidraw=f"/dev/{hidraw}",
        dir_device=f"/sys/class/hidraw/{hidraw}/device",
        mac=mac,
        nome="DualSense Wireless Controller",
        transporte=transporte,
        e_vpad=False,
        rotulo="",
    )


def _mesa_de_dois(folha):
    return [
        _aparelho(folha, folha.CABO, "hidraw90", "aa:bb:cc:00:00:01"),
        _aparelho(folha, folha.RADIO, "hidraw91", "aa:bb:cc:00:00:02"),
    ]


# ---------------------------------------------------------------------------
# 1. O TOM É UM SÓ — o positivo do cabo e a rajada do rádio saem do mesmo PCM
# ---------------------------------------------------------------------------


def test_o_wav_do_cabo_e_byte_a_byte_o_pcm_que_vai_pelo_radio(folha, tmp_path, monkeypatch):
    monkeypatch.setattr(folha, "PASTA", str(tmp_path))
    caminho = folha.wav_do_tom(0.05)
    with wave.open(caminho, "rb") as w:
        assert w.getframerate() == folha.TAXA == 48000
        assert (w.getnchannels(), w.getsampwidth()) == (2, 2)
        dados = w.readframes(w.getnframes())
    assert dados == b"".join(folha.quadros_de_pcm(0.05)), (
        "o WAV do cabo deixou de ser o mesmo som da rajada do rádio — o controle "
        "positivo passa a ter uma variável escondida dentro dele"
    )


def test_o_pcm_do_tom_e_o_do_ensaio_irmao_e_nao_uma_segunda_geracao(folha):
    from o_envelope_do_som_no_radio import pcm_do_tom

    assert folha.quadros_de_pcm(0.05) == tuple(pcm_do_tom(0.05, folha.TOM_HZ))
    assert all(len(q) == 1920 for q in folha.quadros_de_pcm(0.05)), "quadros de 10 ms"


# ---------------------------------------------------------------------------
# 2. AS LINHAS NASCEM DAS TABELAS DO PRODUTO
# ---------------------------------------------------------------------------


def test_todo_arranjo_do_produto_vira_linha_em_todo_envelope(folha):
    """Arranjo novo no produto é linha nova aqui — sem ninguém lembrar."""
    from o_envelope_do_som_no_radio import ENVELOPES

    esperadas = {
        f"audio-{arranjo}-por-{envelope}"
        for arranjo in folha.af.ARRANJO_POR_NOME
        for envelope in ENVELOPES
    }
    achadas = {linha.id for linha in folha.LINHAS if linha.id.startswith("audio-")}
    assert achadas == esperadas, (
        "a folha deixou de cobrir o cruzamento inteiro de arranjo por envelope"
    )
    assert len(esperadas) == 6, "são TRÊS arranjos no produto e DOIS envelopes"


def test_o_terceiro_arranjo_nao_e_alcancavel_por_montar_pelos_dois_arranjos(folha):
    """A razão de a folha montar por `ARRANJO_POR_NOME`, e não pelo atalho.

    `montar_pelos_dois_arranjos` devolve só os dois de `ARRANJOS`. Se um dia ele
    passar a devolver os três, esta régua reprova — e aí o comentário do
    cabeçalho da folha é que está velho, não o código.
    """
    quadros = [b"\x00" * 200, b"\x00" * 200]
    pelos_dois = folha.af.montar_pelos_dois_arranjos(quadros, seq=1)
    assert set(pelos_dois) == {"ds5dongle", "senshi"}
    assert "common-preservado" in folha.af.ARRANJO_POR_NOME
    assert "common-preservado" not in pelos_dois


def test_a_luz_do_passo_zero_existe_nos_dois_envelopes(folha):
    from o_envelope_do_som_no_radio import ENVELOPES

    luzes = {linha.id for linha in folha.LINHAS if linha.id.startswith("a-luz-por-")}
    assert luzes == {f"a-luz-por-{e}" for e in ENVELOPES}, (
        "sem o passo 0 nos DOIS envelopes, «silêncio nos dois» não diz nada"
    )


def test_o_positivo_do_cabo_esta_na_folha_e_e_do_cabo(folha):
    linha = next(ln for ln in folha.LINHAS if ln.id == "tom-pelo-cabo")
    assert linha.so_transporte == folha.CABO
    assert linha.botoes and linha.botoes[0].acao == "tom-no-sink"


# ---------------------------------------------------------------------------
# 3. TODO POSITIVO TEM O NEGATIVO AO LADO
# ---------------------------------------------------------------------------


def test_toda_linha_que_manda_report_tem_o_par_com_crc_errado(folha):
    sem_par = []
    for linha in folha.LINHAS:
        manda = [b for b in linha.botoes if b.acao in ("luz", "audio")]
        if manda and not any(b.crc_errado for b in manda):
            sem_par.append(linha.id)
        if manda and not any(not b.crc_errado for b in manda):
            sem_par.append(linha.id + " (só o negativo)")
    assert not sem_par, f"estas linhas medem sem controle negativo: {sem_par}"


def test_o_crc_errado_corrompe_so_o_rabo_e_o_produto_deixa_de_reconhecer(folha, rep):
    common = folha.af.common_de_audio()
    bom = folha.pacotes_do_tom("ds5dongle", segundos=0.10, common=common)[0]
    ruim = folha.pacotes_do_tom("ds5dongle", segundos=0.10, common=common, crc_errado=True)[0]
    assert bom[:-4] == ruim[:-4], "o negativo tem de mudar SÓ o CRC"
    assert int.from_bytes(bom[-4:], "little") == rep.bt_crc32(bom[:-4], seed=rep.BT_CRC_SEED)
    assert int.from_bytes(ruim[-4:], "little") != rep.bt_crc32(ruim[:-4], seed=rep.BT_CRC_SEED)


# ---------------------------------------------------------------------------
# 4. A CONDIÇÃO É O `common` DO PRODUTO — nenhum offset mora na folha
# ---------------------------------------------------------------------------


def test_a_condicao_da_coluna_e_exatamente_o_common_do_produto(folha, rep):
    coluna = folha.Coluna(alvo=_aparelho(folha, folha.RADIO, "hidraw91", "aa:bb:cc:00:00:02"))
    coluna.volume, coluna.rota, coluna.preamp = 200, rep.SAIDA_SO_NO_ALTO_FALANTE, 5
    assert coluna.common() == folha.af.common_de_audio(
        volume=200, rota=rep.SAIDA_SO_NO_ALTO_FALANTE, preamp=5
    )
    # E o produto põe o volume onde o mapa diz — a folha não escolhe posição.
    assert coluna.common()[rep.COMMON_SPEAKER_VOLUME] == 200


def test_os_tres_campos_da_condicao_sao_os_tres_parametros_do_produto(folha):
    """A linha da condição É a assinatura de `af.common_de_audio`, e não uma cópia."""
    import inspect

    condicao = next(ln for ln in folha.LINHAS if ln.id == "condicao-do-alto-falante")
    atributos = {campo.atributo for campo in condicao.campos}
    do_produto = set(inspect.signature(folha.af.common_de_audio).parameters)
    assert atributos == do_produto == {"volume", "rota", "preamp"}
    assert condicao.assumir, "sem posse não há martelo, e o daemon reescreve os três"


def test_o_volume_dela_chega_ao_report_de_audio_do_arranjo_que_carrega_o_common(folha, rep):
    """O `common-preservado` leva a condição DENTRO do report de áudio.

    É o único dos três que leva — e é por isso que o martelo da condição não é
    enfeite para os outros dois: neles o volume é o do último `0x31`.
    """
    common = folha.af.common_de_audio(volume=201)
    pacote = folha.pacotes_do_tom("common-preservado", segundos=0.10, common=common)[0]
    assert bytes(pacote[3 : 3 + rep.COMMON_LEN]) == common
    assert pacote[3 + rep.COMMON_SPEAKER_VOLUME] == 201


def test_o_ritmo_sai_do_arranjo_e_nao_de_um_numero_digitado(folha):
    for nome, arranjo in folha.af.ARRANJO_POR_NOME.items():
        assert folha.ms_por_report(nome) == arranjo.quadros_de_audio * folha.af.MS_POR_QUADRO


# ---------------------------------------------------------------------------
# 5. A RECUSA É DITA — e a mesa incompleta diz QUAL metade falta
# ---------------------------------------------------------------------------


def test_toda_linha_de_um_transporte_so_tem_a_frase_de_recusa(folha):
    mudas = [ln.id for ln in folha.LINHAS if ln.so_transporte and not ln.recusa]
    assert not mudas, (
        f"estas linhas ficariam MUDAS na coluna do outro transporte: {mudas} — "
        "e coluna muda lê-se como «não fizeram nada»"
    )


def test_os_cruzamentos_recusam_no_cabo_e_o_positivo_recusa_no_radio(folha):
    por_id = {ln.id: ln for ln in folha.LINHAS}
    assert por_id["tom-pelo-cabo"].so_transporte == folha.CABO
    assert por_id["audio-ds5dongle-por-data"].so_transporte == folha.RADIO
    assert por_id["a-luz-por-set_report"].so_transporte == folha.RADIO


def test_a_mesa_incompleta_diz_qual_metade_falta(folha):
    def colunas(*transportes):
        return [
            folha.Coluna(alvo=_aparelho(folha, t, f"hidraw9{i}", f"aa:bb:cc:00:00:0{i}"))
            for i, t in enumerate(transportes)
        ]

    assert folha.mesa_incompleta(colunas(folha.CABO, folha.RADIO)) == ""
    so_cabo = folha.mesa_incompleta(colunas(folha.CABO, folha.CABO))
    assert "RÁDIO" in so_cabo and "2 no cabo e 0 no rádio" in so_cabo
    so_radio = folha.mesa_incompleta(colunas(folha.RADIO))
    assert "CABO" in so_radio and "POSITIVO" in so_radio
    assert "não achei nenhum" in folha.mesa_incompleta([])


# ---------------------------------------------------------------------------
# 6. `--listar` E `--oculta` NÃO TOCAM NO APARELHO
# ---------------------------------------------------------------------------


@pytest.fixture()
def espiao(folha, monkeypatch):
    """A mesa de mentira, a rota de mentira, e um alarme na porta do aparelho."""
    abertas: list[str] = []

    def nunca(caminho, **_kw):
        abertas.append(caminho)
        raise AssertionError(f"esta corrida abriu o nó {caminho} — não podia")

    monkeypatch.setattr(folha, "alvos_da_mesa", lambda: _mesa_de_dois(folha))
    monkeypatch.setattr(folha, "abrir_no_hidraw", nunca)
    monkeypatch.setattr(
        folha,
        "rota_do_controle",
        lambda alvo, uniqs: folha.af.RotaDoNo(
            alvo.transporte == folha.CABO,
            sink="alsa_output.de_mentira" if alvo.transporte == folha.CABO else "",
            por_onde="cabo",
            motivo="" if alvo.transporte == folha.CABO else "o som ainda não chega pelo rádio",
        ),
    )
    return abertas


def test_listar_nao_abre_no_nem_escreve_byte(folha, espiao, capsys):
    assert folha.main(["--listar"]) == 0
    assert espiao == []
    saida = capsys.readouterr().out
    assert "leitura pura" in saida
    assert "o par está na mesa" in saida


def test_oculta_nao_abre_no_e_imprime_a_forma_de_toda_linha(folha, espiao, capsys):
    assert folha.main(["--oculta"]) == 0
    assert espiao == [], "a régua abriu porta no aparelho — ela roda sem ela na frente"
    saida = capsys.readouterr().out
    for linha in folha.LINHAS:
        assert f"LINHAS PROPOSTAS — {linha.titulo}" in saida
    assert "scripts/ensaios/a_folha_do_som_por_controle.py" in saida


def test_a_porta_abre_na_primeira_escrita_e_nunca_no_construtor(folha, monkeypatch):
    """A cura de (6), medida onde ela mora: a `Coluna` nasce sem porta."""
    pedidos: list[str] = []

    class _No:
        fd = 7

        def fechar(self) -> None:
            pass

    monkeypatch.setattr(
        folha, "abrir_no_hidraw", lambda caminho, **_k: (pedidos.append(caminho), _No())[1]
    )
    coluna = folha.Coluna(alvo=_aparelho(folha, folha.RADIO, "hidraw91", "aa:bb:cc:00:00:02"))
    assert pedidos == [], "a porta abriu no construtor"
    coluna.bater()  # sem «Assumir» ligado o martelo não bate, e não abre nada
    assert pedidos == []
    coluna.assumido = True
    monkeypatch.setattr(folha, "enviar", lambda *_a, **_k: None)
    coluna.bater()
    assert pedidos == ["/dev/hidraw91"], "a primeira escrita é que abre a porta"
    assert coluna.escritas == 1


# ---------------------------------------------------------------------------
# O anonimato e a forma da linha do caderno
# ---------------------------------------------------------------------------


def test_nenhum_endereco_inteiro_sai_na_saida(folha, espiao, capsys):
    folha.main(["--oculta"])
    saida = capsys.readouterr().out
    assert "aa:bb:cc:00:00:01" in saida, "a régua tem de achar o endereço mascarado"
    assert "aa:bb:cc:dd" not in saida


def test_a_linha_proposta_segue_o_cabecalho_do_caderno(folha, espiao, capsys):
    from escrita_pelo_broker import COLUNAS_DO_CADERNO

    folha.main(["--oculta"])
    propostas = [
        ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("som-condicao-")
    ]
    assert propostas, "nenhuma linha proposta saiu"
    for proposta in propostas:
        assert proposta.count(",") >= len(COLUNAS_DO_CADERNO) - 1
        campos = proposta.split(",")
        assert campos[1].startswith("audio.alto_falante")
        assert campos[2] in ("cabo", "radio")
    assert not any("é" in ln.split(",")[0] for ln in propostas), (
        "o `id` do caderno é chave de CSV: sem acento"
    )


# ---------------------------------------------------------------------------
# 7. A RAJADA — ela sai inteira, pelo envelope pedido, e PARA no primeiro «não»
# ---------------------------------------------------------------------------


class _Relogio:
    """O laço do GTK, de mentira: guarda o agendado e me deixa girar na mão.

    Sem ele o `timeout_add` de verdade fica pendurado no contexto padrão até o
    fim da sessão de teste — e dispararia `enviar()` sobre um descritor de
    mentira no dia em que qualquer outro teste rodasse um `Gtk.main()`.
    """

    def __init__(self) -> None:
        self.agendados: list[tuple[int, object, tuple]] = []

    def timeout_add(self, ms, callback, *args):
        self.agendados.append((ms, callback, args))
        return len(self.agendados)

    def girar(self, teto: int = 10_000) -> int:
        _ms, callback, args = self.agendados[-1]
        voltas = 0
        while callback(*args) and voltas < teto:
            voltas += 1
        return voltas


@pytest.fixture()
def bancada(folha, monkeypatch):
    """Uma folha de UMA coluna no rádio, com porta de mentira e relógio na mão."""
    from gi.repository import GLib

    class _No:
        fd = 7

        def fechar(self) -> None:
            pass

    enviados: list[tuple[bytes, str]] = []
    monkeypatch.setattr(folha, "abrir_no_hidraw", lambda _c, **_k: _No())
    monkeypatch.setattr(folha, "enviar", lambda _fd, p, e: enviados.append((p, e)))
    relogio = _Relogio()
    monkeypatch.setattr(GLib, "timeout_add", relogio.timeout_add)
    coluna = folha.Coluna(alvo=_aparelho(folha, folha.RADIO, "hidraw91", "aa:bb:cc:00:00:02"))
    tela = folha.Folha([coluna], enxuta=True, segundos=0.10)
    return tela, coluna, enviados, relogio


def _linha_e_botao(folha, linha_id: str, *, crc_errado: bool):
    linha = next(ln for ln in folha.LINHAS if ln.id == linha_id)
    return linha, next(b for b in linha.botoes if b.crc_errado is crc_errado)


def test_a_rajada_manda_o_tom_inteiro_pelo_envelope_pedido(folha, bancada):
    from gi.repository import Gtk

    tela, coluna, enviados, relogio = bancada
    linha, botao = _linha_e_botao(folha, "audio-senshi-por-set_report", crc_errado=False)
    esperados = folha.pacotes_do_tom("senshi", segundos=0.10, common=coluna.common())

    assert tela._bombear(coluna, linha, botao, Gtk.Label()) == ""
    relogio.girar()

    assert [e for _p, e in enviados] == ["set_report"] * len(esperados), (
        "a rajada mudou de envelope no meio, ou não saiu inteira"
    )
    assert len(enviados) == len(esperados) and coluna.escritas == len(esperados)
    assert coluna.rajada_em_voo == "", "a folha ficou achando que ainda está tocando"


def test_a_rajada_adianta_o_nibble_de_sequencia_do_controle(folha, bancada):
    from gi.repository import Gtk

    tela, coluna, _enviados, _relogio = bancada
    linha, botao = _linha_e_botao(folha, "audio-ds5dongle-por-data", crc_errado=False)
    quantos = len(folha.pacotes_do_tom("ds5dongle", segundos=0.10, common=coluna.common()))
    antes = coluna._seq

    tela._bombear(coluna, linha, botao, Gtk.Label())

    assert coluna._seq == (antes + quantos) & 0x0F, (
        "o martelo da condição voltaria a gastar números que a rajada já usou"
    )


def test_a_rajada_para_no_primeiro_nao_do_kernel_em_vez_de_insistir(folha, bancada, monkeypatch):
    """Um kernel sem HIDIOCSOUTPUT recusa TODOS — insistir 150 vezes só atrasa a resposta."""
    import errno

    from gi.repository import Gtk

    tela, coluna, enviados, relogio = bancada

    def recusa(_fd, _p, _e):
        raise OSError(errno.EINVAL, "Invalid argument")

    monkeypatch.setattr(folha, "enviar", recusa)
    linha, botao = _linha_e_botao(folha, "audio-ds5dongle-por-set_report", crc_errado=False)
    assert tela._bombear(coluna, linha, botao, Gtk.Label()) == ""
    relogio.girar()

    assert enviados == []
    assert coluna.escritas == 0
    feito = "; ".join(coluna.feito[linha.id])
    assert "1 recusa(s)" in feito and "Invalid argument" in feito, (
        "a recusa do kernel tem de chegar à nota do caderno, não morrer na tela"
    )


def test_o_negativo_manda_os_mesmos_bytes_com_o_rabo_corrompido(folha, bancada):
    from gi.repository import Gtk

    tela, coluna, enviados, relogio = bancada
    linha, botao = _linha_e_botao(folha, "audio-senshi-por-data", crc_errado=True)
    tela._bombear(coluna, linha, botao, Gtk.Label())
    relogio.girar()

    honestos = folha.pacotes_do_tom("senshi", segundos=0.10, common=coluna.common())
    assert len(enviados) == len(honestos)
    for (mandado, _e), honesto in zip(enviados, honestos, strict=True):
        assert mandado[:-4] == honesto[:-4], "o negativo mudou mais que o CRC"
        assert mandado[-4:] != honesto[-4:], "o negativo saiu com o CRC certo"


def test_o_devolver_tudo_desliga_as_chaves_e_nao_so_por_baixo(folha, bancada):
    tela, coluna, _enviados, _relogio = bancada
    assert tela.chaves, "a linha da condição tem de ter chave de posse"
    tela.chaves[0].set_active(True)
    assert coluna.assumido is True

    tela._devolver_tudo()

    assert coluna.assumido is False
    assert not any(chave.get_active() for chave in tela.chaves), (
        "chave ligada sobre coluna já devolvida é a tela mentindo sobre quem manda no byte"
    )
