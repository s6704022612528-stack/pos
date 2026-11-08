import pyodbc

print("Drivers:", pyodbc.drivers())

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=master;"
    "Trusted_Connection=yes;"
)
print(conn.cursor().execute("SELECT @@VERSION").fetchone()[0])

