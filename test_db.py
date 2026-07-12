from core.database import engine

try:
    with engine.connect() as conn:
        print("✅ Database connection successful!")
except Exception as e:
    print("❌ Database connection failed:", e)