from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from switchbase_teamview.feishu_group_reporter_main import main


if __name__ == "__main__":
    main()
