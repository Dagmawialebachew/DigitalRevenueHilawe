import ast

with open("meal_plan/documents/html_pdf_renderer.py", encoding="utf-8") as f:
    text = f.read()

lines = text.splitlines(keepends=True)

# Find first line index where ast.parse fails
for n in range(1200, len(lines), 50):
    try:
        ast.parse("".join(lines[:n]))
    except SyntaxError as e:
        print(f"Failed at n={n}: {e.msg} (line {e.lineno})")
        # now binary search between n-50 and n
        low = n - 50
        high = n
        while low < high:
            mid = (low + high) // 2
            try:
                ast.parse("".join(lines[:mid]))
                low = mid + 1
            except SyntaxError:
                high = mid
        print(f"First failing line count: {low}")
        # print around line low
        for j in range(max(0, low - 5), min(len(lines), low + 5)):
            print(f"{j+1}: {repr(lines[j])}")
        break
