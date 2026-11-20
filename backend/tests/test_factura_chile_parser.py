"""Regresiones de importes y detalles de facturas, incluidas tablas escaneadas."""
import unittest
from datetime import date
from pathlib import Path

from app.modules.conciliacion.parsers.base_factura_parser import ParsedFactura
from app.modules.conciliacion.parsers.factura_chile_parser import FacturaChileParser
from app.modules.conciliacion.services.factura_service import FacturaService
from app.modules.conciliacion.utils.ocr import tesseract_disponible


class FacturaChileParserTest(unittest.TestCase):
    def setUp(self):
        self.parser = FacturaChileParser()

    @unittest.skipUnless(tesseract_disponible(), "Requiere Tesseract para el PDF escaneado")
    def test_factura_1541_escaneada_supera_validacion_de_importes(self):
        pdf = Path(__file__).resolve().parents[2] / "data" / "F_1541 Local 13-14.pdf"
        factura = self.parser.parse(pdf.read_bytes(), pdf.name)
        self.assertEqual(factura.errores, [])
        self.assertEqual(factura.metodo_extraccion, "ocr")
        self.assertEqual(factura.folio, "1541")
        self.assertEqual(factura.rut_emisor, "76440385-1")
        self.assertEqual(factura.rut_receptor, "78950790-2")
        self.assertEqual(factura.fecha_emision, date(2026, 9, 2))
        self.assertEqual(factura.fecha_vencimiento, date(2026, 9, 7))
        self.assertEqual((factura.neto, factura.exento, factura.iva, factura.total),
                         (2969504, 0, 564206, 3533710))
        self.assertEqual([
            (d.codigo, d.descripcion, d.cantidad, d.unidad,
             d.precio_unitario, d.total_linea) for d in factura.detalles
        ], [
            ("LOCAL 13-14", "Arriendo mensual", 1.0, "MES", 2861256, 2861256),
            ("GGCC", "GGCC Mensual", 1.0, "MES", 108248, 108248),
        ])
        # Usar la misma validación del servicio sin crear ni modificar registros.
        ok, mensaje = FacturaService._validar_importes(None, factura)
        self.assertTrue(ok, mensaje)

    def test_totales_por_etiqueta_admiten_cero(self):
        factura = ParsedFactura()
        self.parser._extraer_totales(
            "Neto $ 2.969.504\nMonto Exento $ 0\nIVA 19% $ 564.206\nTOTAL $ 3.533.710",
            factura,
        )
        self.assertEqual((factura.neto, factura.exento, factura.iva, factura.total),
                         (2969504, 0, 564206, 3533710))

    def test_totales_en_bloque_con_saltos_html(self):
        factura = ParsedFactura()
        self.parser._extraer_totales(
            "Neto<br/>Monto Exento<br/>IVA 19%<br/>TOTAL$<br/>"
            "2.969.504<br/>0<br/>564.206<br/>3.533.710", factura,
        )
        self.assertEqual((factura.neto, factura.exento, factura.iva, factura.total),
                         (2969504, 0, 564206, 3533710))

    def test_bloque_incompleto_no_divide_una_cifra_en_cuatro(self):
        factura = ParsedFactura()
        self.parser._extraer_totales("Neto\nExento\nIVA 19%\nTOTAL$ 3.533.710", factura)
        self.assertIsNone(factura.neto)
        self.assertIsNone(factura.exento)
        self.assertIsNone(factura.iva)
        self.assertEqual(factura.total, 3533710)

    def test_detalles_con_cantidades_decimales_y_campos_concatenados(self):
        for cantidad in ("1.000", "1,000", "1"):
            with self.subTest(cantidad=cantidad):
                factura = ParsedFactura()
                self.parser._extraer_detalles(
                    f"LOCAL 13-14Arriendo mensual{cantidad}MES2.861.256,002.861.256\n"
                    "GGCC GGCC Mensual 2,500 MES 100,00 250", factura,
                )
                self.assertEqual(len(factura.detalles), 2)
                self.assertEqual(factura.detalles[0].cantidad, 1.0)
                self.assertEqual(factura.detalles[0].precio_unitario, 2861256)
                self.assertEqual(factura.detalles[0].total_linea, 2861256)
                self.assertEqual(factura.detalles[1].cantidad, 2.5)
                self.assertEqual(factura.detalles[1].precio_unitario, 100)
                self.assertEqual(factura.detalles[1].total_linea, 250)


if __name__ == "__main__":
    unittest.main()
