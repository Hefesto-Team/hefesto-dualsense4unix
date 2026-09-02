"""MIC-DA-MESA-ELEICAO-01 — as réguas do eleitor de microfone.

A ARMADILHA, medida em três lugares independentes desta casa: **o WirePlumber
não honra nó eleito que não se sustenta.** Ele reelege sozinho, e a preferência
que acabamos de gravar vira lixo. A pós-condição canônica é o ATIVO RELIDO,
nunca o `configured`.

Declarar sucesso pela escrita é o *"silêncio não é sucesso"* na forma mais cara
que ele tem aqui: o LED do controle passaria a mentir sobre o microfone dela —
plástico aceso, `pactl` gravando outra coisa.
"""

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
                # O ponto INTEIRO: aceitar a escrita e devolver OUTRA coisa na
                # leitura seguinte é o que o WirePlumber faz de verdade.
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
            if "--melhor-fonte-elegivel" in argv:
                return (0, _OUTRO if self.sustenta else "")
        return (0, "")


@pytest.fixture()
def pactl(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    dublê = _Pactl()
    # Um script de mentira que DECLARA as duas flags: sem isso o
    # `_script_conhece` recusaria antes de chegar ao dublê, e todas as réguas
    # deste arquivo passariam pelo motivo errado.
    script = tmp_path / "fix_wireplumber_default_source.sh"
    script.write_text(
        "#!/usr/bin/env bash\n--fonte-se-sustenta) :;;\n--melhor-fonte-elegivel) :;;\n"
    )
    monkeypatch.setattr(elm, "_rodar", dublê)
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: script)
    return dublê


# ---------------------------------------------------------------------------
# 7. A eleição não acredita na própria escrita
# ---------------------------------------------------------------------------


def test_escrita_aceita_com_ativo_diferente_e_fracasso(pactl: Any) -> None:
    """CURA A ARRANCAR: declarar sucesso pela escrita.

    Sem esta régua o LED vira mentira de segunda geração: aceso sobre um nó que
    o WirePlumber já desfez.
    """
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
    """Vazio, `auto_null` e `.monitor` são "não sei", nunca "é este".

    Um `.monitor` de padrão é o defeito de gravar o áudio que SAI em vez da voz
    dela — e o medidor de nível mostra sinal, então PARECE que funciona.
    """
    pactl.ativo_depois = nao_resposta
    eleitor = elm.EleitorDeMicrofone()
    r = eleitor._eleger_nome(_ALVO)
    assert r.ok is False
    assert r.ativo is None


# ---------------------------------------------------------------------------
# 8. O critério de "se sustenta" tem UM dono só
# ---------------------------------------------------------------------------


def test_sem_o_script_a_eleicao_recusa_em_vez_de_inventar_criterio(
    monkeypatch: pytest.MonkeyPatch, pactl: Any
) -> None:
    """CURA A ARRANCAR: um filtro de porta escrito em Python.

    Esta régua reprova a EXISTÊNCIA da segunda régua. Do lado Python não há uma
    linha que olhe porta de captura, e escrever uma é o defeito RECEITA-ERRADA-01
    — duas réguas contando coisas diferentes sobre o mesmo estado.
    """
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: None)
    eleitor = elm.EleitorDeMicrofone()

    r = eleitor._eleger_nome(_ALVO)

    assert r.ok is False
    assert pactl.escritas == [], "nada foi escrito no áudio dela"
    assert "segundo critério" in r.motivo


def test_flag_que_o_script_do_disco_nao_conhece_nao_e_chamada(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UMA ELEIÇÃO NÃO PODE VIRAR UMA INSTALAÇÃO. Medido em 01/09/2026.

    Arrancando a flag do shell para ver a régua reprovar, o que se mediu foi
    pior do que a reprovação esperada: o `for arg in "$@"` daquele script
    termina em ``*) printf 'aviso: argumento desconhecido'`` e o `MODE`
    **continua sendo o default, que é `install`**. Chamar o script com uma flag
    que ele não conhece não devolve erro — ele roda o INSTALADOR, escreve
    drop-in e reinicia o WirePlumber da sessão dela. (Aconteceu: a fonte padrão
    passou por `auto_null.monitor` antes de reassentar.)

    E o caso é real, não hipotético: o script instalado em `~/.local/bin` é UM
    por máquina e pode ser mais velho que este pacote.

    CURA A ARRANCAR: tirar o `_script_conhece` e chamar o script direto — a
    régua reprova, porque o dublê registra a chamada que não podia acontecer.
    """
    script = tmp_path / "fix_wireplumber_default_source.sh"
    script.write_text("#!/usr/bin/env bash\n# um script velho, sem as flags novas\n")
    chamadas: list[list[str]] = []

    def _espiao(argv: list[str]) -> tuple[int, str]:
        chamadas.append(argv)
        return (0, "")

    monkeypatch.setattr(elm, "_rodar", _espiao)
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: script)

    assert elm.fonte_se_sustenta(_ALVO) is None
    assert elm.melhor_fonte_elegivel() is None
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
    """`--melhor-fonte-elegivel` vazio: não se elege monitor, não se elege nada.

    É o estado desta bancada em 01/09/2026 — a webcam fora e as três portas
    analógicas `not available`. Cair no `.monitor` é MONITOR-QUE-VENCE-01.
    """
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


# ---------------------------------------------------------------------------
# 9. A eleição GUARDA o anterior
# ---------------------------------------------------------------------------


def test_a_primeira_eleicao_guarda_o_microfone_de_antes(pactl: Any) -> None:
    """CURA A ARRANCAR: apagar a memória.

    Ela existe porque eleger PERSISTE e empurra a preferência anterior pilha
    abaixo (medido com backup do antes e do depois). Numa mesa em turnos,
    quatro eleições empurram o microfone real dela quatro degraus, caladas.
    """
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


# ---------------------------------------------------------------------------
# 10. O eleitor SABE QUEM ELEGEU — e é isso que impede o J2 de tirar o mic da J1
# ---------------------------------------------------------------------------
#
# ACHADO DA AUDITORIA DE 02/09/2026. `devolver_o_microfone()` é GLOBAL: não
# recebe `uniq`. Sem um campo dizendo quem está com o microfone, o laço decidia
# a devolução só pelo bit `mudo` — e na mesa de quatro que ela nomeou o botão
# do Jogador 2 tirava o padrão do sistema da Jogadora 1, que ficava com o LED
# aceso dizendo "estou no ar".
#
# ESTAS RÉGUAS SÃO SOBRE O ELEITOR DE VERDADE, e o motivo é o defeito nº 5 desta
# própria onda: *"o portão não mordia porque o dublê trazia o mesmo default
# falso"*. As réguas de cena em `test_mic_da_mesa_o_ipc_a_tela_e_o_gesto.py`
# usam um `EleitorDeMicrofone` dublado, que mantém o campo por conta própria —
# arrancar a linha do produto não as faria reprovar.


def test_a_eleicao_conferida_registra_quem_esta_com_o_microfone(pactl: Any) -> None:
    """CURA A ARRANCAR: `self.eleito = uniq` em `eleger_por_uniq`.

    Sem ela o `_eleger_ou_devolver` volta a devolver o microfone da mesa na
    borda de QUALQUER controle.
    """
    eleitor = elm.EleitorDeMicrofone()
    assert eleitor.eleito is None, "ninguém elegeu ainda"

    r = eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )

    assert r.ok is True
    assert eleitor.eleito == "aabbcc000011"


def test_a_eleicao_que_o_wireplumber_desfez_nao_registra_dono(pactl: Any) -> None:
    """A escrita não basta: a posse só vale com o ATIVO relido batendo.

    É o mesmo contrato do LED — registrar como dono quem o WirePlumber já
    reelegeu por cima seria a mentira de segunda geração com outro nome.
    """
    pactl.ativo_depois = _OUTRO
    eleitor = elm.EleitorDeMicrofone()

    r = eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )

    assert r.ok is False
    assert eleitor.eleito is None, "a escrita aconteceu, a posse não"


def test_a_devolucao_solta_a_posse_com_ou_sem_para_onde_voltar(pactl: Any) -> None:
    """Os DOIS desfechos da volta soltam o `eleito`.

    O controle saiu do ar nos dois casos. Continuar anotando-o como eleito faria
    a próxima borda dele ser lida como "o eleito devolvendo de novo", e a de
    outro jogador como recusa — o defeito de volta, ao contrário.
    """
    eleitor = elm.EleitorDeMicrofone()
    eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )
    assert eleitor.eleito == "aabbcc000011"

    assert eleitor.devolver_o_microfone().ok is True
    assert eleitor.eleito is None, "com destino, a posse cai"

    eleitor.eleger_por_uniq(
        "aabbcc000011", fontes=[_ALVO], uniqs_com_audio=["aabbcc000011"]
    )
    assert eleitor.eleito == "aabbcc000011"
    pactl.sustenta = False  # não há para onde voltar

    assert eleitor.devolver_o_microfone().ok is False
    assert eleitor.eleito is None, "sem destino também — o controle saiu do ar"
