/* 01_schema.sql - POS database for a convenience store (SQL Server 2019)
   How to run: open in SSMS, click in the editor (select nothing), press F5.
   Safe to re-run: existing tables are dropped and recreated (dev only). */

IF DB_ID(N'POS') IS NULL
    CREATE DATABASE POS;
GO

USE POS;
GO

/* ---- drop old tables (children first) ---- */
DROP TABLE IF EXISTS StockMovement;
DROP TABLE IF EXISTS Payment;
DROP TABLE IF EXISTS SaleItem;
DROP TABLE IF EXISTS Sale;
DROP TABLE IF EXISTS Product;
DROP TABLE IF EXISTS Category;
DROP TABLE IF EXISTS Customer;
DROP TABLE IF EXISTS Employee;
GO

/* ---- 1) Category ---- */
CREATE TABLE Category (
    CategoryID    INT IDENTITY(1,1) CONSTRAINT PK_Category PRIMARY KEY,
    CategoryName  NVARCHAR(100) NOT NULL CONSTRAINT UQ_Category_Name UNIQUE
);
GO

/* ---- 2) Product ---- */
CREATE TABLE Product (
    ProductID     INT IDENTITY(1,1) CONSTRAINT PK_Product PRIMARY KEY,
    Barcode       VARCHAR(20)   NOT NULL CONSTRAINT UQ_Product_Barcode UNIQUE,
    ProductName   NVARCHAR(200) NOT NULL,
    CategoryID    INT           NOT NULL CONSTRAINT FK_Product_Category REFERENCES Category(CategoryID),
    CostPrice     DECIMAL(10,2) NOT NULL CONSTRAINT CK_Product_Cost CHECK (CostPrice >= 0),
    SellPrice     DECIMAL(10,2) NOT NULL CONSTRAINT CK_Product_Sell CHECK (SellPrice >= 0),
    StockQty      INT           NOT NULL CONSTRAINT DF_Product_Stock DEFAULT 0 CONSTRAINT CK_Product_Stock CHECK (StockQty >= 0),
    ReorderLevel  INT           NOT NULL CONSTRAINT DF_Product_Reorder DEFAULT 10 CONSTRAINT CK_Product_Reorder CHECK (ReorderLevel >= 0),
    IsActive      BIT           NOT NULL CONSTRAINT DF_Product_Active DEFAULT 1,
    CreatedAt     DATETIME2(0)  NOT NULL CONSTRAINT DF_Product_Created DEFAULT SYSDATETIME()
);
GO

/* ---- 3) Customer ---- */
CREATE TABLE Customer (
    CustomerID    INT IDENTITY(1,1) CONSTRAINT PK_Customer PRIMARY KEY,
    Phone         VARCHAR(15)   NOT NULL CONSTRAINT UQ_Customer_Phone UNIQUE,
    FullName      NVARCHAR(150) NOT NULL,
    Points        INT           NOT NULL CONSTRAINT DF_Customer_Points DEFAULT 0 CONSTRAINT CK_Customer_Points CHECK (Points >= 0),
    CreatedAt     DATETIME2(0)  NOT NULL CONSTRAINT DF_Customer_Created DEFAULT SYSDATETIME()
);
GO

/* ---- 4) Employee (store a password HASH only, never the real password) ---- */
CREATE TABLE Employee (
    EmployeeID    INT IDENTITY(1,1) CONSTRAINT PK_Employee PRIMARY KEY,
    Username      VARCHAR(50)   NOT NULL CONSTRAINT UQ_Employee_Username UNIQUE,
    PasswordHash  VARCHAR(255)  NOT NULL,
    FullName      NVARCHAR(150) NOT NULL,
    [Role]        VARCHAR(20)   NOT NULL CONSTRAINT CK_Employee_Role CHECK ([Role] IN ('cashier', 'manager')),
    IsActive      BIT           NOT NULL CONSTRAINT DF_Employee_Active DEFAULT 1
);
GO

/* ---- 5) Sale (bill header; CustomerID NULL = walk-in customer) ---- */
CREATE TABLE Sale (
    SaleID          INT IDENTITY(1,1) CONSTRAINT PK_Sale PRIMARY KEY,
    SaleDate        DATETIME2(0)  NOT NULL CONSTRAINT DF_Sale_Date DEFAULT SYSDATETIME(),
    EmployeeID      INT           NOT NULL CONSTRAINT FK_Sale_Employee REFERENCES Employee(EmployeeID),
    CustomerID      INT           NULL CONSTRAINT FK_Sale_Customer REFERENCES Customer(CustomerID),
    Subtotal        DECIMAL(12,2) NOT NULL CONSTRAINT CK_Sale_Subtotal CHECK (Subtotal >= 0),
    DiscountAmount  DECIMAL(12,2) NOT NULL CONSTRAINT DF_Sale_Discount DEFAULT 0 CONSTRAINT CK_Sale_Discount CHECK (DiscountAmount >= 0),
    VatAmount       DECIMAL(12,2) NOT NULL CONSTRAINT DF_Sale_Vat DEFAULT 0 CONSTRAINT CK_Sale_Vat CHECK (VatAmount >= 0),
    TotalAmount     DECIMAL(12,2) NOT NULL CONSTRAINT CK_Sale_Total CHECK (TotalAmount >= 0),
    [Status]        VARCHAR(20)   NOT NULL CONSTRAINT DF_Sale_Status DEFAULT 'completed' CONSTRAINT CK_Sale_Status CHECK ([Status] IN ('completed', 'cancelled'))
);
GO

/* ---- 6) SaleItem (UnitPrice and UnitCost are the values at the time of sale) ---- */
CREATE TABLE SaleItem (
    SaleItemID    INT IDENTITY(1,1) CONSTRAINT PK_SaleItem PRIMARY KEY,
    SaleID        INT           NOT NULL CONSTRAINT FK_SaleItem_Sale REFERENCES Sale(SaleID),
    ProductID     INT           NOT NULL CONSTRAINT FK_SaleItem_Product REFERENCES Product(ProductID),
    Quantity      INT           NOT NULL CONSTRAINT CK_SaleItem_Qty CHECK (Quantity > 0),
    UnitPrice     DECIMAL(10,2) NOT NULL CONSTRAINT CK_SaleItem_Price CHECK (UnitPrice >= 0),
    UnitCost      DECIMAL(10,2) NOT NULL CONSTRAINT CK_SaleItem_Cost CHECK (UnitCost >= 0),
    LineTotal     AS (Quantity * UnitPrice) PERSISTED,
    CONSTRAINT UQ_SaleItem_Sale_Product UNIQUE (SaleID, ProductID)
);
GO

/* ---- 7) Payment (Amount = money received, ChangeAmount = change given) ---- */
CREATE TABLE Payment (
    PaymentID     INT IDENTITY(1,1) CONSTRAINT PK_Payment PRIMARY KEY,
    SaleID        INT           NOT NULL CONSTRAINT FK_Payment_Sale REFERENCES Sale(SaleID),
    Method        VARCHAR(20)   NOT NULL CONSTRAINT CK_Payment_Method CHECK (Method IN ('cash', 'transfer')),
    Amount        DECIMAL(12,2) NOT NULL CONSTRAINT CK_Payment_Amount CHECK (Amount >= 0),
    ChangeAmount  DECIMAL(12,2) NOT NULL CONSTRAINT DF_Payment_Change DEFAULT 0 CONSTRAINT CK_Payment_Change CHECK (ChangeAmount >= 0),
    RefNo         VARCHAR(100)  NULL,
    PaidAt        DATETIME2(0)  NOT NULL CONSTRAINT DF_Payment_PaidAt DEFAULT SYSDATETIME()
);
GO

/* ---- 8) StockMovement (Quantity: positive = stock in, negative = stock out) ---- */
CREATE TABLE StockMovement (
    MovementID    INT IDENTITY(1,1) CONSTRAINT PK_StockMovement PRIMARY KEY,
    ProductID     INT           NOT NULL CONSTRAINT FK_StockMovement_Product REFERENCES Product(ProductID),
    MovementType  VARCHAR(20)   NOT NULL CONSTRAINT CK_StockMovement_Type CHECK (MovementType IN ('receive', 'sale', 'cancel', 'adjust')),
    Quantity      INT           NOT NULL CONSTRAINT CK_StockMovement_Qty CHECK (Quantity <> 0),
    SaleID        INT           NULL CONSTRAINT FK_StockMovement_Sale REFERENCES Sale(SaleID),
    EmployeeID    INT           NOT NULL CONSTRAINT FK_StockMovement_Employee REFERENCES Employee(EmployeeID),
    Note          NVARCHAR(200) NULL,
    CreatedAt     DATETIME2(0)  NOT NULL CONSTRAINT DF_StockMovement_Created DEFAULT SYSDATETIME()
);
GO

/* ---- indexes for faster reports ---- */
CREATE INDEX IX_Sale_SaleDate         ON Sale(SaleDate);
CREATE INDEX IX_Sale_EmployeeID       ON Sale(EmployeeID);
CREATE INDEX IX_Sale_CustomerID       ON Sale(CustomerID);
CREATE INDEX IX_SaleItem_ProductID    ON SaleItem(ProductID);
CREATE INDEX IX_Payment_SaleID        ON Payment(SaleID);
CREATE INDEX IX_StockMovement_Product ON StockMovement(ProductID, CreatedAt);
CREATE INDEX IX_Product_CategoryID    ON Product(CategoryID);
GO

/* ---- starter data: categories ---- */
INSERT INTO Category (CategoryName) VALUES
    (N'เครื่องดื่ม'),
    (N'ขนมและของกินเล่น'),
    (N'อาหารพร้อมทาน'),
    (N'ของใช้ส่วนตัว'),
    (N'ของใช้ในบ้าน'),
    (N'บุหรี่และเครื่องดื่มแอลกอฮอล์'),
    (N'นมและผลิตภัณฑ์นม'),
    (N'บัตรเติมเงินและอื่นๆ');
GO

/* ---- check: should list 8 tables ---- */
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
GO
