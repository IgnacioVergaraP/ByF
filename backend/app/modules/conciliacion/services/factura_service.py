"""Servicio de importación masiva de facturas."""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date

from app.modules.conciliacion.parsers.factura_chile_parser import FacturaChileParser
from app.modules.conciliacion.repositories.factura_repository import FacturaRepository
from app.modules.conciliacion.utils.rut import normalizar_rut


@dataclass
class FacturaResult:
    archivo: str
    ok: bool = False
    duplicada: bool = False
    factura_id: str | None = None
    folio: str | None = None
    errores: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    importacion_id: str | None = None
    archivos_recibidos: int = 0
    facturas_validas: int = 0
    facturas_duplicadas: int = 0
    facturas_con_error: int = 0
    detalles: list[FacturaResult] = field(default_factory=list)


class FacturaService:
    def __init__(self, repo: FacturaRepository | None = None) -> None:
        self.repo = repo or FacturaRepository()

    def _hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def importar_lote(self, archivos: list[tuple[str, bytes]]) -> ImportResult:
        result = ImportResult(archivos_recibidos=len(archivos))
        importacion = self.repo.create_importacion(
            archivos_recibidos=len(archivos),
            facturas_procesadas=0, facturas_validas=0,
            facturas_duplicadas=0, facturas_con_error=0,
        )
        result.importacion_id = importacion.id

        for nombre, data in archivos:
            res = self._procesar_archivo(nombre, data, importacion.id)
            result.detalles.append(res)
            if res.duplicada:
                result.facturas_duplicadas += 1
            elif res.ok:
                result.facturas_validas += 1
            else:
                result.facturas_con_error += 1

        importacion.facturas_procesadas = len(archivos)
        importacion.facturas_validas = result.facturas_validas
        importacion.facturas_duplicadas = result.facturas_duplicadas
        importacion.facturas_con_error = result.facturas_con_error
        importacion.detalle_json = json.dumps(
            [{"archivo": d.archivo, "ok": d.ok, "errores": d.errores}
             for d in result.detalles],
            ensure_ascii=False,
        )
        self.repo.commit()

        # Reconocimiento automático post-importación
        try:
            from app.modules.conciliacion.services.factura_asociacion_service import (
                FacturaAsociacionService,
            )
            FacturaAsociacionService().reconocer_todas()
        except Exception:
            pass

        # Inferir propiedades para las facturas recién importadas
        try:
            from app.modules.conciliacion.services.aprendizaje_service import (
                AprendizajeService,
            )
            from app.core.database import db
            svc = AprendizajeService()
            for res_item in result.detalles:
                if res_item.factura_id:
                    try:
                        svc.inferir_propiedad_para_factura(res_item.factura_id)
                    except Exception:
                        pass
            db.session.commit()
        except Exception:
            try:
                from app.core.database import db
                db.session.rollback()
            except Exception:
                pass

        # Motor de conciliación automática
        try:
            from app.modules.conciliacion.services.conciliacion_service import (
                ConciliacionService,
            )
            ConciliacionService().reconocer_todos()
        except Exception:
            pass

        return result

    def _procesar_archivo(
        self, nombre: str, data: bytes, importacion_id: str
    ) -> FacturaResult:
        res = FacturaResult(archivo=nombre)
        archivo_hash = self._hash(data)

        existente = self.repo.get_por_hash(archivo_hash)
        if existente is not None and existente.estado != "requiere_revision":
            res.duplicada = True
            res.factura_id = existente.id
            res.folio = existente.folio
            res.ok = True
            return res

        parser = FacturaChileParser()
        parsed = parser.parse(data, nombre)
        if parsed.errores:
            res.errores.extend(parsed.errores)
            return res

        if not parsed.folio:
            res.errores.append("No se pudo extraer el folio.")
            return res
        if not parsed.rut_emisor:
            res.errores.append("No se pudo extraer el RUT del emisor.")
            return res

        rut_emisor_norm = normalizar_rut(parsed.rut_emisor)
        if not rut_emisor_norm:
            res.errores.append(f"RUT emisor inválido: {parsed.rut_emisor}")
            return res

        if existente is not None:
            identidad_anterior = (
                existente.rut_emisor_normalizado, existente.tipo_documento, existente.folio,
            )
            identidad_nueva = (rut_emisor_norm, parsed.tipo_documento, parsed.folio)
            if identidad_nueva != identidad_anterior:
                res.errores.append(
                    "La identidad tributaria extraída cambió. Se conservó la factura anterior."
                )
                return res

        conflicto = self.repo.get_por_identidad(
            rut_emisor_norm, parsed.tipo_documento, parsed.folio
        )
        if conflicto is not None and (existente is None or conflicto.id != existente.id):
            res.errores.append(
                f"Conflicto: ya existe la factura {parsed.folio} del emisor "
                f"{rut_emisor_norm} con otro archivo. Marcar para revisión."
            )
            factura = self._crear_factura(
                parsed, nombre, archivo_hash, importacion_id,
                estado="conflicto", validacion_ok=False,
                mensaje="Conflicto de identidad tributaria.",
            )
            res.factura_id = factura.id
            return res

        validacion_ok, mensaje = self._validar_importes(parsed)
        estado = "procesada" if validacion_ok else "requiere_revision"

        if existente is not None and not validacion_ok:
            res.factura_id = existente.id
            res.folio = existente.folio
            res.errores.append(f"No se pudo reprocesar la factura: {mensaje}")
            return res

        factura = self._crear_factura(
            parsed, nombre, archivo_hash, importacion_id,
            estado=estado, validacion_ok=validacion_ok, mensaje=mensaje,
            existente=existente,
        )
        for det in parsed.detalles:
            self.repo.create_detalle(
                factura_id=factura.id,
                codigo=det.codigo,
                descripcion=det.descripcion,
                cantidad=det.cantidad,
                unidad=det.unidad,
                precio_unitario=det.precio_unitario,
                descuento=det.descuento,
                total_linea=det.total_linea,
            )
        self.repo.commit()

        res.ok = True
        res.factura_id = factura.id
        res.folio = factura.folio
        return res

    def _crear_factura(
        self, parsed, nombre: str, archivo_hash: str, importacion_id: str,
        estado: str, validacion_ok: bool, mensaje: str, existente=None,
    ):
        campos = dict(
            importacion_id=importacion_id,
            tipo_documento=parsed.tipo_documento,
            folio=parsed.folio,
            rut_emisor=parsed.rut_emisor,
            rut_emisor_normalizado=normalizar_rut(parsed.rut_emisor or ""),
            razon_social_emisor=parsed.razon_social_emisor,
            rut_receptor=parsed.rut_receptor,
            rut_receptor_normalizado=normalizar_rut(parsed.rut_receptor or ""),
            razon_social_receptor=parsed.razon_social_receptor,
            fecha_emision=parsed.fecha_emision,
            fecha_vencimiento=parsed.fecha_vencimiento,
            neto=parsed.neto,
            exento=parsed.exento,
            iva=parsed.iva,
            total=parsed.total,
            archivo_nombre=nombre,
            archivo_hash=archivo_hash,
            estado=estado,
            validacion_ok=validacion_ok,
            validacion_mensaje=mensaje,
        )
        if existente is not None:
            campos.pop("importacion_id")
            return self.repo.actualizar_factura(existente, **campos)
        return self.repo.create_factura(**campos)

    def _validar_importes(self, parsed) -> tuple[bool, str]:
        errores = []
        if parsed.neto is None or parsed.iva is None or parsed.total is None:
            return False, "Faltan campos de totales (neto, IVA o total)."
        if parsed.neto + (parsed.exento or 0) + parsed.iva != parsed.total:
            errores.append(
                f"Neto ({parsed.neto}) + Exento ({parsed.exento or 0}) + IVA "
                f"({parsed.iva}) != Total ({parsed.total})."
            )
        if parsed.detalles:
            suma = sum(d.total_linea or 0 for d in parsed.detalles)
            base_total = parsed.neto + (parsed.exento or 0)
            if suma != base_total:
                errores.append(
                    f"Suma de líneas ({suma}) != Neto + Exento ({base_total})."
                )
        if errores:
            return False, "; ".join(errores)
        return True, "Validación de importes OK."

    def reprocesar(self, factura_id: str) -> dict:
        """Re-extrae una factura en requiere_revision sin duplicar."""
        from app.modules.conciliacion.models import Factura

        factura = Factura.query.filter_by(id=factura_id).first()
        if factura is None:
            return {"ok": False, "error": "Factura no encontrada."}

        return {
            "ok": False,
            "error": "No se puede reprocesar sin el PDF original. "
                     "Borra la factura con 'Limpiar registros' y súbela de nuevo.",
        }