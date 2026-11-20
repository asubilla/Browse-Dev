from __future__ import annotations

from pathlib import Path

from browse_dev.profiles import handle


def test_profile_lifecycle(monkeypatch, tmp_path, capsys):
	monkeypatch.setenv('BROWSE_DEV_CONFIG_DIR', str(tmp_path))
	assert handle(['save', 'work']) == 0
	created = Path(capsys.readouterr().out.strip())
	assert created.is_dir()

	assert handle(['list']) == 0
	assert 'work *' in capsys.readouterr().out

	assert handle(['save', 'other']) == 0
	capsys.readouterr()  # the save printed the path; clear before checking `use`
	assert handle(['use', 'other']) == 0
	chosen = capsys.readouterr().out.strip()
	assert chosen == str(tmp_path / 'profiles' / 'other')

	assert handle(['list']) == 0
	listed = capsys.readouterr().out
	assert 'other *' in listed and 'work  ' in listed and 'work *' not in listed

	assert handle(['remove', 'other']) == 0
	assert handle(['list']) == 0
	listed = capsys.readouterr().out
	assert 'work *' in listed and 'other' not in listed


def test_register_an_existing_user_data_dir_in_place(monkeypatch, tmp_path, capsys):
	monkeypatch.setenv('BROWSE_DEV_CONFIG_DIR', str(tmp_path / 'config'))
	source = tmp_path / 'my-chrome-profile'
	source.mkdir()
	assert handle(['save', 'mine', str(source)]) == 0
	assert capsys.readouterr().out.strip() == str(source)
	assert handle(['use', 'mine']) == 0
	assert capsys.readouterr().out.strip() == str(source)


def test_invalid_commands_fail_cleanly(monkeypatch, tmp_path, capsys):
	monkeypatch.setenv('BROWSE_DEV_CONFIG_DIR', str(tmp_path))
	assert handle(['save', 'bad name!']) == 1
	assert 'letters, digits' in capsys.readouterr().err
	assert handle(['use', 'missing']) == 1
	assert 'unknown profile' in capsys.readouterr().err
	assert handle(['nope']) == 2
