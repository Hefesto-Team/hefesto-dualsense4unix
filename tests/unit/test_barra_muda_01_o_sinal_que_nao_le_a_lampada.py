"""BARRA-MUDA-01 — o sinal da barra, e as quatro mentiras que ele não pode contar."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import sinal_da_barra as sb

_UNIQ_RADIO = "aa:bb:cc:11:22:01"
_UNIQ_CABO = "aa:bb:cc:11:22:02"
_ADAPTADOR = "aa:bb:cc:99:88:77"


def _no_radio(instancia: str = "0029", no: str = "/dev/hidraw7") -> sb.Instancia:
    return sb.Instancia(
        instancia=instancia,
        uniq=_UNIQ_RADIO,
        adaptador=_ADAPTADOR,
        hw_version="0x00001111",
        input_n=262,
        hidraw=no,
        transporte="bt",
    )


def _no_cabo(instancia: str = "0025") -> sb.Instancia:
    return sb.Instancia(
        instancia=instancia,
        uniq=_UNIQ_CABO,
        adaptador="",
        hw_version="0x00000811",
        input_n=246,
        hidraw="/dev/hidraw5",
        transporte="usb",
    )


def _nascimento(
    instancia: str,
    *,
    sujo: bool,
    quando: float = 1000.0,
    no: str = "/dev/hidraw7",
) -> sb.Nascimento:
    return sb.Nascimento(
        instancia=instancia,
        quando=quando,
        no=no,
        transporte="bt",
        escritor=(600105,) if sujo else (),
        sujo=sujo,
    )


class TestOModuloNaoLeALampada:
    """A honestidade, em forma de teste. Esta classe é o coração do arquivo."""

    PROIBIDAS = ("acesa", "acessa", "apagada", "acendeu", "apagou", "está acesa")

    def test_nenhuma_frase_de_veredito_afirma_estado_da_lampada(self) -> None:
        """Nenhum `porque` pode dizer que a lâmpada está de um jeito ou de outro."""
        frases = []
        for alvo, nascimentos in (
            (_no_radio(), {"0029": _nascimento("0029", sujo=True)}),
            (_no_radio(), {"0029": _nascimento("0029", sujo=False)}),
            (_no_radio(), {}),
            (_no_radio(), None),
            (_no_cabo(), None),
        ):
            frases.append(sb._veredito(alvo, nascimentos).porque)
        frases.append(sb.limpo_para_conectar(sonda=lambda _: {"/dev/hidraw7": [1]})[1])
        frases.append(sb.limpo_para_conectar(sonda=lambda _: {})[1])
        frases.append(sb.relatorio([sb.veredito_do_nascimento(
            instancias=[_no_radio()],
            nascimentos={"0029": _nascimento("0029", sujo=True)},
        )[0]]))

        for frase in frases:
            baixa = frase.lower()
            for proibida in self.PROIBIDAS:
                assert proibida not in baixa, (
                    f"o módulo passou a AFIRMAR estado de lâmpada: {frase!r}. "
                    "Não existe leitura de lâmpada nesta casa — ver a docstring "
                    "de sinal_da_barra.py, três medições."
                )

    def test_o_veredito_fala_de_nascimento_e_nao_de_luz(self) -> None:
        """O suspeito é descrito pelo que foi MEDIDO: a disputa no nascimento."""
        leitura = sb._veredito(_no_radio(), {"0029": _nascimento("0029", sujo=True)})
        assert leitura.confianca == sb.CONFIANCA_SUSPEITA
        assert "nasceu" in leitura.porque


class TestNaoSeiNuncaViraLimpa:
    """O terceiro estado, que é o que separa este detector do que veio antes."""

    def test_sem_diario_o_veredito_e_nao_sei(self) -> None:
        leitura = sb._veredito(_no_radio(), None)
        assert leitura.confianca == sb.CONFIANCA_NAO_SEI
        assert not leitura.pede_reconexao

    def test_instancia_ausente_do_diario_e_nao_sei(self) -> None:
        """Conexão mais velha que o diário: desconhecida, nunca inocente."""
        leitura = sb._veredito(_no_radio("0029"), {"0033": _nascimento("0033", sujo=False)})
        assert leitura.confianca == sb.CONFIANCA_NAO_SEI

    def test_sonda_que_falha_nao_libera_a_reconexao(self) -> None:
        """Prognóstico sem sonda é `nao_sei` — jamais 'pode reconectar'."""
        def explode(_: object) -> dict[str, list[int]]:
            raise OSError("sem /proc")

        confianca, _porque, pids = sb.limpo_para_conectar(sonda=explode)
        assert confianca == sb.CONFIANCA_NAO_SEI
        assert pids == ()

    def test_diario_vazio_e_diario_ilegivel_nao_sao_a_mesma_coisa(self) -> None:
        """`{}` diz 'olhei e não achou'; `None` diz 'não olhei'. Os dois viram"""
        sem_diario = sb._veredito(_no_radio(), None).porque
        so_ausente = sb._veredito(_no_radio(), {}).porque
        assert sem_diario != so_ausente


class TestOCaboNaoESuspeito:
    def test_usb_nunca_pede_reconexao(self) -> None:
        """MEDIDO 03/08 e 11/08: pelo cabo a barra sempre obedeceu."""
        for nascimentos in (None, {}, {"0025": _nascimento("0025", sujo=True)}):
            leitura = sb._veredito(_no_cabo(), nascimentos)
            assert leitura.confianca == sb.CONFIANCA_LIMPA
            assert not leitura.pede_reconexao


class TestOHidrawEReciclado:
    """A armadilha que só aparece com duas instâncias no mesmo nó, em horas"""

    def test_o_escritor_da_instancia_morta_nao_suja_a_viva(self) -> None:
        nascimentos = {
            "0028": sb.Nascimento("0028", 64_800.0, "/dev/hidraw6", "bt", (600105,), True),
            "0033": sb.Nascimento("0033", 71_507.0, "/dev/hidraw6", "bt", (), False),
        }
        viva = _no_radio("0033", "/dev/hidraw6")
        assert sb._veredito(viva, nascimentos).confianca == sb.CONFIANCA_LIMPA


class TestONascimentoVemDoUdev:
    """A régua do udev. O defeito que estes testes pegam já aconteceu de"""

    AGORA = 5000.0

    @staticmethod
    def _responde(usec_por_no: dict[str, str | None]):  # type: ignore[no-untyped-def]
        def _perguntar(syspath: str, nome: str) -> str | None:
            assert nome == "USEC_INITIALIZED", (
                f"o nascimento voltou a perguntar {nome!r}: só o USEC_INITIALIZED é o "
                "instante em que o udev recebeu o nó"
            )
            return usec_por_no.get(syspath.rsplit("/", 1)[-1])

        return _perguntar

    def test_o_instante_do_udev_vira_segundos_desde_o_boot(self) -> None:
        # A decisão D-0810-O-NASCIMENTO-DA-CONEXAO-VEM-DO-UDEV.
        nascimentos = sb.nascimentos_do_udev(
            [_no_radio("0029", "/dev/hidraw7")],
            perguntar=self._responde({"hidraw7": "4000500000"}),
            relogio=lambda: self.AGORA,
        )
        assert nascimentos is not None
        assert nascimentos["0029"].quando == pytest.approx(4000.5)
        assert nascimentos["0029"].no == "/dev/hidraw7"

    def test_o_udev_mudo_e_nao_sei(self) -> None:
        # A decisão D-0810-O-NASCIMENTO-DA-CONEXAO-VEM-DO-UDEV.
        """Perguntou e ninguém respondeu: é `None`, nunca `{}` (que diria «nasceu limpo»)."""
        assert sb.nascimentos_do_udev(
            [_no_radio("0029", "/dev/hidraw7")],
            perguntar=self._responde({}),
            relogio=lambda: self.AGORA,
        ) is None

    @pytest.mark.parametrize("resposta", ["abc", "", "-5", "12.5", "²", "١٢٣"])
    def test_resposta_que_nao_e_numero_e_nao_sei(self, resposta: str) -> None:
        """Só dígito ASCII é instante: o resto é «não respondeu», sem levantar.

        MORDIDA: tirar o ``isascii()`` da conferência faz o ``"²"`` (que é
        ``isdigit``) chegar ao ``int`` e levantar ``ValueError`` aqui.
        """
        assert sb.nascimentos_do_udev(
            [_no_radio("0029", "/dev/hidraw7")],
            perguntar=self._responde({"hidraw7": resposta}),
            relogio=lambda: self.AGORA,
        ) is None

    def test_sem_instancia_nao_pergunta_nem_le_o_diario(self, monkeypatch) -> None:
        def _bomba(*_a: object, **_k: object) -> None:
            raise AssertionError("sem instância viva não há o que ler no diário")

        monkeypatch.setattr(sb, "_linhas_do_diario", _bomba)
        assert sb.nascimentos_do_udev(
            [], perguntar=self._responde({}), relogio=lambda: self.AGORA
        ) == {}

    def test_mais_velha_que_a_janela_do_diario_fica_de_fora(self, monkeypatch) -> None:
        # A decisão D-0810-O-NASCIMENTO-DA-CONEXAO-VEM-DO-UDEV.
        """O diário do daemon só é lido na janela; antes dela o escritor não se sabe."""
        monkeypatch.setattr(sb, "_linhas_do_diario", lambda *_a: [])
        velha_s = self.AGORA - sb.JANELA_DO_DIARIO_S - 10
        nascimentos = sb.nascimentos_do_udev(
            [_no_radio("0029", "/dev/hidraw7"), _no_radio("002a", "/dev/hidraw8")],
            perguntar=self._responde(
                {"hidraw7": str(int(velha_s * 1e6)), "hidraw8": str(int((self.AGORA - 60) * 1e6))}
            ),
            relogio=lambda: self.AGORA,
        )
        assert nascimentos is not None
        assert set(nascimentos) == {"002a"}

    def test_o_escritor_do_log_do_daemon_suja_o_nascimento(self, monkeypatch) -> None:
        linha = (
            "2026-08-22T18:06:02.847377 [info     ] lightbar_escritor_cru_detectado "
            "nos=['/dev/hidraw7'] pids=[600105]"
        )
        visto: list[list[str]] = []

        def _diario(argv, _orcamento):  # type: ignore[no-untyped-def]
            visto.append(list(argv))
            return [(4002.0, linha)]

        monkeypatch.setattr(sb, "_linhas_do_diario", _diario)
        nascimentos = sb.nascimentos_do_udev(
            [_no_radio("0029", "/dev/hidraw7")],
            perguntar=self._responde({"hidraw7": "4000500000"}),
            relogio=lambda: self.AGORA,
        )
        assert nascimentos is not None
        assert nascimentos["0029"].sujo is True
        assert nascimentos["0029"].escritor == (600105,)
        assert "--user" in visto[0] and "-b" in visto[0], (
            "o log do daemon é lido do boot de agora: o monotônico só vale dentro dele"
        )

    def test_diario_ilegivel_nao_diz_limpo(self, monkeypatch) -> None:
        monkeypatch.setattr(sb, "_linhas_do_diario", lambda *_a: None)
        nascimentos = sb.nascimentos_do_udev(
            [_no_radio("0029", "/dev/hidraw7")],
            perguntar=self._responde({"hidraw7": "4000500000"}),
            relogio=lambda: self.AGORA,
        )
        assert nascimentos is not None
        assert nascimentos["0029"].escritor_conhecido is False

    def test_o_diario_em_json_traz_o_monotonico_em_segundos(self, monkeypatch) -> None:
        saida = (
            '{"MESSAGE": "uma", "__MONOTONIC_TIMESTAMP": "64743103000"}\n'
            "lixo que não é json\n"
            '{"MESSAGE": ["bytes"], "__MONOTONIC_TIMESTAMP": "1"}\n'
            '{"MESSAGE": "duas", "__MONOTONIC_TIMESTAMP": "64762847000"}\n'
        )

        class _Proc:
            returncode = 0
            stdout = saida

        monkeypatch.setattr(sb.subprocess, "run", lambda *_a, **_k: _Proc())
        assert sb._linhas_do_diario(["journalctl"], 1.0) == [
            (64743.103, "uma"),
            (64762.847, "duas"),
        ]


class TestAMascara:
    def test_zera_os_octetos_quatro_e_cinco(self) -> None:
        assert sb.mascarar("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:00:00:ff"

    def test_o_relatorio_nao_carrega_endereco_inteiro(self) -> None:
        """O retrato das abas versiona PNG do que aparece na tela."""
        texto = sb.relatorio(
            sb.veredito_do_nascimento(
                instancias=[_no_radio()],
                nascimentos={"0029": _nascimento("0029", sujo=True)},
            )
        )
        assert _UNIQ_RADIO not in texto
        assert sb.mascarar(_UNIQ_RADIO) in texto


class TestOPrognostico:
    """A função que guarda o botão. Sem ela, a cura vira gesto desperdiçado."""

    def test_mesa_suja_recusa_a_hora(self) -> None:
        confianca, _porque, pids = sb.limpo_para_conectar(
            sonda=lambda _: {"/dev/hidraw7": [600105]}
        )
        assert confianca == sb.CONFIANCA_SUSPEITA
        assert pids == (600105,)

    def test_mesa_limpa_libera_a_hora(self) -> None:
        confianca, _porque, pids = sb.limpo_para_conectar(sonda=lambda _: {})
        assert confianca == sb.CONFIANCA_LIMPA
        assert pids == ()

    def test_o_prognostico_nao_e_o_diagnostico(self) -> None:
        """A instância suja de 18:06 continua suja depois de a Steam morrer."""
        assert sb.limpo_para_conectar(sonda=lambda _: {})[0] == sb.CONFIANCA_LIMPA
        diagnostico = sb._veredito(_no_radio(), {"0029": _nascimento("0029", sujo=True)})
        assert diagnostico.confianca == sb.CONFIANCA_SUSPEITA


class TestAEnumeracaoNaoTocaOAparelho:
    def test_raiz_inexistente_devolve_lista_vazia_sem_estourar(self, tmp_path) -> None:
        assert sb.instancias_dualsense(str(tmp_path / "nao-existe")) == []

    def test_le_a_instancia_de_um_sysfs_de_mentira(self, tmp_path) -> None:
        base = tmp_path / "0005:054C:0CE6.0033"
        (base / "input" / "input323").mkdir(parents=True)
        (base / "hidraw" / "hidraw6").mkdir(parents=True)
        (base / "uevent").write_text(
            "DRIVER=playstation\n"
            "HID_ID=0005:0000054C:00000CE6\n"
            f"HID_PHYS={_ADAPTADOR}\n"
            f"HID_UNIQ={_UNIQ_RADIO}\n",
            encoding="utf-8",
        )
        (base / "hardware_version").write_text("0x00000811\n", encoding="utf-8")

        (achada,) = sb.instancias_dualsense(str(tmp_path))
        assert achada.instancia == "0033"
        assert achada.uniq == _UNIQ_RADIO
        assert achada.transporte == "bt"
        assert achada.input_n == 323
        assert achada.hidraw == "/dev/hidraw6"
        assert achada.hw_version == "0x00000811"

    def test_o_bus_0003_sob_o_uhid_e_o_pad_e_fica_de_fora(self, tmp_path) -> None:
        """USB de verdade nunca nasce por uhid: o bus 0003 nesta raiz é o pad.

        Até 07/10/2026 esta régua dizia o contrário (o 0003 virava «cabo»), sobre
        um estado que o sysfs não produz. Quem decide agora é o
        ``pad_usb.e_pad_nosso``, com a regra D1 que o broker já aplicava.
        """
        base = tmp_path / "0003:054C:0CE6.0025"
        base.mkdir(parents=True)
        (base / "uevent").write_text(
            f"HID_ID=0003:0000054C:00000CE6\nHID_UNIQ={_UNIQ_CABO}\n", encoding="utf-8"
        )
        assert sb.instancias_dualsense(str(tmp_path)) == []

    def test_o_vpad_do_projeto_fica_de_fora(self, tmp_path) -> None:
        """O 0DF2 é o nosso gamepad virtual: barra desenhada, não de plástico."""
        base = tmp_path / "0003:054C:0DF2.002F"
        base.mkdir(parents=True)
        (base / "uevent").write_text("HID_ID=0003:0000054C:00000DF2\n", encoding="utf-8")
        assert sb.instancias_dualsense(str(tmp_path)) == []


class TestOCasamentoPorJanela:
    """A janela de 5 s, medida. Um escritor detectado muito depois do"""

    @pytest.mark.parametrize(
        ("atraso_s", "espera_sujo"),
        [(0.64, True), (2.25, True), (4.9, True), (5.6, False), (600.0, False)],
    )
    def test_so_o_que_cai_na_janela_suja_o_nascimento(
        self, atraso_s: float, espera_sujo: bool
    ) -> None:
        """Os quatro atrasos MEDIDOS em 22/08 caem dentro; a Steam que abre dez"""
        nascimentos = {"0029": _nascimento("0029", sujo=False, quando=1000.0)}
        casados = sb.casar_escritores(
            nascimentos,
            [(1000.0 + atraso_s, frozenset({"/dev/hidraw7"}), (600105,))],
        )
        assert casados["0029"].sujo is espera_sujo

    def test_o_no_errado_nao_suja_ainda_que_a_hora_bata(self) -> None:
        """Os irmãos que sobem juntos caem na janela um do outro — é o NÓ que os"""
        nascimentos = {"0033": _nascimento("0033", sujo=False, quando=1000.0, no="/dev/hidraw6")}
        casados = sb.casar_escritores(
            nascimentos,
            [(1002.7, frozenset({"/dev/hidraw8"}), (600105,))],
        )
        assert casados["0033"].sujo is False

    def test_extrai_nos_e_pids_da_linha_real_do_daemon(self) -> None:
        linha = (
            "2026-08-22T18:06:02.847377 [info     ] lightbar_escritor_cru_detectado "
            "nos=['/dev/hidraw7'] pids=[600105]"
        )
        ((quando, nos, pids),) = sb.deteccoes_de_escritor([(1000.0, linha)])
        assert quando == 1000.0
        assert nos == frozenset({"/dev/hidraw7"})
        assert pids == (600105,)

    def test_a_deteccao_de_escritor_casa_a_bancada_de_22_08(self) -> None:
        """O caso inteiro de 22/08/2026, com os instantes reais do kernel e do"""
        nascimentos = {
            "0028": sb.Nascimento("0028", 64_740.852, "/dev/hidraw6", "bt"),
            "0029": sb.Nascimento("0029", 64_762.210, "/dev/hidraw7", "bt"),
            "002a": sb.Nascimento("002a", 64_774.901, "/dev/hidraw8", "bt"),
            "002b": sb.Nascimento("002b", 64_793.102, "/dev/hidraw9", "bt"),
            "0033": sb.Nascimento("0033", 71_507.534, "/dev/hidraw6", "bt"),
            "0034": sb.Nascimento("0034", 71_510.240, "/dev/hidraw8", "bt"),
        }
        deteccoes = [
            (64_743.103, frozenset({"/dev/hidraw6"}), (600105,)),
            (64_762.847, frozenset({"/dev/hidraw7"}), (600105,)),
            (64_776.430, frozenset({"/dev/hidraw8"}), (600105,)),
            (64_794.572, frozenset({"/dev/hidraw9"}), (600105,)),
        ]
        casados = sb.casar_escritores(nascimentos, deteccoes)
        sujos = {chave for chave, nasc in casados.items() if nasc.sujo}
        assert sujos == {"0028", "0029", "002a", "002b"}, (
            "as duas instâncias que ela reconectou às 19:51 têm de sair LIMPAS — "
            "foram elas que acenderam e obedeceram ao ciano."
        )
