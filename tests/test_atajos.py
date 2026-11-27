# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.atajos`` (lógica pura)."""

import pytest

from vislumbra import atajos
from vislumbra.atajos import ACCION, PERFIL, Atajos, Combinacion, ErrorAtajo, combinacion, parsear


# --- Combinaciones -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("texto, canonico, mostrado", [
    ("Ctrl+Alt+P", "Ctrl+Alt+P", "Ctrl+Alt+P"),
    ("ctrl+alt+shift+p", "Ctrl+Alt+Shift+P", "Ctrl+Alt+Mayús+P"),
    ("Mayús+Ctrl+Alt+V", "Ctrl+Alt+Shift+V", "Ctrl+Alt+Mayús+V"),
    ("MAYUS+CONTROL+1", "Ctrl+Shift+1", "Ctrl+Mayús+1"),
    ("Win+Alt+F5", "Alt+Win+F5", "Alt+Win+F5"),
    ("Ctrl+Alt+RePág", "Ctrl+Alt+PageUp", "Ctrl+Alt+RePág"),
    ("Ctrl+Alt+Supr", "Ctrl+Alt+Delete", "Ctrl+Alt+Supr"),
    ("Ctrl+Alt+Left", "Ctrl+Alt+Left", "Ctrl+Alt+←"),
    ("F13", "F13", "F13"), ("Pausa", "Pause", "Pausa"), ("  Ctrl + Alt + 0  ", "Ctrl+Alt+0", "Ctrl+Alt+0"),
])
def test_lectura_tolerante_y_texto_canonico(texto, canonico, mostrado):
    c = parsear(texto)
    assert c.texto() == canonico and c.mostrar() == mostrado
    assert parsear(c.texto()) == c and parsear(c.mostrar()) == c  # ida y vuelta, también con el texto en español


def test_el_orden_de_los_modificadores_no_importa():
    assert parsear("Alt+Ctrl+P") == parsear("Ctrl+Alt+P") == combinacion({"Alt", "Ctrl"}, "P")


@pytest.mark.parametrize("texto", ["", "   ", "+", "Ctrl+", "Ctrl+Alt+", "Ctrl+Alt+ñ", "Ctrl+Alt+Escape", "Cosa+P", "Ctrl+Alt+PP", "P", "Shift+P", "F1", "Ctrl++"])
def test_combinaciones_no_validas_se_rechazan(texto):
    with pytest.raises(ErrorAtajo):
        parsear(texto)


def test_mayus_sola_no_vale_y_el_mensaje_lo_explica():
    with pytest.raises(ErrorAtajo, match="Mayús sola"):
        parsear("Shift+P")
    with pytest.raises(ErrorAtajo, match="Ctrl, Alt o Win"):
        parsear("P")


@pytest.mark.parametrize("texto", [f"F{n}" for n in range(13, 25)] + ["Pause", "Shift+F13"])
def test_sin_modificador_valen_f13_a_f24_y_pausa(texto):
    assert parsear(texto)


def test_cada_tecla_admitida_tiene_su_codigo_de_windows():
    assert combinacion({"Ctrl"}, "A").vk == 0x41 and combinacion({"Ctrl"}, "0").vk == 0x30
    assert combinacion({"Ctrl"}, "F1").vk == 0x70 and combinacion({"Ctrl"}, "F24").vk == 0x87
    assert combinacion({"Ctrl"}, "Pause").vk == 0x13 and combinacion({"Ctrl"}, "Delete").vk == 0x2E
    assert atajos.tecla_de_vk(0x50) == "P" and atajos.tecla_de_vk(0x7C) == "F13" and atajos.tecla_de_vk(0x1B) is None


def test_banderas_de_modificadores_para_register_hotkey():
    assert parsear("Ctrl+Alt+P").banderas == 0x2 | 0x1
    assert parsear("Ctrl+Alt+Shift+Win+P").banderas == 0xF and parsear("F13").banderas == 0


def test_combinacion_con_datos_malos():
    with pytest.raises(ErrorAtajo):
        Combinacion(frozenset({"Ctrl"}), "Escape")
    with pytest.raises(ErrorAtajo):
        Combinacion(frozenset({"Hyper"}), "P")


# --- Atajos por defecto ----------------------------------------------------------------------------------------------
def test_los_valores_por_defecto_son_validos_y_no_se_repiten():
    a = Atajos.por_defecto()
    elementos = a.elementos()
    assert len({c for _, c in elementos}) == len(elementos)
    for _, c in elementos:
        c.validar()
    assert a.acciones["emergencia"].texto() == "Ctrl+Alt+0" and a.acciones["preciso"] is None
    assert set(a.acciones) == set(atajos.ACCIONES) and a.perfiles == {} and a.aviso == "ninguno"


def test_los_valores_por_defecto_no_usan_la_q():
    """Ctrl+Alt+Q escribe «@» con AltGr en algunos teclados: los atajos por defecto la evitan."""
    assert all(c.tecla != "Q" for _, c in Atajos.por_defecto().elementos())


# --- Asignar, quitar y duplicados ---------------------------------------------------------------------------------------
def test_asignar_y_quitar_una_accion():
    a = Atajos.por_defecto()
    a.asignar_accion("preciso", parsear("Ctrl+Alt+M"))
    assert a.acciones["preciso"].texto() == "Ctrl+Alt+M"
    a.asignar_accion("preciso", None)
    assert a.acciones["preciso"] is None


def test_un_atajo_repetido_da_error_con_el_nombre_de_quien_lo_usa():
    a = Atajos.por_defecto()
    with pytest.raises(ErrorAtajo, match="ya la usa «Siguiente perfil»"):
        a.asignar_accion("comparar", parsear("Ctrl+Alt+P"))
    a.asignar_perfil("Código", parsear("Ctrl+Alt+2"))
    with pytest.raises(ErrorAtajo, match="Perfil «Código»"):
        a.asignar_accion("preciso", parsear("Ctrl+Alt+2"))
    with pytest.raises(ErrorAtajo, match="Comparar"):
        a.asignar_perfil("Oscuro", parsear("Ctrl+Alt+B"))


def test_reasignar_la_misma_combinacion_a_la_misma_accion_no_es_un_duplicado():
    a = Atajos.por_defecto()
    a.asignar_accion("siguiente", parsear("Ctrl+Alt+P"))
    a.asignar_perfil("Normal", parsear("Ctrl+Alt+1"))
    a.asignar_perfil("Normal", parsear("Ctrl+Alt+1"))


def test_la_emergencia_se_puede_cambiar_pero_no_quitar():
    a = Atajos.por_defecto()
    with pytest.raises(ErrorAtajo, match="no quitar"):
        a.asignar_accion("emergencia", None)
    a.asignar_accion("emergencia", parsear("Ctrl+Alt+F12"))
    assert a.acciones["emergencia"].texto() == "Ctrl+Alt+F12"


def test_accion_desconocida_y_combinacion_no_valida_al_asignar():
    a = Atajos.por_defecto()
    with pytest.raises(ErrorAtajo, match="no existe"):
        a.asignar_accion("volar", parsear("Ctrl+Alt+J"))
    with pytest.raises(ErrorAtajo):
        a.asignar_accion("preciso", combinacion({"Shift"}, "P"))


def test_normal_admite_atajo_y_renombrar_o_borrar_un_perfil_lo_arrastra():
    a = Atajos.por_defecto()
    a.asignar_perfil("Normal", parsear("Ctrl+Alt+1"))
    a.asignar_perfil("Código", parsear("Ctrl+Alt+2"))
    a.renombrar_perfil("Código", "Programar")
    assert set(a.perfiles) == {"Normal", "Programar"} and a.perfiles["Programar"].texto() == "Ctrl+Alt+2"
    a.quitar_perfil("Programar")
    a.quitar_perfil("NoExiste")
    assert set(a.perfiles) == {"Normal"}


def test_restaurar_valores_por_defecto_no_toca_los_perfiles():
    a = Atajos.por_defecto()
    a.asignar_perfil("Código", parsear("Ctrl+Alt+2"))
    a.asignar_accion("siguiente", parsear("Ctrl+Alt+F9"))
    a.asignar_accion("preciso", parsear("Ctrl+Alt+M"))
    assert a.restaurar_defectos() == []
    assert a.acciones == Atajos.por_defecto().acciones and a.perfiles["Código"].texto() == "Ctrl+Alt+2"


def test_restaurar_avisa_si_un_perfil_usa_un_valor_por_defecto():
    a = Atajos.por_defecto()
    a.asignar_accion("siguiente", parsear("Ctrl+Alt+F9"))
    a.asignar_perfil("Código", parsear("Ctrl+Alt+P"))
    avisos = a.restaurar_defectos()
    assert len(avisos) == 1 and "Siguiente perfil" in avisos[0] and a.acciones["siguiente"] is None


def test_copia_independiente():
    a = Atajos.por_defecto()
    b = a.copia()
    b.asignar_accion("preciso", parsear("Ctrl+Alt+M"))
    assert a.acciones["preciso"] is None


# --- JSON ----------------------------------------------------------------------------------------------------------------------
def test_json_de_ida_y_vuelta():
    a = Atajos.por_defecto()
    a.asignar_accion("preciso", parsear("Ctrl+Alt+M"))
    a.asignar_accion("anterior", None)
    a.asignar_perfil("Código", parsear("Ctrl+Alt+2"))
    a.aviso = "sonido"
    b, avisos = Atajos.de_json(a.a_json())
    assert avisos == [] and b == a
    assert a.a_json()["acciones"]["siguiente"] == "Ctrl+Alt+P" and a.a_json()["acciones"]["anterior"] is None


def test_un_archivo_antiguo_sin_atajos_usa_los_valores_por_defecto():
    a, avisos = Atajos.de_json(None)
    assert avisos == [] and a == Atajos.por_defecto()


def test_accion_ausente_usa_su_valor_por_defecto_y_null_es_sin_atajo():
    a, avisos = Atajos.de_json({"acciones": {"comparar": None}})
    assert avisos == [] and a.acciones["comparar"] is None and a.acciones["siguiente"].texto() == "Ctrl+Alt+P"


def test_un_atajo_malo_se_descarta_solo_ese_y_se_avisa():
    a, avisos = Atajos.de_json({"acciones": {"siguiente": "Shift+P", "comparar": "Ctrl+Alt+J", "volar": "Ctrl+Alt+K", "activo": 5}})
    assert a.acciones["siguiente"] is None and a.acciones["activo"] is None
    assert a.acciones["comparar"].texto() == "Ctrl+Alt+J" and a.acciones["emergencia"].texto() == "Ctrl+Alt+0"
    assert len(avisos) == 3 and any("desconocida" in x for x in avisos) and any("Mayús sola" in x for x in avisos)


def test_un_atajo_repetido_se_descarta_el_segundo():
    a, avisos = Atajos.de_json({"acciones": {"siguiente": "Ctrl+Alt+J", "comparar": "ctrl+alt+j"}})
    assert a.acciones["siguiente"].texto() == "Ctrl+Alt+J" and a.acciones["comparar"] is None
    assert len(avisos) == 1 and "ya la usa «Siguiente perfil»" in avisos[0]


def test_la_emergencia_no_se_pierde_por_un_archivo_raro():
    for emergencia in (None, "basura", 7, "Shift+P"):
        a, avisos = Atajos.de_json({"acciones": {"emergencia": emergencia}})
        assert a.acciones["emergencia"].texto() == "Ctrl+Alt+0" and avisos


def test_un_valor_por_defecto_que_choca_con_otro_atajo_se_queda_sin_atajo():
    a, _ = Atajos.de_json({"acciones": {"siguiente": "Ctrl+Alt+B", "comparar": "Ctrl+Alt+J"}})
    assert a.acciones["siguiente"].texto() == "Ctrl+Alt+B" and a.acciones["comparar"].texto() == "Ctrl+Alt+J"
    b, _ = Atajos.de_json({"acciones": {"siguiente": "Ctrl+Alt+B", "comparar": None}})
    assert b.acciones["siguiente"].texto() == "Ctrl+Alt+B" and b.acciones["comparar"] is None


@pytest.mark.parametrize("datos", ["texto", 5, [], ["Ctrl+Alt+P"]])
def test_un_campo_atajos_ilegible_vuelve_a_los_valores_por_defecto(datos):
    a, avisos = Atajos.de_json(datos)
    assert a == Atajos.por_defecto() and len(avisos) == 1


def test_acciones_o_perfiles_con_formato_raro_no_rompen_nada():
    a, avisos = Atajos.de_json({"acciones": "no", "perfiles": ["no"], "aviso": 5})
    assert a.acciones == Atajos.por_defecto().acciones and a.perfiles == {} and a.aviso == "ninguno" and len(avisos) == 2


def test_los_perfiles_que_ya_no_existen_se_ignoran_y_los_nombres_se_normalizan():
    datos = {"perfiles": {"código": "Ctrl+Alt+2", "Borrado": "Ctrl+Alt+3", "Normal": "Ctrl+Alt+1"}}
    a, avisos = Atajos.de_json(datos, perfiles=["Normal", "Oscuro", "Código"])
    assert avisos == [] and {n: c.texto() for n, c in a.perfiles.items()} == {"Código": "Ctrl+Alt+2", "Normal": "Ctrl+Alt+1"}


def test_aviso_solo_admite_los_valores_conocidos():
    assert Atajos.de_json({"aviso": "notificacion"})[0].aviso == "notificacion"
    assert Atajos.de_json({"aviso": "gritar"})[0].aviso == "ninguno"


def test_las_claves_de_atajo_se_etiquetan_en_español():
    assert Atajos.etiqueta((ACCION, "siguiente")) == "Siguiente perfil"
    assert Atajos.etiqueta((PERFIL, "Código")) == "Perfil «Código»"
