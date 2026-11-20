"""Servicio de importación del Excel maestro de arrendatarios."""
from dataclasses import dataclass, field
from typing import BinaryIO

from openpyxl import load_workbook

from app.modules.conciliacion.repositories.maestro_repository import MaestroRepository
from app.modules.conciliacion.utils.normalization import normalize_text

REQUIRED_COLUMNS = ("CC", "PROPIEDAD", "ARRENDATARIO", "CONCEPTO")


@dataclass
class ImportResult:
    total_rows: int = 0
    imported_rows: int = 0
    skipped_rows: int = 0
    errors: list[dict] = field(default_factory=list)


class ImportService:
    def __init__(self, repository: MaestroRepository | None = None) -> None:
        self.repo = repository or MaestroRepository()

    def import_excel(self, file_stream: BinaryIO) -> ImportResult:
        result = ImportResult()
        try:
            wb = load_workbook(file_stream, data_only=True, read_only=True)
        except Exception as exc:
            result.errors.append({"row": 0, "message": f"No se pudo abrir el Excel: {exc}"})
            return result

        try:
            ws = wb.active
            rows = ws.iter_rows(values_only=True)
            try:
                header = next(rows)
            except StopIteration:
                result.errors.append({"row": 0, "message": "Excel vacío."})
                return result

            header_map = {
                str(col).strip().upper(): idx
                for idx, col in enumerate(header) if col is not None
            }

            missing = [c for c in REQUIRED_COLUMNS if c not in header_map]
            if missing:
                result.errors.append({
                    "row": 0,
                    "message": f"Faltan columnas requeridas: {missing}"
                })
                return result

            idx_cc = header_map["CC"]
            idx_prop = header_map["PROPIEDAD"]
            idx_arr = header_map["ARRENDATARIO"]
            idx_con = header_map["CONCEPTO"]

            for excel_row, row in enumerate(rows, start=2):
                result.total_rows += 1
                try:
                    cc_raw = row[idx_cc] if idx_cc < len(row) else None
                    prop_raw = row[idx_prop] if idx_prop < len(row) else None
                    arr_raw = row[idx_arr] if idx_arr < len(row) else None
                    con_raw = row[idx_con] if idx_con < len(row) else None

                    if not cc_raw or not prop_raw or not arr_raw:
                        result.skipped_rows += 1
                        continue

                    cc_str = str(cc_raw).strip()
                    prop_str = str(prop_raw).strip()
                    arr_str = str(arr_raw).strip()
                    con_str = str(con_raw).strip() if con_raw is not None else ""

                    cc_norm = normalize_text(cc_str)
                    prop_norm = normalize_text(prop_str)
                    arr_norm = normalize_text(arr_str)

                    if not cc_norm or not prop_norm or not arr_norm:
                        result.skipped_rows += 1
                        continue

                    # Buscar centro por normalizado (case-insensitive)
                    centro = self.repo.get_centro_by_codigo(cc_str)
                    if centro is None:
                        centro = self.repo.create_centro(cc_str, cc_str, cc_norm)

                    propiedad = self.repo.get_propiedad(centro.id, prop_norm)
                    if propiedad is None:
                        propiedad = self.repo.create_propiedad(
                            prop_str, prop_norm, centro.id
                        )

                    arrendatario = self.repo.get_arrendatario(arr_norm)
                    if arrendatario is None:
                        arrendatario = self.repo.create_arrendatario(arr_str, arr_norm)

                    self.repo.link_propiedad_arrendatario(
                        propiedad.id, arrendatario.id
                    )

                    if con_str:
                        con_norm = normalize_text(con_str)
                        if con_norm:
                            concepto = self.repo.get_concepto(con_norm)
                            if concepto is None:
                                concepto = self.repo.create_concepto(con_str, con_norm)
                            self.repo.link_propiedad_concepto(
                                propiedad.id, concepto.id
                            )

                    result.imported_rows += 1
                except Exception as exc:
                    result.errors.append({
                        "row": excel_row,
                        "message": f"Error en fila {excel_row}: {exc}",
                    })
                    self.repo.rollback()
                    continue

            self.repo.commit()
        finally:
            wb.close()

        return result