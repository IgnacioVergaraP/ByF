"""Flujo independiente de clasificación y conciliación de egresos."""
import hashlib
from datetime import date
from difflib import SequenceMatcher

from app.core.database import db
from app.modules.conciliacion.models import (
    CentroCosto, GastoAsociacion, GastoDocumento, GastoEgreso, GastoRegla, GastoExcel, GastoExcelFila,
)
from app.modules.conciliacion.utils.normalization import normalize_text


CATALOGO_GASTOS_FIJOS = {
    "Sueldos Personal": [
        "Turnos garita fin de semana", "Sueldos Paicaví", "Anticipos",
    ],
    "Tarjetas": ["Tarjeta Crédito Mastercard"],
    "Sueldos Jefes": [
        "Sueldo Jurgen", "Imposiciones Jurguen", "Honorarios jefes a Anette",
        "Retención pagada en F29 por honorarios Anette",
        "Honorarios jefes (comisión banco por compra USD)",
    ],
    "Beneficios": ["Sodexo"],
    "Operaciones": [
        "Servicio Te Pillé 1", "Servicio Te Pillé 2", "Servicio de aseo",
        "Red Comercio", "Bio Bio Ascensores (mantención de ascensor)",
    ],
    "IVA": ["IVA (separar retención Anette)"],
    "Servicios básicos": [
        "Internet Entel Strip", "Consumos Strip: ESSBIO (60149147-8)",
        "Consumos Strip: CGE (5930101)",
    ],
    "Imposiciones": ["Imposiciones Personal"],
    "Honorarios": ["Fabiola Catalan"],
    "Créditos": ["Crédito pago de impuestos (termina 05-08-2030)"],
    "Seguros": ["BCI Seguros generales POLIZA N°679540"],
}


class GastosService:
    """Persiste reglas explicables y mantiene separado el estado de pago."""

    @staticmethod
    def catalogo() -> dict[str, list[str]]:
        return CATALOGO_GASTOS_FIJOS

    @staticmethod
    def _clave(texto: str) -> str:
        return normalize_text(texto)[:512]

    @staticmethod
    def _regla_dict(regla: GastoRegla | None) -> dict | None:
        if regla is None:
            return None
        return {
            "id": regla.id,
            "campo": regla.campo,
            "valor": regla.valor_normalizado,
            "tipo_gasto": regla.tipo_gasto,
            "categoria": regla.categoria,
            "subcategoria": regla.subcategoria,
        }

    @classmethod
    def _asociaciones(cls, egreso_id: str) -> list[GastoAsociacion]:
        return GastoAsociacion.query.filter_by(egreso_id=egreso_id).all()

    @classmethod
    def egreso_dict(cls, egreso: GastoEgreso) -> dict:
        asociaciones = cls._asociaciones(egreso.id)
        documentos = []
        for asociacion in asociaciones:
            documento = db.session.get(GastoDocumento, asociacion.documento_id)
            if documento is not None:
                documentos.append({
                    "id": documento.id,
                    "asociacion_id": asociacion.id,
                    "archivo_nombre": documento.archivo_nombre,
                    **cls._excel_metadata(documento),
                    "monto": documento.monto,
                    "fecha_documento": (
                        documento.fecha_documento.isoformat()
                        if documento.fecha_documento else None
                    ),
                    "estado_asociacion": asociacion.estado,
                })
        regla = db.session.get(GastoRegla, egreso.regla_id) if egreso.regla_id else None
        regla_sugerida = (
            db.session.get(GastoRegla, egreso.sugerencia_regla_id)
            if egreso.sugerencia_regla_id else None
        )
        return {
            "id": egreso.id,
            "cartola_id": egreso.cartola_id,
            "centro_costo_id": egreso.centro_costo_id,
            "fecha": egreso.fecha.isoformat(),
            "descripcion_original": egreso.descripcion_original,
            "beneficiario": egreso.beneficiario,
            "monto": egreso.monto,
            "tipo_gasto": egreso.tipo_gasto,
            "categoria": egreso.categoria,
            "subcategoria": egreso.subcategoria,
            "clasificacion_origen": (
                egreso.clasificacion_origen if egreso.tipo_gasto else None
            ),
            "regla": cls._regla_dict(regla),
            "sugerencia": ({
                "tipo_gasto": egreso.sugerencia_tipo,
                "categoria": egreso.sugerencia_categoria,
                "subcategoria": egreso.sugerencia_subcategoria,
                "regla": cls._regla_dict(regla_sugerida),
            } if egreso.sugerencia_tipo else None),
            "documentos": documentos,
            "estado_conciliacion": (
                "conciliado" if any(a.estado == "confirmada" for a in asociaciones)
                else "sin_documento" if not asociaciones
                else "sugerido"
            ),
        }

    def crear_cargos(self, cartola_id: str, centro_costo_id: str, cargos: list) -> int:
        agregados = 0
        for cargo in cargos:
            huella = hashlib.sha256(
                f"{cargo.fecha}|{cargo.pagina_origen}|{cargo.orden_en_pagina}|"
                f"{cargo.descripcion_original}|{cargo.monto}".encode("utf-8")
            ).hexdigest()
            existente = GastoEgreso.query.filter_by(
                cartola_id=cartola_id, huella_movimiento=huella,
            ).first()
            if existente is not None:
                continue
            clave = self._clave(cargo.descripcion_original)
            egreso = GastoEgreso(
                cartola_id=cartola_id,
                centro_costo_id=centro_costo_id,
                fecha=cargo.fecha,
                descripcion_original=cargo.descripcion_original,
                descripcion_normalizada=clave,
                beneficiario=cargo.depositante_original,
                monto=cargo.monto,
                pagina_origen=cargo.pagina_origen,
                orden_en_pagina=cargo.orden_en_pagina,
                huella_movimiento=huella,
            )
            db.session.add(egreso)
            db.session.flush()
            self._aplicar_regla(egreso)
            agregados += 1
        self.conciliar_excel(centro_costo_id)
        return agregados

    def _aplicar_regla(self, egreso: GastoEgreso) -> None:
        reglas = GastoRegla.query.filter_by(
            centro_costo_id=egreso.centro_costo_id, campo="descripcion",
        ).all()
        clave = egreso.descripcion_normalizada
        exacta = next((regla for regla in reglas if regla.valor_normalizado == clave), None)
        if exacta is not None and len(clave) >= 5:
            egreso.tipo_gasto = exacta.tipo_gasto
            egreso.categoria = exacta.categoria
            egreso.subcategoria = exacta.subcategoria
            egreso.clasificacion_origen = "automatica"
            egreso.regla_id = exacta.id
            return

        puntajes = []
        tokens = set(clave.split())
        for regla in reglas:
            regla_tokens = set(regla.valor_normalizado.split())
            if len(tokens) < 2 or len(regla_tokens) < 2:
                continue
            similitud = SequenceMatcher(
                None, clave, regla.valor_normalizado
            ).ratio()
            cobertura = len(tokens & regla_tokens) / max(1, min(len(tokens), len(regla_tokens)))
            puntaje = max(similitud, cobertura * 0.85)
            if puntaje >= 0.65:
                puntajes.append((puntaje, regla))
        if not puntajes:
            return
        mejor = max(puntaje for puntaje, _ in puntajes)
        candidatas = [regla for puntaje, regla in puntajes if abs(puntaje - mejor) < 0.02]
        clasificaciones = {
            (r.tipo_gasto, r.categoria, r.subcategoria) for r in candidatas
        }
        if len(clasificaciones) != 1:
            return
        regla = sorted(candidatas, key=lambda item: item.valor_normalizado)[0]
        egreso.sugerencia_tipo = regla.tipo_gasto
        egreso.sugerencia_categoria = regla.categoria
        egreso.sugerencia_subcategoria = regla.subcategoria
        egreso.sugerencia_regla_id = regla.id

    def clasificar(
        self, egreso: GastoEgreso, tipo: str, categoria: str | None,
        subcategoria: str | None, recordar: bool,
    ) -> None:
        if tipo not in ("fijo", "variable"):
            raise ValueError("El tipo de gasto debe ser fijo o variable.")
        if tipo == "fijo":
            if categoria not in CATALOGO_GASTOS_FIJOS:
                raise ValueError("Selecciona una categoría válida del catálogo.")
            if subcategoria not in CATALOGO_GASTOS_FIJOS[categoria]:
                raise ValueError("Selecciona una subcategoría válida para la categoría.")
        else:
            categoria = None
            subcategoria = None

        egreso.tipo_gasto = tipo
        egreso.categoria = categoria
        egreso.subcategoria = subcategoria
        egreso.clasificacion_origen = "manual"
        egreso.regla_id = None
        egreso.sugerencia_tipo = None
        egreso.sugerencia_categoria = None
        egreso.sugerencia_subcategoria = None
        egreso.sugerencia_regla_id = None

        clave = egreso.descripcion_normalizada
        if recordar:
            if len(clave) < 5:
                raise ValueError("La descripción no es suficientemente específica para crear una regla.")
            regla = GastoRegla.query.filter_by(
                centro_costo_id=egreso.centro_costo_id,
                campo="descripcion",
                valor_normalizado=clave,
            ).first()
            if regla is None:
                regla = GastoRegla(
                    centro_costo_id=egreso.centro_costo_id,
                    campo="descripcion",
                    valor_normalizado=clave,
                    tipo_gasto=tipo,
                    categoria=categoria,
                    subcategoria=subcategoria,
                )
                db.session.add(regla)
                db.session.flush()
            else:
                regla.tipo_gasto = tipo
                regla.categoria = categoria
                regla.subcategoria = subcategoria

    @staticmethod
    def desclasificar(egreso: GastoEgreso) -> None:
        egreso.tipo_gasto = None
        egreso.categoria = None
        egreso.subcategoria = None
        egreso.clasificacion_origen = "manual"
        egreso.regla_id = None
        egreso.sugerencia_tipo = None
        egreso.sugerencia_categoria = None
        egreso.sugerencia_subcategoria = None
        egreso.sugerencia_regla_id = None

    @staticmethod
    def listar_archivos(centro_costo_id=None):
        from sqlalchemy import func
        from app.modules.conciliacion.models import Cartola
        cartolas = db.session.query(Cartola, func.count(GastoEgreso.id)).join(
            GastoEgreso, GastoEgreso.cartola_id == Cartola.id,
        ).group_by(Cartola.id).order_by(Cartola.created_at.desc())
        excels = db.session.query(GastoExcel, func.count(GastoExcelFila.id)).outerjoin(
            GastoExcelFila, GastoExcelFila.excel_id == GastoExcel.id,
        ).group_by(GastoExcel.id).order_by(GastoExcel.created_at.desc())
        if centro_costo_id:
            cartolas = cartolas.filter(GastoEgreso.centro_costo_id == centro_costo_id)
            excels = excels.filter(GastoExcel.centro_costo_id == centro_costo_id)
        return {
            "cartolas": [dict(id=c.id, archivo_nombre=c.archivo_nombre,
                              centro_costo_id=c.centro_costo_id, cantidad=cantidad)
                         for c, cantidad in cartolas.all()],
            "excels": [dict(id=e.id, archivo_nombre=e.archivo_nombre,
                            centro_costo_id=e.centro_costo_id, cantidad=cantidad)
                       for e, cantidad in excels.all()],
        }

    @staticmethod
    def eliminar_cartola_gastos(cartola_id):
        from app.modules.conciliacion.models import Cartola, MovimientoBancario
        cartola = db.session.get(Cartola, cartola_id)
        if cartola is None:
            raise LookupError("Cartola no encontrada.")
        egresos = GastoEgreso.query.filter_by(cartola_id=cartola_id).all()
        if not egresos:
            raise LookupError("La cartola no tiene cargos cargados en Gastos.")
        for egreso in egresos:
            GastoAsociacion.query.filter_by(egreso_id=egreso.id).delete(synchronize_session=False)
            db.session.delete(egreso)
        db.session.flush()
        # La cartola es compartida con Ingresos. Conservarla si contiene abonos.
        conserva_abonos = MovimientoBancario.query.filter_by(cartola_id=cartola_id).first() is not None
        if not conserva_abonos:
            db.session.delete(cartola)
        db.session.commit()
        return dict(ok=True, cantidad_eliminada=len(egresos), conserva_abonos=conserva_abonos)

    @staticmethod
    def eliminar_excel(excel_id):
        excel = db.session.get(GastoExcel, excel_id)
        if excel is None:
            raise LookupError("Excel no encontrado.")
        filas = GastoExcelFila.query.filter_by(excel_id=excel_id).all()
        documentos = [db.session.get(GastoDocumento, fila.documento_id) for fila in filas]
        for fila in filas:
            GastoAsociacion.query.filter_by(documento_id=fila.documento_id).delete(synchronize_session=False)
            db.session.delete(fila)
        db.session.flush()
        for documento in documentos:
            if documento is not None:
                db.session.delete(documento)
        db.session.flush()
        db.session.delete(excel)
        db.session.commit()
        return dict(ok=True, cantidad_eliminada=len(filas))

    @staticmethod
    def eliminar_documento(documento_id):
        documento = db.session.get(GastoDocumento, documento_id)
        if documento is None:
            raise LookupError("Documento no encontrado.")
        if GastoExcelFila.query.filter_by(documento_id=documento_id).first() is not None:
            raise ValueError("Este gasto pertenece a un Excel. Bórralo desde Excel cargados.")
        db.session.delete(documento)
        db.session.commit()
        return dict(ok=True)

    @staticmethod
    def _excel_metadata(documento):
        fila = GastoExcelFila.query.filter_by(documento_id=documento.id).first()
        return ({"destinatario": fila.destinatario, "observacion": fila.observacion,
                 "hoja": fila.hoja, "fila": fila.fila, "rut": fila.rut} if fila else {})

    def importar_excel(self, centro_costo_id, archivo_nombre, contenido):
        from app.modules.conciliacion.parsers.gastos_excel_parser import parse_gastos_excel
        if db.session.get(CentroCosto, centro_costo_id) is None:
            raise ValueError("Centro de costo no encontrado.")
        if not archivo_nombre.lower().endswith('.xlsx'):
            raise ValueError("Los gastos deben cargarse en formato Excel (.xlsx).")
        huella = hashlib.sha256(contenido).hexdigest()
        excel = GastoExcel.query.filter_by(centro_costo_id=centro_costo_id, archivo_hash=huella).first()
        duplicada = excel is not None
        if excel is None:
            registros = parse_gastos_excel(contenido)
            excel = GastoExcel(centro_costo_id=centro_costo_id, archivo_nombre=archivo_nombre,
                               archivo_hash=huella, contenido=contenido)
            db.session.add(excel)
            db.session.flush()
            for registro in registros:
                documento = GastoDocumento(centro_costo_id=centro_costo_id,
                    archivo_nombre=archivo_nombre,
                    archivo_hash=hashlib.sha256(f"{huella}|{registro['hoja']}|{registro['fila']}".encode()).hexdigest(),
                    contenido=b'', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    fecha_documento=registro['fecha'], monto=registro['monto'])
                db.session.add(documento)
                db.session.flush()
                db.session.add(GastoExcelFila(documento_id=documento.id, excel_id=excel.id,
                    **{k: registro[k] for k in ('hoja', 'fila', 'destinatario', 'observacion', 'rut')}))
            db.session.flush()
        self.conciliar_excel(centro_costo_id)
        filas = GastoExcelFila.query.filter_by(excel_id=excel.id).all()
        documentos = [db.session.get(GastoDocumento, f.documento_id) for f in filas]
        estados = [GastoAsociacion.query.filter_by(documento_id=d.id).all() for d in documentos]
        confirmados = sum(any(a.estado == 'confirmada' for a in grupo) for grupo in estados)
        sugeridos = sum(bool(grupo) and not any(a.estado == 'confirmada' for a in grupo) for grupo in estados)
        db.session.commit()
        return dict(id=excel.id, duplicada=duplicada, cantidad_gastos=len(filas),
                    conciliados=confirmados, pendientes_aprobacion=sugeridos,
                    sin_coincidencia=len(filas)-confirmados-sugeridos)

    def conciliar_excel(self, centro_costo_id):
        # Evaluar todo el conjunto antes de asignar: nunca resolver duplicados
        # por el orden de filas ni por la eliminación de candidatos ya usados.
        documentos = GastoDocumento.query.join(GastoExcelFila,
            GastoExcelFila.documento_id == GastoDocumento.id).filter(
            GastoDocumento.centro_costo_id == centro_costo_id).all()
        egresos = GastoEgreso.query.filter_by(centro_costo_id=centro_costo_id).all()
        def compatibles(d, e):
            return d.monto == e.monto and abs((d.fecha_documento-e.fecha).days) <= 45
        for documento in documentos:
            if GastoAsociacion.query.filter_by(documento_id=documento.id).first():
                continue
            candidatos = [e for e in egresos if compatibles(documento, e)]
            if not candidatos:
                continue
            unico = len(candidatos) == 1 and sum(compatibles(d, candidatos[0]) for d in documentos) == 1
            if unico:
                elegidos = candidatos
            else:
                nombre = set(self._clave(self._excel_metadata(documento)['destinatario']).split())
                nombre -= {'de', 'del', 'la', 'las', 'los', 'y', 'spa', 'ltda', 'sa'}
                elegidos = []
                for egreso in candidatos:
                    texto = set(self._clave(f"{egreso.beneficiario or ''} {egreso.descripcion_original}").split())
                    # Al menos dos palabras y dos tercios del nombre, sin tildes ni importar el orden.
                    if len(nombre & texto) >= 2 and len(nombre & texto) / max(len(nombre), 1) >= 2/3:
                        elegidos.append(egreso)
            for egreso in elegidos:
                if any(a.estado == 'confirmada' for a in self._asociaciones(egreso.id)):
                    continue
                db.session.add(GastoAsociacion(egreso_id=egreso.id, documento_id=documento.id,
                    estado='confirmada' if unico else 'sugerida'))
            db.session.flush()

    def subir_documento(
        self, centro_costo_id: str, archivo_nombre: str, contenido: bytes,
        content_type: str,
    ) -> tuple[GastoDocumento, bool]:
        if db.session.get(CentroCosto, centro_costo_id) is None:
            raise ValueError("Centro de costo no encontrado.")
        if not archivo_nombre.lower().endswith(".pdf"):
            raise ValueError("Las facturas deben cargarse en formato PDF.")
        huella = hashlib.sha256(contenido).hexdigest()
        existente = GastoDocumento.query.filter_by(
            centro_costo_id=centro_costo_id, archivo_hash=huella,
        ).first()
        if existente is not None:
            return existente, True
        from app.modules.conciliacion.parsers.factura_chile_parser import FacturaChileParser
        parsed = FacturaChileParser().parse(contenido, archivo_nombre)
        if parsed.errores:
            raise ValueError("No se pudo leer la factura: " + "; ".join(parsed.errores))
        if not parsed.folio or not parsed.rut_emisor or parsed.total is None:
            raise ValueError(
                "El PDF no contiene los datos mínimos de una factura: folio, RUT del emisor y total."
            )
        if parsed.neto is not None and parsed.iva is not None:
            if parsed.neto + (parsed.exento or 0) + parsed.iva != parsed.total:
                raise ValueError("Los totales extraídos de la factura no son consistentes.")
        documento = GastoDocumento(
            centro_costo_id=centro_costo_id,
            archivo_nombre=archivo_nombre,
            archivo_hash=huella,
            content_type=content_type,
            contenido=contenido,
            fecha_documento=parsed.fecha_emision,
            monto=parsed.total,
        )
        db.session.add(documento)
        db.session.flush()
        self._sugerir_asociacion(documento)
        db.session.commit()
        return documento, False

    def _sugerir_asociacion(self, documento: GastoDocumento) -> None:
        if documento.monto is None or documento.fecha_documento is None:
            return
        candidatos = GastoEgreso.query.filter_by(
            centro_costo_id=documento.centro_costo_id, monto=documento.monto,
        ).all()
        candidatos = [
            egreso for egreso in candidatos
            if abs((egreso.fecha - documento.fecha_documento).days) <= 45
            and not GastoAsociacion.query.filter_by(egreso_id=egreso.id).first()
        ]
        if len(candidatos) == 1:
            db.session.add(GastoAsociacion(
                egreso_id=candidatos[0].id,
                documento_id=documento.id,
                estado="sugerida",
            ))

    @staticmethod
    def asociar(egreso_id: str, documento_id: str, confirmar: bool) -> GastoAsociacion:
        egreso = db.session.get(GastoEgreso, egreso_id)
        documento = db.session.get(GastoDocumento, documento_id)
        if egreso is None or documento is None:
            raise LookupError("Egreso o documento no encontrado.")
        if egreso.centro_costo_id != documento.centro_costo_id:
            raise ValueError("El egreso y el documento deben pertenecer a la misma entidad.")
        fila_excel = GastoExcelFila.query.filter_by(documento_id=documento_id).first()
        if fila_excel and egreso.monto != documento.monto:
            raise ValueError("El monto del Excel debe coincidir exactamente con el egreso.")
        conflictos = GastoAsociacion.query.filter(
            ((GastoAsociacion.egreso_id == egreso_id) | (GastoAsociacion.documento_id == documento_id)),
            GastoAsociacion.estado == "confirmada",
        ).all()
        if any(a.egreso_id != egreso_id or a.documento_id != documento_id for a in conflictos):
            raise ValueError("El gasto o el egreso ya tiene una conciliación confirmada. Reviértela primero.")
        if confirmar:
            for otra in GastoAsociacion.query.filter(
                ((GastoAsociacion.egreso_id == egreso_id) | (GastoAsociacion.documento_id == documento_id)),
                GastoAsociacion.estado == 'sugerida',
            ).all():
                if otra.egreso_id != egreso_id or otra.documento_id != documento_id:
                    db.session.delete(otra)
        asociacion = GastoAsociacion.query.filter_by(
            egreso_id=egreso_id, documento_id=documento_id,
        ).first()
        if asociacion is None:
            asociacion = GastoAsociacion(
                egreso_id=egreso_id, documento_id=documento_id,
                estado="confirmada" if confirmar else "sugerida",
            )
            db.session.add(asociacion)
        elif confirmar:
            asociacion.estado = "confirmada"
        db.session.commit()
        return asociacion

    @classmethod
    def listar_documentos(cls) -> list[dict]:
        documentos = GastoDocumento.query.order_by(GastoDocumento.created_at.desc()).all()
        result = []
        for documento in documentos:
            asociaciones = GastoAsociacion.query.filter_by(
                documento_id=documento.id,
            ).all()
            result.append({
                "id": documento.id,
                "centro_costo_id": documento.centro_costo_id,
                "archivo_nombre": documento.archivo_nombre,
                "fecha_documento": (
                    documento.fecha_documento.isoformat()
                    if documento.fecha_documento else None
                ),
                "monto": documento.monto,
                **cls._excel_metadata(documento),
                "estado": (
                    "pagado" if any(a.estado == "confirmada" for a in asociaciones)
                    else "pendiente_pago"
                ),
                "asociaciones": [{
                    "id": a.id, "egreso_id": a.egreso_id, "estado": a.estado,
                } for a in asociaciones],
            })
        return result
