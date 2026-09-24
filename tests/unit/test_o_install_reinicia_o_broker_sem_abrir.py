"""O install troca o broker em memória sem abrir os nós — HIDE-SO-O-HIDRAW-02.

Medido em 24/09/2026: o `hefesto-hidraw-broker.service` rodava desde 22/09
com o código velho na memória. Dois installs seguidos copiaram o binário novo
para /usr/local/lib e nenhum reiniciou o serviço: a cura do broker (o Edge
fechado, a recusa do vpad pelas marcas) não valia. Quem coordena reiniciou à
mão, com a Steam fechada.

Um restart puro também não serve: o ExecStopPost (`--restore-all-and-exit`)
ABRE os nós, e a Steam aberta pega o físico nessa janela. A cura tem três
peças, e esta régua cobra as três e a ordem delas:

1. o marcador `reinicio-sem-abrir`, cujo caminho é o do broker (dono único);
2. o SIGKILL antes do restart, porque o processo velho não conhece o marcador;
3. o restart, e só depois o marcador sai.

E duas vizinhas: o `.service` habilitado no boot (sem ele o cabo do boot
nasce aberto até o daemon conectar), e a 72 pela variante aberta quando a
pessoa pede `--no-fechar-o-no` (com a 70 aberta e a 72 fechada o estado fica
incoerente).
"""
from __future__ import annotations

import pathlib
import re

from hefesto_dualsense4unix.broker import hidraw_broker

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts/lib/camada_de_maquina.sh"
UDEV = RAIZ / "scripts/install_udev.sh"
INSTALL = RAIZ / "install.sh"


def _corpo_da_funcao(texto: str, nome: str) -> str:
    inicio = texto.index(f"{nome}() {{")
    fim = texto.index("\n}\n", inicio)
    return texto[inicio:fim]


def _corpo() -> str:
    return _corpo_da_funcao(CAMADA.read_text(encoding="utf-8"), "install_broker_host")


def test_o_marcador_e_o_do_broker() -> None:
    """MORDIDA: troque o caminho do `_marca` — o binário novo não o acharia."""
    corpo = _corpo()
    achado = re.search(r"^\s*_marca=(\S+)$", corpo, re.M)
    assert achado, "o install não escreve o marcador do reinício que não abre"
    assert achado.group(1) == hidraw_broker.REINICIO_SEM_ABRIR_PATH


def test_a_ordem_marcador_sigkill_restart_e_so_depois_sai() -> None:
    """MORDIDA: tire o `kill -s SIGKILL` — o processo velho abriria os nós."""
    corpo = _corpo()
    passos = [
        'install -Dm0644 -o root -g root /dev/null "${_marca}"',
        "systemctl kill -s SIGKILL hefesto-hidraw-broker.service",
        "systemctl restart hefesto-hidraw-broker.service",
        'rm -f "${_marca}"',
    ]
    posicoes = []
    for passo in passos:
        assert passo in corpo, f"falta no install_broker_host: {passo}"
        posicoes.append(corpo.index(passo))
    assert posicoes == sorted(posicoes), "a ordem é marcador, SIGKILL, restart e só então o rm"


def test_o_service_nasce_habilitado_no_boot() -> None:
    """MORDIDA: tire o `enable` do .service — o cabo do boot nasce aberto."""
    assert "systemctl enable hefesto-hidraw-broker.service" in _corpo()


def test_o_broker_troca_antes_do_daemon_renascer() -> None:
    """O 3h (broker) roda antes do 7a (daemon): um daemon que renasce com o
    broker velho recebe `reject_bad_path` e fica cego."""
    texto = INSTALL.read_text(encoding="utf-8")
    chamada = texto.index("\n    install_broker_host\n")
    daemon = texto.index('systemctl --user restart "${DAEMON_UNIT_NAME}"')
    assert chamada < daemon


def test_o_opt_out_abre_a_72_junto_com_a_70() -> None:
    """MORDIDA: instale a 72 do asset nos dois ramos — o opt-out fica pela metade."""
    texto = UDEV.read_text(encoding="utf-8")
    ramo = texto[texto.index("# A 72 FECHA AS ENTRADAS DO FÍSICO"):]
    ramo = ramo[:ramo.index("\nfi\n")]
    aberto = ramo[ramo.index('if [[ "$ABRIR_O_NO" -eq 1 ]]; then'):ramo.index("\nelse\n")]
    assert "regra_do_no_aberta.sh" in aberto
    assert "72-hefesto-touchpad-motion-uaccess.rules" in aberto
