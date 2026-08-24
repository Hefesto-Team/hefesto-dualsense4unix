"""O exame da mesa sai da thread do GTK, e o resultado volta por ela.

23/08/2026. Quarta e mais difícil das curas que o censo de mutação achou
arrancáveis sem nada ficar vermelho na aba Configurações.

O QUE A CURA É
--------------

``PainelDoExame.reexaminar`` (`app/actions/config/secao_exame.py`) faz duas
travessias de thread, e as duas são cura:

1. **a ida** — ``_get_executor().submit(_trabalho)``. O exame chama ``busctl``,
   que é subprocesso; rodá-lo na thread do GTK congela a janela inteira até o
   teto do comando. A cicatriz tem nome e endereço:
   BUG-GUI-SYSTEMCTL-SYNC-NA-THREAD-GTK-01 (`daemon_actions.py:1817-1827`), em
   que um ``subprocess.run`` síncrono travou a janela dela e, em D-state, nem o
   ``kill`` chegava;
2. **a volta** — ``GLib.idle_add(self.aplicar, ...)``. Sem ela o worker escreve
   ``Gtk.Label`` de fora da thread do GTK, que é comportamento indefinido —
   funciona até o dia em que não funciona, e aí não deixa rastro.

POR QUE ESTE TESTE PRECISOU DE OUTRO DUBLÊ
------------------------------------------

`test_config_selo_de_saude.py` monta um ``_ExecutorSincrono`` que RODA o
trabalho dentro do ``submit``. Ele é o dublê certo para o que aquele arquivo
mede — "a montagem não examina" —, e é o dublê ERRADO para esta cura: um
executor síncrono não distingue *"rodou na thread certa"* de *"rodou aqui
mesmo"*. Trocar ``_get_executor().submit(_trabalho)`` por ``_trabalho()`` deixa
tudo verde lá, e é exatamente por isso que esta cura aparecia como arrancável.

O dublê daqui é ADIADO: ele anota o que foi submetido e **não roda nada**. Com
isso a asserção deixa de ser "o exame rodou" e passa a ser **"o executor foi
chamado, e o exame NÃO rodou antes disso"** — que é a única forma de a régua
enxergar a travessia de thread sem depender do escalonador, que é a armadilha
número um desta casa.

A régua, declarada: ``ipc_bridge._get_executor``, ``exame_da_mesa.exame``,
``exame_da_mesa.veredito`` e ``GLib.idle_add`` são todos substituídos. Nada aqui
chama ``busctl``, lê ``/sys`` ou entra no laço do GTK.

AS MORDIDAS, ARRANCADAS E CONFERIDAS EM 23/08/2026
--------------------------------------------------

===============================================================  ===========
mutação                                                          reprova
===============================================================  ===========
``_trabalho()`` direto, no lugar do ``submit`` ao executor        2 de 5
``self.aplicar(...)`` direto, no lugar do ``GLib.idle_add``       2 de 5
===============================================================  ===========
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. `importorskip("gi")`
# aceita o stub que outro arquivo planta em `sys.modules`; esta guarda não.
exigir_gi_real("o exame fora da thread do GTK")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from hefesto_dualsense4unix.app.actions.config.secao_exame import (
    PainelDoExame,
)
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_CERTO,
    Item,
)

#: O que o exame de mentira responde. Uma linha basta: o que se mede aqui é
#: QUEM roda o exame, não o que ele conclui.
ITENS = [
    Item(
        chave="daemon",
        rotulo="O Hefesto está de pé",
        estado=ESTADO_CERTO,
        porque=None,
        cura=None,
    )
]


class _ExecutorAdiado:
    """Anota o que foi submetido e **não roda nada**.

    É a diferença inteira entre este arquivo e o `test_config_selo_de_saude.py`:
    lá o dublê roda o trabalho dentro do ``submit``, e por isso não consegue
    separar "foi para o worker" de "rodou aqui". Aqui o trabalho fica na mão do
    teste, que o roda quando quiser — e só então.
    """

    def __init__(self) -> None:
        self.submetidos: list[Any] = []

    def submit(self, funcao: Any, *args: Any, **kwargs: Any) -> None:
        self.submetidos.append(lambda: funcao(*args, **kwargs))


class _Bancada:
    """O painel, o executor adiado e as duas espiãs, montados juntos."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge
        from hefesto_dualsense4unix.integrations import exame_da_mesa

        self.painel = PainelDoExame()
        self.executor = _ExecutorAdiado()
        self.exames: list[str] = []
        self.postados: list[tuple[Any, tuple[Any, ...]]] = []
        self.aplicados: list[tuple[Any, ...]] = []

        monkeypatch.setattr(ipc_bridge, "_get_executor", lambda: self.executor)
        monkeypatch.setattr(
            exame_da_mesa,
            "exame",
            lambda **_k: (self.exames.append("exame"), ITENS)[1],
        )
        monkeypatch.setattr(exame_da_mesa, "veredito", lambda _itens: ESTADO_CERTO)
        # O `idle_add` NÃO executa: quem executa é a thread do GTK, e fingir o
        # contrário devolveria o mesmo cego do executor síncrono.
        monkeypatch.setattr(
            GLib,
            "idle_add",
            lambda funcao, *args, **_k: self.postados.append((funcao, args)),
        )
        # A espiã do outro lado: se `aplicar` for chamado sem passar pelo
        # `idle_add`, é aqui que aparece.
        original = self.painel.aplicar

        def _aplicar_espiado(*args: Any) -> bool:
            self.aplicados.append(args)
            return original(*args)

        self.painel.aplicar = _aplicar_espiado  # type: ignore[method-assign]

    def rodar_o_worker(self) -> None:
        """Roda o que foi para o executor — o que a thread de verdade faria."""
        for trabalho in list(self.executor.submetidos):
            trabalho()


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> _Bancada:
    return _Bancada(monkeypatch)


class TestOExameVaiParaOWorker:
    def test_reexaminar_submete_e_nao_examina_na_hora(self, bancada: _Bancada) -> None:
        """A asserção que morde: o executor FOI CHAMADO, e o exame não rodou.

        As duas metades são obrigatórias. Só a primeira passaria num produto que
        submetesse E também rodasse; só a segunda passaria num produto que não
        fizesse nada. É a travessia de thread que está sendo medida, e ela só
        existe entre as duas.
        """
        bancada.painel.reexaminar()

        assert len(bancada.executor.submetidos) == 1, (
            "o exame não foi entregue ao worker — se ele rodou, rodou na thread "
            "da janela, e a janela congela até o `busctl` responder"
        )
        assert bancada.exames == [], (
            "o exame rodou dentro de `reexaminar`, isto é, na thread do GTK"
        )

    def test_o_que_foi_submetido_e_o_exame_de_verdade(
        self, bancada: _Bancada
    ) -> None:
        """A régua contra si mesma: submeter qualquer coisa não basta.

        Sem esta, o teste acima passaria num produto que submetesse uma função
        vazia ao executor e nunca examinasse nada — verde perfeito, medindo o
        nada.
        """
        bancada.painel.reexaminar()
        bancada.rodar_o_worker()

        assert bancada.exames == ["exame"]

    def test_sem_executor_a_janela_nao_cai_e_o_painel_destrava(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem worker não há exame — mas também não há painel travado.

        ``_examinando`` é o que barra a reentrância; se ele ficasse ligado depois
        de uma falha do executor, o botão "Examinar de novo" nunca mais faria
        nada nesta sessão.

        A bancada entra aqui só pelas espiãs: sem elas, uma mutação que trocasse
        o ``submit`` por chamada direta faria ESTE teste rodar o exame de
        verdade — ``busctl`` e ``/sys`` na máquina de quem roda a suíte. Um
        teste que toca a bancada ao ser MINADO não é régua, é armadilha.
        """
        from hefesto_dualsense4unix.app import ipc_bridge

        def _sem_executor() -> Any:
            raise RuntimeError("interpretador encerrando")

        monkeypatch.setattr(ipc_bridge, "_get_executor", _sem_executor)

        bancada.painel.reexaminar()

        assert bancada.painel._examinando is False


class TestOResultadoVoltaPelaThreadDoGtk:
    def test_o_worker_posta_o_resultado_no_idle_add(self, bancada: _Bancada) -> None:
        """O worker NÃO escreve widget: ele pede à thread do GTK que escreva."""
        bancada.painel.reexaminar()
        bancada.rodar_o_worker()

        assert bancada.postados, (
            "o resultado do exame não passou pelo `GLib.idle_add` — o worker "
            "escreveu widget de fora da thread do GTK"
        )
        funcao, args = bancada.postados[0]
        assert funcao == bancada.painel.aplicar
        assert args[0] == ITENS
        assert args[1] == ESTADO_CERTO

    def test_o_worker_nao_chama_aplicar_por_conta_propria(
        self, bancada: _Bancada
    ) -> None:
        """A outra metade, e ela é a que a mutação derruba.

        Com o `idle_add` trocado por chamada direta, o teste acima já reprova;
        este diz POR QUE, nomeando quem escreveu o widget na thread errada.
        """
        bancada.painel.reexaminar()
        bancada.rodar_o_worker()

        assert bancada.aplicados == [], (
            "`aplicar` rodou dentro do worker — os `Gtk.Label` da seção foram "
            "escritos de fora da thread do GTK"
        )
