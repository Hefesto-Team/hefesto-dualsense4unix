"""O microfone sem classe morta nem endereço no grafo de som.

O-MICROFONE-SEM-CLASSE-MORTA-NEM-ENDERECO-NO-GRAFO-01. Duas curas, duas mordidas:

* os dois escritores de nó do microfone (o medidor da luz e o alimentador do canal) publicam
  `hefesto.controle=<marca>`, a marca do aparelho que é a mesma no cabo e no rádio, e nunca o
  endereço (mordida: a propriedade `hefesto.uniq` de volta em `propriedades_do_canal`);
* a classe que alternava o mudo da fonte padrão não existe mais, nem o campo que a guardava no
  daemon (mordida: a classe de volta em `audio_control`).

Quatro controles forjados: a marca vem do controle, nunca do transporte nem do adaptador.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.integrations import (
    audio_control,
    canal_do_microfone,
    nivel_do_microfone,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import campo_do_controle

OS_QUATRO = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)

SRC = Path(__file__).resolve().parents[2] / "src"

DOZE_HEX = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{12}(?![0-9a-f])")
ENDERECO_COM_SEPARADOR = re.compile(r"(?i)(?:[0-9a-f]{2}[:\-_]){5}[0-9a-f]{2}")


def _argvs(uniq: str) -> dict[str, list[str]]:
    return {
        "medidor": nivel_do_microfone.argv_do_medidor("alsa_input.fonte", uniq),
        "alimentador": canal_do_microfone.argv_do_alimentador(
            uniq, "alsa_input.fonte", taxa_hz=48000, canais=2
        ),
    }


@pytest.mark.parametrize("uniq", OS_QUATRO)
def test_nenhum_argv_de_parec_do_produto_traz_endereco_nem_a_chave_antiga(uniq: str) -> None:
    for quem, argv in _argvs(uniq).items():
        texto = " ".join(argv)
        assert "hefesto.uniq" not in texto, f"o {quem} ainda publica a chave `hefesto.uniq`"
        assert not DOZE_HEX.search(texto), f"o {quem} publica doze hex seguidos: {argv}"
        assert not ENDERECO_COM_SEPARADOR.search(texto), f"o {quem} publica um endereço: {argv}"
        sufixo = uniq.replace(":", "")
        assert sufixo not in texto.lower()
        assert campo_do_controle(uniq)[0] in [a.removeprefix("--property=") for a in argv]


def test_a_marca_e_so_do_controle_e_os_quatro_nao_se_misturam() -> None:
    """Quatro controles (A e B no mesmo adaptador): cada argv leva só a marca do controle.

    O argv não recebe transporte nem adaptador: o controle que passa do rádio ao cabo e volta
    gera o mesmo argv.
    """
    marcas = {u: campo_do_controle(u) for u in OS_QUATRO}
    assert all(len(m) == 1 for m in marcas.values())
    assert len({m[0] for m in marcas.values()}) == 4, "dois controles ganharam a mesma marca"
    for uniq in OS_QUATRO:
        assert _argvs(uniq) == _argvs(uniq)
        for argv in _argvs(uniq).values():
            props = [a.removeprefix("--property=") for a in argv]
            assert marcas[uniq][0] in props
            assert not any(marcas[outro][0] in props for outro in OS_QUATRO if outro != uniq)


def test_o_produto_nao_escreve_a_chave_hefesto_uniq_em_lugar_nenhum() -> None:
    achados = [
        str(arquivo.relative_to(SRC))
        for arquivo in SRC.rglob("*.py")
        if "hefesto.uniq" in arquivo.read_text(encoding="utf-8")
    ]
    assert achados == [], f"a chave `hefesto.uniq` voltou ao código: {achados}"


def test_a_classe_que_alternava_o_mudo_da_fonte_padrao_nao_existe_mais() -> None:
    assert not hasattr(audio_control, "AudioControl")
    assert "AudioControl" not in audio_control.__all__
    for nome in audio_control.__all__:
        assert hasattr(audio_control, nome), f"`__all__` promete `{nome}` e o módulo não tem"
    campos = {campo.name for campo in dataclasses.fields(Daemon)}
    assert "_audio" not in campos, "o daemon ainda guarda o campo da classe removida"
    achados = [
        str(arquivo.relative_to(SRC))
        for arquivo in SRC.rglob("*.py")
        if re.search(r"^class AudioControl\b|\bAudioControl\(\)", arquivo.read_text("utf-8"), re.M)
    ]
    assert achados == [], f"a classe voltou ao código: {achados}"
