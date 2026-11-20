"""Excedente al seleccionar un depósito desde Ver aplicaciones de una factura."""
import unittest
from datetime import date
from unittest.mock import patch

from flask import Flask

from app.core.database import db
from app.modules.conciliacion.models import (
    AplicacionPago, Cartola, CuentaBancaria, Factura, MovimientoBancario,
)
from app.modules.conciliacion.routes import bp
from app.modules.conciliacion.services.conciliacion_service import ConciliacionService


class ExcedenteManualTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        db.init_app(app)
        app.register_blueprint(bp, url_prefix="/api/conciliacion")
        self.contexto = app.app_context()
        self.contexto.push()
        db.create_all()
        self.client = app.test_client()
        cuenta = CuentaBancaria(banco="Prueba", numero_cuenta="123")
        db.session.add(cuenta)
        db.session.flush()
        cartola = Cartola(cuenta_id=cuenta.id, archivo_nombre="cartola.pdf", archivo_hash="cartola")
        db.session.add(cartola)
        db.session.flush()
        self.mov = MovimientoBancario(
            cartola_id=cartola.id, fecha=date(2026, 9, 30), descripcion_original="DEPÓSITO",
            monto=150000, pagina_origen=1, orden_en_pagina=1, huella_movimiento="mov",
        )
        db.session.add(self.mov)
        self.actual = self.crear_factura("1", 100000)
        self.otra = self.crear_factura("2", 80000)
        self.otro_receptor = self.crear_factura("3", 90000, rut="OTRO")
        self.en_revision = self.crear_factura("4", 90000, estado="requiere_revision")
        db.session.commit()
        # No se crean identidades tributarias ni asociaciones de depositantes.

    def crear_factura(self, folio, total, rut="RECEPTOR", estado="procesada"):
        factura = Factura(
            folio=folio, total=total, rut_receptor_normalizado=rut,
            archivo_nombre=f"{folio}.pdf", archivo_hash=folio, estado=estado,
        )
        db.session.add(factura)
        db.session.flush()
        return factura

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.contexto.pop()

    def aplicar(self, factura=None, monto=100000, llave="manual-1"):
        return self.client.post("/api/conciliacion/aplicaciones-pago", json={
            "movimiento_id": self.mov.id,
            "factura_id": (factura or self.actual).id,
            "monto_aplicado": monto,
            "llave_idempotencia": llave,
        })

    def test_manual_devuelve_sobrante_sin_asociacion_previa(self):
        respuesta = self.aplicar()
        self.assertEqual(respuesta.status_code, 200, respuesta.get_json())
        resultado = respuesta.get_json()
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["excedente"]["monto_disponible"], 50000)
        self.assertEqual(resultado["excedente"]["movimiento_id"], self.mov.id)
        self.assertEqual([f["factura_id"] for f in resultado["excedente"]["facturas_candidatas"]],
                         [self.otra.id])
        saldos = self.client.get(f"/api/conciliacion/facturas/{self.actual.id}/saldos").get_json()
        self.assertEqual(saldos["saldo_pendiente"], 0)
        repetida = self.aplicar().get_json()
        self.assertTrue(repetida["idempotente"])
        self.assertEqual(repetida["excedente"], resultado["excedente"])
        self.assertEqual(AplicacionPago.query.count(), 1)

    def test_aplicar_sobrante_actualiza_saldos_y_se_agota(self):
        self.assertEqual(self.aplicar().status_code, 200)
        respuesta = self.aplicar(self.otra, monto=50000, llave="manual-2")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.get_json()["excedente"])
        saldos = self.client.get(f"/api/conciliacion/facturas/{self.otra.id}/saldos").get_json()
        self.assertEqual(saldos["saldo_pendiente"], 30000)
        self.assertEqual(AplicacionPago.query.count(), 2)

    def test_informa_sobrante_aunque_no_haya_otras_facturas_pendientes(self):
        self.otra.estado = "requiere_revision"
        db.session.commit()
        respuesta = self.aplicar()
        self.assertEqual(respuesta.status_code, 200)
        excedente = respuesta.get_json()["excedente"]
        self.assertEqual(excedente["monto_disponible"], 50000)
        self.assertEqual(excedente["facturas_candidatas"], [])

    def test_receptor_desconocido_no_ofrece_facturas_de_otro_receptor(self):
        self.actual.rut_receptor_normalizado = None
        self.otra.rut_receptor_normalizado = None
        db.session.commit()
        respuesta = self.aplicar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json()["excedente"]["facturas_candidatas"], [])

    def test_recupera_excedente_al_reabrir_sin_repetir_el_pago(self):
        self.assertEqual(self.aplicar().status_code, 200)
        url = f"/api/conciliacion/facturas/{self.actual.id}/excedentes"
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        items = respuesta.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["monto_disponible"], 50000)
        self.assertEqual(items[0]["facturas_candidatas"][0]["factura_id"], self.otra.id)
        self.assertEqual(AplicacionPago.query.count(), 1)
        self.assertEqual(self.aplicar(self.otra, 50000, "saldo-final").status_code, 200)
        self.assertEqual(self.client.get(url).get_json()["items"], [])

    def test_recuperacion_no_incluye_aplicaciones_revertidas(self):
        respuesta = self.aplicar().get_json()
        self.client.post(f"/api/conciliacion/aplicaciones-pago/{respuesta['aplicacion_id']}/revertir")
        items = self.client.get(f"/api/conciliacion/facturas/{self.actual.id}/excedentes").get_json()["items"]
        self.assertEqual(items, [])

    def test_recuperacion_de_factura_inexistente_devuelve_404(self):
        respuesta = self.client.get("/api/conciliacion/facturas/inexistente/excedentes")
        self.assertEqual(respuesta.status_code, 404)

    def test_error_de_calculo_no_deja_un_pago_guardado(self):
        with patch.object(ConciliacionService, "_calcular_excedente", side_effect=RuntimeError("falló cálculo")):
            respuesta = self.aplicar()
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(AplicacionPago.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
