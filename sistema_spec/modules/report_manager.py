# modules/report_manager.py
import os
import pandas as pd
from datetime import datetime
import json
from fpdf import FPDF

from config.settings import REPORTS_DIR
from models.base_model import get_db_connection
from models.report_model import Report

class ReportManager:
    """
    Manages the generation and metadata of reports.
    Now capable of generating reports in Excel and PDF formats.
    """
    def __init__(self, data_dir, reports_dir, user_manager):
        self.data_dir = data_dir
        self.reports_dir = reports_dir
        self.user_manager = user_manager
        Report._create_table()
        os.makedirs(self.reports_dir, exist_ok=True)

    def _save_report_metadata(self, report_type, generated_by_user_id, file_path, filters):
        """Saves report metadata to the database."""
        report = Report(
            report_type=report_type,
            generation_date=datetime.now().isoformat(),
            generated_by_user_id=generated_by_user_id,
            file_path=file_path,
            filters_json=json.dumps(filters, default=str) # Use default=str for dates
        )
        report.save()
        print(f"Report metadata saved for: {file_path}")

    def get_all_reports_metadata(self):
        """
        Retrieves all report metadata from the database, including the generator's username.
        This method is added back to fix the AttributeError.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            query = """
                SELECT r.id, r.report_type, r.generation_date, r.file_path, r.filters_json, u.username AS generated_by_username
                FROM reports r
                LEFT JOIN users u ON r.generated_by_user_id = u.id
                ORDER BY r.generation_date DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if conn:
                conn.close()

    def _generate_file(self, df, base_filename, title, export_format="excel"):
        """
        Generic file generation helper for Excel and PDF.

        Args:
            df (pd.DataFrame): The data to be exported.
            base_filename (str): The base name for the output file.
            title (str): The title for the report.
            export_format (str): 'excel' or 'pdf'.

        Returns:
            tuple: (bool, str, str) - Success status, message, and file path.
        """
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{base_filename}_{timestamp_str}.{export_format}"
        file_path = os.path.join(self.reports_dir, file_name)

        try:
            if export_format == "excel":
                df.to_excel(file_path, index=False)
            elif export_format == "pdf":
                pdf = FPDF(orientation='L') # Landscape orientation for more columns
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, title, 0, 1, 'C')
                pdf.ln(10)

                pdf.set_font("Arial", 'B', 8)
                # Table Header - Adjust cell width
                col_widths = {col: int(260 / len(df.columns)) for col in df.columns} # Dynamic width
                for col in df.columns:
                    pdf.cell(col_widths[col], 10, col, 1, 0, 'C')
                pdf.ln()

                pdf.set_font("Arial", '', 8)
                # Table Rows
                for index, row in df.iterrows():
                    for i, col in enumerate(df.columns):
                        pdf.cell(col_widths[col], 10, str(row[col]), 1, 0)
                    pdf.ln()
                pdf.output(file_path)
            else:
                return False, f"Unsupported format: {export_format}", None

            return True, f"Report generated successfully: {file_path}", file_path

        except Exception as e:
            print(f"Error generating file: {e}")
            return False, f"Error generating report file: {e}", None

    def generate_sales_report(self, start_date, end_date, generated_by_user_id, export_format="excel"):
        """Fetches sales data and generates a report."""
        conn = get_db_connection()
        try:
            query = """
                SELECT
                    s.id, s.sale_date, c.name as customer_name, s.total_amount,
                    s.discount_applied, s.payment_method, s.status, u.username as registered_by
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                LEFT JOIN users u ON s.user_id = u.id
                WHERE s.sale_date BETWEEN ? AND ?
                ORDER BY s.sale_date DESC
            """
            df = pd.read_sql_query(query, conn, params=(start_date, end_date))
            if df.empty:
                return False, "No sales data found for the selected period.", None

            success, message, file_path = self._generate_file(df, "sales_report", "Sales Report", export_format)

            if success:
                filters = {"start_date": start_date, "end_date": end_date}
                self._save_report_metadata("Sales Report", generated_by_user_id, file_path, filters)

            return success, message, file_path
        except Exception as e:
            return False, f"Error generating sales report: {e}", None
        finally:
            if conn:
                conn.close()

    def generate_stock_report(self, generated_by_user_id, export_format="excel"):
        """Fetches stock data and generates a report."""
        conn = get_db_connection()
        try:
            query = """
                SELECT
                    p.id, p.name, p.part_number, p.manufacturer, p.price, p.cost,
                    p.stock, p.min_stock, p.location, s.name as supplier_name
                FROM parts p
                LEFT JOIN suppliers s ON p.supplier_id = s.id
                ORDER BY p.name ASC
            """
            df = pd.read_sql_query(query, conn)
            if df.empty:
                return False, "No stock data found.", None

            success, message, file_path = self._generate_file(df, "stock_report", "Stock Report", export_format)

            if success:
                self._save_report_metadata("Stock Report", generated_by_user_id, file_path, {})

            return success, message, file_path
        except Exception as e:
            return False, f"Error generating stock report: {e}", None
        finally:
            if conn:
                conn.close()

    def generate_financial_summary_report(self, start_date, end_date, generated_by_user_id, export_format="excel"):
        """Fetches financial data and generates a summary report."""
        conn = get_db_connection()
        try:
            query = """
                SELECT transaction_date, type, category, description, amount
                FROM financial_transactions
                WHERE transaction_date BETWEEN ? AND ?
                ORDER BY transaction_date
            """
            df = pd.read_sql_query(query, conn, params=(start_date, end_date))
            if df.empty:
                return False, "No financial data for the selected period.", None

            total_revenue = df[df['type'] == 'Receita']['amount'].sum()
            total_expense = df[df['type'] == 'Despesa']['amount'].sum()
            balance = total_revenue - total_expense

            summary_df = pd.DataFrame({
                'Description': ['Total Revenue', 'Total Expense', 'Final Balance'],
                'Amount': [f"R$ {total_revenue:.2f}", f"R$ {total_expense:.2f}", f"R$ {balance:.2f}"]
            })
            
            # Also include the detailed transaction list in the same report if it's Excel
            if export_format == 'excel':
                with pd.ExcelWriter(os.path.join(self.reports_dir, f"financial_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")) as writer:
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    df.to_excel(writer, sheet_name='Transactions', index=False)
                file_path = writer.path
                success = True
                message = f"Report generated successfully: {file_path}"
            else: # For PDF, just generate summary or you could make it multi-page
                 success, message, file_path = self._generate_file(summary_df, "financial_summary", "Financial Summary", export_format)


            if success:
                filters = {"start_date": start_date, "end_date": end_date}
                self._save_report_metadata("Financial Summary Report", generated_by_user_id, file_path, filters)

            return success, message, file_path
        except Exception as e:
            return False, f"Error generating financial report: {e}", None
        finally:
            if conn:
                conn.close()

    def generate_service_order_report(self, start_date, end_date, status, assigned_user_id, generated_by_user_id, export_format="excel"):
        """Fetches service order data and generates a report."""
        conn = get_db_connection()
        try:
            query = """
                SELECT
                    so.id, so.order_date, c.name as customer_name, so.vehicle_plate,
                    so.description, so.status, so.total_amount, u.username as assigned_to
                FROM service_orders so
                JOIN customers c ON so.customer_id = c.id
                LEFT JOIN users u ON so.assigned_user_id = u.id
                WHERE so.order_date BETWEEN ? AND ?
            """
            params = [start_date, end_date]
            if status:
                query += " AND so.status = ?"
                params.append(status)
            if assigned_user_id:
                query += " AND so.assigned_user_id = ?"
                params.append(assigned_user_id)

            query += " ORDER BY so.order_date DESC"

            df = pd.read_sql_query(query, conn, params=tuple(params))
            if df.empty:
                return False, "No service order data found for the selected criteria.", None

            success, message, file_path = self._generate_file(df, "service_order_report", "Service Order Report", export_format)

            if success:
                filters = {"start_date": start_date, "end_date": end_date, "status": status, "assigned_user_id": assigned_user_id}
                self._save_report_metadata("Service Order Report", generated_by_user_id, file_path, filters)

            return success, message, file_path
        except Exception as e:
            return False, f"Error generating service order report: {e}", None
        finally:
            if conn:
                conn.close()
