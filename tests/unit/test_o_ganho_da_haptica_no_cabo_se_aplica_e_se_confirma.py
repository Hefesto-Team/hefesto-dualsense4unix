"""O ganho da háptica no cabo chega ao fluxo do laço, e quem confirma é a leitura do fluxo.

O servidor de mentira guarda o que o ``module-stream-restore`` guarda (o volume por
``media.name``) e devolve esse volume a cada fluxo que nasce, como o servidor faz
com o laço que sobe de novo. Os ``126 %`` do fluxo são o fator linear ``2.0000``
pela raiz cúbica: tanto a escrita de agora quanto a restauração os deixam, e por
isso só a leitura do fluxo diz se o ganho pedido é o que está lá.

MORDIDAS:

* o ``casar`` sem a conferência do fluxo a cada passada: a restauração que chega
  depois da escrita fica, e a régua reprova;
* a confirmação pelo ``rc`` (sem reler o fluxo): o ``pactl`` que responde sem
  aplicar passa por aplicado, e a régua reprova;
* a passada logo depois de o laço subir dizendo a falha em ``info``: a falha
  ``sem_fluxo_do_laco`` volta ao diário a cada laço que sobe, e a régua reprova;
* a escrita sem olhar o fluxo antes: o laço que já nasce no ganho é reescrito, e a
  régua reprova.
"""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from hefesto_dualsense4unix.integrations.audio_ks_dualsense import MARCA_DO_LACO_DO_CABO
from hefesto_dualsense4unix.integrations.haptica_do_cabo import (
    HapticaDoCabo,
    RotaDoCabo,
    chave_do_aparelho,
)
from tests.unit import pactl_json_de_mentira as pj

_DONO = "aa:bb:cc:00:00:0b"
_MARCA = "APARELHOBRANCO"
_ROTA = RotaDoCabo(captura="61157", destino="60332", dono=_DONO)
_NORMA = 65536
_CANAIS = ("front-left", "front-right", "rear-left", "rear-right")


def _bruto(fator: float) -> int:
    """O valor que o ``pactl`` 16.1 manda por um fator linear (``pa_sw_volume_from_linear``)."""
    return 0 if fator <= 0 else round(fator ** (1 / 3) * _NORMA)


def _nome_da_midia() -> str:
    return f"{MARCA_DO_LACO_DO_CABO}{chave_do_aparelho(_MARCA)} output"


class _Servidor:
    """Os fluxos de saída, o que o ``stream-restore`` guarda, e o ``pactl`` que os lê e escreve."""

    def __init__(self, *, aplica: bool = True) -> None:
        self.fluxos: dict[int, dict[str, Any]] = {}
        self.guardado: dict[str, list[int]] = {}
        self.escritas: list[list[str]] = []
        self.aplica = aplica
        self._proximo = 300

    def nasce(self, nome: str) -> int:
        self._proximo += 1
        volume = list(self.guardado.get(nome, [_NORMA] * 4))
        self.fluxos[self._proximo] = {"nome": nome, "volume": volume}
        return self._proximo

    def restaura(self, indice: int, volume: Sequence[int]) -> None:
        self.fluxos[indice]["volume"] = list(volume)

    def motores(self, indice: int) -> list[int]:
        return list(self.fluxos[indice]["volume"][2:])

    def __call__(self, argv: list[str]) -> str | None:
        if pj.e_lista_json(argv, "sink-inputs"):
            return pj.texto(*(
                {**pj.fluxo(i, 60332, props={
                    "media.name": f["nome"],
                    "node.name": "output." + f["nome"].removesuffix(" output"),
                }), "channel_map": ",".join(_CANAIS), "volume": {
                    canal: {"value": v, "value_percent": f"{round(v * 100 / _NORMA)}%",
                            "db": "0.00 dB"}
                    for canal, v in zip(_CANAIS, f["volume"], strict=True)}}
                for i, f in self.fluxos.items()))
        if argv[:2] == ["pactl", "set-sink-input-volume"]:
            self.escritas.append(list(argv))
            indice = int(argv[2])
            if indice not in self.fluxos or not pj.o_pactl_aceita_os_volumes(argv[3:]):
                return None
            if self.aplica:
                volume = [_bruto(float(v)) for v in argv[3:]]
                self.fluxos[indice]["volume"] = volume
                self.guardado[self.fluxos[indice]["nome"]] = volume
            return ""
        return ""


class _Lacos:
    def __init__(self) -> None:
        self.ligados: set[str] = set()

    def esta_ligado(self, chave: str) -> bool:
        return chave in self.ligados

    def ligar(self, chave: str, **_kw: object) -> bool:
        self.ligados.add(chave)
        return True

    def desligar(self, chave: str) -> None:
        self.ligados.discard(chave)


@pytest.fixture
def servidor(monkeypatch: pytest.MonkeyPatch) -> _Servidor:
    """O servidor de mentira atrás do executor do produto: nada de injeção na háptica."""
    s = _Servidor()
    monkeypatch.setattr(afb, "_rodar", s)
    return s


def _linhas(
    diario: list[MutableMapping[str, Any]], evento: str
) -> list[MutableMapping[str, Any]]:
    return [r for r in diario if r["event"] == evento and r["log_level"] == "info"]


def test_os_126_por_cento_sao_o_fator_dois() -> None:
    """O fluxo a 126 % nos motores é o ``2.0000`` linear: o valor do ganho a 200 %."""
    assert _bruto(2.0) == 82570
    assert round(_bruto(2.0) * 100 / _NORMA) == 126


def test_o_laco_que_nasce_depois_recebe_o_ganho_na_passada_seguinte(servidor: _Servidor) -> None:
    servidor.guardado[_nome_da_midia()] = [_NORMA, _NORMA, 0, 0]
    cabo = HapticaDoCabo(_Lacos())
    with structlog.testing.capture_logs() as diario:
        cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
        assert not cabo.leva_os_motores(_MARCA)
        indice = servidor.nasce(_nome_da_midia())
        assert servidor.motores(indice) == [0, 0], "o fluxo nasce com o volume guardado"
        for _ in range(3):
            cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
    assert servidor.motores(indice) == [82570, 82570]
    assert cabo.leva_os_motores(_MARCA)
    assert len(servidor.escritas) == 1, f"escreveu {len(servidor.escritas)} vezes"
    assert len(_linhas(diario, "haptica_do_cabo_portao")) == 1
    assert _linhas(diario, "haptica_do_cabo_portao_falhou") == [], (
        "a passada em que o laço acabou de subir não é falha")


def test_o_stream_restore_que_chega_depois_nao_decide_o_ganho(servidor: _Servidor) -> None:
    indice = servidor.nasce(_nome_da_midia())
    cabo = HapticaDoCabo(_Lacos())
    cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
    cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
    assert servidor.motores(indice) == [82570, 82570]
    servidor.restaura(indice, [_NORMA, _NORMA, 0, 0])
    cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
    assert servidor.motores(indice) == [82570, 82570], "a restauração velha ficou no fluxo"


def test_o_pactl_que_responde_sem_aplicar_nao_confirma(servidor: _Servidor) -> None:
    servidor.aplica = False
    indice = servidor.nasce(_nome_da_midia())
    cabo = HapticaDoCabo(_Lacos())
    with structlog.testing.capture_logs() as diario:
        for _ in range(3):
            cabo.casar({_MARCA: _ROTA}, {_MARCA: 0.5})
    assert servidor.motores(indice) == [_NORMA, _NORMA]
    assert not cabo.leva_os_motores(_MARCA), "o rc 0 passou por volume aplicado"
    assert len(servidor.escritas) == 3, "cada passada tenta de novo"
    falhas = _linhas(diario, "haptica_do_cabo_portao_falhou")
    assert [(r["motivo"], r["uniq"]) for r in falhas] == [("fluxo_nao_confirmou", _DONO)]
    assert _linhas(diario, "haptica_do_cabo_portao") == []


def test_o_fluxo_que_ja_nasce_no_ganho_nao_se_reescreve(servidor: _Servidor) -> None:
    servidor.guardado[_nome_da_midia()] = [_NORMA, _NORMA, _bruto(2.0), _bruto(2.0)]
    servidor.nasce(_nome_da_midia())
    cabo = HapticaDoCabo(_Lacos())
    with structlog.testing.capture_logs() as diario:
        cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
        cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
    assert servidor.escritas == []
    assert cabo.leva_os_motores(_MARCA)
    assert len(_linhas(diario, "haptica_do_cabo_portao")) == 1


def test_o_ganho_novo_chega_ao_fluxo_e_ao_proximo_laco(servidor: _Servidor) -> None:
    lacos = _Lacos()
    indice = servidor.nasce(_nome_da_midia())
    cabo = HapticaDoCabo(lacos)
    cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
    cabo.casar({_MARCA: _ROTA}, {_MARCA: 2.0})
    cabo.casar({_MARCA: _ROTA}, {_MARCA: 0.5})
    assert servidor.motores(indice) == [_bruto(0.5)] * 2
    cabo.soltar(_MARCA)
    del servidor.fluxos[indice]
    novo = servidor.nasce(_nome_da_midia())
    assert servidor.motores(novo) == [_bruto(0.5)] * 2, "a restauração só repete a última escrita"


def test_o_laco_que_nao_nasce_diz_a_falha_uma_vez(servidor: _Servidor) -> None:
    cabo = HapticaDoCabo(_Lacos())
    with structlog.testing.capture_logs() as diario:
        for _ in range(4):
            cabo.casar({_MARCA: _ROTA}, {_MARCA: 1.0})
    falhas = _linhas(diario, "haptica_do_cabo_portao_falhou")
    assert [r["motivo"] for r in falhas] == ["sem_fluxo_do_laco"]
