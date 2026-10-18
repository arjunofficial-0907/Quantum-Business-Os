### 1. Navigate to the backend

```powershell
cd backend
```

### 2. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies (first time only)

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

Make sure the required `.env` file is configured in the `backend` directory.

### 5. Start the server

```powershell
python -m uvicorn app.main:app --reload
```

### 6. Open the API documentation

- **API:** http://127.0.0.1:8000
- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

### 7. Stop the server

Press `Ctrl + C` in the terminal.

**Note:** Ensure your database and other required services are running before starting the backend.
