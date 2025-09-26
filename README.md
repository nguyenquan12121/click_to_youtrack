# GitHub Issues → YouTrack Importer

This project allows you to fetch **open issues from a GitHub repository** and import them into **YouTrack** as tasks using the YouTrack REST API.

---

## Quickstart

- Clone the repo

### Windows

- Run `.\start.bat`

### Linux,MacOS

- Run `./start.sh`, make sure to `chmod` first

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

## Showcase

- Authenticating with youtrack
  ![alt text](screenshots/1.png)
- Successfull github repository search
  ![alt text](screenshots/2.png)
- Selecting 3 issues then importing them leads to this prompt
  ![alt text](screenshots/3.png)
- Successfull issue import
  ![alt text](screenshots/4.png)
- Logging into Youtrack, the 3 issues have been imported (newly starred ones)
  ![alt text](screenshots/5.png)
- Title, Description, Status, State have been imported
  ![alt text](screenshots/6.png)
- Imported issues are colored green
  ![alt text](screenshots/7.png)
- Use `Check Sync Status` to see if the issues are updated on github. Use `Sync All Mapped Issues` push new issues to Youtrack
  ![alt text](screenshots/8.png)
