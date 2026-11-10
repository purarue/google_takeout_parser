from click.testing import CliRunner

from google_takeout_parser.__main__ import main


def test_move_rejects_non_zip_file(tmp_path):
    not_zip = tmp_path / "takeout.txt"
    not_zip.write_text("not a zip")
    runner = CliRunner()
    result = runner.invoke(
        main, ["move", "--from", str(not_zip), "--to-dir", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)
    assert "expected a .zip file" in result.output
