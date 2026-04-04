# Shubham Tradelink - Battery Shop Management System

This is a **Battery Shop Management System** built for "Shubham Tradelink". It is a web application developed using **Python (Flask)** on the backend, **MongoDB** for the database, and **Tailwind CSS** for modern, responsive frontend styling with built-in dark mode support.

## Application Sections

Here is an overall summary of the different sections and what you can do in each:

### 1. Dashboard (`/`)
* **Purpose:** The central hub and landing page of the application.
* **What it does:** Provides a high-level overview of the shop's daily operations. It displays key performance indicators, recent activities, or quick summaries of sales, stock, and outstanding credits to give a quick snapshot of the business.

### 2. Sales (`/sales`)
* **Purpose:** Handling all billing and transactions.
* **Sections:** 
  * **New Sale (`/sales/add`):** Allows you to create a new battery sale, record the customer details, battery model, warranty given, and price.
  * **Sales History (`/sales/history`):** A ledger of all past transactions. You can view past invoices and verify what was sold on a particular date.

### 3. Customers (`/customers`)
* **Purpose:** Customer relationship management (CRM).
* **What it does:** Allows you to maintain a directory of your customers. You can view customer details, their contact information, and their purchase history. This is helpful for recurring customers and ensuring you have contact details for warranty claims.

### 4. Inventory / Stock (`/inventory`)
* **Purpose:** Managing the physical stock of batteries in the shop.
* **What it does:** Allows you to add, edit, or remove battery models from your catalogue. You can track quantities available to know when to restock, and it also manages specific details for each battery type, such as its brand and the default warranty period it carries.

### 5. Warranties (`/warranties`)
* **Purpose:** Managing and verifying post-sale battery warranties.
* **What it does:** Provides a dedicated interface to look up warranty statuses. For example, if a customer comes in with a faulty battery, this section allows you to quickly verify their initial purchase (e.g., via their phone number) and determine if the battery is still within its valid warranty period.

### 6. Mechanics (`/mechanics`)
* **Purpose:** Managing mechanic relationships and credit tracking (Khata).
* **What it does:** A specialized section for local mechanics who buy batteries on behalf of their customers or on credit. You can register mechanics, track their ongoing credit balances, record payments they make against their balance, and manage their specific transaction history.
