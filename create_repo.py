import os

# Define the folder structure
structure = {
    "main": ["bot.py"],
    "": ["config.py"],  # root-level file
    "database": ["db.py"],
    "handlers": [
        "onboarding.py",
        "payment.py",
        "delivery.py",
        "dashboard.py",
        "admin.py",
        "fallback.py",
    ],
    "keyboards": ["reply.py", "inline.py"],
    "middlewares": ["language.py", "throttling.py", "error.py"],
    "utils": ["localization.py", "product_matcher.py", "helpers.py"],
    "docker": [],  # you can add Dockerfile later
}

def create_structure(base_path="."):
    for folder, files in structure.items():
        folder_path = os.path.join(base_path, folder)
        if folder:  # skip root
            os.makedirs(folder_path, exist_ok=True)
        for file in files:
            file_path = os.path.join(folder_path, file)
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("# " + file + "\n")
                print(f"Created {file_path}")

if __name__ == "__main__":
    create_structure()
    print("✅ Project structure created successfully!")
