export const SAMPLE_ORDERS_CSV = `Order ID,Order Date,Customer Name,Product Name,Category,Sub-Category,Region,Sales,Quantity,Discount,Profit
ORD-2024-1001,2024-01-15,Acme Corp,Enterprise Laptop Pro,Technology,Computers,West,2499.99,2,0.05,450.00
ORD-2024-1002,2024-01-16,Global Dynamics,Ergonomic Desk Chair,Furniture,Chairs,East,350.00,1,0.00,85.00
ORD-2024-1003,2024-01-18,Stark Industries,UltraWide Monitor 34",Technology,Displays,Central,899.50,1,0.10,210.00
ORD-2024-1004,2024-01-20,Wayne Enterprises,Wireless Noise-Canceling Headset,Technology,Audio,South,299.99,3,0.00,90.00
ORD-2024-1005,2024-01-22,Cyberdyne Systems,Standing Desk Converter,Furniture,Furnishings,West,199.00,2,0.15,35.00
ORD-2024-1006,2024-01-25,Umbrella Corp,High-Yield Toner Cartridge,Office Supplies,Paper,East,120.50,5,0.00,40.00
ORD-2024-1007,2024-01-28,Initech,Premium Recycled Paper Box,Office Supplies,Paper,Central,45.00,10,0.00,12.00
ORD-2024-1008,2024-02-01,Acme Corp,Docking Station Dual 4K,Technology,Accessories,West,249.00,2,0.00,60.00
`;

export const SAMPLE_CUSTOMERS_CSV = `Customer Name,Segment,Region,Country,City
Acme Corp,Corporate,West,USA,San Francisco
Global Dynamics,Consumer,East,USA,New York
Stark Industries,Corporate,Central,USA,Chicago
Wayne Enterprises,Home Office,South,USA,Atlanta
Cyberdyne Systems,Corporate,West,USA,Los Angeles
Umbrella Corp,Corporate,East,USA,Boston
Initech,Consumer,Central,USA,Austin
`;

export const SAMPLE_PRODUCTS_CSV = `Product Name,Category,Sub-Category,Unit Price,Unit Cost
Enterprise Laptop Pro,Technology,Computers,1249.99,1024.99
Ergonomic Desk Chair,Furniture,Chairs,350.00,265.00
UltraWide Monitor 34",Technology,Displays,899.50,689.50
Wireless Noise-Canceling Headset,Technology,Audio,99.99,69.99
Standing Desk Converter,Furniture,Furnishings,99.50,82.00
High-Yield Toner Cartridge,Office Supplies,Paper,24.10,16.10
Premium Recycled Paper Box,Office Supplies,Paper,4.50,3.30
Docking Station Dual 4K,Technology,Accessories,124.50,94.50
`;

export const SAMPLE_RETURNS_CSV = `Order ID,Returned,Reason
ORD-2024-1005,Yes,Defective item
ORD-2024-1007,Yes,Wrong size ordered
`;

export function downloadSampleCsv(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
