"""O contador do que o jogo manda por tiro (08/10/2026).

``scripts/ensaios/contar_o_que_o_jogo_manda.py`` conta, numa GRAVAÇÃO do que o jogo escreveu no
controle, os blocos de gatilho, a luz, os motores e o áudio do jogo, por segundo e por tiro, e
responde às três perguntas da sprint. Aqui a gravação é sintética (uma rajada de três tiros, um
bloco de gatilho e uma cor por tiro) e o vpad gravador roda sobre o ``/dev/uhid`` de mentira do
``test_uhid_replica``. Nenhum aparelho, nenhum daemon, nenhum jogo.

Cada régua tem a sua mordida: apagar um bloco da gravação derruba o número, contar a luz como
gatilho reprova, deduplicar os blocos iguais reprova, e o gravador anota ANTES da deduplicação
do produto (o produto entrega ao sink só o bloco que mudou).
"""

from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad as ug

RAIZ = Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "ensaios" / "contar_o_que_o_jogo_manda.py"
PROTOCOLO = RAIZ / "docs" / "protocol" / "o-que-o-jogo-manda-por-tiro.md"


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("contar_o_que_o_jogo_manda", INSTRUMENTO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


ens: Any = _carregar()
Evento = ens.Evento

ARMA = bytes([0x25, 2, 6, 5, 0, 0, 0, 0, 0, 0, 0])
VIBRACAO = bytes([0x26, 40, 3, 0, 0, 0, 0, 0, 0, 0, 0])
OFF = bytes([0x05] + [0] * 10)


def corpo(*, direito: bytes | None = None, esquerdo: bytes | None = None,
          cor: tuple[int, int, int] | None = None, jogador: int | None = None,
          motores: tuple[int, int] | None = None, flag0_extra: int = 0,
          flag1_extra: int = 0) -> bytes:
    """O report 0x02 sem o id (47 bytes), com as flags que a cada campo cabem."""
    c = bytearray(47)
    c[0] |= flag0_extra
    c[1] |= flag1_extra
    if direito is not None:
        c[0] |= 0x04
        c[10:21] = direito
    if esquerdo is not None:
        c[0] |= 0x08
        c[21:32] = esquerdo
    if cor is not None:
        c[1] |= 0x04
        c[44:47] = bytes(cor)
    if jogador is not None:
        c[1] |= 0x10
        c[43] = jogador
    if motores is not None:
        c[0] |= 0x01
        c[2], c[3] = motores
    return bytes(c)


def saida(t: float, **kw: Any) -> Any:
    return Evento(t, "saida", corpo(**kw))


def rajada_de_audio(t: float, quadros: int = 3) -> list[Any]:
    return [Evento(t + i * 0.01, "audio", energia=0.5) for i in range(quadros)]


def tres_tiros(*, apagar: int | None = None) -> list[Any]:
    """Abre em 0, depois três tiros em 1,0 / 1,3 / 1,6 s: um bloco de arma e uma cor em cada."""
    eventos: list[Any] = [Evento(0.0, "abriu")]
    for i, t in enumerate((1.0, 1.3, 1.6)):
        eventos += rajada_de_audio(t)
        if i != apagar:
            eventos.append(saida(t + 0.001, direito=ARMA))
        eventos.append(saida(t + 0.002, cor=(255, 0, 0)))
    return eventos


def test_tres_tiros_dao_tres_blocos_de_gatilho_tres_cores_e_um_bloco_por_tiro() -> None:
    c = ens.contar(tres_tiros())
    assert c.categorias["gatilho_direito"].total == 3
    assert c.categorias["luz"].total == 3
    assert c.categorias["gatilho_esquerdo"].total == 0
    assert (c.tiros, c.origem_dos_tiros) == (3, "áudio dos canais 3 e 4")
    assert (c.blocos_de_gatilho_por_tiro_mediana, c.blocos_de_gatilho_por_tiro_maximo) == (1, 1)


def test_apagar_um_bloco_da_gravacao_derruba_o_numero() -> None:
    inteira = ens.contar(tres_tiros())
    faltando = ens.contar(tres_tiros(apagar=1))
    assert inteira.categorias["gatilho_direito"].total == 3
    assert faltando.categorias["gatilho_direito"].total == 2
    assert faltando.categorias["luz"].total == 3, "só o bloco apagado sai da conta"


def test_a_luz_nao_e_gatilho_e_o_gatilho_nao_e_luz() -> None:
    assert ens.categorias_do_corpo(corpo(cor=(1, 2, 3))) == ["luz"]
    assert ens.categorias_do_corpo(corpo(direito=ARMA)) == ["gatilho_direito"]
    assert ens.categorias_do_corpo(corpo(esquerdo=ARMA, direito=ARMA, cor=(1, 2, 3))) == [
        "gatilho_direito", "gatilho_esquerdo", "luz"]
    assert ens.categorias_do_corpo(corpo(jogador=0b00100)) == ["luzes_de_jogador"]
    assert ens.categorias_do_corpo(corpo(motores=(10, 20))) == ["motores"]
    assert ens.categorias_do_corpo(b"") == []


def test_bloco_escrito_sem_a_flag_ligada_nao_conta() -> None:
    c = bytearray(corpo(direito=ARMA))
    c[0] = 0
    assert ens.categorias_do_corpo(bytes(c)) == []
    assert ens.blocos_de_gatilho(bytes(c)) == {}


def test_o_audio_do_jogo_conta_so_com_volume() -> None:
    sem_volume = corpo(flag0_extra=0x40)
    assert "audio_do_jogo" not in ens.categorias_do_corpo(sem_volume)
    com_volume = bytearray(sem_volume)
    com_volume[5] = 0x80
    assert "audio_do_jogo" in ens.categorias_do_corpo(bytes(com_volume))


def test_blocos_iguais_em_seguida_contam_todos() -> None:
    """O jogo que reescreve o mesmo bloco três vezes escreveu três vezes."""
    eventos = [saida(1.0 + i * 0.05, direito=ARMA) for i in range(3)]
    assert ens.contar(eventos).categorias["gatilho_direito"].total == 3


def test_por_segundo_e_pico_em_um_segundo() -> None:
    eventos = [saida(0.0 + i * 0.1, direito=ARMA) for i in range(5)]
    eventos += [saida(3.0, direito=ARMA), saida(4.0, direito=ARMA)]
    cat = ens.contar(eventos).categorias["gatilho_direito"]
    assert cat.total == 7
    assert cat.pico_por_segundo == 5
    assert cat.por_segundo == pytest.approx(7 / 4.0)


def test_o_bloco_pertence_ao_tiro_cuja_janela_o_contem() -> None:
    eventos = rajada_de_audio(1.0) + rajada_de_audio(1.5)
    eventos += [saida(1.01 + i * 0.01, direito=ARMA) for i in range(4)]
    eventos += [saida(1.51, direito=ARMA)]
    c = ens.contar(eventos)
    assert c.tiros == 2
    assert c.blocos_de_gatilho_por_tiro_maximo == 4
    assert c.blocos_de_gatilho_por_tiro_mediana == 2.5


def test_as_marcas_de_tiro_valem_mais_que_o_audio() -> None:
    eventos = rajada_de_audio(1.0) + rajada_de_audio(1.5) + rajada_de_audio(2.0)
    eventos += [Evento(1.0, "tiro")]
    c = ens.contar(eventos)
    assert (c.tiros, c.origem_dos_tiros) == (1, "marcas")


def test_sem_tiros_nao_ha_por_tiro_e_a_resposta_diz_sem_dado() -> None:
    c = ens.contar([saida(1.0, direito=ARMA), saida(2.0, direito=ARMA)])
    assert c.tiros == 0 and c.origem_dos_tiros == "nenhuma"
    assert c.blocos_de_gatilho_por_tiro_mediana is None
    assert "sem dado" in ens.respostas(c)[0]


def test_tiros_do_audio_separa_rajadas_pelo_silencio_e_ignora_o_abaixo_do_limiar() -> None:
    assert ens.tiros_do_audio(rajada_de_audio(1.0, quadros=5)) == [1.0]
    duas = rajada_de_audio(1.0, 2) + rajada_de_audio(1.3, 2)
    assert ens.tiros_do_audio(duas) == [1.0, 1.3]
    baixo = [Evento(t / 100, "audio", energia=0.01) for t in range(100, 120)]
    assert ens.tiros_do_audio(baixo) == []


def _off_e_volta(intervalo: float, volta: bytes = ARMA) -> list[Any]:
    return [
        saida(1.0, direito=ARMA), saida(1.1, direito=OFF), saida(1.1 + intervalo, direito=volta),
    ]


def test_off_e_o_mesmo_efeito_em_menos_de_4_ms_e_sim() -> None:
    c = ens.contar(_off_e_volta(0.002))
    assert c.off_e_o_mesmo_em_menos_de_4ms == 1
    assert "sim (1 vez" in ens.respostas(c)[1]


def test_off_e_o_mesmo_efeito_em_10_ms_nao_conta() -> None:
    assert ens.contar(_off_e_volta(0.010)).off_e_o_mesmo_em_menos_de_4ms == 0


def test_off_e_outro_efeito_em_menos_de_4_ms_nao_conta() -> None:
    assert ens.contar(_off_e_volta(0.002, volta=VIBRACAO)).off_e_o_mesmo_em_menos_de_4ms == 0


def test_sem_bloco_de_gatilho_o_off_e_sem_dado_e_nunca_nao() -> None:
    """Uma gravação só de luz não sabe se o jogo rearma: a resposta é «sem dado», não «não»."""
    c = ens.contar([Evento(0.0, "abriu"), saida(1.0, cor=(255, 0, 0)),
                    saida(1.5, cor=(0, 255, 0))])
    assert c.off_e_o_mesmo_em_menos_de_4ms is None
    assert "4 ms: sem dado" in ens.respostas(c)[1]


def test_o_off_de_um_lado_nao_casa_com_o_efeito_do_outro() -> None:
    eventos = [saida(1.0, direito=ARMA), saida(1.1, esquerdo=OFF), saida(1.101, direito=ARMA)]
    assert ens.contar(eventos).off_e_o_mesmo_em_menos_de_4ms == 0


def test_o_modo_cru_zero_tambem_e_off() -> None:
    cru = bytes(11)
    eventos = [saida(1.0, esquerdo=ARMA), saida(1.1, esquerdo=cru), saida(1.102, esquerdo=ARMA)]
    assert ens.contar(eventos).off_e_o_mesmo_em_menos_de_4ms == 1


def test_gatilho_em_meio_segundo_depois_de_abrir_e_sim() -> None:
    c = ens.contar([Evento(0.0, "abriu"), saida(0.2, direito=ARMA)])
    assert c.gatilho_nos_primeiros_meio_segundo is True
    assert "sim" in ens.respostas(c)[2]


def test_gatilho_depois_de_meio_segundo_e_nao() -> None:
    c = ens.contar([Evento(0.0, "abriu"), saida(0.7, direito=ARMA)])
    assert c.gatilho_nos_primeiros_meio_segundo is False
    assert ens.respostas(c)[2].endswith("não")


def test_sem_abertura_ou_sem_gatilho_e_sem_dado() -> None:
    assert ens.contar([saida(0.2, direito=ARMA)]).gatilho_nos_primeiros_meio_segundo is None
    assert ens.contar(
        [Evento(0.0, "abriu"), saida(0.2, cor=(1, 1, 1))]
    ).gatilho_nos_primeiros_meio_segundo is None


def test_cada_abertura_tem_a_sua_janela() -> None:
    """Basta uma sessão com o gatilho cedo; sem nenhuma, a resposta é «não»."""
    eventos = [
        Evento(0.0, "abriu"), saida(2.0, direito=ARMA),
        Evento(10.0, "abriu"), saida(10.1, direito=ARMA),
    ]
    assert ens.contar(eventos).gatilho_nos_primeiros_meio_segundo is True
    eventos = [
        Evento(0.0, "abriu"), saida(0.1, direito=ARMA),
        Evento(10.0, "abriu"), saida(12.0, direito=ARMA),
    ]
    assert ens.contar(eventos).gatilho_nos_primeiros_meio_segundo is True
    nenhum = [Evento(0.0, "abriu"), Evento(10.0, "abriu"), saida(12.0, direito=ARMA)]
    assert ens.contar(nenhum).gatilho_nos_primeiros_meio_segundo is False


def test_gravacao_vazia_nao_tem_o_que_contar() -> None:
    with pytest.raises(ValueError, match="vazia"):
        ens.contar([])


def test_a_gravacao_vai_e_volta_sem_perder_nada() -> None:
    eventos = sorted(tres_tiros(), key=lambda e: e.t)
    de_volta = ens.ler_gravacao(ens.escrever_gravacao(eventos))
    assert [(e.tipo, e.corpo) for e in de_volta] == [(e.tipo, e.corpo) for e in eventos]
    assert ens.contar(de_volta) == ens.contar(eventos)


def test_linha_torta_da_gravacao_diz_o_numero_da_linha() -> None:
    texto = '{"t": 1.0, "tipo": "abriu"}\nnão é json\n'
    with pytest.raises(ValueError, match="linha 2"):
        ens.ler_gravacao(texto)
    with pytest.raises(ValueError, match="linha 1"):
        ens.ler_gravacao('{"t": 1.0, "tipo": "inventado"}\n')
    with pytest.raises(ValueError, match="linha 1"):
        ens.ler_gravacao('{"tipo": "abriu"}\n')


def _output_event(report: bytes) -> bytes:
    event = struct.pack("<I", ug.UHID_OUTPUT)
    event += report.ljust(ug.HID_MAX_DESCRIPTOR_SIZE, b"\0")[: ug.HID_MAX_DESCRIPTOR_SIZE]
    event += struct.pack("<HB", len(report), 1)
    return event


def _evento(tipo: int) -> bytes:
    return struct.pack("<I", tipo) + bytes(8)


def test_o_corpo_do_uhid_output_e_o_report_sem_o_id() -> None:
    c = corpo(direito=ARMA)
    assert ens.corpo_do_uhid_output(_output_event(bytes([0x02]) + c)) == c
    assert ens.corpo_do_uhid_output(_output_event(bytes([0x31]) + c)) is None
    assert ens.corpo_do_uhid_output(_output_event(b"\x02")) is None
    assert ens.corpo_do_uhid_output(b"curto") is None


class _FakeFd:
    def __init__(self) -> None:
        self.reads: list[bytes] = []


class _Relogio:
    t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture()
def fake_uhid(monkeypatch: pytest.MonkeyPatch) -> _FakeFd:
    fake = _FakeFd()
    monkeypatch.setattr(ug.os, "open", lambda *_a, **_k: 4242)
    monkeypatch.setattr(ug.os, "close", lambda _fd: None)
    monkeypatch.setattr(ug.os, "set_blocking", lambda _fd, _b: None)
    monkeypatch.setattr(ug.os, "write", lambda _fd, data: len(data))

    def _read(_fd: int, _size: int) -> bytes:
        if not fake.reads:
            raise BlockingIOError
        return fake.reads.pop(0)

    monkeypatch.setattr(ug.os, "read", _read)
    return fake


def _blueprint() -> dict[str, Any]:
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: bytes([0x05]) + bytes(40),
            0x09: bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13),
            0x20: bytes([0x20]) + bytes(63),
        },
    }


def _tres_iguais_no_vpad_do_produto(fake_uhid: _FakeFd) -> tuple[Any, list[tuple[str, bytes]]]:
    """Um vpad do PRODUTO recebe o mesmo bloco três vezes e um eco de outro id."""
    entregues: list[tuple[str, bytes]] = []
    relogio = _Relogio()
    pad = ug.UhidDualSense(
        player=1, blueprint=_blueprint(), time_fn=relogio, sleep_fn=lambda _s: None,
        trigger_sink=lambda lado, bloco: entregues.append((lado, bloco)))
    pad._sem_gadget = True
    assert pad.start() is True
    fake_uhid.reads += [_evento(ug.UHID_START), _evento(ug.UHID_OPEN)]
    pad.pump_ff()
    relogio.t = 1.0
    c = corpo(direito=ARMA)
    fake_uhid.reads += [_output_event(bytes([0x02]) + c)] * 3
    fake_uhid.reads.append(_output_event(bytes([0x31]) + c))
    pad.pump_ff()
    return pad, entregues


def test_a_escuta_anota_no_vpad_do_produto_antes_da_deduplicacao(fake_uhid: _FakeFd) -> None:
    """O jogo escreve o MESMO bloco três vezes: o produto entrega um só, a escuta anota três."""
    eventos: list[ens.Evento] = []
    tirar = ens.instalar_escuta(eventos)
    try:
        _pad, entregues = _tres_iguais_no_vpad_do_produto(fake_uhid)
    finally:
        tirar()

    c = corpo(direito=ARMA)
    assert [e.tipo for e in eventos] == ["abriu", "saida", "saida", "saida"]
    assert all(e.corpo == c for e in eventos if e.tipo == "saida")
    assert len(entregues) == 1, "o produto deduplica: a escuta existe para não subcontar"
    assert ens.contar(eventos).categorias["gatilho_direito"].total == 3


def test_tirada_a_escuta_o_vpad_do_produto_volta_a_ser_o_mesmo(fake_uhid: _FakeFd) -> None:
    original = ug.UhidDualSense.__dict__["_handle_event"]
    eventos: list[ens.Evento] = []
    ens.instalar_escuta(eventos)()
    assert ug.UhidDualSense.__dict__["_handle_event"] is original
    _tres_iguais_no_vpad_do_produto(fake_uhid)
    assert eventos == [], "tirada, a escuta não anota mais nada"


def test_a_gravacao_roda_o_daemon_com_a_escuta_e_a_tira_mesmo_se_ele_cai(
    fake_uhid: _FakeFd,
) -> None:
    """O jogo atira pelo vpad que o DAEMON liga ao físico: a gravação é o daemon com a escuta."""
    original = ug.UhidDualSense.__dict__["_handle_event"]

    def daemon_que_cria_o_vpad_e_cai() -> int:
        _tres_iguais_no_vpad_do_produto(fake_uhid)
        raise RuntimeError("o daemon caiu")

    with pytest.raises(RuntimeError):
        ens.gravar_no_aparelho(60.0, rodar_o_daemon=daemon_que_cria_o_vpad_e_cai)
    assert ug.UhidDualSense.__dict__["_handle_event"] is original

    eventos = ens.gravar_no_aparelho(
        60.0, rodar_o_daemon=lambda: (_tres_iguais_no_vpad_do_produto(fake_uhid), 0)[1])
    assert [e.tipo for e in eventos] == ["abriu", "saida", "saida", "saida"]
    assert ug.UhidDualSense.__dict__["_handle_event"] is original


def test_ler_imprime_a_tabela_e_as_tres_respostas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arquivo = tmp_path / "g.jsonl"
    arquivo.write_text(ens.escrever_gravacao(tres_tiros()), encoding="utf-8")
    assert ens.main(["--ler", str(arquivo), "--transporte", "radio", "--controle", "P2"]) == 0
    saida_ = capsys.readouterr().out
    assert ens.CABECALHO_DA_TABELA in saida_
    assert "| PRAGMATA | radio | P2 | gatilho_direito | 3 |" in saida_
    assert "blocos de gatilho por tiro: mediana 1, máximo 1 em 3 tiro(s)" in saida_
    assert "em menos de 4 ms: não" in saida_
    assert "primeiros 0,5 s depois de abrir o controle: não" in saida_


def test_ler_um_arquivo_que_nao_existe_ou_torto_e_sem_dado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ens.main(["--ler", str(tmp_path / "nao-existe.jsonl")]) == ens.RC_SEM_DADO
    torto = tmp_path / "torto.jsonl"
    torto.write_text("lixo\n", encoding="utf-8")
    assert ens.main(["--ler", str(torto)]) == ens.RC_SEM_DADO
    assert "SEM DADO" in capsys.readouterr().out


def test_gravar_recusa_e_nao_sobe_o_vpad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import latencia_do_tato as lat

    monkeypatch.setattr(lat, "recusas", lambda *_a, **_k: ["há daemon no ar"])

    def nao_pode(*_a: object, **_k: object) -> None:
        raise AssertionError("recusado: o vpad não pode subir")

    monkeypatch.setattr(ens, "gravar_no_aparelho", nao_pode)
    rc = ens.main(["--gravar", "5", "--saida", str(tmp_path / "g.jsonl")])
    assert rc == ens.RC_RECUSADO
    assert "RECUSADO: há daemon no ar" in capsys.readouterr().out
    assert not (tmp_path / "g.jsonl").exists()


def test_gravar_sem_saida_e_recusado(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import latencia_do_tato as lat

    monkeypatch.setattr(lat, "recusas", lambda *_a, **_k: [])
    monkeypatch.setattr(ens, "gravar_no_aparelho", lambda *_a, **_k: pytest.fail("sem --saida"))
    assert ens.main(["--gravar", "5"]) == ens.RC_RECUSADO
    assert "--saida" in capsys.readouterr().out


def test_gravar_guarda_a_gravacao_e_conta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import latencia_do_tato as lat

    monkeypatch.setattr(lat, "recusas", lambda *_a, **_k: [])
    monkeypatch.setattr(ens, "gravar_no_aparelho", lambda *_a, **_k: tres_tiros())
    destino = tmp_path / "g.jsonl"
    assert ens.main(["--gravar", "5", "--saida", str(destino)]) == 0
    assert len(ens.ler_gravacao(destino.read_text(encoding="utf-8"))) == len(tres_tiros())
    assert ens.CABECALHO_DA_TABELA in capsys.readouterr().out


def test_os_offsets_e_as_flags_sao_os_do_vpad() -> None:
    """O contador lê o report como o produto o lê: se o vpad mudar um offset, esta régua reprova."""
    assert ens.OFFSET_FLAG0 == ug._VALID_FLAG0_OFFSET
    assert ens.OFFSET_FLAG1 == ug._VALID_FLAG1_OFFSET
    assert ens.OFFSET_GATILHO_DIREITO == ug._TRIGGER_R_BLOCK_OFFSET
    assert ens.OFFSET_GATILHO_ESQUERDO == ug._TRIGGER_L_BLOCK_OFFSET
    assert ens.TAMANHO_DO_BLOCO == ug._TRIGGER_BLOCK_LEN
    assert ens.OFFSET_LEDS_DE_JOGADOR == ug._PLAYER_LEDS_OFFSET
    assert ens.OFFSET_COR_DA_BARRA == ug._LIGHTBAR_RGB_OFFSET
    assert ens.FLAG0_GATILHO_DIREITO == ug._TRIGGER_R_EFFECT_ENABLE
    assert ens.FLAG0_GATILHO_ESQUERDO == ug._TRIGGER_L_EFFECT_ENABLE
    assert ens.FLAG0_VIBRACAO == ug._VIBRATION_FLAGS
    assert ens.FLAG0_AUDIO_DO_JOGO == ug._AUDIO_FLAGS_DO_JOGO
    assert ens.FLAG1_BARRA == ug._LIGHTBAR_CONTROL_ENABLE
    assert ens.FLAG1_LEDS_DE_JOGADOR == ug._PLAYER_INDICATOR_CONTROL_ENABLE
    assert ens.PRIMEIRA_JANELA_S == ug._GAME_REPLICA_GRACE_S, (
        "a pergunta «nos primeiros 0,5 s» é a da graça do vpad: se uma muda, a outra segue")


def test_o_contador_concorda_com_o_vpad_sobre_quais_blocos_o_jogo_escreveu(
    fake_uhid: _FakeFd,
) -> None:
    """Para cada report, o lado que o contador acha é o que o vpad entrega ao sink."""
    casos: list[dict[str, Any]] = [
        {"direito": ARMA}, {"esquerdo": VIBRACAO}, {"direito": ARMA, "esquerdo": OFF},
    ]
    for kw in casos:
        entregues: list[str] = []
        relogio = _Relogio()
        pad = ug.UhidDualSense(
            player=1, blueprint=_blueprint(), time_fn=relogio, sleep_fn=lambda _s: None,
            trigger_sink=lambda lado, _b, destino=entregues: destino.append(lado))
        pad._sem_gadget = True
        assert pad.start() is True
        fake_uhid.reads += [_evento(ug.UHID_START), _evento(ug.UHID_OPEN)]
        pad.pump_ff()
        relogio.t = 1.0
        fake_uhid.reads.append(_output_event(bytes([0x02]) + corpo(**kw)))
        pad.pump_ff()
        lados = {"direito": "right", "esquerdo": "left"}
        esperados = sorted(lados[lado] for lado in ens.blocos_de_gatilho(corpo(**kw)))
        assert sorted(entregues) == esperados
        pad.stop()


def test_o_protocolo_traz_o_cabecalho_da_tabela_e_as_tres_perguntas() -> None:
    texto = PROTOCOLO.read_text(encoding="utf-8")
    assert ens.CABECALHO_DA_TABELA in texto
    assert "scripts/ensaios/contar_o_que_o_jogo_manda.py" in texto
    assert "blocos de gatilho por tiro" in texto
    assert "Off e o mesmo efeito em menos de 4 ms" in texto
    assert "primeiros 0,5 s depois de abrir o controle" in texto
