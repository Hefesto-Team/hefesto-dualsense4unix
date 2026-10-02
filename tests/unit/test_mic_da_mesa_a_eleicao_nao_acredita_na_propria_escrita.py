"""MIC-DA-MESA-ELEICAO-01 — as réguas do eleitor de microfone."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm

_ALVO = "alsa_input.usb-Sony_DualSense-00.iec958-stereo"
_OUTRO = "alsa_input.pci-0000_00_1f.3.analog-stereo"


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    """O settle não dorme na suíte — o que se mede é a RELEITURA, não o relógio."""
    monkeypatch.setattr(elm, "SETTLE_PASSOS", 3)
    monkeypatch.setattr(elm, "SETTLE_PASSO_S", 0.0)


class _Pactl:
    """Dublê de `pactl` + do script do WirePlumber, com respostas roteirizadas."""

    def __init__(
        self,
        *,
        ativo: str = "",
        ativo_depois: str | None = None,
        sustenta: bool | None = True,
    ) -> None:
        self.ativo = ativo
        self.ativo_depois = ativo_depois
        self.sustenta = sustenta
        self.escritas: list[str] = []

    def __call__(self, argv: list[str]) -> tuple[int, str]:
        if argv[:1] == ["pactl"]:
            if argv[1] == "get-default-source":
                return (0, self.ativo)
            if argv[1] == "set-default-source":
                self.escritas.append(argv[2])
                self.ativo = (
                    self.ativo_depois if self.ativo_depois is not None else argv[2]
                )
                return (0, "")
            return (0, "")
        if argv[:1] == ["bash"]:
            if "--fonte-se-sustenta" in argv:
                if self.sustenta is None:
                    return (1, "")
                return (0, argv[-1] if self.sustenta else "")
            if "--outra-captura-elegivel" in argv:
                return (0, _OUTRO if self.sustenta else "")
        return (0, "")


@pytest.fixture()
def pactl(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    dublê = _Pactl()
    script = tmp_path / "fix_wireplumber_default_source.sh"
    script.write_text(
        "#!/usr/bin/env bash\n--fonte-se-sustenta) :;;\n--outra-captura-elegivel) :;;\n"
    )
    monkeypatch.setattr(elm, "_rodar", dublê)
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: script)
    return dublê


def test_escrita_aceita_com_ativo_diferente_e_fracasso(pactl: Any) -> None:
    """CURA A ARRANCAR: declarar sucesso pela escrita."""
    pactl.ativo_depois = _OUTRO
    eleitor = elm.EleitorDeMicrofone()

    r = eleitor._eleger_nome(_ALVO)

    assert pactl.escritas == [_ALVO], "a escrita ACONTECEU"
    assert r.ok is False, "e mesmo assim não é sucesso"
    assert r.ativo == _OUTRO
    assert "reelegeu" in r.motivo


def test_escrita_com_ativo_igual_e_sucesso(pactl: Any) -> None:
    """A metade que prova que a régua não é "nunca dá certo"."""
    eleitor = elm.EleitorDeMicrofone()
    r = eleitor._eleger_nome(_ALVO)
    assert r.ok is True
    assert r.ativo == _ALVO


@pytest.mark.parametrize(
    "nao_resposta", ["", "auto_null", "auto_null.monitor", "alsa_output.x.monitor"]
)
def test_as_tres_nao_respostas_nao_contam_como_ativo(
    pactl: Any, nao_resposta: str
) -> None:
    """Vazio, `auto_null` e `.monitor` são "não sei", nunca "é este"."""
    pactl.ativo_depois = nao_resposta
    eleitor = elm.EleitorDeMicrofone()
    r = eleitor._eleger_nome(_ALVO)
    assert r.ok is False
    assert r.ativo is None


def test_sem_o_script_a_eleicao_recusa_em_vez_de_inventar_criterio(
    monkeypatch: pytest.MonkeyPatch, pactl: Any
) -> None:
    """CURA A ARRANCAR: um filtro de porta escrito em Python."""
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: None)
    eleitor = elm.EleitorDeMicrofone()

    r = eleitor._eleger_nome(_ALVO)

    assert r.ok is False
    assert pactl.escritas == [], "nada foi escrito no áudio dela"
    assert "segundo critério" in r.motivo


def test_flag_que_o_script_do_disco_nao_conhece_nao_e_chamada(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UMA ELEIÇÃO NÃO PODE VIRAR UMA INSTALAÇÃO. Medido em 01/09/2026."""
    script = tmp_path / "fix_wireplumber_default_source.sh"
    script.write_text("#!/usr/bin/env bash\n# um script velho, sem as flags novas\n")
    chamadas: list[list[str]] = []

    def _espiao(argv: list[str]) -> tuple[int, str]:
        chamadas.append(argv)
        return (0, "")

    monkeypatch.setattr(elm, "_rodar", _espiao)
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: script)

    assert elm.fonte_se_sustenta(_ALVO) is None
    with pytest.raises(elm.ConsultaIndisponivelError):
        elm.outra_captura_elegivel()
    assert chamadas == [], "o script velho não pode ser chamado nem uma vez"


def test_alvo_que_nao_se_sustenta_nao_e_escrito(pactl: Any) -> None:
    """Eleger nó sem porta usável sobrescreve a preferência dela por lixo."""
    pactl.sustenta = False
    eleitor = elm.EleitorDeMicrofone()

    r = eleitor._eleger_nome(_ALVO)

    assert r.ok is False
    assert pactl.escritas == []
    assert "porta de captura usável" in r.motivo


def test_sem_para_onde_voltar_nao_elege_nada(pactl: Any) -> None:
    """`--outra-captura-elegivel` vazio: não se elege monitor, não se elege nada."""
    pactl.sustenta = False
    eleitor = elm.EleitorDeMicrofone()

    r = eleitor.devolver_o_microfone()

    assert r.ok is False
    assert pactl.escritas == []
    assert "não há microfone para onde voltar" in r.motivo


def test_o_caminho_de_volta_elege_a_melhor_que_nao_e_o_controle(pactl: Any) -> None:
    """A metade que prova que a volta funciona quando há para onde voltar."""
    eleitor = elm.EleitorDeMicrofone()
    r = eleitor.devolver_o_microfone()
    assert r.ok is True
    assert pactl.escritas == [_OUTRO]


def test_a_primeira_eleicao_guarda_o_microfone_de_antes(pactl: Any) -> None:
    """CURA A ARRANCAR: apagar a memória."""
    pactl.ativo = _OUTRO
    eleitor = elm.EleitorDeMicrofone()

    eleitor.eleger_por_uniq(
        "aabbcc000001",
        fontes=[_ALVO],
        uniqs_com_audio=["aabbcc000001"],
    )

    assert eleitor.anterior == _OUTRO


def test_a_memoria_e_gravada_uma_vez_por_sessao(pactl: Any) -> None:
    """Regravar a cada eleição faria a memória virar o controle anterior."""
    pactl.ativo = _OUTRO
    eleitor = elm.EleitorDeMicrofone()

    eleitor._eleger_nome(_ALVO)
    assert eleitor.anterior == _OUTRO

    eleitor._eleger_nome(_ALVO)
    assert eleitor.anterior == _OUTRO, "a segunda eleição não pode reescrever a memória"


def test_a_eleicao_conferida_registra_quem_esta_com_o_microfone(pactl: Any) -> None:
    """CURA A ARRANCAR: `self.eleito = uniq` em `eleger_por_uniq`."""
    eleitor = elm.EleitorDeMicrofone()
    assert eleitor.eleito is None, "ninguém elegeu ainda"

    r = eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )

    assert r.ok is True
    assert eleitor.eleito == "aabbcc000011"


def test_a_eleicao_que_o_wireplumber_desfez_nao_registra_dono(pactl: Any) -> None:
    """A escrita não basta: a posse só vale com o ATIVO relido batendo."""
    pactl.ativo_depois = _OUTRO
    eleitor = elm.EleitorDeMicrofone()

    r = eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )

    assert r.ok is False
    assert eleitor.eleito is None, "a escrita aconteceu, a posse não"


def test_a_devolucao_solta_a_posse_so_quando_ela_foi_conferida(pactl: Any) -> None:
    """A posse muda pela RELEITURA DO ATIVO — e pelo ato de calar sem destino."""
    eleitor = elm.EleitorDeMicrofone()
    eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )
    assert eleitor.eleito == "aabbcc000011"

    assert eleitor.devolver_o_microfone().ok is True
    assert eleitor.eleito is None, "a volta foi CONFERIDA: a posse cai"

    eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )
    assert eleitor.eleito == "aabbcc000011"
    pactl.sustenta = False
    escritas = list(pactl.escritas)

    assert eleitor.devolver_o_microfone().ok is False
    assert eleitor.eleito == "aabbcc000011", (
        "a volta sozinha, sem destino, não sabe se foi um ato de calar: a "
        "posse fica de pé"
    )

    calou = eleitor.passar_o_padrao([], ["aabbcc000011"], "aabbcc000011")
    assert calou.ok is True and calou.motivo == "", (
        "o ato de calar do eleito sem destino está FEITO: sem frase no cartão"
    )
    assert eleitor.eleito is None, "o ato de calar sem destino solta a posse"
    assert pactl.escritas == escritas, "e nada foi escrito"
