import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Open a new connection to the POS database."""
    conn_str = (
        f"DRIVER={{{os.getenv('POS_DRIVER')}}};"
        f"SERVER={os.getenv('POS_SERVER')};"
        f"DATABASE={os.getenv('POS_DATABASE')};"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)