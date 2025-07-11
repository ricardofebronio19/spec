# modules/stock_manager.py
from models.part_model import Part
from models.base_model import get_db_connection
from modules.notification_manager import NotificationManager
import sqlite3

class StockManager:
    def __init__(self, notification_manager=None):
        Part._create_table()
        self.notification_manager = notification_manager

    def add_part(self, name, description, part_number, manufacturer, price, cost,
                 stock, min_stock, location, supplier_id, category,
                 original_code=None, similar_code_01=None, similar_code_02=None, barcode=None):
        """Adds a new part to stock."""
        try:
            barcode = barcode if barcode else None
            original_code = original_code if original_code else None
            similar_code_01 = similar_code_01 if similar_code_01 else None
            similar_code_02 = similar_code_02 if similar_code_02 else None

            # Usando Part.search com dois argumentos: query e column_name
            if part_number and Part.search(part_number, 'part_number'):
                return False, f"Part with number '{part_number}' already exists."
            
            if original_code and Part.search(original_code, 'original_code'):
                return False, f"A part with Original Code '{original_code}' already exists."
            if similar_code_01 and Part.search(similar_code_01, 'similar_code_01'):
                return False, f"A part with Similar Code 01 '{similar_code_01}' already exists."
            if similar_code_02 and Part.search(similar_code_02, 'similar_code_02'):
                return False, f"A part with Similar Code 02 '{similar_code_02}' already exists."
            if barcode and Part.search(barcode, 'barcode'):
                return False, f"A part with Barcode '{barcode}' already exists."

            part = Part(
                name=name, description=description, part_number=part_number,
                manufacturer=manufacturer, price=price, cost=cost, stock=stock,
                min_stock=min_stock, location=location, supplier_id=supplier_id,
                category=category, original_code=original_code,
                similar_code_01=similar_code_01, similar_code_02=similar_code_02,
                barcode=barcode
            )
            part.save()

            if self.notification_manager:
                self.notification_manager.check_low_stock(part.id, part.stock, part.min_stock)

            return True, "Part added successfully!"
        except Exception as e:
            return False, f"Error adding part: {e}"

    def update_part(self, part_id, name, description, part_number, manufacturer, price, cost,
                    stock, min_stock, location, supplier_id, category,
                    original_code=None, similar_code_01=None, similar_code_02=None, barcode=None):
        """Updates an existing part's data."""
        part = Part.get_by_id(part_id)
        if part:
            barcode = barcode if barcode else None
            original_code = original_code if original_code else None
            similar_code_01 = similar_code_01 if similar_code_01 else None
            similar_code_02 = similar_code_02 if similar_code_02 else None

            # Usando Part.search com dois argumentos: query e column_name
            existing_part_by_number = Part.search(part_number, 'part_number')
            if existing_part_by_number and any(p.id != part_id and p.part_number == part_number for p in existing_part_by_number):
                return False, f"Part with number '{part_number}' already exists for another record."
            
            existing_part_by_original_code = Part.search(original_code, 'original_code')
            if original_code and existing_part_by_original_code and any(p.id != part_id and p.original_code == original_code for p in existing_part_by_original_code):
                return False, f"A part with Original Code '{original_code}' already exists for another record."

            existing_part_by_similar_code_01 = Part.search(similar_code_01, 'similar_code_01')
            if similar_code_01 and existing_part_by_similar_code_01 and any(p.id != part_id and p.similar_code_01 == similar_code_01 for p in existing_part_by_similar_code_01):
                return False, f"A part with Similar Code 01 '{similar_code_01}' already exists for another record."

            existing_part_by_similar_code_02 = Part.search(similar_code_02, 'similar_code_02')
            if similar_code_02 and existing_part_by_similar_code_02 and any(p.id != part_id and p.similar_code_02 == similar_code_02 for p in existing_part_by_similar_code_02):
                return False, f"A part with Similar Code 02 '{similar_code_02}' already exists for another record."

            existing_part_by_barcode = Part.search(barcode, 'barcode')
            if barcode and existing_part_by_barcode and any(p.id != part_id and p.barcode == barcode for p in existing_part_by_barcode):
                return False, f"A part with Barcode '{barcode}' already exists for another record."


            part.name = name; part.description = description; part.part_number = part_number;
            part.manufacturer = manufacturer; part.price = price; part.cost = cost;
            part.stock = stock; part.min_stock = min_stock; part.location = location;
            part.supplier_id = supplier_id; part.category = category;
            part.original_code = original_code; part.similar_code_01 = similar_code_01;
            part.similar_code_02 = similar_code_02; part.barcode = barcode;
            part.save()

            if self.notification_manager:
                self.notification_manager.check_low_stock(part.id, part.stock, part.min_stock)

            return True, "Part updated successfully!"
        return False, "Part not found."

    def delete_part(self, part_id):
        """Deletes a part."""
        Part.delete(part_id)
        return True, "Part removed successfully!"

    def get_all_parts(self):
        """Returns all parts."""
        return Part.get_all()

    def get_part_by_id(self, part_id):
        """Returns a part by ID."""
        return Part.get_by_id(part_id)

    def search_parts(self, query):
        """Searches for parts by name, part number, manufacturer, or codes."""
        # Esta chamada agora está correta, pois Part.search() sem column_name faz a busca ampla.
        return Part.search(query)

    def add_stock(self, part_id, quantity, user_id=None, cursor=None):
        """Adds a quantity to a part's stock."""
        part = Part.get_by_id(part_id)
        if part:
            part.stock += quantity
            part.save(cursor=cursor)
            if self.notification_manager:
                self.notification_manager.check_low_stock(part.id, part.stock, part.min_stock)
            return True, f"Stock for '{part.name}' updated to {part.stock}."
        return False, "Part not found."

    def remove_stock(self, part_id, quantity, user_id=None, cursor=None):
        """Removes a quantity from a part's stock."""
        part = Part.get_by_id(part_id)
        if part:
            if part.stock >= quantity:
                part.stock -= quantity
                part.save(cursor=cursor)
                if self.notification_manager:
                    self.notification_manager.check_low_stock(part.id, part.stock, part.min_stock)
                return True, f"Stock for '{part.name}' updated to {part.stock}."
            else:
                return False, f"Not enough stock for '{part.name}'. Available: {part.stock}."
        return False, "Part not found."

    def get_parts_below_min_stock(self):
        """Returns a list of parts with stock below minimum."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM parts WHERE stock <= min_stock")
        rows = cursor.fetchall()
        conn.close()
        return [Part(**dict(row)) for row in rows]

