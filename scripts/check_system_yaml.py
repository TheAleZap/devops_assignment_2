"""Check that system.yaml matches the code (the schema only checks its format).

For each service: the folders and OpenAPI file exist, port_default equals the default in config.py,
the env section lists exactly the variables config.py reads, and every endpoint in `calls`
exists in the called service's OpenAPI document. Exits with 1 and lists the problems otherwise.
Run from the repository root: python scripts/check_system_yaml.py
"""
import json
import re
import sys
from pathlib import Path

import yaml


def check(system):
    problems = []
    for name, service in system["services"].items():
        for key in ("path", "openapi", "migrations"):
            if not Path(service[key]).exists():
                problems.append(f"{name}: {key} {service[key]} does not exist")
        config = Path(service["path"], "config.py").read_text(encoding="utf-8")
        read = set(re.findall(r'os\.environ\.get\("([A-Z0-9_]+)"', config))
        listed = set(service["env"])
        if read != listed:
            problems.append(f"{name}: env in config.py {sorted(read)} != env in system.yaml {sorted(listed)}")
        port = re.search(r'os\.environ\.get\("PORT", "(\d+)"\)', config)
        if port is None or int(port.group(1)) != service["port_default"]:
            problems.append(f"{name}: port_default {service['port_default']} does not match config.py")
        for call in service.get("calls", []):
            target = json.loads(Path(system["services"][call["service"]]["openapi"]).read_text(encoding="utf-8"))
            for endpoint in call["endpoints"]:
                method, path = endpoint.split(" ", 1)
                if method.lower() not in target["paths"].get(path, {}):
                    problems.append(f"{name}: calls {endpoint}, which is not in {call['service']}'s OpenAPI document")
    return problems


if __name__ == "__main__":
    problems = check(yaml.safe_load(Path("system.yaml").read_text(encoding="utf-8")))
    for problem in problems:
        print("ERROR:", problem)
    if problems:
        sys.exit(1)
    print("system.yaml matches the code")
