import json
import sys

text = sys.stdin.read()
parsed = json.loads(text)
obj = parsed
if isinstance(parsed, dict) and "products" in parsed:
    obj = parsed["products"]
print(type(obj), obj.__class__)
print(obj if isinstance(obj, dict) else obj[0])
