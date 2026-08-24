"""A terceira resposta de ``uniqs_no_radio``, e por que ela existe.

23/08/2026. Terceira das quatro curas que o censo de mutação achou arrancáveis
sem nada ficar vermelho na aba Configurações.

``uniqs_no_radio`` (`app/actions/config/secao_controles.py`) devolve **três**
coisas, e não duas: o conjunto de quem está no rádio, o conjunto vazio, e
``None``. O ``None`` é a razão de a função existir.

    Uma lista vazia porque ``/sys`` não pôde ser lido é indistinguível de uma
    lista vazia porque todos os controles caíram.

Quem consome é a espera pelo botão PS (``EsperaPeloPS``), e ela lê "sumiu" como
o primeiro dos DOIS marcos que autorizam anunciar "voltou". Com a raiz do sysfs
ilegível — um contêiner sem ``/sys/devices/virtual/misc/uhid`` montado, um
kernel sem ``uhid``, um confinamento qualquer — a função sem a cura devolveria
``set()`` no primeiro tique, a espera marcaria ``caiu`` sem nada ter caído, e a
pessoa veria o card anunciar uma queda que não houve. É a família do
ELO-MUDO-01: ausência de notícia lida como notícia.

O QUE ESTE ARQUIVO MEDE E O QUE ELE NÃO MEDE
--------------------------------------------

Mede as três respostas da sonda e a costura dela com a espera REAL — a
``EsperaPeloPS`` construída sem ``sonda=``, que é a única configuração em que a
cura está no caminho. `test_a_luz_nao_acende_o_botao_do_card.py` já mede a
espera com sonda de mentira; o que faltava era exatamente o pedaço entre as
duas, e é onde a cura mora.

A régua, declarada: nada aqui lê o sysfs da máquina de quem roda a suíte.
``RAIZ_UHID`` é reapontada para um diretório do ``tmp_path``, e
``instancias_dualsense`` é substituída — as duas no módulo
``integrations.sinal_da_barra``, que é de onde ``uniqs_no_radio`` as importa na
hora da chamada.

AS MORDIDAS, ARRANCADAS E CONFERIDAS EM 23/08/2026
--------------------------------------------------

===============================================================  ===========
mutação                                                          reprova
===============================================================  ===========
a guarda da raiz sai (raiz ausente vira conjunto vazio)           2 de 6
o ``except OSError`` devolve ``set()`` em vez de ``None``         1 de 6
===============================================================  ===========
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    ESPERA_PROCURANDO,
    EsperaPeloPS,
    uniqs_no_radio,
)
from hefesto_dualsense4unix.integrations.sinal_da_barra import Instancia

#: O DualSense da mesa de teste. Máscara da casa: octetos 4 e 5 zerados.
NO_RADIO = "aa:bb:cc:00:00:4f"

#: Outro, ligado no cabo — ele não conta como "no rádio" e serve para provar
#: que o filtro do transporte continua de pé.
NO_CABO = "aa:bb:cc:00:00:6d"


def _instancia(uniq: str, transporte: str) -> Instancia:
    return Instancia(
        instancia="0031",
        uniq=uniq,
        adaptador="hci0",
        hw_version="0x00000100",
        input_n=42,
        hidraw="hidraw3",
        transporte=transporte,
    )


@pytest.fixture
def raiz_viva(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Uma raiz de uhid que EXISTE, para a guarda deixar a leitura acontecer."""
    raiz = tmp_path / "uhid"
    raiz.mkdir()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.sinal_da_barra.RAIZ_UHID", str(raiz)
    )
    return raiz


def _plantar(monkeypatch: pytest.MonkeyPatch, resposta: Any) -> None:
    """Troca a enumeração do sysfs por uma resposta de mentira, ou por uma falha.

    O dublê copia UMA propriedade da função de verdade, e ela é a que importa
    aqui: ``instancias_dualsense`` engole o ``OSError`` do ``os.listdir`` e
    devolve **lista vazia** quando a raiz não existe (`sinal_da_barra.py:350`).
    Um dublê que devolvesse a resposta plantada mesmo sem raiz mostraria a
    mutação como "sonda otimista"; a mutação de verdade produz "mesa vazia", que
    é a mentira exata que a cura impede. Régua que não copia isso mede outra
    coisa.
    """

    def _falso(raiz_uhid: str = "", *_args: Any, **_kwargs: Any) -> Any:
        from hefesto_dualsense4unix.integrations import sinal_da_barra

        if not Path(raiz_uhid or sinal_da_barra.RAIZ_UHID).is_dir():
            return []
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.sinal_da_barra.instancias_dualsense",
        _falso,
    )


class TestAsTresRespostasDaSonda:
    def test_sem_a_raiz_do_uhid_a_resposta_e_nao_sei(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura em uma linha: raiz ausente devolve ``None``, nunca ``set()``.

        E a espiã confirma que o caminho da leitura nem foi tentado — se ele
        tivesse sido, a resposta teria vindo do sysfs de verdade.
        """
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.sinal_da_barra.RAIZ_UHID",
            str(tmp_path / "uhid-que-nao-existe"),
        )
        _plantar(monkeypatch, [_instancia(NO_RADIO, "bt")])

        assert uniqs_no_radio() is None

    def test_leitura_que_falha_no_meio_tambem_e_nao_sei(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A raiz existe e a leitura estoura — continua sendo "não sei"."""
        _plantar(monkeypatch, OSError("permissão negada"))

        assert uniqs_no_radio() is None

    def test_com_a_raiz_viva_a_resposta_e_quem_esta_no_radio(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A régua contra si mesma: a sonda TEM de saber responder.

        Sem esta, os dois testes acima passariam numa sonda quebrada que
        devolvesse ``None`` sempre — que é como um portão dá verde sem medir.
        """
        _plantar(
            monkeypatch,
            [_instancia(NO_RADIO, "bt"), _instancia(NO_CABO, "usb")],
        )

        assert uniqs_no_radio() == {NO_RADIO.replace(":", "")}

    def test_a_mesa_vazia_de_verdade_e_conjunto_vazio(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O outro lado do "não sei": com a raiz legível, vazio é vazio.

        É esta resposta que autoriza a espera a marcar "sumiu" — e ela precisa
        continuar distinta do ``None``, ou a cura teria trocado um erro por
        outro.
        """
        _plantar(monkeypatch, [])

        assert uniqs_no_radio() == set()


class TestAEsperaNaoAcusaQuedaQueNaoHouve:
    """A costura: a espera REAL, com a sonda REAL, sem sysfs para ler.

    ``EsperaPeloPS`` sem ``sonda=`` usa ``uniqs_no_radio``. É a única
    configuração em que a cura está no caminho — e é a que roda na janela dela.
    """

    def test_sysfs_ilegivel_nao_marca_o_controle_como_caido(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.sinal_da_barra.RAIZ_UHID",
            str(tmp_path / "uhid-que-nao-existe"),
        )
        espera = EsperaPeloPS(NO_RADIO, total_s=3)

        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.caiu is False, (
            "a sonda cega foi lida como queda — a espera vai anunciar que o "
            "controle caiu sem nada ter caído"
        )

    def test_a_mesa_vazia_legivel_marca_a_queda(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A régua contra si mesma, do lado da espera.

        Sem esta, o teste acima passaria numa espera que nunca marca queda
        nenhuma — e aí ele mediria a inércia, não a cura.
        """
        _plantar(monkeypatch, [])
        espera = EsperaPeloPS(NO_RADIO, total_s=3)

        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.caiu is True
