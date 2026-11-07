# Put Blink Bird on GitHub

## Easiest: browser upload to a new repository
1. Download and extract **blink-bird.zip**.
2. On GitHub, choose **New repository** and name it, for example, **blink-bird**.
   Choose Public or Private. For the terminal method below, leave the repository
   empty (do not initialize a README, license or .gitignore).
3. Open the repository and select **uploading an existing file**, or
   **Add file → Upload files**.
4. Upload the **contents** of the extracted blink-bird folder. Preserve the
   assets, blinkbird, tests and docs subfolders. The repository root should contain
   main.py and README.md, not another enclosing blink-bird folder.
5. Include .gitignore (your file browser may hide it). Do not upload .venv,
   __pycache__, personal EEG recordings, or credentials.
6. Enter a message such as "Add redesigned Blink Bird" and commit.
   Upload the extracted files, not only the ZIP.

GitHub stores the source; this desktop pygame application is run locally.
GitHub Pages cannot run it as a Python desktop game.

## Terminal: a new empty repository
From inside the extracted folder:
```bash
git init
git add .
git commit -m "Add responsive Blink Bird with guided calibration"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```
Replace both placeholders with your GitHub username and repository name.
Use GitHub's supported sign-in flow or a personal access token when prompted;
do not put credentials in source files.

## Existing repository (recommended: use a branch)
Clone your own repository into a separate folder:
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
git switch -c blink-bird-redesign
```
Copy the contents of the extracted project into this checkout. Review existing
files before overwriting. Older game.py, inputs.py, muse_input.py and root
test_*.py are not used by the new launcher; archive or remove them deliberately
to avoid maintaining two conflicting implementations. The new entry point is
**python main.py**.

Then:
```bash
python -m pip install -r requirements-muse.txt
python -m unittest discover -s tests -v
git status
git diff
git add .
git commit -m "Redesign Blink Bird and improve blink responsiveness"
git push -u origin blink-bird-redesign
```
Open the branch on GitHub, choose **Compare & pull request**, review and merge.
Do not force-push over existing work.

You do not need to fork the reference repository: this package is standalone.
If modifying a fork, use the same branch workflow and make this project's
main.py the entry point.
