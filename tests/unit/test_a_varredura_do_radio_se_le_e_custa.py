"""A varredura se LÊ do BlueZ, muda o destino da ordem, e o doctor diz o preço.

RESERVA-DO-RADIO-01, 20/09/2026. A sprint queria RESERVAR um adaptador para os
controles. A medição de 20/09 derrubou a premissa — *"a varredura é do adaptador
que a PESSOA ABRE"* — e a cura que sobrou não adivinha: ela pergunta o
`Discovering` ao `org.bluez.Adapter1`.

Este arquivo prende as três peças da cura, e o barramento é de MENTIRA de
propósito: abrir varredura de verdade na máquina dela custa de 32,5% a 43,4% dos
pacotes do adaptador, com quatro DualSense de pé.

O BARRAMENTO DE MENTIRA É `busctl`, NÃO UM DUBLÊ DE FUNÇÃO
-----------------------------------------------------------
`tests/unit/barramento_de_mentira.py` põe um `busctl` de shell na frente do
`PATH`. A régua exercita o subprocesso, a saída crua (`b true`, `s "AC:…"`) e a
peneira de forma — o caminho inteiro do produto. Um dublê que devolvesse
`{"hci0": True}` seria mais frouxo que o produto e esconderia exatamente o que
mais quebra aqui: o parsing e o casamento de caixa do endereço.

AS NOVE MORDIDAS, arrancadas e conferidas em 20/09/2026
--------------------------------------------------------
1. **Trocar o endereço por `hciN`** em `quem_esta_varrendo` (pôr
   `varrendo.add(hci)` no lugar de `varrendo.add(endereco)`): reprova
   `test_o_leitor_responde_pelo_endereco_e_nunca_pelo_hci_n` **e**
   `test_o_oraculo_a_varredura_muda_o_destino_da_ordem` — o `hciN` é a VAGA,
   não o aparelho, e ele inverte entre boots. O filtro do motor compara com o
   `HID_PHYS`, que é MAC: um filtro por `hciN` nunca casa, e um filtro que não
   casa fica VERDE e MUDO enquanto a pessoa perde 43% dos pacotes.
2. **Devolver `Varredura()` no lugar de `Varredura(motivo=SEM_BUSCTL)`**:
   reprova `test_sem_busctl_a_resposta_e_nao_sei_e_nunca_nenhum`. É a assinatura
   das dez réguas que caíram em 20/09 — `set()` vazio querendo dizer as duas
   coisas opostas.
3. **Somar o adaptador que diz `Discovering=true` sem dizer `Address`** (pôr
   `hci` em `varrendo` em vez de `mudos`): reprova
   `test_quem_varre_sem_endereco_legivel_nao_entra_como_varrendo` com um
   `varrendo` que contém `hci7` — chave que plano nenhum reivindica.
4. **Ler `Discovering` ausente como `false`** (`continue` no lugar de
   `mudos.add(hci)`): reprova `test_adaptador_mudo_nao_e_adaptador_parado`.
5. **Trocar o "fim da fila" por EXCLUSÃO** em `ordem_de_redistribuicao` (filtrar
   `p.endereco not in em_busca` em vez de ordenar por isso): reprova
   `test_o_unico_destino_possivel_continua_valendo_mesmo_varrendo` com
   `ordem is None` — a máquina de dois adaptadores fica MUDA exatamente onde a
   perda é maior, e calar não é conselho.
6. **Arrancar a chave de ordenação** (voltar a `key=lambda p:
   p.agora.fracao_total`): reprova
   `test_o_destino_que_varre_desce_para_o_fim_da_fila` e o oráculo — o motor
   volta a mandar o controle para o adaptador que varre.

E AS TRÊS QUE SOBRAM
--------------------
7. **Mexer em `QUEDA_MINIMA_MEDIDA`/`QUEDA_MAXIMA_MEDIDA` sem mexer no
   `doctor.sh`**: reprova `test_o_doctor_cita_os_numeros_do_dono`. Os dois
   números viviam como PROSA em cinco arquivos e não tinham dono; agora têm um,
   e esta régua é o que impede a segunda grafia de nascer.
8. **Trocar o corpo de `varredura_recente` por `quem_esta_varrendo()`**:
   reprova `test_a_lembranca_poupa_o_barramento_dentro_da_validade` — a
   thread do GTK volta a abrir subprocesso a cada pintura, que é a forma do
   travamento de 15/09/2026.
9. As duas da FIAÇÃO moram em
   `tests/unit/test_a_conta_de_slots_por_adaptador.py`, bloco 9: a seção
   passando a varredura ao motor, e a guarda que impede a suíte de abrir
   sete processos contra o `bluetoothd` DELA.

AS DUAS QUE A CONFERÊNCIA ADVERSARIAL ACRESCENTOU (20/09/2026)
---------------------------------------------------------------
As nove acima foram arrancadas uma a uma e as nove reprovaram. O que elas não
cobriam apareceu ao pôr um `busctl` que NÃO RESPONDE na frente do `PATH` — o
barramento travado, que é o caso que a lembrança de 3 s não alcança:

10. **Arrancar o `ORCAMENTO_DA_LEITURA`** (devolver o padrão de 5,0 s a
    `_rodar`): reprova `test_o_barramento_travado_nao_segura_a_thread_do_desenho`.
    MEDIDO: com três adaptadores e o `busctl` travado a leitura segurava a
    thread por **15,1 s** — e quem a chama é `_aplicar_estado`, que o
    `ipc_bridge.call_async` reposta por `GLib.idle_add`, ou seja, a thread do
    DESENHO. A lembrança segurava a frequência e não a duração: é o travamento
    de 15/09/2026 escrito de novo, com o rádio no caminho da pintura.
11. **Arrancar o `MESA_TODA_MUDA`**: reprova
    `test_a_mesa_toda_muda_nao_e_uma_mesa_parada`. Com o barramento travado a
    leitura voltava com `sei=True` e `varrendo` vazio — o `set()` ambíguo que
    este módulo existe para matar, entrando pela porta dos fundos: ninguém foi
    ouvido, e a resposta dizia "ninguém varre".
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus, varredura_do_radio
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    PALAVRAS_DE_CULPA,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR = (REPO_ROOT / "scripts" / "doctor.sh").read_text(encoding="utf-8")

P1 = "aa:bb:cc:00:00:11"
P2 = "aa:bb:cc:00:00:22"
P3 = "aa:bb:cc:00:00:33"
P4 = "aa:bb:cc:00:00:44"
P5 = "aa:bb:cc:00:00:55"
P6 = "aa:bb:cc:00:00:66"
P7 = "aa:bb:cc:00:00:77"
P8 = "aa:bb:cc:00:00:88"


def _sem_dois_pontos(mac: str) -> str:
    """Como o `uniq` do estado do daemon chega: 12 hex, sem separador."""
    return mac.replace(":", "")


def _bancada(mapa: dict[str, str]) -> dict[str, Any]:
    """Um `/sys/class/hidraw` de mentira: `{uniq do controle: MAC do adaptador}`.

    Mesma forma de `test_a_conta_de_slots_por_adaptador._bancada`. Sem ela o
    teste mediria a bancada de quem o roda — e quem o roda é a mesa DELA, com
    quatro DualSense de pé.
    """
    nos = {f"hidraw{i}": (uniq, phys) for i, (uniq, phys) in enumerate(mapa.items())}
    textos = {
        f"/sys/class/hidraw/{no}/device/uevent": f"HID_UNIQ={uniq}\nHID_PHYS={phys}\n"
        for no, (uniq, phys) in nos.items()
    }
    return {
        "listar": lambda _raiz: sorted(nos),
        "ler": lambda caminho: textos.get(caminho, ""),
    }


def _controle(uniq: str, slot: int | None = None, *, ponte: str | None = None) -> dict[str, Any]:
    """Um controle no rádio. ``ponte`` é a ponte de som/vibração DELE de pé —"""
    return {
        "transport": "bt",
        "connected": True,
        "uniq": _sem_dois_pontos(uniq),
        "player_slot": slot,
        "ponte_do_radio": ponte,
    }


def test_sem_busctl_a_resposta_e_nao_sei_e_nunca_nenhum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 2. Sem ferramenta para perguntar, a resposta é "não sei"."""
    vazio = tmp_path / "path-sem-busctl"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))
    assert shutil.which("busctl") is None, "o cenário precisa de um PATH sem busctl"

    leitura = varredura_do_radio.quem_esta_varrendo()

    assert not leitura.sei
    assert leitura.motivo == varredura_do_radio.SEM_BUSCTL
    assert leitura.varrendo == frozenset()
    assert "não" in leitura.motivo, "a ausência tem de se declarar em português"


def test_o_doctor_cita_os_numeros_do_dono() -> None:
    """MORDIDA 7. Mexer na constante sem mexer no `doctor.sh` reprova aqui."""
    minimo = varredura_do_radio.QUEDA_MINIMA_MEDIDA
    maximo = varredura_do_radio.QUEDA_MAXIMA_MEDIDA
    esperado_min = f"{minimo:.1f}".replace(".", ",")
    esperado_max = f"{maximo:.1f}".replace(".", ",")

    bloco = DOCTOR.split("Discovering: yes")[1][:900]
    assert f"{esperado_min}%" in bloco, (
        f"o doctor não cita a queda mínima medida ({esperado_min}%) — o número "
        "tem dono em varredura_do_radio.QUEDA_MINIMA_MEDIDA"
    )
    assert f"{esperado_max}%" in bloco


def test_o_aviso_do_doctor_diz_o_custo_e_nao_so_o_estado() -> None:
    """O que a sprint pediu: o aviso já estava no lugar certo e calava o preço."""
    bloco = DOCTOR.split("Discovering: yes")[1][:900]
    assert "MEDIDO" in bloco
    assert "NESTE adaptador" in bloco
    assert "21 s" in bloco, "a cauda de 21 s é o que impede o aviso de parecer falso"


def test_o_aviso_do_doctor_nao_culpa_ninguem() -> None:
    """Nenhuma palavra de culpa no texto que CHEGA a ela."""
    bloco = DOCTOR.split("Discovering: yes")[1][:900].lower()
    for palavra in PALAVRAS_DE_CULPA:
        assert palavra not in bloco, f"«{palavra}» culpa alguém pelo rádio ocupado"


def test_o_leitor_nao_toca_no_radio_de_ninguem(tmp_path: Path) -> None:
    """Ler é tudo o que se pode fazer daqui, e o fonte tem de dizer isso."""
    fonte = Path(varredura_do_radio.__file__).read_text(encoding="utf-8")
    corpo = fonte.split('"""', 2)[2]
    for verbo in ("StartDiscovery", "StopDiscovery", "set-property", "Powered"):
        assert verbo not in corpo, f"o leitor não pode chamar {verbo}"
    for escrita in bluez_dbus.ESCRITAS:
        assert f".{escrita}(" not in corpo, f"o leitor não pode chamar {escrita}"
    assert ".propriedade(" in corpo


def _busctl_que_trava(tmp_path: Path, quantos: int) -> Path:
    """Um `busctl` que LISTA a mesa e depois não responde mais nada."""
    raiz = tmp_path / "barramento-travado"
    (raiz / "bin").mkdir(parents=True)
    nos = "".join(f"/org/bluez/hci{i}\n" for i in range(quantos))
    alvo = raiz / "bin" / "busctl"
    alvo.write_text(
        "#!/usr/bin/env bash\n"
        'case "${1:-}" in\n'
        f"  tree) printf '/org/bluez\\n{nos}'; exit 0 ;;\n"
        "  get-property) sleep 600 ;;\n"
        "esac\n"
        "exit 1\n",
        encoding="utf-8",
    )
    alvo.chmod(0o755)
    return raiz


def test_o_barramento_travado_nao_segura_a_thread_do_desenho(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 10. O orçamento da leitura, e ele é a thread do DESENHO que paga.

    `varredura_recente` é chamada de `_ContaDeSlots._aplicar_estado`, que o
    `ipc_bridge.call_async` reposta por `GLib.idle_add` — thread principal do
    GTK, a mesma que pinta. MEDIDO em 20/09/2026 com este mesmo cenário e o
    padrão de 5,0 s por pergunta: **15,1 s de janela presa**, três adaptadores,
    uma pergunta travada em cada.

    A lembrança de 3 s não alcança isso: ela segura quantas vezes se pergunta,
    não quanto tempo cada pergunta dura.

    TRÊS adaptadores de propósito — é a mesa dela, e é onde o defeito é maior.
    Com um só, um padrão de 5 s daria 5 s e o mesmo limite pegaria; com três,
    o arranjo difícil mostra que o corte é do ORÇAMENTO INTEIRO e não de uma
    pergunta.
    """
    raiz = _busctl_que_trava(tmp_path, 3)
    monkeypatch.setenv("PATH", f"{raiz / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")

    inicio = time.monotonic()
    leitura = varredura_do_radio.quem_esta_varrendo()
    custou = time.monotonic() - inicio

    assert custou < 2.0, (
        f"o barramento travado segurou a thread do desenho por {custou:.1f} s "
        f"— o orçamento é de {varredura_do_radio.ORCAMENTO_DA_LEITURA} s"
    )
    assert not leitura.sei, "leitura interrompida não pode dizer «ninguém varre»"
    assert leitura.motivo == varredura_do_radio.SEM_RESPOSTA_A_TEMPO
    assert leitura.varrendo == frozenset()


