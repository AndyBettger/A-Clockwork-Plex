# Testing A Clockwork Plex

Run tests with the same project virtual environment used by the dashboard service. Do not use bare system `python3`, because Raspberry Pi OS may not have Flask installed globally.

From the repository root:

```bash
bash scripts/run-tests.sh
```

The runner searches for, in order:

1. the currently activated virtual environment;
2. `venv/bin/python`;
3. `.venv/bin/python`.

It then:

- verifies that Flask is installed in the selected environment;
- compiles the application modules;
- runs the Python unit and API tests;
- runs JavaScript syntax checks when Node.js is available.

To run the Python suite directly:

```bash
venv/bin/python -m unittest discover -s tests -v
```

To install or refresh dependencies in the project environment:

```bash
venv/bin/python -m pip install -r requirements.txt
```

The alarm scheduler remains disabled during the configuration-model test phase, so running these tests cannot trigger an alarm.
