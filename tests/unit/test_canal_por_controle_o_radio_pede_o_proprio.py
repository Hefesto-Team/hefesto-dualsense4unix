"""CANAL-POR-CONTROLE-01 — cada controle pede o canal DELE, e ninguém tira de ninguém.

Decisão dela, 03/09/2026, com as palavras dela e sem corrigi-las:
*"4 controles os 4 tem que ter canais de entrada unico pra cada qual."*  (noqa-acento)

**O QUE ESTAVA MEDIDO**, com os dois controles na mesa: existia UM canal, o do
cabo. O do rádio não publicava fonte nenhuma, e quem recusava eram duas travas
NOSSAS — a env de opt-in e a declaração `uniq` a `uniq` no `maquina.json`.

**A LEITURA QUE A §2 DA SPRINT OBRIGA, e é o que estes testes protegem.** As
duas travas protegiam UMA razão — *"a ponte é um gesto explícito"* — e ela
continua valendo. O que caducou foi a ALAVANCA: elas negavam o CANAL para
evitar a CAPTURA, e o cabo prova que os dois são separáveis (medido em
03/09/2026: a source do cabo existe e está `SUSPENDED`, publicada e sem
capturar). Então a trava virou automática, e o critério é o do cabo — PROCURA.

AS DUAS METADES, e nenhuma vale sozinha:

1. **sem pedido, nada sobe** — é a privacidade das duas travas, intacta. Um
   `is_enabled` verdadeiro sem `alvos()` vazio seria o microfone ligando junto
   com o daemon, que é o que o cabeçalho do módulo recusa desde 25/07/2026;
2. **com pedido, sobe SÓ o dele** — é a decisão dela. Quatro controles, quatro
   canais, e ninguém precisa tirar o de ninguém.

COMO MORDE (exercido em 03/09/2026, cura arrancada e devolvida por `cp`)
------------------------------------------------------------------------
* tire o `| self._registro.abertos()` de `BtMicSubsystem.alvos` ->
  `test_quem_pediu_ganha_a_ponte_dele` e o ponta-a-ponta reprovam: o pedido
  volta a não valer nada e o rádio volta a ficar sem canal;
* tire o `_soltar_os_que_ela_desmarcou` do laço ->
  `test_desmarcar_no_aplicar_vence_o_pedido` reprova: o interruptor do card
  perde para um toque de botão de minutos antes;
* tire o `_esquecer_quem_saiu_da_mesa` -> `test_quem_sai_da_mesa_perde_o_pedido`
  reprova, e o defeito que ele deixaria passar é o *"liga sozinho"* pela porta
  dos fundos: a reconexão do controle subiria a ponte sem ninguém pedir.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
)
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm

#: Os da mesa dela, na faixa sintética que o portão de anonimato exige em
#: `tests/` (`test_anonimato_de_fixtures`).
UM = "aabbcc000001"
DOIS = "aabbcc000002"

#: O nome que `PonteMicBluetooth` publica: prefixo mais os TRÊS últimos octetos.
FONTE_DE_UM = "hefesto_dualsense_bt_000001"
FONTE_DO_CABO = "alsa_input.usb-Sony_DualSense-00.iec958-stereo"
FONTE_DA_PLACA = "alsa_input.pci-0000_00_1f.3.analog-stereo"


class _No:
    """Um `NoDualSenseBT` o bastante para `alvos` — só o que ele lê."""

    def __init__(self, uniq: str) -> None:
        self.uniq = uniq
        self.caminho = f"/dev/{uniq}"


def _config(**campos: Any) -> Any:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    return DaemonConfig(**campos)


@pytest.fixture(autouse=True)
def sem_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A env é o caminho à mão e vale por TODOS — ligada, ela apaga a medida."""
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)


# ===========================================================================
# 1. O registro de procura — o que ficou no lugar da declaração à mão
# ===========================================================================


class TestORegistro:
    def test_pedir_normaliza_o_endereco(self) -> None:
        """A chave é o `uniq` de doze hex, venha ele como vier.

        Um pedido escrito com dois-pontos e outro sem seriam DOIS donos do
        mesmo microfone, e o segundo subiria uma ponte em cima do primeiro.
        """
        registro = RegistroDePedidosDeCanal()
        assert registro.pedir("AA:BB:CC:00:00:01") is True
        assert registro.abertos() == frozenset({UM})

    def test_endereco_ilegivel_nao_vira_pedido(self) -> None:
        """Sem endereço não há de quem seja o canal — e sem dono não se sobe."""
        registro = RegistroDePedidosDeCanal()
        assert registro.pedir("") is False
        assert registro.pedir("nao-e-um-mac") is False
        assert registro.abertos() == frozenset()

    def test_o_pedido_acorda_quem_dorme(self) -> None:
        """Sem isto o canal esperaria a varredura inteira depois do toque dela.

        E os segundos entre o botão e o canal no ar apareceriam na tela como
        "não pegou" — a mentira que a eleição existe para não contar.
        """
        registro = RegistroDePedidosDeCanal()
        registro.novidade.clear()
        registro.pedir(UM)
        assert registro.novidade.is_set() is True

    def test_pedir_de_novo_nao_e_novidade(self) -> None:
        """Repetir o pedido não acorda o laço: nada mudou para reconciliar."""
        registro = RegistroDePedidosDeCanal()
        registro.pedir(UM)
        registro.novidade.clear()
        assert registro.pedir(UM) is True
        assert registro.novidade.is_set() is False

    def test_esquecer_ausentes_devolve_quem_saiu(self) -> None:
        registro = RegistroDePedidosDeCanal()
        registro.pedir(UM)
        registro.pedir(DOIS)
        assert registro.esquecer_ausentes(frozenset({UM})) == frozenset({DOIS})
        assert registro.abertos() == frozenset({UM})

    def test_o_registro_aguenta_duas_threads(self) -> None:
        """Ele é escrito pelo laço do daemon e lido pela thread do subsystem."""
        registro = RegistroDePedidosDeCanal()
        erros: list[BaseException] = []

        def _pede(qual: str) -> None:
            try:
                for _ in range(200):
                    registro.pedir(qual)
                    registro.abertos()
                    registro.soltar(qual)
            except BaseException as exc:  # pragma: no cover - só se houver corrida
                erros.append(exc)

        fios = [threading.Thread(target=_pede, args=(u,)) for u in (UM, DOIS)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(5.0)
        assert erros == []


# ===========================================================================
# 2. AS DUAS METADES — sem pedido nada sobe; com pedido sobe só o dele
# ===========================================================================


class TestAsDuasMetades:
    def test_sem_pedido_nada_sobe_e_a_privacidade_fica_de_pe(self) -> None:
        """A metade que as duas travas protegiam, e que NÃO saiu.

        `is_enabled` verdadeiro é o supervisor de pé para atender o primeiro
        toque. Ligado não é capturando: sem ponte não há `0x32`, não há libopus
        e não há microfone.
        """
        subsystem = BtMicSubsystem(registro=RegistroDePedidosDeCanal())
        config = _config()
        assert subsystem.is_enabled(config) is True
        subsystem._config = config
        assert subsystem.alvos([_No(UM), _No(DOIS)]) == []

    def test_quem_pediu_ganha_a_ponte_dele(self) -> None:
        """A CURA. Sem a união com o registro, o pedido não vale nada."""
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        subsystem._config = _config()
        assert subsystem.pedir_canal(UM) is True
        assert [no.uniq for no in subsystem.alvos([_No(UM), _No(DOIS)])] == [UM]

    def test_pedir_um_nao_liga_os_quatro(self) -> None:
        """O coração do "por controle", agora pelo caminho da procura."""
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        subsystem._config = _config()
        subsystem.pedir_canal(DOIS)
        escolhidos = [no.uniq for no in subsystem.alvos([_No(UM), _No(DOIS)])]
        assert escolhidos == [DOIS]

    def test_a_declaracao_antiga_continua_valendo(self) -> None:
        """Quem já marcou o controle no card não perde nada com a procura."""
        subsystem = BtMicSubsystem(registro=RegistroDePedidosDeCanal())
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({UM}))
        assert [no.uniq for no in subsystem.alvos([_No(UM), _No(DOIS)])] == [UM]

    def test_declarado_e_pedido_somam_sem_se_atropelar(self) -> None:
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({UM}))
        registro.pedir(DOIS)
        escolhidos = sorted(no.uniq for no in subsystem.alvos([_No(UM), _No(DOIS)]))
        assert escolhidos == [UM, DOIS]


# ===========================================================================
# 3. A VIDA DO PEDIDO — ele não caduca no relógio, e não sobrevive à mesa
# ===========================================================================


class TestAVidaDoPedido:
    def test_quem_sai_da_mesa_perde_o_pedido(self) -> None:
        """Sem isto a RECONEXÃO subiria a ponte sozinha — o "liga sozinho".

        Um pedido não caduca no relógio (*"ninguém perde nada quando outro é
        eleito"*), mas ele é da sessão daquele controle na mesa. Quem voltar
        pede de novo, com o botão, se quiser.
        """
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        registro.pedir(UM)
        registro.pedir(DOIS)
        subsystem._esquecer_quem_saiu_da_mesa([_No(DOIS)])
        assert registro.abertos() == frozenset({DOIS})

    def test_desmarcar_no_aplicar_vence_o_pedido(self) -> None:
        """O interruptor do card é o gesto mais explícito que ela tem.

        Ler só o estado ATUAL não bastaria: `alvos()` une os dois conjuntos e a
        procura manteria de pé o que ela acabou de desligar. O que decide é a
        BORDA de descida da declaração.
        """
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        declarados = {UM}
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset(declarados))
        subsystem._declarados_antes = frozenset(declarados)
        registro.pedir(UM)

        # Ela desmarca o microfone deste controle no "Aplicar".
        declarados.clear()
        subsystem._soltar_os_que_ela_desmarcou()

        assert registro.abertos() == frozenset()
        assert subsystem.alvos([_No(UM)]) == []

    def test_desmarcar_um_nao_solta_o_pedido_do_outro(self) -> None:
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        declarados = {UM, DOIS}
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset(declarados))
        subsystem._declarados_antes = frozenset(declarados)
        registro.pedir(UM)
        registro.pedir(DOIS)

        declarados.discard(UM)
        subsystem._soltar_os_que_ela_desmarcou()

        assert registro.abertos() == frozenset({DOIS})


# ===========================================================================
# 4. O GANCHO — daemon importando `integrations`, nunca o contrário
# ===========================================================================


class TestOGancho:
    @pytest.fixture(autouse=True)
    def gancho_limpo(self) -> Any:
        anterior = elm.registrar_pedidor_de_canal(None)
        yield
        elm.registrar_pedidor_de_canal(anterior)

    def test_sem_pedidor_o_pedido_e_um_false_honesto(self) -> None:
        """Fora do daemon ninguém atende, e mentir aqui viraria espera à toa."""
        assert elm.pedir_canal(UM) is False

    def test_o_pedidor_que_explode_nao_derruba_o_gesto(self) -> None:
        """O toque no botão dela não pode virar traceback no laço do daemon."""

        def _explode(_uniq: str) -> bool:
            raise RuntimeError("o registro sumiu")

        elm.registrar_pedidor_de_canal(_explode)
        assert elm.pedir_canal(UM) is False

    def test_registrar_devolve_o_anterior(self) -> None:
        """É o que deixa o `stop()` devolver o gancho em vez de zerá-lo."""

        def _primeiro(_uniq: str) -> bool:
            return True

        def _segundo(_uniq: str) -> bool:
            return False

        assert elm.registrar_pedidor_de_canal(_primeiro) is None
        assert elm.registrar_pedidor_de_canal(_segundo) is _primeiro

    def test_o_pedido_chega_ao_registro_do_subsystem(self) -> None:
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        elm.registrar_pedidor_de_canal(subsystem.pedir_canal)
        assert elm.pedir_canal(UM) is True
        assert registro.abertos() == frozenset({UM})


# ===========================================================================
# 5. PONTA A PONTA — o controle do rádio pede o canal dele e elege
# ===========================================================================


class _Pactl:
    """Dublê de `pactl` + do script do WirePlumber."""

    def __init__(self, ativo: str = FONTE_DA_PLACA) -> None:
        self.ativo = ativo
        self.escritas: list[str] = []

    def __call__(self, argv: list[str]) -> tuple[int, str]:
        if argv[:1] == ["pactl"]:
            if argv[1] == "get-default-source":
                return (0, self.ativo)
            if argv[1] == "set-default-source":
                self.escritas.append(argv[2])
                self.ativo = argv[2]
                return (0, "")
            return (0, "")
        if argv[:1] == ["bash"]:
            if "--fonte-se-sustenta" in argv:
                return (0, argv[-1])
            if "--melhor-fonte-elegivel" in argv:
                return (0, FONTE_DA_PLACA)
        return (0, "")


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    """A mesa dela: um `pactl` dublado e o script que DECLARA as duas flags."""
    dublê = _Pactl()
    script = tmp_path / "fix_wireplumber_default_source.sh"
    script.write_text(
        "#!/usr/bin/env bash\n--fonte-se-sustenta) :;;\n--melhor-fonte-elegivel) :;;\n"
    )
    monkeypatch.setattr(elm, "_rodar", dublê)
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: script)
    monkeypatch.setattr(elm, "SETTLE_PASSOS", 3)
    monkeypatch.setattr(elm, "SETTLE_PASSO_S", 0.0)
    monkeypatch.setattr(elm, "ESPERA_DO_CANAL_PASSO_S", 0.0)
    monkeypatch.setattr(elm, "casamento_usb_agora", lambda _u: None)
    return dublê


class TestPontaAPonta:
    @pytest.fixture(autouse=True)
    def gancho_limpo(self) -> Any:
        anterior = elm.registrar_pedidor_de_canal(None)
        yield
        elm.registrar_pedidor_de_canal(anterior)

    def test_o_controle_do_radio_pede_o_canal_e_elege(
        self, bancada: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O CAMINHO QUE NÃO EXISTIA. Sem a cura, isto é a recusa de sempre.

        Medido em 03/09/2026 na mesa dela: o controle do rádio não publicava
        fonte nenhuma, e apertar o botão do microfone respondia *"não há canal
        de captura atribuível a este controle"* — sem nada que ela pudesse
        fazer a respeito de dentro do produto.
        """
        publicadas: list[str] = []
        registro = RegistroDePedidosDeCanal()

        def _pedidor(uniq: str) -> bool:
            # A ponte subindo: é o que o `BtMicSubsystem` faz na varredura
            # seguinte, e o efeito visível é a source no PipeWire.
            if registro.pedir(uniq):
                publicadas.append(FONTE_DE_UM)
                return True
            return False

        elm.registrar_pedidor_de_canal(_pedidor)
        monkeypatch.setattr(elm, "fontes_de_captura_agora", lambda: list(publicadas))

        eleitor = elm.EleitorDeMicrofone()
        resultado = eleitor.eleger_o_controle(UM, [UM])

        assert registro.abertos() == frozenset({UM})
        assert resultado.ok is True
        assert resultado.alvo == FONTE_DE_UM
        assert eleitor.eleito == UM
        assert bancada.escritas == [FONTE_DE_UM]

    def test_o_cabo_nao_pede_nada(
        self, bancada: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quem já tem canal não pede — o toque no cabo custa o mesmo de sempre.

        Pedir aqui gastaria o orçamento de espera inteiro a cada toque, e ainda
        subiria uma ponte de rádio para um controle que está no cabo.
        """
        pedidos: list[str] = []
        elm.registrar_pedidor_de_canal(lambda u: pedidos.append(u) or True)
        monkeypatch.setattr(elm, "fontes_de_captura_agora", lambda: [FONTE_DO_CABO])

        resultado = elm.EleitorDeMicrofone().eleger_o_controle(UM, [UM])

        assert pedidos == []
        assert resultado.ok is True
        assert resultado.alvo == FONTE_DO_CABO

    def test_quando_ninguem_atende_a_recusa_e_a_de_sempre(
        self, bancada: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NENHUMA FRASE NOVA — ela recusou a premissa do recado, não o texto.

        Sem pedidor registrado (o subsystem no chão, ou um processo que não é o
        daemon), a resposta tem de ser palavra por palavra a que já existia.
        """
        monkeypatch.setattr(elm, "fontes_de_captura_agora", list)

        resultado = elm.EleitorDeMicrofone().eleger_o_controle(UM, [UM])

        assert resultado.ok is False
        assert resultado.motivo == (
            "o PipeWire não publica canal de captura nenhum para o "
            "controle — no rádio isso precisa da ponte de microfone"
        )

    def test_o_canal_que_nao_sobe_no_orcamento_nao_inventa_frase(
        self, bancada: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pedido aceito e canal que não aparece: a recusa continua a de sempre.

        É o caso da libopus ausente ou do hidraw recusado — a ponte foi pedida
        e não subiu. Nada de tela nova; o texto é o que já havia.
        """
        elm.registrar_pedidor_de_canal(lambda _u: True)
        monkeypatch.setattr(elm, "fontes_de_captura_agora", list)
        monkeypatch.setattr(elm, "ESPERA_DO_CANAL_PASSOS", 2)

        resultado = elm.EleitorDeMicrofone().eleger_o_controle(UM, [UM])

        assert resultado.ok is False
        assert resultado.motivo == (
            "o PipeWire não publica canal de captura nenhum para o "
            "controle — no rádio isso precisa da ponte de microfone"
        )

    def test_o_canal_de_um_nao_e_o_canal_do_outro(
        self, bancada: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quatro canais quer dizer que a source de UM não serve para DOIS.

        Com a ponte de UM no ar e DOIS pedindo, o canal publicado não pode ser
        atribuído a DOIS — senão a mesa inteira voltaria a dividir um microfone
        só, que é a premissa que ela recusou.
        """
        elm.registrar_pedidor_de_canal(lambda _u: True)
        monkeypatch.setattr(elm, "fontes_de_captura_agora", lambda: [FONTE_DE_UM])
        monkeypatch.setattr(elm, "ESPERA_DO_CANAL_PASSOS", 2)

        resultado = elm.EleitorDeMicrofone().eleger_o_controle(DOIS, [UM, DOIS])

        assert resultado.ok is False
        assert resultado.motivo == (
            "não há canal de captura atribuível a este controle — no "
            "rádio ele só aparece com a ponte de microfone de pé"
        )


# ===========================================================================
# 6. O LAÇO ACORDA — a espera não pode aparecer na tela como "não pegou"
# ===========================================================================


class _Gerenciador:
    def __init__(self) -> None:
        self.parado = False

    def dormir(self, _segundos: float) -> bool:
        return self.parado


class TestOLacoAcorda:
    def test_o_pedido_encurta_a_espera(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Com a novidade posta, `_dormir` volta na hora em vez de dormir 5 s."""
        import hefesto_dualsense4unix.daemon.subsystems.bt_mic as bt

        monkeypatch.setattr(bt, "RECONCILIA_S", 30.0)
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        registro.pedir(UM)

        inicio = threading.Event()
        inicio.set()
        assert subsystem._dormir(_Gerenciador()) is False
        assert registro.novidade.is_set() is False

    def test_a_parada_do_gerenciador_ainda_para_o_laco(self) -> None:
        """A outra fonte de parada continua valendo — `dormir(0.0)` a relê."""
        registro = RegistroDePedidosDeCanal()
        subsystem = BtMicSubsystem(registro=registro)
        registro.novidade.set()
        gerenciador = _Gerenciador()
        gerenciador.parado = True
        assert subsystem._dormir(gerenciador) is True
