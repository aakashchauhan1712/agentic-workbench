"""
Smoke-test: import all project modules and check for syntax errors.
Run from the agentic_workbench/ directory.
"""
import sys, os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")
sys.path.insert(0, os.path.dirname(__file__))

errors = []

modules_to_test = [
    "core.config",
    "core.conversation_store",
    "core.agent",
    "tools.review_skills",
    "utils.helpers",
]

for mod in modules_to_test:
    try:
        import importlib
        importlib.import_module(mod)
        print(f"  [OK] {mod}")
    except Exception as e:
        print(f"  [FAIL] {mod}: {e}")
        errors.append((mod, e))

if errors:
    print(f"\n{len(errors)} module(s) failed to import.")
    sys.exit(1)
else:
    print("\nAll modules imported successfully.")
