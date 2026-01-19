import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_CONFIG = {
    'host': os.getenv('localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('antiviruss'),
    'user': os.getenv('root'),
    'password': os.getenv('123'),
    'charset': os.getenv('utf8mb4')
}
