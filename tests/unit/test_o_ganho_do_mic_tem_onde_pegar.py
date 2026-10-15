"""O-GANHO-DO-MIC-TEM-DONO-01/B — o ganho de entrada: o escritor, o leitor e o perfil.

O deslizante da aba Controles saiu com o desenho do todo (15/10/2026), e com ele o gesto
`ganho-mic`. O ganho segue com dono: o perfil o aplica pelo `integrations.ganho_do_microfone`.
"""

from __future__ import annotations

import pathlib

from hefesto_dualsense4unix.integrations import ganho_do_microfone as gm
from tests.unit import pactl_json_de_mentira as pj

PUBLICADO = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")
BANCADA = pathlib.Path("mockup/02-controles.html")


def test_o_desenho_do_todo_nao_tem_a_linha_do_ganho() -> None:
    """O desenho de 15/10/2026 deixa o microfone só com o Volume, no desenho e no publicado.

    MORDIDA: ponha o `<input data-gesto="ganho-mic">` de volta na página e isto reprova.
    """
    for pagina in (BANCADA, PUBLICADO):
        corpo = pagina.read_text(encoding="utf-8")
        assert 'data-gesto="ganho-mic"' not in corpo and 'class="vol ganho"' not in corpo, (
            f"a linha do Ganho voltou a {pagina}")


class TestOEscritorPerguntaAoAparelho:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_escritor_relê_o_aparelho_e_nao_devolve_o_pedido(self) -> None:
        """**A regra da casa: quando um valor tem dono, pergunte ao dono.**"""
        do_sistema = pathlib.Path(
            "src/hefesto_dualsense4unix/integrations/ganho_do_microfone.py"
        ).read_text(encoding="utf-8")
        i = do_sistema.index("def definir(")
        corpo_real = do_sistema[i:]
        assert corpo_real.count("scontents") >= 2, (
            "o escritor não relê o aparelho depois de escrever")
        assert "depois[1], depois[2]" in corpo_real, (
            "o retorno não é a releitura")


class TestOElementoNaoSeDigita:
    def test_o_nome_perde_as_aspas_e_guarda_o_indice(self) -> None:
        """`'Headset',0` -> `Headset,0`."""
        assert gm._nome_do_scontrol("'Headset',0") == "Headset,0"
        assert gm._nome_do_scontrol("'Mic Boost',1") == "Mic Boost,1"
        assert gm._nome_do_scontrol("Capture,0") == "Capture,0"

    def test_o_indice_nao_se_perde(self) -> None:
        """`Headset` sem o `,0` escreve no elemento 0 de uma placa cujo ganho"""
        assert gm._nome_do_scontrol("'Headset',2").endswith(",2")

    def test_o_parser_devolve_elemento_por_cento_e_db(self) -> None:
        texto = (
            "Simple mixer control 'Headset',0\n"
            "  Capabilities: cvolume cswitch\n"
            "  Capture channels: Mono\n"
            "  Mono: Capture 101 [100%] [48.00dB] [on]\n")
        assert gm.elemento_e_ganho_do_scontents(texto) == ("Headset,0", 100, 48.0)

    def test_os_dois_parsers_tem_corpo_unico(self) -> None:
        """Dois parsers da mesma saída é como o leitor e o escritor do mesmo"""
        texto = (
            "Simple mixer control 'Mic',1\n"
            "  Capabilities: cvolume\n"
            "  Mono: Capture 40 [37%] [12.50dB] [on]\n")
        inteiro = gm.elemento_e_ganho_do_scontents(texto)
        assert inteiro is not None
        assert gm.ganho_do_scontents(texto) == (inteiro[1], inteiro[2])

    def test_sem_elemento_de_ganho_nao_se_chuta_zero(self) -> None:
        """Chutar zero pintaria «ganho no mínimo» sobre uma placa sem ganho."""
        assert gm.elemento_e_ganho_do_scontents(
            "Simple mixer control 'PCM',0\n  Capabilities: pvolume\n") is None
        assert gm.ganho_do_scontents("") is None


class TestAPlacaSaiDoServidorDeSom:
    def test_o_no_casa_com_a_placa_alsa(self) -> None:
        lista = pj.texto(
            pj.no(7, "alsa_input.usb-Sony-00.mono-fallback", props={"alsa.card": "3"}),
            pj.no(9, "hefesto_mic_a0fa9c"))
        assert gm.placa_de_cada_fonte(lista) == {
            "alsa_input.usb-Sony-00.mono-fallback": "3"}

    def test_lista_vazia_nao_inventa_placa(self) -> None:
        assert gm.placa_de_cada_fonte("") == {}
        assert gm.placa_de_cada_fonte("lixo\nsem nada\n") == {}


class TestOGanhoViajaNoPerfil:
    """**21/09/2026 — a segunda metade da ordem de produto, e a que faltava.**"""

    def _perfil_vazio(self):
        from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

        return Profile(name="regua-do-ganho", match=MatchManual())

    def test_o_campo_existe_nos_dois_niveis(self):
        """MORDIDA: tire `gain` de um dos dois. O `model_copy` do gesto passa a"""
        from hefesto_dualsense4unix.profiles.schema import (
            ControllerMicOverride,
            ProfileMicConfig,
        )

        assert "gain" in ProfileMicConfig.model_fields
        assert "gain" in ControllerMicOverride.model_fields

    def test_o_ganho_chega_ao_controllers_do_perfil(self):
        """O gesto grava no `controllers[uniq]`, nunca só na seção global."""
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        prof = self._perfil_vazio()
        d = DraftConfig.from_profile(prof)
        uniq = "aa:bb:cc:00:00:01"
        d2 = d.with_controller_mic(
            uniq, d.effective_mic_for(uniq).model_copy(update={"gain": 62}))
        p2 = d2.to_profile(prof.name, priority=prof.priority)
        guardado = [v.mic.gain for v in (p2.controllers or {}).values()]
        assert guardado == [62], f"o ganho não chegou ao disco: {p2.controllers}"

    def test_o_salvar_nao_destroi_o_ganho(self):
        """**A FAMÍLIA DE DEFEITO QUE ISTO EVITA TEM NOME E DATA:** em 05/09 o"""
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        prof = self._perfil_vazio()
        d = DraftConfig.from_profile(prof)
        uniq = "aa:bb:cc:00:00:01"
        p2 = d.with_controller_mic(
            uniq, d.effective_mic_for(uniq).model_copy(update={"gain": 62})
        ).to_profile(prof.name, priority=prof.priority)
        chave = next(iter(p2.controllers))
        d3 = DraftConfig.from_profile(p2)
        assert d3.effective_mic_for(chave).gain == 62, (
            "o ganho não chegou ao card — o override guarda e a tela não lê")
        p3 = d3.to_profile(prof.name, priority=p2.priority)
        assert p3.controllers[chave].mic.gain == 62, (
            "o Salvar destruiu o ganho que a aba tinha gravado")

    def test_a_ativacao_do_perfil_escreve_o_ganho_na_placa(self):
        """**«GRAVEI» NÃO É «CHEGOU AO APARELHO»** — é a régua desta casa, e o
        campo que grava e ninguém aplica é pior que campo nenhum: ele acende a
        coluna «Ajuste próprio» sobre um valor que nada aplica.

        MORDIDA: tire a chamada a `_aplicar_ganho_do_mic` do `apply_mic`.
        """
        from hefesto_dualsense4unix.profiles import manager as mgr

        escritos = []

        class _Falso:
            @staticmethod
            def definir(uniq, por_cento, na_mesa):
                escritos.append((uniq, por_cento, tuple(na_mesa)))
                return (por_cento, -3.0)

        from hefesto_dualsense4unix import integrations
        from hefesto_dualsense4unix.integrations import ganho_do_microfone

        antes = ganho_do_microfone.definir
        integrations.ganho_do_microfone.definir = _Falso.definir
        try:
            m = mgr.ProfileManager.__new__(mgr.ProfileManager)
            relatorio: dict[str, str] = {}
            secao = type("S", (), {"gain": 62})()
            estado = m._aplicar_ganho_do_mic(secao, "aa:bb:cc:00:00:01", relatorio)
        finally:
            integrations.ganho_do_microfone.definir = antes

        assert escritos == [("aa:bb:cc:00:00:01", 62, ("aa:bb:cc:00:00:01",))]
        assert estado == "aplicado"
        assert relatorio["mic:ganho:aa:bb:cc:00:00:01"] == "aplicado"

    def test_sem_uniq_nao_escreve_na_placa_de_ninguem(self):
        """A seção GLOBAL não sabe em qual placa escrever, e chutar a primeira"""
        from hefesto_dualsense4unix.profiles import manager as mgr

        m = mgr.ProfileManager.__new__(mgr.ProfileManager)
        relatorio: dict[str, str] = {}
        secao = type("S", (), {"gain": 62})()
        assert m._aplicar_ganho_do_mic(secao, None, relatorio) == "sem_uniq"
        assert relatorio == {"mic:ganho": "sem_uniq"}

    def test_o_apply_mic_chama_mesmo_o_aplicador_do_ganho(self):
        """**A RÉGUA DE CIMA MEDE O MÉTODO; ESTA MEDE A LIGAÇÃO.**

        Sem ela, `_aplicar_ganho_do_mic` poderia existir inteiro e correto e
        nunca ser chamado — *a cura escrita e nunca ligada*, que é o defeito
        mais caro desta casa e já custou uma leva inteira.

        E a ORDEM importa: a chamada tem de vir ANTES do `return None` que
        atalha a seção sem `volume` e sem `muted`. Um perfil que guarde só o
        ganho sairia pela porta sem escrever nada.

        MORDIDA: mova a chamada para depois do `return None`.
        """
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/profiles/manager.py"
        ).read_text(encoding="utf-8")
        i = fonte.index("    def apply_mic(")
        corpo = fonte[i : fonte.index("\n    def ", i + 10)]
        assert "self._aplicar_ganho_do_mic(" in corpo, (
            "o `apply_mic` não chama o aplicador do ganho — a cura está "
            "escrita e não ligada")
        assert corpo.index("self._aplicar_ganho_do_mic(") < corpo.index(
            "if volume is None and muted is None:"
        ), "o ganho é aplicado DEPOIS do atalho — um perfil só com ganho sai " \
           "pela porta sem escrever nada"
