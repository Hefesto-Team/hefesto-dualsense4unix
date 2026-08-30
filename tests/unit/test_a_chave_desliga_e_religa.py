"""A régua da CHAVE — desligar um Hefesto por completo, e religar.

Pedido dela, 29/08/2026: *"temos que garantir que eu possa DESLIGAR o impacto
do outro Hefesto por completo e RELIGAR ele (...) com o botão de desligar
funcionando sem zuar o resto"*.

O QUE ESTA RÉGUA EXISTE PARA PEGAR
-----------------------------------
A cura óbvia — `systemctl --user mask` — parece fechar tudo e NÃO fecha. Medido
em 29/08: quando o `systemctl start` falha, o botão "Ligar daemon" da GUI cai
num `subprocess.Popen` (`app/actions/daemon_actions.py:2162-2176`) que levanta o
daemon sem passar por systemd nenhum. A chave em disco é o que tapa esse furo, e
estes testes travam os dois lados dela: que a AUSÊNCIA não muda nada, e que a
PRESENÇA é obedecida nos dois caminhos.
"""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.utils import chave

RAIZ = Path(__file__).resolve().parents[2]


def _por_a_chave(config_dir: Path) -> Path:
    """Escreve a chave como o `hefesto-chave.sh` escreve.

    O produto só LÊ a chave (ver o cabeçalho de `utils/chave.py`); quem escreve
    é o script. O teste imita o script de propósito — se um dia o formato
    divergir, é aqui que se vê.
    """
    alvo = chave.caminho_da_chave(config_dir)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(
        "desligado em 2026-08-29T21:00:00-03:00 por hefesto-chave\n"
        "para religar:  hefesto-chave estavel on\n",
        encoding="utf-8",
    )
    return alvo


def test_a_chave_ausente_nao_muda_nada(tmp_path):
    """O estado normal, e o que ele tem de custar: nada.

    Um HOME sem chave nenhuma não pode ver diferença de comportamento — senão
    esta leva teria mexido no produto que ela usa todo dia.
    """
    assert chave.motivo_do_desligamento(tmp_path) is None


def test_a_chave_posta_e_lida_e_a_retirada_some(tmp_path):
    alvo = _por_a_chave(tmp_path)
    assert chave.motivo_do_desligamento(tmp_path) is not None
    alvo.unlink()
    assert chave.motivo_do_desligamento(tmp_path) is None


def test_a_chave_diz_quando_e_como_desfazer(tmp_path):
    """O dia em que ela topar com este arquivo sem lembrar do contexto, a
    resposta tem de estar dentro dele — e quem a lê tem de repassar isso."""
    _por_a_chave(tmp_path)
    motivo = chave.motivo_do_desligamento(tmp_path)
    assert "desligado em" in motivo
    assert "para religar:" in motivo
    assert "hefesto-chave" in motivo


def test_chave_ilegivel_conta_como_desligado(tmp_path):
    """O estado seguro é RECUSAR.

    Quem pôs o arquivo queria o app parado; um erro de leitura não é permissão
    para subir e tomar o aparelho. Um diretório no lugar do arquivo é a forma
    mais simples de tornar a leitura impossível sem depender de permissão.
    """
    alvo = chave.caminho_da_chave(tmp_path)
    alvo.mkdir(parents=True)
    motivo = chave.motivo_do_desligamento(tmp_path)
    assert motivo is not None
    assert "não pôde ser lida" in motivo


def test_a_chave_de_uma_casa_nao_alcanca_a_outra(tmp_path):
    """Desligar o estável não pode desligar o de desenvolvimento junto —
    é literalmente o pedido dela ("garantir que ele funcione enquanto eu tenho
    a versão estável instalada")."""
    casa_dela = tmp_path / "hefesto-dualsense4unix"
    casa_de_dev = tmp_path / "hefesto-dev-dualsense4unix"
    casa_dela.mkdir()
    casa_de_dev.mkdir()
    _por_a_chave(casa_dela)
    assert chave.motivo_do_desligamento(casa_dela) is not None
    assert chave.motivo_do_desligamento(casa_de_dev) is None


def test_o_recado_diz_o_que_por_que_e_o_que_fazer():
    """Regra desta casa para frase de diagnóstico. Sem as três partes, a
    recusa vira "não funciona" e ela fica sem saída."""
    texto = chave.recado_da_recusa("desligado em 2026-08-29 por hefesto-chave")
    assert "NÃO subiu" in texto            # o quê
    assert "desligado pela chave" in texto  # por quê
    assert "Para religar:" in texto         # o que fazer


# --------------------------------------------------------------------------
# OS DOIS CAMINHOS QUE A CHAVE TEM DE FECHAR
# --------------------------------------------------------------------------
def test_o_daemon_consulta_a_chave_antes_de_tomar_o_aparelho():
    """A ORDEM é o teste, não a presença.

    Se a checagem viesse DEPOIS do `acquire_or_takeover`, um daemon que está
    prestes a recusar já teria mandado SIGTERM e depois SIGKILL no daemon que
    estava no ar — desligar um Hefesto derrubaria o outro. Mova a checagem
    para depois e este teste reprova.
    """
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "main.py"
    ).read_text(encoding="utf-8")
    # Mede a CHAMADA, não a menção: o comentário que explica a ordem cita o
    # `acquire_or_takeover` algumas linhas antes, e uma régua que procurasse o
    # nome solto mediria a prosa em vez do código. (Foi o que ela fez na
    # primeira versão, e reprovou um código que estava certo.)
    onde_a_chave = fonte.index("chave.motivo_do_desligamento()")
    onde_o_takeover = fonte.index("acquire_or_takeover(single_instance_name())")
    assert onde_a_chave < onde_o_takeover, (
        "a chave tem de ser consultada ANTES do takeover do aparelho"
    )


def test_o_botao_da_gui_nao_contorna_a_chave_pelo_popen():
    """O furo que a máscara não tapa, e a régua que o prova fechado.

    `app/actions/daemon_actions.py` sobe o daemon por `Popen` quando o
    `systemctl start` falha — e `systemctl start` numa unit mascarada falha
    SEMPRE. Sem esta guarda, `hefesto-chave estavel off` seria desfeito por um
    clique no botão "Ligar". Arranque a guarda e este teste reprova.
    """
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions"
        / "daemon_actions.py"
    ).read_text(encoding="utf-8")
    onde_a_guarda = fonte.index("motivo_do_desligamento")
    onde_o_popen = fonte.index("Fallback: spawn do daemon como child via Popen")
    assert onde_a_guarda < onde_o_popen


# --------------------------------------------------------------------------
# O SCRIPT DA CHAVE
# --------------------------------------------------------------------------
def test_o_script_da_chave_usa_os_nomes_de_unit_que_existem():
    """Conferidos na máquina dela em 29/08 com `systemctl --user
    list-unit-files`.

    O vigia da Steam chama-se `hefesto-steam-input-guard.*` — e NÃO
    `hefesto-dualsense4unix-steam-input-guard.*`, que era o nome suposto. Um
    `systemctl stop` num nome que não existe devolve sucesso sem parar coisa
    nenhuma: a chave diria "desliguei" e o vigia continuaria de pé.
    """
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    for unit in (
        "hefesto-dualsense4unix.service",
        "hefesto-dualsense4unix-storm-watch.service",
        "hefesto-steam-input-guard.path",
        "hefesto-steam-input-guard.timer",
    ):
        assert unit in script, unit
    # O nome que NÃO existe não pode aparecer.
    assert "hefesto-dualsense4unix-steam-input-guard" not in script


def test_a_chave_nao_toca_a_camada_compartilhada():
    """Regras udev, broker e bt-agent são da MÁQUINA, não do app.

    O app de dev precisa deles para enxergar o aparelho, e mexer neles exigiria
    sudo toda vez — custo que ela vetou em 22/08/2026. Se algum dia a chave
    ganhar um `systemctl stop hefesto-hidraw-broker`, este teste reprova.
    """
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    linhas_de_acao = [
        linha for linha in script.splitlines()
        if ("systemctl" in linha or "rm " in linha)
        and not linha.lstrip().startswith("#")
    ]
    proibidos = ("hidraw-broker", "bt-agent", "bt-health-watchdog",
                 "bt-bonds-snapshot", "udev")
    for linha in linhas_de_acao:
        # `systemctl is-active` (leitura) sobre o broker é permitido: é o
        # retrato. O que não pode é AGIR sobre ele.
        if "is-active" in linha:
            continue
        for proibido in proibidos:
            assert proibido not in linha, linha


def test_a_chave_nao_mata_por_pgrep():
    """`pgrep -f hefesto` alcançaria o OUTRO Hefesto — e este próprio script.

    O pid file é a única forma de mirar um processo desta casa e só dele.
    """
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    acoes = [
        linha for linha in script.splitlines()
        if not linha.lstrip().startswith("#")
    ]
    assert not any("pgrep" in linha for linha in acoes)
    assert not any("pkill" in linha for linha in acoes)
    assert ".pid" in script


def test_o_script_e_o_produto_concordam_no_nome_do_arquivo():
    """Um escritor (o script, em bash) e um leitor (o produto, em Python).

    Duas linguagens, um nome de arquivo — e nada obriga os dois a concordar.
    Troque uma letra de `chave.NOME_DO_ARQUIVO` ou do script e este teste
    reprova: sem ele, `hefesto-chave estavel off` escreveria um arquivo que o
    daemon nunca leria, e a chave diria "desliguei" sem ter desligado.
    """
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    assert chave.NOME_DO_ARQUIVO in script
    assert script.count(chave.NOME_DO_ARQUIVO) >= 3  # estado, off e on
