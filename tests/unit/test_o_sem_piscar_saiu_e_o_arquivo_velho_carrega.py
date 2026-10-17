"""O «Sem piscar» saiu da tela e do produto, e o `maquina.json` que o tinha ligado carrega
(AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01, item I2, 16/10/2026).

O usuário pediu: *«aquele sem piscar some da tela. Já existe o efeito Luz fixa. não devemos ter um
botão ali pra isso»*. O interruptor era global (`maquina.json`, chave `luz.sem_piscar`) e, ligado,
segurava todo efeito a uma subida por segundo. Tirar só o botão deixaria quem o ligou preso no
modo suave sem jeito de desligar; por isso ele sai inteiro: o desenho, o gesto, o campo do
caderno e o parâmetro do motor. A chave velha no disco é descartada pela migração, e o efeito
volta ao teto de três subidas por segundo (WCAG 2.3.1), que vale para todos desde 15/10.

O lar é de mentira: o `conftest` desvia `HOME` e os `XDG_*`, e o `maquina.json` escrito aqui
mora nele.

MORDIDAS (feitas à mão, 16/10/2026): tirar o `documento.pop("luz", None)` de
`migrar_o_documento` reprova `test_a_migracao_descarta_a_chave_velha` e a gravação; devolver o
parâmetro `sem_piscar` a `cor_no_instante` reprova `test_o_motor_nao_tem_mais_o_modo_suave`.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import re

from hefesto_dualsense4unix.daemon.subsystems import luz_animada
from hefesto_dualsense4unix.interface import onde, pacotes
from hefesto_dualsense4unix.profiles import efeitos_de_luz, schema
from hefesto_dualsense4unix.utils import maquina

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
PAGINA = "04-iluminacao.html"

DOCUMENTO_VELHO = {
    "version": 1,
    "luz": {"sem_piscar": True},
    "mesa": {"altura_da_antena": "acima"},
}


def test_a_migracao_descarta_a_chave_velha() -> None:
    # D-1610-O-SEM-PISCAR-SAI
    migrado = maquina.migrar_o_documento(DOCUMENTO_VELHO)
    assert "luz" not in migrado, "a chave `luz` sobreviveu à migração"
    assert migrado["mesa"] == {"altura_da_antena": "acima"}, "a migração levou o vizinho junto"


def test_o_arquivo_velho_carrega_e_a_gravacao_tira_a_chave_do_disco() -> None:
    # D-1610-O-SEM-PISCAR-SAI
    caminho = maquina.caminho_da_maquina()
    caminho.write_text(json.dumps(DOCUMENTO_VELHO), encoding="utf-8")
    carregada = maquina.carregar_maquina()
    assert carregada.mesa.altura_da_antena == "acima", "o arquivo velho não carregou o que vale"
    assert not hasattr(carregada, "luz")
    assert maquina.gravar_maquina({"mesa": {"linha_de_visada": "livre"}})
    no_disco = json.loads(caminho.read_text(encoding="utf-8"))
    assert "luz" not in no_disco, "a gravação devolveu a chave velha ao disco"
    assert no_disco["mesa"] == {"altura_da_antena": "acima", "linha_de_visada": "livre"}


def test_a_tela_nao_tem_o_interruptor_nem_o_gesto() -> None:
    for caminho in (onde.pagina(PAGINA), onde.PUBLICADO / PAGINA):
        texto = caminho.read_text(encoding="utf-8")
        assert "Sem piscar" not in texto and "sem-piscar" not in texto, (
            f"o «Sem piscar» voltou a {caminho.parent.name}/{caminho.name}")
    assert pacotes.gesto_da_pagina(PAGINA, "sem-piscar") is None


def test_o_motor_nao_tem_mais_o_modo_suave() -> None:
    # D-1510-O-PISCAR-SEM-PISCAR-VIRA-RESPIRAR
    assert "sem_piscar" not in inspect.signature(efeitos_de_luz.cor_no_instante).parameters
    assert "sem_piscar" not in inspect.signature(luz_animada.LuzAnimada).parameters
    assert "luz" not in maquina.MaquinaConfig.model_fields
    for nome in ("sem_piscar_da_mesa", "sem_piscar_da_declaracao", "declaracao_do_sem_piscar"):
        assert not hasattr(schema, nome), f"`schema.{nome}` ficou sem quem o chame"


def test_nenhum_codigo_fala_do_sem_piscar() -> None:
    """Só a migração pode lembrar dele, e a conferência do gerador, que cobra a ausência."""
    # D-1510-O-SEM-PISCAR-E-DO-COMPUTADOR
    achados = []
    for arquivo in sorted(SRC.rglob("*")):
        if arquivo.suffix not in {".py", ".css", ".js"} or arquivo.name == "maquina.py":
            continue
        for linha in arquivo.read_text(encoding="utf-8", errors="replace").splitlines():
            if re.search(r"sem[_-]piscar|SEM_PISCAR", linha) and " not in " not in linha:
                achados.append(f"{arquivo.relative_to(RAIZ)}: {linha.strip()[:80]}")
    assert not achados, f"o «Sem piscar» ficou no código: {achados}"
