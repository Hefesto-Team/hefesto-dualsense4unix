"""O-GANHO-DO-MIC-TEM-DONO-01/B — o deslizante que faltava, e o lugar dela."""

from __future__ import annotations

import pathlib
import re

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes.a02_controles import (
    RAZAO_DO_GANHO_FORA,
    _elemento_e_ganho_do_scontents,
    _ganho_do_scontents,
    _nome_do_scontrol,
    _placa_de_cada_fonte,
)

PUBLICADO = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")
BANCADA = pathlib.Path("mockup/02-controles.html")
GERADOR = pathlib.Path("src/hefesto_dualsense4unix/interface/aba02.py")
PACOTE = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py")

MESA = 4


@pytest.mark.parametrize("alvo", [PUBLICADO, BANCADA], ids=["publicado", "mockup"])
class TestOGanhoTemOndePegar:
    def test_ha_um_input_de_ganho_em_cada_cartao(self, alvo: pathlib.Path) -> None:
        """**A MORDIDA PRINCIPAL: troque o `<input>` por um `<span>`.**"""
        corpo = alvo.read_text(encoding="utf-8")
        inputs = re.findall(
            r'<input[^>]*data-gesto="ganho-mic"[^>]*>', corpo)
        assert len(inputs) == MESA, (
            f"o ganho tem {len(inputs)} deslizante(s) e devia ter {MESA} — "
            f"sem `<input type=\"range\">` a barra PINTA o valor e não há "
            f"onde pegá-la, que é a queixa dela de 20/09")
        for tag in inputs:
            assert 'type="range"' in tag, f"não é deslizante: {tag}"
            assert 'data-hef-alvo="valor"' in tag, (
                "sem o alvo `valor` o tique escreve o número como TEXTO dentro "
                f"do input, em vez de mover o cursor: {tag}")

    def test_o_ganho_desceu_para_linha_propria(self, alvo: pathlib.Path) -> None:
        """A POSIÇÃO É DO USUÁRIO, e ela a aprovou por imagem."""
        corpo = alvo.read_text(encoding="utf-8")
        assert re.search(r'<div class="vol ganho"', corpo), (
            "o ganho não é uma linha de volume — ele voltou para a linha do "
            "rótulo, que é a posição que ela recusou")
        for linha_do_rotulo in re.findall(r'<div class="rot rot-linha">.*?</div>',
                                          corpo, re.S):
            assert "ganho" not in linha_do_rotulo, (
                "o ganho voltou para a linha do rótulo do Microfone")

    def test_as_duas_linhas_dizem_o_nome(self, alvo: pathlib.Path) -> None:
        """Sem o nome, são dois trilhos iguais empilhados."""
        corpo = alvo.read_text(encoding="utf-8")
        for nome in ("Volume", "Ganho"):
            vistos = corpo.count(f'<span class="rot-vol">{nome}</span>')
            assert vistos == MESA, (
                f"o rótulo «{nome}» está em {vistos} lugar(es) e devia estar "
                f"em {MESA}")

    def test_a_unidade_separa_os_dois_eixos(self, alvo: pathlib.Path) -> None:
        """Um sai em por cento e o outro em decibéis."""
        corpo = alvo.read_text(encoding="utf-8")
        assert corpo.count('<span class="un">dB</span>') == MESA


class TestOAtoChegaAoAparelho:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_gesto_esta_registrado_e_chama_o_escritor(self) -> None:
        """MORDIDA: tire o decorador, ou troque a chamada por um `pass`."""
        fonte = PACOTE.read_text(encoding="utf-8")
        assert '@gesto("02-controles.html", "ganho-mic", grava="gravar_pelo_gesto")' in fonte, (
            "o gesto perdeu o `grava` — o ganho volta a não viajar no disco")
        i = fonte.index("def ganho_mic(")
        corpo = fonte[i:i + 2500]
        assert "definir_ganho_do_microfone(" in corpo, (
            "o gesto não chama o escritor — é a cura escrita e nunca ligada")
        assert "RAZAO_DO_GANHO_FORA" in corpo, (
            "a recusa não tem razão, ou inventou uma segunda frase para o "
            "mesmo fato que o cinza do trilho já explica")

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

    def test_o_guarda_do_clique_duplo_esta_no_lugar(self) -> None:
        """Um `<input type=range>` clicado dispara `change` E `click`."""
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("def ganho_mic(")
        corpo = fonte[i:i + 2500]
        assert '"tipo"' in corpo and '"click"' in corpo, (
            "o gesto não separa o `click` que vem depois do `change`")


class TestOElementoNaoSeDigita:
    def test_o_nome_perde_as_aspas_e_guarda_o_indice(self) -> None:
        """`'Headset',0` -> `Headset,0`."""
        assert _nome_do_scontrol("'Headset',0") == "Headset,0"
        assert _nome_do_scontrol("'Mic Boost',1") == "Mic Boost,1"
        assert _nome_do_scontrol("Capture,0") == "Capture,0"

    def test_o_indice_nao_se_perde(self) -> None:
        """`Headset` sem o `,0` escreve no elemento 0 de uma placa cujo ganho"""
        assert _nome_do_scontrol("'Headset',2").endswith(",2")

    def test_o_parser_devolve_elemento_por_cento_e_db(self) -> None:
        texto = (
            "Simple mixer control 'Headset',0\n"
            "  Capabilities: cvolume cswitch\n"
            "  Capture channels: Mono\n"
            "  Mono: Capture 101 [100%] [48.00dB] [on]\n")
        assert _elemento_e_ganho_do_scontents(texto) == ("Headset,0", 100, 48.0)

    def test_os_dois_parsers_tem_corpo_unico(self) -> None:
        """Dois parsers da mesma saída é como o leitor e o escritor do mesmo"""
        texto = (
            "Simple mixer control 'Mic',1\n"
            "  Capabilities: cvolume\n"
            "  Mono: Capture 40 [37%] [12.50dB] [on]\n")
        inteiro = _elemento_e_ganho_do_scontents(texto)
        assert inteiro is not None
        assert _ganho_do_scontents(texto) == (inteiro[1], inteiro[2])

    def test_sem_elemento_de_ganho_nao_se_chuta_zero(self) -> None:
        """Chutar zero pintaria «ganho no mínimo» sobre uma placa sem ganho."""
        assert _elemento_e_ganho_do_scontents(
            "Simple mixer control 'PCM',0\n  Capabilities: pvolume\n") is None
        assert _ganho_do_scontents("") is None


class TestAPlacaSaiDoServidorDeSom:
    def test_o_no_casa_com_a_placa_alsa(self) -> None:
        lista = (
            'Source #7\n'
            '\tName: alsa_input.usb-Sony-00.mono-fallback\n'
            '\t\talsa.card = "3"\n'
            'Source #9\n'
            '\tName: hefesto_mic_a0fa9c\n')
        assert _placa_de_cada_fonte(lista) == {
            "alsa_input.usb-Sony-00.mono-fallback": "3"}

    def test_lista_vazia_nao_inventa_placa(self) -> None:
        assert _placa_de_cada_fonte("") == {}
        assert _placa_de_cada_fonte("lixo\nsem nada\n") == {}


def test_a_razao_do_cinza_e_a_mesma_da_recusa() -> None:
    """Uma frase só para o mesmo fato — o trilho cinza e o clique recusado."""
    assert "cabo" in RAZAO_DO_GANHO_FORA.lower()
    fonte = PACOTE.read_text(encoding="utf-8")
    i = fonte.index("def ganho_mic(")
    assert "RAZAO_DO_GANHO_FORA" in fonte[i:i + 2500]


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
