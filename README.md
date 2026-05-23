# 🔋 Shubham Tradelink — Battery Shop ERP & Management System

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web_Framework-black?style=for-the-badge&logo=flask)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css)
![PWA](https://img.shields.io/badge/PWA-Ready-5A0FC8?style=for-the-badge&logo=pwa)

A comprehensive, production-ready full-stack Enterprise Resource Planning (ERP) application custom-built for **Shubham Tradelink**, a retail battery business. 

This system digitizes manual pen-and-paper ledgers, offering a complete solution for inventory tracking, CRM, sales generation, warranty validation, and mechanic credit management.

---

## ✨ Key Features

* **Progressive Web App (PWA):** Installs as a standalone app on mobile devices for quick access on the shop floor.
* **Secure Authentication:** Built-in session management, hashed passwords, and environment-driven credentials.
* **Modern UI/UX:** Responsive, mobile-first design built with Tailwind CSS, featuring a polished dark/glassmorphic aesthetic.
* **Robust Security:** Implements HTTP security headers (`X-Frame-Options`, `Content-Type-Options`), strict cookie policies, and cache control to prevent data leakage.
* **Cloud-Ready:** Pre-configured for deployment on platforms like Render (`render.yaml` included) using MongoDB Atlas for a scalable NoSQL backend.

---

## 🛠️ Technical Architecture

### Tech Stack
- **Backend:** Python 3.11+, Flask
- **Database:** MongoDB Atlas (NoSQL) with `pymongo` and `certifi` for secure TLS connections.
- **Frontend:** HTML5, Jinja2 Templating, Tailwind CSS (via CDN).
- **Architecture:** Modular MVC-style architecture using Flask Blueprints for clean separation of concerns.

### Project Structure
```text
├── app.py                 # Application factory & entry point
├── config.py              # Environment variable & secret management
├── models/                # Database connection singletons & schema logic
├── routes/                # Modular Flask Blueprints (Sales, Auth, Inventory, etc.)
├── static/                # Assets and PWA Service Worker
├── templates/             # Jinja2 HTML views
└── render.yaml            # IaC (Infrastructure as Code) for automated deployment
```

---

## 💼 Business Modules

### 1. 📊 Dashboard
A centralized hub providing high-level metrics, daily sales snapshots, low-stock alerts, and outstanding mechanic credit balances at a glance.

### 2. 🛒 Sales & Billing
An intuitive Point-of-Sale (POS) interface. Record battery models sold, capture customer details instantly, calculate pricing, and issue digital invoices. Maintains a chronological ledger of all transactions.

### 3. 👥 Customer Relationship Management (CRM)
Maintain a searchable directory of customers. Track purchase history and contact information to streamline future support and marketing.

### 4. 📦 Inventory Management
Real-time stock tracking. Add, edit, or remove battery models, track brands, monitor stock levels, and set default warranty periods for automated calculation during sales.

### 5. 🛡️ Warranty Claims
A dedicated portal to instantly verify post-sale warranty validity. Search by customer phone number or invoice ID to seamlessly process replacements or repairs without digging through physical receipts.

### 6. 🔧 Mechanic Ledger (Khata)
A specialized accounting module tailored for local auto-mechanics who purchase on credit. Track running balances, log partial payments, and view detailed transaction histories for individual mechanics.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.11+
* A MongoDB Atlas cluster (or local MongoDB instance)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/jaimindave13/Shubham-Tradelink.git
   cd Shubham-Tradelink
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   Create a `.env` file in the root directory and configure your secrets:
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/
   DB_NAME=battery_shop
   SECRET_KEY=your_super_secret_flask_key
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your_secure_password
   ```

5. **Run the Application**
   ```bash
   python app.py
   ```
   The app will be available at `http://127.0.0.1:5000`.

---

## 🔒 Security Posture
* **Zero Hardcoded Secrets:** All credentials are injected via environment variables.
* **Sanitized Git History:** Repository is clean of `.env` files and sensitive git-tracked data.
* **Secure Sessions:** Sessions are encrypted, `HttpOnly`, and `SameSite=Lax`.

---
*Designed & Developed by [Jaimin Dave](https://github.com/jaimindave13)*
