"""La reimportación repara extracciones pendientes sin duplicar facturas."""
import hashlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from app.core.database import db
from app.modules.conciliacion.models import Factura, DetalleFactura
from app.modules.conciliacion.parsers.base_factura_parser import ParsedFactura
from app.modules.conciliacion.repositories.factura_repository import FacturaRepository
from app.modules.conciliacion.routes import bp
from app.modules.conciliacion.utils.ocr import tesseract_disponible


class FacturaReimportacionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        db.init_app(self.app)
        self.app.register_blueprint(bp, url_prefix="/api/conciliacion")
        self.contexto = self.app.app_context()
        self.contexto.push()
        db.create_all()
        self.client = self.app.test_client()
        self.pdf = Path(__file__).resolve().parents[2] / "data" / "F_1541 Local 13-14.pdf"
        self.data = self.pdf.read_bytes()
        repo = FacturaRepository()
        origen = repo.create_importacion(archivos_recibidos=1)
        factura = repo.create_factura(
            importacion_id=origen.id, folio="1541", tipo_documento="FACTURA_ELECTRONICA",
            rut_emisor="76440385-1", rut_emisor_normalizado="76440385-1",
            archivo_nombre=self.pdf.name, archivo_hash=hashlib.sha256(self.data).hexdigest(),
            estado="requiere_revision", validacion_ok=False,
            iva=564206, total=3533710, neto=None,
            validacion_mensaje="Faltan campos de totales (neto, IVA o total).",
        )
        # Una extracción parcial previa debe reemplazarse, sin acumular líneas.
        repo.create_detalle(factura.id, codigo="PARCIAL", total_linea=1)
        repo.commit()
        self.factura_id = factura.id
        self.created_at = factura.created_at
        self.importacion_id = factura.importacion_id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.contexto.pop()

    def importar(self):
        respuesta = self.client.post("/api/conciliacion/facturas/import", data={
            "files[]": (io.BytesIO(self.data), self.pdf.name),
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.get_json())
        return respuesta.get_json()

    @unittest.skipUnless(tesseract_disponible(), "Requiere Tesseract")
    def test_post_repara_factura_y_siguiente_post_es_duplicado(self):
        resultado = self.importar()
        self.assertEqual(resultado["facturas_validas"], 1)
        self.assertEqual(resultado["facturas_duplicadas"], 0)
        self.assertEqual(resultado["facturas_con_error"], 0)
        factura = self.client.get(
            f"/api/conciliacion/facturas/{self.factura_id}"
        ).get_json()
        self.assertEqual(factura["id"], self.factura_id)
        self.assertEqual(factura["estado"], "procesada")
        self.assertTrue(factura["validacion_ok"])
        self.assertEqual(factura["neto"], 2969504)
        self.assertEqual(factura["exento"], 0)
        self.assertEqual([d["total_linea"] for d in factura["detalles"]], [2861256, 108248])
        guardada = db.session.get(Factura, self.factura_id)
        self.assertEqual(guardada.created_at, self.created_at)
        self.assertEqual(guardada.importacion_id, self.importacion_id)
        self.assertEqual(Factura.query.count(), 1)
        self.assertEqual(DetalleFactura.query.count(), 2)
        with patch("app.modules.conciliacion.services.factura_service.FacturaChileParser.parse") as parse:
            repetido = self.importar()
            parse.assert_not_called()
        self.assertEqual(repetido["facturas_duplicadas"], 1)
        self.assertEqual(repetido["facturas_validas"], 0)
        self.assertEqual(Factura.query.count(), 1)
        self.assertEqual(DetalleFactura.query.count(), 2)

    @unittest.skipUnless(tesseract_disponible(), "Requiere Tesseract")
    def test_importa_exenta_enerfit_con_detalle_y_precio_decimal(self):
        pdf = self.pdf.with_name("FEX 80 Enerfit.pdf")
        self.data = pdf.read_bytes()
        self.pdf = pdf
        resultado = self.importar()
        self.assertEqual(resultado["facturas_validas"], 1)
        factura = Factura.query.filter_by(folio="80").one()
        self.assertEqual(factura.tipo_documento, "FACTURA_EXENTA_ELECTRONICA")
        self.assertEqual(factura.rut_emisor, "76440385-1")
        self.assertEqual(factura.rut_receptor, "76508234-K")
        self.assertEqual(factura.razon_social_emisor,
                         "CONSTRUCTORA INMOBILIARIA E INVERSIONES PAICAVI URBANO LIMITADA")
        self.assertEqual(factura.razon_social_receptor, "COMERCIAL ENERFIT LIMITADA")
        self.assertEqual((factura.neto, factura.exento, factura.iva, factura.total),
                         (0, 940127, 0, 940127))
        self.assertEqual(factura.estado, "procesada")
        self.assertTrue(factura.validacion_ok)
        detalle = self.client.get(
            f"/api/conciliacion/facturas/{factura.id}"
        ).get_json()["detalles"]
        self.assertEqual(len(detalle), 1)
        self.assertEqual(detalle[0]["codigo"], "Rol 144-42")
        self.assertEqual(detalle[0]["descripcion"], "Inmueble San Martin 1321 Interior")
        self.assertEqual(detalle[0]["cantidad"], 23)
        self.assertEqual(detalle[0]["unidad"], "UF")
        self.assertEqual(detalle[0]["precio_unitario"], 40875.09)
        self.assertEqual(detalle[0]["total_linea"], 940127)

    def test_extraccion_invalida_conserva_datos_anteriores(self):
        parsed = ParsedFactura(folio="1541", rut_emisor="76440385-1", neto=100, iva=19, total=999)
        with patch("app.modules.conciliacion.services.factura_service.FacturaChileParser.parse", return_value=parsed):
            resultado = self.importar()
        self.assertEqual(resultado["facturas_con_error"], 1)
        self.assertEqual(resultado["facturas_validas"], 0)
        factura = db.session.get(Factura, self.factura_id)
        self.assertIsNone(factura.neto)
        self.assertEqual(factura.total, 3533710)
        self.assertEqual(factura.estado, "requiere_revision")
        self.assertEqual([d.codigo for d in factura.detalles], ["PARCIAL"])
        self.assertEqual(Factura.query.count(), 1)

    def test_error_de_ocr_conserva_factura(self):
        with patch("app.modules.conciliacion.services.factura_service.FacturaChileParser.parse",
                   return_value=ParsedFactura(errores=["No se pudo extraer texto."])):
            resultado = self.importar()
        self.assertEqual(resultado["facturas_con_error"], 1)
        self.assertEqual(db.session.get(Factura, self.factura_id).estado, "requiere_revision")
        self.assertEqual(DetalleFactura.query.count(), 1)

    def test_cambio_de_identidad_no_sobrescribe_factura(self):
        parsed = ParsedFactura(folio="9999", rut_emisor="76440385-1", neto=100, iva=19, total=119)
        with patch("app.modules.conciliacion.services.factura_service.FacturaChileParser.parse", return_value=parsed):
            resultado = self.importar()
        self.assertEqual(resultado["facturas_con_error"], 1)
        self.assertEqual(db.session.get(Factura, self.factura_id).folio, "1541")
        self.assertEqual(Factura.query.count(), 1)
        self.assertEqual(DetalleFactura.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
