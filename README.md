# Beginner Python Portfolio Dashboard

A simple Streamlit app for entering investments and viewing:

- Total portfolio value
- Profit or loss
- Return percentage
- The weight of each holding in the portfolio

Prices are entered manually, so no brokerage account or API key is needed.

## Requirements

- Python 3.10 or newer
- Visual Studio Code
- The Python extension for VS Code

## Set up the project in VS Code

1. Open this folder in VS Code.
2. Open the VS Code terminal with **Terminal > New Terminal**.
3. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

4. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   On macOS or Linux, use `source .venv/bin/activate` instead.

5. Install the required packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Start the dashboard:

   ```powershell
   python -m streamlit run app.py
   ```

Streamlit will print a local address, usually `http://localhost:8501`, and should
open it in your browser automatically.

You can also press **F5** in VS Code and choose **Run Portfolio Dashboard** after
installing the dependencies and selecting the `.venv` Python interpreter.

## How to use it

1. Enter a ticker such as `AAPL`.
2. Enter how many shares you own.
3. Enter the price paid for each share.
4. Enter its current price.
5. Select **Add to portfolio**.

Add more investments to see how much each one contributes to the total portfolio.
The data stays available while the browser session is open, but it is not saved to
a file when the app closes.

## Project files

- `app.py` contains the dashboard and calculations.
- `requirements.txt` lists the Python packages to install.
- `.vscode/launch.json` lets you start the app with the VS Code debugger.
