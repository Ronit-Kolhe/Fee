import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime, date
import webbrowser
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import black, blue, HexColor
import subprocess
import sys
import json
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from tkcalendar import Calendar, DateEntry

class FeeReceiptApp:
    CLASS_OPTIONS = ["MINI KG", "JR KG", "SR KG"]
    TOTAL_FEE = 19000
    
    def __init__(self, root):
        self.root = root
        self.root.title("Fee Receipt Generator - Offline")
        self.root.geometry("1000x700")
        self.root.configure(bg='#f0f0f0')
        
        # Initialize database
        self.init_database()
        
        # Create main interface
        self.create_widgets()
        
        # Register a font that supports the rupee symbol
        try:
            pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
            self.rupee_font = 'Arial'
        except Exception:
            # Fallback to default font if Arial is not found
            self.rupee_font = 'Helvetica'
            messagebox.showwarning("Font Warning", "Arial.ttf not found. Rupee symbol may not display correctly. Install 'Arial' font or place 'Arial.ttf' in the 'templates' folder.")
    
    def init_database(self):
        """Initialize SQLite database and create tables if they don't exist"""
        # Create directories
        os.makedirs("db", exist_ok=True)
        os.makedirs("receipts", exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        
        self.conn = sqlite3.connect("db/students.db")
        self.cursor = self.conn.cursor()
        
        # Create students table (add parent_name, parent_number, parent_email if not exist)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class TEXT NOT NULL,
                contact TEXT,
                mother_name TEXT,
                father_name TEXT,
                parent_number TEXT,
                parent_email TEXT,
                created_date DATE DEFAULT CURRENT_DATE
            )
        ''')
        # Try to add columns if they don't exist (for upgrades)
        try:
            self.cursor.execute('ALTER TABLE students ADD COLUMN mother_name TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute('ALTER TABLE students ADD COLUMN father_name TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute('ALTER TABLE students ADD COLUMN parent_number TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute('ALTER TABLE students ADD COLUMN parent_email TEXT')
        except sqlite3.OperationalError:
            pass
        # Remove the old parent_name column if it exists (optional, but good for cleanup)
        # Note: SQLite doesn't directly support dropping columns easily. A common workaround is
        # to create a new table, copy data, drop the old table, and rename the new one.
        # For simplicity here, we'll just add the new columns and ignore the old one in code.
        # If a clean migration is needed, more complex SQL would be required.
        # Keeping the old column won't break the app but is less clean.
        # Let's check if parent_name exists and, if so, create a new table structure without it
        self.cursor.execute("PRAGMA table_info(students)")
        columns = [info[1] for info in self.cursor.fetchall()]
        if 'parent_name' in columns:
            self.cursor.execute('''
                CREATE TABLE students_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    class TEXT NOT NULL,
                    contact TEXT,
                    mother_name TEXT,
                    father_name TEXT,
                    parent_number TEXT,
                    parent_email TEXT,
                    created_date DATE DEFAULT CURRENT_DATE
                )
            ''')
            self.cursor.execute('''
                INSERT INTO students_new (id, name, class, contact, parent_number, parent_email, created_date)
                SELECT id, name, class, contact, parent_number, parent_email, created_date FROM students
            ''')
            self.cursor.execute('DROP TABLE students')
            self.cursor.execute('ALTER TABLE students_new RENAME TO students')
        
        # Create payments table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                due_date DATE,
                paid_date DATE,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'Pending',
                receipt_path TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id)
            )
        ''')
        
        # Try to add payment_mode column if it doesn't exist
        try:
            self.cursor.execute('ALTER TABLE payments ADD COLUMN payment_mode TEXT')
        except sqlite3.OperationalError:
            pass
        
        self.conn.commit()
    
    def create_widgets(self):
        """Create the main GUI interface"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Student Management
        student_frame = ttk.Frame(notebook)
        notebook.add(student_frame, text="Student Management")
        self.create_student_tab(student_frame)
        
        # Tab 2: Fee Payment
        payment_frame = ttk.Frame(notebook)
        notebook.add(payment_frame, text="Fee Payment")
        self.create_payment_tab(payment_frame)
        
        # Tab 3: Payment History
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="Payment History")
        self.create_history_tab(history_frame)
        
        # Tab 4: Settings
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="Settings")
        self.create_settings_tab(settings_frame)
    
    def create_student_tab(self, parent):
        """Create student management interface"""
        # Create two main frames: one for the form, one for the list
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Form Frame (left side)
        form_frame = ttk.LabelFrame(main_frame, text="Student Details", padding="10")
        form_frame.pack(side='left', fill='y', padx=5, pady=5)

        # List Frame (right side)
        list_frame = ttk.LabelFrame(main_frame, text="All Students", padding="10")
        list_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)

        # --- Search Frame ---
        search_frame = ttk.Frame(list_frame, padding="5")
        search_frame.pack(fill='x')

        ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        self.student_search_entry = ttk.Entry(search_frame, width=40)
        self.student_search_entry.pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(search_frame, text="Search", command=self.search_students).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Clear Search", command=self.clear_student_search).pack(side='left', padx=5)

        # --- Form Widgets ---
        row_counter = 0
        ttk.Label(form_frame, text="Student Name:").grid(row=row_counter, column=0, sticky='w', padx=5, pady=5)
        self.student_name = ttk.Entry(form_frame, width=30)
        self.student_name.grid(row=row_counter, column=1, padx=5, pady=5)
        row_counter += 1

        ttk.Label(form_frame, text="Class:").grid(row=row_counter, column=0, sticky='w', padx=5, pady=5)
        self.student_class = ttk.Combobox(form_frame, width=27, state='readonly', values=self.CLASS_OPTIONS)
        self.student_class.grid(row=row_counter, column=1, padx=5, pady=5)
        row_counter += 1

        ttk.Label(form_frame, text="Contact Number:").grid(row=row_counter, column=0, sticky='w', padx=5, pady=5)
        self.student_contact = ttk.Entry(form_frame, width=30)
        self.student_contact.grid(row=row_counter, column=1, padx=5, pady=5)
        row_counter += 1

        ttk.Label(form_frame, text="Mother Name:").grid(row=row_counter, column=0, sticky='w', padx=5, pady=5)
        self.mother_name = ttk.Entry(form_frame, width=30)
        self.mother_name.grid(row=row_counter, column=1, padx=5, pady=5)
        row_counter += 1

        ttk.Label(form_frame, text="Father Name:").grid(row=row_counter, column=0, sticky='w', padx=5, pady=5)
        self.father_name = ttk.Entry(form_frame, width=30)
        self.father_name.grid(row=row_counter, column=1, padx=5, pady=5)
        row_counter += 1

        ttk.Label(form_frame, text="Parent Number:").grid(row=row_counter, column=0, sticky='w', padx=5, pady=5)
        self.parent_number = ttk.Entry(form_frame, width=30)
        self.parent_number.grid(row=row_counter, column=1, padx=5, pady=5)
        row_counter += 1

        ttk.Label(form_frame, text="Parent Email:").grid(row=row_counter, column=0, sticky='w', padx=5, pady=5)
        self.parent_email = ttk.Entry(form_frame, width=30)
        self.parent_email.grid(row=row_counter, column=1, padx=5, pady=5)
        row_counter += 1

        # --- Form Buttons ---
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row_counter, column=0, columnspan=2, pady=10)

        self.add_update_button = ttk.Button(button_frame, text="Add Student", command=self.save_student_changes)
        self.add_update_button.pack(side='left', padx=5)

        self.clear_button = ttk.Button(button_frame, text="Clear Form", command=self.clear_student_form)
        self.clear_button.pack(side='left', padx=5)
        
        # Import CSV Button (moved to form section)
        ttk.Button(button_frame, text="Import from CSV", command=self.import_students_csv).pack(side='left', padx=5)
        
        self.selected_student_id = None # To keep track of student being edited

        # --- List Widgets ---
        columns = ('ID', 'Name', 'Class', 'Contact', 'Mother Name', 'Father Name', 'Parent Number', 'Parent Email', 'Created Date')
        self.student_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.student_tree.heading(col, text=col)
            self.student_tree.column(col, width=100)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.student_tree.yview)
        self.student_tree.configure(yscrollcommand=scrollbar.set)

        self.student_tree.pack(side='top', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Configure tags for alternating row colors
        self.student_tree.tag_configure('evenrow', background='lightblue') # Light blue
        self.student_tree.tag_configure('oddrow', background='white')  # White
        
        # --- List Buttons ---
        list_button_frame = ttk.Frame(list_frame)
        list_button_frame.pack(side='bottom', fill='x', pady=5)

        # Edit Button
        ttk.Button(list_button_frame, text="Edit Selected Student", command=self.select_student_for_edit).pack(side='left', padx=5)
        
        # Delete Button
        ttk.Button(list_button_frame, text="Delete Selected Student", command=self.delete_selected_student).pack(side='left', padx=5)

        # Bind treeview selection to load student data
        self.student_tree.bind('<<TreeviewSelect>>', self.select_student_for_edit)

        # Load students initially
        self.load_students()
    
    def create_payment_tab(self, parent):
        """Create payment processing interface"""
        # Payment Form
        form_frame = ttk.LabelFrame(parent, text="Record Fee Payment", padding="10")
        form_frame.pack(fill='x', padx=10, pady=5)
        
        # Class filter for students
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=10, pady=2)
        ttk.Label(filter_frame, text="Filter by Class:").pack(side='left', padx=5)
        self.payment_class_filter = ttk.Combobox(filter_frame, width=15, state='readonly', values=['All'] + self.CLASS_OPTIONS)
        self.payment_class_filter.set('All')
        self.payment_class_filter.pack(side='left', padx=5)
        self.payment_class_filter.bind('<<ComboboxSelected>>', self.update_payment_student_list)
        # Search box with auto-complete
        ttk.Label(filter_frame, text="Search Student:").pack(side='left', padx=5)
        self.student_search_var = tk.StringVar()
        self.student_search = ttk.Entry(filter_frame, textvariable=self.student_search_var, width=25)
        self.student_search.pack(side='left', padx=5)
        self.student_search.bind('<KeyRelease>', self.autocomplete_student_search)
        self.student_search.bind('<Return>', self.select_autocomplete_student)
        self.student_search_suggestions = tk.Listbox(filter_frame, width=25, height=3)
        self.student_search_suggestions.pack_forget()
        self.student_search_suggestions.bind('<<ListboxSelect>>', self.select_autocomplete_student)
        
        # Student Selection
        ttk.Label(form_frame, text="Select Student:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.student_combo = ttk.Combobox(form_frame, width=30, state='readonly')
        self.student_combo.grid(row=0, column=1, padx=5, pady=5)
        self.student_combo.bind("<<ComboboxSelected>>", self.update_fee_info)
        # Class (read-only)
        ttk.Label(form_frame, text="Class:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
        self.selected_class = ttk.Entry(form_frame, width=15, state='readonly')
        self.selected_class.grid(row=0, column=3, padx=5, pady=5)
        # Contact (read-only)
        ttk.Label(form_frame, text="Contact:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.selected_contact = ttk.Entry(form_frame, width=20, state='readonly')
        self.selected_contact.grid(row=1, column=1, padx=5, pady=5)
        # Paid Date
        ttk.Label(form_frame, text="Paid Date:").grid(row=1, column=2, sticky='w', padx=5, pady=5)
        
        self.paid_date_entry = DateEntry(form_frame, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.paid_date_entry.grid(row=1, column=3, padx=5, pady=5, sticky='we')
        
        # Due Date
        ttk.Label(form_frame, text="Due Date:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        
        self.due_date_entry = DateEntry(form_frame, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.due_date_entry.grid(row=4, column=1, padx=5, pady=5, sticky='we')
        
        # Mini-summary
        self.fee_summary_var = tk.StringVar(value="")
        ttk.Label(form_frame, textvariable=self.fee_summary_var, font=("Helvetica", 10, "bold")).grid(row=2, column=0, columnspan=4, sticky='w', padx=5, pady=5)
        # Amount Paid
        ttk.Label(form_frame, text="Amount Paid (₹):").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.amount = ttk.Entry(form_frame, width=15)
        self.amount.grid(row=3, column=1, padx=5, pady=5)
        # Pay Full Due button
        ttk.Button(form_frame, text="Pay Full Due", command=self.pay_full_due).grid(row=3, column=2, padx=5, pady=5)
        # Show All Dues button
        ttk.Button(form_frame, text="Show All Pending", command=self.show_all_pending).grid(row=3, column=3, padx=5, pady=5)
        
        # Total Fee (read-only, always 18000)
        ttk.Label(form_frame, text="Total Fee (₹):").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.total_fee = ttk.Entry(form_frame, width=15, state='readonly')
        self.total_fee.grid(row=4, column=1, padx=5, pady=5)
        self.total_fee.config(state='normal'); self.total_fee.delete(0, tk.END); self.total_fee.insert(0, str(self.TOTAL_FEE)); self.total_fee.config(state='readonly')
        
        # Fee Info Labels
        self.fee_paid_so_far_var = tk.StringVar(value="Fee Paid So Far: ₹0.00")
        self.fee_remaining_var = tk.StringVar(value="Fee Remaining: ₹0.00")
        ttk.Label(form_frame, textvariable=self.fee_paid_so_far_var).grid(row=4, column=2, padx=5, pady=5, sticky='w')
        ttk.Label(form_frame, textvariable=self.fee_remaining_var).grid(row=4, column=3, padx=5, pady=5, sticky='w')
        
        # Payment Mode
        ttk.Label(form_frame, text="Payment Mode:").grid(row=5, column=0, sticky='w', padx=5, pady=5)
        self.payment_mode = ttk.Combobox(form_frame, width=27, state='readonly', values=["Cash", "Online", "Cheque", "Other"])
        self.payment_mode.grid(row=5, column=1, padx=5, pady=5)
        self.payment_mode.set("Cash") # Default value
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=6, column=0, columnspan=4, pady=10)
        
        ttk.Button(button_frame, text="Record Payment", command=self.record_payment).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Generate Receipt", command=self.generate_receipt).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh Students", command=self.load_student_combo).pack(side='left', padx=5)
        
        # Recent Payments
        recent_frame = ttk.LabelFrame(parent, text="Recent Payments", padding="10")
        recent_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for recent payments
        payment_columns = ('ID', 'Student', 'Class', 'Due Date', 'Paid Date', 'Amount', 'Status', 'Payment Mode')
        self.payment_tree = ttk.Treeview(recent_frame, columns=payment_columns, show='headings', height=12)
        
        for col in payment_columns:
            self.payment_tree.heading(col, text=col)
            self.payment_tree.column(col, width=100)
        
        # Scrollbar for payments
        payment_scrollbar = ttk.Scrollbar(recent_frame, orient='vertical', command=self.payment_tree.yview)
        self.payment_tree.configure(yscrollcommand=payment_scrollbar.set)
        
        self.payment_tree.pack(side='left', fill='both', expand=True)
        payment_scrollbar.pack(side='right', fill='y')
        
        # Configure tags for alternating row colors
        self.payment_tree.tag_configure('evenrow', background='lightblue') # Light blue
        self.payment_tree.tag_configure('oddrow', background='white')  # White
        
        # Delete Payment Button
        delete_btn = ttk.Button(recent_frame, text="Delete Payment", command=self.delete_selected_payment)
        delete_btn.pack(side='bottom', pady=5, anchor='e')
        
        # Filter buttons for status
        filter_frame2 = ttk.Frame(parent)
        filter_frame2.pack(fill='x', padx=10, pady=2)
        ttk.Button(filter_frame2, text='All', command=lambda: self.filter_payments_tree('All')).pack(side='left', padx=2)
        ttk.Button(filter_frame2, text='Cleared', command=lambda: self.filter_payments_tree('Cleared')).pack(side='left', padx=2)
        ttk.Button(filter_frame2, text='Pending', command=lambda: self.filter_payments_tree('Pending')).pack(side='left', padx=2)
        
        # Load data
        self.load_student_combo()
        self.load_recent_payments()
    
    def create_history_tab(self, parent):
        """Create payment history interface"""
        # Filter Frame
        filter_frame = ttk.LabelFrame(parent, text="Filter Options", padding="10")
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        # Class Filter (Row 0)
        ttk.Label(filter_frame, text="Filter by Class:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.filter_class = ttk.Combobox(filter_frame, width=15, values=['All'] + self.CLASS_OPTIONS, state='readonly')
        self.filter_class.grid(row=0, column=1, padx=5, pady=5, sticky='we')
        self.filter_class.set('All')
        
        # Status Filter (Row 0)
        ttk.Label(filter_frame, text="Filter by Status:").grid(row=0, column=2, padx=5, pady=5, sticky='w')
        self.filter_status = ttk.Combobox(filter_frame, values=['All', 'Pending', 'Cleared'], width=15)
        self.filter_status.grid(row=0, column=3, padx=5, pady=5, sticky='we')
        self.filter_status.set('All')

        # Date Range Filter (Row 1)
        row_counter = 1
        ttk.Label(filter_frame, text="From Paid Date:").grid(row=row_counter, column=0, padx=5, pady=5, sticky='w')
        
        self.filter_start_date_entry = DateEntry(filter_frame, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_start_date_entry.grid(row=row_counter, column=1, padx=5, pady=5, sticky='we')

        ttk.Label(filter_frame, text="To Paid Date:").grid(row=row_counter, column=2, padx=5, pady=5, sticky='w')

        self.filter_end_date_entry = DateEntry(filter_frame, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_end_date_entry.grid(row=row_counter, column=3, padx=5, pady=5, sticky='we')

        # Buttons (Row 0 and Row 1)
        button_frame = ttk.Frame(filter_frame)
        button_frame.grid(row=0, column=4, rowspan=2, padx=5, pady=5, sticky='ns')

        ttk.Button(button_frame, text="Apply Filter", command=self.apply_filter).pack(pady=2)
        ttk.Button(button_frame, text="Export to CSV", command=self.export_to_csv).pack(pady=2)
        
        # --- Search Frame (Row 2) ---
        row_counter += 1
        search_frame = ttk.Frame(filter_frame)
        search_frame.grid(row=row_counter, column=0, columnspan=4, padx=5, pady=5, sticky='we')
        
        ttk.Label(search_frame, text="Search Student:").pack(side='left', padx=5)
        self.history_search_entry = ttk.Entry(search_frame, width=40)
        self.history_search_entry.pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(search_frame, text="Search", command=self.apply_filter).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Clear Search", command=self.clear_history_search).pack(side='left', padx=5)

        # Summary bar
        self.summary_var = tk.StringVar(value='')
        summary_label = ttk.Label(parent, textvariable=self.summary_var, font=('Helvetica', 12, 'bold'))
        summary_label.pack(fill='x', padx=10, pady=2)
        
        # Collection in Range Summary
        self.range_collection_var = tk.StringVar(value='')
        range_collection_label = ttk.Label(parent, textvariable=self.range_collection_var, font=('Helvetica', 10, 'italic'))
        range_collection_label.pack(fill='x', padx=10, pady=1)

        # Filter buttons for status
        filter_frame2 = ttk.Frame(parent)
        filter_frame2.pack(fill='x', padx=10, pady=2)
        ttk.Button(filter_frame2, text='All', command=lambda: self.filter_history_tree('All')).pack(side='left', padx=2)
        ttk.Button(filter_frame2, text='Cleared', command=lambda: self.filter_history_tree('Cleared')).pack(side='left', padx=2)
        ttk.Button(filter_frame2, text='Pending', command=lambda: self.filter_history_tree('Pending')).pack(side='left', padx=2)
        
        # History Tree
        history_frame = ttk.LabelFrame(parent, text="Payment History", padding="10")
        history_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        history_columns = ('ID', 'Student', 'Class', 'Contact', 'Due Date', 'Paid Date', 'Amount', 'Status', 'Receipt', 'Payment Mode')
        self.history_tree = ttk.Treeview(history_frame, columns=history_columns, show='headings', height=15)
        
        for col in history_columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=100)
        
        # Scrollbar for history
        history_scrollbar = ttk.Scrollbar(history_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        self.history_tree.pack(side='left', fill='both', expand=True)
        history_scrollbar.pack(side='right', fill='y')
        
        # Context menu for history
        self.history_tree.bind("<Double-1>", self.open_receipt)
        
        # Generate Receipt Button
        gen_receipt_btn = ttk.Button(history_frame, text="Generate Receipt", command=self.generate_receipt_from_history)
        gen_receipt_btn.pack(side='bottom', pady=5, anchor='e')
        
        self.load_payment_history()
        self.load_class_filter()
    
    def create_settings_tab(self, parent):
        """Create settings interface"""
        settings_frame = ttk.LabelFrame(parent, text="Application Settings", padding="20")
        settings_frame.pack(fill='x', padx=10, pady=5)
        # School Info (fixed, not editable)
        ttk.Label(settings_frame, text="School Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.school_name = ttk.Entry(settings_frame, width=40, state='readonly')
        self.school_name.grid(row=0, column=1, padx=5, pady=5)
        self.school_name.config(state='normal'); self.school_name.delete(0, tk.END); self.school_name.insert(0, "Little Angels Pre-School"); self.school_name.config(state='readonly')
        ttk.Label(settings_frame, text="School Address:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.school_address = ttk.Entry(settings_frame, width=40, state='readonly')
        self.school_address.grid(row=1, column=1, padx=5, pady=5)
        self.school_address.config(state='normal'); self.school_address.delete(0, tk.END); self.school_address.insert(0, "Shivane, Pune-23"); self.school_address.config(state='readonly')
        ttk.Label(settings_frame, text="Contact Number:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.school_contact = ttk.Entry(settings_frame, width=40, state='readonly')
        self.school_contact.grid(row=2, column=1, padx=5, pady=5)
        self.school_contact.config(state='normal'); self.school_contact.delete(0, tk.END); self.school_contact.insert(0, "8657633646 & 9765848509"); self.school_contact.config(state='readonly')
        # Buttons
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Open Receipts Folder", command=self.open_receipts_folder).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Backup Database", command=self.backup_database).pack(side='left', padx=5)
        ttk.Button(button_frame, text="WhatsApp Web", command=self.open_whatsapp_web).pack(side='left', padx=5)
    
    def add_student(self):
        """Add a new student to the database"""
        name = self.student_name.get().strip()
        class_name = self.student_class.get().strip()
        contact = self.student_contact.get().strip()
        mother_name = self.mother_name.get().strip()
        father_name = self.father_name.get().strip()
        parent_number = self.parent_number.get().strip()
        parent_email = self.parent_email.get().strip()
        
        if not name or not class_name:
            messagebox.showerror("Error", "Name and Class are required fields!")
            return
        
        try:
            self.cursor.execute(
                "INSERT INTO students (name, class, contact, mother_name, father_name, parent_number, parent_email) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, class_name, contact, mother_name, father_name, parent_number, parent_email)
            )
            self.conn.commit()
            
            # Clear form
            self.student_name.delete(0, tk.END)
            self.student_class.delete(0, tk.END)
            self.student_contact.delete(0, tk.END)
            self.mother_name.delete(0, tk.END)
            self.father_name.delete(0, tk.END)
            self.parent_number.delete(0, tk.END)
            self.parent_email.delete(0, tk.END)
            
            # Refresh displays
            self.load_students()
            self.load_student_combo()
            
            messagebox.showinfo("Success", f"Student '{name}' added successfully!")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error adding student: {e}")
    
    def load_students(self, query=""):
        """Load all students into the treeview, optionally filtered by a query"""
        # Clear existing items
        for item in self.student_tree.get_children():
            self.student_tree.delete(item)
        # Fetch and display students, sorted by class then name
        sql_query = "SELECT id, name, class, contact, mother_name, father_name, parent_number, parent_email, created_date FROM students"
        params = []

        if query:
            sql_query += " WHERE name LIKE ? OR class LIKE ? OR contact LIKE ? OR mother_name LIKE ? OR father_name LIKE ? OR parent_number LIKE ? OR parent_email LIKE ?"
            search_term = f"%{query}%"
            params = [search_term] * 7 # Apply search term to all searchable columns

        sql_query += " ORDER BY class, name"

        self.cursor.execute(sql_query, params)
        students = self.cursor.fetchall()
        for i, student in enumerate(students):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.student_tree.insert('', 'end', values=student, tags=(tag,))

    def search_students(self):
        """Perform search based on the text in the search entry"""
        query = self.student_search_entry.get()
        self.load_students(query)

    def clear_student_search(self):
        """Clear the search entry and reload all students"""
        self.student_search_entry.delete(0, tk.END)
        self.load_students()
    
    def load_student_combo(self):
        # Load students into the combobox for payment form, respecting class filter
        selected_class = getattr(self, 'payment_class_filter', None)
        if selected_class and selected_class.get() != 'All':
            self.cursor.execute("SELECT id, name, class FROM students WHERE class = ? ORDER BY name", (selected_class.get(),))
        else:
            self.cursor.execute("SELECT id, name, class FROM students ORDER BY class, name")
        students = self.cursor.fetchall()
        student_list = [f"{s[1]} ({s[2]}) - ID:{s[0]}" for s in students]
        self.student_combo['values'] = student_list
        self.autocomplete_student_names = [s[1] for s in students]
    
    def record_payment(self):
        """Record a new payment"""
        if not self.student_combo.get():
            messagebox.showerror("Error", "Please select a student!")
            return
        try:
            # Extract student ID from combo selection
            student_info = self.student_combo.get()
            student_id = int(student_info.split("ID:")[1])
            due_date = self.due_date_entry.get()
            paid_date = self.paid_date_entry.get()
            amount = float(self.amount.get())  # Fee Paid Currently
            payment_mode = self.payment_mode.get() # Get payment mode
            # Validate dates
            datetime.strptime(due_date, "%Y-%m-%d")
            datetime.strptime(paid_date, "%Y-%m-%d")
            # Insert payment as 'Pending' by default
            status = "Pending"
            self.cursor.execute(
                """INSERT INTO payments (student_id, due_date, paid_date, amount, status, payment_mode) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, due_date, paid_date, amount, status, payment_mode)
            )
            self.conn.commit()
            # After insert, update all this student's payments to 'Cleared' if total paid >= 18000, else 'Pending'
            self.cursor.execute("SELECT SUM(amount) FROM payments WHERE student_id = ?", (student_id,))
            total_paid = self.cursor.fetchone()[0] or 0.0
            new_status = "Cleared" if total_paid >= self.TOTAL_FEE else "Pending"
            self.cursor.execute("UPDATE payments SET status = ? WHERE student_id = ?", (new_status, student_id))
            self.conn.commit()
            # Clear form
            self.amount.delete(0, tk.END)
            # Refresh displays
            self.load_recent_payments()
            self.load_payment_history()
            self.update_fee_info()  # Update fee info after payment
            messagebox.showinfo("Success", "Payment recorded successfully!")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error recording payment: {e}")
    
    def generate_receipt(self):
        """Generate PDF receipt for the last payment"""
        if not self.student_combo.get():
            messagebox.showerror("Error", "Please select a student first!")
            return
        
        try:
            # Get the last payment for this student
            student_info = self.student_combo.get()
            student_id = int(student_info.split("ID:")[1])
            
            self.cursor.execute("""
                SELECT p.*, s.name, s.class, s.contact, s.mother_name, s.father_name, s.parent_number, s.parent_email
                FROM payments p 
                JOIN students s ON p.student_id = s.id 
                WHERE p.student_id = ? 
                ORDER BY p.created_date DESC 
                LIMIT 1
            """, (student_id,))
            
            payment_data = self.cursor.fetchone()
            if not payment_data:
                messagebox.showerror("Error", "No payment found for this student!")
                return
            
            # Generate receipt
            receipt_path = self.create_pdf_receipt(payment_data)
            
            # Update database with receipt path
            self.cursor.execute(
                "UPDATE payments SET receipt_path = ? WHERE id = ?",
                (receipt_path, payment_data[0])
            )
            self.conn.commit()
            
            # Ask if user wants to open the receipt
            if messagebox.askyesno("Receipt Generated", 
                                 f"Receipt saved as:\n{receipt_path}\n\nWould you like to open the Receipts folder to send it via WhatsApp?"): # Modified message
                self.open_receipts_folder() # Open folder instead of file directly
                # Add prompt to open WhatsApp Web
                if messagebox.askyesno("Send via WhatsApp", "Would you like to open WhatsApp Web now to send the receipt?"):
                    self.open_whatsapp_web()
            
            # Refresh displays
            self.load_recent_payments()
            self.load_payment_history()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error generating receipt: {e}")
    
    def create_pdf_receipt(self, payment_data):
        """Create a PDF receipt matching the provided template, now with parent info"""
        # Unpack payment data
        # payment_id, student_id, due_date, paid_date, amount, status, receipt_path, created_date, payment_mode, name, class_name, contact, mother_name, father_name, parent_number, parent_email
        payment_id, student_id, due_date, paid_date, amount, status, receipt_path, created_date, payment_mode, name, class_name, contact, mother_name, father_name, parent_number, parent_email = payment_data
        # Try to get total fee and paid so far for this student
        try:
            self.cursor.execute("SELECT SUM(amount) FROM payments WHERE student_id = ?", (student_id,))
            paid_so_far = self.cursor.fetchone()[0] or 0.0
            total_fee = float(self.total_fee.get()) if hasattr(self, 'total_fee') and self.total_fee.get() else paid_so_far
            remaining = max(total_fee - paid_so_far, 0.0)
        except Exception:
            total_fee = paid_so_far = amount
            remaining = 0.0
        # Create filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        base_filename = f"{safe_name}_{class_name}_{paid_date}"
        filename = f"{base_filename}.pdf"
        receipt_path = os.path.join("receipts", filename)

        # Check if file exists and generate a unique name if necessary
        counter = 1
        while os.path.exists(receipt_path):
            filename = f"{base_filename}_{counter}.pdf"
            receipt_path = os.path.join("receipts", filename)
            counter += 1

        # Create PDF
        full_width, full_height = A4
        half_a4_height = full_height / 2
        c = canvas.Canvas(receipt_path, pagesize=(full_width, half_a4_height))
        width, height = full_width, half_a4_height # Use the new, smaller height for calculations
        # Colors and fonts
        blue = HexColor('#1a355e')
        light_blue = HexColor('#5fa8d3')
        # Logo
        logo_path = os.path.join("templates", "logo.png")
        if os.path.exists(logo_path):
            # Adjust logo vertical position
            c.drawImage(logo_path, 40, height - 80, width=80, height=80, mask='auto') # Adjusted from height - 110
        # School name and slogan
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(blue)
        # Adjust school name vertical position
        c.drawString(140, height - 30, self.school_name.get()) # Adjusted from height - 60
        c.setFont("Helvetica", 12)
        c.setFillColor(light_blue)
        # Adjust slogan vertical position
        c.drawString(140, height - 50, "CHOOSE SMART, BE SMART") # Adjusted from height - 80

        # Add School Address and Contact
        c.setFont("Helvetica", 10)
        c.setFillColor(black)
        # Adjust address and contact vertical positions
        c.drawString(140, height - 70, f"Address: {self.school_address.get()}") # Adjusted from height - 100
        c.drawString(140, height - 85, f"Contact: {self.school_contact.get()}") # Adjusted from height - 115

        # Fee Receipt title
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(blue)
        # Adjust title vertical position
        c.drawRightString(width - 40, height - 30, "FEE RECEIPT") # Adjusted from height - 60
        # Draw line under header
        c.setStrokeColor(blue)
        c.setLineWidth(2)
        # Adjust line vertical position
        c.line(40, height - 100, width - 40, height - 100) # Adjusted from height - 130
        # Student info
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        # Adjust starting y for student info
        y = height - 120 # Adjusted from height - 160
        c.drawString(50, y, "Student Name:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, name)
        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(50, y, "Class:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, class_name)
        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(50, y, "Contact Number:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, contact)
        y -= 20
        # Parent Info
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(50, y, "Mother Name:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, mother_name or "-")
        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(50, y, "Father Name:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, father_name or "-")
        # Removed Parent Number
        # c.setFont("Helvetica-Bold", 12)
        # c.setFillColor(blue)
        # c.drawString(50, y, "Parent Number:")
        # c.setFont("Helvetica", 12)
        # c.setFillColor(black)
        # c.drawString(170, y, parent_number or "-")
        # y -= 20 # Adjust y if line is removed
        # This y -= 20 was mistakenly kept. Removing it.
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        # The Parent Email should be 20 units below Father Name
        y -= 20 # This was the redundant y decrement. It should be removed.
        c.drawString(50, y, "Parent Email:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, parent_email or "-")
        # This y -= 20 was here before. No need to remove it as it's the correct spacing after Parent Email
        y -= 20
        # Receipt No and Date
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(50, y, "Receipt No:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, f"{payment_id:04d}")
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(350, y, "Date:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(400, y, datetime.now().strftime('%d/%m/%Y'))
        # Draw line
        y -= 10
        c.setStrokeColor(blue)
        c.setLineWidth(1)
        c.line(40, y, width - 40, y)
        y -= 20 # Changed from y -= 25 to y -= 20 for consistent spacing
        # Payment Mode
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(50, y, "Payment Mode:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, payment_mode)
        y -= 20
        # Due Date, Total Fee, Fee Paid, Remaining, Status
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(50, y, "Due Date:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(170, y, due_date)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(350, y, "Total Fee:")
        # Use the registered font for currency
        c.setFont(self.rupee_font, 12) # Use rupee font
        c.setFillColor(black)
        c.drawString(500, y, f"₹{total_fee:.2f}")
        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(350, y, "Fee Paid")
        # Use the registered font for currency
        c.setFont(self.rupee_font, 12) # Use rupee font
        c.setFillColor(black)
        c.drawString(500, y, f"₹{amount:.2f}")
        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(350, y, "Remaining Balance:")
        # Use the registered font for currency
        c.setFont(self.rupee_font, 12) # Use rupee font
        c.setFillColor(black)
        c.drawString(500, y, f"₹{remaining:.2f}")
        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(blue)
        c.drawString(350, y, "Status:")
        c.setFont("Helvetica", 12)
        c.setFillColor(black)
        c.drawString(500, y, status)
        # Draw line
        y -= 10
        c.setStrokeColor(blue)
        c.setLineWidth(1)
        c.line(40, y, width - 40, y)
        c.save()
        return receipt_path
    
    def load_recent_payments(self):
        """Load recent payments into the treeview"""
        # Clear existing items
        for item in self.payment_tree.get_children():
            self.payment_tree.delete(item)
        
        # Fetch recent payments
        self.cursor.execute("""
            SELECT p.id, s.name, s.class, p.due_date, p.paid_date, p.amount, p.status, p.payment_mode
            FROM payments p
            JOIN students s ON p.student_id = s.id
            ORDER BY p.created_date DESC
            LIMIT 20
        """)
        
        payments = self.cursor.fetchall()
        for i, payment in enumerate(payments):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            # Note: filter_payments_tree function also adds status tags, ensure compatibility
            status_tag = 'cleared' if payment[6] == 'Cleared' else 'pending' # Assuming status is at index 6
            # We are adding payment_mode to the end of the payment tuple, so it is at index 7.
            # The treeview columns now expect 8 values, so we should pass all of them.
            self.payment_tree.insert('', 'end', values=payment, tags=(tag, status_tag))
        self.payment_tree.tag_configure('cleared', background='#d4f7d4')
        self.payment_tree.tag_configure('pending', background='#ffd6d6')

    def load_payment_history(self):
        """Load complete payment history"""
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # Fetch all payments
        self.cursor.execute("""
            SELECT p.id, s.name, s.class, s.contact, p.due_date, p.paid_date, 
                   p.amount, p.status, p.receipt_path, p.payment_mode
            FROM payments p
            JOIN students s ON p.student_id = s.id
            ORDER BY p.created_date DESC
        """
        )
        
        payments = self.cursor.fetchall()
        for i, payment in enumerate(payments):
            row_tag = 'evenrow' if i % 2 == 0 else 'oddrow' # For alternating row colors
            receipt_status = "Yes" if payment[8] else "No"
            display_payment = payment[:8] + (receipt_status, payment[9],) # Append receipt status and payment mode
            status_tag = 'cleared' if payment[7] == 'Cleared' else 'pending' # Corrected index for status
            self.history_tree.insert('', 'end', values=display_payment, tags=(row_tag, status_tag)) # Pass both tags
        self.history_tree.tag_configure('cleared', background='#d4f7d4')
        self.history_tree.tag_configure('pending', background='#ffd6d6')
        self.history_tree.tag_configure('evenrow', background='lightblue') # Ensure these are configured
        self.history_tree.tag_configure('oddrow', background='white')
        self.update_summary_bar()

    def load_class_filter(self):
        """Load unique classes for filter dropdown"""
        self.filter_class['values'] = ['All'] + self.CLASS_OPTIONS
        self.filter_class.set('All')
    
    def apply_filter(self):
        """Apply filters (class, status, date range, search) to payment history"""
        print("[DEBUG] Applying history filter...") # Debug print
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Build query based on filters
        query = """
            SELECT p.id, s.name, s.class, s.contact, p.due_date, p.paid_date,
                   p.amount, p.status, p.receipt_path, p.payment_mode
            FROM payments p
            JOIN students s ON p.student_id = s.id
            WHERE 1=1
        """
        params = []

        if self.filter_class.get() and self.filter_class.get() != 'All':
            query += " AND s.class = ?"
            params.append(self.filter_class.get())

        if self.filter_status.get() != 'All':
            query += " AND p.status = ?"
            params.append(self.filter_status.get())

        # Add date range filter
        start_date = self.filter_start_date_entry.get().strip()
        end_date = self.filter_end_date_entry.get().strip()

        if start_date and end_date:
            query += " AND p.paid_date BETWEEN ? AND ?"
            params.append(start_date)
            params.append(end_date)
        elif start_date:
            query += " AND p.paid_date >= ?"
            params.append(start_date)
        elif end_date:
            query += " AND p.paid_date <= ?"
            params.append(end_date)
            
        # Add search filter
        search_query = self.history_search_entry.get().strip()
        if search_query:
            query += " AND (s.name LIKE ? OR s.class LIKE ? OR s.contact LIKE ?)"
            search_term = f"%{search_query}%"
            params.extend([search_term] * 3)

        query += " ORDER BY p.created_date DESC"

        try:
            self.cursor.execute(query, params)
            payments = self.cursor.fetchall()

            for payment in payments:
                receipt_status = "Yes" if payment[8] else "No"
                display_payment = payment[:8] + (receipt_status, payment[9],) # Append receipt status and payment mode
                tag = 'cleared' if payment[6] == 'Cleared' else 'pending'
                self.history_tree.insert('', 'end', values=display_payment, tags=(tag,))

            self.history_tree.tag_configure('cleared', background='#d4f7d4')
            self.history_tree.tag_configure('pending', background='#ffd6d6')

            self.update_summary_bar()

        except Exception as e:
            messagebox.showerror("Database Error", f"Error applying filter: {e}")
    
    def open_receipt(self, event):
        """Open receipt file when double-clicked"""
        selection = self.history_tree.selection()
        if selection:
            item = self.history_tree.item(selection[0])
            payment_id = item['values'][0]
            
            # Get receipt path from database
            self.cursor.execute("SELECT receipt_path FROM payments WHERE id = ?", (payment_id,))
            result = self.cursor.fetchone()
            
            if result and result[0]:
                self.open_file(result[0])
            else:
                messagebox.showinfo("No Receipt", "No receipt found for this payment.")
    
    def open_receipts_folder(self):
        """Open the receipts folder in file explorer"""
        receipts_path = os.path.abspath("receipts")
        self.open_file(receipts_path)
    
    def open_whatsapp_web(self):
        """Open WhatsApp Web in browser"""
        webbrowser.open("https://web.whatsapp.com")
        messagebox.showinfo("WhatsApp Web", 
                          "WhatsApp Web opened in your browser.\n" +
                          "You can manually attach receipt files from the receipts folder.")
    
    def backup_database(self):
        """Create a backup of the database"""
        try:
            backup_path = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
                title="Save Database Backup"
            )
            
            if backup_path:
                # Copy database file
                import shutil
                shutil.copy2("db/students.db", backup_path)
                messagebox.showinfo("Success", f"Database backed up to:\n{backup_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Error creating backup: {e}")
    
    def export_to_csv(self):
        """Export payment history to CSV"""
        try:
            import csv
            
            csv_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                title="Export Payment History"
            )
            
            if csv_path:
                self.cursor.execute("""
                    SELECT s.name, s.class, s.contact, p.due_date, p.paid_date, 
                           p.amount, p.status, p.created_date, p.payment_mode
                    FROM payments p
                    JOIN students s ON p.student_id = s.id
                    ORDER BY p.created_date DESC
                """)
                
                payments = self.cursor.fetchall()
                
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Student Name', 'Class', 'Contact', 'Due Date', 
                                   'Paid Date', 'Amount', 'Status', 'Created Date', 'Payment Mode'])
                    writer.writerows(payments)
                
                messagebox.showinfo("Success", f"Payment history exported to:\n{csv_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting to CSV: {e}")
    
    def open_file(self, filepath):
        """Open file with default system application"""
        try:
            if sys.platform.startswith('darwin'):  # macOS
                subprocess.call(['open', filepath])
            elif sys.platform.startswith('win'):  # Windows
                os.startfile(filepath)
            else:  # Linux
                subprocess.call(['xdg-open', filepath])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")
    
    def __del__(self):
        """Close database connection when app is destroyed"""
        if hasattr(self, 'conn'):
            self.conn.close()

    def update_fee_info(self, event=None):
        student_info = self.student_combo.get()
        if not student_info:
            self.selected_class.config(state='normal'); self.selected_class.delete(0, tk.END); self.selected_class.config(state='readonly')
            self.selected_contact.config(state='normal'); self.selected_contact.delete(0, tk.END); self.selected_contact.config(state='readonly')
            self.fee_summary_var.set("")
            return
        try:
            student_id = int(student_info.split("ID:")[1])
            self.cursor.execute("SELECT class, contact, mother_name, father_name, parent_number, parent_email FROM students WHERE id = ?", (student_id,))
            row = self.cursor.fetchone()
            class_name, contact, mother_name, father_name, parent_number, parent_email = row if row else ("", "", "", "", "", "")
            self.selected_class.config(state='normal'); self.selected_class.delete(0, tk.END); self.selected_class.insert(0, class_name); self.selected_class.config(state='readonly')
            self.selected_contact.config(state='normal'); self.selected_contact.delete(0, tk.END); self.selected_contact.insert(0, contact); self.selected_contact.config(state='readonly')
            self.cursor.execute("SELECT SUM(amount) FROM payments WHERE student_id = ?", (student_id,))
            paid = self.cursor.fetchone()[0] or 0.0
            total = self.TOTAL_FEE
            remaining = max(total - paid, 0.0)
            self.fee_summary_var.set(f"Total Fee: ₹{total:.2f} | Paid: ₹{paid:.2f} | Remaining: ₹{remaining:.2f}")
        except Exception:
            self.fee_summary_var.set("")

    def pay_full_due(self):
        # Auto-fill the remaining amount
        summary = self.fee_summary_var.get()
        if 'Remaining:' in summary:
            try:
                remaining = float(summary.split('Remaining: ₹')[1].split()[0])
                self.amount.delete(0, tk.END)
                self.amount.insert(0, f"{remaining:.2f}")
            except Exception:
                pass
        else:
            # fallback: try to get from update_fee_info
            self.update_fee_info()

    def show_all_pending(self):
        # Show all students with outstanding pending payments in a popup
        pending_win = tk.Toplevel(self.root)
        pending_win.title("All Outstanding Pending Payments")
        tree = ttk.Treeview(pending_win, columns=("Name", "Class", "Contact", "Pending Amount"), show='headings')
        for col in ("Name", "Class", "Contact", "Pending Amount"):
            tree.heading(col, text=col)
        tree.pack(fill='both', expand=True)

        # Select students and calculate total paid amount
        self.cursor.execute("""
            SELECT s.name, s.class, s.contact, SUM(p.amount) as total_paid
            FROM students s
            LEFT JOIN payments p ON s.id = p.student_id
            GROUP BY s.id, s.name, s.class, s.contact
            HAVING SUM(p.amount) < ? OR SUM(p.amount) IS NULL
            ORDER BY s.class, s.name
        """, (self.TOTAL_FEE,))

        for row in self.cursor.fetchall():
            name, class_name, contact, total_paid = row
            total_paid = total_paid or 0.0 # Handle students with no payments
            pending_amount = self.TOTAL_FEE - total_paid
            tree.insert('', 'end', values=(name, class_name, contact, f"₹{pending_amount:.2f}"))

    def delete_selected_payment(self):
        """Delete the selected payment from the recent payments treeview"""
        selected = self.payment_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a payment to delete.")
            return
        item = self.payment_tree.item(selected[0])
        payment_id = item['values'][0]
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this payment record?"):
            try:
                self.cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
                self.conn.commit()
                self.load_recent_payments()
                self.load_payment_history()
                self.update_fee_info()
                messagebox.showinfo("Deleted", "Payment record deleted successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete payment: {e}")

    def generate_receipt_from_history(self):
        """Generate a receipt for the selected payment in history"""
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a payment record in history.")
            return
        item = self.history_tree.item(selected[0])
        payment_id = item['values'][0]
        # Fetch payment and student info for this payment_id
        self.cursor.execute("""
            SELECT p.*, s.name, s.class, s.contact, s.mother_name, s.father_name, s.parent_number, s.parent_email
            FROM payments p 
            JOIN students s ON p.student_id = s.id 
            WHERE p.id = ?
        """, (payment_id,))
        payment_data = self.cursor.fetchone()
        if not payment_data:
            messagebox.showerror("Error", "Payment record not found.")
            return
        # Generate receipt
        receipt_path = self.create_pdf_receipt(payment_data)
        # Update database with receipt path
        self.cursor.execute(
            "UPDATE payments SET receipt_path = ? WHERE id = ?",
            (receipt_path, payment_id)
        )
        self.conn.commit()
        # Ask if user wants to open the receipt
        if messagebox.askyesno("Receipt Generated", 
                             f"Receipt saved as:\n{receipt_path}\n\nWould you like to open the Receipts folder to send it via WhatsApp?"): # Modified message
            self.open_receipts_folder() # Open folder instead of file directly
            # Add prompt to open WhatsApp Web
            if messagebox.askyesno("Send via WhatsApp", "Would you like to open WhatsApp Web now to send the receipt?"):
                self.open_whatsapp_web()
        # Refresh displays
        self.load_recent_payments()
        self.load_payment_history()

    def filter_payments_tree(self, status):
        # Filter recent payments by status
        for item in self.payment_tree.get_children():
            self.payment_tree.delete(item)
        query = '''SELECT p.id, s.name, s.class, p.due_date, p.paid_date, p.amount, p.status, p.payment_mode FROM payments p JOIN students s ON p.student_id = s.id'''
        params = []
        if status != 'All':
            query += ' WHERE p.status = ?'
            params.append(status)
        query += ' ORDER BY p.created_date DESC LIMIT 20'
        self.cursor.execute(query, params)
        payments = self.cursor.fetchall()
        for payment in payments:
            tag = 'cleared' if payment[6] == 'Cleared' else 'pending'
            # We are adding payment_mode to the end of the payment tuple, so it is at index 7.
            # The treeview columns now expect 8 values, so we should pass all of them.
            self.payment_tree.insert('', 'end', values=payment, tags=(tag,))
        self.payment_tree.tag_configure('cleared', background='#d4f7d4')
        self.payment_tree.tag_configure('pending', background='#ffd6d6')

    def filter_history_tree(self, status):
        # Filter payment history by status
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        query = '''SELECT p.id, s.name, s.class, s.contact, p.due_date, p.paid_date, p.amount, p.status, p.receipt_path, p.payment_mode FROM payments p JOIN students s ON p.student_id = s.id'''
        params = []
        if status != 'All':
            query += ' WHERE p.status = ?'
            params.append(status)
        query += ' ORDER BY p.created_date DESC'
        self.cursor.execute(query, params)
        payments = self.cursor.fetchall()
        for i, payment in enumerate(payments):
            row_tag = 'evenrow' if i % 2 == 0 else 'oddrow' # For alternating row colors
            status_tag = 'cleared' if payment[7] == 'Cleared' else 'pending' # Corrected index for status
            receipt_status = 'Yes' if payment[8] else 'No' # Corrected index for receipt_path
            display_payment = payment[:8] + (receipt_status, payment[9],) # Append receipt status and payment mode
            self.history_tree.insert('', 'end', values=display_payment, tags=(row_tag, status_tag))
        self.history_tree.tag_configure('cleared', background='#d4f7d4')
        self.history_tree.tag_configure('pending', background='#ffd6d6')
        self.history_tree.tag_configure('evenrow', background='lightblue') # Ensure these are configured
        self.history_tree.tag_configure('oddrow', background='white')

    def update_summary_bar(self):
        # Show total due and total cleared amounts based on overall student payment status
        # Calculate total paid per student
        self.cursor.execute("""
            SELECT student_id, SUM(amount) as total_paid
            FROM payments
            GROUP BY student_id
        """)
        student_totals = dict(self.cursor.fetchall())

        total_pending_amount = 0.0
        total_cleared_value = 0.0 # Represents the sum of TOTAL_FEE for cleared students

        self.cursor.execute("SELECT id FROM students") # Get all student IDs
        all_student_ids = [row[0] for row in self.cursor.fetchall()]

        for student_id in all_student_ids:
            paid = student_totals.get(student_id, 0.0)
            if paid < self.TOTAL_FEE:
                total_pending_amount += (self.TOTAL_FEE - paid)
            else:
                total_cleared_value += paid # Student has paid full fee or more, sum the actual paid amount

        self.summary_var.set(f'Total Pending: ₹{total_pending_amount:.2f}    |    Total Cleared: ₹{total_cleared_value:.2f}')

    def update_payment_student_list(self, event=None):
        # Update student list in combo and auto-complete based on class filter
        selected_class = self.payment_class_filter.get()
        if selected_class == 'All':
            self.cursor.execute("SELECT id, name, class FROM students ORDER BY class, name")
        else:
            self.cursor.execute("SELECT id, name, class FROM students WHERE class = ? ORDER BY name", (selected_class,))
        students = self.cursor.fetchall()
        student_list = [f"{s[1]} ({s[2]}) - ID:{s[0]}" for s in students]
        self.student_combo['values'] = student_list
        self.autocomplete_student_names = [s[1] for s in students]
        self.student_search_var.set("")
        self.student_search_suggestions.pack_forget()

    def autocomplete_student_search(self, event=None):
        # Show suggestions in the listbox
        query = self.student_search_var.get().lower()
        if not hasattr(self, 'autocomplete_student_names'):
            self.update_payment_student_list()
        matches = [name for name in self.autocomplete_student_names if query in name.lower()]
        if matches and query:
            self.student_search_suggestions.delete(0, tk.END)
            for name in matches:
                self.student_search_suggestions.insert(tk.END, name)
            self.student_search_suggestions.place(x=self.student_search.winfo_x(), y=self.student_search.winfo_y()+self.student_search.winfo_height())
            self.student_search_suggestions.lift()
            self.student_search_suggestions.pack(side='left', padx=5)
        else:
            self.student_search_suggestions.pack_forget()

    def select_autocomplete_student(self, event=None):
        # Set the student_combo to the selected name
        if self.student_search_suggestions.size() > 0 and self.student_search_suggestions.curselection():
            selected_name = self.student_search_suggestions.get(self.student_search_suggestions.curselection()[0])
        else:
            selected_name = self.student_search_var.get()
        # Find the matching student in the combo
        for val in self.student_combo['values']:
            if val.startswith(selected_name + ' '):
                self.student_combo.set(val)
                self.update_fee_info()
                break
        self.student_search_suggestions.pack_forget()

    def import_students_csv(self):
        """Import students from a CSV file with columns: name, class, contact, mother_name, father_name, parent_number, parent_email"""
        import csv
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        count = 0
        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = row.get('name', '').strip()
                    class_name = row.get('class', '').strip()
                    contact = row.get('contact', '').strip()
                    mother_name = row.get('mother_name', '').strip()
                    father_name = row.get('father_name', '').strip()
                    parent_number = row.get('parent_number', '').strip()
                    parent_email = row.get('parent_email', '').strip()
                    if not name or not class_name:
                        continue  # skip incomplete rows
                    try:
                        self.cursor.execute(
                            "INSERT INTO students (name, class, contact, mother_name, father_name, parent_number, parent_email) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (name, class_name, contact, mother_name, father_name, parent_number, parent_email)
                        )
                        count += 1
                    except Exception:
                        continue
                self.conn.commit()
            self.load_students()
            self.load_student_combo()
            messagebox.showinfo("Import Complete", f"Imported {count} students from CSV.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import: {e}")

    def save_student_changes(self):
        """Save changes to an existing student or add a new one"""
        name = self.student_name.get().strip()
        class_name = self.student_class.get().strip()
        contact = self.student_contact.get().strip()
        mother_name = self.mother_name.get().strip()
        father_name = self.father_name.get().strip()
        parent_number = self.parent_number.get().strip()
        parent_email = self.parent_email.get().strip()

        if not name or not class_name:
            messagebox.showerror("Error", "Name and Class are required fields!")
            return

        try:
            if self.selected_student_id is None:
                # Add new student
                self.cursor.execute(
                    "INSERT INTO students (name, class, contact, mother_name, father_name, parent_number, parent_email) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, class_name, contact, mother_name, father_name, parent_number, parent_email)
                )
                self.conn.commit()
                messagebox.showinfo("Success", f"Student '{name}' added successfully!")
            else:
                # Update existing student
                self.cursor.execute(
                    """UPDATE students SET name = ?, class = ?, contact = ?, mother_name = ?, father_name = ?, parent_number = ?, parent_email = ? WHERE id = ?""",
                    (name, class_name, contact, mother_name, father_name, parent_number, parent_email, self.selected_student_id)
                )
                self.conn.commit()
                messagebox.showinfo("Success", f"Student '{name}' updated successfully!")

            # Refresh displays and clear form
            self.load_students()
            self.load_student_combo()
            self.clear_student_form()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error saving student: {e}")

    def clear_student_form(self):
        """Clear the student form fields and reset button text"""
        self.student_name.delete(0, tk.END)
        self.student_class.set('')
        self.student_contact.delete(0, tk.END)
        self.mother_name.delete(0, tk.END)
        self.father_name.delete(0, tk.END)
        self.parent_number.delete(0, tk.END)
        self.parent_email.delete(0, tk.END)
        self.add_update_button.config(text="Add Student")
        self.selected_student_id = None

    def select_student_for_edit(self, event=None):
        """Load selected student data into the form for editing"""
        selected_item = self.student_tree.focus()
        if not selected_item:
            return # No item selected

        values = self.student_tree.item(selected_item, 'values')
        # Values are: ID, Name, Class, Contact, Mother Name, Father Name, Parent Number, Parent Email, Created Date
        student_id = values[0]
        name = values[1]
        class_name = values[2]
        contact = values[3]
        mother_name = values[4]
        father_name = values[5]
        parent_number = values[6]
        parent_email = values[7]

        # Populate form fields
        self.clear_student_form() # Clear first
        self.student_name.insert(0, name)
        self.student_class.set(class_name)
        self.student_contact.insert(0, contact)
        self.mother_name.insert(0, mother_name)
        self.father_name.insert(0, father_name)
        self.parent_number.insert(0, parent_number)
        self.parent_email.insert(0, parent_email)

        # Set the button text and store the selected student's ID
        self.add_update_button.config(text="Save Changes")
        self.selected_student_id = student_id

    def delete_selected_student(self):
        """Delete the selected student from the database"""
        selected_item = self.student_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "Please select a student to delete.")
            return

        values = self.student_tree.item(selected_item, 'values')
        student_id = values[0]
        student_name = values[1]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete student '{student_name}'\n\nNote: This will NOT delete associated payment records."):
            try:
                # Note: This only deletes the student record. Associated payments will remain
                # linked to a non-existent student ID. For a robust application, you might
                # want to also delete related payments or handle them differently.
                self.cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
                self.conn.commit()
                self.load_students()
                self.load_student_combo()
                self.clear_student_form() # Clear form if the deleted student was being edited
                messagebox.showinfo("Deleted", f"Student '{student_name}' deleted successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete student: {e}")

    def open_calendar(self, date_entry):
        """Opens a calendar popup to select a date for the given entry widget."""
        top = tk.Toplevel(self.root)
        top.transient(self.root)
        top.grab_set()
        
        # Position the calendar near the entry field (basic positioning)
        # You might want more sophisticated positioning
        x = self.root.winfo_x() + date_entry.winfo_x()
        y = self.root.winfo_y() + date_entry.winfo_y() + date_entry.winfo_height()
        top.geometry(f"300x200+{x}+{y}")
        
        cal = Calendar(top, selectmode='day', date_pattern='yyyy-mm-dd')
        cal.pack(pady=10)
        
        def on_date_select():
            selected_date = cal.get_date()
            print(f"[DEBUG] Selected date from calendar: {selected_date}") # Debug print
            date_entry.delete(0, tk.END)
            date_entry.insert(0, selected_date)
            top.destroy()
            
        ttk.Button(top, text="Select Date", command=on_date_select).pack()

    def clear_history_search(self):
        """Clear the history search entry and reload all payments"""
        self.history_search_entry.delete(0, tk.END)
        self.load_payment_history()

def main():
    # Check if required packages are installed
    try:
        import reportlab
    except ImportError:
        print("Installing required package: reportlab")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
        import reportlab
    
    root = tk.Tk()
    app = FeeReceiptApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()