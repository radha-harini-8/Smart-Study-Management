# Smart Study Resource Management

An intelligent academic resource platform built with Flask, SQLAlchemy, HTML, CSS and vanilla JavaScript. It goes beyond folders by using metadata, search, ratings, activity, bookmarks, recommendations and AI-style revision summaries.

## Run locally

1. Install Python 3.10+ and create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Optionally copy `.env.example` to `.env` and configure a production secret or MySQL URL.
3. Start the app:
   ```bash
   python app.py
   ```
4. Open `http://127.0.0.1:5000`.

SQLite is the default, so no database setup is needed for the prototype. It seeds departments, subjects, representative resources, ratings, and these accounts:

| Role | Email | Password |
| --- | --- | --- |
| Student | student@smartstudy.test | student123 |
| Faculty | faculty@smartstudy.test | faculty123 |
| Admin | admin@smartstudy.test | admin123 |

## MySQL

Create a database by running `schema.sql`, then set the following in `.env`:

```env
DATABASE_URL=mysql+pymysql://username:password@localhost/smart_study
```

The application creates its mapped tables at first boot and seeds a working starter dataset. Uploaded files are stored in `static/uploads/`; configure external object storage before a production deployment.

## Core capabilities

- Secure hashed-password login plus student, faculty, and admin roles.
- Rich resource upload metadata and hierarchy filters.
- Dedicated previous-question-paper library.
- Multi-term search and type/department/subject/unit filters with autocomplete.
- Bookmark and one-rating-per-user APIs.
- Activity-aware, subject/tag-aligned content recommendations.
- On-demand local AI-style summary cards, designed to remain functional without an external API key.
- Users can add new courses while uploading; course metadata is saved and available in future uploads.
- Uploaded files are stored with unique filenames, and can later be previewed or downloaded from the matching resource page.

For a production AI model, replace the deterministic generator in `generate_summary` in `app.py` with the provider SDK of choice; retain the existing stored `Summary` output contract.
