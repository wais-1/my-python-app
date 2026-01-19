import sys
import random
import os
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QStackedWidget, QLabel,
                             QComboBox, QLineEdit, QTextEdit, QDateEdit, 
                             QFileDialog, QMessageBox, QScrollArea, QGridLayout,
                             QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QPixmap

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from peewee import *
import xlsxwriter

# Настройки подключения
DB_CONFIG = {
    'host': 'pma.tikhomirova.net',
    'user': 'root',
    'password': '123',
    'database': 'antiviruss'
}

# База данных MySQL
db = MySQLDatabase(
    DB_CONFIG['database'],
    host=DB_CONFIG['host'],
    user=DB_CONFIG['user'],
    password=DB_CONFIG['password'],
)

def fix_database_structure():
    """Проверяет и исправляет структуру базы данных"""
    try:
        cursor = db.execute_sql("SHOW TABLES")
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"Существующие таблицы: {existing_tables}")
        
        # Исправляем таблицу signatures
        if 'signatures' in existing_tables:
            cursor = db.execute_sql("DESCRIBE signatures")
            columns = [row[0] for row in cursor.fetchall()]
            print(f"Столбцы таблицы signatures: {columns}")
            
            if 'manufacturer_id' in columns:
                cursor = db.execute_sql("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'signatures' AND COLUMN_NAME = 'manufacturer_id'")
                result = cursor.fetchone()
                if result:
                    current_type = result[0]
                    
                    if current_type.upper() != 'INT':
                        print("Исправляем тип manufacturer_id на INT в таблице signatures...")
                        try:
                            # Сначала удаляем старый столбец
                            db.execute_sql("ALTER TABLE signatures DROP COLUMN manufacturer_id")
                            # Добавляем новый с правильным типом
                            db.execute_sql("ALTER TABLE signatures ADD COLUMN manufacturer_id INT")
                            # Добавляем внешний ключ
                            db.execute_sql("ALTER TABLE signatures ADD FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id)")
                            print("Столбец manufacturer_id исправлен на INT в таблице signatures")
                        except Exception as e:
                            print(f"Ошибка при исправлении столбца в signatures: {e}")
        
        # Исправляем таблицу products
        if 'products' in existing_tables:
            cursor = db.execute_sql("DESCRIBE products")
            columns = [row[0] for row in cursor.fetchall()]
            print(f"Столбцы таблицы products: {columns}")
            
            # Проверяем наличие manufacturer_id
            if 'manufacturer_id' not in columns:
                print("Добавляем столбец manufacturer_id в таблицу products...")
                try:
                    db.execute_sql("ALTER TABLE products ADD COLUMN manufacturer_id INT")
                    # Добавляем внешний ключ
                    db.execute_sql("ALTER TABLE products ADD FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id)")
                    print("Столбец manufacturer_id добавлен в таблицу products")
                    
                    # Если есть существующие записи, устанавливаем значение по умолчанию
                    try:
                        first_manufacturer = Manufacturer.select().first()
                        if first_manufacturer:
                            db.execute_sql("UPDATE products SET manufacturer_id = %s", (first_manufacturer.id,))
                            print("Установлен manufacturer_id для существующих записей")
                    except Exception as e:
                        print(f"Ошибка при обновлении существующих записей: {e}")
                        
                except Exception as e:
                    print(f"Ошибка при добавлении столбца в products: {e}")
        
        return True
    except Exception as e:
        print(f"Ошибка при проверке структуры БД: {e}")
        return False

def initialize_database():
    global db
    
    try:
        # Закрываем существующее подключение, если есть
        if db.is_connection_usable():
            db.close()
        
        # Создаем новое подключение
        db.connect()
        print("Успешное подключение к MySQL")
        
    except Exception as e:
        print(f"Ошибка подключения к MySQL: {e}")
        
        # Пробуем подключиться без создания базы данных
        try:
            # Просто переподключаемся к существующей базе
            db.connect()
            print("Переподключение к MySQL успешно")
        except Exception as e2:
            print(f"Не удалось подключиться к базе данных: {e2}")
            # Создаем QMessageBox, но только если QApplication уже создан
            try:
                from PyQt6.QtWidgets import QMessageBox, QApplication
                app = QApplication.instance()
                if app is not None:
                    QMessageBox.critical(None, "Ошибка базы данных", 
                                       f"Не удалось подключиться к базе данных:\n{e2}")
            except:
                pass
            return False
    
    # Сначала проверяем и исправляем структуру базы данных
    if not fix_database_structure():
        print("Предупреждение: Не удалось проверить/исправить структуру БД")
    
    # Создаем таблицы, если они не существуют (без удаления существующих)
    try:
        # Создаем таблицы только если они не существуют
        db.create_tables([Manufacturer, Malware, Product, Signature], safe=True)
        print("Таблицы успешно созданы или уже существуют")
    except Exception as e:
        print(f"Ошибка создания таблиц: {e}")
        return False
    
    # Создаем тестовые данные только если таблицы пустые
    try:
        # Проверяем, есть ли уже данные в таблицах
        if Manufacturer.select().count() == 0:
            create_sample_data()
            print("Тестовые данные успешно созданы")
        else:
            print("В базе данных уже есть данные, тестовые данные не создаются")
    except Exception as e:
        print(f"Ошибка создания тестовых данных: {e}")
    
    return True

# Модели данных
class BaseModel(Model):
    class Meta:
        database = db

class Manufacturer(BaseModel):
    name = CharField()
    description = TextField()
    country = CharField()
    website = CharField()
    image_path = CharField(null=True)
    creation_date = DateField()
    manufacturer_id = CharField(unique=True)
    
    class Meta:
        table_name = 'manufacturers'

class Product(BaseModel):
    product_id = CharField(unique=True)
    name = CharField()
    description = TextField()
    version = CharField()
    release_date = DateField()
    update_size = CharField()
    image_path = CharField(null=True)
    manufacturer = ForeignKeyField(Manufacturer, backref='products', on_delete='CASCADE')
    
    class Meta:
        table_name = 'products'

class Malware(BaseModel):
    malware_id = CharField(unique=True)
    name = CharField()
    description = TextField()
    threat_level = CharField()
    discovery_date = DateField()
    malware_type = CharField()
    
    class Meta:
        table_name = 'malware'

class Signature(BaseModel):
    signature_id = CharField(unique=True)
    name = CharField()
    data = TextField()
    creation_date = DateField()
    malware = ForeignKeyField(Malware, backref='signatures', on_delete='CASCADE')
    manufacturer = ForeignKeyField(Manufacturer, backref='signatures', on_delete='CASCADE', null=True)
    
    class Meta:
        table_name = 'signatures'

def create_sample_data():
    """Создаем тестовые данные"""
    # Проверяем, есть ли уже производители
    if Manufacturer.select().count() == 0:
        manufacturers_data = [
            {
                'name': 'Kaspersky Lab',
                'description': 'Российская компания, специализирующаяся на разработке систем защиты от киберугроз',
                'country': 'Россия',
                'website': 'https://www.kaspersky.ru',
                'manufacturer_id': 'MAN-0001',
                'creation_date': datetime.now().date()
            },
            {
                'name': 'Norton',
                'description': 'Американская компания, один из пионеров антивирусной индустрии',
                'country': 'США',
                'website': 'https://www.norton.com',
                'manufacturer_id': 'MAN-0002',
                'creation_date': datetime.now().date()
            },
            {
                'name': 'Bitdefender',
                'description': 'Румынская компания, известная своими технологиями машинного обучения',
                'country': 'Румыния',
                'website': 'https://www.bitdefender.com',
                'manufacturer_id': 'MAN-0003',
                'creation_date': datetime.now().date()
            }
        ]

        for data in manufacturers_data:
            try:
                Manufacturer.create(**data)
                print(f"Создан производитель: {data['name']}")
            except Exception as e:
                print(f"Ошибка создания производителя {data['name']}: {e}")

    # Создаем тестовые данные для вредоносных программ
    if Malware.select().count() == 0:
        malware_data = [
            {
                'malware_id': 'MAL-0001',
                'name': 'Trojan.Win32.Generic',
                'description': 'Троянская программа, скрытно устанавливающая вредоносное ПО',
                'threat_level': 'Высокий',
                'discovery_date': datetime.now().date(),
                'malware_type': 'Троян'
            },
            {
                'malware_id': 'MAL-0002',
                'name': 'WannaCry',
                'description': 'Шифровальщик, атаковавший системы по всему миру в 2017 году',
                'threat_level': 'Критический',
                'discovery_date': datetime.now().date(),
                'malware_type': 'Рансомвер'
            }
        ]

        for data in malware_data:
            try:
                Malware.create(**data)
                print(f"Создана вредоносная программа: {data['name']}")
            except Exception as e:
                print(f"Ошибка создания вредоносной программы {data['name']}: {e}")

    # Создаем тестовые данные для сигнатур
    if Signature.select().count() == 0 and Malware.select().count() > 0:
        malware = Malware.select().first()
        manufacturer = Manufacturer.select().first()
        signature_data = [
            {
                'signature_id': 'SIG-0001',
                'name': 'Trojan.Generic Signature',
                'data': '4D5A90000300000004000000FFFF0000',
                'creation_date': datetime.now().date(),
                'malware': malware,
                'manufacturer': manufacturer
            }
        ]

        for data in signature_data:
            try:
                Signature.create(**data)
                print(f"Создана сигнатура: {data['name']}")
            except Exception as e:
                print(f"Ошибка создания сигнатуры {data['name']}: {e}")

# Инициализируем базу данных при импорте
db_initialized = initialize_database()

# МОДУЛЬ ЭКСПОРТА В EXCEL
class ExcelExporter:
    def __init__(self, filename="antivirus_report.xlsx"):
        self.filename = filename
    
    def export_all_data(self):
        """Экспорт всех данных проекта в Excel"""
        try:
            workbook = xlsxwriter.Workbook(self.filename)
            
            # Создаем обязательные листы в правильном порядке
            self._create_project_data_sheet(workbook)
            self._create_analytics_sheet(workbook)  # Аналитика должна быть второй
            self._create_visualization_sheet(workbook)
            
            workbook.close()
            return True, self.filename
        except Exception as e:
            print(f"Ошибка при экспорте: {e}")
            import traceback
            print(f"Подробности ошибки: {traceback.format_exc()}")
            return False, str(e)
    
    def _create_project_data_sheet(self, workbook):
        """Лист 1: Данные проекта"""
        worksheet = workbook.add_worksheet('Данные проекта')
        
        # Форматы (остаются те же)
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#366092', 'font_color': 'white', 'border': 1
        })
        
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        
        section_format = workbook.add_format({
            'bold': True, 'font_size': 12, 'bg_color': '#E6E6E6', 'border': 1,
            'align': 'center'
        })
        
        cell_format = workbook.add_format({'border': 1, 'text_wrap': True})
        center_format = workbook.add_format({'border': 1, 'align': 'center'})
        date_format = workbook.add_format({'border': 1, 'num_format': 'dd.mm.yyyy'})
        
        # Заголовок отчета
        worksheet.merge_range('A1:H1', 'База данных вирусов и антивирусных сигнатур', title_format)
        worksheet.merge_range('A2:H2', 'Тихомирова Дарья Игоревна', title_format)
        
        current_row = 4
        
        # Данные производителей
        current_row = self._add_manufacturers_data(worksheet, workbook, current_row, section_format, header_format, cell_format, center_format, date_format)
        
        # Добавляем пустую строку между секциями
        current_row += 1
        # Данные продуктов
        current_row = self._add_products_data(worksheet, workbook, current_row, section_format, header_format, cell_format, center_format, date_format)
        
        # Добавляем пустую строку между секциями
        current_row += 1
        # Данные вредоносных программ
        current_row = self._add_malware_data(worksheet, workbook, current_row, section_format, header_format, cell_format, center_format, date_format)
        
        # Добавляем пустую строку между секциями
        current_row += 1
        # Данные сигнатур
        current_row = self._add_signatures_data(worksheet, workbook, current_row, section_format, header_format, cell_format, center_format, date_format)
        
        # Настраиваем ширину колонок
        worksheet.set_column('A:A', 12)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 15)
        worksheet.set_column('F:F', 12)
        worksheet.set_column('G:G', 30)
        worksheet.set_column('H:H', 15)
        
        # Включаем заморозку для заголовков
        worksheet.freeze_panes(3, 0)
    
    def _add_manufacturers_data(self, worksheet, workbook, start_row, section_format, header_format, cell_format, center_format, date_format):
        """Добавляем данные производителей и возвращает следующую строку"""
        worksheet.merge_range(f'A{start_row}:H{start_row}', 'ПРОИЗВОДИТЕЛИ АНТИВИРУСОВ', section_format)
        
        headers = ['ID', 'Название', 'Страна', 'Веб-сайт', 'Дата создания', 'Кол-во продуктов', 'Описание']
        for col, header in enumerate(headers):
            worksheet.write(start_row + 1, col, header, header_format)
        
        manufacturers = Manufacturer.select()
        current_row = start_row + 2
        
        for manufacturer in manufacturers:
            products_count = Product.select().where(Product.manufacturer == manufacturer).count()
            
            worksheet.write(current_row, 0, manufacturer.manufacturer_id, center_format)
            worksheet.write(current_row, 1, manufacturer.name, cell_format)
            worksheet.write(current_row, 2, manufacturer.country, cell_format)
            worksheet.write(current_row, 3, manufacturer.website, cell_format)
            worksheet.write(current_row, 4, manufacturer.creation_date, date_format)
            worksheet.write(current_row, 5, products_count, center_format)
            worksheet.write(current_row, 6, manufacturer.description, cell_format)
            current_row += 1
        
        return current_row

    def _add_products_data(self, worksheet, workbook, start_row, section_format, header_format, cell_format, center_format, date_format):
        """Добавляем данные продуктов и возвращает следующую строку"""
        worksheet.merge_range(f'A{start_row}:H{start_row}', 'АНТИВИРУСНЫЕ ПРОГРАММЫ', section_format)
        
        headers = ['ID', 'Название', 'Производитель', 'Версия', 'Размер обновления', 'Дата выпуска', 'Описание']
        for col, header in enumerate(headers):
            worksheet.write(start_row + 1, col, header, header_format)
        
        products = Product.select()
        current_row = start_row + 2
        
        for product in products:
            worksheet.write(current_row, 0, product.product_id, center_format)
            worksheet.write(current_row, 1, product.name, cell_format)
            worksheet.write(current_row, 2, product.manufacturer.name, cell_format)
            worksheet.write(current_row, 3, product.version, center_format)
            worksheet.write(current_row, 4, product.update_size, center_format)
            worksheet.write(current_row, 5, product.release_date, date_format)
            worksheet.write(current_row, 6, product.description, cell_format)
            current_row += 1
        
        return current_row

    def _add_malware_data(self, worksheet, workbook, start_row, section_format, header_format, cell_format, center_format, date_format):
        """Добавляем данные вредоносных программ и возвращает следующую строку"""
        worksheet.merge_range(f'A{start_row}:H{start_row}', 'ВРЕДОНОСНЫЕ ПРОГРАММЫ', section_format)
        
        headers = ['ID', 'Название', 'Тип', 'Уровень опасности', 'Дата обнаружения', 'Кол-во сигнатур', 'Описание']
        for col, header in enumerate(headers):
            worksheet.write(start_row + 1, col, header, header_format)
        
        malware_list = Malware.select()
        current_row = start_row + 2
        
        for malware in malware_list:
            signatures_count = Signature.select().where(Signature.malware == malware).count()
            
            # Условное форматирование для уровня опасности
            threat_format = cell_format
            if malware.threat_level == 'Критический':
                threat_format = workbook.add_format({'border': 1, 'bg_color': '#FF0000', 'font_color': 'white'})
            elif malware.threat_level == 'Высокий':
                threat_format = workbook.add_format({'border': 1, 'bg_color': '#FF6B6B'})
            elif malware.threat_level == 'Средний':
                threat_format = workbook.add_format({'border': 1, 'bg_color': '#FFD966'})
            else:
                threat_format = workbook.add_format({'border': 1, 'bg_color': '#A9D08E'})
            
            worksheet.write(current_row, 0, malware.malware_id, center_format)
            worksheet.write(current_row, 1, malware.name, cell_format)
            worksheet.write(current_row, 2, malware.malware_type, cell_format)
            worksheet.write(current_row, 3, malware.threat_level, threat_format)
            worksheet.write(current_row, 4, malware.discovery_date, date_format)
            worksheet.write(current_row, 5, signatures_count, center_format)
            worksheet.write(current_row, 6, malware.description, cell_format)
            current_row += 1
        
        return current_row

    def _add_signatures_data(self, worksheet, workbook, start_row, section_format, header_format, cell_format, center_format, date_format):
        """Добавляем данные сигнатур и возвращает следующую строку"""
        worksheet.merge_range(f'A{start_row}:H{start_row}', 'СИГНАТУРЫ ОБНАРУЖЕНИЯ', section_format)
        
        headers = ['ID', 'Название', 'Вредоносная программа', 'Производитель', 'Дата создания', 'Данные сигнатуры']
        for col, header in enumerate(headers):
            worksheet.write(start_row + 1, col, header, header_format)
        
        signatures = Signature.select()
        current_row = start_row + 2
        
        for signature in signatures:
            manufacturer_name = signature.manufacturer.name if signature.manufacturer else "Не указан"
            worksheet.write(current_row, 0, signature.signature_id, center_format)
            worksheet.write(current_row, 1, signature.name, cell_format)
            worksheet.write(current_row, 2, f"{signature.malware.malware_id} - {signature.malware.name}", cell_format)
            worksheet.write(current_row, 3, manufacturer_name, cell_format)
            worksheet.write(current_row, 4, signature.creation_date, date_format)
            worksheet.write(current_row, 5, signature.data, cell_format)
            current_row += 1
        
        return current_row
    
    def _create_analytics_sheet(self, workbook):
        """Лист 2: Аналитика - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        worksheet = workbook.add_worksheet('Аналитика')

        # Устанавливаем ширину колонок
        worksheet.set_column('A:A', 25)  # Производитель/Тип ВП
        worksheet.set_column('B:B', 15)  # Страна/Количество  
        worksheet.set_column('C:C', 18)  # Кол-во продуктов/Уровень опасности
        worksheet.set_column('D:D', 15)  # Доля рынка/Средний возраст
        worksheet.set_column('E:E', 12)  # Для диаграмм
        worksheet.set_column('F:F', 15)  # Для диаграмм
            
        # Форматы
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#366092', 'font_color': 'white', 'border': 1
        })
        
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#5B9BD5', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        
        # Заголовок
        worksheet.merge_range('A1:F1', 'АНАЛИТИКА ДАННЫХ АНТИВИРУСНОЙ БАЗЫ', title_format)
        
        # Статистика по производителям
        current_row = self._add_manufacturer_stats(worksheet, workbook, 3, header_format)
        
        # Статистика по вредоносным программам
        current_row = self._add_malware_stats(worksheet, workbook, current_row + 2, header_format)
        
        # Сводная таблица
        current_row = self._add_summary_table(worksheet, workbook, current_row + 2, header_format)
        
        # Диаграммы
        self._add_charts(worksheet, workbook, current_row)

    def _add_manufacturer_stats(self, worksheet, workbook, start_row, header_format):
        """Статистика по производителям - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        worksheet.merge_range(f'A{start_row}:D{start_row}', 'СТАТИСТИКА ПРОИЗВОДИТЕЛЕЙ', 
                            workbook.add_format({'bold': True, 'font_size': 12, 'bg_color': '#E6E6E6', 'border': 1}))
        
        headers = ['Производитель', 'Количество продуктов', 'Доля рынка (%)', 'Страна']
        for col, header in enumerate(headers):
            worksheet.write(start_row + 1, col, header, header_format)
        
        manufacturers = Manufacturer.select()
        total_products = Product.select().count()
        
        # Форматы
        int_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0'})
        percent_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0.00%'})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        
        current_row = start_row + 2
        for manufacturer in manufacturers:
            products_count = Product.select().where(Product.manufacturer == manufacturer).count()
            market_share = (products_count / total_products) if total_products > 0 else 0
            
            worksheet.write(current_row, 0, manufacturer.name, text_format)
            worksheet.write(current_row, 1, products_count, int_format)
            worksheet.write(current_row, 2, market_share, percent_format)
            worksheet.write(current_row, 3, manufacturer.country, text_format)
            current_row += 1
        
        return current_row

    def _add_malware_stats(self, worksheet, workbook, start_row, header_format):
        """Статистика по вредоносным программам - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        worksheet.merge_range(f'A{start_row}:D{start_row}', 'СТАТИСТИКА ВРЕДОНОСНЫХ ПРОГРАММ', 
                            workbook.add_format({'bold': True, 'font_size': 12, 'bg_color': '#E6E6E6', 'border': 1}))
        
        headers = ['Тип ВП', 'Количество', 'Уровень опасности', 'Средний возраст (дней)']
        for col, header in enumerate(headers):
            worksheet.write(start_row + 1, col, header, header_format)
        
        # Форматы
        int_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0'})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        
        # Группировка по типам
        from peewee import fn
        malware_stats = (Malware
                        .select(Malware.malware_type, fn.COUNT(Malware.id).alias('count'))
                        .group_by(Malware.malware_type))
        
        today = datetime.now().date()
        
        current_row = start_row + 2
        for stat in malware_stats:
            # Находим самый распространенный уровень опасности для этого типа
            common_threat = (Malware
                        .select(Malware.threat_level)
                        .where(Malware.malware_type == stat.malware_type)
                        .group_by(Malware.threat_level)
                        .order_by(fn.COUNT(Malware.id).desc())
                        .first())
            
            # Вычисляем средний возраст
            try:
                discovery_dates = (Malware
                                .select(Malware.discovery_date)
                                .where(Malware.malware_type == stat.malware_type))
                
                total_days = 0
                count = 0
                
                for malware in discovery_dates:
                    if malware.discovery_date:
                        days_diff = (today - malware.discovery_date).days
                        total_days += days_diff
                        count += 1
                
                avg_age = total_days / count if count > 0 else 0
            except Exception as e:
                print(f"Ошибка расчета среднего возраста: {e}")
                avg_age = 0
            
            worksheet.write(current_row, 0, stat.malware_type, text_format)
            worksheet.write(current_row, 1, stat.count, int_format)
            worksheet.write(current_row, 2, common_threat.threat_level if common_threat else 'Н/Д', text_format)
            worksheet.write(current_row, 3, int(avg_age), int_format)
            current_row += 1
        
        return current_row

    def _add_summary_table(self, worksheet, workbook, start_row, header_format):
        """Сводная таблица - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        worksheet.merge_range(f'A{start_row}:C{start_row}', 'СВОДНАЯ СТАТИСТИКА', 
                            workbook.add_format({'bold': True, 'font_size': 12, 'bg_color': '#E6E6E6', 'border': 1}))
        
        headers = ['Показатель', 'Значение', 'Примечание']
        for col, header in enumerate(headers):
            worksheet.write(start_row + 1, col, header, header_format)
        
        # Получаем актуальные данные
        total_manufacturers = Manufacturer.select().count()
        total_products = Product.select().count()
        total_malware = Malware.select().count()
        total_signatures = Signature.select().count()
        countries_count = len(set(m.country for m in Manufacturer.select()))
        malware_types = len(set(m.malware_type for m in Malware.select()))
        
        # Получаем распределение по уровням опасности
        threat_levels = {
            'Критический': Malware.select().where(Malware.threat_level == 'Критический').count(),
            'Высокий': Malware.select().where(Malware.threat_level == 'Высокий').count(),
            'Средний': Malware.select().where(Malware.threat_level == 'Средний').count(),
            'Низкий': Malware.select().where(Malware.threat_level == 'Низкий').count()
        }
        
        stats = [
            ('Всего производителей', total_manufacturers, 'Уникальных компаний'),
            ('Всего антивирусов', total_products, 'Записей в каталоге'),
            ('Всего вредоносных программ', total_malware, 'Известных ВП'),
            ('Всего сигнатур', total_signatures, 'Шаблонов обнаружения'),
            ('Страны производителей', countries_count, 'Уникальных стран'),
            ('Типы вредоносных программ', malware_types, 'Категорий ВП'),
            ('', '', ''),  # Пустая строка для разделения
            ('Уровни опасности:', '', ''),
            ('• Критический', threat_levels['Критический'], ''),
            ('• Высокий', threat_levels['Высокий'], ''),
            ('• Средний', threat_levels['Средний'], ''),
            ('• Низкий', threat_levels['Низкий'], '')
        ]
        
        # Форматы
        int_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0'})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        bold_format = workbook.add_format({'border': 1, 'align': 'left', 'bold': True})
        
        current_row = start_row + 2
        for indicator, value, note in stats:
            if indicator == 'Уровни опасности:':
                worksheet.write(current_row, 0, indicator, bold_format)
            elif indicator.startswith('•'):
                worksheet.write(current_row, 0, indicator, text_format)
                if value != '':
                    worksheet.write(current_row, 1, value, int_format)
            else:
                worksheet.write(current_row, 0, indicator, text_format)
                if value != '':
                    worksheet.write(current_row, 1, value, int_format)
            
            worksheet.write(current_row, 2, note, text_format)
            current_row += 1
        
        return current_row

    def _add_charts(self, worksheet, workbook, start_row):
        """Добавляем диаграммы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Диаграмма 1: Распределение продуктов по производителям
            chart1 = workbook.add_chart({'type': 'column'})
            
            # Данные для диаграммы
            manufacturers = Manufacturer.select()
            
            # Записываем данные для диаграммы
            data_start_row = 4
            for i, manufacturer in enumerate(manufacturers, start=data_start_row):
                products_count = Product.select().where(Product.manufacturer == manufacturer).count()
                worksheet.write(i, 5, manufacturer.name)  # Колонка F
                worksheet.write(i, 6, products_count)     # Колонка G
            
            chart1.add_series({
                'name': 'Количество продуктов',
                'categories': f'=Аналитика!$F${data_start_row + 1}:$F${data_start_row + len(manufacturers)}',
                'values': f'=Аналитика!$G${data_start_row + 1}:$G${data_start_row + len(manufacturers)}',
            })
            
            chart1.set_title({'name': 'Распределение продуктов по производителям'})
            chart1.set_x_axis({'name': 'Производители'})
            chart1.set_y_axis({'name': 'Количество продуктов'})
            
            # Позиционируем диаграмму
            worksheet.insert_chart(f'E{data_start_row}', chart1, {'x_offset': 25, 'y_offset': 10})
            
            # Диаграмма 2: Распределение ВП по уровням опасности
            chart2 = workbook.add_chart({'type': 'pie'})
            
            # Получаем данные по уровням опасности
            threat_levels = ['Критический', 'Высокий', 'Средний', 'Низкий']
            
            threat_start_row = start_row + 5
            for i, level in enumerate(threat_levels, start=threat_start_row):
                count = Malware.select().where(Malware.threat_level == level).count()
                worksheet.write(i, 5, level)   # Колонка F
                worksheet.write(i, 6, count)   # Колонка G
            
            chart2.add_series({
                'name': 'Уровни опасности',
                'categories': f'=Аналитика!$F${threat_start_row + 1}:$F${threat_start_row + len(threat_levels)}',
                'values': f'=Аналитика!$G${threat_start_row + 1}:$G${threat_start_row + len(threat_levels)}',

            })
            
            chart2.set_title({'name': 'Распределение ВП по уровням опасности'})
            
            # Позиционируем вторую диаграмму
            worksheet.insert_chart(f'E{threat_start_row}', chart2, {'x_offset': 25, 'y_offset': 10})
            
        except Exception as e:
            print(f"Ошибка создания диаграмм: {e}")
    
    def _create_visualization_sheet(self, workbook):
        """Лист 3: Визуализация"""
        worksheet = workbook.add_worksheet('Визуализация')
        
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#366092', 'font_color': 'white'
        })
        
        worksheet.merge_range('A1:F1', 'ВИЗУАЛИЗАЦИЯ ДАННЫХ АНТИВИРУСНОЙ БАЗЫ', title_format)
        
        # Инфографика - ключевые показатели
        self._add_infographics(worksheet, workbook)
        
        # Дополнительные графики
        self._add_additional_charts(worksheet, workbook)
    
    def _add_infographics(self, worksheet, workbook):
        """Добавляем инфографику"""
        # Ключевые показатели в стиле инфографики
        indicators = [
            ('Всего записей в базе', 
             f"{Product.select().count() + Malware.select().count() + Signature.select().count()}",
             "Общее количество объектов"),
            ('Антивирусных программ', 
             f"{Product.select().count()}",
             "Записей в каталоге"),
            ('Вредоносных программ', 
             f"{Malware.select().count()}",
             "Известных угроз"),
            ('Сигнатуры обнаружения', 
             f"{Signature.select().count()}",
             "Шаблонов для защиты"),
            ('Производителей', 
             f"{Manufacturer.select().count()}",
             "Компаний из разных стран"),
            ('Критических угроз', 
             f"{Malware.select().where(Malware.threat_level == 'Критический').count()}",
             "Высокоприоритетных ВП")
        ]
        
        # Создаем красивую сетку для инфографики
        box_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#F2F2F2', 'text_wrap': True
        })
        
        value_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#E6F0FF'
        })
        
        desc_format = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'italic': True,
            'border': 1, 'bg_color': '#F2F2F2'
        })
        
        row = 3
        col = 0
        for icon, value, description in indicators:
            # Иконка и название
            worksheet.merge_range(row, col, row, col + 1, icon, box_format)
            # Значение
            worksheet.merge_range(row + 1, col, row + 1, col + 1, value, value_format)
            # Описание
            worksheet.merge_range(row + 2, col, row + 2, col + 1, description, desc_format)
            
            col += 2
            if col >= 6:  # 3 колонки в ряду
                col = 0
                row += 4
    
    def _add_additional_charts(self, worksheet, workbook):
        """Добавляем дополнительные графики"""
        # Линейный график: Динамика по датам
        chart3 = workbook.add_chart({'type': 'line'})
        
        # Группируем продукты по годам выпуска
        from peewee import fn
        product_years = (Product
                        .select(fn.YEAR(Product.release_date).alias('year'), 
                            fn.COUNT(Product.id).alias('count'))
                        .where(Product.release_date.is_null(False))
                        .group_by(fn.YEAR(Product.release_date))
                        .order_by(fn.YEAR(Product.release_date)))
        
        # Подготавливаем данные
        years_data = []
        for stat in product_years:
            if stat.year:
                years_data.append([stat.year, stat.count])
        
        # Записываем данные на лист
        data_start_row = 30
        if years_data:
            for i, (year, count) in enumerate(years_data):
                worksheet.write(data_start_row + i, 0, year)
                worksheet.write(data_start_row + i, 1, count)
            
            chart3.add_series({
                'name': 'Выпуск антивирусов',
                'categories': f'=Визуализация!$A${data_start_row + 1}:$A${data_start_row + len(years_data)}',
                'values': f'=Визуализация!$B${data_start_row + 1}:$B${data_start_row + len(years_data)}',
                'marker': {'type': 'circle', 'size': 6}
            })
            
            chart3.set_title({'name': 'Динамика выпуска антивирусов по годам'})
            chart3.set_x_axis({'name': 'Год'})
            chart3.set_y_axis({'name': 'Количество выпусков'})
            
            worksheet.insert_chart('A15', chart3)
        else:
            # Если нет данных, создаем заглушку
            worksheet.write(data_start_row, 0, "Нет данных для построения графика")


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)
        self.setParent(parent)

# Диалоги для редактирования вредоносных программ и сигнатур
class EditMalwareDialog(QDialog):
    def __init__(self, malware, parent=None):
        super().__init__(parent)
        self.malware = malware
        self.parent = parent
        self.setWindowTitle(f"Редактирование ВП: {malware.name}")
        self.setModal(True)
        self.setFixedSize(500, 500)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        # ID ВП (только для чтения)
        form_layout.addWidget(QLabel(), 0, 0)
        self.malware_id_input = QLineEdit(self.malware.malware_id)
        self.malware_id_input.setReadOnly(True)
        self.malware_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.malware_id_input, 0, 1)
        
        # Название
        form_layout.addWidget(QLabel("Название:"), 1, 0)
        self.name_input = QLineEdit(self.malware.name)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.name_input, 1, 1)
        
        # Описание
        form_layout.addWidget(QLabel("Описание:"), 2, 0)
        self.description_input = QTextEdit(self.malware.description)
        self.description_input.setMaximumHeight(100)
        self.description_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.description_input, 2, 1)
        
        # Уровень опасности
        form_layout.addWidget(QLabel("Уровень опасности:"), 3, 0)
        self.threat_level_combo = QComboBox()
        self.threat_level_combo.addItems(["Низкий", "Средний", "Высокий", "Критический"])
        self.threat_level_combo.setCurrentText(self.malware.threat_level)
        self.threat_level_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.threat_level_combo, 3, 1)
        
        # Дата открытия
        form_layout.addWidget(QLabel("Дата открытия:"), 4, 0)
        discovery_date = self.malware.discovery_date
        if isinstance(discovery_date, str):
            qdate = QDate.fromString(discovery_date, "yyyy-MM-dd")
        else:
            qdate = QDate(discovery_date.year, discovery_date.month, discovery_date.day)
        
        self.date_input = QDateEdit(qdate)
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.date_input, 4, 1)
        
        # Тип
        form_layout.addWidget(QLabel("Тип:"), 5, 0)
        self.type_input = QLineEdit(self.malware.malware_type)
        self.type_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.type_input, 5, 1)
        
        layout.addWidget(form_widget)
        
        # Кнопки диалога
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
            QPushButton:hover {
                background-color: #bdbda0;
            }
        """)
        save_btn.clicked.connect(self.save_changes)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addWidget(button_widget)
    
    def save_changes(self):
        if not all([self.name_input.text(), self.description_input.toPlainText(), 
                   self.type_input.text()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        try:
            self.malware.name = self.name_input.text()
            self.malware.description = self.description_input.toPlainText()
            self.malware.threat_level = self.threat_level_combo.currentText()
            self.malware.discovery_date = self.date_input.date().toPyDate()
            self.malware.malware_type = self.type_input.text()
            
            self.malware.save()
            
            QMessageBox.information(self, "Успех", "Вредоносная программа успешно обновлена")
            self.accept()
            
            if self.parent:
                self.parent.load_malware()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить вредоносную программу: {str(e)}")

class EditSignatureDialog(QDialog):
    def __init__(self, signature, parent=None):
        super().__init__(parent)
        self.signature = signature
        self.parent = parent
        self.setWindowTitle(f"Редактирование сигнатуры: {signature.name}")
        self.setModal(True)
        self.setFixedSize(500, 550)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        # ID сигнатуры (только для чтения)
        form_layout.addWidget(QLabel(), 0, 0)
        self.signature_id_input = QLineEdit(self.signature.signature_id)
        self.signature_id_input.setReadOnly(True)
        self.signature_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.signature_id_input, 0, 1)
        
        # Название
        form_layout.addWidget(QLabel("Название:"), 1, 0)
        self.name_input = QLineEdit(self.signature.name)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.name_input, 1, 1)
        
        # Данные
        form_layout.addWidget(QLabel("Данные:"), 2, 0)
        self.data_input = QTextEdit(self.signature.data)
        self.data_input.setMaximumHeight(100)
        self.data_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.data_input, 2, 1)
        
        # Дата создания
        form_layout.addWidget(QLabel("Дата создания:"), 3, 0)
        creation_date = self.signature.creation_date
        if isinstance(creation_date, str):
            qdate = QDate.fromString(creation_date, "yyyy-MM-dd")
        else:
            qdate = QDate(creation_date.year, creation_date.month, creation_date.day)
        
        self.date_input = QDateEdit(qdate)
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.date_input, 3, 1)
        
        # Вредоносная программа
        form_layout.addWidget(QLabel("Вредоносная программа:"), 4, 0)
        self.malware_combo = QComboBox()
        self.load_malware_combo()
        self.malware_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        current_index = self.malware_combo.findData(self.signature.malware.id)
        if current_index >= 0:
            self.malware_combo.setCurrentIndex(current_index)
        form_layout.addWidget(self.malware_combo, 4, 1)
        
        # Производитель
        form_layout.addWidget(QLabel("Производитель:"), 5, 0)
        self.manufacturer_combo = QComboBox()
        self.load_manufacturers_combo()
        self.manufacturer_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        if self.signature.manufacturer:
            current_index = self.manufacturer_combo.findData(self.signature.manufacturer.id)
            if current_index >= 0:
                self.manufacturer_combo.setCurrentIndex(current_index)
        form_layout.addWidget(self.manufacturer_combo, 5, 1)
        
        layout.addWidget(form_widget)
        
        # Кнопки диалога
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
            QPushButton:hover {
                background-color: #bdbda0;
            }
        """)
        save_btn.clicked.connect(self.save_changes)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addWidget(button_widget)
    
    def load_malware_combo(self):
        self.malware_combo.clear()
        try:
            malware_list = Malware.select()
            for malware in malware_list:
                self.malware_combo.addItem(f"{malware.malware_id} - {malware.name}", malware.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить вредоносные программы: {str(e)}")
    
    def load_manufacturers_combo(self):
        self.manufacturer_combo.clear()
        try:
            manufacturers = Manufacturer.select()
            for manufacturer in manufacturers:
                self.manufacturer_combo.addItem(manufacturer.name, manufacturer.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить производителей: {str(e)}")
    
    def save_changes(self):
        if not all([self.name_input.text(), self.data_input.toPlainText()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        try:
            self.signature.name = self.name_input.text()
            self.signature.data = self.data_input.toPlainText()
            self.signature.creation_date = self.date_input.date().toPyDate()
            self.signature.malware_id = self.malware_combo.currentData()
            self.signature.manufacturer_id = self.manufacturer_combo.currentData()
            
            self.signature.save()
            
            QMessageBox.information(self, "Успех", "Сигнатура успешно обновлена")
            self.accept()
            
            if self.parent:
                self.parent.load_signatures()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить сигнатуру: {str(e)}")

# Виджеты карточек для ВП и сигнатур
class MalwareCard(QWidget):
    def __init__(self, malware, parent=None):
        super().__init__(parent)
        self.malware = malware
        self.parent = parent
        self.initUI()
    
    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        self.setLayout(main_layout)
        self.setFixedWidth(320)
        self.setFixedHeight(400)
        
        self.setObjectName("MalwareCard")
        self.setStyleSheet("""
            QWidget#MalwareCard {
                background-color: #000000;
                border: 2px solid #f4f4bd;
                border-radius: 12px;
            }
            QWidget#MalwareCard:hover {
                border: 2px solid #ffffff;
                background-color: #000000;
            }
        """)
        
        # Заголовок
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        id_label = QLabel(f"ID: {self.malware.malware_id}")
        id_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: 400;
                color: #a7d8de;
                background-color: rgba(0, 0, 0, 0.3);
                padding: 2px 6px;
                border-radius: 8px;
            }
        """)
        id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name_label = QLabel(self.malware.name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 400;
                color: #f4f4bd;
                padding: 4px 0px;
                background: transparent;
            }
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        
        header_layout.addWidget(id_label)
        header_layout.addWidget(name_label)
        main_layout.addWidget(header_widget)
        
        # Информация
        info_widget = QWidget()
        info_layout = QGridLayout(info_widget)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(6)
        
        info_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 8px;
            }
        """)
        
        info_style = """
            QLabel {
                color: #e8e8c8;
                font-size: 12px;
                padding: 2px 4px;
                background: transparent;
            }
        """
        
        threat_label = QLabel("Уровень опасности:")
        threat_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        threat_value = QLabel(self.malware.threat_level)
        threat_value.setStyleSheet(info_style)
        
        date_label = QLabel("Дата открытия:")
        date_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        date_value = QLabel(str(self.malware.discovery_date))
        date_value.setStyleSheet(info_style)
        
        type_label = QLabel("Тип:")
        type_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        type_value = QLabel(self.malware.malware_type)
        type_value.setStyleSheet(info_style)
        
        info_layout.addWidget(threat_label, 0, 0)
        info_layout.addWidget(threat_value, 0, 1)
        info_layout.addWidget(date_label, 1, 0)
        info_layout.addWidget(date_value, 1, 1)
        info_layout.addWidget(type_label, 2, 0)
        info_layout.addWidget(type_value, 2, 1)
        
        main_layout.addWidget(info_widget)
        
        # Описание
        desc_widget = QWidget()
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.setContentsMargins(8, 8, 8, 8)
        
        desc_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 8px;
            }
        """)
        
        desc_label = QLabel("Описание:")
        desc_label.setStyleSheet("font-weight: 400; color: #a7d8de; font-size: 12px; background: transparent;")
        
        desc_text = QLabel(self.malware.description)
        desc_text.setStyleSheet("""
            QLabel {
                color: #e8e8c8;
                font-size: 11px;
                background: transparent;
                padding: 6px;
            }
        """)
        desc_text.setWordWrap(True)
        desc_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(desc_text)
        main_layout.addWidget(desc_widget)
        
        # Кнопки
        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        
        edit_btn = QPushButton("Редактировать")
        edit_btn.setFixedHeight(32)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
        """)
        edit_btn.clicked.connect(self.edit_malware)

        delete_btn = QPushButton("Удалить")
        delete_btn.setFixedHeight(32)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8c4a4a;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #9c5a5a;
            }
        """)
        delete_btn.clicked.connect(self.delete_malware)
        
        footer_layout.addWidget(edit_btn)
        footer_layout.addWidget(delete_btn)
        main_layout.addWidget(footer_widget)
    
    def edit_malware(self):
        try:
            dialog = EditMalwareDialog(self.malware, self.parent)
            result = dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог редактирования: {str(e)}")
    
    def delete_malware(self):
        reply = QMessageBox.question(self, "Удаление", 
                                   f"Вы точно хотите удалить ВП '{self.malware.name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Проверяем, есть ли связанные сигнатуры
                signatures_count = Signature.select().where(Signature.malware == self.malware).count()
                if signatures_count > 0:
                    QMessageBox.warning(self, "Ошибка", 
                                      f"Невозможно удалить ВП. У нее есть {signatures_count} связанных сигнатур.")
                    return
                
                self.malware.delete_instance()
                if self.parent:
                    self.parent.load_malware()
                QMessageBox.information(self, "Успех", "Вредоносная программа успешно удалена")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить вредоносную программу: {str(e)}")

class SignatureCard(QWidget):
    def __init__(self, signature, parent=None):
        super().__init__(parent)
        self.signature = signature
        self.parent = parent
        self.initUI()
    
    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        self.setLayout(main_layout)
        self.setFixedWidth(320)
        self.setFixedHeight(400)  # Увеличил высоту для дополнительных кнопок
        
        self.setObjectName("SignatureCard")
        self.setStyleSheet("""
            QWidget#SignatureCard {
                background-color: #000000;
                border: 2px solid #f4f4bd;
                border-radius: 12px;
            }
            QWidget#SignatureCard:hover {
                border: 2px solid #ffffff;
                background-color: #000000;
            }
        """)
        
        # Заголовок
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        id_label = QLabel(f"ID: {self.signature.signature_id}")
        id_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: 400;
                color: #a7d8de;
                background-color: rgba(0, 0, 0, 0.3);
                padding: 2px 6px;
                border-radius: 8px;
            }
        """)
        id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name_label = QLabel(self.signature.name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 400;
                color: #f4f4bd;
                padding: 4px 0px;
                background: transparent;
            }
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        
        header_layout.addWidget(id_label)
        header_layout.addWidget(name_label)
        main_layout.addWidget(header_widget)
        
        # Информация
        info_widget = QWidget()
        info_layout = QGridLayout(info_widget)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(6)
        
        info_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 8px;
            }
        """)
        
        info_style = """
            QLabel {
                color: #e8e8c8;
                font-size: 12px;
                padding: 2px 4px;
                background: transparent;
            }
        """
        
        date_label = QLabel("Дата создания:")
        date_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        date_value = QLabel(str(self.signature.creation_date))
        date_value.setStyleSheet(info_style)
        
        malware_label = QLabel("Вредоносная программа:")
        malware_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        malware_value = QLabel(f"{self.signature.malware.malware_id} - {self.signature.malware.name}")
        malware_value.setStyleSheet(info_style)
        malware_value.setWordWrap(True)
        
        manufacturer_label = QLabel("Производитель:")
        manufacturer_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        manufacturer_value = QLabel(self.signature.manufacturer.name if self.signature.manufacturer else "Не указан")
        manufacturer_value.setStyleSheet(info_style)
        manufacturer_value.setWordWrap(True)
        
        info_layout.addWidget(date_label, 0, 0)
        info_layout.addWidget(date_value, 0, 1)
        info_layout.addWidget(malware_label, 1, 0)
        info_layout.addWidget(malware_value, 1, 1)
        info_layout.addWidget(manufacturer_label, 2, 0)
        info_layout.addWidget(manufacturer_value, 2, 1)
        
        main_layout.addWidget(info_widget)
        
        # Данные
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        data_layout.setContentsMargins(8, 8, 8, 8)
        
        data_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 8px;
            }
        """)
        
        data_label = QLabel("Данные:")
        data_label.setStyleSheet("font-weight: 400; color: #a7d8de; font-size: 12px; background: transparent;")
        
        data_text = QLabel(self.signature.data)
        data_text.setStyleSheet("""
            QLabel {
                color: #e8e8c8;
                font-size: 11px;
                background: transparent;
                padding: 6px;
                font-family: monospace;
            }
        """)
        data_text.setWordWrap(True)
        data_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        data_layout.addWidget(data_label)
        data_layout.addWidget(data_text)
        main_layout.addWidget(data_widget)
        
        # Кнопки
        footer_widget = QWidget()
        footer_layout = QVBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        
        # Верхний ряд кнопок
        top_row_widget = QWidget()
        top_row_layout = QHBoxLayout(top_row_widget)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        
        malware_btn = QPushButton("С какими ВП борется")
        malware_btn.setToolTip("Показать вредоносную программу")
        malware_btn.setFixedHeight(32)
        malware_btn.setStyleSheet("""
            QPushButton {
                background-color: none;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
                border: 1px solid #f4f4bd;
            }
            QPushButton:hover {
                border: 3px solid #f4f4bd;
            }
            QPushButton:pressed {
                background-color: #5c4858;
            }
        """)
        malware_btn.clicked.connect(self.show_malware)
        
        manufacturer_btn = QPushButton("Производитель")
        manufacturer_btn.setToolTip("Информация о производителе")
        manufacturer_btn.setFixedHeight(32)
        manufacturer_btn.setStyleSheet("""
            QPushButton {
                background-color: none;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
                border: 1px solid #f4f4bd;
            }
            QPushButton:hover {
                border: 3px solid #f4f4bd;
            }
            QPushButton:pressed {
                background-color: #5c4858;
            }
        """)
        manufacturer_btn.clicked.connect(self.show_manufacturer)
        
        top_row_layout.addWidget(malware_btn)
        top_row_layout.addWidget(manufacturer_btn)
        
        # Нижний ряд кнопок
        bottom_row_widget = QWidget()
        bottom_row_layout = QHBoxLayout(bottom_row_widget)
        bottom_row_layout.setContentsMargins(0, 0, 0, 0)
        bottom_row_layout.setSpacing(10)
        
        edit_btn = QPushButton("Редактировать")
        edit_btn.setToolTip("Редактировать сигнатуру")
        edit_btn.setFixedHeight(32)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
            QPushButton:pressed {
                background-color: #3a6e7c;
            }
        """)
        edit_btn.clicked.connect(self.edit_signature)

        delete_btn = QPushButton("Удалить")
        delete_btn.setToolTip("Удалить сигнатуру")
        delete_btn.setFixedHeight(32)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8c4a4a;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #9c5a5a;
            }
            QPushButton:pressed {
                background-color: #7c3a3a;
            }
        """)
        delete_btn.clicked.connect(self.delete_signature)
        
        bottom_row_layout.addWidget(edit_btn)
        bottom_row_layout.addWidget(delete_btn)
        
        footer_layout.addWidget(top_row_widget)
        footer_layout.addWidget(bottom_row_widget)
        main_layout.addWidget(footer_widget)
    
    def show_malware(self):
        """Показать страницу с вредоносной программой"""
        try:
            # Создаем страницу для отображения ВП
            malware_page = MalwareDetailPage(self.signature.malware, self.parent)
            self.parent.stacked_widget.addWidget(malware_page)
            self.parent.stacked_widget.setCurrentWidget(malware_page)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть страницу ВП: {str(e)}")
    
    def show_manufacturer(self):
        """Показать страницу с производителем"""
        try:
            if self.signature.manufacturer:
                self.parent.show_manufacturer_detail(self.signature.manufacturer)
            else:
                QMessageBox.information(self, "Информация", "Производитель не указан для этой сигнатуры")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть страницу производителя: {str(e)}")
    
    def edit_signature(self):
        try:
            dialog = EditSignatureDialog(self.signature, self.parent)
            result = dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог редактирования: {str(e)}")
    
    def delete_signature(self):
        reply = QMessageBox.question(self, "Удаление", 
                                   f"Вы точно хотите удалить сигнатуру '{self.signature.name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.signature.delete_instance()
                if self.parent:
                    self.parent.load_signatures()
                QMessageBox.information(self, "Успех", "Сигнатура успешно удалена")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить сигнатуру: {str(e)}")

# Страница деталей вредоносной программы
class MalwareDetailPage(QWidget):
    def __init__(self, malware, parent=None):
        super().__init__(parent)
        self.malware = malware
        self.parent = parent
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        title_label = QLabel(f"Вредоносная программа: {self.malware.name}")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        info_widget = self.create_info_widget()
        layout.addWidget(info_widget)
        
        buttons_widget = self.create_buttons_widget()
        layout.addWidget(buttons_widget)
        
        layout.addStretch()
    
    def create_info_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        id_label = QLabel(f"ID: {self.malware.malware_id}")
        id_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 400;
                color: #a7d8de;
                background-color: rgba(0, 0, 0, 0.3);
                padding: 8px 12px;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(id_label)
        
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(20, 20, 20, 20)
        
        grid_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 12px;
            }
        """)
        
        label_style = """
            QLabel {
                color: #e8e8c8;
                font-size: 14px;
                padding: 8px 4px;
                background: transparent;
            }
        """
        
        bold_label_style = "font-weight: 400; color: #a7d8de; background: transparent;"
        
        grid_layout.addWidget(QLabel("Название:"), 0, 0)
        name_label = QLabel(self.malware.name)
        name_label.setStyleSheet(label_style)
        grid_layout.addWidget(name_label, 0, 1)
        
        grid_layout.addWidget(QLabel("Тип:"), 1, 0)
        type_label = QLabel(self.malware.malware_type)
        type_label.setStyleSheet(label_style)
        grid_layout.addWidget(type_label, 1, 1)
        
        grid_layout.addWidget(QLabel("Уровень опасности:"), 2, 0)
        threat_label = QLabel(self.malware.threat_level)
        threat_label.setStyleSheet(label_style)
        grid_layout.addWidget(threat_label, 2, 1)
        
        grid_layout.addWidget(QLabel("Дата открытия:"), 3, 0)
        date_label = QLabel(str(self.malware.discovery_date))
        date_label.setStyleSheet(label_style)
        grid_layout.addWidget(date_label, 3, 1)
        
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            if item and isinstance(item.widget(), QLabel) and i % 2 == 0:
                item.widget().setStyleSheet(bold_label_style)
        
        layout.addWidget(grid_widget)
        
        desc_label = QLabel("Описание:")
        desc_label.setStyleSheet("font-weight: 400; color: #a7d8de; font-size: 16px; margin-top: 15px;")
        layout.addWidget(desc_label)
        
        desc_text = QLabel(self.malware.description)
        desc_text.setStyleSheet("""
            QLabel {
                color: #e8e8c8;
                font-size: 14px;
                background: transparent;
                padding: 12px;
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 8px;
            }
        """)
        desc_text.setWordWrap(True)
        desc_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(desc_text)
        
        return widget
    
    def create_buttons_widget(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        back_btn = QPushButton("Назад к списку")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        back_btn.clicked.connect(lambda: self.parent.stacked_widget.setCurrentIndex(5))
        
        edit_btn = QPushButton("Редактировать")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        edit_btn.clicked.connect(self.edit_malware)
        
        delete_btn = QPushButton("Удалить")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8c4a4a;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        delete_btn.clicked.connect(self.delete_malware)
        
        next_btn = QPushButton("Далее")
        next_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
        """)
        next_btn.clicked.connect(self.next_malware)
        
        layout.addWidget(back_btn)
        layout.addWidget(edit_btn)
        layout.addWidget(delete_btn)
        layout.addWidget(next_btn)
        
        return widget
    
    def edit_malware(self):
        dialog = EditMalwareDialog(self.malware, self.parent)
        dialog.exec()
    
    def delete_malware(self):
        reply = QMessageBox.question(self, "Удаление", 
                                   f"Вы точно хотите удалить ВП '{self.malware.name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            signatures_count = Signature.select().where(Signature.malware == self.malware).count()
            if signatures_count > 0:
                QMessageBox.warning(self, "Ошибка", 
                                  f"Невозможно удалить ВП. У нее есть {signatures_count} связанных сигнатур.")
                return
            
            try:
                self.malware.delete_instance()
                self.parent.load_malware()
                self.parent.stacked_widget.setCurrentIndex(5)
                QMessageBox.information(self, "Успех", "Вредоносная программа успешно удалена")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить вредоносную программу: {str(e)}")
    
    def next_malware(self):
        malware_list = list(Malware.select().order_by(Malware.malware_id))
        if not malware_list:
            return
        
        current_index = -1
        for i, malware in enumerate(malware_list):
            if malware.id == self.malware.id:
                current_index = i
                break
        
        if current_index == -1:
            return
        
        next_index = (current_index + 1) % len(malware_list)
        next_malware = malware_list[next_index]
        
        malware_page = MalwareDetailPage(next_malware, self.parent)
        self.parent.stacked_widget.addWidget(malware_page)
        self.parent.stacked_widget.setCurrentWidget(malware_page)

class EditProductDialog(QDialog):
    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.product = product
        self.parent = parent
        self.setWindowTitle(f"Редактирование товара: {product.name}")
        self.setModal(True)
        self.setFixedSize(500, 600)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Поля для редактирования
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        # ID товара (только для чтения)
        form_layout.addWidget(QLabel("ID товара:"), 0, 0)
        self.product_id_input = QLineEdit(self.product.product_id)
        self.product_id_input.setReadOnly(True)
        self.product_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.product_id_input, 0, 1)
        
        # Название
        form_layout.addWidget(QLabel("Название:"), 1, 0)
        self.name_input = QLineEdit(self.product.name)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.name_input, 1, 1)
        
        # Описание
        form_layout.addWidget(QLabel("Описание:"), 2, 0)
        self.description_input = QTextEdit(self.product.description)
        self.description_input.setMaximumHeight(100)
        self.description_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.description_input, 2, 1)
        
        # Версия (Цена)
        form_layout.addWidget(QLabel("Цена:"), 3, 0)
        self.version_input = QLineEdit(self.product.version)
        self.version_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.version_input, 3, 1)
        
        # Дата выпуска
        form_layout.addWidget(QLabel("Дата выпуска:"), 4, 0)
        release_date = self.product.release_date
        if isinstance(release_date, str):
            qdate = QDate.fromString(release_date, "yyyy-MM-dd")
        else:
            qdate = QDate(release_date.year, release_date.month, release_date.day)
        
        self.date_input = QDateEdit(qdate)
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.date_input, 4, 1)
        
        # Размер обновления (Рейтинг)
        form_layout.addWidget(QLabel("Рейтинг:"), 5, 0)
        self.size_input = QLineEdit(self.product.update_size)
        self.size_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.size_input, 5, 1)
        
        # Производитель
        form_layout.addWidget(QLabel("Производитель:"), 6, 0)
        self.manufacturer_combo = QComboBox()
        self.load_manufacturers_combo()
        self.manufacturer_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        current_index = self.manufacturer_combo.findData(self.product.manufacturer.id)
        if current_index >= 0:
            self.manufacturer_combo.setCurrentIndex(current_index)
        form_layout.addWidget(self.manufacturer_combo, 6, 1)
        
        # Загрузка изображения
        form_layout.addWidget(QLabel("Изображение:"), 7, 0)
        image_layout = QHBoxLayout()
        self.image_btn = QPushButton("Выбрать изображение")
        self.image_btn.setStyleSheet("""
            QPushButton {
                background-color: #3e6767;
                color: #f4f4bd;
                padding: 8px 15px;
                border-radius: 15px;
                border: 1px solid #f4f4bd;
            }
        """)
        self.image_btn.clicked.connect(self.select_image)
        image_layout.addWidget(self.image_btn)
        
        self.image_label = QLabel(os.path.basename(self.product.image_path) if self.product.image_path else "Не выбрано")
        self.image_label.setStyleSheet("color: #f4f4bd;")
        image_layout.addWidget(self.image_label)
        
        form_layout.addLayout(image_layout, 7, 1)
        
        layout.addWidget(form_widget)
        
        # Кнопки диалога
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
            QPushButton:hover {
                background-color: #bdbda0;
            }
        """)
        save_btn.clicked.connect(self.save_changes)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addWidget(button_widget)
        
        self.image_path = self.product.image_path
    
    def load_manufacturers_combo(self):
        self.manufacturer_combo.clear()
        try:
            manufacturers = Manufacturer.select()
            for manufacturer in manufacturers:
                self.manufacturer_combo.addItem(manufacturer.name, manufacturer.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить производителей: {str(e)}")
    
    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", 
                                                 "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.image_path = file_path
            self.image_label.setText(os.path.basename(file_path))
    
    def save_changes(self):
        if not all([self.name_input.text(), self.description_input.toPlainText(), 
                   self.version_input.text(), self.size_input.text()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        try:
            self.product.name = self.name_input.text()
            self.product.description = self.description_input.toPlainText()
            self.product.version = self.version_input.text()
            self.product.release_date = self.date_input.date().toPyDate()
            self.product.update_size = self.size_input.text()
            self.product.manufacturer_id = self.manufacturer_combo.currentData()
            
            if self.image_path:
                self.product.image_path = self.image_path
            
            self.product.save()
            
            QMessageBox.information(self, "Успех", "Товар успешно обновлен")
            self.accept()
            
            if self.parent:
                self.parent.load_products()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить товар: {str(e)}")

class EditManufacturerDialog(QDialog):
    def __init__(self, manufacturer, parent=None):
        super().__init__(parent)
        self.manufacturer = manufacturer
        self.parent = parent
        self.setWindowTitle(f"Редактирование производителя: {manufacturer.name}")
        self.setModal(True)
        self.setFixedSize(500, 600)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Поля для редактирования
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        # ID производителя (только для чтения)
        form_layout.addWidget(QLabel("ID производителя:"), 0, 0)
        self.manufacturer_id_input = QLineEdit(self.manufacturer.manufacturer_id)
        self.manufacturer_id_input.setReadOnly(True)
        self.manufacturer_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.manufacturer_id_input, 0, 1)
        
        # Название
        form_layout.addWidget(QLabel("Название:"), 1, 0)
        self.name_input = QLineEdit(self.manufacturer.name)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.name_input, 1, 1)
        
        # URL сайта
        form_layout.addWidget(QLabel("URL сайта:"), 2, 0)
        self.website_input = QLineEdit(self.manufacturer.website)
        self.website_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.website_input, 2, 1)
        
        # Страна
        form_layout.addWidget(QLabel("Страна:"), 3, 0)
        self.country_input = QLineEdit(self.manufacturer.country)
        self.country_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.country_input, 3, 1)
        
        # Дата создания
        form_layout.addWidget(QLabel("Дата создания:"), 4, 0)
        creation_date = self.manufacturer.creation_date
        if isinstance(creation_date, str):
            qdate = QDate.fromString(creation_date, "yyyy-MM-dd")
        else:
            qdate = QDate(creation_date.year, creation_date.month, creation_date.day)
        
        self.date_input = QDateEdit(qdate)
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.date_input, 4, 1)
        
        # Описание
        form_layout.addWidget(QLabel("Описание:"), 5, 0)
        self.description_input = QTextEdit(self.manufacturer.description)
        self.description_input.setMaximumHeight(100)
        self.description_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.description_input, 5, 1)
        
        # Загрузка изображения
        form_layout.addWidget(QLabel("Изображение:"), 6, 0)
        image_layout = QHBoxLayout()
        self.image_btn = QPushButton("Выбрать изображение")
        self.image_btn.setStyleSheet("""
            QPushButton {
                background-color: #3e6767;
                color: #f4f4bd;
                padding: 8px 15px;
                border-radius: 15px;
                border: 1px solid #f4f4bd;
            }
        """)
        self.image_btn.clicked.connect(self.select_image)
        image_layout.addWidget(self.image_btn)
        
        self.image_label = QLabel(os.path.basename(self.manufacturer.image_path) if self.manufacturer.image_path else "Не выбрано")
        self.image_label.setStyleSheet("color: #f4f4bd;")
        image_layout.addWidget(self.image_label)
        
        form_layout.addLayout(image_layout, 6, 1)
        
        layout.addWidget(form_widget)
        
        # Кнопки диалога
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
            QPushButton:hover {
                background-color: #bdbda0;
            }
        """)
        save_btn.clicked.connect(self.save_changes)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addWidget(button_widget)
        
        self.image_path = self.manufacturer.image_path
    
    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", 
                                                 "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.image_path = file_path
            self.image_label.setText(os.path.basename(file_path))
    
    def save_changes(self):
        if not all([self.name_input.text(), self.website_input.text(), 
                   self.country_input.text(), self.description_input.toPlainText()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        try:
            self.manufacturer.name = self.name_input.text()
            self.manufacturer.website = self.website_input.text()
            self.manufacturer.country = self.country_input.text()
            self.manufacturer.creation_date = self.date_input.date().toPyDate()
            self.manufacturer.description = self.description_input.toPlainText()
            
            if self.image_path:
                self.manufacturer.image_path = self.image_path
            
            self.manufacturer.save()
            
            QMessageBox.information(self, "Успех", "Производитель успешно обновлен")
            self.accept()
            
            if self.parent:
                self.parent.load_manufacturers()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить производителя: {str(e)}")

class ProductCard(QWidget):
    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.product = product
        self.parent = parent
        self.initUI()
    
    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        header_widget = self.create_header()
        main_layout.addWidget(header_widget)
        
        content_widget = self.create_content()
        main_layout.addWidget(content_widget)
        
        footer_widget = self.create_footer()
        main_layout.addWidget(footer_widget)
        
        self.setLayout(main_layout)
        self.setFixedWidth(320)
        self.setFixedHeight(550)
        
        self.setObjectName("ProductCard")
        self.setStyleSheet("""
            QWidget#ProductCard {
                background-color: #000000;
                border: 2px solid #f4f4bd;
                border-radius: 12px;
            }
            QWidget#ProductCard:hover {
                border: 2px solid #ffffff;
                background-color: #000000;
            }
        """)
    
    def create_header(self):
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        header_widget.setStyleSheet("background: transparent;")
        
        id_label = QLabel(f"ID: {self.product.product_id}")
        id_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: 400;
                color: #a7d8de;
                background-color: rgba(0, 0, 0, 0.3);
                padding: 2px 6px;
                border-radius: 8px;
            }
        """)
        id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name_label = QLabel(self.product.name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 400;
                color: #f4f4bd;
                padding: 4px 0px;
                background: transparent;
            }
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        
        header_layout.addWidget(id_label)
        header_layout.addWidget(name_label)
        
        return header_widget
    
    def create_content(self):
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        content_widget.setStyleSheet("background: transparent;")
        
        if self.product.image_path and os.path.exists(self.product.image_path):
            image_container = QWidget()
            image_layout = QVBoxLayout(image_container)
            image_layout.setContentsMargins(0, 0, 0, 0)
            image_container.setStyleSheet("background: transparent;")
            
            image_label = QLabel()
            pixmap = QPixmap(self.product.image_path)
            pixmap = pixmap.scaled(260, 140, Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    padding: 4px;
                }
            """)
            
            image_layout.addWidget(image_label)
            content_layout.addWidget(image_container)
        
        info_widget = self.create_info_section()
        content_layout.addWidget(info_widget)
        
        desc_widget = self.create_description_section()
        content_layout.addWidget(desc_widget)
        
        return content_widget
    
    def create_info_section(self):
        info_widget = QWidget()
        info_layout = QGridLayout(info_widget)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(6)
        
        info_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 8px;
            }
        """)
        
        info_style = """
            QLabel {
                color: #e8e8c8;
                font-size: 12px;
                padding: 2px 4px;
                background: transparent;
            }
        """
        
        version_label = QLabel("Цена:")
        version_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        version_value = QLabel(self.product.version)
        version_value.setStyleSheet(info_style)
        
        date_label = QLabel("Дата выпуска:")
        date_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        date_value = QLabel(str(self.product.release_date))
        date_value.setStyleSheet(info_style)
        
        size_label = QLabel("Рейтинг:")
        size_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        size_value = QLabel(self.product.update_size)
        size_value.setStyleSheet(info_style)
        
        manufacturer_label = QLabel("Производитель:")
        manufacturer_label.setStyleSheet("font-weight: 400; color: #a7d8de; background: transparent;")
        manufacturer_value = QLabel(self.product.manufacturer.name)
        manufacturer_value.setStyleSheet(info_style)
        manufacturer_value.setWordWrap(True)
        
        info_layout.addWidget(version_label, 0, 0)
        info_layout.addWidget(version_value, 0, 1)
        info_layout.addWidget(date_label, 1, 0)
        info_layout.addWidget(date_value, 1, 1)
        info_layout.addWidget(size_label, 2, 0)
        info_layout.addWidget(size_value, 2, 1)
        info_layout.addWidget(manufacturer_label, 3, 0)
        info_layout.addWidget(manufacturer_value, 3, 1)
        
        return info_widget
    
    def create_description_section(self):
        desc_widget = QWidget()
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.setContentsMargins(8, 8, 8, 8)
        
        desc_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 8px;
            }
        """)
        
        desc_label = QLabel("Описание:")
        desc_label.setStyleSheet("font-weight: 400; color: #a7d8de; font-size: 12px; background: transparent;")
        
        desc_text = QLabel(self.product.description)
        desc_text.setStyleSheet("""
            QLabel {
                color: #e8e8c8;
                font-size: 11px;
                background: transparent;
                padding: 6px;
            }
        """)
        desc_text.setWordWrap(True)
        desc_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(desc_text)
        
        return desc_widget
    
    def create_footer(self):
        footer_widget = QWidget()
        footer_layout = QVBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        
        footer_widget.setStyleSheet("background: transparent;")
        
        top_row_widget = QWidget()
        top_row_layout = QHBoxLayout(top_row_widget)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_widget.setStyleSheet("background: transparent;")
        
        manufacturer_btn = QPushButton("Производитель")
        manufacturer_btn.setToolTip("Информация о производителе")
        manufacturer_btn.setFixedHeight(32)
        manufacturer_btn.setStyleSheet("""
            QPushButton {
                background-color: none;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 12px;
                border: 1px solid #f4f4bd;
            }
            QPushButton:hover {
                border: 3px solid #f4f4bd;
            }
            QPushButton:pressed {
                background-color: #5c4858;
            }
        """)
        manufacturer_btn.clicked.connect(lambda: self.parent.show_manufacturer_detail(self.product.manufacturer))
        
        top_row_layout.addWidget(manufacturer_btn)
        
        bottom_row_widget = QWidget()
        bottom_row_layout = QHBoxLayout(bottom_row_widget)
        bottom_row_layout.setContentsMargins(0, 0, 0, 0)
        bottom_row_layout.setSpacing(10)
        bottom_row_widget.setStyleSheet("background: transparent;")
        
        edit_btn = QPushButton("Редактировать")
        edit_btn.setToolTip("Редактировать товар")
        edit_btn.setFixedHeight(32)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
            QPushButton:pressed {
                background-color: #3a6e7c;
            }
        """)
        edit_btn.clicked.connect(self.edit_product)

        delete_btn = QPushButton("Удалить")
        delete_btn.setToolTip("Удалить товар")
        delete_btn.setFixedHeight(32)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8c4a4a;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #9c5a5a;
            }
            QPushButton:pressed {
                background-color: #7c3a3a;
            }
        """)
        delete_btn.clicked.connect(self.delete_product)
        
        bottom_row_layout.addWidget(edit_btn)
        bottom_row_layout.addWidget(delete_btn)
        
        footer_layout.addWidget(top_row_widget)
        footer_layout.addWidget(bottom_row_widget)
        
        return footer_widget
    
    def edit_product(self):
        try:
            dialog = EditProductDialog(self.product, self.parent)
            result = dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог редактирования: {str(e)}")
    
    def delete_product(self):
        reply = QMessageBox.question(self, "Удаление", 
                                   f"Вы точно хотите удалить товар '{self.product.name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.product.delete_instance()
                if self.parent:
                    self.parent.load_products()
                QMessageBox.information(self, "Успех", "Товар успешно удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить товар: {str(e)}")

class ManufacturerDetailPage(QWidget):
    def __init__(self, manufacturer, parent=None):
        super().__init__(parent)
        self.manufacturer = manufacturer
        self.parent = parent
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        title_label = QLabel(f"Производитель: {self.manufacturer.name}")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        info_widget = self.create_info_widget()
        layout.addWidget(info_widget)
        
        buttons_widget = self.create_buttons_widget()
        layout.addWidget(buttons_widget)
        
        layout.addStretch()
    
    def create_info_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        id_label = QLabel(f"ID: {self.manufacturer.manufacturer_id}")
        id_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 400;
                color: #a7d8de;
                background-color: rgba(0, 0, 0, 0.3);
                padding: 8px 12px;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(id_label)
        
        if self.manufacturer.image_path and os.path.exists(self.manufacturer.image_path):
            image_label = QLabel()
            pixmap = QPixmap(self.manufacturer.image_path)
            pixmap = pixmap.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    padding: 10px;
                    margin-bottom: 10px;
                }
            """)
            layout.addWidget(image_label)
        
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(20, 20, 20, 20)
        
        grid_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 12px;
            }
        """)
        
        label_style = """
            QLabel {
                color: #e8e8c8;
                font-size: 14px;
                padding: 8px 4px;
                background: transparent;
            }
        """
        
        bold_label_style = "font-weight: 400; color: #a7d8de; background: transparent;"
        
        grid_layout.addWidget(QLabel("Название:"), 0, 0)
        name_label = QLabel(self.manufacturer.name)
        name_label.setStyleSheet(label_style)
        grid_layout.addWidget(name_label, 0, 1)
        
        grid_layout.addWidget(QLabel("Страна:"), 1, 0)
        country_label = QLabel(self.manufacturer.country)
        country_label.setStyleSheet(label_style)
        grid_layout.addWidget(country_label, 1, 1)
        
        grid_layout.addWidget(QLabel("Веб-сайт:"), 2, 0)
        website_label = QLabel(f'<a href="{self.manufacturer.website}">{self.manufacturer.website}</a>')
        website_label.setStyleSheet(label_style)
        website_label.setOpenExternalLinks(True)
        grid_layout.addWidget(website_label, 2, 1)
        
        grid_layout.addWidget(QLabel("Дата создания:"), 3, 0)
        date_label = QLabel(str(self.manufacturer.creation_date))
        date_label.setStyleSheet(label_style)
        grid_layout.addWidget(date_label, 3, 1)
        
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            if item and isinstance(item.widget(), QLabel) and i % 2 == 0:
                item.widget().setStyleSheet(bold_label_style)
        
        layout.addWidget(grid_widget)
        
        desc_label = QLabel("Описание:")
        desc_label.setStyleSheet("font-weight: 400; color: #a7d8de; font-size: 16px; margin-top: 15px;")
        layout.addWidget(desc_label)
        
        desc_text = QLabel(self.manufacturer.description)
        desc_text.setStyleSheet("""
            QLabel {
                color: #e8e8c8;
                font-size: 14px;
                background: transparent;
                padding: 12px;
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 8px;
            }
        """)
        desc_text.setWordWrap(True)
        desc_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(desc_text)
        
        return widget
    
    def create_buttons_widget(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        back_btn = QPushButton("Назад к списку")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        back_btn.clicked.connect(lambda: self.parent.stacked_widget.setCurrentIndex(4))
        
        edit_btn = QPushButton("Редактировать")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        edit_btn.clicked.connect(self.edit_manufacturer)
        
        delete_btn = QPushButton("Удалить")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8c4a4a;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        delete_btn.clicked.connect(self.delete_manufacturer)
        
        next_btn = QPushButton("Далее")
        next_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
        """)
        next_btn.clicked.connect(self.next_manufacturer)
        
        layout.addWidget(back_btn)
        layout.addWidget(edit_btn)
        layout.addWidget(delete_btn)
        layout.addWidget(next_btn)
        
        return widget
    
    def edit_manufacturer(self):
        dialog = EditManufacturerDialog(self.manufacturer, self.parent)
        dialog.exec()
    
    def delete_manufacturer(self):
        reply = QMessageBox.question(self, "Удаление", 
                                   f"Вы точно хотите удалить производителя '{self.manufacturer.name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            products_count = Product.select().where(Product.manufacturer == self.manufacturer).count()
            if products_count > 0:
                QMessageBox.warning(self, "Ошибка", 
                                  f"Невозможно удалить производителя. У него есть {products_count} товар(ов).")
                return
            
            try:
                self.manufacturer.delete_instance()
                self.parent.load_manufacturers()
                self.parent.stacked_widget.setCurrentIndex(4)
                QMessageBox.information(self, "Успех", "Производитель успешно удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить производителя: {str(e)}")
    
    def next_manufacturer(self):
        manufacturers = list(Manufacturer.select().order_by(Manufacturer.manufacturer_id))
        if not manufacturers:
            return
        
        current_index = -1
        for i, manuf in enumerate(manufacturers):
            if manuf.id == self.manufacturer.id:
                current_index = i
                break
        
        if current_index == -1:
            return
        
        next_index = (current_index + 1) % len(manufacturers)
        next_manufacturer = manufacturers[next_index]
        
        self.parent.show_manufacturer_detail(next_manufacturer)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Антивирусы - MySQL")
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet("""
            QWidget {
                background-color: #3e6767;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        menu_widget = QWidget()
        menu_widget.setFixedWidth(300)
        menu_widget.setStyleSheet("""
            QWidget {
                background-color: #3e6775;
                border-right: 1px solid #ccc;
            }
        """)
        menu_layout = QVBoxLayout(menu_widget)
        menu_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        menu_layout.setSpacing(10)
        
        self.stacked_widget = QStackedWidget()
        
        self.create_pages()
        self.create_menu_buttons(menu_layout)
        
        main_layout.addWidget(menu_widget)
        main_layout.addWidget(self.stacked_widget)
        
        # Загружаем данные только если база данных инициализирована
        if db_initialized:
            self.load_products()
            self.load_manufacturers()
            self.load_malware()
            self.load_signatures()
        else:
            QMessageBox.warning(self, "Предупреждение", 
                              "База данных не инициализирована. Приложение будет работать в ограниченном режиме.")
    
    def closeEvent(self, event):
        try:
            if db.is_connection_usable():
                db.close()
                print("Подключение к базе данных закрыто")
        except:
            pass
        event.accept()

    def show_manufacturer_detail(self, manufacturer):
        manufacturer_page = ManufacturerDetailPage(manufacturer, self)
        self.stacked_widget.addWidget(manufacturer_page)
        self.stacked_widget.setCurrentWidget(manufacturer_page)
    
    def get_next_manufacturer_id(self):
        try:
            max_id = Manufacturer.select(fn.MAX(Manufacturer.manufacturer_id)).scalar()
            if not max_id:
                return "MAN-0001"
            
            if max_id.startswith("MAN-"):
                try:
                    current_id = int(max_id.split("-")[1])
                    next_id = current_id + 1
                    return f"MAN-{next_id:04d}"
                except (ValueError, IndexError):
                    return "MAN-0001"
            else:
                return "MAN-0001"
                
        except Exception as e:
            print(f"Ошибка при генерации ID производителя: {e}")
            return "MAN-0001"
    
    def get_next_product_id(self):
        try:
            max_id = Product.select(fn.MAX(Product.product_id)).scalar()
            if not max_id:
                return "PROD-0001"
            
            if max_id.startswith("PROD-"):
                try:
                    current_id = int(max_id.split("-")[1])
                    next_id = current_id + 1
                    return f"PROD-{next_id:04d}"
                except (ValueError, IndexError):
                    return "PROD-0001"
            else:
                return "PROD-0001"
                
        except Exception as e:
            print(f"Ошибка при генерации ID товара: {e}")
            return "PROD-0001"
    
    def get_next_malware_id(self):
        try:
            max_id = Malware.select(fn.MAX(Malware.malware_id)).scalar()
            if not max_id:
                return "MAL-0001"
            
            if max_id.startswith("MAL-"):
                try:
                    current_id = int(max_id.split("-")[1])
                    next_id = current_id + 1
                    return f"MAL-{next_id:04d}"
                except (ValueError, IndexError):
                    return "MAL-0001"
            else:
                return "MAL-0001"
                
        except Exception as e:
            print(f"Ошибка при генерации ID ВП: {e}")
            return "MAL-0001"
    
    def get_next_signature_id(self):
        try:
            max_id = Signature.select(fn.MAX(Signature.signature_id)).scalar()
            if not max_id:
                return "SIG-0001"
            
            if max_id.startswith("SIG-"):
                try:
                    current_id = int(max_id.split("-")[1])
                    next_id = current_id + 1
                    return f"SIG-{next_id:04d}"
                except (ValueError, IndexError):
                    return "SIG-0001"
            else:
                return "SIG-0001"
                
        except Exception as e:
            print(f"Ошибка при генерации ID сигнатуры: {e}")
            return "SIG-0001"
    
    def create_pages(self):
        self.new_product_page = self.create_new_product_page()
        self.stacked_widget.addWidget(self.new_product_page)

        self.new_manufacturer_page = self.create_new_manufacturer_page()
        self.stacked_widget.addWidget(self.new_manufacturer_page)
        
        self.new_vp_page = self.create_new_malware_page()
        self.stacked_widget.addWidget(self.new_vp_page)

        self.new_signature_page = self.create_new_signature_page()
        self.stacked_widget.addWidget(self.new_signature_page)
        
        self.manufacturer_page = self.create_manufacturer_page()
        self.stacked_widget.addWidget(self.manufacturer_page)

        self.signature_page = self.create_signature_page()
        self.stacked_widget.addWidget(self.signature_page)

        self.vp_page = self.create_malware_page()
        self.stacked_widget.addWidget(self.vp_page)
        
        self.antivirus_page = self.create_antivirus_page()
        self.stacked_widget.addWidget(self.antivirus_page)

        self.main_page = self.create_dashboard_page()
        self.stacked_widget.addWidget(self.main_page)
    
    def create_styled_page(self, title):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addStretch()
        return page
    
    def create_menu_buttons(self, layout):
        buttons_main = [
            ("Создать новый товар", 0),
            ("Создать нового производителя", 1),
            ("Создать новую ВП", 2),
            ("Создать новую сигнатуру", 3),
            ("Производители", 4),
            ("Сигнатуры", 5),
            ("Вредоносные программы", 6),
            ("Антивирусная база", 7),
            ("Главная", 8)
        ]

        for text, index in buttons_main:
            btn = QPushButton(text)
            btn.setFixedHeight(40)
            
            if text.startswith("Создать"):
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 14px;
                        font-weight: 400;
                        padding: 9px 15px;
                        border: none;
                        border-radius: 19px;
                        text-align: center;
                        background-color: #f4f4bd;
                        color: #3e6775;
                        width: 210px;
                    }
                    QPushButton:hover {
                        background-color: #bdbda0;
                    }
                """)

            elif text.startswith("Главная") or text.startswith("Сигнатуры"):
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 14px;
                        font-weight: 400;
                        padding: 9px 15px;
                        border: 1px solid #f4f4bd;
                        border-radius: 19px;
                        text-align: center;
                        background-color: none;
                        color: #f4f4bd;
                        max-width: 100px;
                    }
                    QPushButton:hover {
                        border: 3px solid #f4f4bd;
                    }
                """)

            elif text.startswith("Производители"):
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 14px;
                        font-weight: 400;
                        padding: 9px 15px;
                        border: 1px solid #f4f4bd;
                        border-radius: 19px;
                        text-align: center;
                        background-color: none;
                        color: #f4f4bd;
                        max-width: 120px;
                    }
                    QPushButton:hover {
                        border: 3px solid #f4f4bd;
                    }
                """)

            elif text.startswith("Антивирусная"):
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 14px;
                        font-weight: 400;
                        padding: 9px 15px;
                        border: 1px solid #f4f4bd;
                        border-radius: 19px;
                        text-align: center;
                        background-color: none;
                        color: #f4f4bd;
                        max-width: 180px;
                    }
                    QPushButton:hover {
                        border: 3px solid #f4f4bd;
                    }
                """)
        
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 14px;
                        font-weight: normal;
                        padding: 9px 15px;
                        border: 1px solid #f4f4bd;
                        border-radius: 19px;
                        text-align: center;
                        background-color: none;
                        color: #f4f4bd;
                        min-width: 188px;
                    }
                    QPushButton:hover {
                        border: 3px solid #f4f4bd;
                    }
                """)
            btn.clicked.connect(lambda checked, idx=index: self.stacked_widget.setCurrentIndex(idx))
            layout.addWidget(btn)
        
        # ДОБАВЛЯЕМ КНОПКУ ЭКСПОРТА
        export_btn = QPushButton("Экспорт в Excel")
        export_btn.setFixedHeight(40)
        export_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: 400;
                padding: 8px;
                border: 1px solid #4CAF50;
                border-radius: 15px;
                text-align: center;
                background-color: none;
                color: #4CAF50;
                width: 210px;
                margin-top: 10px;
            }
            QPushButton:hover {
                border: 3px solid #4CAF50;
            }
        """)
        export_btn.clicked.connect(self.export_to_excel)
        layout.addWidget(export_btn)

    def export_to_excel(self):
        """Экспорт данных в Excel"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Сохранить отчет Excel", "antivirus_report.xlsx", "Excel Files (*.xlsx)"
            )
            
            if filename:
                exporter = ExcelExporter(filename)
                success, result = exporter.export_all_data()
                
                if success:
                    QMessageBox.information(self, "Успех", f"Отчет успешно сохранен:\n{result}")
                else:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось создать отчет:\n{result}")
                    
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при экспорте:\n{str(e)}")


    
    def create_new_malware_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Создание новой вредоносной программы")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        form_layout.addWidget(QLabel(), 0, 0)
        malware_id_layout = QHBoxLayout()
        
        self.malware_id_input = QLineEdit()
        self.malware_id_input.setPlaceholderText("Автоматически генерируется...")
        self.malware_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 18px;
            }
        """)
        self.malware_id_input.setReadOnly(True)
        malware_id_layout.addWidget(self.malware_id_input)
        
        generate_id_btn = QPushButton("Сгенерировать")
        generate_id_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 8px 12px;
                border-radius: 15px;
            }
        """)
        generate_id_btn.clicked.connect(self.generate_malware_id)
        malware_id_layout.addWidget(generate_id_btn)
        
        form_layout.addLayout(malware_id_layout, 0, 1)
        
        form_layout.addWidget(QLabel(), 1, 0)
        self.malware_name_input = QLineEdit()
        self.malware_name_input.setPlaceholderText("Введите название ВП")
        self.malware_name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.malware_name_input, 1, 1)
        
        form_layout.addWidget(QLabel(), 2, 0)
        self.malware_description_input = QTextEdit()
        self.malware_description_input.setPlaceholderText("Введите описание ВП")
        self.malware_description_input.setMaximumHeight(100)
        self.malware_description_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.malware_description_input, 2, 1)
        
        form_layout.addWidget(QLabel(), 3, 0)
        self.malware_threat_combo = QComboBox()
        self.malware_threat_combo.addItems(["Низкий", "Средний", "Высокий", "Критический"])
        self.malware_threat_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.malware_threat_combo, 3, 1)
        
        form_layout.addWidget(QLabel(), 4, 0)
        self.malware_date_input = QDateEdit()
        self.malware_date_input.setDate(QDate.currentDate())
        self.malware_date_input.setCalendarPopup(True)
        self.malware_date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.malware_date_input, 4, 1)
        
        form_layout.addWidget(QLabel(), 5, 0)
        self.malware_type_input = QLineEdit()
        self.malware_type_input.setPlaceholderText("Введите тип ВП (например, Троян, Вирус и т.д.)")
        self.malware_type_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.malware_type_input, 5, 1)
        
        layout.addWidget(form_widget)
        
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        create_btn = QPushButton("Создать ВП")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
        """)
        create_btn.clicked.connect(self.create_malware)
        button_layout.addWidget(create_btn)
        
        back_btn = QPushButton("Назад к списку")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        back_btn.clicked.connect(self.go_back_from_create_malware)
        button_layout.addWidget(back_btn)
        
        layout.addWidget(button_widget)
        layout.addStretch()
        
        self.generate_malware_id()
        
        return page
    
    def create_new_signature_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Создание новой сигнатуры")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        form_layout.addWidget(QLabel(), 0, 0)
        signature_id_layout = QHBoxLayout()
        
        self.signature_id_input = QLineEdit()
        self.signature_id_input.setPlaceholderText("Автоматически генерируется...")
        self.signature_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 18px;
            }
        """)
        self.signature_id_input.setReadOnly(True)
        signature_id_layout.addWidget(self.signature_id_input)
        
        generate_id_btn = QPushButton("Сгенерировать")
        generate_id_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 8px 12px;
                border-radius: 15px;
            }
        """)
        generate_id_btn.clicked.connect(self.generate_signature_id)
        signature_id_layout.addWidget(generate_id_btn)
        
        form_layout.addLayout(signature_id_layout, 0, 1)
        
        form_layout.addWidget(QLabel(), 1, 0)
        self.signature_name_input = QLineEdit()
        self.signature_name_input.setPlaceholderText("Введите название сигнатуры")
        self.signature_name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.signature_name_input, 1, 1)
        
        form_layout.addWidget(QLabel(), 2, 0)
        self.signature_data_input = QTextEdit()
        self.signature_data_input.setPlaceholderText("Введите данные сигнатуры")
        self.signature_data_input.setMaximumHeight(100)
        self.signature_data_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.signature_data_input, 2, 1)
        
        form_layout.addWidget(QLabel(), 3, 0)
        self.signature_date_input = QDateEdit()
        self.signature_date_input.setDate(QDate.currentDate())
        self.signature_date_input.setCalendarPopup(True)
        self.signature_date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.signature_date_input, 3, 1)
        
        form_layout.addWidget(QLabel(), 4, 0)
        self.signature_malware_combo = QComboBox()
        self.load_malware_combo()
        self.signature_malware_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.signature_malware_combo, 4, 1)
        
        # Добавляем поле выбора производителя
        form_layout.addWidget(QLabel(), 5, 0)
        self.signature_manufacturer_combo = QComboBox()
        self.load_manufacturers_combo_signature()
        self.signature_manufacturer_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.signature_manufacturer_combo, 5, 1)
        
        layout.addWidget(form_widget)
        
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        create_btn = QPushButton("Создать сигнатуру")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
        """)
        create_btn.clicked.connect(self.create_signature)
        button_layout.addWidget(create_btn)
        
        back_btn = QPushButton("Назад к списку")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        back_btn.clicked.connect(self.go_back_from_create_signature)
        button_layout.addWidget(back_btn)
        
        layout.addWidget(button_widget)
        layout.addStretch()
        
        self.generate_signature_id()
        
        return page
    
    def generate_malware_id(self):
        next_id = self.get_next_malware_id()
        self.malware_id_input.setText(next_id)
    
    def generate_signature_id(self):
        next_id = self.get_next_signature_id()
        self.signature_id_input.setText(next_id)
    
    def generate_product_id(self):
        next_id = self.get_next_product_id()
        self.product_id_input.setText(next_id)
    
    def generate_manufacturer_id(self):
        next_id = self.get_next_manufacturer_id()
        self.manufacturer_id_input.setText(next_id)
    
    def load_malware_combo(self):
        self.signature_malware_combo.clear()
        try:
            malware_list = Malware.select()
            for malware in malware_list:
                self.signature_malware_combo.addItem(f"{malware.malware_id} - {malware.name}", malware.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить вредоносные программы: {str(e)}")
    
    def load_manufacturers_combo_signature(self):
        """Загрузка производителей для создания сигнатур - используем те же производители, что и для антивирусных программ"""
        self.signature_manufacturer_combo.clear()
        try:
            manufacturers = Manufacturer.select()
            for manufacturer in manufacturers:
                self.signature_manufacturer_combo.addItem(manufacturer.name, manufacturer.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить производителей: {str(e)}")
    
    def load_manufacturers_combo(self):
        """Загрузка производителей для создания продуктов"""
        self.manufacturer_combo.clear()
        try:
            manufacturers = Manufacturer.select()
            for manufacturer in manufacturers:
                self.manufacturer_combo.addItem(manufacturer.name, manufacturer.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить производителей: {str(e)}")
    
    def create_malware(self):
        if not all([self.malware_id_input.text(), self.malware_name_input.text(), 
                   self.malware_description_input.toPlainText(), self.malware_type_input.text()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        existing_malware = Malware.get_or_none(Malware.malware_id == self.malware_id_input.text())
        if existing_malware:
            QMessageBox.warning(self, "Ошибка", "ВП с таким номером уже существует")
            self.generate_malware_id()
            return
        
        try:
            malware = Malware(
                malware_id=self.malware_id_input.text(),
                name=self.malware_name_input.text(),
                description=self.malware_description_input.toPlainText(),
                threat_level=self.malware_threat_combo.currentText(),
                discovery_date=self.malware_date_input.date().toPyDate(),
                malware_type=self.malware_type_input.text()
            )
            malware.save()
            
            QMessageBox.information(self, "Успех", "Вредоносная программа успешно создана")
            self.clear_malware_form()
            self.stacked_widget.setCurrentIndex(6)
            self.load_malware()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать вредоносную программу: {str(e)}")
    
    def create_signature(self):
        if not all([self.signature_id_input.text(), self.signature_name_input.text(), 
                   self.signature_data_input.toPlainText()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        if self.signature_malware_combo.currentData() is None:
            QMessageBox.warning(self, "Ошибка", "Необходимо выбрать вредоносную программу")
            return
        
        if self.signature_manufacturer_combo.currentData() is None:
            QMessageBox.warning(self, "Ошибка", "Необходимо выбрать производителя")
            return
        
        existing_signature = Signature.get_or_none(Signature.signature_id == self.signature_id_input.text())
        if existing_signature:
            QMessageBox.warning(self, "Ошибка", "Сигнатура с таким номером уже существует")
            self.generate_signature_id()
            return
        
        try:
            signature = Signature(
                signature_id=self.signature_id_input.text(),
                name=self.signature_name_input.text(),
                data=self.signature_data_input.toPlainText(),
                creation_date=self.signature_date_input.date().toPyDate(),
                malware_id=self.signature_malware_combo.currentData(),
                manufacturer_id=self.signature_manufacturer_combo.currentData()
            )
            signature.save()
            
            QMessageBox.information(self, "Успех", "Сигнатура успешно создана")
            self.clear_signature_form()
            self.stacked_widget.setCurrentIndex(5)
            self.load_signatures()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать сигнатуру: {str(e)}")
    
    def clear_malware_form(self):
        self.malware_name_input.clear()
        self.malware_description_input.clear()
        self.malware_type_input.clear()
        self.malware_date_input.setDate(QDate.currentDate())
        self.malware_threat_combo.setCurrentIndex(0)
        self.generate_malware_id()
    
    def clear_signature_form(self):
        self.signature_name_input.clear()
        self.signature_data_input.clear()
        self.signature_date_input.setDate(QDate.currentDate())
        self.generate_signature_id()
    
    def go_back_from_create_malware(self):
        reply = QMessageBox.question(self, "Подтверждение", 
                                   "Вы точно хотите вернуться назад? Все несохраненные данные будут потеряны.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_malware_form()
            self.stacked_widget.setCurrentIndex(8)
    
    def go_back_from_create_signature(self):
        reply = QMessageBox.question(self, "Подтверждение", 
                                   "Вы точно хотите вернуться назад? Все несохраненные данные будут потеряны.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_signature_form()
            self.stacked_widget.setCurrentIndex(8)
    
    def create_malware_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Вредоносные программы")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Добавляем фильтры
        filters_widget = QWidget()
        filters_layout = QHBoxLayout(filters_widget)
        filters_layout.setContentsMargins(20, 0, 20, 20)
        
        search_label = QLabel("Поиск:")
        search_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd;")
        filters_layout.addWidget(search_label)
        
        self.malware_search_input = QLineEdit()
        self.malware_search_input.setPlaceholderText("Поиск по названию, описанию...")
        self.malware_search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
            }
        """)
        self.malware_search_input.textChanged.connect(self.filter_malware)
        filters_layout.addWidget(self.malware_search_input)
        
        # Фильтр по уровню опасности
        threat_filter_label = QLabel("Уровень опасности:")
        threat_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(threat_filter_label)
        
        self.malware_threat_filter = QComboBox()
        self.malware_threat_filter.addItem("Все уровни")
        self.malware_threat_filter.addItems(["Низкий", "Средний", "Высокий", "Критический"])
        self.malware_threat_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 150px;
            }
        """)
        self.malware_threat_filter.currentTextChanged.connect(self.filter_malware)
        filters_layout.addWidget(self.malware_threat_filter)
        
        # Фильтр по типу
        type_filter_label = QLabel("Тип:")
        type_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(type_filter_label)
        
        self.malware_type_filter = QComboBox()
        self.malware_type_filter.addItem("Все типы")
        self.malware_type_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 150px;
            }
        """)
        self.malware_type_filter.currentTextChanged.connect(self.filter_malware)
        filters_layout.addWidget(self.malware_type_filter)
        
        # Фильтр по году
        year_filter_label = QLabel("Год обнаружения:")
        year_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(year_filter_label)
        
        self.malware_year_filter = QComboBox()
        self.malware_year_filter.addItem("Все годы")
        self.malware_year_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 120px;
            }
        """)
        self.malware_year_filter.currentTextChanged.connect(self.filter_malware)
        filters_layout.addWidget(self.malware_year_filter)
        
        layout.addWidget(filters_widget)
        
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.malware_layout = QVBoxLayout(scroll_widget)
        
        self.malware_container = QWidget()
        self.malware_grid = QHBoxLayout(self.malware_container)
        self.malware_grid.addStretch()
        
        self.malware_layout.addWidget(self.malware_container)
        self.malware_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        layout.addWidget(scroll_area)
        
        return page
    
    def create_signature_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Сигнатуры")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Добавляем фильтры
        filters_widget = QWidget()
        filters_layout = QHBoxLayout(filters_widget)
        filters_layout.setContentsMargins(20, 0, 20, 20)
        
        search_label = QLabel("Поиск:")
        search_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd;")
        filters_layout.addWidget(search_label)
        
        self.signature_search_input = QLineEdit()
        self.signature_search_input.setPlaceholderText("Поиск по названию, данным...")
        self.signature_search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
            }
        """)
        self.signature_search_input.textChanged.connect(self.filter_signatures)
        filters_layout.addWidget(self.signature_search_input)
        
        # Фильтр по вредоносным программам
        malware_filter_label = QLabel("Вредоносная программа:")
        malware_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(malware_filter_label)
        
        self.signature_malware_filter = QComboBox()
        self.signature_malware_filter.addItem("Все ВП")
        self.signature_malware_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 200px;
            }
        """)
        self.signature_malware_filter.currentTextChanged.connect(self.filter_signatures)
        filters_layout.addWidget(self.signature_malware_filter)
        
        # Фильтр по производителям
        manufacturer_filter_label = QLabel("Производитель:")
        manufacturer_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(manufacturer_filter_label)
        
        self.signature_manufacturer_filter = QComboBox()
        self.signature_manufacturer_filter.addItem("Все производители")
        self.signature_manufacturer_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 200px;
            }
        """)
        self.signature_manufacturer_filter.currentTextChanged.connect(self.filter_signatures)
        filters_layout.addWidget(self.signature_manufacturer_filter)
        
        # Фильтр по году
        year_filter_label = QLabel("Год создания:")
        year_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(year_filter_label)
        
        self.signature_year_filter = QComboBox()
        self.signature_year_filter.addItem("Все годы")
        self.signature_year_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 120px;
            }
        """)
        self.signature_year_filter.currentTextChanged.connect(self.filter_signatures)
        filters_layout.addWidget(self.signature_year_filter)
        
        layout.addWidget(filters_widget)
        
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.signatures_layout = QVBoxLayout(scroll_widget)
        
        self.signatures_container = QWidget()
        self.signatures_grid = QHBoxLayout(self.signatures_container)
        self.signatures_grid.addStretch()
        
        self.signatures_layout.addWidget(self.signatures_container)
        self.signatures_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        layout.addWidget(scroll_area)
        
        return page
    
    def load_malware(self):
        if hasattr(self, 'malware_grid'):
            for i in reversed(range(self.malware_grid.count())):
                widget = self.malware_grid.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
        
        try:
            malware_list = Malware.select().order_by(Malware.malware_id)
            for malware in malware_list:
                card = MalwareCard(malware, self)
                self.malware_grid.insertWidget(self.malware_grid.count() - 1, card)
            
            # Загружаем фильтры после загрузки данных
            self.load_malware_filters()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить вредоносные программы: {str(e)}")
    
    def load_signatures(self):
        if hasattr(self, 'signatures_grid'):
            for i in reversed(range(self.signatures_grid.count())):
                widget = self.signatures_grid.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
        
        try:
            # Используем правильный запрос с JOIN
            signatures = (Signature
                        .select(Signature, Manufacturer, Malware)
                        .join(Malware, on=(Signature.malware_id == Malware.id))
                        .join(Manufacturer, JOIN.LEFT_OUTER, on=(Signature.manufacturer_id == Manufacturer.id))
                        .order_by(Signature.signature_id))
            
            for signature in signatures:
                card = SignatureCard(signature, self)
                self.signatures_grid.insertWidget(self.signatures_grid.count() - 1, card)
            
            # Загружаем фильтры после загрузки данных
            self.load_signature_filters()
            
        except Exception as e:
            print(f"Ошибка загрузки сигнатур: {e}")
            # Пробуем альтернативный способ загрузки
            try:
                print("Пробуем альтернативный способ загрузки...")
                signatures = Signature.select().order_by(Signature.signature_id)
                for signature in signatures:
                    # Вручную загружаем связанные объекты
                    try:
                        signature.malware = Malware.get_by_id(signature.malware_id)
                    except:
                        signature.malware = None
                    
                    try:
                        if signature.manufacturer_id:
                            signature.manufacturer = Manufacturer.get_by_id(signature.manufacturer_id)
                        else:
                            signature.manufacturer = None
                    except:
                        signature.manufacturer = None
                    
                    card = SignatureCard(signature, self)
                    self.signatures_grid.insertWidget(self.signatures_grid.count() - 1, card)
                
                self.load_signature_filters()
                
            except Exception as e2:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить сигнатуры: {str(e2)}")
    
    def filter_malware(self):
        search_text = self.malware_search_input.text().lower()
        threat_filter = self.malware_threat_filter.currentText()
        type_filter = self.malware_type_filter.currentText()
        year_filter = self.malware_year_filter.currentText()
        
        for i in range(self.malware_grid.count()):
            widget = self.malware_grid.itemAt(i).widget()
            if widget and isinstance(widget, MalwareCard):
                malware = widget.malware
                
                # Проверка текстового поиска
                text_match = (search_text in malware.name.lower() or 
                             search_text in malware.malware_type.lower() or 
                             search_text in malware.threat_level.lower() or
                             search_text in malware.description.lower() or
                             search_text in malware.malware_id.lower())
                
                # Проверка фильтра по уровню опасности
                threat_match = (threat_filter == "Все уровни" or 
                               threat_filter == malware.threat_level)
                
                # Проверка фильтра по типу
                type_match = (type_filter == "Все типы" or 
                             type_filter == malware.malware_type)
                
                # Проверка фильтра по году
                year_match = True
                if year_filter != "Все годы" and malware.discovery_date:
                    year_match = str(malware.discovery_date.year) == year_filter
                
                if text_match and threat_match and type_match and year_match:
                    widget.show()
                else:
                    widget.hide()
    
    def filter_signatures(self):
        search_text = self.signature_search_input.text().lower()
        malware_filter = self.signature_malware_filter.currentText()
        manufacturer_filter = self.signature_manufacturer_filter.currentText()
        year_filter = self.signature_year_filter.currentText()
        
        for i in range(self.signatures_grid.count()):
            widget = self.signatures_grid.itemAt(i).widget()
            if widget and isinstance(widget, SignatureCard):
                signature = widget.signature
                
                # Проверка текстового поиска
                text_match = (search_text in signature.name.lower() or 
                             search_text in signature.data.lower() or 
                             search_text in signature.signature_id.lower())
                
                # Проверка фильтра по вредоносной программе
                malware_match = (malware_filter == "Все ВП" or 
                               malware_filter == f"{signature.malware.malware_id} - {signature.malware.name}")
                
                # Проверка фильтра по производителю
                manufacturer_match = True
                if manufacturer_filter != "Все производители" and signature.manufacturer:
                    manufacturer_match = manufacturer_filter == signature.manufacturer.name
                
                # Проверка фильтра по году
                year_match = True
                if year_filter != "Все годы" and signature.creation_date:
                    year_match = str(signature.creation_date.year) == year_filter
                
                if text_match and malware_match and manufacturer_match and year_match:
                    widget.show()
                else:
                    widget.hide()

    def create_new_manufacturer_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Создание нового производителя")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        form_layout.addWidget(QLabel(), 0, 0)
        manufacturer_id_layout = QHBoxLayout()
        
        self.manufacturer_id_input = QLineEdit()
        self.manufacturer_id_input.setPlaceholderText("Автоматически генерируется...")
        self.manufacturer_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 18px;
            }
        """)
        self.manufacturer_id_input.setReadOnly(True)
        manufacturer_id_layout.addWidget(self.manufacturer_id_input)
        
        generate_id_btn = QPushButton("Сгенерировать")
        generate_id_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 8px 12px;
                border-radius: 15px;
            }
        """)
        generate_id_btn.clicked.connect(self.generate_manufacturer_id)
        manufacturer_id_layout.addWidget(generate_id_btn)
        
        form_layout.addLayout(manufacturer_id_layout, 0, 1)
        
        form_layout.addWidget(QLabel(), 1, 0)
        self.manufacturer_name_input = QLineEdit()
        self.manufacturer_name_input.setPlaceholderText("Введите название производителя")
        self.manufacturer_name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.manufacturer_name_input, 1, 1)
        
        form_layout.addWidget(QLabel(), 2, 0)
        self.manufacturer_website_input = QLineEdit()
        self.manufacturer_website_input.setPlaceholderText("Введите URL сайта")
        self.manufacturer_website_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.manufacturer_website_input, 2, 1)
        
        form_layout.addWidget(QLabel(), 3, 0)
        self.manufacturer_country_input = QLineEdit()
        self.manufacturer_country_input.setPlaceholderText("Введите страну")
        self.manufacturer_country_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.manufacturer_country_input, 3, 1)
        
        form_layout.addWidget(QLabel(), 4, 0)
        self.manufacturer_date_input = QDateEdit()
        self.manufacturer_date_input.setDate(QDate.currentDate())
        self.manufacturer_date_input.setCalendarPopup(True)
        self.manufacturer_date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.manufacturer_date_input, 4, 1)
        
        form_layout.addWidget(QLabel(), 5, 0)
        self.manufacturer_description_input = QTextEdit()
        self.manufacturer_description_input.setPlaceholderText("Введите описание производителя")
        self.manufacturer_description_input.setMaximumHeight(100)
        self.manufacturer_description_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.manufacturer_description_input, 5, 1)
        
        form_layout.addWidget(QLabel(), 6, 0)
        image_layout = QHBoxLayout()
        self.manufacturer_image_btn = QPushButton("Выбрать изображение")
        self.manufacturer_image_btn.setStyleSheet("""
            QPushButton {
                background-color: #3e6767;
                color: #f4f4bd;
                padding: 8px 15px;
                border-radius: 15px;
                border: 1px solid #f4f4bd;
            }
        """)
        self.manufacturer_image_btn.clicked.connect(self.select_manufacturer_image)
        image_layout.addWidget(self.manufacturer_image_btn)
        self.manufacturer_image_label = QLabel("Не выбрано")
        self.manufacturer_image_label.setStyleSheet("color: #f4f4bd;")
        image_layout.addWidget(self.manufacturer_image_label)
        form_layout.addLayout(image_layout, 6, 1)
        
        layout.addWidget(form_widget)
        
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        create_btn = QPushButton("Создать производителя")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
        """)
        create_btn.clicked.connect(self.create_manufacturer)
        button_layout.addWidget(create_btn)
        
        back_btn = QPushButton("Назад к списку")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        back_btn.clicked.connect(self.go_back_from_create_manufacturer)
        button_layout.addWidget(back_btn)
        
        layout.addWidget(button_widget)
        layout.addStretch()
        
        self.manufacturer_image_path = None
        
        self.generate_manufacturer_id()
        
        return page
    
    def create_manufacturer_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Производители")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Добавляем фильтры
        filters_widget = QWidget()
        filters_layout = QHBoxLayout(filters_widget)
        filters_layout.setContentsMargins(20, 0, 20, 20)
        
        search_label = QLabel("Поиск:")
        search_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd;")
        filters_layout.addWidget(search_label)
        
        self.manufacturer_search_input = QLineEdit()
        self.manufacturer_search_input.setPlaceholderText("Поиск по названию, стране, описанию...")
        self.manufacturer_search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
            }
        """)
        self.manufacturer_search_input.textChanged.connect(self.filter_manufacturers)
        filters_layout.addWidget(self.manufacturer_search_input)
        
        # Фильтр по стране
        country_filter_label = QLabel("Страна:")
        country_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(country_filter_label)
        
        self.manufacturer_country_filter = QComboBox()
        self.manufacturer_country_filter.addItem("Все страны")
        self.manufacturer_country_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 150px;
            }
        """)
        self.manufacturer_country_filter.currentTextChanged.connect(self.filter_manufacturers)
        filters_layout.addWidget(self.manufacturer_country_filter)
        
        # Фильтр по году
        year_filter_label = QLabel("Год создания:")
        year_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(year_filter_label)
        
        self.manufacturer_year_filter = QComboBox()
        self.manufacturer_year_filter.addItem("Все годы")
        self.manufacturer_year_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 120px;
            }
        """)
        self.manufacturer_year_filter.currentTextChanged.connect(self.filter_manufacturers)
        filters_layout.addWidget(self.manufacturer_year_filter)
        
        layout.addWidget(filters_widget)
        
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.manufacturers_layout = QVBoxLayout(scroll_widget)
        
        self.manufacturers_container = QWidget()
        self.manufacturers_grid = QVBoxLayout(self.manufacturers_container)
        
        self.manufacturers_layout.addWidget(self.manufacturers_container)
        self.manufacturers_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        layout.addWidget(scroll_area)
        
        return page
    
    def create_new_product_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Создание нового товара")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        
        form_layout.addWidget(QLabel(), 0, 0)
        product_id_layout = QHBoxLayout()
        
        self.product_id_input = QLineEdit()
        self.product_id_input.setPlaceholderText("Автоматически генерируется...")
        self.product_id_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #6c5868;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 18px;
            }
        """)
        self.product_id_input.setReadOnly(True)
        product_id_layout.addWidget(self.product_id_input)
        
        generate_id_btn = QPushButton("Сгенерировать")
        generate_id_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 8px 12px;
                border-radius: 15px;
            }
        """)
        generate_id_btn.clicked.connect(self.generate_product_id)
        product_id_layout.addWidget(generate_id_btn)
        
        form_layout.addLayout(product_id_layout, 0, 1)
        
        form_layout.addWidget(QLabel(), 1, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Введите название антивируса")
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.name_input, 1, 1)
        
        form_layout.addWidget(QLabel(), 2, 0)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Введите описание")
        self.description_input.setMaximumHeight(100)
        self.description_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.description_input, 2, 1)
        
        form_layout.addWidget(QLabel(), 3, 0)
        self.version_input = QLineEdit()
        self.version_input.setPlaceholderText("Введите цену")
        self.version_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.version_input, 3, 1)
        
        form_layout.addWidget(QLabel(), 4, 0)
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.date_input, 4, 1)
        
        form_layout.addWidget(QLabel(), 5, 0)
        self.size_input = QLineEdit()
        self.size_input.setPlaceholderText("Введите рейтинг")
        self.size_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.size_input, 5, 1)
        
        form_layout.addWidget(QLabel(), 6, 0)
        self.manufacturer_combo = QComboBox()
        self.manufacturer_combo.setPlaceholderText("Выберите производителя")
        self.load_manufacturers_combo()
        self.manufacturer_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
            }
        """)
        form_layout.addWidget(self.manufacturer_combo, 6, 1)
        
        form_layout.addWidget(QLabel(), 7, 0)
        image_layout = QHBoxLayout()
        self.image_btn = QPushButton("Выбрать изображение")
        self.image_btn.setStyleSheet("""
            QPushButton {
                background-color: #3e6767;
                color: #f4f4bd;
                padding: 8px 15px;
                border-radius: 15px;
                border: 1px solid #f4f4bd;
            }
        """)
        self.image_btn.clicked.connect(self.select_image)
        image_layout.addWidget(self.image_btn)
        self.image_label = QLabel("Не выбрано")
        self.image_label.setStyleSheet("color: #f4f4bd;")
        image_layout.addWidget(self.image_label)
        form_layout.addLayout(image_layout, 7, 1)
        
        layout.addWidget(form_widget)
        
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        create_btn = QPushButton("Создать товар")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4bd;
                color: #3e6775;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
                font-weight: 400;
            }
        """)
        create_btn.clicked.connect(self.create_product)
        button_layout.addWidget(create_btn)
        
        back_btn = QPushButton("Назад к списку")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                padding: 12px 25px;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        back_btn.clicked.connect(self.go_back_from_create)
        button_layout.addWidget(back_btn)
        
        layout.addWidget(button_widget)
        layout.addStretch()
        
        self.image_path = None
        
        self.generate_product_id()
        
        return page
    
    def create_antivirus_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title_label = QLabel("Антивирусные базы")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 400;
                color: #f4f4bd;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Добавляем фильтры
        filters_widget = QWidget()
        filters_layout = QHBoxLayout(filters_widget)
        filters_layout.setContentsMargins(20, 0, 20, 20)
        
        search_label = QLabel("Поиск:")
        search_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd;")
        filters_layout.addWidget(search_label)
        
        self.product_search_input = QLineEdit()
        self.product_search_input.setPlaceholderText("Поиск по названию, цене, рейтингу...")
        self.product_search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
            }
        """)
        self.product_search_input.textChanged.connect(self.filter_products)
        filters_layout.addWidget(self.product_search_input)
        
        # Фильтр по производителю
        manufacturer_filter_label = QLabel("Производитель:")
        manufacturer_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(manufacturer_filter_label)
        
        self.product_manufacturer_filter = QComboBox()
        self.product_manufacturer_filter.addItem("Все производители")
        self.product_manufacturer_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 150px;
            }
        """)
        self.product_manufacturer_filter.currentTextChanged.connect(self.filter_products)
        filters_layout.addWidget(self.product_manufacturer_filter)
        
        # Фильтр по году
        year_filter_label = QLabel("Год выпуска:")
        year_filter_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #f4f4bd; margin-left: 15px;")
        filters_layout.addWidget(year_filter_label)
        
        self.product_year_filter = QComboBox()
        self.product_year_filter.addItem("Все годы")
        self.product_year_filter.setStyleSheet("""
            QComboBox {
                padding: 8px;
                background-color: #3e6767;
                color: #f4f4bd;
                border: 1px solid #f4f4bd;
                border-radius: 15px;
                font-size: 14px;
                min-width: 120px;
            }
        """)
        self.product_year_filter.currentTextChanged.connect(self.filter_products)
        filters_layout.addWidget(self.product_year_filter)
        
        layout.addWidget(filters_widget)
        
        scroll_area = QScrollArea()

        scroll_widget = QWidget()
        self.products_layout = QVBoxLayout(scroll_widget)
        
        self.products_container = QWidget()
        self.products_grid = QHBoxLayout(self.products_container)
        self.products_grid.addStretch()
        
        self.products_layout.addWidget(self.products_container)
        self.products_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        layout.addWidget(scroll_area)
        
        return page
    
    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # ЗАГОЛОВОК ДАШБОРДА
        title_label = QLabel("АНТИВИРУСНАЯ БАЗА - АНАЛИТИЧЕСКАЯ ПАНЕЛЬ")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 600;
                color: #f4f4bd;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        subtitle_label = QLabel("Статистика и аналитика базы данных антивирусов")
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 400;
                color: #a7d8de;
                margin-bottom: 30px;
            }
        """)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label)
        
        # ИНФОРМАЦИОННЫЕ КАРТОЧКИ ПРОЕКТА
        stats_cards_widget = self.create_stats_cards()
        layout.addWidget(stats_cards_widget)
        
        # ФИЛЬТРЫ ДЛЯ ГРАФИКОВ
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.addStretch()
        
        period_label = QLabel("ПЕРИОД АНАЛИТИКИ:")
        period_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #f4f4bd; text-transform: uppercase; margin-right: 20px;")
        filter_layout.addWidget(period_label)
        
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Неделя", "Месяц", "Год"])
        self.period_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                font-size: 14px;
                background-color: #6c5868;
                border-radius: 18px;
                min-width: 120px;
                color: #f4f4bd;
                padding: 12px;
            }
        """)
        self.period_combo.currentTextChanged.connect(self.update_dashboard)
        filter_layout.addWidget(self.period_combo)
        
        layout.addWidget(filter_widget)
        
        # ГРАФИКИ
        charts_widget = QWidget()
        charts_layout = QHBoxLayout(charts_widget)
        
        # КРУГОВАЯ ДИАГРАММА: Распределение по производителям
        self.pie_canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.update_pie_chart()
        charts_layout.addWidget(self.pie_canvas)
        
        # СТОЛБЧАТАЯ ДИАГРАММА: Продукты по производителям
        self.bar_canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.update_bar_chart()
        charts_layout.addWidget(self.bar_canvas)
        
        layout.addWidget(charts_widget)
        
        # СТАТИСТИКА
        stats_widget = self.create_stats_widget()
        layout.addWidget(stats_widget)

        layout.addStretch()
        
        return page

    def create_stats_cards(self):
        """Создает информационные карточки с данными проекта"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 20)
        layout.setSpacing(15)
        
        # Получаем актуальные данные из базы
        try:
            total_manufacturers = Manufacturer.select().count()
            total_products = Product.select().count()
            total_malware = Malware.select().count()
            total_signatures = Signature.select().count()
            
            # Страны производителей
            countries_count = len(set(m.country for m in Manufacturer.select()))
            
            # Уровни опасности
            critical_threats = Malware.select().where(Malware.threat_level == 'Критический').count()
            
            # Типы вредоносных программ
            malware_types = len(set(m.malware_type for m in Malware.select()))
            
        except Exception as e:
            print(f"Ошибка загрузки данных для дашборда: {e}")
            # Значения по умолчанию
            total_manufacturers = 3
            total_products = 0
            total_malware = 2
            total_signatures = 1
            countries_count = 3
            critical_threats = 1
            malware_types = 2
        
        # Карточка 1: Производители
        card1 = self.create_stat_card(
            "ПРОИЗВОДИТЕЛИ", 
            f"{total_manufacturers}", 
            f"из {countries_count} стран", 
            "#4CAF50"
        )
        layout.addWidget(card1)
        
        # Карточка 2: Антивирусы
        card2 = self.create_stat_card(
            "АНТИВИРУСЫ", 
            f"{total_products}", 
            "в каталоге", 
            "#2196F3"
        )
        layout.addWidget(card2)
        
        # Карточка 3: Вредоносные программы
        card3 = self.create_stat_card(
            "ВРЕДОНОСНЫЕ ПРОГРАММЫ", 
            f"{total_malware}", 
            f"{critical_threats} критических", 
            "#FF9800"
        )
        layout.addWidget(card3)
        
        # Карточка 4: Сигнатуры
        card4 = self.create_stat_card(
            "СИГНАТУРЫ", 
            f"{total_signatures}", 
            f"{malware_types} типов угроз", 
            "#9C27B0"
        )
        layout.addWidget(card4)
        
        return widget

    def create_stat_card(self, title, value, description, color):
        """Создает одну информационную карточку"""
        card = QWidget()
        card.setFixedHeight(120)
        card.setObjectName("StatCard")
        
        card.setStyleSheet(f"""
            QWidget#StatCard {{
                background-color: {color};
                border-radius: 15px;
                border: 2px solid #f4f4bd;
            }}
            QWidget#StatCard:hover {{
                border: 3px solid #ffffff;
                background-color: {color};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        
        # Заголовок
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 600;
                color: #ffffff;
                background: transparent;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title_label)
        
        # Значение
        value_label = QLabel(value)
        value_label.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: 700;
                color: #ffffff;
                background: transparent;
                padding: 5px 0px;
            }
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        
        # Описание
        desc_label = QLabel(description)
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 400;
                color: #e8f5e8;
                background: transparent;
                font-style: italic;
            }
        """)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        return card

    def update_dashboard(self):
        self.update_pie_chart()
        self.update_bar_chart()
        self.update_stats_cards()

    def update_stats_cards(self):
        """Обновляет данные в информационных карточках"""
        try:
            # Эта функция будет вызываться при изменении данных
            # В реальном приложении здесь можно обновлять карточки
            pass
        except Exception as e:
            print(f"Ошибка обновления карточек: {e}")

    def update_pie_chart(self):
        """Обновляет круговую диаграмму распределения по производителям"""
        self.pie_canvas.axes.clear()
        
        try:
            # Получаем данные о производителях и количестве их продуктов
            manufacturers = Manufacturer.select()
            manufacturer_data = []
            
            for manufacturer in manufacturers:
                products_count = Product.select().where(Product.manufacturer == manufacturer).count()
                manufacturer_data.append({
                    'name': manufacturer.name,
                    'count': products_count
                })
            
            # Сортируем по количеству продуктов (по убыванию)
            manufacturer_data.sort(key=lambda x: x['count'], reverse=True)
            
            # Подготавливаем данные для диаграммы
            labels = [data['name'] for data in manufacturer_data]
            sizes = [data['count'] for data in manufacturer_data]
            
            # Цвета для диаграммы
            colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc', '#c2c2f0']
            
            # Создаем круговую диаграмму
            wedges, texts, autotexts = self.pie_canvas.axes.pie(
                sizes, labels=labels, autopct='%1.1f%%', 
                colors=colors[:len(labels)], startangle=90
            )
            
            # Настраиваем внешний вид
            self.pie_canvas.axes.set_title('Распределение продуктов по производителям', 
                                         fontsize=14, fontweight='bold', color='#f4f4bd')
            
            # Настраиваем текст
            for text in texts:
                text.set_color('#f4f4bd')
                text.set_fontsize(10)
            
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            # Делаем диаграмму круглой
            self.pie_canvas.axes.axis('equal')
            
        except Exception as e:
            print(f"Ошибка создания круговой диаграммы: {e}")
            # Заглушка при ошибке
            self.pie_canvas.axes.text(0.5, 0.5, 'Нет данных', 
                                    horizontalalignment='center', verticalalignment='center',
                                    transform=self.pie_canvas.axes.transAxes, fontsize=14, color='#f4f4bd')
            self.pie_canvas.axes.set_title('Распределение продуктов по производителям', 
                                         fontsize=14, fontweight='bold', color='#f4f4bd')
        
        self.pie_canvas.fig.tight_layout()
        self.pie_canvas.draw()

    def update_bar_chart(self):
        """Обновляет столбчатую диаграмму продуктов по производителям"""
        self.bar_canvas.axes.clear()
        
        try:
            # Получаем данные о производителях и количестве их продуктов
            manufacturers = Manufacturer.select()
            manufacturer_names = []
            product_counts = []
            
            for manufacturer in manufacturers:
                products_count = Product.select().where(Product.manufacturer == manufacturer).count()
                manufacturer_names.append(manufacturer.name)
                product_counts.append(products_count)
            
            # Создаем столбчатую диаграмму
            bars = self.bar_canvas.axes.bar(manufacturer_names, product_counts, 
                                          color='#a7b7c6', alpha=0.7, edgecolor='#f4f4bd', linewidth=1)
            
            # Настраиваем заголовок и подписи
            self.bar_canvas.axes.set_title('Количество продуктов по производителям', 
                                         fontsize=14, fontweight='bold', color='#f4f4bd')
            self.bar_canvas.axes.set_ylabel('Количество продуктов', color='#f4f4bd')
            
            # Настраиваем цвета осей
            self.bar_canvas.axes.tick_params(axis='x', rotation=45, colors='#f4f4bd')
            self.bar_canvas.axes.tick_params(axis='y', colors='#f4f4bd')
            
            # Настраиваем цвет фона
            self.bar_canvas.axes.set_facecolor('#3e6767')
            self.bar_canvas.fig.patch.set_facecolor('#3e6767')
            
            # Добавляем значения на столбцы
            for bar in bars:
                height = bar.get_height()
                self.bar_canvas.axes.text(bar.get_x() + bar.get_width()/2., height,
                                        f'{int(height)}', ha='center', va='bottom',
                                        color='#f4f4bd', fontweight='bold')
            
        except Exception as e:
            print(f"Ошибка создания столбчатой диаграммы: {e}")
            # Заглушка при ошибке
            self.bar_canvas.axes.text(0.5, 0.5, 'Нет данных', 
                                    horizontalalignment='center', verticalalignment='center',
                                    transform=self.bar_canvas.axes.transAxes, fontsize=14, color='#f4f4bd')
            self.bar_canvas.axes.set_title('Количество продуктов по производителям', 
                                         fontsize=14, fontweight='bold', color='#f4f4bd')
        
        self.bar_canvas.fig.tight_layout()
        self.bar_canvas.draw()
    
    def create_stats_widget(self):
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        
        # Получаем актуальные данные
        try:
            total_products = Product.select().count()
            total_manufacturers = Manufacturer.select().count()
            avg_products = total_products / total_manufacturers if total_manufacturers > 0 else 0
        except:
            total_products = 0
            total_manufacturers = 0
            avg_products = 0
        
        total_products_widget = QWidget()
        total_products_layout = QVBoxLayout(total_products_widget)
        
        total_products_label = QLabel("Всего продуктов")
        total_products_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f4bd; text-transform: uppercase; margin: 0 auto 0;")
        total_products_layout.addWidget(total_products_label)
        
        self.total_products_value = QLabel(f"{total_products}")
        self.total_products_value.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #f4f4bd;
                padding: 10px;
                background-color: #6c5868;
                border-radius: 8px;
                border: none;
            }
        """)
        self.total_products_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_products_layout.addWidget(self.total_products_value)
        
        total_manufacturers_widget = QWidget()
        total_manufacturers_layout = QVBoxLayout(total_manufacturers_widget)
        
        total_manufacturers_label = QLabel("Всего производителей")
        total_manufacturers_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f4bd; text-transform: uppercase; margin: 0 auto 0;")
        total_manufacturers_layout.addWidget(total_manufacturers_label)
        
        self.total_manufacturers_value = QLabel(f"{total_manufacturers}")
        self.total_manufacturers_value.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #f4f4bd;
                padding: 10px;
                background-color: #6c5868;
                border-radius: 8px;
                border: none;
            }
        """)
        self.total_manufacturers_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_manufacturers_layout.addWidget(self.total_manufacturers_value)
        
        avg_widget = QWidget()
        avg_layout = QVBoxLayout(avg_widget)
        
        avg_label = QLabel("Среднее на производителя")
        avg_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f4bd; text-transform: uppercase; margin: 0 auto 0;")
        avg_layout.addWidget(avg_label)
        
        self.avg_value = QLabel(f"{avg_products:.1f}")
        self.avg_value.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #f4f4bd;
                padding: 10px;
                background-color: #6c5868;
                border-radius: 8px;
                border: none;
            }
        """)
        self.avg_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avg_layout.addWidget(self.avg_value)
        
        stats_layout.addWidget(total_products_widget)
        stats_layout.addWidget(total_manufacturers_widget)
        stats_layout.addWidget(avg_widget)
        
        return stats_widget

    # Методы для загрузки фильтров
    def load_product_filters(self):
        """Загрузка данных для фильтров продуктов"""
        try:
            # Загрузка производителей
            self.product_manufacturer_filter.clear()
            self.product_manufacturer_filter.addItem("Все производители")
            manufacturers = Manufacturer.select().order_by(Manufacturer.name)
            for manufacturer in manufacturers:
                self.product_manufacturer_filter.addItem(manufacturer.name)
            
            # Загрузка годов
            self.product_year_filter.clear()
            self.product_year_filter.addItem("Все годы")
            years = Product.select(Product.release_date).distinct().order_by(Product.release_date.desc())
            year_set = set()
            for product in years:
                if product.release_date:
                    year = product.release_date.year
                    year_set.add(year)
            
            for year in sorted(year_set, reverse=True):
                self.product_year_filter.addItem(str(year))
                
        except Exception as e:
            print(f"Ошибка загрузки фильтров продуктов: {e}")

    def load_manufacturer_filters(self):
        """Загрузка данных для фильтров производителей"""
        try:
            # Загрузка стран
            self.manufacturer_country_filter.clear()
            self.manufacturer_country_filter.addItem("Все страны")
            countries = Manufacturer.select(Manufacturer.country).distinct().order_by(Manufacturer.country)
            country_set = set()
            for manufacturer in countries:
                if manufacturer.country:
                    country_set.add(manufacturer.country)
            
            for country in sorted(country_set):
                self.manufacturer_country_filter.addItem(country)
            
            # Загрузка годов
            self.manufacturer_year_filter.clear()
            self.manufacturer_year_filter.addItem("Все годы")
            years = Manufacturer.select(Manufacturer.creation_date).distinct().order_by(Manufacturer.creation_date.desc())
            year_set = set()
            for manufacturer in years:
                if manufacturer.creation_date:
                    year = manufacturer.creation_date.year
                    year_set.add(year)
            
            for year in sorted(year_set, reverse=True):
                self.manufacturer_year_filter.addItem(str(year))
                
        except Exception as e:
            print(f"Ошибка загрузки фильтров производителей: {e}")

    def load_signature_filters(self):
        """Загрузка данных для фильтров сигнатур"""
        try:
            # Загрузка вредоносных программ
            self.signature_malware_filter.clear()
            self.signature_malware_filter.addItem("Все ВП")
            malware_list = Malware.select().order_by(Malware.name)
            for malware in malware_list:
                self.signature_malware_filter.addItem(f"{malware.malware_id} - {malware.name}")
            
            # Загрузка производителей
            self.signature_manufacturer_filter.clear()
            self.signature_manufacturer_filter.addItem("Все производители")
            manufacturers = Manufacturer.select().order_by(Manufacturer.name)
            for manufacturer in manufacturers:
                self.signature_manufacturer_filter.addItem(manufacturer.name)
            
            # Загрузка годов
            self.signature_year_filter.clear()
            self.signature_year_filter.addItem("Все годы")
            years = Signature.select(Signature.creation_date).distinct().order_by(Signature.creation_date.desc())
            year_set = set()
            for signature in years:
                if signature.creation_date:
                    year = signature.creation_date.year
                    year_set.add(year)
            
            for year in sorted(year_set, reverse=True):
                self.signature_year_filter.addItem(str(year))
                
        except Exception as e:
            print(f"Ошибка загрузки фильтров сигнатур: {e}")

    def load_malware_filters(self):
        """Загрузка данных для фильтров вредоносных программ"""
        try:
            # Загрузка типов
            self.malware_type_filter.clear()
            self.malware_type_filter.addItem("Все типы")
            types = Malware.select(Malware.malware_type).distinct().order_by(Malware.malware_type)
            type_set = set()
            for malware in types:
                if malware.malware_type:
                    type_set.add(malware.malware_type)
            
            for malware_type in sorted(type_set):
                self.malware_type_filter.addItem(malware_type)
            
            # Загрузка годов
            self.malware_year_filter.clear()
            self.malware_year_filter.addItem("Все годы")
            years = Malware.select(Malware.discovery_date).distinct().order_by(Malware.discovery_date.desc())
            year_set = set()
            for malware in years:
                if malware.discovery_date:
                    year = malware.discovery_date.year
                    year_set.add(year)
            
            for year in sorted(year_set, reverse=True):
                self.malware_year_filter.addItem(str(year))
                
        except Exception as e:
            print(f"Ошибка загрузки фильтров ВП: {e}")

    # Модифицированные методы загрузки данных
    def load_products(self):
        if hasattr(self, 'products_grid'):
            for i in reversed(range(self.products_grid.count())):
                widget = self.products_grid.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
        
        try:
            products = Product.select().order_by(Product.product_id)
            for product in products:
                card = ProductCard(product, self)
                self.products_grid.insertWidget(self.products_grid.count() - 1, card)
            
            # Загружаем фильтры после загрузки данных
            self.load_product_filters()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить товары: {str(e)}")

    def load_manufacturers(self):
        if hasattr(self, 'manufacturers_grid'):
            for i in reversed(range(self.manufacturers_grid.count())):
                widget = self.manufacturers_grid.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
        
        try:
            manufacturers = Manufacturer.select().order_by(Manufacturer.manufacturer_id)
            for manufacturer in manufacturers:
                manufacturer_widget = self.create_manufacturer_widget(manufacturer)
                self.manufacturers_grid.addWidget(manufacturer_widget)
            
            # Загружаем фильтры после загрузки данных
            self.load_manufacturer_filters()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить производителей: {str(e)}")

    def load_signatures(self):
        if hasattr(self, 'signatures_grid'):
            for i in reversed(range(self.signatures_grid.count())):
                widget = self.signatures_grid.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
        
        try:
            # Используем правильный запрос с JOIN
            signatures = (Signature
                        .select(Signature, Manufacturer, Malware)
                        .join(Malware, on=(Signature.malware_id == Malware.id))
                        .join(Manufacturer, JOIN.LEFT_OUTER, on=(Signature.manufacturer_id == Manufacturer.id))
                        .order_by(Signature.signature_id))
            
            for signature in signatures:
                card = SignatureCard(signature, self)
                self.signatures_grid.insertWidget(self.signatures_grid.count() - 1, card)
            
            # Загружаем фильтры после загрузки данных
            self.load_signature_filters()
            
        except Exception as e:
            print(f"Ошибка загрузки сигнатур: {e}")
            # Пробуем альтернативный способ загрузки
            try:
                print("Пробуем альтернативный способ загрузки...")
                signatures = Signature.select().order_by(Signature.signature_id)
                for signature in signatures:
                    # Вручную загружаем связанные объекты
                    try:
                        signature.malware = Malware.get_by_id(signature.malware_id)
                    except:
                        signature.malware = None
                    
                    try:
                        if signature.manufacturer_id:
                            signature.manufacturer = Manufacturer.get_by_id(signature.manufacturer_id)
                        else:
                            signature.manufacturer = None
                    except:
                        signature.manufacturer = None
                    
                    card = SignatureCard(signature, self)
                    self.signatures_grid.insertWidget(self.signatures_grid.count() - 1, card)
                
                self.load_signature_filters()
                
            except Exception as e2:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить сигнатуры: {str(e2)}")

    def filter_products(self):
        search_text = self.product_search_input.text().lower()
        manufacturer_filter = self.product_manufacturer_filter.currentText()
        year_filter = self.product_year_filter.currentText()
        
        for i in range(self.products_grid.count()):
            widget = self.products_grid.itemAt(i).widget()
            if widget and isinstance(widget, ProductCard):
                product = widget.product
                
                # Проверка текстового поиска
                text_match = (search_text in product.name.lower() or 
                             search_text in product.version.lower() or 
                             search_text in product.update_size.lower() or
                             search_text in product.description.lower() or
                             search_text in product.product_id.lower())
                
                # Проверка фильтра по производителю
                manufacturer_match = (manufacturer_filter == "Все производители" or 
                                     manufacturer_filter == product.manufacturer.name)
                
                # Проверка фильтра по году
                year_match = True
                if year_filter != "Все годы" and product.release_date:
                    year_match = str(product.release_date.year) == year_filter
                
                if text_match and manufacturer_match and year_match:
                    widget.show()
                else:
                    widget.hide()

    def filter_manufacturers(self):
        search_text = self.manufacturer_search_input.text().lower()
        country_filter = self.manufacturer_country_filter.currentText()
        year_filter = self.manufacturer_year_filter.currentText()
        
        for i in range(self.manufacturers_grid.count()):
            widget = self.manufacturers_grid.itemAt(i).widget()
            if widget:
                manufacturer = None
                # Находим производителя в виджете
                for child in widget.findChildren(QLabel):
                    if child.text().startswith("ID:"):
                        manufacturer_id = child.text().split(": ")[1]
                        manufacturer = Manufacturer.get_or_none(Manufacturer.manufacturer_id == manufacturer_id)
                        break
                
                if manufacturer:
                    # Проверка текстового поиска
                    text_match = (search_text in manufacturer.name.lower() or 
                                 search_text in manufacturer.country.lower() or 
                                 search_text in manufacturer.description.lower() or
                                 search_text in manufacturer.manufacturer_id.lower())
                    
                    # Проверка фильтра по стране
                    country_match = (country_filter == "Все страны" or 
                                    country_filter == manufacturer.country)
                    
                    # Проверка фильтра по году
                    year_match = True
                    if year_filter != "Все годы" and manufacturer.creation_date:
                        year_match = str(manufacturer.creation_date.year) == year_filter
                    
                    if text_match and country_match and year_match:
                        widget.show()
                    else:
                        widget.hide()
                else:
                    widget.hide()

    def load_manufacturers_combo(self):
        self.manufacturer_combo.clear()
        try:
            manufacturers = Manufacturer.select()
            for manufacturer in manufacturers:
                self.manufacturer_combo.addItem(manufacturer.name, manufacturer.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить производителей: {str(e)}")
    
    def select_manufacturer_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", 
                                                 "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.manufacturer_image_path = file_path
            self.manufacturer_image_label.setText(os.path.basename(file_path))
    
    def create_manufacturer(self):
        if not all([self.manufacturer_id_input.text(), self.manufacturer_name_input.text(), 
                   self.manufacturer_website_input.text(), self.manufacturer_country_input.text(),
                   self.manufacturer_description_input.toPlainText()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        existing_manufacturer = Manufacturer.get_or_none(Manufacturer.manufacturer_id == self.manufacturer_id_input.text())
        if existing_manufacturer:
            QMessageBox.warning(self, "Ошибка", "Производитель с таким номером уже существует")
            self.generate_manufacturer_id()
            return
        
        try:
            manufacturer = Manufacturer(
                manufacturer_id=self.manufacturer_id_input.text(),
                name=self.manufacturer_name_input.text(),
                website=self.manufacturer_website_input.text(),
                country=self.manufacturer_country_input.text(),
                creation_date=self.manufacturer_date_input.date().toPyDate(),
                description=self.manufacturer_description_input.toPlainText(),
                image_path=self.manufacturer_image_path
            )
            manufacturer.save()
            
            QMessageBox.information(self, "Успех", "Производитель успешно создан")
            self.clear_manufacturer_form()
            self.stacked_widget.setCurrentIndex(4)
            self.load_manufacturers()
            
        except IntegrityError as e:
            QMessageBox.critical(self, "Ошибка", f"Производитель с таким ID уже существует. Сгенерирован новый ID.")
            self.generate_manufacturer_id()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать производителя: {str(e)}")
    
    def clear_manufacturer_form(self):
        self.manufacturer_name_input.clear()
        self.manufacturer_website_input.clear()
        self.manufacturer_country_input.clear()
        self.manufacturer_description_input.clear()
        self.manufacturer_date_input.setDate(QDate.currentDate())
        self.manufacturer_image_path = None
        self.manufacturer_image_label.setText("Не выбрано")
        self.generate_manufacturer_id()
    
    def go_back_from_create_manufacturer(self):
        reply = QMessageBox.question(self, "Подтверждение", 
                                   "Вы точно хотите вернуться назад? Все несохраненные данные будут потеряны.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_manufacturer_form()
            self.stacked_widget.setCurrentIndex(8)
    
    def create_manufacturer_widget(self, manufacturer):
        widget = QWidget()
        widget.setObjectName("ManufacturerWidget")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        
        widget.setStyleSheet("""
            QWidget#ManufacturerWidget {
                background-color: #65848f;
                border: 2px solid #f4f4bd;
                border-radius: 12px;
                margin: 5px;
            }
            QWidget#ManufacturerWidget:hover {
                border: 3px solid #f4f4bd;
            }
        """)
        
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_widget.setStyleSheet("background: transparent;")
        
        id_name_layout = QHBoxLayout()
        
        id_label = QLabel(f"ID: {manufacturer.manufacturer_id}")
        id_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 400;
                color: #a7d8de;
                background-color: rgba(0, 0, 0, 0.3);
                padding: 2px 6px;
                border-radius: 8px;
            }
        """)
        
        name_label = QLabel(manufacturer.name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 400;
                color: #f4f4bd;
                padding: 4px 0px;
            }
        """)
        
        id_name_layout.addWidget(id_label)
        id_name_layout.addWidget(name_label)
        id_name_layout.addStretch()
        
        details_label = QLabel(f"Страна: {manufacturer.country} | Сайт: {manufacturer.website}")
        details_label.setStyleSheet("color: #e8e8c8; font-size: 12px;")
        
        desc_label = QLabel(manufacturer.description)
        desc_label.setStyleSheet("color: #e8e8c8; font-size: 11px;")
        desc_label.setWordWrap(True)
        
        info_layout.addLayout(id_name_layout)
        info_layout.addWidget(details_label)
        info_layout.addWidget(desc_label)
        
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_widget.setStyleSheet("background: transparent;")
        
        detail_btn = QPushButton("Подробнее")
        detail_btn.setFixedSize(80, 30)
        detail_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
            QPushButton:pressed {
                background-color: #3a6e7c;
            }
        """)
        detail_btn.clicked.connect(lambda: self.show_manufacturer_detail(manufacturer))
        
        edit_btn = QPushButton("Редактировать")
        edit_btn.setFixedSize(80, 30)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5868;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a8e9c;
            }
            QPushButton:pressed {
                background-color: #3a6e7c;
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_manufacturer(manufacturer))
        
        delete_btn = QPushButton("Удалить")
        delete_btn.setFixedSize(80, 30)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8c4a4a;
                color: #f4f4bd;
                border-radius: 15px;
                font-weight: 400;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #9c5a5a;
            }
            QPushButton:pressed {
                background-color: #7c3a3a;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_manufacturer(manufacturer))
        
        buttons_layout.addWidget(detail_btn)
        buttons_layout.addWidget(edit_btn)
        buttons_layout.addWidget(delete_btn)
        
        layout.addWidget(info_widget)
        layout.addWidget(buttons_widget)
        
        return widget
    
    def edit_manufacturer(self, manufacturer):
        dialog = EditManufacturerDialog(manufacturer, self)
        dialog.exec()
    
    def delete_manufacturer(self, manufacturer):
        reply = QMessageBox.question(self, "Удаление", 
                                   f"Вы точно хотите удалить производителя '{manufacturer.name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            products_count = Product.select().where(Product.manufacturer == manufacturer).count()
            if products_count > 0:
                QMessageBox.warning(self, "Ошибка", 
                                  f"Невозможно удалить производителя. У него есть {products_count} товар(ов).")
                return
            
            try:
                manufacturer.delete_instance()
                self.load_manufacturers()
                QMessageBox.information(self, "Успех", "Производитель успешно удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить производителя: {str(e)}")

    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", 
                                                 "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.image_path = file_path
            self.image_label.setText(os.path.basename(file_path))
    
    def create_product(self):
        if not all([self.product_id_input.text(), self.name_input.text(), 
                   self.description_input.toPlainText(), self.version_input.text(),
                   self.size_input.text()]):
            QMessageBox.warning(self, "Ошибка", "Все поля должны быть заполнены")
            return
        
        existing_product = Product.get_or_none(Product.product_id == self.product_id_input.text())
        if existing_product:
            QMessageBox.warning(self, "Ошибка", "Товар с таким номером уже существует")
            self.generate_product_id()
            return
        
        try:
            product = Product(
                product_id=self.product_id_input.text(),
                name=self.name_input.text(),
                description=self.description_input.toPlainText(),
                version=self.version_input.text(),
                release_date=self.date_input.date().toPyDate(),
                update_size=self.size_input.text(),
                image_path=self.image_path,
                manufacturer_id=self.manufacturer_combo.currentData()
            )
            product.save()
            
            QMessageBox.information(self, "Успех", "Товар успешно создан")
            self.clear_form()
            self.stacked_widget.setCurrentIndex(7)
            self.load_products()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать товар: {str(e)}")
    
    def clear_form(self):
        self.name_input.clear()
        self.description_input.clear()
        self.version_input.clear()
        self.size_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.image_path = None
        self.image_label.setText("Не выбрано")
        self.generate_product_id()
    
    def go_back_from_create(self):
        reply = QMessageBox.question(self, "Подтверждение", 
                                   "Вы точно хотите вернуться назад? Все несохраненные данные будут потеряны.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_form()
            self.stacked_widget.setCurrentIndex(8)


# Добавьте этот код в конец вашего файла, перед запуском приложения

# Добавьте этот код в конец вашего файла, перед запуском приложения

import os
import logging
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, cm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Регистрируем кириллические шрифты
try:
    # Попробуем зарегистрировать стандартные системные шрифты
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))
    CYRILLIC_FONT_AVAILABLE = True
except:
    try:
        # Альтернативные шрифты
        pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'arialbd.ttf'))
        CYRILLIC_FONT_AVAILABLE = True
    except:
        # Если шрифты не найдены, используем встроенный шрифт (будет показывать квадраты для кириллицы)
        CYRILLIC_FONT_AVAILABLE = False
        logger.warning("Кириллические шрифты не найдены. Русский текст может отображаться некорректно.")

class PDFReporter:
    """Базовый класс для генерации PDF отчетов с поддержкой кириллицы"""
    
    def __init__(self, filename):
        self.filename = filename
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Настройка пользовательских стилей с поддержкой кириллицы"""
        # Определяем шрифты для использования
        if CYRILLIC_FONT_AVAILABLE:
            normal_font = 'DejaVuSans'
            bold_font = 'DejaVuSans-Bold'
        else:
            normal_font = 'Helvetica'
            bold_font = 'Helvetica-Bold'
        
        # Создаем стиль для русского текста
        self.styles.add(ParagraphStyle(
            name='RussianTitle',
            fontName=bold_font,
            fontSize=16,
            alignment=1,  # Center alignment
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='RussianHeading2',
            parent=self.styles['Heading2'],
            fontName=bold_font,
            fontSize=14,
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='RussianNormal',
            parent=self.styles['Normal'],
            fontName=normal_font,
            fontSize=10,
            leading=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='RussianTableHeader',
            parent=self.styles['Normal'],
            fontName=bold_font,
            fontSize=10,
            alignment=1,  # Center
            textColor=colors.white
        ))
        
        self.styles.add(ParagraphStyle(
            name='RussianTableCell',
            parent=self.styles['Normal'],
            fontName=normal_font,
            fontSize=8,
            leading=10
        ))

    def create_title_page(self, canvas, doc, title, subtitle=""):
        """Создание титульной страницы с поддержкой кириллицы"""
        canvas.saveState()
        
        # Устанавливаем шрифт в зависимости от доступности кириллических шрифтов
        if CYRILLIC_FONT_AVAILABLE:
            canvas.setFont('DejaVuSans-Bold', 16)
        else:
            canvas.setFont('Helvetica-Bold', 16)
            
        canvas.drawCentredString(A4[0]/2, A4[1]-100, title)
        
        if subtitle:
            if CYRILLIC_FONT_AVAILABLE:
                canvas.setFont('DejaVuSans', 12)
            else:
                canvas.setFont('Helvetica', 12)
            canvas.drawCentredString(A4[0]/2, A4[1]-130, subtitle)
        
        if CYRILLIC_FONT_AVAILABLE:
            canvas.setFont('DejaVuSans', 10)
        else:
            canvas.setFont('Helvetica', 10)
            
        canvas.drawCentredString(A4[0]/2, A4[1]-160, f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        canvas.drawCentredString(A4[0]/2, A4[1]-180, "Антивирусная база данных")
        canvas.restoreState()

class StatisticalPDFReporter(PDFReporter):
    """Генератор статистического отчета с поддержкой кириллицы"""
    
    def __init__(self, filename="statistical_report.pdf"):
        super().__init__(filename)
    
    def generate_report(self):
        """Генерация статистического отчета"""
        try:
            doc = SimpleDocTemplate(
                self.filename,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            story = []
            
            # Титульная страница
            story.append(Paragraph("СТАТИСТИЧЕСКИЙ ОТЧЕТ", self.styles['RussianTitle']))
            story.append(Paragraph("Антивирусная база данных", self.styles['RussianHeading2']))
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M')}", 
                                 self.styles['RussianNormal']))
            story.append(Spacer(1, 40))
            
            # Общая статистика
            story.append(Paragraph("ОБЩАЯ СТАТИСТИКА", self.styles['RussianHeading2']))
            story.append(Spacer(1, 12))
            
            # Получаем статистические данные
            stats_data = self.get_statistical_data()
            story.extend(self.create_statistics_section(stats_data))
            
            # Анализ данных
            story.append(Paragraph("АНАЛИЗ ДАННЫХ", self.styles['RussianHeading2']))
            story.append(Spacer(1, 12))
            
            analysis_data = self.get_analysis_data()
            story.extend(self.create_analysis_section(analysis_data))
            
            doc.build(story, onFirstPage=self.add_page_number, onLaterPages=self.add_page_number)
            logger.info(f"Статистический отчет создан: {self.filename}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка генерации статистического отчета: {e}")
            return False
    
    def add_page_number(self, canvas, doc):
        """Добавляет номер страницы"""
        canvas.saveState()
        if CYRILLIC_FONT_AVAILABLE:
            canvas.setFont('DejaVuSans', 9)
        else:
            canvas.setFont('Helvetica', 9)
        page_num_text = f"Страница {doc.page}"
        canvas.drawRightString(A4[0] - 72, 30, page_num_text)
        canvas.restoreState()
    
    def get_statistical_data(self):
        """Получение статистических данных из БД"""
        try:
            data = {
                'total_manufacturers': Manufacturer.select().count(),
                'total_products': Product.select().count(),
                'total_malware': Malware.select().count(),
                'total_signatures': Signature.select().count(),
                'countries_count': len(set(m.country for m in Manufacturer.select())),
                'critical_threats': Malware.select().where(Malware.threat_level == 'Критический').count(),
                'malware_types': len(set(m.malware_type for m in Malware.select())),
                'recent_products': Product.select().where(
                    Product.release_date >= datetime.now().date() - timedelta(days=30)
                ).count()
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Ошибка получения статистических данных: {e}")
            return {}
    
    def get_analysis_data(self):
        """Получение данных для анализа"""
        try:
            # Распределение продуктов по производителям
            manufacturer_stats = []
            manufacturers = Manufacturer.select()
            for manufacturer in manufacturers:
                products_count = Product.select().where(Product.manufacturer == manufacturer).count()
                manufacturer_stats.append({
                    'name': manufacturer.name,
                    'products_count': products_count
                })
            
            # Распределение ВП по уровням опасности
            threat_stats = []
            threat_levels = ['Критический', 'Высокий', 'Средний', 'Низкий']
            for level in threat_levels:
                count = Malware.select().where(Malware.threat_level == level).count()
                threat_stats.append({
                    'level': level,
                    'count': count
                })
            
            # Топ производителей по количеству продуктов
            manufacturer_stats.sort(key=lambda x: x['products_count'], reverse=True)
            top_manufacturers = manufacturer_stats[:5]
            
            return {
                'manufacturer_stats': manufacturer_stats,
                'threat_stats': threat_stats,
                'top_manufacturers': top_manufacturers
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения данных анализа: {e}")
            return {}
    
    def create_statistics_section(self, stats_data):
        """Создание раздела общей статистики"""
        elements = []
        
        if not stats_data:
            elements.append(Paragraph("Нет данных для отображения", self.styles['RussianNormal']))
            return elements
        
        # Создаем таблицу со статистикой
        stats_table_data = [
            [Paragraph('Показатель', self.styles['RussianTableHeader']), 
             Paragraph('Значение', self.styles['RussianTableHeader'])],
            [Paragraph('Всего производителей', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('total_manufacturers', 0)), self.styles['RussianTableCell'])],
            [Paragraph('Всего антивирусных программ', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('total_products', 0)), self.styles['RussianTableCell'])],
            [Paragraph('Всего вредоносных программ', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('total_malware', 0)), self.styles['RussianTableCell'])],
            [Paragraph('Всего сигнатур обнаружения', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('total_signatures', 0)), self.styles['RussianTableCell'])],
            [Paragraph('Стран производителей', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('countries_count', 0)), self.styles['RussianTableCell'])],
            [Paragraph('Критических угроз', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('critical_threats', 0)), self.styles['RussianTableCell'])],
            [Paragraph('Типов вредоносных программ', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('malware_types', 0)), self.styles['RussianTableCell'])],
            [Paragraph('Новых продуктов за 30 дней', self.styles['RussianTableCell']), 
             Paragraph(str(stats_data.get('recent_products', 0)), self.styles['RussianTableCell'])]
        ]
        
        stats_table = Table(stats_table_data, colWidths=[3*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3e6767')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f4f4bd')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def create_analysis_section(self, analysis_data):
        """Создание раздела анализа данных"""
        elements = []
        
        if not analysis_data:
            elements.append(Paragraph("Нет данных для анализа", self.styles['RussianNormal']))
            return elements
        
        # Топ производителей
        elements.append(Paragraph("ТОП-5 ПРОИЗВОДИТЕЛЕЙ", self.styles['RussianHeading2']))
        
        top_manufacturers_data = [
            [Paragraph('Производитель', self.styles['RussianTableHeader']), 
             Paragraph('Количество продуктов', self.styles['RussianTableHeader'])]
        ]
        
        for manufacturer in analysis_data.get('top_manufacturers', []):
            top_manufacturers_data.append([
                Paragraph(manufacturer['name'], self.styles['RussianTableCell']),
                Paragraph(str(manufacturer['products_count']), self.styles['RussianTableCell'])
            ])
        
        top_table = Table(top_manufacturers_data, colWidths=[3.5*inch, 2*inch])
        top_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c5868')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8e8c8')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(top_table)
        elements.append(Spacer(1, 20))
        
        # Распределение по уровням опасности
        elements.append(Paragraph("РАСПРЕДЕЛЕНИЕ ПО УРОВНЯМ ОПАСНОСТИ", self.styles['RussianHeading2']))
        
        threat_data = [
            [Paragraph('Уровень опасности', self.styles['RussianTableHeader']), 
             Paragraph('Количество', self.styles['RussianTableHeader'])]
        ]
        
        for threat in analysis_data.get('threat_stats', []):
            threat_data.append([
                Paragraph(threat['level'], self.styles['RussianTableCell']),
                Paragraph(str(threat['count']), self.styles['RussianTableCell'])
            ])
        
        threat_table = Table(threat_data, colWidths=[2.5*inch, 1.5*inch])
        threat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8c4a4a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffcccc')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(threat_table)
        
        return elements

class DetailedPDFReporter(PDFReporter):
    """Генератор детального табличного отчета с поддержкой кириллицы"""
    
    def __init__(self, filename="detailed_report.pdf"):
        super().__init__(filename)
    
    def generate_report(self):
        """Генерация детального отчета"""
        try:
            doc = SimpleDocTemplate(
                self.filename,
                pagesize=A4,
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36
            )
            
            story = []
            
            # Титульная страница
            story.extend(self.create_title_section())
            
            # Раздел 1: Производители
            story.extend(self.create_manufacturers_section())
            
            # Раздел 2: Антивирусные программы
            story.extend(self.create_products_section())
            
            # Раздел 3: Вредоносные программы
            story.extend(self.create_malware_section())
            
            # Раздел 4: Сигнатуры
            story.extend(self.create_signatures_section())
            
            doc.build(story, onFirstPage=self.add_page_number, onLaterPages=self.add_page_number)
            logger.info(f"Детальный отчет создан: {self.filename}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка генерации детального отчета: {e}")
            return False
    
    def add_page_number(self, canvas, doc):
        """Добавляет номер страницы"""
        canvas.saveState()
        if CYRILLIC_FONT_AVAILABLE:
            canvas.setFont('DejaVuSans', 9)
        else:
            canvas.setFont('Helvetica', 9)
        page_num_text = f"Страница {doc.page}"
        canvas.drawRightString(A4[0] - 36, 30, page_num_text)
        canvas.restoreState()
    
    def create_title_section(self):
        """Создание титульного раздела"""
        elements = []
        
        elements.append(Paragraph("ДЕТАЛЬНЫЙ ОТЧЕТ", self.styles['RussianTitle']))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("Антивирусная база данных", self.styles['RussianHeading2']))
        elements.append(Spacer(1, 5))
        elements.append(Paragraph(f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M')}", 
                               self.styles['RussianNormal']))
        elements.append(Spacer(1, 30))
        
        return elements
    
    def create_manufacturers_section(self):
        """Создание раздела производителей"""
        elements = []
        
        elements.append(Paragraph("1. ПРОИЗВОДИТЕЛИ АНТИВИРУСОВ", self.styles['RussianHeading2']))
        elements.append(Spacer(1, 12))
        
        try:
            manufacturers = Manufacturer.select().order_by(Manufacturer.name)
            
            if not manufacturers:
                elements.append(Paragraph("Нет данных о производителях", self.styles['RussianNormal']))
                return elements
            
            # Создаем таблицу
            table_data = [[
                Paragraph('ID', self.styles['RussianTableHeader']),
                Paragraph('Название', self.styles['RussianTableHeader']),
                Paragraph('Страна', self.styles['RussianTableHeader']),
                Paragraph('Сайт', self.styles['RussianTableHeader']),
                Paragraph('Дата создания', self.styles['RussianTableHeader'])
            ]]
            
            for manufacturer in manufacturers:
                creation_date = manufacturer.creation_date.strftime('%d.%m.%Y') if manufacturer.creation_date else 'Н/Д'
                table_data.append([
                    Paragraph(manufacturer.manufacturer_id, self.styles['RussianTableCell']),
                    Paragraph(manufacturer.name, self.styles['RussianTableCell']),
                    Paragraph(manufacturer.country, self.styles['RussianTableCell']),
                    Paragraph(manufacturer.website, self.styles['RussianTableCell']),
                    Paragraph(creation_date, self.styles['RussianTableCell'])
                ])
            
            # Создаем таблицу с автоматическим определением ширины колонок
            table = Table(table_data, colWidths=[1*inch, 2*inch, 1*inch, 1.5*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3e6767')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f8f8')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f4bd')])
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
            
            # Статистика по разделу
            elements.append(Paragraph(f"Всего производителей: {len(manufacturers)}", 
                                   self.styles['RussianNormal']))
            elements.append(Spacer(1, 20))
            
        except Exception as e:
            logger.error(f"Ошибка создания раздела производителей: {e}")
            elements.append(Paragraph("Ошибка загрузки данных производителей", self.styles['RussianNormal']))
        
        return elements
    
    def create_products_section(self):
        """Создание раздела антивирусных программ"""
        elements = []
        
        elements.append(Paragraph("2. АНТИВИРУСНЫЕ ПРОГРАММЫ", self.styles['RussianHeading2']))
        elements.append(Spacer(1, 12))
        
        try:
            products = (Product
                       .select(Product, Manufacturer)
                       .join(Manufacturer)
                       .order_by(Product.name))
            
            if not products:
                elements.append(Paragraph("Нет данных об антивирусных программах", self.styles['RussianNormal']))
                return elements
            
            # Создаем таблицу
            table_data = [[
                Paragraph('ID', self.styles['RussianTableHeader']),
                Paragraph('Название', self.styles['RussianTableHeader']),
                Paragraph('Производитель', self.styles['RussianTableHeader']),
                Paragraph('Цена', self.styles['RussianTableHeader']),
                Paragraph('Рейтинг', self.styles['RussianTableHeader']),
                Paragraph('Дата выпуска', self.styles['RussianTableHeader'])
            ]]
            
            for product in products:
                release_date = product.release_date.strftime('%d.%m.%Y') if product.release_date else 'Н/Д'
                table_data.append([
                    Paragraph(product.product_id, self.styles['RussianTableCell']),
                    Paragraph(product.name, self.styles['RussianTableCell']),
                    Paragraph(product.manufacturer.name, self.styles['RussianTableCell']),
                    Paragraph(product.version, self.styles['RussianTableCell']),
                    Paragraph(product.update_size, self.styles['RussianTableCell']),
                    Paragraph(release_date, self.styles['RussianTableCell'])
                ])
            
            table = Table(table_data, colWidths=[0.8*inch, 1.5*inch, 1.2*inch, 0.8*inch, 0.8*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c5868')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f8f8')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#e8e8c8')])
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(f"Всего антивирусных программ: {len(products)}", 
                                   self.styles['RussianNormal']))
            elements.append(Spacer(1, 20))
            
        except Exception as e:
            logger.error(f"Ошибка создания раздела продуктов: {e}")
            elements.append(Paragraph("Ошибка загрузки данных антивирусных программ", self.styles['RussianNormal']))
        
        return elements
    
    def create_malware_section(self):
        """Создание раздела вредоносных программ"""
        elements = []
        
        elements.append(Paragraph("3. ВРЕДОНОСНЫЕ ПРОГРАММЫ", self.styles['RussianHeading2']))
        elements.append(Spacer(1, 12))
        
        try:
            malware_list = Malware.select().order_by(Malware.threat_level.desc(), Malware.name)
            
            if not malware_list:
                elements.append(Paragraph("Нет данных о вредоносных программах", self.styles['RussianNormal']))
                return elements
            
            table_data = [[
                Paragraph('ID', self.styles['RussianTableHeader']),
                Paragraph('Название', self.styles['RussianTableHeader']),
                Paragraph('Тип', self.styles['RussianTableHeader']),
                Paragraph('Уровень опасности', self.styles['RussianTableHeader']),
                Paragraph('Дата обнаружения', self.styles['RussianTableHeader'])
            ]]
            
            for malware in malware_list:
                discovery_date = malware.discovery_date.strftime('%d.%m.%Y') if malware.discovery_date else 'Н/Д'
                table_data.append([
                    Paragraph(malware.malware_id, self.styles['RussianTableCell']),
                    Paragraph(malware.name, self.styles['RussianTableCell']),
                    Paragraph(malware.malware_type, self.styles['RussianTableCell']),
                    Paragraph(malware.threat_level, self.styles['RussianTableCell']),
                    Paragraph(discovery_date, self.styles['RussianTableCell'])
                ])
            
            table = Table(table_data, colWidths=[0.8*inch, 2*inch, 1.2*inch, 1.2*inch, 1*inch])
            
            # Создаем стиль таблицы
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8c4a4a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f8f8')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ])
            
            # Добавляем цветовое кодирование для уровней опасности
            for i, malware in enumerate(malware_list, start=1):
                if malware.threat_level == 'Критический':
                    style.add('BACKGROUND', (3, i), (3, i), colors.HexColor('#ffcccc'))
                elif malware.threat_level == 'Высокий':
                    style.add('BACKGROUND', (3, i), (3, i), colors.HexColor('#ffebcc'))
            
            table.setStyle(style)
            
            elements.append(table)
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(f"Всего вредоносных программ: {len(malware_list)}", 
                                   self.styles['RussianNormal']))
            elements.append(Spacer(1, 20))
            
        except Exception as e:
            logger.error(f"Ошибка создания раздела ВП: {e}")
            elements.append(Paragraph("Ошибка загрузки данных вредоносных программ", self.styles['RussianNormal']))
        
        return elements
    
    def create_signatures_section(self):
        """Создание раздела сигнатур - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        elements = []
        
        elements.append(Paragraph("4. СИГНАТУРЫ ОБНАРУЖЕНИЯ", self.styles['RussianHeading2']))
        elements.append(Spacer(1, 12))

        try:
            # ПРОСТАЯ ЗАГРУЗКА СИГНАТУР БЕЗ СЛОЖНЫХ JOIN
            signatures = Signature.select().order_by(Signature.creation_date.desc())
            
            if not signatures:
                elements.append(Paragraph("Нет данных о сигнатурах", self.styles['RussianNormal']))
                return elements
            
            table_data = [[
                Paragraph('ID', self.styles['RussianTableHeader']),
                Paragraph('Название', self.styles['RussianTableHeader']),
                Paragraph('Вредоносная программа', self.styles['RussianTableHeader']),
                Paragraph('Производитель', self.styles['RussianTableHeader']),
                Paragraph('Дата создания', self.styles['RussianTableHeader'])
            ]]
            
            for signature in signatures:
                try:
                    # Загружаем связанные объекты вручную
                    malware_name = "Неизвестно"
                    if signature.malware_id:
                        try:
                            malware = Malware.get_by_id(signature.malware_id)
                            malware_name = f"{malware.malware_id} - {malware.name}"
                        except:
                            malware_name = "ВП не найдена"
                    
                    manufacturer_name = "Не указан"
                    if signature.manufacturer_id:
                        try:
                            manufacturer = Manufacturer.get_by_id(signature.manufacturer_id)
                            manufacturer_name = manufacturer.name
                        except:
                            manufacturer_name = "Производитель не найден"
                    
                    creation_date = signature.creation_date.strftime('%d.%m.%Y') if signature.creation_date else 'Н/Д'
                    
                    table_data.append([
                        Paragraph(signature.signature_id or "", self.styles['RussianTableCell']),
                        Paragraph(signature.name or "", self.styles['RussianTableCell']),
                        Paragraph(malware_name, self.styles['RussianTableCell']),
                        Paragraph(manufacturer_name, self.styles['RussianTableCell']),
                        Paragraph(creation_date, self.styles['RussianTableCell'])
                    ])
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки сигнатуры {signature.signature_id}: {e}")
                    continue
            
            if len(table_data) == 1:  # Только заголовки
                elements.append(Paragraph("Нет данных для отображения", self.styles['RussianNormal']))
                return elements
            
            table = Table(table_data, colWidths=[0.8*inch, 1.5*inch, 2*inch, 1.2*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5a8e9c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f8f8')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica' if not CYRILLIC_FONT_AVAILABLE else 'DejaVuSans'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#e6f0ff')])
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(f"Всего сигнатур: {len(table_data) - 1}", self.styles['RussianNormal']))
            
        except Exception as e:
            logger.error(f"Ошибка создания раздела сигнатур: {e}")
            elements.append(Paragraph(f"Ошибка загрузки данных сигнатур: {str(e)}", self.styles['RussianNormal']))
        
        return elements

# Интеграция с главным окном приложения
def add_pdf_export_to_main_window(main_window_class):
    """Добавляет функциональность PDF-экспорта в главное окно"""
    
    original_init = main_window_class.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.pdf_reporter = PDFReporter("temp.pdf")
    
    def export_statistical_pdf(self):
        """Экспорт статистического отчета в PDF"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Сохранить статистический отчет", 
                "antivirus_statistical_report.pdf", 
                "PDF Files (*.pdf)"
            )
            
            if filename:
                reporter = StatisticalPDFReporter(filename)
                success = reporter.generate_report()
                
                if success:
                    QMessageBox.information(self, "Успех", 
                                          f"Статистический отчет успешно сохранен:\n{filename}")
                    # Открываем файл
                    try:
                        os.startfile(filename)
                    except:
                        QMessageBox.information(self, "Успех", f"Файл сохранен: {filename}")
                else:
                    QMessageBox.critical(self, "Ошибка", 
                                       "Не удалось создать статистический отчет")
                    
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", 
                               f"Произошла ошибка при экспорте:\n{str(e)}")
    
    def export_detailed_pdf(self):
        """Экспорт детального отчета в PDF"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Сохранить детальный отчет", 
                "antivirus_detailed_report.pdf", 
                "PDF Files (*.pdf)"
            )
            
            if filename:
                reporter = DetailedPDFReporter(filename)
                success = reporter.generate_report()
                
                if success:
                    QMessageBox.information(self, "Успех", 
                                          f"Детальный отчет успешно сохранен:\n{filename}")
                    # Открываем файл
                    try:
                        os.startfile(filename)
                    except:
                        QMessageBox.information(self, "Успех", f"Файл сохранен: {filename}")
                else:
                    QMessageBox.critical(self, "Ошибка", 
                                       "Не удалось создать детальный отчет")
                    
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", 
                               f"Произошла ошибка при экспорте:\n{str(e)}")
    
    # Добавляем методы в класс
    main_window_class.__init__ = new_init
    main_window_class.export_statistical_pdf = export_statistical_pdf
    main_window_class.export_detailed_pdf = export_detailed_pdf
    
    return main_window_class

# Модифицируем класс MainWindow для добавления кнопок PDF-экспорта
@add_pdf_export_to_main_window
class EnhancedMainWindow(MainWindow):
    pass

# Добавляем кнопки PDF-экспорта в меню
def add_pdf_buttons_to_menu(self, layout):
    """Добавляет кнопки PDF-экспорта в меню"""
    # После кнопки Excel экспорта добавляем PDF кнопки
    
    pdf_export_widget = QWidget()
    pdf_export_layout = QVBoxLayout(pdf_export_widget)
    pdf_export_layout.setSpacing(5)
    
    # Кнопка статистического отчета
    stats_pdf_btn = QPushButton("📊 Стат. отчет PDF")
    stats_pdf_btn.setFixedHeight(35)
    stats_pdf_btn.setStyleSheet("""
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border-radius: 15px;
            font-weight: 400;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
    """)
    stats_pdf_btn.clicked.connect(self.export_statistical_pdf)
    pdf_export_layout.addWidget(stats_pdf_btn)
    
    # Кнопка детального отчета
    detailed_pdf_btn = QPushButton("📋 Дет. отчет PDF")
    detailed_pdf_btn.setFixedHeight(35)
    detailed_pdf_btn.setStyleSheet("""
        QPushButton {
            background-color: #2196F3;
            color: white;
            border-radius: 15px;
            font-weight: 400;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #1976D2;
        }
    """)
    detailed_pdf_btn.clicked.connect(self.export_detailed_pdf)
    pdf_export_layout.addWidget(detailed_pdf_btn)
    
    # Добавляем в основной layout после Excel кнопки
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item and hasattr(item.widget(), 'text') and item.widget().text() == "Экспорт в Excel":
            layout.insertWidget(i + 1, pdf_export_widget)
            break

# Заменяем оригинальный метод создания меню
OriginalMainWindow = MainWindow
MainWindow = EnhancedMainWindow

# Модифицируем метод create_menu_buttons для добавления PDF кнопок
original_create_menu_buttons = MainWindow.create_menu_buttons

def new_create_menu_buttons(self, layout):
    original_create_menu_buttons(self, layout)
    add_pdf_buttons_to_menu(self, layout)

MainWindow.create_menu_buttons = new_create_menu_buttons

# Запуск приложения
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Проверяем подключение к базе данных перед запуском
    if not db_initialized:
        print("Предупреждение: База данных не инициализирована. Приложение будет работать в ограниченном режиме.")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
    pass 
