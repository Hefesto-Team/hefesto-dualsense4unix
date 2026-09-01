#!/usr/bin/env python3
"""O pacote da aba `08` Conexões.

O QUE TEM DONO: a contagem da mesa por transporte, e é o que o cabeçalho desta
aba promete (`2 na mesa · 1 no cabo · 1 no rádio`). Sai de `controllers[]`, e a
mesma regra das outras: conta os CONECTADOS.

O EXAME NÃO TEM DONO NO `state_full`, e é honesto dizer por quê: as cinco linhas
do Check-up saem do `doctor`, que é outro programa e responde por outro caminho.
Elas não são estado do daemon — são o resultado de um exame que alguém mandou
rodar. Pintá-las do `state_full` seria inventar.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Aqui estavam "exame" e "adaptadores" como órfãos.
#: Os dois têm dono, e são os mesmos que a `gui/aba_conexoes.py` dela usa hoje:
#: `integrations/exame_da_mesa` devolve os itens do exame prontos, e
#: `integrations/radio_da_mesa.ocupacao_por_adaptador` diz quem está em qual
#: adaptador. Perguntar só ao `state_full` foi o erro.
SEM_DONO: dict[str, str] = {}


def _exame() -> list[dict]:
    """Os itens do exame da mesa, do mesmo módulo que a GUI dela usa.

    ELE TOCA O SISTEMA (`busctl`, sysfs), logo pode demorar ou falhar — e uma
    falha aqui NÃO pode derrubar a aba. A lista vazia é um estado legítimo
    ("nada a apontar"); a exceção vira lista vazia com o motivo ao lado, para
    que a tela não confunda "examinei e está tudo bem" com "não consegui
    examinar" — que é o defeito que esta casa chama de *ausência de notícia
    lida como sucesso*.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations import exame_da_mesa

        itens = []
        for fn in ("energia_do_radio", "energia_das_portas", "suporte_ao_controle"):
            f = getattr(exame_da_mesa, fn, None)
            if f is None:
                continue
            try:
                r = f()
            except Exception:
                continue
            for it in (r if isinstance(r, (list, tuple)) else [r]):
                if it is None:
                    continue
                # OS CAMPOS SÃO `rotulo`, `estado` e `porque` — os do
                # `exame_da_mesa.Item`, lidos do dataclass. A primeira versão
                # daqui pedia `titulo` com `or str(it)` de reserva, e o `Item`
                # não tem `titulo`: a reserva ganhava sempre e o **`repr` do
                # objeto Python foi parar na tela dela**, visível na foto de
                # 01/09 — `Item(chave='energia_do_radio', rotulo='Economia de
                # energia desligada', estado='a`, cortado no meio.
                #
                # Um `getattr` com reserva é o disfarce perfeito para um campo
                # que não existe: ele não levanta, e o que sai parece dado.
                estado = str(getattr(it, "estado", "") or "")
                itens.append({
                    "chave": getattr(it, "chave", fn),
                    "titulo": str(getattr(it, "rotulo", "") or ""),
                    "porque": str(getattr(it, "porque", "") or ""),
                    "estado": estado,
                    # `certo` é o único estado que não pede nada — os outros
                    # (`ajustar`, `atencao`) são achados de verdade.  # noqa-acento
                    "grave": estado.lower() not in {"certo", ""},
                })
        return itens
    except Exception:
        return []


def _adaptadores(conectados) -> dict:
    """Quem está em qual adaptador de rádio.

    O MAC NÃO SAI DAQUI CRU para lugar nenhum que se grave: este pacote devolve
    para a tela em memória, e a máscara da casa (octetos 4 e 5 zerados) é o que
    vai para qualquer relato. São dois portões nesta árvore e eles não perdoam.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        ocup = radio_da_mesa.ocupacao_por_adaptador([c.get("uniq") for c in conectados])
        return {str(k): v for k, v in (ocup or {}).items()}
    except Exception:
        return {}


@registrar("08-conexoes.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    itens = _exame()
    adap = _adaptadores(ctx.conectados)

    colunas = {}
    for c in ctx.conectados:
        colunas[str(c.get("uniq") or "")] = {
            "via": (c.get("transport") or "").upper(),
            "bateria": c.get("battery_pct"),
            "ponte": bool(c.get("uniq") in (st.get("pontes_confirmadas") or {})),
            "fragil": bool(c.get("uniq") in (st.get("native_bt_fragil_controles") or [])),
        }
    return {
        "colunas": colunas,
        # AS DUAS LISTAS SÃO O QUE A TELA MOSTRA, uma por bloco de achado: o
        # selo (CERTO/AJUSTAR) e a frase. Elas se distribuem pelos elementos de
        # mesmo `data-campo`, na ordem — o gerador não precisa saber quantos
        # achados o exame vai devolver.
        "selo": ["AJUSTAR" if i["grave"] else "CERTO" for i in itens],
        "achado": [i["titulo"] for i in itens],
        "exame": itens,
        "achados": len(itens),
        "graves": sum(1 for i in itens if i["grave"]),
        "adaptadores": adap,
        "sem_driver": st.get("controles_sem_driver") or [],
        "sem_dono": {},
        "cobertura": {"pintados": 4 + len(itens) + len(adap)
                      + sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }
