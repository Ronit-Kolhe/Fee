# Fee Receipt Generator

This is a desktop application built with Python's Tkinter library to manage student fee payments and generate PDF receipts. It's designed for small educational institutions to keep track of student data, payments, and payment history in an offline environment.

## Features

- **Student Management:** Add, update, delete, and search for student records.
- **Fee Payment Tracking:** Record fee payments for each student.
- **PDF Receipt Generation:** Automatically generate and save PDF receipts for payments.
- **Payment History:** View a complete history of all transactions with filtering options.
- **Data Import/Export:** Import student data from a CSV file and export payment history to a CSV file.
- **Data Backup:** Create a backup of the application's database.
- **User-Friendly Interface:** A tabbed interface makes it easy to navigate between different functionalities.

## Setup and Installation

1.  **Prerequisites:**
    * Python 3.x

2.  **Clone the repository or download the source code:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

3.  **Install the required libraries:**
    Open your terminal or command prompt and run the following command to install the necessary packages from the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Directory Structure:**
    The application expects the following directory structure. It will create these folders automatically when you first run the application.
    ```
    /
    |-- main.py
    |-- requirements.txt
    |-- db/
    |   |-- students.db
    |-- receipts/
    |-- templates/
        |-- logo.png
    ```
    * Place your school's logo in the `templates` folder and name it `logo.png`.
    * If you have the `Arial.ttf` font file, place it in the `templates` folder to ensure the Rupee symbol (₹) renders correctly on the PDF receipts.

## How to Run the Application

1.  Navigate to the directory where `main.py` is located.
2.  Run the following command in your terminal:
    ```bash
    python main.py
    ```

## How to Use the Application

-   **Student Management Tab:**
    -   Fill in the form on the left to add a new student.
    -   Select a student from the list on the right to edit or delete their information.
    -   Use the search bar to find specific students.
    -   Import a list of students using the "Import from CSV" button.

-   **Fee Payment Tab:**
    -   Select a student from the dropdown menu.
    -   Their fee summary (Total, Paid, Remaining) will be displayed.
    -   Enter the amount being paid and the payment date.
    -   Click "Record Payment" to save the transaction.
    -   Click "Generate Receipt" to create a PDF receipt for the last recorded payment.

-   **Payment History Tab:**
    -   View a list of all payment transactions.
    -   Use the filters at the top to narrow down the results by class, payment status, or date range.
    -   Double-click on a payment record to open the associated receipt if it exists.
    -   Export the filtered view to a CSV file.

-   **Settings Tab:**
    -   Open the `receipts` folder directly.
    -   Backup the entire student database.
    -   Open WhatsApp Web to easily share receipts.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
