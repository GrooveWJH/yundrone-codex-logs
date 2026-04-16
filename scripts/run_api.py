from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from switchbase_teamview.api import main


if __name__ == "__main__":
    main()
