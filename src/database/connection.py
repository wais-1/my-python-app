import mysql.connector
from mysql.connector import Error
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from config.database import DATABASE_CONFIG

def get_connection():
    """Создает и возвращает соединение с базой данных"""
    try:
        connection = mysql.connector.connect(
            host=DATABASE_CONFIG['localhost'],
            port=DATABASE_CONFIG['3306'],
            database=DATABASE_CONFIG['antiviruss'],
            user=DATABASE_CONFIG['root'],
            password=DATABASE_CONFIG['123']
        )
        return connection
    except Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None
