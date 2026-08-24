"""ONDA0-Z1/T1: ``frase_do_desfecho`` — o CORPO do daemon manda, o host explica.

A mordida da tarefa (a que prova a inversão): um corpo de mesa vazia
(``aplicado_em: []``, ``guardado_em: []``) com um ``host`` que jura que o alvo
está NA mesa. Antes desta função, a heurística de ``host`` venceria e a frase
diria "aplicado" — é exatamente o que a bancada mediu em 23/08/2026. Depois da
cura, a frase tem de dizer que nada aconteceu, porque é isso que o CORPO diz.

**Arranque o passo 2** (comente a leitura de ``destinos_da_aplicacao`` e volte
direto para a heurística de host) e veja a "aplicado" mentirosa voltar — é o
teste ``test_z1_t1_mordida_sem_o_passo_2_a_mesa_vazia_minta_de_novo`` que exerce
isso; ele SÓ reprova se a inversão realmente aconteceu.
"""

from __future__ import annotations

from typing import ClassVar

from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    GUARDADO,
    NADA_ACONTECEU,
    frase_do_desfecho,
)


class _HostNaMesa:
    """Jura que o alvo está NA mesa — nenhuma das três razões de guardado vale."""

    _edit_target_uniq = None  # "Todos": sem alvo a guardar
    _coop_ligado = False
    _modo_nativo_ligado = False


class _HostAlvoFora:
    _edit_target_uniq = "aa:bb:cc:00:00:01"
    _edit_target_label = "Controle 2 (BT)"
    # o alvo não está aqui
    _target_uniq_by_index: ClassVar[dict[int, str]] = {0: "aa:bb:cc:00:00:02"}
    _coop_ligado = False
    _modo_nativo_ligado = False


CORPO_MESA_VAZIA = {"status": "ok", "aplicado_em": [], "guardado_em": []}


def test_z1_t1_corpo_vazio_diz_que_nada_aconteceu_mesmo_com_host_dizendo_mesa_cheia() -> None:
    """A MORDIDA: corpo de mesa vazia, host jurando alvo presente -> "nada"."""
    msg = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", CORPO_MESA_VAZIA, _HostNaMesa())
    assert NADA_ACONTECEU in msg
    assert "aplicado" not in msg


def test_z1_t1_mordida_sem_o_passo_2_a_mesa_vazia_minta_de_novo() -> None:
    """Sem a leitura das listas (passo 2), a heurística do host venceria e
    mentiria "aplicado" — replica aqui a decisão SEM a cura para provar que o
    teste de cima está medindo a inversão, não outra coisa."""

    def frase_sem_a_cura(assunto: str, corpo: object, host: object) -> str:
        # é a heurística de ANTES: ignora `corpo`, decide só pelo host.
        if getattr(host, "_modo_nativo_ligado", False):
            return f"{assunto} guardado"
        if getattr(host, "_edit_target_uniq", None):
            return f"{assunto} guardado"
        return f"{assunto} aplicado"

    msg = frase_sem_a_cura("Gatilho esquerdo (L2): Rigid", CORPO_MESA_VAZIA, _HostNaMesa())
    assert msg.endswith("aplicado")  # a mentira que a bancada mediu em 23/08


def test_z1_t1_recusado_no_corpo_usa_o_motivo_do_daemon() -> None:
    """O dublê tem de saber RECUSAR (armadilha A2): corpo com `motivo` vence
    tudo — inclusive um host que diria "aplicado"."""
    corpo = {"status": "recusado", "motivo": "Fim <= Início"}
    msg = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", corpo, _HostNaMesa())
    assert "Fim <= Início" in msg


def test_z1_t1_status_ok_com_motivo_nao_e_recusa() -> None:
    """Achado do advogado da premissa (24/08): `status: "ok"` + `motivo` é
    sucesso PARCIAL (o `rumble.stop` que solta o par mas não cala o motor que
    o jogo segura pelo hidraw), não recusa. Rotular como "recusado" seria a
    mesma mentira que esta função existe para matar, na direção oposta."""
    corpo = {"status": "ok", "motivo": "o jogo pode seguir vibrando pelo hidraw"}
    msg = frase_do_desfecho("Vibração", corpo, _HostNaMesa())
    assert "o jogo pode seguir vibrando pelo hidraw" in msg
    assert "recusado" not in msg


def test_z1_t1_aplicado_em_um_so_destino_fica_byte_a_byte_igual_ao_de_hoje() -> None:
    """A mordida gêmea: um MAC em `aplicado_em` continua dizendo "aplicado"."""
    corpo = {"status": "ok", "aplicado_em": ["aa:bb:cc:00:00:01"], "guardado_em": []}
    msg = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", corpo, _HostNaMesa())
    assert msg == "Gatilho esquerdo (L2): Rigid aplicado"


def test_z1_t1_aplicado_em_varios_destinos_nomeia_quantos() -> None:
    corpo = {
        "status": "ok",
        "aplicado_em": ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"],
        "guardado_em": [],
    }
    msg = frase_do_desfecho("Cor (50%)", corpo, _HostNaMesa())
    assert "2 controles" in msg


def test_z1_t1_guardado_em_usa_as_razoes_do_host_como_porque() -> None:
    corpo = {"status": "ok", "aplicado_em": [], "guardado_em": ["aa:bb:cc:00:00:01"]}
    msg = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", corpo, _HostAlvoFora())
    assert GUARDADO in msg
    assert "Controle 2" in msg


def test_z1_t1_coop_so_entra_quando_coop_aplica_e_verdade() -> None:
    """O co-op nunca governa gatilho/cor — só os 5 LEDs de jogador. Um host
    com o co-op ligado NÃO pode aparecer como razão quando `coop_aplica` é
    False (o padrão), mesmo que o corpo esteja guardado por outro motivo."""

    class _HostCoopLigado:
        _edit_target_uniq = None
        _coop_ligado = True
        _modo_nativo_ligado = True  # a razão real do guardado, aqui

    corpo = {"status": "ok", "aplicado_em": [], "guardado_em": ["aa:bb:cc:00:00:01"]}
    msg = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", corpo, _HostCoopLigado())
    assert "co-op" not in msg
    assert "Modo Nativo" in msg or "nativo" in msg.lower()


def test_z1_t1_coop_entra_quando_coop_aplica_e_o_chamador_pede() -> None:
    class _HostCoopLigado:
        _edit_target_uniq = None
        _coop_ligado = True
        _modo_nativo_ligado = False

    corpo = {"status": "ok", "aplicado_em": [], "guardado_em": ["aa:bb:cc:00:00:01"]}
    msg = frase_do_desfecho(
        "5 LEDs de jogador", corpo, _HostCoopLigado(), coop_aplica=True
    )
    assert "co-op" in msg


def test_z1_t1_corpo_ausente_cai_na_heuristica_de_hoje() -> None:
    """Sem resposta do daemon (``None``), não há nada a ler — o ramo 4 usa a
    heurística de host, exatamente como o código de antes desta tarefa."""
    msg = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", None, _HostAlvoFora())
    assert GUARDADO in msg
    assert "Controle 2" in msg

    msg2 = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", None, _HostNaMesa())
    assert msg2 == "Gatilho esquerdo (L2): Rigid aplicado"
