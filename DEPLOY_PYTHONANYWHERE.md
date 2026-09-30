# Deploy SmartStudy to PythonAnywhere + MySQL

This deployment uses standard Flask/WSGI plus eight-second browser polling for live platform activity. It is reliable on ordinary PythonAnywhere web apps; WebSockets/Socket.IO are still an experimental PythonAnywhere feature.

## 1. Create the MySQL database

1. Create a paid PythonAnywhere account (new free accounts do not include MySQL).
2. Open **Databases → MySQL**, set a MySQL password, and create a database named `smartstudy`.
3. Note the MySQL host, username, and full database name displayed there. The database normally has the form `YOUR_USERNAME$smartstudy`.

## 2. Upload the project and create a virtual environment

From a PythonAnywhere Bash console:

```bash
cd ~
unzip smart-study-resource-management.zip -d smartstudy
cd smartstudy
mkvirtualenv --python=/usr/bin/python3.12 smartstudy-env
pip install -r requirements.txt
```

Create `~/.smartstudy.env` (never upload this file to Git):

```env
SECRET_KEY=generate-a-long-random-value
DATABASE_URL=mysql+pymysql://YOUR_MYSQL_USER:YOUR_MYSQL_PASSWORD@YOUR_MYSQL_HOST/YOUR_USERNAME$smartstudy
UPLOAD_DIR=/home/YOUR_USERNAME/smartstudy/uploads
```

Load it before initialising:

```bash
set -a; source ~/.smartstudy.env; set +a
python -c "from app import initialize_database; initialize_database()"
```

## 3. Configure the web app

1. Open **Web → Add a new web app → Manual configuration** and select Python 3.12.
2. Set the virtual environment to `/home/YOUR_USERNAME/.virtualenvs/smartstudy-env`.
3. Edit the generated WSGI file and put the following before importing the app:

```python
import os, sys
from pathlib import Path

project_home = "/home/YOUR_USERNAME/smartstudy"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

for line in Path("/home/YOUR_USERNAME/.smartstudy.env").read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        os.environ[key] = value

from app import app as application
```

4. In **Static files**, map `/static/` to `/home/YOUR_USERNAME/smartstudy/static/`.
5. Click **Reload**. Your public app will be at `https://YOUR_USERNAME.pythonanywhere.com`.

## Live updates and operating notes

- Every logged-in dashboard polls `/api/live-activity` every 8 seconds. Uploads, views, downloads, and bookmarks are persisted in MySQL and then appear to every user.
- The app configures SQLAlchemy `pool_recycle=280` because PythonAnywhere closes idle MySQL connections after five minutes.
- Run database setup only from a Bash console using `initialize_database()`, never in the WSGI import path.
- Uploaded resources are stored in the persistent `UPLOAD_DIR` set above and are retrieved through the application’s preview/download routes. Back up this directory alongside MySQL. For production-scale PDFs, move uploads to S3/Cloudinary.
