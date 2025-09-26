# GitHub Issues → YouTrack Importer

This project allows you to fetch **open issues from a GitHub repository** and import them into **YouTrack** as tasks using the YouTrack REST API.

---

## Quickstart

- Clone the repo
- **Windows**  
  Run `.\start.bat`
- **Linux,MacOS**
  Run `./start.sh`, make sure to `chmod` first

## Usage

- Generate a YouTrack permanent token following JetBrains’ guide:
  [Authentication with Permanent Token](https://www.jetbrains.com/help/youtrack/devportal/Manage-Permanent-Token.html)

- Save the token to a text file (e.g. youtrack_token.txt).
  The application will prompt you to provide this token when needed.

- Run the app and follow the prompts to import GitHub issues into YouTrack.

## Development

### Windows:

- `python -m venv .venv`
- `.\.venv\Scripts\Activate.ps1`

### MacOS/Linux:

- `python3 -m venv .venv`
- `source .venv/bin/activate`

- Install dependencies: `pip install -r requirements.txt`

- Start the server: `python src/app.py`
